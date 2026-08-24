#!/usr/bin/env bash
# watchdog.sh — the organ the chain was missing. Run by cron every 10 minutes.
#
# WHY (2026-08-17, gotcha #45): chain liveness was 100% "each session schedules
# the next". One session ended its turn mid-story without reaching its exit
# ritual, and the program was simply over — no successor, no error, no alarm,
# 38 minutes of silence until a human happened to look at a status pane.
#
# THE ONE RULE THAT MATTERS: this thing may restart an ACCIDENT. It must never
# restart a DECISION. A chain that parked on a fork (exit ritual d) is working
# correctly, and auto-restarting it would walk straight through the fork policy
# ADR-010 exists to enforce. The tell is AWAITING_PO.md: a session that parks
# deliberately writes to it, a session that dies does not.
#
# That rule was stated here from the first day and broken anyway on 2026-08-24
# (F-066), because it was implemented as an edge detector on a hash while the
# thing it must express is a STATE. A park now LATCHES
# (automation/logs/watchdog_parked) and is cleared by exactly one thing: the
# `automation/next_session.sh` command every AWAITING_PO entry names as the
# resume. Two facts make that safe, and neither is optional:
#   - red() re-stamps the AWAITING_PO baseline after appending, so the watchdog
#     cannot latch on its OWN alarm and wedge the chain shut;
#   - the heal path cannot clear the latch (WATCHDOG_HEAL=1), so the one actor
#     with a motive to un-park a fork does not hold the eraser.
#
# Escalation, in order:
#   GREEN  something is alive (session / pending successor / detached run) -> silent
#   HEAL   nothing alive, nothing was decided, budget remains -> restart, log only
#   RED    needs a human -> Windows toast + AWAITING_PO.md entry, no restart
#
# RED is rationed on purpose. Same condition toasts at most once an hour, and
# only conditions a human must personally clear ever reach RED at all.
set -uo pipefail
cd "$(dirname "$0")/.."   # repo root

LOGS="automation/logs"
mkdir -p "${LOGS}"
WLOG="${LOGS}/watchdog.log"
TOAST_STATE="${LOGS}/watchdog_toast_state"
HEAL_STATE="${LOGS}/watchdog_heal_state"
PO_HASH="${LOGS}/watchdog_awaiting_po.sha"
PARK_STATE="${LOGS}/watchdog_parked"   # a park persists until a human resumes

PENDING_GRACE="${WATCHDOG_PENDING_GRACE:-900}"    # a queued session has 15 min to appear
HEAL_WINDOW="${WATCHDOG_HEAL_WINDOW:-900}"        # two heals inside this = not working
MAX_CONSECUTIVE_HEALS="${WATCHDOG_MAX_HEALS:-3}"  # then stop and ask for a human
TOAST_REPEAT="${WATCHDOG_TOAST_REPEAT:-3600}"     # re-nag the same RED at most hourly
NOW="$(date +%s)"

log() { printf '%s  %s\n' "$(date -u '+%F %T')" "$1" >> "${WLOG}"; }

# --- RED: toast + the PO's inbox, rationed by key ------------------------------
red() {
  local key="$1" title="$2" message="$3"
  local last_key="" last_at=0
  if [ -f "${TOAST_STATE}" ]; then
    last_key="$(awk '{print $1}' "${TOAST_STATE}" 2>/dev/null || echo '')"
    last_at="$(awk '{print $2}' "${TOAST_STATE}" 2>/dev/null || echo 0)"
  fi
  [ -n "${last_at}" ] || last_at=0

  if [ "${key}" = "${last_key}" ] && [ $((NOW - last_at)) -lt "${TOAST_REPEAT}" ]; then
    log "RED ${key} — still red, toast suppressed (last $((NOW - last_at))s ago)"
    return 0
  fi

  log "RED ${key} — ${message}"
  echo "${key} ${NOW}" > "${TOAST_STATE}"

  if automation/toast.sh "${title}" "${message}" >> "${WLOG}" 2>&1; then
    log "RED ${key} — toast delivered"
  else
    log "RED ${key} — TOAST FAILED (see above); AWAITING_PO.md is the only channel left"
  fi

  {
    echo ""
    echo "## $(date -u '+%F %H:%M') UTC — watchdog: ${title}"
    echo "${message}"
    echo ""
    echo "Watchdog log: automation/logs/watchdog.log"
  } >> AWAITING_PO.md

  # The alarm channel IS the park sensor, so the watchdog must not read its own
  # handwriting as a session's fork. Re-stamp the baseline with the file as it
  # now stands (2026-08-24, F-066): before this, every red() left a change that
  # the NEXT pass reported as "a session parked on a fork". That false park was
  # not harmless bookkeeping — it is the reason a real park had to be allowed to
  # DECAY (a latch would otherwise have wedged the chain shut on any FAILED
  # run), and the decay is what let the program-close park be healed 20 minutes
  # after it was correctly detected. Killing the false park is what makes the
  # latch in step 5 safe.
  sha256sum AWAITING_PO.md 2>/dev/null | awk '{print $1}' > "${PO_HASH}" || true
}

