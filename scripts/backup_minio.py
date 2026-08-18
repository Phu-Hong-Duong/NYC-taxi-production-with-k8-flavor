"""backup_minio.py — mirror every MinIO bucket to a host directory.

The object half of `make backup` (M4-S2). The database half is pg_dump inside
scripts/platform_backup.sh; this is the half that carries the MLflow artifacts —
every logged model, signature, input example and plot for both champion
versions. They live on a PVC, and PVCs die with the cluster.

WHY HOST-SIDE boto3 AND NOT `mc mirror` IN THE POD. `mc` does exist at
/usr/bin/mc inside the MinIO image, but it can only write to paths the POD can
see, so a pod-side mirror would land the copy on the very PVC it is meant to
survive, and getting it out again means `kubectl cp` of a directory — a second
transfer with its own failure modes. The client-writes-directly-to-MinIO path is
already this program's architecture (gotcha #5: the tracking server does not
proxy artifacts, so `boto3` is a declared dependency and the MinIO API is
published on the host at 9000 by a kind hostPort). We back up the way we write.

BUCKETS ARE ENUMERATED FROM THE SERVER, NEVER FROM A LIST. A hardcoded
`mlflow-artifacts` would be a twin of the deploy recipe, and a backup whose
target list drifts is worse than no backup: it succeeds, prints a size, and
omits the bucket somebody added last month. Flyte's blob store arrives in this
same story — it is backed up from the first run, because nobody had to remember.

Usage:
  uv run python scripts/backup_minio.py --dest <dir>          # mirror
  uv run python scripts/backup_minio.py --dest <dir> --dry-run
Exit: 0 mirrored (a JSON summary on stdout) · 1 refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env(env_file: Path) -> dict[str, str]:
    """Read .env without exporting it — the same contract platform_secrets.sh has.

    No value from here is ever printed; the summary carries endpoints and sizes.
    """
    if not env_file.exists():
        raise SystemExit(
            f"[backup-minio] FAIL: no {env_file} (scripts/platform_secrets.sh owns it)"
        )
    env: dict[str, str] = {}
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def mirror(dest: Path, *, dry_run: bool = False, env_file: Path | None = None) -> dict:
    import boto3
    from botocore.config import Config

    env = load_env(env_file or REPO_ROOT / ".env")
    endpoint = env.get("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
    # The ROOT credential, not the `mlflow` user: the point of enumerating
    # buckets from the server is seeing ALL of them, and the mlflow user is
    # scoped to its own. Nothing is printed, and nothing is written to disk.
    access = env.get("MINIO_ROOT_USER")
    secret = env.get("MINIO_ROOT_PASSWORD")
    if not access or not secret:
        raise SystemExit("[backup-minio] FAIL: .env has no MINIO_ROOT_USER/MINIO_ROOT_PASSWORD")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=env.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )

    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    names = ", ".join(buckets) or "(none)"
    print(f"[backup-minio] endpoint {endpoint} — {len(buckets)} bucket(s): {names}")

    summary = {"endpoint": endpoint, "buckets": [], "objects": 0, "bytes": 0}
    for bucket in buckets:
        n_obj = 0
        n_bytes = 0
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                key, size = obj["Key"], obj["Size"]
                n_obj += 1
                n_bytes += size
                if dry_run:
                    continue
                target = dest / bucket / key
                target.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(bucket, key, str(target))
        summary["buckets"].append({"name": bucket, "objects": n_obj, "bytes": n_bytes})
        summary["objects"] += n_obj
        summary["bytes"] += n_bytes
        verb = "would mirror" if dry_run else "mirrored"
        print(f"[backup-minio] {verb} {bucket}: {n_obj} object(s), {n_bytes / 1048576:.1f} MiB")

    if not dry_run:
        # A copy is only a backup if what landed equals what was listed. Counting
        # the files on disk is a different measurement from counting the keys the
        # server returned, which is the whole point of making it.
        for entry in summary["buckets"]:
            root = dest / entry["name"]
            on_disk = [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
            if len(on_disk) != entry["objects"]:
                raise SystemExit(
                    f"[backup-minio] FAIL: {entry['name']} listed {entry['objects']} object(s) "
                    f"but {len(on_disk)} file(s) landed on disk"
                )
            landed = sum(p.stat().st_size for p in on_disk)
            if landed != entry["bytes"]:
                raise SystemExit(
                    f"[backup-minio] FAIL: {entry['name']} listed {entry['bytes']} byte(s) "
                    f"but {landed} byte(s) landed on disk"
                )
        n = summary["objects"]
        print(f"[backup-minio] ok  {n} object(s) verified on disk by count AND bytes")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", required=True, help="directory to mirror into (created if absent)")
    ap.add_argument("--dry-run", action="store_true", help="list and size, write nothing")
    ap.add_argument("--summary-json", help="write the summary here as well as to stdout")
    args = ap.parse_args(argv)

    dest = Path(args.dest)
    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    summary = mirror(dest, dry_run=args.dry_run)
    if args.summary_json and not args.dry_run:
        Path(args.summary_json).write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
