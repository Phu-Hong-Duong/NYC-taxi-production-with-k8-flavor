#!/usr/bin/env bash
# next_session.sh — schedule the NEXT autonomous session (local, WSL2).
# Usage: automation/next_session.sh <executor|architect|rev> [delay_seconds=120]
# Halts silently if automation/STOP exists. Daily cap guards runaway chains.
# Proven by running at Session 1 (hello-chain) before any real work trusts it.
#
# 2026-08-17 (gotcha #45): this script now leaves a TRACE of chain liveness.
# Before, "is the chain alive?" was unanswerable from outside — a session that
# ended without calling this script was indistinguishable from one still
# working, and the program stayed dead in silence for 38 minutes. Two markers
# under automation/logs/ close that gap and are what automation/watchdog.sh
# reads:
#   pending_successor  a session is QUEUED but has not started yet
#   running_session    a session is running right now, with its pid
# They also make the double-schedule impossible: a session that detaches a job
# with `run_detached.sh --then-schedule` must not also schedule by hand, and
# now it simply cannot.
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

# --- one successor, never two -------------------------------------------------
# A stale marker (a session that died between the write below and the launch)
# must not wedge the chain shut, so anything past the grace window is ignored.
PENDING="automation/logs/pending_successor"
PENDING_GRACE="${CHAIN_PENDING_GRACE:-900}"
if [ -f "${PENDING}" ]; then
  P_AGE=$(( $(date +%s) - $(stat -c %Y "${PENDING}") ))
  if [ "${P_AGE}" -lt "${PENDING_GRACE}" ]; then
    echo "[chain] a successor is ALREADY queued ($(cat "${PENDING}"), ${P_AGE}s ago) — refusing to schedule a second."
    exit 0
  fi
  echo "[chain] ignoring stale pending_successor (${P_AGE}s old, grace ${PENDING_GRACE}s)."
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
echo "${ROLE} queued $(date -u +%FT%TZ) for +${DELAY}s" > "${PENDING}"

# PERMISSIONS: set CLAUDE_PERMISSION_FLAGS once in your shell profile (see automation/README.md).
# Default is the safer acceptEdits mode; unattended clusters usually need the allowlist
# in .claude/settings.local.json on top of it.
# The resolved FLAGS are ALSO env-forwarded into the spawned session, so any successor
# it schedules inherits the same mode — .bashrc exports don't survive non-interactive
# shells (gotcha #26).
FLAGS="${CLAUDE_PERMISSION_FLAGS:---permission-mode acceptEdits}"

# ONE SESSION IN THE TREE AT A TIME. Two executors sharing a working tree edit
# each other's files and commit over each other. This is not hypothetical: on
# 2026-08-17 a detached job was due to schedule a successor while a
# hand-started session was still mid-story. The queued session therefore waits
# for the tree to go idle rather than launching on top of whoever holds it.
IDLE_WAIT="${CHAIN_IDLE_WAIT:-1800}"
IDLE_POLL="${CHAIN_IDLE_POLL:-30}"   # knob so the guard can be tested in seconds

# setsid: own session and process group, so the queued session cannot be taken
# down by whatever exits upstream of it (gotcha #45's other half).
setsid nohup bash -c "sleep ${DELAY}; \
  if [ -f automation/STOP ]; then rm -f '${PENDING}'; exit 0; fi; \
  waited=0; \
  while [ -f automation/logs/running_session ] \
     && kill -0 \$(awk '{print \$1}' automation/logs/running_session 2>/dev/null) 2>/dev/null \
     && [ \$waited -lt ${IDLE_WAIT} ]; do sleep ${IDLE_POLL}; waited=\$((waited + ${IDLE_POLL})); done; \
  if [ -f automation/STOP ]; then rm -f '${PENDING}'; exit 0; fi; \
  rm -f '${PENDING}'; \
  echo \"\$\$ ${ROLE} \$(date -u +%FT%TZ)\" > automation/logs/running_session; \
  CLAUDE_PERMISSION_FLAGS='${FLAGS}' claude --model ${MODEL} ${FLAGS} -p \"\$(cat ${PROMPT})\" >> '${LOG}' 2>&1; \
  rm -f automation/logs/running_session" \
  >/dev/null 2>&1 &

echo "[chain] scheduled ${ROLE} (+${DELAY}s, model=${MODEL}, flags=${FLAGS}, session #$((COUNT+1)) today) → ${LOG}"