# Any green observation means the last heal worked; forget the failure streak.
clear_heal_streak() { [ -f "${HEAL_STATE}" ] && rm -f "${HEAL_STATE}"; return 0; }

green() { log "GREEN — $1"; clear_heal_streak; exit 0; }

# --- 1. Paused by hand is not broken -------------------------------------------
if [ -f automation/STOP ]; then
  log "STOP present — chain paused deliberately; standing down."
  exit 0
fi

# --- 2. Is a session running right now? ----------------------------------------
if [ -f "${LOGS}/running_session" ]; then
  RS_PID="$(awk '{print $1}' "${LOGS}/running_session" 2>/dev/null || echo '')"
  if [ -n "${RS_PID}" ] && kill -0 "${RS_PID}" 2>/dev/null; then
    green "session alive (pid ${RS_PID}, $(awk '{print $2}' "${LOGS}/running_session"))"
  fi
  log "stale running_session marker (pid ${RS_PID:-?} is gone) — clearing"
  rm -f "${LOGS}/running_session"
fi

# --- 3. Is a successor queued and still plausible? -----------------------------
if [ -f "${LOGS}/pending_successor" ]; then
  P_AGE=$((NOW - $(stat -c %Y "${LOGS}/pending_successor")))
  if [ "${P_AGE}" -lt "${PENDING_GRACE}" ]; then
    green "successor queued $(cat "${LOGS}/pending_successor") ${P_AGE}s ago — inside grace"
  fi
  log "pending_successor is ${P_AGE}s old (grace ${PENDING_GRACE}s) — it never launched; clearing"
  rm -f "${LOGS}/pending_successor"
fi

