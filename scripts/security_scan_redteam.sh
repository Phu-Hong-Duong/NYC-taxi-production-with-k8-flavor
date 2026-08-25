#!/usr/bin/env bash
# M9-S9 — prove the secret scan can FIND one.
#
# "Zero secrets" is the answer this story expects and the answer a broken scanner
# gives. `make security-scan` records its inputs so a reader can see it looked;
# this watches it actually catch something, in the two places that matter and in
# the two CLASSES the triage keeps apart:
#
#   arm A — a credential in an untracked, unignored working-tree file. That is
#           the dangerous middle: one `git add -A` from history, and the scan
#           must call it BLOCKING rather than filing it beside `.env`.
#   arm B — a credential in a real COMMIT on a scratch branch. This is the one
#           that tests the claim the whole story rests on: that the history leg
#           walks every ref and not just HEAD's ancestry.
#
# THE PLANTED VALUE IS GENERATED AT RUN TIME AND APPEARS NOWHERE IN THIS FILE.
# A drill that carried a credential-shaped literal would become a finding in the
# scan it exists to test — which is not hypothetical: the first version of the
# scan's own RECORD tripped `generic-api-key` thirteen times on its own sha256
# fields, and it was right to.
#
# CLEANUP IS PART OF THE DRILL, NOT ITS EPILOGUE. Arm B writes a real object into
# this clone's store, so the branch is deleted, the reflog expired and the object
# pruned, and then the history scan is RE-RUN and required to come back clean —
# because "I deleted the branch" and "the object is gone" are different claims
# and only the second one is what publishing cares about. Nothing is ever pushed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SCRATCH_BRANCH="redteam/m9-s9-planted-secret"
PLANT_FILE="redteam_planted_credential.txt"
RECORD="automation/runs/m9-security/scan.json"
FAILURES=0
CHECKS=0
START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[sec-redteam] FAIL: the working tree is dirty. This drill commits and then" >&2
  echo "[sec-redteam]       destroys history; it refuses to run over uncommitted work." >&2
  exit 2
fi

RECORD_BEFORE=""
[[ -f "$RECORD" ]] && RECORD_BEFORE="$(sha256sum "$RECORD" | awk '{print $1}')"

cleanup() {
  local rc=$?
  echo
  echo "[sec-redteam] restoring"
  rm -f "$PLANT_FILE"
  git checkout -q "$START_BRANCH" 2>/dev/null || true
  git branch -D "$SCRATCH_BRANCH" >/dev/null 2>&1 || true
  git reflog expire --expire-unreachable=now --all >/dev/null 2>&1 || true
  git gc --prune=now --quiet >/dev/null 2>&1 || true
  return $rc
}
trap cleanup EXIT

check() {  # $1 = description, $2 = 1 for pass
  CHECKS=$((CHECKS + 1))
  if [[ "$2" == "1" ]]; then
    echo "  ok  $1"
  else
    echo "  FAIL $1" >&2
    FAILURES=$((FAILURES + 1))
  fi
}

# The plant: an AWS-shaped access key id + secret, both generated at run time.
# Real shape, never a real key, and never written into a tracked file.
#
# The generator moved to `scripts/redteam_plant.py` at M9-S13, when the hook drill
# needed the same one: F-071 is the record of what goes wrong when a plant is
# drawn without regard for the rules that must match it, and a lesson learned in
# one copy of a generator is a lesson the other copy has not learned. That file
# carries the argument (alphabet, entropy floor, and why entropy is measured over
# the whole matched string).
PLANTED="$(python3 scripts/redteam_plant.py)"
KEY_ID="$(echo "$PLANTED" | sed -n 1p)"
KEY_SECRET="$(echo "$PLANTED" | sed -n 2p)"
ENTROPY="$(echo "$PLANTED" | sed -n 3p)"
echo "[sec-redteam] planted an AWS-shaped pair, id ${KEY_ID:0:8}… (generated this run)"
echo "[sec-redteam]   shannon entropy id/secret: $ENTROPY — drawn above the rules' floors"

# ---------------------------------------------------------------------------
echo
echo "[sec-redteam] arm A — untracked, unignored file in the working tree"
{
  printf 'aws_access_key_id = %s\n' "$KEY_ID"
  printf 'aws_secret_access_key = %s\n' "$KEY_SECRET"
} > "$PLANT_FILE"

if git check-ignore -q "$PLANT_FILE"; then
  echo "[sec-redteam] FAIL: $PLANT_FILE is gitignored — arm A would test nothing." >&2
  exit 2
fi

set +e
OUT_A="$(uv run python scripts/security_scan.py --stage tree-secrets --no-write 2>&1)"
RC_A=$?
set -e
echo "$OUT_A" | grep -E 'BLOCKING|secrets in git' || true
check "arm A exits non-zero (a blocking finding must be a refusal a caller can hear)" \
  "$([[ $RC_A -ne 0 ]] && echo 1 || echo 0)"
check "arm A names $PLANT_FILE as BLOCKING" \
  "$(echo "$OUT_A" | grep -q "BLOCKING.*$PLANT_FILE" && echo 1 || echo 0)"
