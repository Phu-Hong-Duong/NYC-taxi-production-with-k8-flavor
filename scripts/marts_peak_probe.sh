#!/usr/bin/env bash
# marts_peak_probe.sh — run a publish and measure what it costs the volume (M4-S5).
#
# D-003 is a debt about a NUMBER: `make marts` full-refreshes `trips_clean`, so the
# live table and its staging copy coexist mid-swap and the `marts` database peaks
# at ~23 GB against a ~13 GB steady state. The row says the debt closes on either
# an incremental materialisation or a recorded decision that full refresh stays —
# and in both cases with the number RE-MEASURED, because M1-S4's 23 GB is a
# measurement of 2026-08-16 and a debt argued from a remembered number is a debt
# argued from nothing.
#
# So this wraps a publish and samples the thing that actually pays: the size of the
# `marts` DATABASE, which includes the staging table, its indexes and the dead
# tuples a DELETE leaves behind. It also samples the postgres pod's filesystem,
# because a database that fits and a volume that fills are different failures.
#
# IT MEASURES, IT DOES NOT JUDGE. There is no threshold here and no exit code
# beyond the wrapped command's: a bar invented in a probe would be a gate nobody
# voted for (gates and thresholds are configs/*.yaml and a PO fork). The decision
# reads these numbers in docs/pipeline_m4.md.
#
# Usage: scripts/marts_peak_probe.sh <label> -- <command...>
#        scripts/marts_peak_probe.sh full-refresh -- make marts
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${POSTGRES_NAMESPACE:-platform}"
POD="${POSTGRES_POD:-postgres-0}"
KUBECTL=(kubectl --context "${KUBE_CONTEXT:-kind-mlops-taxi}")
INTERVAL="${PROBE_INTERVAL:-5}"
OUT_DIR="${PROBE_DIR:-$REPO_ROOT/automation/runs/m4-marts}"

LABEL="${1:?usage: marts_peak_probe.sh <label> -- <command...>}"; shift
[[ "${1:-}" == "--" ]] && shift
[[ $# -gt 0 ]] || { echo "[peak] no command given" >&2; exit 2; }

mkdir -p "$OUT_DIR"
SAMPLES="$OUT_DIR/${LABEL}.samples.tsv"
SUMMARY="$OUT_DIR/${LABEL}.json"

# One psql per sample. Two numbers: the database's own size (what the marts cost)
# and the mount's used bytes (what the node pays). `-tA` so the output is the value
# and nothing else — a header row would become a sample.
sample() {
  "${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- sh -c \
    "psql -tA -U postgres -d postgres -c \"select pg_database_size('marts')\"; \
     df -B1 --output=used /var/lib/postgresql/data | tail -1" 2>/dev/null \
    | tr '\n' '\t'
}

echo "== marts peak probe: $LABEL =="
printf 'epoch\tmarts_bytes\tpgdata_used_bytes\n' >"$SAMPLES"

# The sampler is a child of THIS script and is killed on EXIT, so it cannot
# outlive the measurement it is measuring. It writes one line per interval; a
# sample that fails (the pod busy, a connection refused) writes nothing rather
# than a zero — a zero would become the minimum and make the delta look enormous.
(
  while :; do
    line="$(sample || true)"
    [[ -n "${line// /}" ]] && printf '%s\t%s\n' "$(date +%s)" "$line" >>"$SAMPLES"
    sleep "$INTERVAL"
  done
) &
sampler=$!
trap 'kill "$sampler" 2>/dev/null || true' EXIT

started=$(date +%s)
rc=0
"$@" || rc=$?
finished=$(date +%s)

kill "$sampler" 2>/dev/null || true
sleep 1
# One last sample AFTER the command, because the steady state is what the volume
# lives with and the run's last in-flight sample is not it.
printf '%s\t%s\n' "$(date +%s)" "$(sample || true)" >>"$SAMPLES"

python3 - "$SAMPLES" "$SUMMARY" "$LABEL" "$started" "$finished" "$rc" "$*" "$INTERVAL" <<'PY'
import json, sys

samples_path, summary_path, label, started, finished, rc, command, interval = sys.argv[1:9]
rows = []
for line in open(samples_path).read().splitlines()[1:]:
    parts = [p for p in line.split("\t") if p.strip()]
    if len(parts) >= 3:
        rows.append((int(parts[0]), int(parts[1]), int(parts[2])))

if not rows:
    sys.exit("[peak] no samples were taken — is the postgres pod reachable?")

marts = [r[1] for r in rows]
used = [r[2] for r in rows]
gib = lambda n: round(n / 2**30, 2)  # noqa: E731 — one local formatter, read twice

summary = {
    "label": label,
    "command": command,
    "exit_code": int(rc),
    "seconds": int(finished) - int(started),
    "samples": len(rows),
    # Recorded because it BOUNDS the honesty of the peak: a 5 s sampler cannot see a
    # spike shorter than 5 s, so a reader has to know the resolution the number was
    # measured at. The first run of this probe left it null, which is exactly the
    # kind of missing denominator that turns a measurement into a claim.
    "interval_seconds": float(interval),
    "marts_db_start_gib": gib(marts[0]),
    "marts_db_peak_gib": gib(max(marts)),
    "marts_db_end_gib": gib(marts[-1]),
    "marts_db_peak_over_end": round(max(marts) / marts[-1], 3) if marts[-1] else None,
    "pgdata_used_start_gib": gib(used[0]),
    "pgdata_used_peak_gib": gib(max(used)),
    "pgdata_used_end_gib": gib(used[-1]),
}
json.dump(summary, open(summary_path, "w"), indent=2)
print(f"[peak] {label}: {summary['seconds']}s, {summary['samples']} samples")
print(f"[peak]   marts database  start {summary['marts_db_start_gib']} GiB  "
      f"PEAK {summary['marts_db_peak_gib']} GiB  end {summary['marts_db_end_gib']} GiB "
      f"(peak/end {summary['marts_db_peak_over_end']}x)")
print(f"[peak]   PGDATA used     start {summary['pgdata_used_start_gib']} GiB  "
      f"peak {summary['pgdata_used_peak_gib']} GiB  end {summary['pgdata_used_end_gib']} GiB")
print(f"[peak] -> {summary_path}")
PY

exit "$rc"