# --- 4. Is a detached job still working? It owns the handoff. ------------------
if compgen -G "automation/runs/*.status" > /dev/null; then
  for st in automation/runs/*.status; do
    NAME="$(basename "${st}" .status)"
    STATE="$(awk '{print $1}' "${st}" 2>/dev/null || echo '')"
    case "${STATE}" in
      RUNNING)
        R_PID="$(awk '{print $2}' "${st}")"
        if kill -0 "${R_PID}" 2>/dev/null; then
          green "detached run '${NAME}' in flight (pid ${R_PID}) — it schedules the successor"
        fi
        log "detached run '${NAME}' says RUNNING but pid ${R_PID} is gone — it was killed"
        echo "KILLED ? $(date -u +%FT%TZ)" > "${st}"
        red "run-killed-${NAME}" \
            "Chain: detached run was killed" \
            "'${NAME}' died without finishing, so it never scheduled a successor. Last output: automation/runs/${NAME}.log — restart it with automation/run_detached.sh once you know why."
        exit 0
        ;;
      FAILED)
        RC="$(awk '{print $2}' "${st}")"
        red "run-failed-${NAME}" \
            "Chain: detached run FAILED" \
            "'${NAME}' exited ${RC} and never delivered its result. Alarmed once; the chain heals on a later pass. Read the RECORD, not the code — a refusal writes a record, a crash writes nothing (gotcha #97). Log: automation/runs/${NAME}.log"
        # Ack it, exactly as the KILLED branch above rewrites its corpse: ONE
        # failure alarms ONCE and then stops blocking the heal path. Before
        # this (2026-08-24) a FAILED status was a permanent landmine — a
        # 4-day-old 'FAILED 2' from M7-S4 (a run whose record HAD arrived;
        # make collapses every CLI code to 2, gotcha #97) made every pass exit
        # here, so an executor killed by a transient API error could never be
        # healed. The original line is kept inside the ack for the record.
        OLD_LINE="$(cat "${st}" 2>/dev/null)"
        echo "FAILED-ACKED ${RC} $(date -u +%FT%TZ) (was: ${OLD_LINE})" > "${st}"
        exit 0
        ;;
    esac
  done
fi

# --- 5. Did the last session PARK on a fork? Then it is working as designed. ---
# A park is a STATE, not an event, and that distinction cost a real park. Until
# 2026-08-24 this was an edge detector on a hash: it fired on the pass where
# AWAITING_PO.md changed and forgot by the next one, so the program-close park
# was correctly detected at 06:40, alarmed, and then HEALED at 07:00 — the one
# thing the header says this script must never do. "No change since the last
# pass" is not "no unanswered fork".
#
# So the park LATCHES, and only the resume command every AWAITING_PO entry
# names can clear it (next_session.sh, run by a human who has answered). The
# watchdog itself never clears it: healing a park is the bug, so the heal path
# must not hold the eraser.
PARK_MSG="The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor"

if [ -f "${PARK_STATE}" ]; then
  # Rationed, so a long park nags hourly and appends to the inbox once, rather
  # than growing a note every ten minutes forever.
  red "parked-on-fork" "Chain parked — your decision needed" "${PARK_MSG}"
  log "parked since $(awk '{print $2}' "${PARK_STATE}" 2>/dev/null) — still parked; only 'automation/next_session.sh <role>' clears it"
  exit 0
fi

PO_NOW="$(sha256sum AWAITING_PO.md 2>/dev/null | awk '{print $1}' || echo 'none')"
PO_WAS="$(cat "${PO_HASH}" 2>/dev/null || echo '')"
echo "${PO_NOW}" > "${PO_HASH}"
if [ -n "${PO_WAS}" ] && [ "${PO_NOW}" != "${PO_WAS}" ]; then
  echo "parked $(date -u +%FT%TZ) ${PO_NOW}" > "${PARK_STATE}"
  red "parked-on-fork" "Chain parked — your decision needed" "${PARK_MSG}"
  exit 0
fi

# --- 6. Budget guards — a cap is a decision, not an accident -------------------
TODAY="$(date +%F)"
COUNT="$(cat "${LOGS}/count_${TODAY}" 2>/dev/null || echo 0)"
MAX_PER_DAY="${CHAIN_MAX_PER_DAY:-40}"
if [ "${COUNT}" -ge "${MAX_PER_DAY}" ]; then
  red "daily-cap" \
      "Chain: daily session cap reached" \
      "${COUNT}/${MAX_PER_DAY} sessions used today; the chain halted itself so it cannot burn quota unattended. Raise CHAIN_MAX_PER_DAY or delete automation/logs/count_${TODAY}, then resume."
  exit 0
fi

# --- 7. Restarting something that keeps dying is not healing -------------------
STREAK=0; LAST_HEAL=0
if [ -f "${HEAL_STATE}" ]; then
  STREAK="$(awk '{print $1}' "${HEAL_STATE}" 2>/dev/null || echo 0)"
  LAST_HEAL="$(awk '{print $2}' "${HEAL_STATE}" 2>/dev/null || echo 0)"
fi
[ -n "${STREAK}" ] || STREAK=0
[ -n "${LAST_HEAL}" ] || LAST_HEAL=0

if [ $((NOW - LAST_HEAL)) -lt "${HEAL_WINDOW}" ]; then
  STREAK=$((STREAK + 1))
else
  STREAK=1
fi

if [ "${STREAK}" -gt "${MAX_CONSECUTIVE_HEALS}" ]; then
  red "heal-loop" \
      "Chain keeps dying — restarting is not working" \
      "The watchdog restarted the chain ${MAX_CONSECUTIVE_HEALS} times and each session died within $((HEAL_WINDOW / 60)) minutes. Something is wrong that a restart cannot fix — check the newest automation/logs/*_executor.log. Not restarting again until you clear automation/logs/watchdog_heal_state."
  exit 0
fi

# --- 8. Accidental death, budget available: heal it ---------------------------
log "chain is DEAD (no session, no successor, no detached run, no new fork) — healing, attempt ${STREAK}"
echo "${STREAK} ${NOW}" > "${HEAL_STATE}"

# WATCHDOG_HEAL=1 stops the scheduler clearing a park latch on the watchdog's
# behalf. Step 5 already exits before this line whenever a latch exists, so this
# is the second of two independent guards — the failure it prevents (a heal that
# silently un-parks a fork) is exactly the one that leaves no trace.
if OUT="$(WATCHDOG_HEAL=1 automation/next_session.sh executor 15 2>&1)"; then
  log "HEAL — ${OUT}"
else
  log "HEAL FAILED — ${OUT}"
  red "heal-failed" \
      "Chain: watchdog could not restart it" \
      "automation/next_session.sh refused or errored: ${OUT}"
fi
exit 0
