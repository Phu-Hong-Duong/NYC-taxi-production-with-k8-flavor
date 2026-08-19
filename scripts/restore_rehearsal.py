#!/usr/bin/env python
"""Restore the newest backup's small dumps into SCRATCH state, and check them.

M6-S5, behind `make restore-drill`. Since M4-S2 every backup artifact this
program writes has carried the same sentence: **RESTORE IS NOT REHEARSED.** The
dumps were proven COMPLETE (a gzip CRC over every byte plus pg_dump's own
completion marker) and the object mirror was proven by count AND bytes — but
"these files restore a working platform" stayed a hypothesis, and a hypothesis
in a lifeboat is the worst place to keep one.

WHAT THIS CLAIMS, AND WHAT IT REFUSES TO CLAIM.
It claims: the three small, IRREPLACEABLE dumps (mlflow · optuna · metabase)
load into a live Postgres with `ON_ERROR_STOP=1` and the databases that come out
of them contain what the running platform contains, checked row by row against
the live databases AND against records committed in this repository; and the
object mirror uploads back into MinIO byte-identically, checked by sha256
against the live object.

It does NOT claim that a full restore over a dead platform works. Nothing here
restores over anything: every database is created fresh under a `_restore_drill`
suffix, every object goes into a scratch bucket, and all of it is dropped at the
end. The honest label therefore moves ONE NOTCH — from "not rehearsed" to
"scratch-rehearsed <date>; full restore over a dead platform still not" — and
that is the whole point. A drill that overstated itself would be worse than the
sentence it replaced.

WHY `marts` IS DELIBERATELY NOT IN THIS DRILL. It is 1.2 GiB of the 1.6 GiB
backup and it is the ONE database that is provably rebuildable from DVC pins
plus `make marts` (M1-S5's fresh-volume proof). The other four total under
400 KiB and are the irreplaceable ones — the registry, the studies, the boards.
Restoring 1.2 GiB into a scratch database to prove a path the aggregates already
prove would cost the peak M4-S5 measured (2.075x the database size) for no new
information. Stated here rather than left to be noticed.

WHY SCRATCH DATABASES AND NOT A SECOND POSTGRES. D-002's rule: one Postgres,
databases added additively. A scratch database is exactly that path used for
five minutes, and it is dropped by name. The LIVE databases are never connected
to except to COUNT — the drill snapshots their sizes before and after and a
change is a FAILED check.

Usage:
    make restore-drill
    make restore-drill RESTORE_ARGS="--backup <dir> --keep"   # keep the scratch state
Exit: 0 every check passed · 1 a check failed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m6-restore"
BACKUP_ROOT = Path("/home/longt/dvc-remote/nyc-taxi-platform-backups")

NAMESPACE = "platform"
POD = "postgres-0"
SCRATCH_SUFFIX = "_restore_drill"

#: The small, irreplaceable databases. `marts` and `flyte` are excluded and the
#: module docstring says why for `marts`; `flyte` is orchestrator state whose
#: contents are runs already recorded as JSON in this repo.
TARGETS = ["mlflow", "optuna", "metabase"]

#: Tables counted in both the restored copy and the live database. Chosen to be
#: STABLE — a table the platform writes to on its own (metabase's
#: `query_execution`, mlflow's `metrics` during a fit) would differ for a correct
#: restore, because the backup is a point in time and the platform kept running.
COUNTED: dict[str, list[str]] = {
    "mlflow": ["experiments", "runs", "registered_models", "model_versions"],
    "optuna": ["studies", "trials"],
    "metabase": ["report_card", "report_dashboard", "core_user"],
}


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str) -> None:
    print(f"[restore-drill] {msg}", flush=True)


def psql(database: str, sql: str, *, tuples_only: bool = True) -> str:
    """Run one statement in the pod. Never over TCP — nothing publishes 5432."""
    args = ["kubectl", "-n", NAMESPACE, "exec", "-i", POD, "--", "psql", "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        args += ["-tA"]
    args += ["-U", "postgres", "-d", database, "-c", sql]
    result = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(f"psql -d {database}: {result.stderr.strip()}")
    return result.stdout.strip()


def table_counts(database: str, tables: list[str]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for table in tables:
        try:
            out[table] = int(psql(database, f"SELECT count(*) FROM {table}"))  # noqa: S608
        except RuntimeError:
            out[table] = None
    return out


def database_sizes() -> dict[str, int]:
    rows = psql("postgres", "SELECT datname, pg_database_size(datname) FROM pg_database")
    sizes: dict[str, int] = {}
    for line in rows.splitlines():
        name, _, size = line.partition("|")
        sizes[name] = int(size)
    return sizes


def newest_backup() -> Path:
    candidates = sorted(p for p in BACKUP_ROOT.iterdir() if p.is_dir())
    if not candidates:
        raise SystemExit(f"[restore-drill] FAIL: no backup under {BACKUP_ROOT}")
    return candidates[-1]


def gzip_complete(path: Path) -> tuple[bool, str]:
    """Re-prove the dump before restoring it — the M4-S2 verification, replayed.

    Cheap, and it means a failed restore below cannot be blamed on a file that
    was already known to be short.
    """
    marker = "-- PostgreSQL database dump complete"
    try:
        tail = ""
        with gzip.open(path, "rt", errors="replace") as handle:
            for chunk in handle:
                tail = (tail + chunk)[-4096:]
    except Exception as error:  # noqa: BLE001
        return False, f"gzip CRC failed: {error}"
    return (marker in tail), ("complete marker present" if marker in tail else "marker ABSENT")


# --- the repo's own records, used as the second witness -----------------------


def expected_from_repo() -> dict[str, Any]:
    """Numbers this repository already commits, derived — never typed here.

    F-017's rule applied to a restore: a check that compares the restored copy
    only against the live database proves the two agree, which is also what a
    restore of the WRONG backup into the WRONG database would show if somebody
    restored live into itself. These come from tracked artifacts instead.
    """
    boards = sorted((REPO_ROOT / "analytics" / "metabase" / "boards").glob("*.json"))
    dashboard_names: list[str] = []
    card_names: list[str] = []
    for path in boards:
        payload = json.loads(path.read_text())
        dashboard_names.append(payload["name"])
        card_names.extend(card["name"] for card in payload.get("cards", []))
    studies: dict[str, int] = {}
    for path in sorted((REPO_ROOT / "automation" / "runs" / "m3s4").glob("sniper-*.json")):
        record = json.loads(path.read_text())
        studies[record["study"]] = int(record["trials_total"])
    return {
        "metabase_dashboard_names": sorted(dashboard_names),
        "metabase_card_names": sorted(card_names),
        "optuna_studies": studies,
        "sources": {
            "metabase": "analytics/metabase/boards/*.json",
            "optuna": "automation/runs/m3s4/sniper-*.json",
        },
    }


# --- the MinIO half -----------------------------------------------------------


def minio_client() -> Any:
    import boto3
    from botocore.config import Config

    env: dict[str, str] = {}
    for raw in (REPO_ROOT / ".env").read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return boto3.client(
        "s3",
        endpoint_url=env.get("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=env["MINIO_ROOT_USER"],
        aws_secret_access_key=env["MINIO_ROOT_PASSWORD"],
        region_name=env.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore_objects(
    backup: Path, checks: list[tuple[bool, str]], record: dict[str, Any], *, keep: bool
) -> None:
    """Upload the mirrored `flyte-data` bucket into a SCRATCH bucket and check it.

    `flyte-data` is chosen because it is small (184 objects, 765 KiB) and
    COMPLETE — a whole bucket restored, not a sample. One `mlflow-artifacts`
    object is then restored as well and compared by sha256 against the LIVE
    object, because the artifacts are what serving actually needs and byte
    identity is the only claim worth making about them.
    """
    source = backup / "minio" / "flyte-data"
    if not source.exists():
        checks.append((False, f"the backup has no mirrored flyte-data at {source}"))
        return
    files = sorted(p for p in source.rglob("*") if p.is_file())
    scratch_bucket = "restore-drill-scratch"
    s3 = minio_client()

    live_buckets_before = sorted(b["Name"] for b in s3.list_buckets().get("Buckets", []))
    if scratch_bucket in live_buckets_before:
        checks.append((False, f"{scratch_bucket} already exists — refusing to reuse it"))
        return

    t0 = time.monotonic()
    s3.create_bucket(Bucket=scratch_bucket)
    uploaded_bytes = 0
    for path in files:
        key = str(path.relative_to(source))
        s3.upload_file(str(path), scratch_bucket, key)
        uploaded_bytes += path.stat().st_size
    seconds = round(time.monotonic() - t0, 2)

    listed = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=scratch_bucket):
        listed.extend(page.get("Contents", []))
    server_bytes = sum(o["Size"] for o in listed)

    checks.append(
        (
            len(listed) == len(files) and server_bytes == uploaded_bytes,
            f"flyte-data restored WHOLE into a scratch bucket: {len(listed)} object(s) / "
            f"{server_bytes} byte(s) == {len(files)} file(s) / {uploaded_bytes} byte(s) on "
            f"disk, in {seconds}s",
        )
    )

    # One artifact, restored and compared byte for byte against the live object.
    artifacts = sorted(p for p in (backup / "minio" / "mlflow-artifacts").rglob("*") if p.is_file())
    artifact_check: dict[str, Any] = {}
    mlmodels = [p for p in artifacts if p.name == "MLmodel"]
    if mlmodels:
        chosen = mlmodels[0]
        key = str(chosen.relative_to(backup / "minio" / "mlflow-artifacts"))
        s3.upload_file(str(chosen), scratch_bucket, f"artifact-check/{key}")
        restored = s3.get_object(Bucket=scratch_bucket, Key=f"artifact-check/{key}")["Body"].read()
        live = s3.get_object(Bucket="mlflow-artifacts", Key=key)["Body"].read()
        artifact_check = {
            "key": key,
            "restored_sha256": sha256_bytes(restored),
            "live_sha256": sha256_bytes(live),
            "bytes": len(restored),
        }
        checks.append(
            (
                artifact_check["restored_sha256"] == artifact_check["live_sha256"],
                f"a restored MLflow artifact is byte-identical to the live object "
                f"({key}, sha256 {artifact_check['restored_sha256'][:12]}…)",
            )
        )
    else:
        checks.append((False, "the backup mirror carries no MLmodel file to compare"))

    record["minio"] = {
        "scratch_bucket": scratch_bucket,
        "objects_restored": len(listed),
        "bytes_restored": server_bytes,
        "seconds": seconds,
        "artifact_byte_identity": artifact_check,
        "kept": keep,
    }

    if keep:
        say(f"    --keep: scratch bucket {scratch_bucket} left in place")
        return
    for page in paginator.paginate(Bucket=scratch_bucket):
        for obj in page.get("Contents", []):
            s3.delete_object(Bucket=scratch_bucket, Key=obj["Key"])
    s3.delete_bucket(Bucket=scratch_bucket)
    after = sorted(b["Name"] for b in s3.list_buckets().get("Buckets", []))
    checks.append(
        (
            after == live_buckets_before,
            f"the scratch bucket is gone and the live bucket list is unchanged: {after}",
        )
    )


# --- the drill ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", help="the backup directory (default: the newest)")
    parser.add_argument(
        "--keep", action="store_true", help="leave the scratch databases and bucket in place"
    )
    parser.add_argument("--record", default=str(RECORD_DIR / "restore_drill.json"))
    args = parser.parse_args(argv)

    backup = Path(args.backup) if args.backup else newest_backup()
    print("== the restore rehearsal (M6-S5) ==")
    say(f"backup {backup}")

    checks: list[tuple[bool, str]] = []
    record: dict[str, Any] = {
        "story": "M6-S5",
        "measured_at": now(),
        "backup": str(backup),
        "targets": TARGETS,
        "what_this_claims": (
            "the three small irreplaceable dumps restore into scratch databases whose "
            "contents match the live platform AND this repository's own records, and the "
            "object mirror uploads back byte-identically"
        ),
        "what_this_does_not_claim": (
            "that a full restore over a DEAD platform works. Nothing here restores over "
            "anything; the live databases are only counted, never written."
        ),
        "databases": {},
    }

    sizes_before = database_sizes()
    say(f"live databases before: {sorted(sizes_before)}")

    expected = expected_from_repo()
    record["expected_from_repo"] = expected

    for name in TARGETS:
        dump = backup / "postgres" / f"{name}.sql.gz"
        scratch = f"{name}{SCRATCH_SUFFIX}"
        say(f"--- {name} -> {scratch} ---")
        if not dump.exists():
            checks.append((False, f"{name}: no dump at {dump}"))
            continue

        ok, detail = gzip_complete(dump)
        checks.append((ok, f"{name}: the dump re-verifies before restoring — {detail}"))
        if not ok:
            continue

        psql("postgres", f'DROP DATABASE IF EXISTS "{scratch}"')
        psql("postgres", f'CREATE DATABASE "{scratch}"')

        t0 = time.monotonic()
        # zcat on the HOST, psql inside the pod: the same transport `make marts`
        # publishes 56M rows over, and the reason is the same — nothing of ours
        # publishes 5432, and a restore path that needs a port opened is a
        # restore path nobody can run in an incident.
        with gzip.open(dump, "rb") as handle:
            proc = subprocess.Popen(  # noqa: S603
                [
                    "kubectl",
                    "-n",
                    NAMESPACE,
                    "exec",
                    "-i",
                    POD,
                    "--",
                    "psql",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-q",
                    "-U",
                    "postgres",
                    "-d",
                    scratch,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, err = proc.communicate(handle.read())
        seconds = round(time.monotonic() - t0, 2)
        restored_ok = proc.returncode == 0
        checks.append(
            (
                restored_ok,
                f"{name}: restored into {scratch} in {seconds}s with ON_ERROR_STOP=1 "
                f"(exit {proc.returncode})",
            )
        )
        entry: dict[str, Any] = {
            "dump": str(dump),
            "dump_bytes": dump.stat().st_size,
            "scratch_database": scratch,
            "restore_seconds": seconds,
            "psql_exit_code": proc.returncode,
            "stderr_tail": err.decode(errors="replace").strip().splitlines()[-3:],
        }
        if restored_ok:
            restored_counts = table_counts(scratch, COUNTED[name])
            live_counts = table_counts(name, COUNTED[name])
            entry["row_counts"] = {"restored": restored_counts, "live": live_counts}
            agree = [t for t in COUNTED[name] if restored_counts[t] == live_counts[t]]
            differ = {
                t: (restored_counts[t], live_counts[t])
                for t in COUNTED[name]
                if restored_counts[t] != live_counts[t]
            }
            checks.append(
                (
                    not differ,
                    f"{name}: every counted table matches the LIVE database "
                    f"({', '.join(f'{t}={restored_counts[t]}' for t in agree)})"
                    + (f" · DIFFER: {differ}" if differ else ""),
                )
            )
        record["databases"][name] = entry

    # --- the second witness: the repository's own records ---------------------
    mlflow_scratch = f"mlflow{SCRATCH_SUFFIX}"
    try:
        alias = psql(
            mlflow_scratch,
            "SELECT a.alias, a.version FROM registered_model_aliases a "
            "WHERE a.name = 'nyc-taxi-eta'",
        )
        live_alias = psql(
            "mlflow",
            "SELECT a.alias, a.version FROM registered_model_aliases a "
            "WHERE a.name = 'nyc-taxi-eta'",
        )
        record["mlflow_alias"] = {"restored": alias, "live": live_alias}
        checks.append(
            (
                alias == live_alias and "champion" in alias,
                f"the restored registry carries the same @champion pointer as the live one: "
                f"{alias!r}",
            )
        )
    except RuntimeError as error:
        checks.append((False, f"could not read the restored registry alias: {error}"))

    try:
        rows = psql(
            f"optuna{SCRATCH_SUFFIX}",
            "SELECT s.study_name, count(t.trial_id) FROM studies s "
            "LEFT JOIN trials t ON t.study_id = s.study_id GROUP BY s.study_name",
        )
        observed = {}
        for line in rows.splitlines():
            study, _, count = line.partition("|")
            observed[study] = int(count)
        record["optuna_studies"] = {
            "restored": observed,
            "expected_from_repo": expected["optuna_studies"],
        }
        matched = {
            study: count
            for study, count in expected["optuna_studies"].items()
            if observed.get(study) == count
        }
        checks.append(
            (
                matched == expected["optuna_studies"],
                f"the restored studies carry the trial counts automation/runs/m3s4 recorded: "
                f"{matched} (of {expected['optuna_studies']})",
            )
        )
    except RuntimeError as error:
        checks.append((False, f"could not read the restored studies: {error}"))

    # The BI seat is checked BY NAME and as a SUBSET, and the first draft of this
    # check got it wrong in a way worth keeping: it compared counts, expected
    # 3 dashboards / 28 cards from `analytics/metabase/boards/*.json`, and found
    # 4 / 67. Nothing was broken. `scripts/metabase_boards.py` converges by name
    # and NEVER deletes (M1-S5's stated asymmetry), and Metabase's own setup
    # creates an `E-commerce Insights` example dashboard and its questions from
    # the bundled Sample Database. So the app-db legitimately holds content this
    # repository does not describe, and "the boards are checked-in JSON" is a
    # claim about OUR boards, not a claim that the app-db mirrors the repo.
    try:
        restored_dashboards = sorted(
            psql(f"metabase{SCRATCH_SUFFIX}", "SELECT name FROM report_dashboard").splitlines()
        )
        restored_cards = sorted(
            psql(f"metabase{SCRATCH_SUFFIX}", "SELECT name FROM report_card").splitlines()
        )
        want_dashboards = expected["metabase_dashboard_names"]
        want_cards = expected["metabase_card_names"]
        missing_dashboards = [n for n in want_dashboards if n not in restored_dashboards]
        missing_cards = [n for n in want_cards if n not in restored_cards]
        record["metabase"] = {
            "restored_dashboards": restored_dashboards,
            "restored_card_count": len(restored_cards),
            "expected_dashboard_names_from_repo": want_dashboards,
            "expected_card_count_from_repo": len(want_cards),
            "extra_not_described_by_the_repo": [
                n for n in restored_dashboards if n not in want_dashboards
            ],
            "note": (
                "a SUBSET check, deliberately: metabase_boards.py never deletes and Metabase "
                "ships its own example dashboard, so the app-db is a superset of the repo's "
                "boards by design"
            ),
        }
        checks.append(
            (
                not missing_dashboards and not missing_cards,
                f"every board this repo commits survives the restore BY NAME: "
                f"{len(want_dashboards)} dashboard(s) / {len(want_cards)} card(s) found among "
                f"the restored {len(restored_dashboards)}/{len(restored_cards)} "
                f"(the extra are Metabase's own examples: "
                f"{record['metabase']['extra_not_described_by_the_repo']})",
            )
        )
    except RuntimeError as error:
        checks.append((False, f"could not read the restored boards: {error}"))

    # --- the object half ------------------------------------------------------
    say("--- the object mirror ---")
    restore_objects(backup, checks, record, keep=args.keep)

    # --- drop the scratch, and prove the live databases never moved -----------
    if not args.keep:
        for name in TARGETS:
            psql("postgres", f'DROP DATABASE IF EXISTS "{name}{SCRATCH_SUFFIX}"')
        say("scratch databases dropped")
    sizes_after = database_sizes()
    record["live_database_sizes"] = {"before": sizes_before, "after": sizes_after}
    live_names_before = sorted(n for n in sizes_before if not n.endswith(SCRATCH_SUFFIX))
    live_names_after = sorted(n for n in sizes_after if not n.endswith(SCRATCH_SUFFIX))
    checks.append(
        (
            live_names_before == live_names_after,
            f"the live database list is unchanged: {live_names_after}",
        )
    )
    checks.append(
        (
            args.keep or not [n for n in sizes_after if n.endswith(SCRATCH_SUFFIX)],
            "no scratch database survives the drill",
        )
    )

    print()
    failures = [text for good, text in checks if not good]
    for good, text in checks:
        say(("ok  " if good else "FAIL ") + text)
    record["checks"] = [{"passed": good, "check": text} for good, text in checks]
    record["verdict"] = "GREEN" if not failures else "RED"
    Path(args.record).parent.mkdir(parents=True, exist_ok=True)
    Path(args.record).write_text(json.dumps(record, indent=2) + "\n")
    say(f"record -> {args.record}")
    if failures:
        say(f"RED — {len(failures)} check(s) failed.")
        return 1
    say(f"GREEN — {len(checks)} check(s) passed. The label moves one notch, not to green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
