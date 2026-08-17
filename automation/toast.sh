#!/usr/bin/env bash
# toast.sh — raise the PO's EXISTING Claude Code alarm from inside WSL.
#
# RED ONLY. This is the chain's alarm, not its narrator: it fires when the
# chain needs a HUMAN and cannot heal itself. Everything the watchdog can fix
# by itself is fixed silently into automation/logs/watchdog.log. A notifier
# that cries wolf gets muted, and a muted alarm is worse than none.
#
# IT DELEGATES, DELIBERATELY. ~/.claude/toast.ps1 is the PO's own notifier,
# already wired to Claude Code's Notification hooks. Reusing it is not just
# tidiness — that script is where two real Windows traps are already solved,
# and a fresh notifier walks into both:
#   1. AUMID. Windows silently DROPS toasts under an unregistered
#      AppUserModelID: no banner, no error, no trace. The obvious choice,
#      {1AC14E77-...}\WindowsPowerShell\v1.0\powershell.exe, is exactly one of
#      the dead ones on this machine — a hand-rolled toast returned "OK" here
#      and was never shown. toast.ps1 sends under the Claude Desktop AUMID (a
#      packaged app, permanently registered), so the alarm also lands in the
#      Action Center under the icon the PO already looks for.
#   2. scenario/duration. Staying on screen needs scenario=alarm AND buttons —
#      a scenario toast with no buttons is silently demoted to auto-dismiss.
# It also appends one line per invocation to ~/.claude/toast.log ending in
# held=1 / held=0 — what Windows ACTUALLY kept, not what we sent. This script
# reads that line back and reports it, so "the chain alarm is broken" and "I
# missed the chain alarm" stay distinguishable from the couch.
#
# Usage: automation/toast.sh <headline> <detail>
set -uo pipefail

HEADLINE="${1:?headline required}"
DETAIL="${2:?detail required}"

TOAST_PS1="${CHAIN_TOAST_PS1:-C:/Users/longt/.claude/toast.ps1}"
TOAST_LOG="${CHAIN_TOAST_LOG:-/mnt/c/Users/longt/.claude/toast.log}"
TAG="${CHAIN_TOAST_TAG:-ChainWatchdog}"

command -v powershell.exe >/dev/null 2>&1 || {
  echo "[toast] powershell.exe not reachable from WSL — no toast sent."; exit 1; }

# PowerShell single-quoted literals: the only escape is '' for '. Doing the
# quoting HERE, inside one base64 payload, means neither bash word-splitting
# nor WSL's argv interop ever sees the message text — that seam is where
# notifiers usually break on an apostrophe in someone's error string.
psq() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"; }

PS_SCRIPT="\$ErrorActionPreference='Stop'
try {
  & $(psq "${TOAST_PS1}") -Message $(psq "${HEADLINE}") -Detail $(psq "${DETAIL}") \
      -Sound 'Looping.Alarm2' -Ring -Urgent -Tag $(psq "${TAG}")
  'DISPATCHED'
} catch { 'TOAST_FAILED: ' + \$_.Exception.Message }"

# Snapshot the log BEFORE dispatch. Reading tail -1 afterwards without this
# happily reports yesterday's held=1 as proof that today's alarm landed —
# which is the precise failure this check exists to catch.
LINES_BEFORE=0
[ -f "${TOAST_LOG}" ] && LINES_BEFORE="$(wc -l < "${TOAST_LOG}" 2>/dev/null || echo 0)"

ENCODED="$(printf '%s' "${PS_SCRIPT}" | iconv -f UTF-8 -t UTF-16LE | base64 -w 0)"
# -ExecutionPolicy Bypass is load-bearing: the PO's hooks pass it too, and
# without it a Restricted policy refuses to load toast.ps1 at all.
RESULT="$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
            -EncodedCommand "${ENCODED}" 2>&1 | tr -d '\r' | tr '\n' ' ')"

# Verify the control, never its status: ask the notifier's OWN log what Windows
# kept — but only believe a line this invocation actually added.
VERDICT="unverified"
if [ -f "${TOAST_LOG}" ]; then
  LINES_AFTER="$(wc -l < "${TOAST_LOG}" 2>/dev/null || echo 0)"
  if [ "${LINES_AFTER}" -le "${LINES_BEFORE}" ]; then
    VERDICT="NO NEW toast.log LINE — toast.ps1 never ran to completion"
  else
    LAST="$(tail -1 "${TOAST_LOG}" 2>/dev/null | tr -d '\r')"
    case "${LAST}" in
      *"held=1"*) VERDICT="held=1 (Windows is holding it)" ;;
      *"held=0"*) VERDICT="held=0 — SENT AND DROPPED (Do-Not-Disturb, or the AppId went stale)" ;;
      *)          VERDICT="new toast.log line carries no held= field" ;;
    esac
  fi
fi

echo "[toast] dispatch: ${RESULT}"
echo "[toast] delivery: ${VERDICT}"

case "${RESULT}${VERDICT}" in
  *TOAST_FAILED*|*held=0*|*unverified*) exit 1 ;;
  *) exit 0 ;;
esac
