#!/usr/bin/env bash
# port_precheck.sh — refuse to build on top of a foreign stack (gotcha #10).
#
# The fleet rule: this laptop may host other project stacks. kind publishes its
# host ports at CREATE time, and the platform services claim the rest during M0
# S3+. A port already held by somebody else surfaces as an opaque failure deep
# inside `kind create` or a helm wait — hours later, far from the cause. So we
# look first, and we name the port and its holder when we refuse.
#
# Checked set = the CLAUDE.md "Port family" + every hostPort in the kind config
# (parsed, so the recipe stays the single source of truth for what kind binds).
#
# Usage:
#   scripts/port_precheck.sh              # the real check (family + kind config)
#   scripts/port_precheck.sh 5000 9000    # explicit ports — used by the unit
#                                         # tests; NOT a bypass (cluster.sh
#                                         # never passes arguments).
#
# Exit: 0 all clear · 2 at least one port busy · 1 misuse / missing `ss`.
#
# KNOWN LIMITATION (WSL2, unverified as of 2026-08-16): `ss` sees only listeners
# inside the WSL VM. A Windows-side process holding e.g. 5000 is invisible here,
# yet Docker Desktop publishes container ports on the Windows host too — so a
# clean pre-check does not prove a Windows-side port is free. If a bind fails
# anyway, check the Windows side with `Get-NetTCPConnection -LocalPort <p>`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND_CONFIG="${KIND_CONFIG:-$REPO_ROOT/infra/kind/kind-config.yaml}"

# The port family — human-readable twin lives in CLAUDE.md "Port family".
# Change both together; a drifting pair is worse than either alone.
declare -A PURPOSE=(
  [5000]="MLflow UI"
  [9000]="MinIO API"
  [9001]="MinIO console"
  [8080]="Flyte console"
  [3000]="Grafana"
  [8081]="KServe ingress"
  [9091]="Pushgateway"
  [3030]="Metabase"
  [5432]="Postgres (in-cluster only — a host listener here is a foreign stack)"
)

if ! command -v ss >/dev/null 2>&1; then
  echo "[ports] FAIL: 'ss' not found (iproute2). Cannot verify ports; refusing to guess." >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  PORTS=("$@")
else
  PORTS=("${!PURPOSE[@]}")
  if [[ -f "$KIND_CONFIG" ]]; then
    while read -r hp; do
      [[ -n "$hp" ]] && PORTS+=("$hp")
    done < <(awk '/hostPort:/ {gsub(/[^0-9]/, "", $2); if ($2 != "") print $2}' "$KIND_CONFIG")
  fi
fi

# de-duplicate, keep numeric order for a stable, readable report
mapfile -t PORTS < <(printf '%s\n' "${PORTS[@]}" | sort -n -u)

snapshot="$(ss -tlnp 2>/dev/null || ss -tln)"

busy=()
declare -A HOLDER=()
for p in "${PORTS[@]}"; do
  hit="$(printf '%s\n' "$snapshot" | awk -v pat=":${p}\$" 'NR > 1 && $4 ~ pat {print; exit}')"
  if [[ -n "$hit" ]]; then
    busy+=("$p")
    HOLDER[$p]="$hit"
  fi
done

if [[ ${#busy[@]} -eq 0 ]]; then
  echo "[ports] OK — all ${#PORTS[@]} required ports free: ${PORTS[*]}"
  exit 0
fi

echo "[ports] REFUSING: ${#busy[@]} of ${#PORTS[@]} required ports are already in use." >&2
for p in "${busy[@]}"; do
  echo "  port ${p} (${PURPOSE[$p]:-kind hostPort}) held by:" >&2
  echo "    ${HOLDER[$p]}" >&2
done
cat >&2 <<'EOM'
[ports] This is gotcha #10: another stack on this machine owns a port we need.
        Free it (stop that stack) and re-run — do NOT renumber our ports, the
        family in CLAUDE.md is what every later milestone and runbook assumes.
EOM
exit 2
