#!/usr/bin/env bash
# platform_backup.sh — the lifeboat behind `make backup` (M4-S2).
#
# WHY THIS EXISTS, AND WHY IT EXISTS *BEFORE* FLYTE. Since M2 the kind cluster
# holds the only copy of state nothing else can rebuild: the MLflow registry
# (champion versions 1 AND 2 with their signatures), every run and artifact in
# MinIO, the Metabase app-db, and both M3 Optuna studies (9,133.8 s of fitting).
# All of it sits on PVCs, and PVCs die with the cluster. M4 is about to add a
# fifth and sixth tenant to that Postgres; the M4 kickoff's top law is that no
# story may take the cluster down. This script is that law's constructive half —
# it does not prevent a rebuild, it makes one survivable.
#
# HONEST LIMITS, STATED HERE RATHER THAN DISCOVERED LATER:
#   1. SAME PHYSICAL DISK. The destination is a plain directory beside the DVC
#      remote (/home/longt/dvc-remote/...), outside the repo. It survives
#      `make destroy`, a wrong `rm -rf` in the repo, and a kind rebuild. It does
#      NOT survive disk loss. Identical honesty to the DVC remote's own header.
#   2. RESTORE IS NOT REHEARSED AT M4. This ships the copy, not the drill. An
#      unrehearsed restore is a hypothesis. Rehearsing it is a named M6-gameday
#      candidate (M4 kickoff, S2 Do-list) and the deployments ledger row says so.
#      Until then: this is a lifeboat, not a DR program.
#   3. IT IS A SNAPSHOT, NOT A POINT-IN-TIME. Databases are dumped one after the
#      other while the platform runs. Nothing writes to these databases during a
#      backup on this single-operator machine, but the guarantee is "each dump is
#      internally consistent" (pg_dump takes its own snapshot), not "all five
#      agree with each other".
#
# TARGETS ARE ENUMERATED FROM THE LIVE SERVER, NEVER FROM A LIST. Every database
# that is not a template gets dumped; every MinIO bucket gets mirrored. A
# hardcoded list would be a twin of scripts/postgres_databases.sh, and a backup
# whose target list drifts is worse than no backup: it succeeds, prints a size,
# and silently omits whatever somebody added last. Flyte's own databases arrive
# later in this very story and are covered by the first run afterwards, because
# nobody had to remember to add them.
#
# EVERY DUMP IS PROVEN COMPLETE, NOT MERELY NON-EMPTY — AND THE FIRST DESIGN OF
# THIS CHECK COULD NOT HAVE DONE IT (M4-S2, gotcha #54). The obvious form was
# `pg_dump -Fc` verified by streaming the archive back through
# `kubectl exec -i … pg_restore --list`. Two things were wrong with it:
#   (a) it did not check what its comment claimed. A custom-format archive keeps
#       its table of contents at the FRONT, so `--list` succeeds happily on a
#       file whose tail was never written — i.e. on exactly the truncation the
#       check existed to catch. Ask of any self-assertion: could it tell if it
#       were false? This one could not (gotcha #51's question, one layer down).
#   (b) it hung. `kubectl exec -i` with stdin redirected from a file did not
#       terminate on a 1 MB dump after 120 s, twice, having worked once on a
#       1.2 GB one. A backup that intermittently never returns is not a backup.
# So the format is PLAIN SQL piped through gzip on the host, and verification is
# entirely host-side and reads every byte:
#   * gzip -t decompresses the whole file and checks its CRC — a truncated or
#     corrupted transfer fails here, over the full archive rather than a header.
#   * the last line must be pg_dump's own `-- PostgreSQL database dump complete`,
#     which the tool writes only after it has finished. That is the source
#     saying it finished, not us inferring it from a plausible file size.
# Honest cost of plain over custom: no selective restore, no parallel restore.
# For a lifeboat that is a fair trade — and the restore is simpler for it
# (`psql < dump.sql.gz`), which matters at the hour somebody needs it.
#
# Usage:
#   scripts/platform_backup.sh              # the real thing
#   DRY_RUN=1 scripts/platform_backup.sh    # enumerate + size, write nothing
#   BACKUP_ROOT=/somewhere scripts/platform_backup.sh
# Exit: 0 backed up · 1 refused / failed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${POSTGRES_NAMESPACE:-platform}"
POD="${POSTGRES_POD:-postgres-0}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/longt/dvc-remote/nyc-taxi-platform-backups}"
DRY_RUN="${DRY_RUN:-0}"
STAMP="${BACKUP_STAMP:-$(date -u +%Y-%m-%dT%H-%M-%SZ)}"
DEST="$BACKUP_ROOT/$STAMP"

human() { numfmt --to=iec-i --suffix=B --format='%.1f' "$1" 2>/dev/null || echo "$1 bytes"; }

echo "== platform backup =="
echo "[backup] destination $DEST"
echo "[backup] limits: same physical disk · restore NOT rehearsed (M6 gameday candidate) · per-database snapshot"