check "arm A gives the reason 'untracked AND NOT ignored'" \
  "$(echo "$OUT_A" | grep -q 'untracked AND NOT ignored' && echo 1 || echo 0)"
check "arm A does NOT print the planted secret" \
  "$(echo "$OUT_A" | grep -q "$KEY_SECRET" && echo 0 || echo 1)"

rm -f "$PLANT_FILE"

# ---------------------------------------------------------------------------
echo
echo "[sec-redteam] arm B — a real commit on a scratch branch, reachable only from it"
git checkout -q -b "$SCRATCH_BRANCH"
{
  printf 'aws_access_key_id = %s\n' "$KEY_ID"
  printf 'aws_secret_access_key = %s\n' "$KEY_SECRET"
} > "$PLANT_FILE"
git add "$PLANT_FILE"
# --no-verify, and it is NOT a workaround: from M9-S13 this clone may carry a
# pre-commit hook whose entire job is to refuse a staged credential, and this arm
# stages one on purpose. Without the flag the drill dies at `git commit` under
# `set -e` — which is what happened the first time the hook existed (F-080). The
# hook being right is the reason the flag is here; that the AUDIT still catches
# what the bypass let through is the thing this arm goes on to prove.
echo "[sec-redteam]   (committing with --no-verify: the M9-S13 hook correctly refuses this)"
git commit -q --no-verify \
  -m "redteam(m9-s9): planted credential — DRILL ONLY, destroyed by the same script"
PLANTED_COMMIT="$(git rev-parse --short HEAD)"
# Leave HEAD on the starting branch: the point is that --all reaches a ref that
# HEAD's own ancestry does not. A scan run from the branch itself would pass
# under a --log-opts nobody checked.
git checkout -q "$START_BRANCH"
check "the planted commit $PLANTED_COMMIT is NOT reachable from $START_BRANCH" \
  "$(git merge-base --is-ancestor "$PLANTED_COMMIT" "$START_BRANCH" 2>/dev/null && echo 0 || echo 1)"

set +e
OUT_B="$(uv run python scripts/security_scan.py --stage history-secrets --no-write 2>&1)"
RC_B=$?
set -e
echo "$OUT_B" | grep -E 'BLOCKING|secrets in git' || true
check "arm B exits non-zero" "$([[ $RC_B -ne 0 ]] && echo 1 || echo 0)"
check "arm B names $PLANT_FILE as BLOCKING" \
  "$(echo "$OUT_B" | grep -q "BLOCKING.*$PLANT_FILE" && echo 1 || echo 0)"
check "arm B names the planted commit $PLANTED_COMMIT" \
  "$(echo "$OUT_B" | grep -q "$PLANTED_COMMIT" && echo 1 || echo 0)"
check "arm B still acknowledges the gameday value (one plant, one argument, no collateral)" \
  "$(echo "$OUT_B" | grep -q 'wrong-credential-gameday' && echo 1 || echo 0)"
check "arm B does NOT print the planted secret" \
  "$(echo "$OUT_B" | grep -q "$KEY_SECRET" && echo 0 || echo 1)"

# ---------------------------------------------------------------------------
echo
echo "[sec-redteam] destroying the plant and re-asking"
rm -f "$PLANT_FILE"
git branch -D "$SCRATCH_BRANCH" >/dev/null
git reflog expire --expire-unreachable=now --all
git gc --prune=now --quiet

check "the planted object is GONE from this clone (not merely unreferenced)" \
  "$(git cat-file -e "$PLANTED_COMMIT^{commit}" 2>/dev/null && echo 0 || echo 1)"

set +e
OUT_C="$(uv run python scripts/security_scan.py --stage tree-secrets --stage history-secrets --no-write 2>&1)"
RC_C=$?
set -e
check "the untampered scan is GREEN again (exit 0)" "$([[ $RC_C -eq 0 ]] && echo 1 || echo 0)"
check "and it reports 0 blocking findings" \
  "$(echo "$OUT_C" | grep -q 'secrets in git (tracked files + full history): 0' && echo 1 || echo 0)"
check "the tracked record was never rewritten (both runs used --no-write)" \
  "$([[ -z "$RECORD_BEFORE" || "$RECORD_BEFORE" == "$(sha256sum "$RECORD" | awk '{print $1}')" ]] && echo 1 || echo 0)"
check "git status is clean" "$([[ -z "$(git status --porcelain)" ]] && echo 1 || echo 0)"
check "HEAD is back on $START_BRANCH" \
  "$([[ "$(git rev-parse --abbrev-ref HEAD)" == "$START_BRANCH" ]] && echo 1 || echo 0)"

echo
if [[ $FAILURES -eq 0 ]]; then
  echo "[sec-redteam] PASSED — $CHECKS checks, 0 failures. The scan named a planted"
  echo "[sec-redteam] credential in the working tree"
  echo "[sec-redteam] and in a commit no branch pointed at, redacted both, and came back"
  echo "[sec-redteam] clean once the plant was destroyed."
  exit 0
fi
echo "[sec-redteam] FAILED — $FAILURES of $CHECKS check(s)" >&2
exit 1
