#!/usr/bin/env bash
# run_detached.sh — run a long job so it OUTLIVES the session that started it.
#
# WHY THIS EXISTS (gotcha #45, paid for on 2026-08-17):
# A Claude Code background task is a CHILD of the session process. When the
# session's turn ends, that process exits and every child dies mid-flight.
# On 2026-08-17 an executor launched the 4-arm full-scale confirmation as a
# background task, then ended its turn with "I'll pick this up when the
# confirmation run reports" — and killed the run by ending. It had completed
# one arm. Nothing reported, nothing was scheduled, the chain died for 38
# minutes until a human noticed.
#
# setsid puts the job in its OWN session and process group, so no exit
# upstream can take it along. The status file is how a LATER session reads
# the result: the job outlives every session, so no session ever waits.
#
# Usage:
#   automation/run_detached.sh <name> [--then-schedule <role>] -- <command...>
#
#   <name>            slug for the log/status pair under automation/runs/
#   --then-schedule   on completion, call next_session.sh <role>. THE JOB
#                     schedules the successor, not the session that launched
#                     it — that is the whole point. If you pass this, you must
#                     NOT call next_session.sh yourself (next_session.sh will
#                     refuse the double anyway).
#
# Example:
#   automation/run_detached.sh m3s3-confirmation --then-schedule executor -- \
#     make ablation ABLATION_ARGS="--full-scale --sets v1,v1_g1,v1_g2,v2"
#
# Read it back from any later session:
#   cat automation/runs/m3s3-confirmation.status   # RUNNING|DONE|FAILED
#   tail -40 automation/runs/m3s3-confirmation.log
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

NAME="${1:?name required (slug for the log/status pair)}"; shift
SCHEDULE_ROLE=""
if [ "${1:-}" = "--then-schedule" ]; then
  SCHEDULE_ROLE="${2:?role required after --then-schedule}"; shift 2
fi
[ "${1:-}" = "--" ] || { echo "[detached] expected -- before the command" >&2; exit 1; }
shift
[ "$#" -gt 0 ] || { echo "[detached] no command given" >&2; exit 1; }

case "${SCHEDULE_ROLE}" in
  ""|executor|architect|rev) ;;
  *) echo "[detached] unknown role: ${SCHEDULE_ROLE}" >&2; exit 1 ;;
esac

mkdir -p automation/runs
LOG="automation/runs/${NAME}.log"
STATUS="automation/runs/${NAME}.status"

if [ -f "${STATUS}" ] && grep -q '^RUNNING' "${STATUS}" 2>/dev/null; then
  RUNNING_PID="$(awk '{print $2}' "${STATUS}")"
  if kill -0 "${RUNNING_PID}" 2>/dev/null; then
    echo "[detached] ${NAME} is ALREADY RUNNING (pid ${RUNNING_PID}) — refusing to start a second."
    echo "[detached] status: $(cat "${STATUS}")"
    exit 0
  fi
  echo "[detached] stale RUNNING status for ${NAME} (pid ${RUNNING_PID} is gone) — overwriting."
fi

: > "${LOG}"
CMD_STR="$*"

# setsid + nohup: own session, own process group, immune to the caller's exit.
setsid nohup bash -c '
  set -o pipefail
  cd "$1"; shift
  status="$1"; shift
  log="$1"; shift
  role="$1"; shift
  echo "RUNNING $$ $(date -u +%FT%TZ)" > "${status}"
  {
    echo "[detached] pid $$ started $(date -u +%FT%TZ)"
    echo "[detached] command: $*"
    echo "----------------------------------------------------------------"
  } >> "${log}"
  set +e
  "$@" >> "${log}" 2>&1
  rc=$?
  set -e
  if [ "${rc}" -eq 0 ]; then
    echo "DONE 0 $(date -u +%FT%TZ)" > "${status}"
  else
    echo "FAILED ${rc} $(date -u +%FT%TZ)" > "${status}"
  fi
  {
    echo "----------------------------------------------------------------"
    echo "[detached] exit ${rc} at $(date -u +%FT%TZ)"
  } >> "${log}"
  # The JOB schedules the successor. A session that ends is a session that is
  # gone; a detached job is still here to hand the chain forward.
  if [ -n "${role}" ]; then
    if [ -f automation/STOP ]; then
      echo "[detached] STOP present — not scheduling ${role}." >> "${log}"
    else
      automation/next_session.sh "${role}" 30 >> "${log}" 2>&1 \
        || echo "[detached] next_session.sh ${role} failed (see above)" >> "${log}"
    fi
  fi
' _ "$PWD" "${STATUS}" "${LOG}" "${SCHEDULE_ROLE}" "$@" >/dev/null 2>&1 &

disown 2>/dev/null || true
sleep 1

echo "[detached] ${NAME} launched — survives session exit, WSL shutdown excepted."
echo "[detached] command : ${CMD_STR}"
echo "[detached] log     : ${LOG}"
echo "[detached] status  : ${STATUS}  ($(cat "${STATUS}" 2>/dev/null || echo 'starting'))"
if [ -n "${SCHEDULE_ROLE}" ]; then
  echo "[detached] on completion it will schedule: ${SCHEDULE_ROLE}"
  echo "[detached] DO NOT call next_session.sh yourself this session."
fi
