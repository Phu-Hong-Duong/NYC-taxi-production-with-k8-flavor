"""The properties of the credential rotation (M9-S12).

The rotation itself needs a live platform and is proved by its record and by the
ten gates. What is testable offline is the part that decides WHAT rotates — and
that is the part where a mistake is silent. Every test here is about the
inventory, the refusals, or the no-echo law; none of them needs a cluster.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "rotate_credentials.py"
SECRETS_SH = REPO / "scripts" / "platform_secrets.sh"

sys.path.insert(0, str(REPO / "scripts"))
import rotate_credentials as rc  # noqa: E402


# ------------------------------------------------------------- the inventory ---
def test_every_env_example_key_is_classified_exactly_once():
    """No key may be in both buckets, and none may be in neither.

    `.env.example` is the tracked shape of `.env` (the real file is gitignored),
    so it is the only copy of the inventory a test can read.
    """
    keys = {
        m.group(1)
        for line in (REPO / ".env.example").read_text().splitlines()
        if (m := re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line.strip()))
    }
    assert keys, ".env.example parsed to zero keys — the parser, not the file, is wrong"
    both = keys & set(rc.ROTATE) & set(rc.IDENTITIES)
    assert not both, f"classified twice: {sorted(both)}"
    neither = keys - set(rc.ROTATE) - set(rc.IDENTITIES)
    assert not neither, (
        f"unclassified key(s) in .env.example: {sorted(neither)} — add each to ROTATE "
        "(with a family and an in-place mechanism) or to IDENTITIES (with the reason)"
    )


def test_the_required_list_in_platform_secrets_is_fully_classified():
    """The rotation's inventory must cover the deploy recipe's REQUIRED list.

    These are twins: `platform_secrets.sh` refuses to deploy without these keys,
    so every one of them is live somewhere in the platform. A key it demands and
    this script does not classify is a credential nobody rotates.
    """
    text = SECRETS_SH.read_text()
    block = re.search(r"^REQUIRED=\((.*?)\)$", text, re.S | re.M)
    assert block, "could not find the REQUIRED=( … ) array in platform_secrets.sh"
    required = set(block.group(1).split())
    assert len(required) >= 20, f"parsed only {len(required)} REQUIRED keys — the parser is wrong"
    unclassified = required - set(rc.ROTATE) - set(rc.IDENTITIES)
    assert not unclassified, (
        f"platform_secrets.sh REQUIREs unclassified key(s): {sorted(unclassified)}"
    )


def test_every_rotatable_key_belongs_to_a_known_family_with_a_rotator():
    for key, family in rc.ROTATE.items():
        assert family in rc.FAMILY_ORDER, (
            f"{key} names family {family!r}, which is not in FAMILY_ORDER"
        )
        assert family in rc.ROTATORS, f"family {family!r} has no rotator"
    assert set(rc.ROTATORS) == set(rc.FAMILY_ORDER)
    assert set(rc.CONSUMERS) == set(rc.FAMILY_ORDER)


def test_every_identity_carries_a_reason():
    """A key excluded from rotation without a stated reason is an unexamined exclusion."""
    for key, why in rc.IDENTITIES.items():
        assert len(why.strip()) > 15, (
            f"{key} is excluded from rotation with no real reason: {why!r}"
        )


def test_minio_users_and_postgres_roles_are_drawn_from_the_identity_keys():
    """The user/role NAMES come from .env keys classified as identities, never typed here."""
    for ak, sk in rc.MINIO_USERS:
        assert ak in rc.IDENTITIES, f"{ak} is a username and must be an identity"
        assert rc.ROTATE.get(sk) == "minio-users", f"{sk} must rotate in the minio-users family"
    for user_key, pw_key in rc.PG_TENANT_KEYS:
        assert user_key in rc.IDENTITIES, f"{user_key} is a role name and must be an identity"
        assert rc.ROTATE.get(pw_key) == "postgres", f"{pw_key} must rotate in the postgres family"


def test_minio_users_are_rotated_before_minio_root():
    """Re-issuing a named user needs the root credential, so root must go last.

    Reverse them and every `mc admin user add` authenticates with a password the
    server no longer has.
    """
    assert rc.FAMILY_ORDER.index("minio-users") < rc.FAMILY_ORDER.index("minio-root")


# --------------------------------------------------------------- the refusals ---
def _plan(env_text: str, tmp_path: pathlib.Path) -> subprocess.CompletedProcess[str]:
    env_file = tmp_path / "env"
    env_file.write_text(env_text)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--plan"],
        env={**os.environ, "ENV_FILE": str(env_file)},
        capture_output=True, text=True, cwd=REPO,
    )


@pytest.fixture
def full_env() -> str:
    return "".join(f"{k}=x\n" for k in sorted(set(rc.ROTATE) | set(rc.IDENTITIES)))


def test_plan_accepts_a_fully_classified_env(full_env, tmp_path):
    p = _plan(full_env, tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "every one classified" in p.stdout


def test_an_unclassified_key_is_REFUSED_never_skipped(full_env, tmp_path):
    """The design decision this file exists to protect.

    A rotation that passes silently over a credential added later reports success
    while an old value lives on — worse than not rotating, because the operator
    now believes it is done.
    """
    p = _plan(full_env + "NEW_SERVICE_TOKEN=deadbeef\n", tmp_path)
    assert p.returncode == 2, f"expected refusal, got {p.returncode}: {p.stdout}{p.stderr}"
    assert "NEW_SERVICE_TOKEN" in p.stderr
    assert "does not classify" in p.stderr


def test_a_missing_expected_key_is_REFUSED(full_env, tmp_path):
    """The other direction: a plan naming a credential this platform lacks
    describes another platform."""
    trimmed = "".join(
        line + "\n" for line in full_env.splitlines()
        if not line.startswith("SERVING_S3_SECRET_KEY=")
    )
    p = _plan(trimmed, tmp_path)
    assert p.returncode == 2, f"expected refusal, got {p.returncode}: {p.stdout}{p.stderr}"
    assert "SERVING_S3_SECRET_KEY" in p.stderr
    assert "missing" in p.stderr


def test_rotating_without_the_pre_rotation_copy_is_REFUSED(full_env, tmp_path, monkeypatch):
    """Losing .env mid-rotation orphans every volume; the copy is the only undo."""
    env_file = tmp_path / "env"
    env_file.write_text(full_env)
    monkeypatch.setattr(rc, "ENV_FILE", env_file)
    monkeypatch.setattr(rc, "PRE_ROTATION", tmp_path / "nope")
    monkeypatch.setattr(sys, "argv", ["rotate_credentials.py"])
    with pytest.raises(rc.RotationError, match="Copy .env aside BEFORE the first change"):
        rc.main()


# ---------------------------------------------------------------- .env writes ---
def test_write_env_keys_touches_only_the_named_lines(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("# a comment that must survive\nA=1\nB=2\n\nC=3\n")
    rc.write_env_keys(env_file, {"B": "new"})
    assert env_file.read_text() == "# a comment that must survive\nA=1\nB=new\n\nC=3\n"
    assert oct(env_file.stat().st_mode)[-3:] == "600"


def test_write_env_keys_refuses_a_partial_write(tmp_path):
    """A key with no line in .env means the file is not the one this plan was made for."""
    env_file = tmp_path / "env"
    env_file.write_text("A=1\n")
    with pytest.raises(rc.RotationError, match="no line for: B"):
        rc.write_env_keys(env_file, {"A": "x", "B": "y"})
    assert env_file.read_text() == "A=1\n", "the file must be unchanged when the write is refused"


# --------------------------------------------------------------- the generators ---
def test_generators_are_twins_of_platform_secrets_sh():
    """Same shape as the shell the platform was built with: 32 hex, plus a login variant.

    `gen_login_password`'s suffix exists because Metabase rejects a password its
    complexity rule dislikes and 32 random hex characters can legitimately hold
    neither a digit nor a capital.
    """
    assert re.fullmatch(r"[0-9a-f]{32}", rc.gen_secret())
    login = rc.gen_login_password()
    assert re.fullmatch(r"[0-9a-f]{32}Aa1", login)
    assert any(c.isdigit() for c in login) and any(c.isupper() for c in login)
    assert len({rc.gen_secret() for _ in range(50)}) == 50, "generator repeated a value"
    # The shell twins must still exist, or these are copies of nothing.
    sh = SECRETS_SH.read_text()
    assert "openssl rand -hex 16" in sh
    assert "%sAa1" in sh


def test_human_facing_logins_use_the_login_safe_generator():
    """Asked of the AST, because the file argues about both generators in prose."""
    tree = ast.parse(SCRIPT.read_text())
    for fn_name, expected in (("rotate_metabase_admin", "gen_login_password"),
                              ("rotate_grafana", "gen_login_password"),
                              ("rotate_postgres", "gen_secret")):
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == fn_name
        )
        called = {
            n.func.id for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert expected in called, f"{fn_name} must mint its value with {expected}"


# ------------------------------------------------------------- the no-echo law ---
def test_no_secret_value_ever_reaches_argv():
    """Credentials go to psql and mc on STDIN only.

    argv is readable by `ps` inside the pod and is recorded in a kubectl audit
    log, which is why postgres_databases.sh has passed passwords on stdin since
    M1-S4. Asked of the AST: every subprocess-ish call's argument list is checked
    for a subscript of `env` or `new`, which is how a value would get there.
    """
    tree = ast.parse(SCRIPT.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if fname not in {"kubectl", "run", "_mc", "_psql", "run_script"}:
            continue
        for arg in node.args:  # positional args only: `stdin=` is a keyword, and is allowed
            for sub in ast.walk(arg):
                if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                        and sub.value.id in {"env", "new"}):
                    offenders.append(f"line {node.lineno}: {fname}(… {sub.value.id}[…] …)")
    assert not offenders, "a credential reached a command line: " + "; ".join(offenders)


def test_the_record_never_carries_a_value():
    """The record names WHAT rotated, never to what.

    Checked structurally: no dict literal assigned into `record[...]` may hold a
    subscript of `new`.
    """
    tree = ast.parse(SCRIPT.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Subscript) and "record" in ast.dump(t) for t in node.targets
        ):
            for sub in ast.walk(node.value):
                if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                        and sub.value.id == "new"):
                    offenders.append(f"line {node.lineno}")
    assert not offenders, (
        "the rotation record would carry a secret value at " + ", ".join(offenders)
    )


def test_the_script_never_prints_a_secret():
    """No print() may interpolate a subscript of `env` or `new`.

    A value printed once is in a session log, a scrollback buffer and eventually
    a screenshot (platform_secrets.sh's own words).
    """
    tree = ast.parse(SCRIPT.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                        and sub.value.id in {"env", "new"}):
                    offenders.append(f"line {node.lineno}")
    assert not offenders, "a print() would emit a secret at " + ", ".join(offenders)


# ------------------------------------------------------------------ gitignore ---
def test_the_pre_rotation_copy_is_gitignored_and_the_example_is_not():
    """The finding this story opened with: `.env` does not match `.env.pre-rotation`.

    gitignore patterns are literal names, not prefixes. One `git add -A` during a
    rotation would otherwise commit every OLD credential in the program.
    """
    def ignored(path: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO).returncode == 0

    assert ignored(".env"), ".env must be gitignored"
    assert ignored(".env.pre-rotation"), "the rotation's undo copy is NOT gitignored"
    assert ignored(".env.anything-else"), "a future .env sibling would not be gitignored"
    assert not ignored(".env.example"), ".env.example is the tracked shape and must stay visible"
    tracked = subprocess.run(
        ["git", "ls-files", ".env.example"], cwd=REPO, capture_output=True, text=True
    )
    assert tracked.stdout.strip() == ".env.example"


# --------------------------------------------------------------- the record ---
RECORD = REPO / "automation" / "runs" / "m9-publish" / "rotation.json"


@pytest.mark.needs_records
def test_the_rotation_record_covers_every_rotatable_key_and_holds_no_value():
    """F-054's rule: the record is tracked, so its absence means deleted-or-lost,
    never 'not run yet'."""
    assert RECORD.exists(), f"{RECORD} is missing — M9-S12's rotation record is tracked evidence"
    rec = json.loads(RECORD.read_text())
    covered = {k for fam in rec["families"].values() for k in fam["rotated_keys"]}
    assert covered == set(rc.ROTATE), (
        f"the record covers {sorted(covered)}; the inventory says {sorted(rc.ROTATE)}"
    )
    assert rec["rotated_key_count"] == len(rc.ROTATE)
    # No 32-hex-or-longer token anywhere in the record: that is the shape every
    # generator here emits, so its absence is the checkable form of "no values".
    blob = json.dumps(rec)
    assert not re.search(r"\b[0-9a-f]{32,}\b", blob), (
        "the rotation record contains a secret-shaped value"
    )


@pytest.mark.needs_records
def test_the_record_proves_the_old_credentials_were_refused():
    rec = json.loads(RECORD.read_text())
    probes = rec.get("old_credentials_refused")
    assert probes, "the record carries no old-credential refusal block"
    names = {c["check"] for c in probes["checks"]}
    assert {"minio-root", "postgres-mlflow"} <= names, f"missing a negative probe: {sorted(names)}"
    assert "postgres-mlflow-NEW-works" in names, (
        "the positive control is missing — an absence check with no presence check "
        "passes against a dead platform (gotcha #105)"
    )
    failed = [c["check"] for c in probes["checks"] if not c["refused"]]
    assert not failed, f"these probes did not refuse: {failed}"
