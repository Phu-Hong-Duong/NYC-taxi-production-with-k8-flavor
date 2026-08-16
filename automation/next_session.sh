#!/usr/bin/env bash
# next_session.sh — schedule the NEXT autonomous session (local, WSL2).
# Usage: automation/next_session.sh <executor|architect|rev> [delay_seconds=120]
# Halts silently if automation/STOP exists. Daily cap guards runaway chains.
# Proven by running at Session 1 (hello-chain) before any real work trusts it.
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

ROLE="${1:?role required: executor|architect|rev}"
DELAY="${2:-120}"

if [ -f automation/STOP ]; then echo "[chain] STOP file present — not scheduling."; exit 0; fi

TODAY="$(date +%F)"
COUNT_FILE="automation/logs/count_${TODAY}"
mkdir -p automation/logs
COUNT="$(cat "${COUNT_FILE}" 2>/dev/null || echo 0)"
MAX_PER_DAY="${CHAIN_MAX_PER_DAY:-40}"
if [ "${COUNT}" -ge "${MAX_PER_DAY}" ]; then
  {
    echo ""
    echo "## $(date '+%F %H:%M') — chain cap"
    echo "Daily session cap (${MAX_PER_DAY}) reached; chain halted itself."
    echo "Resume: delete automation/logs/count_${TODAY} or raise CHAIN_MAX_PER_DAY, then run: automation/next_session.sh executor"
  } >> AWAITING_PO.md
  echo "[chain] daily cap reached — halted; noted in AWAITING_PO.md"; exit 0
fi

case "${ROLE}" in
  executor)  MODEL="opus";  PROMPT="automation/executor_prompt.md"  ;;
  architect) MODEL="fable"; PROMPT="automation/architect_prompt.md" ;;
  rev)       MODEL="opus";  PROMPT="automation/rev_prompt.md"       ;;
  *) echo "[chain] unknown role: ${ROLE}"; exit 1 ;;
esac
[ -f "${PROMPT}" ] || { echo "[chain] missing prompt file ${PROMPT}"; exit 1; }

LOG="automation/logs/$(date +%Y%m%d_%H%M%S)_${ROLE}.log"
echo $((COUNT + 1)) > "${COUNT_FILE}"

# PERMISSIONS: set CLAUDE_PERMISSION_FLAGS once in your shell profile (see automation/README.md).
# Default is the safer acceptEdits mode; unattended clusters usually need the allowlist
# in .claude/settings.local.json on top of it.
# The resolved FLAGS are ALSO env-forwarded into the spawned session, so any successor
# it schedules inherits the same mode — .bashrc exports don't survive non-interactive
# shells (gotcha #26).
FLAGS="${CLAUDE_PERMISSION_FLAGS:---permission-mode acceptEdits}"

nohup bash -c "sleep ${DELAY}; \
  [ -f automation/STOP ] && exit 0; \
  CLAUDE_PERMISSION_FLAGS='${FLAGS}' claude --model ${MODEL} ${FLAGS} -p \"\$(cat ${PROMPT})\" >> '${LOG}' 2>&1" \
  >/dev/null 2>&1 &

echo "[chain] scheduled ${ROLE} (+${DELAY}s, model=${MODEL}, flags=${FLAGS}, session #$((COUNT+1)) today) → ${LOG}"
