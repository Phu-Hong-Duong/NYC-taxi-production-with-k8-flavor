#!/usr/bin/env bash
# M9-S13 — watch the pre-commit hook REFUSE a commit, and watch it let one through.
#
# THREE ARMS, AND THE FIRST ONE IS THE LOAD-BEARING ONE.
#
#   arm A (negative control)  an ordinary staged file COMMITS, with the hook
#         installed and having demonstrably RUN. Without this, "the plant was
#         blocked" is equally consistent with a hook that refuses everything —
#         which is worse than no hook, because its owner uninstalls it by Friday.
#         And the hook must be shown to have run: gotcha #81's shape at the
#         commit boundary — a hook that is installed, executable, and doing
#         nothing looks exactly like a hook that passed.
#
#   arm B (the drill)         a generated credential is STAGED and `git commit`
#         is REFUSED: non-zero, naming the file, printing no secret, and — the
#         check that says nothing slipped through — HEAD unmoved.
#
#   arm C (the honest limit)  `git commit --no-verify` with the same plant staged
#         SUCCEEDS. The PO was told this hook is bypassable; measuring it is the
#         difference between a documented limit and a claimed one. The commit is
#         then destroyed — branch deleted, reflog expired, objects pruned — and
#         `git cat-file -e` is ASKED, because "I deleted the branch" and "the
#         object is gone" are different claims and only the second is the one
#         publishing cares about.
#
# It MUTATES NO HOOK. The drill refuses to run unless the hook is already
# installed and current, so it cannot pass by installing a hook of its own
# devising, and it cannot leave your clone in a state you did not choose.
# Everything happens on a scratch branch; nothing is ever pushed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SCRATCH_BRANCH="redteam/m9-s13-hook"
PLANT_FILE="redteam_hook_planted_credential.txt"
CONTROL_FILE="redteam_hook_control.txt"
RECORD="automation/runs/m9-hook/redteam.json"
WRITE=1
[[ "${1:-}" == "--no-write" ]] && WRITE=0
FAILURES=0
CHECKS=0
START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
START_SHA="$(git rev-parse HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[hook-redteam] FAIL: the working tree is dirty. This drill commits and then" >&2
  echo "[hook-redteam]       destroys history; it refuses to run over uncommitted work." >&2
  exit 2
fi

if ! bash scripts/install_hooks.sh --check >/dev/null 2>&1; then
  echo "[hook-redteam] FAIL: the pre-commit hook is not installed or not current in" >&2
  echo "[hook-redteam]       this clone. Run 'make install-hooks' first — this drill" >&2
  echo "[hook-redteam]       deliberately does not install it, so that it cannot pass" >&2
  echo "[hook-redteam]       against a hook of its own making." >&2
  bash scripts/install_hooks.sh --check >&2 || true
  exit 2
fi

