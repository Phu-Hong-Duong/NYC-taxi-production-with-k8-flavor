#!/usr/bin/env bash
# Prove the 100-pair parity table can go RED. (M8-S4)
#
# A table of zeros is not evidence until something has been watched making it
# non-zero. Both halves of this comparison come out of the same Feast install, so
# the reading a sceptic should reach for first is "two reads of one store will
# always agree" — this drill is the answer to that reading, and it is the reason
# `docs/feast_online_parity_table.md` is worth committing.
#
# WHAT IS PLANTED. One OD pair's serialized feature bytes are copied onto ANOTHER
# pair's Redis key (`infra/feast/online_redteam.py`). Every byte written was
# written by Feast: the protobuf parses, the dtype is right, the value is a real
# median from a real pair, and nothing logs anything. That is what a wrong-row or
# wrong-stamp materialization looks like from the outside, and it is precisely
# the failure the OFFLINE store cannot detect for itself. A drill that planted
# garbage would prove the parser works.
#
# WHERE IT IS PLANTED. Row 92 of the declared set — the pair whose median moves
# most across its point-in-time windows — chosen in advance by
# `docs/feast_online_m8.md` §3 as the row where a wrong value shows up by the
# largest margin. The donor is derived, not typed.
#
# WHAT MUST HOLD:
#   1. the parity run goes RED, exit 1, NAMING od_window.od_median_duration_min
#   2. the other 15 columns still pass — a gate that fails on any edit is a
#      checksum, not a gate (the verify-m3 red team's rule)
#   3. the restore is byte-identical by sha256 over the hash
#   4. the re-run is GREEN again and `git status` is clean
#
# It writes NO record and NO table: both parity runs use `--no-write`, so the
# committed accept artifact is never overwritten with a tampered verdict. It
# re-materializes nothing, deploys nothing, and touches exactly one Redis hash.
#
#   bash scripts/feast_online_parity_redteam.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
VENV_PY="$REPO_ROOT/.venv-feast/bin/python"
REDTEAM="$REPO_ROOT/infra/feast/online_redteam.py"
# 6381, not the 6380 the parity run uses: the two forwards are alive at the same
# time and a shared local port would make the drill fail for its own reasons
# (gotcha #55's family).
LOCAL_PORT="${FEAST_REDTEAM_PORT:-6381}"
SAVE="$(mktemp)"
NAMED_COLUMN="od_window.od_median_duration_min"

FAILURES=0
note() { echo "[redteam] $*"; }
check() { if [[ "$1" == "0" ]]; then note "ok  $2"; else note "FAIL $2"; FAILURES=$((FAILURES + 1)); fi; }

read -r TARGET DONOR < <(uv run python scripts/feast_online_pairs.py --print-redteam-pair | tail -1)
note "target $TARGET   donor $DONOR   (both DERIVED from the published source)"

kubectl --context "$CONTEXT" -n feast port-forward svc/redis "${LOCAL_PORT}:6379" >/tmp/redteam-fwd.$$ 2>&1 &
FWD_PID=$!
RESTORED=0
cleanup() {
  if [[ "$RESTORED" == "0" ]]; then
    note "cleanup: restoring the store before exit"
    FEAST_REDIS_CONNECTION="localhost:${LOCAL_PORT}" "$VENV_PY" "$REDTEAM" \
      --mode restore --target "$TARGET" --save "$SAVE" || true
  fi
  kill "$FWD_PID" 2>/dev/null || true
  rm -f "$SAVE" "/tmp/redteam-fwd.$$"
}
trap cleanup EXIT

for _ in $(seq 1 40); do grep -q "Forwarding from" "/tmp/redteam-fwd.$$" && break; sleep 0.25; done
grep -q "Forwarding from" "/tmp/redteam-fwd.$$" || { note "FAIL the port-forward never came up"; exit 1; }
export FEAST_REDIS_CONNECTION="localhost:${LOCAL_PORT}"

BEFORE="$("$VENV_PY" "$REDTEAM" --mode digest --target "$TARGET" --save "$SAVE")"
note "hash digest before: $BEFORE"

note "planting..."
"$VENV_PY" "$REDTEAM" --mode plant --target "$TARGET" --donor "$DONOR" --save "$SAVE" || exit 1

note "running the parity against the tampered store (--no-write)"
set +e
TAMPERED="$(uv run python scripts/feast_online_parity.py --no-write 2>&1)"
TAMPERED_RC=$?
set -e
echo "$TAMPERED" | grep -E "FAIL|max \|online" | sed 's/^/[redteam]   /'

[[ "$TAMPERED_RC" == "1" ]]; check $? "the parity run exited 1 (observed $TAMPERED_RC)"
echo "$TAMPERED" | grep -q "FAIL $NAMED_COLUMN"; check $? "it NAMED $NAMED_COLUMN"
STILL_OK="$(echo "$TAMPERED" | grep -c "^\[online-parity\]   ok  ")"
[[ "$STILL_OK" -ge 25 ]]; check $? "$STILL_OK other sub-check line(s) still passed (a gate that fails on any edit is a checksum)"

note "restoring..."
"$VENV_PY" "$REDTEAM" --mode restore --target "$TARGET" --save "$SAVE"; check $? "restore reported byte-identical"
RESTORED=1
AFTER="$("$VENV_PY" "$REDTEAM" --mode digest --target "$TARGET" --save "$SAVE")"
[[ "$BEFORE" == "$AFTER" ]]; check $? "sha256 over the hash is identical ($AFTER)"

note "re-running the parity (--no-write)"
set +e
uv run python scripts/feast_online_parity.py --no-write >/tmp/redteam-green.$$ 2>&1
GREEN_RC=$?
set -e
[[ "$GREEN_RC" == "0" ]]; check $? "the untampered run is GREEN again (exit $GREEN_RC)"
grep -q "PASSED" /tmp/redteam-green.$$; check $? "it printed PASSED"
rm -f /tmp/redteam-green.$$

[[ -z "$(git status --porcelain)" ]]; check $? "the working tree is clean — the drill left no residue"

if [[ "$FAILURES" -eq 0 ]]; then
  note "PASSED — the table can go RED, names the planted column, and restores exactly"
  exit 0
fi
note "FAILED — $FAILURES check(s) did not hold"
exit 1
