#!/usr/bin/env bash
# verify_m2_redteam.sh — prove `make verify-m2` can go RED, and can come back.
#
# The twin of `marts-redteam` and `train-redteam`, applied to the gate itself. A
# suite that has only ever been seen passing is a suite nobody has tested; M1's
# gate shipped with a leg that grepped for a string the script never printed and
# reported "0 output(s) byte-identical" while passing. The cure is to break
# something on purpose and watch the light change.
#
# What it breaks, and why this one: **the champion alias**. It is the single most
# load-bearing fact in M2 — the registry's answer to "what did we promote?" — and
# it is the only fault this suite can inject that is (a) instant, (b) exactly
# reversible, and (c) invisible to every check that is not actually reading the
# registry. Deleting it does NOT quietly break the model: version 1, its run, its
# signature and its artifacts are untouched throughout. Only the pointer moves.
#
# Because the alias is load-bearing, its removal is expected to fail SEVERAL
# sub-checks, not one: everything that asks "which model?" loses its answer. That
# is the honest shape of this fault, so the drill asserts both halves —
#   * the RED run NAMES the alias as the thing that does not resolve, and
#   * the sections that do not depend on the registry are still RUN and still
#     pass (a gate that collapses to one failure when one thing breaks tells you
#     nothing about the rest of the system).
#
# Safety: the alias is restored by an EXIT trap, so a Ctrl-C, a failure, or a
# crash mid-drill still leaves `@champion` pointing where it pointed. The restore
# is idempotent (set-to-the-recorded-version), and the script re-reads the
# registry afterwards to prove it, rather than assuming the write worked.
#
# Usage: scripts/verify_m2_redteam.sh   (via `make verify-m2-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STATE_FILE="$(mktemp)"
RESTORED=0

say() { printf '\n\033[1m[verify-m2-redteam] %s\033[0m\n' "$1"; }
ok()  { printf '  \033[32mok  \033[0m %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; PROBLEMS=$((PROBLEMS + 1)); }
PROBLEMS=0

alias_op() {  # alias_op <read|drop|restore>
  ALIAS_OP="$1" STATE_FILE="$STATE_FILE" uv run python - <<'PY'
import json, os, sys

import mlflow

from taxi_mlops.training import tracking
from taxi_mlops.training.run import load_train_config

cfg = load_train_config("configs/train.yaml")
tracking.configure(cfg["mlflow"])
client = mlflow.MlflowClient()
name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]
op, state_file = os.environ["ALIAS_OP"], os.environ["STATE_FILE"]

if op == "read":
    mv = client.get_model_version_by_alias(name, alias)
    json.dump({"name": name, "alias": alias, "version": str(mv.version)},
              open(state_file, "w"))
    print(f"models:/{name}@{alias} -> version {mv.version}")
elif op == "drop":
    client.delete_registered_model_alias(name, alias)
    try:
        client.get_model_version_by_alias(name, alias)
    except Exception:
        print(f"alias @{alias} deleted — it no longer resolves")
    else:
        print("STILL RESOLVES", file=sys.stderr)
        raise SystemExit(1)
elif op == "restore":
    state = json.load(open(state_file))
    client.set_registered_model_alias(state["name"], state["alias"], state["version"])
    mv = client.get_model_version_by_alias(state["name"], state["alias"])
    assert str(mv.version) == state["version"], "restored to the WRONG version"
    print(f"models:/{state['name']}@{state['alias']} -> version {mv.version} (restored)")
PY
}

restore() {
  [[ "$RESTORED" -eq 1 ]] && return 0
  if alias_op restore | grep -v '^\[mlflow\]'; then
    RESTORED=1
  else
    printf '\033[31m[verify-m2-redteam] COULD NOT RESTORE THE CHAMPION ALIAS.\033[0m\n' >&2
    printf 'Run this by hand:  uv run python -c "%s"\n' \
      "import mlflow,json;from taxi_mlops.training import tracking;from taxi_mlops.training.run import load_train_config;c=load_train_config('configs/train.yaml');tracking.configure(c['mlflow']);mlflow.MlflowClient().set_registered_model_alias('nyc-taxi-eta','champion','1')" >&2
  fi
  rm -f "$STATE_FILE"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. what is champion right now (restored to exactly this, whatever happens)"
if ! alias_op read | grep -v '^\[mlflow\]'; then
  echo "the champion alias does not resolve BEFORE the drill — nothing to red-team." >&2
  exit 2
fi

# ------------------------------------------------------------ 1. break it -----
say "1. delete the champion alias — the model, its run and its artifacts stay untouched"
if ! alias_op drop | grep -v '^\[mlflow\]'; then
  echo "could not delete the alias; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m2 — expected RED, naming the alias"
red_log="$(bash scripts/verify_m2.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m2\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED, as it must be with no champion"
else
  bad "the gate exited 0 with NO CHAMPION ALIAS — it is not reading the registry"
fi
if printf '%s\n' "$red_log" | grep -q 'does not resolve'; then
  ok "it NAMES the broken thing: models:/…@champion does not resolve"
else
  bad "the RED run does not name the alias — a failure you have to guess at"
fi
# "Others still counted": the sections that do not ask the registry anything must
# still have RUN and passed. A suite that stops at the first failure would report
# one problem and hide nine.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 25 ]]; then
  ok "$red_oks sub-check(s) still ran and passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "error_segments is queryable" "RAN against the marts warehouse" \
                   "reproduced the memo's headline" "is EMPTY — marts read model output"; do
  if printf '%s\n' "$red_log" | grep -qF "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# ------------------------------------------------------------ 3. put it back --
say "3. restore the alias and re-run — expected GREEN again"
restore
trap - EXIT
green_log="$(bash scripts/verify_m2.sh 2>&1)"
green_rc=$?
printf '%s\n' "$green_log" | tail -6
if [[ "$green_rc" -eq 0 ]]; then
  green_oks="$(printf '%s\n' "$green_log" | grep -c 'ok  ')"
  ok "the gate is GREEN again ($green_oks sub-checks, exit 0) — the drill left nothing behind"
else
  bad "the gate is still RED after the restore (rc=$green_rc) — the drill damaged something"
  printf '%s\n' "$green_log" | grep 'FAIL' >&2
fi

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$PROBLEMS" -eq 0 ]]; then
  printf '\033[32m[verify-m2-redteam] PASSED: the M2 gate went RED naming the champion alias, kept\033[0m\n'
  printf '\033[32m                    counting every other sub-check, and returned GREEN when restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m2-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
