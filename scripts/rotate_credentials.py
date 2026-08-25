#!/usr/bin/env python3
"""rotate_credentials.py — replace every credential in .env, IN PLACE, on a live platform.

WHY THIS EXISTS, AND WHY IT IS NOT `make destroy`
-------------------------------------------------
The PO asked (AWAITING_PO 2026-08-24-5, answer 2) for the platform's credentials
to be rotated before the repository goes public, and said explicitly that an
IN-PLACE rotation is preferred over a rebuild:

    "an in-place secret rotation is preferred over a rebuild of the stateful
     cluster if one is available, since a full restore over a dead platform is
     still un-rehearsed."

That last clause is the whole argument. `make destroy` + redeploy regenerates
every credential in one command — and takes every PVC with it: the MLflow
registry, the one Postgres holding five tenants, the MinIO objects, the Feast
online store. `make restore-drill` rehearses a restore into SCRATCH databases
and no further (M6-S5); a full restore over a dead platform has never been
performed. So the cheap path spends state whose recovery is unproven, and this
script is the expensive path that spends none of it.

WHAT A CREDENTIAL IS, HERE
--------------------------
`.env` holds 27 keys and only 12 of them are secrets. The rest are IDENTITIES
(`AWS_ACCESS_KEY_ID=mlflow` is a username), endpoints, a region and a bucket
name. Rotating an identity is not a rotation, it is a rename — it would orphan
the MinIO user the chart creates and the Postgres role that owns a database.
So every key is CLASSIFIED, and:

    A KEY THIS SCRIPT DOES NOT RECOGNISE IS A FAILURE, NEVER A SKIP.

That is the one design decision worth reading twice. A rotation that silently
passes over a credential added after it was written is worse than no rotation
at all: it reports success, the operator believes every secret is new, and one
old value lives on with nothing saying so. F-048's rule (an unresolvable value
fails loudly rather than resolving to something convenient), applied to a
credential inventory instead of to a divisor.

THE ORDER, AND THE WINDOW IT ACCEPTS
------------------------------------
Per family: BACKING SERVICE first, then `.env` + the Kubernetes Secret, then the
consumers restart. Between the first and the third step the platform holds a
credential its clients have not been told about — a real mismatch window, which
the charter accepts on a laptop and which this script records rather than hides.
What is NOT accepted is ending with any pair disagreeing, and that is what the
accept sweep (all ten gates) is for.

Postgres is the one family where `.env` is written BEFORE the service changes,
and that is deliberate: `scripts/postgres_databases.sh` is the ONE recipe in
this repo that owns role passwords (it has ALTER'd them to `.env` on every run
since M1-S4), and a second ALTER path living here would be its twin. This repo
deletes twins. The cost is the window, and the undo is `.env.pre-rotation`.

NOTHING IS EVER ECHOED
----------------------
No value is printed, logged, put in argv, or written to the record — not the
new one and not the old one. Secrets reach `psql` and `mc` on STDIN only
(`postgres_databases.sh`'s law, because argv is visible to `ps` inside the pod
and to a kubectl audit log). The record says what rotated, never to what.

Usage:
  scripts/rotate_credentials.py --plan               enumerate + classify, touch nothing
  scripts/rotate_credentials.py                      rotate every family
  scripts/rotate_credentials.py --families postgres  rotate one family (safe stopping point)
  scripts/rotate_credentials.py --verify-old-refused prove the PRE-rotation values are dead
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import secrets as pysecrets
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = pathlib.Path(os.environ.get("ENV_FILE", REPO / ".env"))
PRE_ROTATION = REPO / ".env.pre-rotation"
RECORD = REPO / "automation" / "runs" / "m9-publish" / "rotation.json"
KUBECTL = ["kubectl", "--context", os.environ.get("KUBE_CONTEXT", "kind-mlops-taxi")]

# --------------------------------------------------------------- the inventory ---
# Each rotatable key with the family that owns its in-place mechanism. The family
# names are the CLI's `--families` vocabulary and the record's keys.
ROTATE: dict[str, str] = {
    # Postgres role passwords. The superuser is in the same family but has no
    # recipe of its own — see rotate_postgres().
    "POSTGRES_PASSWORD": "postgres",
    "MLFLOW_DB_PASSWORD": "postgres",
    "MARTS_DB_PASSWORD": "postgres",
    "METABASE_DB_PASSWORD": "postgres",
    "OPTUNA_DB_PASSWORD": "postgres",
    "FLYTE_DB_PASSWORD": "postgres",
    # MinIO named users. `mc admin user add` on an existing accessKey re-issues
    # its secret in place; the objects and the policy are untouched.
    "AWS_SECRET_ACCESS_KEY": "minio-users",
    "FLYTE_S3_SECRET_KEY": "minio-users",
    "SERVING_S3_SECRET_KEY": "minio-users",
    # MinIO root is env-borne: Secret + a Recreate restart. The PVC keeps every
    # object, so this is in-place in the sense the PO asked for.
    "MINIO_ROOT_PASSWORD": "minio-root",
    # Grafana's admin login. Its storage is an emptyDir (persistence is OFF by
    # M6-S1's decision), so a restart genuinely re-creates the admin from the
    # Secret rather than leaving a stale row in a sqlite file.
    "GRAFANA_ADMIN_PASSWORD": "grafana",
    # Metabase's admin login lives in the app-db, which is a real Postgres
    # database and survives every restart. Only Metabase's own API can change it.
    "METABASE_ADMIN_PASSWORD": "metabase-admin",
}

# Not secrets. Each one is a name, an address or a setting; rotating any of them
# renames a thing that other state points at. The reason is on the line.
IDENTITIES: dict[str, str] = {
    "MINIO_ROOT_USER": "a username (the MinIO root account's name)",
    "AWS_ACCESS_KEY_ID": "a username — the MinIO user the chart creates, twinned with infra/helm/minio/values.yaml",
    "AWS_DEFAULT_REGION": "a setting, not a credential",
    "MLFLOW_TRACKING_URI": "an endpoint — the host-side address of the tracking server, not a credential",
    "MLFLOW_S3_ENDPOINT_URL": "an endpoint — the host-side address of MinIO, twinned with the port family",
    "MLFLOW_ARTIFACT_BUCKET": "a bucket name — renaming it orphans every artifact",
    "MLFLOW_DB_USER": "a Postgres role name — it OWNS a database",
    "MARTS_DB_USER": "a Postgres role name — it OWNS a database",
    "METABASE_DB_USER": "a Postgres role name — it OWNS a database",
    "METABASE_ADMIN_EMAIL": "a login identity, stored in the Metabase app-db",
    "OPTUNA_DB_USER": "a Postgres role name — it OWNS a database",
    "FLYTE_DB_USER": "a Postgres role name — it OWNS a database",
    "FLYTE_S3_ACCESS_KEY": "a username (the MinIO user `flyte`)",
    "SERVING_S3_ACCESS_KEY": "a username (the MinIO user `serving`)",
    "GRAFANA_ADMIN_USER": "a login identity",
}

FAMILY_ORDER = ["postgres", "minio-users", "minio-root", "grafana", "metabase-admin"]

# Which consumers hold a copy of which family's credential. Drained ONCE at the
# end of a run rather than per key: `deploy-flyte` is a helm upgrade and mlflow
# is touched by two families, so a naive per-key drain would restart the same
# workload four times to reach the same state.
CONSUMERS: dict[str, list[str]] = {
    "postgres": ["mlflow", "metabase", "flyte"],
    "minio-users": ["mlflow", "flyte", "serving"],
    # minio-root restarts MinIO inside its own rotator, because the restart is
    # what makes the new root credential live and the user read-back that PROVES
    # it has to happen after it. Listing it here too would restart it twice.
    "minio-root": [],
    "grafana": ["grafana"],
    "metabase-admin": [],
}

# The Postgres roles this program owns, and the key holding each one's password.
# `postgres` (the superuser) is deliberately FIRST and deliberately separate:
# postgres_databases.sh's DATABASES list describes tenant databases, and the
# superuser owns none.
PG_SUPERUSER = ("postgres", "POSTGRES_PASSWORD")
PG_TENANT_KEYS = [
    ("MLFLOW_DB_USER", "MLFLOW_DB_PASSWORD"),
    ("MARTS_DB_USER", "MARTS_DB_PASSWORD"),
    ("METABASE_DB_USER", "METABASE_DB_PASSWORD"),
    ("OPTUNA_DB_USER", "OPTUNA_DB_PASSWORD"),
    ("FLYTE_DB_USER", "FLYTE_DB_PASSWORD"),
]

# MinIO named users: the .env key holding the accessKey, and the one holding the secret.
MINIO_USERS = [
    ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
    ("FLYTE_S3_ACCESS_KEY", "FLYTE_S3_SECRET_KEY"),
    ("SERVING_S3_ACCESS_KEY", "SERVING_S3_SECRET_KEY"),
]


class RotationError(RuntimeError):
    """A refusal that names what it refused. Never carries a value."""


# ------------------------------------------------------------------ plumbing ---
def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_env(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        raise RotationError(f"{path} does not exist — there is nothing to rotate")
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v
    return out


def write_env_keys(path: pathlib.Path, updates: dict[str, str]) -> None:
    """Rewrite ONLY the named keys, preserving order, comments and every other line.

    A regenerate-the-file approach would drop the header comment that warns the
    reader these passwords are baked into volumes — which is the one sentence in
    .env that stops somebody deleting it.
    """
    lines = path.read_text().splitlines(keepends=True)
    seen: set[str] = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        if m and m.group(1) in updates:
            key = m.group(1)
            eol = "\n" if line.endswith("\n") else ""
            lines[i] = f"{key}={updates[key]}{eol}"
            seen.add(key)
    missing = sorted(set(updates) - seen)
    if missing:
        raise RotationError(f"{path} has no line for: {', '.join(missing)} — refusing a partial write")
    path.write_text("".join(lines))
    os.chmod(path, 0o600)


def gen_secret() -> str:
    """32 hex chars — the twin of platform_secrets.sh's gen_secret().

    Same shape for the same reason: no quoting hazard in YAML, in psql or in a URL.
    """
    return pysecrets.token_hex(16)


def gen_login_password() -> str:
    """The twin of platform_secrets.sh's gen_login_password().

    Metabase enforces a complexity rule (length plus at least one digit) that 32
    random hex characters can legitimately fail. The suffix guarantees a digit
    and a capital without touching entropy. Grafana has no such rule but shares
    the generator: a human-facing login is a human-facing login.
    """
    return f"{pysecrets.token_hex(16)}Aa1"


def kubectl(*args: str, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run([*KUBECTL, *args], input=stdin, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RotationError(f"kubectl {' '.join(args[:4])}… failed rc={p.returncode}: {p.stderr.strip()[:300]}")
    return p


def run_script(rel: str, env_extra: dict[str, str] | None = None) -> None:
    env = {**os.environ, **(env_extra or {})}
    p = subprocess.run(["bash", str(REPO / rel)], cwd=REPO, env=env, capture_output=True, text=True)
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-6:])
    if p.returncode != 0:
        raise RotationError(f"{rel} failed rc={p.returncode}:\n{tail}")
    print(f"[rotate]   {rel} ok")
    for line in tail.splitlines()[-2:]:
        print(f"[rotate]     | {line}")


# ------------------------------------------------------------ classification ---
def classify(env: dict[str, str]) -> dict[str, Any]:
    """Every key in .env lands in exactly one bucket, or this refuses.

    Two directions, both load-bearing:
      - a key in .env that this script does not know  -> FAIL (an unrotated secret
        that reports as rotated is the failure this whole story exists to prevent)
      - a key this script expects that .env lacks     -> FAIL (a rotation plan
        naming a credential the platform does not have is describing another
        platform)
    """
    known = set(ROTATE) | set(IDENTITIES)
    present = set(env)
    unknown = sorted(present - known)
    absent = sorted(known - present)
    if unknown:
        raise RotationError(
            "REFUSING: .env holds key(s) this script does not classify: "
            + ", ".join(unknown)
            + "\n  A rotation that silently skips a credential reports success while an old"
            "\n  value lives on. Add each one to ROTATE (with its family and an in-place"
            "\n  mechanism) or to IDENTITIES (with the reason it is not a secret)."
        )
    if absent:
        raise RotationError(
            "REFUSING: .env is missing key(s) this script expects: " + ", ".join(absent)
        )
    return {
        "env_keys": len(present),
        "rotatable": sorted(ROTATE),
        "identities": {k: IDENTITIES[k] for k in sorted(IDENTITIES)},
        "families": {f: sorted(k for k, fam in ROTATE.items() if fam == f) for f in FAMILY_ORDER},
    }


# ----------------------------------------------------------------- postgres ---
def _psql(sql: str, stdin_extra: str = "") -> str:
    """Run SQL as the superuser over `kubectl exec` — the transport `make marts` uses.

    No port is published for Postgres (CLAUDE.md's port family says "in-cluster
    only"), and authentication inside the pod is local, which is why this keeps
    working while the superuser's own password is being replaced.
    """
    p = kubectl(
        "-n", "platform", "exec", "-i", "postgres-0", "--",
        "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-tA", "-f", "-",
        stdin=stdin_extra + sql,
    )
    return p.stdout.strip()


def rotate_postgres(env: dict[str, str], new: dict[str, str], record: dict[str, Any]) -> None:
    """Six role passwords: five tenants through the ONE recipe, plus the superuser.

    The superuser gets its ALTER here because postgres_databases.sh describes
    TENANT databases and `postgres` owns none of them — adding it to that list
    would make a recipe about databases also be a recipe about the account that
    can drop them.
    """
    for key in FAMILY_KEYS["postgres"]:
        new[key] = gen_secret()
    write_env_keys(ENV_FILE, {k: new[k] for k in FAMILY_KEYS["postgres"]})
    print("[rotate]   .env written for 6 Postgres key(s)")

    # The five tenants, through the recipe that has owned them since M1-S4.
    run_script("scripts/postgres_databases.sh")

    # The superuser. Password on STDIN as a \set variable, never in argv.
    role, key = PG_SUPERUSER
    _psql(
        "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'role', :'pw')\\gexec\n",
        stdin_extra=f"\\set role '{role}'\n\\set pw '{new[key]}'\n",
    )
    print(f"[rotate]   ALTER ROLE {role} ok (superuser; no password printed)")

    # Read back the fact that a rotation happened WITHOUT reading a password:
    # pg_authid.rolpassword holds a SCRAM verifier, and its salt changes on every
    # ALTER. Comparing the verifier before/after would be the strongest check;
    # comparing its LENGTH proves only that one exists. So assert the shape.
    roles = [PG_SUPERUSER[0]] + [env[u] for u, _ in PG_TENANT_KEYS]
    quoted = ", ".join(f"'{r}'" for r in roles)
    got = _psql(
        f"SELECT rolname || '=' || CASE WHEN rolpassword LIKE 'SCRAM-SHA-256%' THEN 'scram' "
        f"ELSE 'OTHER' END FROM pg_authid WHERE rolname IN ({quoted}) ORDER BY rolname;\n"
    )
    shapes = dict(line.split("=", 1) for line in got.splitlines() if "=" in line)
    bad = sorted(r for r in roles if shapes.get(r) != "scram")
    if bad:
        raise RotationError(f"role(s) do not hold a SCRAM verifier after ALTER: {', '.join(bad)}")
    print(f"[rotate]   {len(roles)} role(s) hold a SCRAM-SHA-256 verifier (read back from pg_authid)")
    record["families"]["postgres"] = {
        "rotated_keys": sorted(FAMILY_KEYS["postgres"]),
        "roles": roles,
        "mechanism": "ALTER ROLE — five tenants via scripts/postgres_databases.sh, the superuser here",
        "verified": f"{len(roles)} roles hold a SCRAM-SHA-256 verifier",
        "at": now(),
    }


# -------------------------------------------------------------- minio users ---
def _mc(script: str, stdin: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run `mc` inside the MinIO pod with credentials fed on STDIN.

    `kubectl exec -- sh -c "mc alias set … $PASSWORD"` would put the root
    password in argv, where `ps` inside the pod and the kubectl audit log can
    both read it. `read -r` keeps it in a shell variable instead.
    """
    return kubectl(
        "-n", "platform", "exec", "-i", "deploy/minio", "--", "sh", "-c", script,
        stdin=stdin, check=check,
    )


def _minio_user_policies(root_user: str, root_pw: str) -> dict[str, str]:
    p = _mc(
        'read -r RU; read -r RP; mc alias set r http://127.0.0.1:9000 "$RU" "$RP" >/dev/null 2>&1 '
        "&& mc admin user list r --json",
        stdin=f"{root_user}\n{root_pw}\n",
    )
    out: dict[str, str] = {}
    for line in p.stdout.strip().splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("accessKey"):
            out[d["accessKey"]] = d.get("policyName", "")
    return out


def rotate_minio_users(env: dict[str, str], new: dict[str, str], record: dict[str, Any]) -> None:
    """Re-issue each named user's secret key in place, and PROVE the policy survived.

    `mc admin user add` on an existing accessKey replaces the secret and leaves
    the objects alone. What it does to the POLICY is the thing worth checking
    rather than assuming: `serving` carries two of them
    (`readonly,serving-readonly`), and a re-issue that quietly reset it to the
    default would hand the most-exposed identity in the program more access than
    it had — a change nothing else here would notice, because every read it
    performs would still succeed.
    """
    root_user, root_pw = env["MINIO_ROOT_USER"], env["MINIO_ROOT_PASSWORD"]
    before = _minio_user_policies(root_user, root_pw)
    print(f"[rotate]   {len(before)} MinIO user(s) before: " + ", ".join(f"{k}[{v}]" for k, v in sorted(before.items())))

    for ak_key, sk_key in MINIO_USERS:
        access = env[ak_key]
        if access not in before:
            raise RotationError(f"MinIO has no user '{access}' (from {ak_key}) — refusing to CREATE one during a rotation")
        new[sk_key] = gen_secret()
        _mc(
            'read -r RU; read -r RP; read -r AK; read -r SK; '
            'mc alias set r http://127.0.0.1:9000 "$RU" "$RP" >/dev/null 2>&1 '
            '&& mc admin user add r "$AK" "$SK" >/dev/null',
            stdin=f"{root_user}\n{root_pw}\n{access}\n{new[sk_key]}\n",
        )
        print(f"[rotate]   mc admin user add {access} ok (secret re-issued; no value printed)")

    after = _minio_user_policies(root_user, root_pw)
    drifted = {k: (before[k], after.get(k, "<missing>")) for k in before if after.get(k) != before[k]}
    if drifted:
        raise RotationError(
            "MinIO policy attachment CHANGED across the re-issue: "
            + "; ".join(f"{k}: {b!r} -> {a!r}" for k, (b, a) in sorted(drifted.items()))
        )
    print(f"[rotate]   policy attachment unchanged for all {len(after)} user(s) (read back, not assumed)")

    write_env_keys(ENV_FILE, {k: new[k] for k in FAMILY_KEYS["minio-users"]})
    print("[rotate]   .env written for 3 MinIO user key(s)")
    record["families"]["minio-users"] = {
        "rotated_keys": sorted(FAMILY_KEYS["minio-users"]),
        "users": sorted(before),
        "policies_preserved": {k: before[k] for k in sorted(before)},
        "mechanism": "mc admin user add (re-issues an existing accessKey's secret in place)",
        "at": now(),
    }


# --------------------------------------------------------------- minio root ---
def rotate_minio_root(env: dict[str, str], new: dict[str, str], record: dict[str, Any]) -> None:
    """Root is env-borne: Secret, restart, then PROVE the named users survived.

    The hazard this checks for is specific and is not in the binary's `--help`:
    some MinIO versions encrypt the IAM data (the named users, their policies)
    with the root credential, and expect MINIO_ROOT_USER_OLD / _PASSWORD_OLD on
    the restart that rotates it. If this deployment is one of those, rotating
    root without them makes `mlflow`, `flyte` and `serving` unreadable — a total
    platform outage that looks like three simultaneous wrong passwords.

    So the check is empirical rather than argued: re-issue root, restart, then
    list the users again. The undo is exact (the Secret is the only carrier;
    .env.pre-rotation holds the old value) and is named in the failure text.
    """
    new["MINIO_ROOT_PASSWORD"] = gen_secret()
    write_env_keys(ENV_FILE, {"MINIO_ROOT_PASSWORD": new["MINIO_ROOT_PASSWORD"]})
    print("[rotate]   .env written for MINIO_ROOT_PASSWORD")
    run_script("scripts/platform_secrets.sh")
    kubectl("-n", "platform", "rollout", "restart", "deploy/minio")
    kubectl("-n", "platform", "rollout", "status", "deploy/minio", "--timeout=300s")
    print("[rotate]   minio restarted on the new root credential")

    users = _minio_user_policies(env["MINIO_ROOT_USER"], new["MINIO_ROOT_PASSWORD"])
    expected = {env[ak] for ak, _ in MINIO_USERS}
    if not expected.issubset(set(users)):
        raise RotationError(
            "the named MinIO users did not survive the root rotation "
            f"(found {sorted(users)}, expected {sorted(expected)}). "
            "UNDO: put MINIO_ROOT_PASSWORD back from .env.pre-rotation, re-run "
            "scripts/platform_secrets.sh, restart deploy/minio."
        )
    print(f"[rotate]   {len(users)} named user(s) still readable AFTER the root rotation — no IAM re-encryption hazard on this build")
    record["families"]["minio-root"] = {
        "rotated_keys": ["MINIO_ROOT_PASSWORD"],
        "mechanism": "Secret minio-root + rollout restart deploy/minio (the PVC keeps every object)",
        "verified": f"{len(users)} named users readable after restart: {sorted(users)}",
        "at": now(),
    }


# ------------------------------------------------------------------ grafana ---
def rotate_grafana(env: dict[str, str], new: dict[str, str], record: dict[str, Any]) -> None:
    """Secret + restart, and the restart is what makes it a rotation.

    Grafana's persistence is OFF by M6-S1's decision (the boards and the
    datasource are provisioned from git on every start, so its sqlite holds only
    UI preferences). That makes its storage an emptyDir, which is exactly why
    this works: the admin user is re-created from the Secret on every boot, so
    there is no stale password row to leave behind. On a PERSISTENT Grafana this
    same two-step would silently do nothing.
    """
    new["GRAFANA_ADMIN_PASSWORD"] = gen_login_password()
    write_env_keys(ENV_FILE, {"GRAFANA_ADMIN_PASSWORD": new["GRAFANA_ADMIN_PASSWORD"]})
    print("[rotate]   .env written for GRAFANA_ADMIN_PASSWORD")
    run_script("scripts/platform_secrets.sh")
    record["families"]["grafana"] = {
        "rotated_keys": ["GRAFANA_ADMIN_PASSWORD"],
        "mechanism": "Secret monitoring/grafana-admin + restart (persistence is OFF, so the admin is re-created from it)",
        "at": now(),
    }


# ----------------------------------------------------------- metabase admin ---
def rotate_metabase_admin(env: dict[str, str], new: dict[str, str], record: dict[str, Any]) -> None:
    """The only family whose service change MUST come first, because it needs the old value.

    Metabase's admin password lives in the app-db — a real database in the one
    Postgres — so it survives every pod restart and no Secret carries it. The
    only in-place mechanism is Metabase's own API, and `PUT /api/user/:id/password`
    requires the CURRENT password. So: authenticate old, change, then write .env.
    Writing .env first would lock this script out of the instance it is trying to
    change.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    from metabase_boards import BASE_URL, Client, authenticate, wait_for_health  # noqa: PLC0415

    client = Client(BASE_URL)
    wait_for_health(client, timeout_s=180)
    authenticate(client, env)  # with the OLD password, which is still the live one
    me = client.get("/api/user/current")
    uid = int(me["id"])
    new["METABASE_ADMIN_PASSWORD"] = gen_login_password()
    client.put(
        f"/api/user/{uid}/password",
        {"password": new["METABASE_ADMIN_PASSWORD"], "old_password": env["METABASE_ADMIN_PASSWORD"]},
    )
    print(f"[rotate]   Metabase admin password changed via the API (user id {uid})")

    # Prove it, by logging in again from scratch on the new value. A PUT that
    # returned 200 is the API's claim; a fresh session is the fact.
    fresh = Client(BASE_URL)
    fresh.post("/api/session", {"username": env["METABASE_ADMIN_EMAIL"], "password": new["METABASE_ADMIN_PASSWORD"]})
    print("[rotate]   a FRESH login on the new password succeeded")

    write_env_keys(ENV_FILE, {"METABASE_ADMIN_PASSWORD": new["METABASE_ADMIN_PASSWORD"]})
    print("[rotate]   .env written for METABASE_ADMIN_PASSWORD")
    record["families"]["metabase-admin"] = {
        "rotated_keys": ["METABASE_ADMIN_PASSWORD"],
        "user_id": uid,
        "mechanism": "PUT /api/user/:id/password (the app-db is persistent; no Secret carries this)",
        "verified": "a fresh POST /api/session on the new password returned a session",
        "at": now(),
    }


FAMILY_KEYS = {f: sorted(k for k, fam in ROTATE.items() if fam == f) for f in FAMILY_ORDER}
ROTATORS = {
    "postgres": rotate_postgres,
    "minio-users": rotate_minio_users,
    "minio-root": rotate_minio_root,
    "grafana": rotate_grafana,
    "metabase-admin": rotate_metabase_admin,
}


# ----------------------------------------------------------------- consumers ---
def drain_consumers(pending: set[str], record: dict[str, Any]) -> None:
    """Restart every workload holding a copy, exactly once each.

    Deduplicated on purpose: `mlflow` holds a credential from two families and
    `flyte` from two, and `deploy-flyte` is a helm upgrade. Restarting each of
    them once per key would reach the same state four times as slowly, and the
    charter's rule is about no pair being left disagreeing — not about the number
    of restarts.
    """
    done: list[str] = []
    if "mlflow" in pending:
        kubectl("-n", "mlflow", "rollout", "restart", "deploy/mlflow")
        kubectl("-n", "mlflow", "rollout", "status", "deploy/mlflow", "--timeout=600s")
        done.append("mlflow/mlflow (restart)")
    if "metabase" in pending:
        kubectl("-n", "metabase", "rollout", "restart", "deploy/metabase")
        kubectl("-n", "metabase", "rollout", "status", "deploy/metabase", "--timeout=600s")
        done.append("metabase/metabase (restart)")
    if "grafana" in pending:
        kubectl("-n", "monitoring", "rollout", "restart", "deploy/grafana")
        kubectl("-n", "monitoring", "rollout", "status", "deploy/grafana", "--timeout=600s")
        done.append("monitoring/grafana (restart)")
    if "flyte" in pending:
        # NOT a restart: the flyte-binary chart renders its DB password and its S3
        # secret key out of VALUES, so the rendered ConfigMap/Secret in the cluster
        # still holds the OLD ones. Only a helm upgrade through deploy_flyte.sh —
        # which hands them over in a mode-600 overlay it deletes on EXIT — replaces
        # them. A `rollout restart` here would look like it worked and change nothing.
        run_script("scripts/deploy_flyte.sh")
        done.append("flyte (helm upgrade via deploy_flyte.sh — values-rendered credentials)")
    if "serving" in pending:
        # The predictor's storage-initializer fetches the champion under
        # SERVING_S3_SECRET_KEY, so this is the one place the rotation is proved
        # against a real download rather than against a login.
        run_script("scripts/deploy_champion.sh")
        done.append("serving (make serve — the storage-initializer re-fetches under the new credential)")
    for line in done:
        print(f"[rotate]   consumer converged: {line}")
    record["consumers_converged"] = done


# ------------------------------------------------------- the negative probes ---
def verify_old_refused(record_path: pathlib.Path) -> int:
    """Prove the PRE-rotation values are dead. Runs AFTER the positive sweep.

    Order matters and is the point (gotcha #105 / F-060): an absence check run
    first would pass against a platform that is simply down. "The old password
    is refused" only means something once "the new password works" has been
    shown — which is what the ten gates do.
    """
    if not PRE_ROTATION.exists():
        raise RotationError(f"{PRE_ROTATION} is gone — the old values cannot be probed")
    old = read_env(PRE_ROTATION)
    live = read_env(ENV_FILE)
    checks: list[dict[str, Any]] = []

    def note(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "refused": ok, "detail": detail})
        print(f"[old-refused] {'ok  ' if ok else 'FAIL'} {name}: {detail}")

    # 1. MinIO root, old password. `mc alias set` validates against the server.
    if old["MINIO_ROOT_PASSWORD"] == live["MINIO_ROOT_PASSWORD"]:
        note("minio-root", False, "the old and live values are IDENTICAL — nothing rotated")
    else:
        p = _mc(
            'read -r RU; read -r RP; mc alias set old http://127.0.0.1:9000 "$RU" "$RP"',
            stdin=f"{old['MINIO_ROOT_USER']}\n{old['MINIO_ROOT_PASSWORD']}\n",
            check=False,
        )
        note("minio-root", p.returncode != 0,
             f"mc alias set with the pre-rotation root password exited {p.returncode} (non-zero = refused)")

    # 2. A MinIO NAMED user, old secret — a different code path from root.
    if old["SERVING_S3_SECRET_KEY"] != live["SERVING_S3_SECRET_KEY"]:
        p = _mc(
            'read -r AK; read -r SK; mc alias set olduser http://127.0.0.1:9000 "$AK" "$SK"',
            stdin=f"{old['SERVING_S3_ACCESS_KEY']}\n{old['SERVING_S3_SECRET_KEY']}\n",
            check=False,
        )
        note("minio-user-serving", p.returncode != 0,
             f"mc alias set as `serving` with its pre-rotation secret exited {p.returncode} (non-zero = refused)")

    # 3. Postgres, old tenant password, over TCP inside the pod (password auth,
    #    not the local peer auth the ALTERs used — so this exercises the verifier).
    if old["MLFLOW_DB_PASSWORD"] != live["MLFLOW_DB_PASSWORD"]:
        p = kubectl(
            "-n", "platform", "exec", "-i", "postgres-0", "--", "sh", "-c",
            'read -r U; read -r P; PGPASSWORD="$P" psql -h 127.0.0.1 -U "$U" -d mlflow -tAc "select 1"',
            stdin=f"{old['MLFLOW_DB_USER']}\n{old['MLFLOW_DB_PASSWORD']}\n", check=False,
        )
        refused = p.returncode != 0 and "authentication failed" in (p.stderr + p.stdout).lower()
        note("postgres-mlflow", refused,
             f"psql as `{old['MLFLOW_DB_USER']}` with its pre-rotation password exited {p.returncode}"
             + (" with an authentication failure" if refused else f" — stderr: {p.stderr.strip()[:120]}"))

    # 4. And the NEW password must work over the same path — the positive control
    #    that stops #3 passing because the database is simply gone.
    p = kubectl(
        "-n", "platform", "exec", "-i", "postgres-0", "--", "sh", "-c",
        'read -r U; read -r P; PGPASSWORD="$P" psql -h 127.0.0.1 -U "$U" -d mlflow -tAc "select 1"',
        stdin=f"{live['MLFLOW_DB_USER']}\n{live['MLFLOW_DB_PASSWORD']}\n", check=False,
    )
    note("postgres-mlflow-NEW-works", p.returncode == 0 and p.stdout.strip() == "1",
         f"the same path with the CURRENT password exited {p.returncode} (0 = accepted; this is the control)")

    payload = {"at": now(), "checks": checks,
               "note": "run AFTER the positive sweep: an absence check before a presence check passes against a dead platform"}
    if record_path.exists():
        rec = json.loads(record_path.read_text())
        rec["old_credentials_refused"] = payload
        record_path.write_text(json.dumps(rec, indent=2) + "\n")
    failed = [c["check"] for c in checks if not c["refused"]]
    if failed:
        print(f"[old-refused] FAILED: {', '.join(failed)}")
        return 1
    print(f"[old-refused] PASSED — {len(checks)} check(s), the pre-rotation values are dead")
    return 0


# ---------------------------------------------------------------------- main ---
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true", help="enumerate and classify; touch nothing")
    ap.add_argument("--families", default=",".join(FAMILY_ORDER),
                    help=f"comma-separated subset of {FAMILY_ORDER} (each is a safe stopping point)")
    ap.add_argument("--verify-old-refused", action="store_true",
                    help="prove the .env.pre-rotation values are refused (run AFTER the positive sweep)")
    ap.add_argument("--out", default=str(RECORD))
    args = ap.parse_args()
    out = pathlib.Path(args.out)

    env = read_env(ENV_FILE)
    inventory = classify(env)

    if args.verify_old_refused:
        return verify_old_refused(out)

    if args.plan:
        print(f"== rotation plan ==  {inventory['env_keys']} key(s) in {ENV_FILE.name}, every one classified")
        for fam in FAMILY_ORDER:
            print(f"  family {fam:<15} {len(FAMILY_KEYS[fam])} key(s): {', '.join(FAMILY_KEYS[fam])}")
            print(f"    consumers: {', '.join(CONSUMERS[fam]) or '(none)'}")
        print(f"  NOT rotated ({len(IDENTITIES)} — identities, endpoints and settings, not secrets):")
        for k in sorted(IDENTITIES):
            print(f"    {k:<24} {IDENTITIES[k]}")
        print("[plan] nothing was changed.")
        return 0

    families = [f.strip() for f in args.families.split(",") if f.strip()]
    unknown = [f for f in families if f not in ROTATORS]
    if unknown:
        raise RotationError(f"unknown family/families: {', '.join(unknown)} (known: {', '.join(FAMILY_ORDER)})")
    if not PRE_ROTATION.exists():
        raise RotationError(
            f"{PRE_ROTATION} does not exist. Copy .env aside BEFORE the first change — losing it "
            "mid-rotation orphans every volume. (It is gitignored by `.env.*`; verified with git check-ignore.)"
        )

    record: dict[str, Any] = {
        "story": "M9-S12", "started_at": now(), "env_file": ENV_FILE.name,
        "inventory": inventory, "families": {},
        "sanction": "AWAITING_PO 2026-08-24-5, answer 2 (YES, in-place preferred over destroy+rebuild)",
        "no_values_recorded": "this record names what rotated, never to what — old or new",
    }
    new: dict[str, str] = {}
    pending: set[str] = set()

    print(f"== credential rotation ==  families: {', '.join(families)}")
    for fam in FAMILY_ORDER:
        if fam not in families:
            continue
        print(f"-- family {fam} --")
        ROTATORS[fam](env, new, record)
        pending.update(CONSUMERS[fam])
        # Every family except postgres writes .env itself and then needs the
        # Secrets converged; postgres and minio-root already ran the script.
        if fam in ("postgres", "minio-users"):
            run_script("scripts/platform_secrets.sh")

    print("-- consumers --")
    drain_consumers(pending, record)

    record["finished_at"] = now()
    record["rotated_key_count"] = len(new)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[rotate] {len(new)} credential(s) rotated across {len(families)} family/families -> {out}")
    print("[rotate] NEXT: the positive sweep (the ten gates), THEN --verify-old-refused.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RotationError as exc:
        print(f"[rotate] FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
