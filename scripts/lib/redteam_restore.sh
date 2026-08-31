#!/usr/bin/env bash
# redteam_restore.sh — the snapshot / restore / verify-sha scaffold every
# record-editing red team shares. SOURCE it.
#
# Consolidated at CU-S3 out of eight copies (verify_m3…verify_m9_redteam and
# gate_margin_redteam) that differed only in the name of the variable holding
# the target path and in one line of prose. Nothing here is new.
#
# WHAT LIVES HERE — the plumbing that makes a destructive drill safe, and the
# counters its verdict is read off:
#   * PROBLEMS,                 the drill's own failure count
#   * say / ok / bad,           the three printers (labelled by REDTEAM_LABEL)
#   * redteam_snapshot <path>,  byte copy + sha + the EXIT trap, in that order
#   * redteam_restore,          idempotent, sha-verified, two ways back on failure
#   * redteam_assert_restored,  the drill's own proof it left nothing behind
#
# WHAT DELIBERATELY DOES NOT LIVE HERE, and must not move here later:
#   * THE PLANT. A red team's plant IS its argument — which field, chosen from
#     the record rather than typed, wrong in the direction that still reads as a
#     pass. Eight plants, eight arguments, no copies.
#   * THE ASSERTIONS about the RED run: which artifacts must name the fault, how
#     many sub-checks must still pass, which legs must stay GREEN by design.
#     A drill that fails on ANY edit is a checksum; those clauses are what make
#     each one a drill.
#   * THE "record is missing" REFUSAL. Each drill's message names what the
#     record IS and, where one exists, the command that produces it. That is a
#     pointer to work, not plumbing.
#
# ORDER IS LOAD-BEARING inside redteam_snapshot: the copy is taken, then the
# trap is installed. A trap installed first would, on an interrupt in the
# microsecond before the copy exists, "restore" the target from an empty file.
#
# Usage, in a drill, after REPO_ROOT is computed:
#     REDTEAM_LABEL="[verify-m9-redteam]"
#     source "$REPO_ROOT/scripts/lib/redteam_restore.sh"
#     ...
#     redteam_snapshot "$RECORD"     # step 0
#     ...                            # the plant, the RED run, the assertions
#     redteam_assert_restored        # step 3
#
# It is sourced, never executed: it defines and returns.

: "${REDTEAM_LABEL:?set REDTEAM_LABEL (e.g. '[verify-m9-redteam]') before sourcing}"

REDTEAM_TARGET=""
REDTEAM_BACKUP=""
REDTEAM_BEFORE_SHA=""
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m%s %s\033[0m\n' "$REDTEAM_LABEL" "$1"; }
ok()  { printf '  \033[32mok  \033[0m %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; PROBLEMS=$((PROBLEMS + 1)); }

# Put the target back exactly as it was found, and SAY whether that worked
# rather than assuming it. Idempotent: the EXIT trap and the drill's own step 3
# both call it, and only the first does anything.
redteam_restore() {
  [[ "$RESTORED" -eq 1 ]] && return 0
  if cp "$REDTEAM_BACKUP" "$REDTEAM_TARGET"; then
    RESTORED=1
    local now before
    now="$(sha256sum "$REDTEAM_TARGET" | cut -d' ' -f1)"
    before="$(sha256sum "$REDTEAM_BACKUP" | cut -d' ' -f1)"
    if [[ "$now" == "$before" ]]; then
      printf '  restored %s (sha256 %s…)\n' "$REDTEAM_TARGET" "${now:0:12}"
    else
      printf '\033[31m  RESTORE DID NOT MATCH — %s is not what it was.\033[0m\n' "$REDTEAM_TARGET" >&2
    fi
  else
    printf '\033[31m%s COULD NOT RESTORE %s.\033[0m\n' "$REDTEAM_LABEL" "$REDTEAM_TARGET" >&2
    # The byte copy is named FIRST because it is right under every condition; it
    # was taken at step 0 of THIS run, so it is exactly what was there, and it
    # is deliberately not deleted on this path. `git checkout --` is right only
    # if the file was committed as this drill found it, which a failing restore
    # path may not assume.
    printf 'Copy it back by hand:  cp %s %s\n' "$REDTEAM_BACKUP" "$REDTEAM_TARGET" >&2
    printf '  (or, if it was committed as found:  git checkout -- %s)\n' "$REDTEAM_TARGET" >&2
    return 0
  fi
  rm -f "$REDTEAM_BACKUP"
}

# Step 0. Take the byte copy, record the sha, arm the trap — in that order —
# and print the one line a reader compares against step 3's.
redteam_snapshot() {
  REDTEAM_TARGET="$1"
  REDTEAM_BACKUP="$(mktemp)"
  cp "$REDTEAM_TARGET" "$REDTEAM_BACKUP"
  REDTEAM_BEFORE_SHA="$(sha256sum "$REDTEAM_TARGET" | cut -d' ' -f1)"
  trap redteam_restore EXIT
  printf '  %s  sha256 %s…\n' "$REDTEAM_TARGET" "${REDTEAM_BEFORE_SHA:0:12}"
}

# Step 3. Restore, disarm the trap, and PROVE byte-identity rather than claiming
# it — a drill that damaged the evidence it read must say so in its own verdict.
redteam_assert_restored() {
  redteam_restore
  trap - EXIT
  local after
  after="$(sha256sum "$REDTEAM_TARGET" | cut -d' ' -f1)"
  if [[ "$after" == "$REDTEAM_BEFORE_SHA" ]]; then
    ok "$REDTEAM_TARGET is byte-identical to what the drill found (sha256 ${after:0:12}…)"
  else
    bad "$REDTEAM_TARGET changed across the drill — ${REDTEAM_BEFORE_SHA:0:12}… -> ${after:0:12}…"
  fi
}