cleanup() {
  local rc=$?
  echo
  echo "[hook-redteam] restoring"
  rm -f "$PLANT_FILE" "$CONTROL_FILE"
  # Forceful restoration ONLY when the drill is not already home. On the happy
  # path this is a no-op by the time the trap runs, and it has to be: a blanket
  # `checkout -f` / `reset --hard` here would revert the record the drill writes
  # two lines earlier — a cleanup that destroys the run's own evidence (F-063 and
  # gotcha #48, one family along).
  if [[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" != "$START_BRANCH" ||
        "$(git rev-parse HEAD 2>/dev/null)" != "$START_SHA" ]]; then
    git checkout -q -f "$START_BRANCH" 2>/dev/null || true
    git reset -q --hard "$START_SHA" 2>/dev/null || true
  fi
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

PLANTED="$(python3 scripts/redteam_plant.py)"
KEY_ID="$(echo "$PLANTED" | sed -n 1p)"
KEY_SECRET="$(echo "$PLANTED" | sed -n 2p)"
ENTROPY="$(echo "$PLANTED" | sed -n 3p)"
echo "[hook-redteam] planted an AWS-shaped pair, id ${KEY_ID:0:8}… (generated this run)"
echo "[hook-redteam]   shannon entropy id/secret: $ENTROPY — drawn above the rules' floors"

git checkout -q -b "$SCRATCH_BRANCH"

# ---------------------------------------------------------------------------
echo
echo "[hook-redteam] arm A — the negative control: an ordinary commit must PASS"
printf 'a line of ordinary text with nothing secret in it\n' > "$CONTROL_FILE"
git add "$CONTROL_FILE"
set +e
OUT_A="$(git commit -m "redteam(m9-s13): ordinary commit — DRILL ONLY" 2>&1)"
RC_A=$?
set -e
check "arm A: the commit SUCCEEDS with the hook installed" \
  "$([[ $RC_A -eq 0 ]] && echo 1 || echo 0)"
check "arm A: the hook demonstrably RAN (an installed hook doing nothing looks identical)" \
  "$(echo "$OUT_A" | grep -q 'sec-scan. staged-secrets' && echo 1 || echo 0)"
check "arm A: it reported looking at the INDEX, not at the tree or at history" \
  "$(echo "$OUT_A" | grep -q 'secrets staged for commit: 0' && echo 1 || echo 0)"
CONTROL_SHA="$(git rev-parse HEAD)"
check "arm A: HEAD moved (the control really committed)" \
  "$([[ "$CONTROL_SHA" != "$START_SHA" ]] && echo 1 || echo 0)"

# ---------------------------------------------------------------------------
echo
echo "[hook-redteam] arm B — a staged credential must be REFUSED"
{
  printf 'aws_access_key_id = %s\n' "$KEY_ID"
  printf 'aws_secret_access_key = %s\n' "$KEY_SECRET"
} > "$PLANT_FILE"
git add "$PLANT_FILE"
set +e
OUT_B="$(git commit -m "redteam(m9-s13): planted credential — MUST NOT LAND" 2>&1)"
RC_B=$?
set -e
echo "$OUT_B" | grep -E 'BLOCKING|COMMIT REFUSED|staged for commit' || true
check "arm B: the commit is REFUSED (non-zero from git commit)" \
  "$([[ $RC_B -ne 0 ]] && echo 1 || echo 0)"
check "arm B: the refusal names $PLANT_FILE as BLOCKING" \
  "$(echo "$OUT_B" | grep -q "BLOCKING.*$PLANT_FILE" && echo 1 || echo 0)"
check "arm B: it gives the reason 'staged for commit'" \
  "$(echo "$OUT_B" | grep -q 'staged for commit — one .git commit. from history' && echo 1 || echo 0)"
check "arm B: the message says COMMIT REFUSED, not the audit's park-at-AWAITING_PO text" \
  "$(echo "$OUT_B" | grep -q 'COMMIT REFUSED' && echo 1 || echo 0)"
check "arm B: it does NOT print the planted secret" \
  "$(echo "$OUT_B" | grep -q "$KEY_SECRET" && echo 0 || echo 1)"
check "arm B: HEAD did NOT move — nothing was committed" \
  "$([[ "$(git rev-parse HEAD)" == "$CONTROL_SHA" ]] && echo 1 || echo 0)"
check "arm B: the plant is still STAGED, so the author can fix it rather than re-find it" \
  "$(git diff --cached --name-only | grep -qx "$PLANT_FILE" && echo 1 || echo 0)"

# ---------------------------------------------------------------------------
echo
echo "[hook-redteam] arm C — the honest limit, MEASURED: --no-verify bypasses it"
set +e
OUT_C="$(git commit --no-verify -m "redteam(m9-s13): bypassed hook — DRILL ONLY, destroyed below" 2>&1)"
RC_C=$?
set -e
check "arm C: --no-verify commits the very thing the hook refused (the limit is real)" \
  "$([[ $RC_C -eq 0 ]] && echo 1 || echo 0)"
check "arm C: and the hook printed nothing, because it never ran" \
  "$(echo "$OUT_C" | grep -q 'sec-scan' && echo 0 || echo 1)"
BYPASSED_COMMIT="$(git rev-parse --short HEAD)"
check "arm C: the bypassed commit $BYPASSED_COMMIT is NOT reachable from $START_BRANCH" \
  "$(git merge-base --is-ancestor "$BYPASSED_COMMIT" "$START_BRANCH" 2>/dev/null && echo 0 || echo 1)"

# The audit of record is the net under the hook: it walks every ref, so it sees
# what --no-verify let through. That is the whole reason the hook is not the
# thing publishing is conditional on.
set +e
OUT_D="$(uv run python scripts/security_scan.py --stage history-secrets --no-write 2>&1)"
RC_D=$?
set -e
check "the AUDIT still catches it (--all reaches a ref HEAD's ancestry does not)" \
  "$([[ $RC_D -ne 0 ]] && echo "$OUT_D" | grep -q "BLOCKING.*$PLANT_FILE" && echo 1 || echo 0)"

# ---------------------------------------------------------------------------
echo
echo "[hook-redteam] destroying the bypassed commit and re-asking"
git checkout -q "$START_BRANCH"
git branch -D "$SCRATCH_BRANCH" >/dev/null
rm -f "$PLANT_FILE" "$CONTROL_FILE"
git reflog expire --expire-unreachable=now --all
git gc --prune=now --quiet

check "the bypassed object is GONE from this clone (not merely unreferenced)" \
  "$(git cat-file -e "$BYPASSED_COMMIT^{commit}" 2>/dev/null && echo 0 || echo 1)"

set +e
OUT_E="$(uv run python scripts/security_scan.py --stage tree-secrets --stage history-secrets --no-write 2>&1)"
RC_E=$?
set -e
check "the untampered audit is GREEN again (exit 0)" "$([[ $RC_E -eq 0 ]] && echo 1 || echo 0)"
check "and it reports 0 blocking findings" \
  "$(echo "$OUT_E" | grep -q 'secrets in git (tracked files + full history): 0' && echo 1 || echo 0)"
check "HEAD is back where it started ($START_BRANCH at ${START_SHA:0:12}…)" \
  "$([[ "$(git rev-parse HEAD)" == "$START_SHA" && "$(git rev-parse --abbrev-ref HEAD)" == "$START_BRANCH" ]] && echo 1 || echo 0)"
check "the working tree is clean apart from the record this drill is about to write" \
  "$([[ -z "$(git status --porcelain -- . ':!automation/runs/m9-hook')" ]] && echo 1 || echo 0)"

echo
if [[ $WRITE -eq 1 ]]; then
  mkdir -p "$(dirname "$RECORD")"
  cat > "$RECORD" <<JSON
{
  "story": "M9-S13",
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "git_head": "$START_SHA",
  "drill": "the pre-commit hook, watched refusing and watched permitting",
  "hook": "scripts/hooks/pre-commit -> .git/hooks/pre-commit (untracked by git, so this record is a statement about the machine it ran on)",
  "arms": {
    "A_negative_control": "an ordinary staged file commits, and the hook is proved to have RUN",
    "B_refusal": "a generated AWS-shaped credential staged; git commit REFUSED, HEAD unmoved, secret never printed",
    "C_documented_limit": "git commit --no-verify commits the same plant — the bypass is measured, not claimed — and the audit of record still catches it"
  },
  "checks": $CHECKS,
  "failures": $FAILURES,
  "verdict": "$([[ $FAILURES -eq 0 ]] && echo PASSED || echo FAILED)",
  "what_this_does_not_prove": "that the hook is installed in any other clone. .git/hooks is untracked; make security-scan remains the audit of record."
}
JSON
  echo "[hook-redteam] wrote $RECORD"
fi

if [[ $FAILURES -eq 0 ]]; then
  echo "[hook-redteam] PASSED — $CHECKS checks, 0 failures. The hook refused a staged"
  echo "[hook-redteam] credential, let an ordinary commit through, and --no-verify walked"
  echo "[hook-redteam] straight past it — which is why the audit, not the hook, is the gate."
  exit 0
fi
echo "[hook-redteam] FAILED — $FAILURES of $CHECKS check(s)" >&2
exit 1
