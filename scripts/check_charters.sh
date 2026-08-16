#!/usr/bin/env bash
# check_charters.sh — "every charter carries at least three refusals" (M0 gate,
# BLUEPRINT §9/M0), checked mechanically instead of by reading and nodding.
#
# ROLES.md's own first line says it: "A role that cannot say no is decoration".
# The gate turns that into a number, so this script turns the number into a test.
#
# Shape it parses (docs/org/ROLES.md):
#   ## XX — Title
#   Mission: ...
#   Produces: ...
#   REFUSES: item one; item two;
#   item three continued across lines.
#   Tensions: ...
# Refusal items are separated by ';' and the block ends at `Tensions:`, the next
# `## ` heading, or EOF.
#
# Usage: scripts/check_charters.sh [roles-file] [min-refusals]
# Exit:  0 every charter passes · 1 file missing/unparseable · 2 a charter is short
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROLES="${1:-$REPO_ROOT/docs/org/ROLES.md}"
MIN="${2:-3}"

if [[ ! -f "$ROLES" ]]; then
  echo "[charters] FAIL: no such file: $ROLES" >&2
  exit 1
fi

# awk prints one "ROLE<TAB>COUNT" row per charter; the shell judges. Splitting it
# that way keeps the counting testable and the verdict readable.
report="$(awk -v OFS='\t' '
  function flush_role() {
    if (role == "") return
    n = 0
    if (refuses != "") {
      m = split(refuses, parts, ";")
      for (i = 1; i <= m; i++) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", parts[i])
        gsub(/^[.[:space:]]+$/, "", parts[i])
        if (parts[i] != "") n++
      }
    }
    print role, n
    role = ""; refuses = ""; collecting = 0
  }
  /^## / {
    flush_role()
    line = substr($0, 4)
    split(line, h, " — ")           # em dash separates id from title
    role = h[1]
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", role)
    next
  }
  /^REFUSES:/ { refuses = substr($0, 9); collecting = 1; next }
  collecting && /^(Tensions:|Mission:|Produces:)/ { collecting = 0; next }
  collecting && /^[[:space:]]*$/ { collecting = 0; next }
  collecting { refuses = refuses " " $0 }
  END { flush_role() }
' "$ROLES")"

if [[ -z "$report" ]]; then
  echo "[charters] FAIL: no '## ' charter headings found in $ROLES — refusing to pass a file I could not parse." >&2
  exit 1
fi

fails=0
total=0
while IFS=$'\t' read -r role count; do
  total=$((total + 1))
  if (( count >= MIN )); then
    printf '   ok   %-4s %d refusals\n' "$role" "$count"
  else
    printf '   FAIL %-4s %d refusals (minimum %d)\n' "$role" "$count" "$MIN" >&2
    fails=$((fails + 1))
  fi
done <<< "$report"

if (( fails > 0 )); then
  echo "[charters] REFUSING: $fails of $total charters carry fewer than $MIN refusals." >&2
  echo "[charters] A charter without teeth is decoration (docs/org/ROLES.md, line 3)." >&2
  exit 2
fi

echo "[charters] OK — all $total charters carry >= $MIN refusals."
