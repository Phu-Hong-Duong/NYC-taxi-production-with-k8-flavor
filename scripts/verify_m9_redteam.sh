#!/usr/bin/env bash
# verify_m9_redteam.sh — proves `make verify-m9` can go RED, on the program's
# last crossing. The M2-S5 … M8-S5 discipline, inherited whole: a gate nobody
# has watched say no is a green light.
#
# WHAT IT PLANTS, AND WHY THIS FIELD.
#
# One number in `automation/runs/m9-store-watch/headroom.json`: the online
# store's EXPECTED key count, shortened by exactly the size of one view — and
# the view is CHOSEN from the record as the smallest one, which on today's
# record is `zone_static`, the 263 rows that carry every centroid the champion's
# nine geometry features are built from.
#
# It is not a lie about a measurement. It is what a correct-looking expectation
# of the WRONG POPULATION reports, and it looks like nothing at all:
#
#   * it is derived from the record's own fields (total minus one view), so it
#     is exactly the number a tidying edit would produce;
#   * A-12b compares `keys < keys_expected` and NEITHER SIDE IS A LITERAL, so
#     the rule is not loosened, not renamed, and stays `health=ok` and
#     `inactive` — the live alerting stack reads identically before and after;
#   * the drill's records, the demo, the alias, the lock and the pins are all
#     untouched, so ~40 of the gate's sub-checks have no reason to complain;
#   * and the store it describes could lose every centroid it holds — breaking
#     every JFK quote on the wire — while still satisfying the alert that exists
#     to notice. That is the failure the three-witness leg was written for.
#
# WHAT MUST HAPPEN. THREE independent artifacts must contradict it: the record's
# own per-view arithmetic, the live store's DBSIZE plus the M8-S4
# materialization record, and `docs/store_watchdog_m9.md` — the only witness a
# human reads. And the legs that read the DEMO, the rules, the drill and the
# pointer must STAY GREEN: what separates a gate that fails on a wrong number
# from a checksum is that an unrelated edit does not turn the milestone red.
#
# WHAT IT TOUCHES: one tracked JSON file, restored under an EXIT trap and
# verified by sha256. No cluster state, no pod, no image, no Redis key, no
# Prometheus rule, no MLflow run, no registry version, no alias, no traffic and
# no page. The drill's entire footprint is one file that ends the run
# byte-identical to how it started.
#
# Usage: scripts/verify_m9_redteam.sh   (via `make verify-m9-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m9-store-watch/headroom.json"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[verify-m9-redteam] %s\033[0m\n' "$1"; }
ok()  { printf '  \033[32mok  \033[0m %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; PROBLEMS=$((PROBLEMS + 1)); }

restore() {
  [[ "$RESTORED" -eq 1 ]] && return 0
  if cp "$BACKUP" "$RECORD"; then
    RESTORED=1
    local now before
    now="$(sha256sum "$RECORD" | cut -d' ' -f1)"
    before="$(sha256sum "$BACKUP" | cut -d' ' -f1)"
    if [[ "$now" == "$before" ]]; then
      printf '  restored %s (sha256 %s…)\n' "$RECORD" "${now:0:12}"
    else
      printf '\033[31m  RESTORE DID NOT MATCH — %s is not what it was.\033[0m\n' "$RECORD" >&2
    fi
  else
    printf '\033[31m[verify-m9-redteam] COULD NOT RESTORE %s.\033[0m\n' "$RECORD" >&2
    printf 'The drill kept a copy at %s — copy it back by hand.\n' "$BACKUP" >&2
    printf '  (or, since it is tracked:  git checkout -- %s)\n' "$RECORD" >&2
    return 0
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no headroom record to red-team." >&2
  echo "Run: make store-watch-headroom" >&2
  exit 2
fi
cp "$RECORD" "$BACKUP"
BEFORE_SHA="$(sha256sum "$RECORD" | cut -d' ' -f1)"
printf '  %s  sha256 %s…\n' "$RECORD" "${BEFORE_SHA:0:12}"

# ------------------------------------------------------------ 1. break it -----
say "1. shorten the EXPECTED key count by exactly one view — the arithmetic a tidying edit produces"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
expected = rec["expected_keys"]

# The target view is CHOSEN from the record — the smallest one, so the plant is
# the least visible edit available and the resulting total is still the right
# order of magnitude. A typed view name would stop being an argument about the
# property the day the source set legitimately changed.
view, size = min(expected["per_view"].items(), key=lambda kv: kv[1])
was = expected["total"]
expected["total"] = was - size
path.write_text(json.dumps(rec, indent=1) + "\n")

share = 100.0 * size / was
print(f"  expected_keys.total: {was:,} -> {expected['total']:,} — short by exactly the "
      f"{size:,} keys of {view!r} ({share:.2f}% of the store, and the smallest view there is). "
      f"UNTOUCHED: per_view {expected['per_view']}, transformer_dependency_keys "
      f"{expected['transformer_dependency_keys']:,}, the live_store block, the "
      f"materialization block and three_witnesses_agree={rec['three_witnesses_agree']}.")
print(f"  A-12b compares keys < keys_expected with NO LITERAL on either side, so the rule is "
      f"not loosened and stays inactive — but a store that lost every one of {view!r}'s keys "
      f"would now satisfy it, and {view!r} is where the centroids live.")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m9 — expected RED, from the record's arithmetic, the live store AND the write-up"
red_log="$(bash scripts/verify_m9.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -aE 'FAIL|\[verify-m9\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose expected count no longer reconciles"
else
  bad "the gate exited 0 — it read a plausible total and believed it"
fi
if printf '%s\n' "$red_log" | grep -aq "per-view counts sum to"; then
  ok "the ARITHMETIC leg fired: the record's own per-view counts do not sum to its total, so the expected side of A-12b is not derived from the sources it claims"
else
  bad "no leg checked the expected total against its own parts — the gate is reading a summary field it cannot check"
fi
if printf '%s\n' "$red_log" | grep -aq "witnesses disagree"; then
  ok "the LIVE leg fired: DBSIZE and the M8-S4 materialization record both still say what the store really holds, and they are not the same number any more"
else
  bad "the live leg did NOT fire — a rewritten expectation contradicted nothing outside its own file"
fi
if printf '%s\n' "$red_log" | grep -aq "the write-up quotes no record for"; then
  ok "the PROSE leg fired: docs/store_watchdog_m9.md renders an expected count the record no longer holds — the only witness a human reads"
else
  bad "the prose leg did NOT fire — the write-up and the records may drift apart unnoticed"
fi

# "Others still counted": every section that does not read this field must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides forty.
red_oks="$(printf '%s\n' "$red_log" | grep -ac 'ok  ')"
if [[ "$red_oks" -ge 38 ]]; then
  ok "$red_oks sub-check line(s) still passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "<option> elements" \
                   "PUBLISHED trip" \
                   "recorded OPEN and honestly" \
                   "BEFORE the accept record" \
                   "compares a claim to 0" \
                   "series the rules SELECT are produced by" \
                   "DEMO's own request path answered" \
                   "LOADED with health=ok" \
                   "FIRED and reached Alertmanager" \
                   "NOT ONE of the" \
                   "BYTE-IDENTICAL to the m7-closed tag"; do
  if printf '%s\n' "$red_log" | grep -aqE "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# THE LEG THAT MUST **NOT** FIRE, and it is the whole reason for choosing this
# field. A-12b carries no number on either side, so a shortened EXPECTATION does
# not loosen a documented bar — the rules leg has nothing to complain about, and
# a gate that went red there too would be failing on the fact of an edit rather
# than on a wrong number.
if printf '%s\n' "$red_log" | grep -aq "bar-shaped number in all three rules"; then
  ok "the NO-NUMBER leg is STILL GREEN — the plant leaves every rule's argument intact, which is what makes this a test of the gate's reasoning rather than a checksum"
else
  bad "the rules leg went red too — the plant was too crude to distinguish a wrong population from any change"
fi
if printf '%s\n' "$red_log" | grep -aq "the demo's EXACT bar was committed"; then
  ok "and law 4's ordering leg is still green — the plant is a value, not a history, and the gate distinguishes the two"
else
  bad "the ordering leg went red too — collateral damage across artifacts"
fi

# ------------------------------------------------------------ 3. put it back --
say "3. restore the record and re-run — expected GREEN again"
restore
trap - EXIT
after_sha="$(sha256sum "$RECORD" | cut -d' ' -f1)"
if [[ "$after_sha" == "$BEFORE_SHA" ]]; then
  ok "$RECORD is byte-identical to what the drill found (sha256 ${after_sha:0:12}…)"
else
  bad "$RECORD changed across the drill — ${BEFORE_SHA:0:12}… -> ${after_sha:0:12}…"
fi
green_log="$(bash scripts/verify_m9.sh 2>&1)"
green_rc=$?
printf '%s\n' "$green_log" | tail -8
if [[ "$green_rc" -eq 0 ]]; then
  green_oks="$(printf '%s\n' "$green_log" | grep -ac 'ok  ')"
  ok "the gate is GREEN again ($green_oks sub-check line(s), exit 0) — the drill left nothing behind"
else
  bad "the gate is still RED after the restore (rc=$green_rc) — the drill damaged something"
  printf '%s\n' "$green_log" | grep -a 'FAIL' >&2
fi

# A clean drill leaves a CLEAN TREE — a property that could only be stated once
# the records became tracked files (F-029, closed at M5-S1, and still paying).
dirty="$(git status --porcelain "$RECORD")"
if [[ -z "$dirty" ]]; then
  ok "git status is clean for $RECORD — the restore is byte-identical to the committed record"
else
  bad "the tree is dirty after the drill: $dirty"
fi

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$PROBLEMS" -eq 0 ]]; then
  printf '\033[32m[verify-m9-redteam] PASSED: the M9 gate went RED on ONE rewritten expected\033[0m\n'
  printf '\033[32m                    key count — short by exactly the view that holds every\033[0m\n'
  printf '\033[32m                    centroid, derived from the record own fields, leaving\033[0m\n'
  printf '\033[32m                    A-12b unloosened and every alert inactive — and named\033[0m\n'
  printf '\033[32m                    the record own arithmetic, the live store AND the\033[0m\n'
  printf '\033[32m                    write-up a human reads, while the demo, the rules, the\033[0m\n'
  printf '\033[32m                    drill and the pointer stayed green. GREEN on restore.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m9-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