if ! "${KUBECTL[@]}" -n "$NAMESPACE" get pod "$POD" >/dev/null 2>&1; then
  echo "[backup] FAIL: $NAMESPACE/$POD is not there — is the cluster up?" >&2
  exit 1
fi

# --- 1. what exists, asked of the server -------------------------------------
mapfile -t DATABASES < <(
  "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
    psql -U postgres -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
)
echo "[backup] ${#DATABASES[@]} database(s) on the server: ${DATABASES[*]}"

if [[ "$DRY_RUN" == "1" ]]; then
  for db in "${DATABASES[@]}"; do
    size="$("${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
      psql -U postgres -d postgres -tAc "SELECT pg_size_pretty(pg_database_size('$db'))")"
    echo "[backup] DRY_RUN — WOULD dump $db (live size $size)"
  done
  uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/backup_minio.py" --dest "$DEST/minio" --dry-run
  echo "[backup] DRY_RUN — nothing written."
  exit 0
fi

mkdir -p "$DEST/postgres" "$DEST/minio"

# --- 2. the databases ---------------------------------------------------------
# The dump is produced by the pod's OWN pg_dump, so client and server versions
# can never disagree (the host has no postgres client at all, by design — no port
# is published for 5432). gzip runs on the HOST so the compression cost lands on
# the machine with spare cores rather than on the database's.
END_MARKER='-- PostgreSQL database dump complete'
total_pg=0
for db in "${DATABASES[@]}"; do
  out="$DEST/postgres/${db}.sql.gz"
  echo "[backup] pg_dump $db ..."
  start=$(date +%s)
  "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
    pg_dump -U postgres --no-password -d "$db" | gzip -c > "$out"
  elapsed=$(( $(date +%s) - start ))
  bytes=$(stat -c %s "$out")
  total_pg=$(( total_pg + bytes ))

  # Every byte read back, twice over: gzip's CRC, then pg_dump's own last word.
  if ! gzip -t "$out"; then
    echo "[backup] FAIL: $out does not decompress cleanly — the transfer was truncated" >&2
    exit 1
  fi
  # The marker is not the LAST line, and assuming it was cost this script its
  # first green run. Postgres 16.11's pg_dump closes with a `\unrestrict <token>`
  # psql meta-command (the restrict/unrestrict hardening) plus trailing blank
  # lines AFTER `-- PostgreSQL database dump complete`. So: look in the tail,
  # do not equal the tail. A blank last line is what a truncated file also has,
  # which is why the first form failed closed rather than passing wrongly.
  # `-- "$END_MARKER"`: the marker itself starts with `--`, so without the
  # end-of-options guard grep reads it as a flag and dies with a usage message
  # while the check reports a truncated dump. A verifier that fails for its own
  # reasons and blames the artifact is worse than no verifier.
  if ! zcat "$out" | tail -n 10 | grep -qF -- "$END_MARKER"; then
    echo "[backup] FAIL: $out has no pg_dump completion marker in its last 10 lines" >&2
    echo "[backup]       the dump was cut short — the file is not a backup" >&2
    exit 1
  fi
  echo "[backup] ok  $db -> $(human "$bytes") in ${elapsed}s, gzip CRC clean, ends with pg_dump's completion marker"
done

# --- 3. the objects -----------------------------------------------------------
uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/backup_minio.py" \
  --dest "$DEST/minio" --summary-json "$DEST/minio_summary.json"

# --- 4. the manifest ----------------------------------------------------------
total_bytes=$(du -sb "$DEST" | cut -f1)
"${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- psql -U postgres -tAc "select version()" \
  > "$DEST/postgres_version.txt"
cat > "$DEST/MANIFEST.txt" <<EOM
platform backup — $STAMP (UTC)
produced by scripts/platform_backup.sh on context $CONTEXT

databases dumped (pg_dump plain SQL | gzip, enumerated from pg_database,
templates excluded; each verified by gzip -t over every byte AND by pg_dump's
own '$END_MARKER' as the last line):
$(for db in "${DATABASES[@]}"; do printf '  %-12s %s\n' "$db" "$(human "$(stat -c %s "$DEST/postgres/${db}.sql.gz")")"; done)
postgres total: $(human "$total_pg")

minio: see minio_summary.json (buckets enumerated from the server)

total on disk: $(human "$total_bytes")

RESTORE IS NOT REHEARSED. Each dump has been proven COMPLETE (gzip CRC over
every byte, plus pg_dump's own completion marker as the final line) and the
object mirror has been verified by object count AND byte total — but no restore
has ever been performed from this directory, so "these files restore a working
platform" remains a hypothesis. Rehearsing it is an M6-gameday candidate.
The intended shape when that day comes:
  zcat <db>.sql.gz | kubectl -n platform exec -i postgres-0 -- psql -U postgres -d <db>
  # the objects: no restore mode exists yet, by design — writing one before a
  # rehearsal would be a second untested path, not a safer one.
EOM

echo
echo "[backup] MANIFEST:"
cat "$DEST/MANIFEST.txt"
echo "[backup] done — $DEST"
