#!/usr/bin/env bash
# Prove `make parity` can go RED — without touching the model that is serving.
#
# M5-S3. Every red team in this repo since `marts-redteam` has the same shape and
# the same inversion: it plants ONE cause, asserts the check names it, and FAILS
# if the check stays green. What makes a parity red team different from the
# others is what it must NOT do. The alias-deletion drill (verify-m2) mutates the
# registry; the record-edit drill (verify-m4) mutates a tracked file. Here the
# obvious lever — point the endpoint at another model — would mean a deploy and a
# pointer move, i.e. the drill would break production to prove a test works. So
# both arms plant the cause inside the TEST:
#
#   ARM A  every feature is sent under its own name and dtype carrying the NEXT
#          feature's values. Every input is individually valid — right name,
#          right type, right shape, a number in range — and only the PAIRING is
#          wrong, so the endpoint returns a perfectly plausible number of
#          minutes for the wrong trip. It must produce a delta far above 1e-6.
#          (The first draft of this arm rotated the ORDER of the inputs instead
#          and measured exactly 0.000e+00: this runtime pairs by NAME, because
#          mlserver hands MLflow a named frame and the logged signature reorders
#          it. The drill going green under its own tampering is what taught that
#          — see docs/parity_m5.md §4.)
#
#   ARM B  the OFFLINE side loads registry version 1 explicitly (a read, never an
#          alias move) while the endpoint keeps serving version 2. The two must
#          not be reported as agreeing.
#
# Neither arm restarts a pod, redeploys, or writes to the registry. The
# InferenceService is not touched at all; `make parity` is green before and after
# and this script proves it by re-running it at the end.
#
# Exit code is INVERTED, like every red team here: 0 means the drill succeeded
# (the test went red for the planted cause and green again afterwards).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

RECORD_DIR="automation/runs/m5-parity"
FAILURES=0
CHECKS=0

say() { printf '\n=== %s\n' "$*"; }
ok() { CHECKS=$((CHECKS + 1)); printf 'ok    %s\n' "$*"; }
bad() {
	CHECKS=$((CHECKS + 1))
	FAILURES=$((FAILURES + 1))
	printf 'FAIL  %s\n' "$*"
}

# The state that must be identical afterwards. The alias is read, never written —
# a drill that could move the serving pointer is a drill nobody should run twice.
alias_now() {
	# The M5-S2 resolver, whose stdout is the payload and nothing else. Read with
	# a plain `grep`/`sed` rather than a python one-liner: the OpenMP shim re-execs
	# and cannot replay a `-c` source string on this host (F-024).
	uv run python scripts/resolve_champion_storage.py 2>/dev/null |
		sed -n 's/.*"version": "\([^"]*\)".*/\1/p' | head -1
}

ALIAS_BEFORE="$(alias_now)"
printf '[redteam] @champion resolves to version %s before the drill\n' "$ALIAS_BEFORE"

say 'ARM A — every feature carries its neighbour value (the served model is untouched)'
set +e
ARM_A="$(uv run python -m taxi_mlops.serving.parity --permute-columns --no-record 2>&1)"
ARM_A_RC=$?
set -e
printf '%s\n' "$ARM_A" | grep -Ev '^(Downloading artifacts|\[mlflow\])' | tail -25

if [[ $ARM_A_RC -eq 0 ]]; then
	bad "arm A: parity EXITED 0 with the columns rotated — a positional payload sent to the wrong features is exactly the defect this test exists to catch"
else
	ok "arm A: parity exited $ARM_A_RC (non-zero) with the columns rotated"
fi
# Naming the cause, not merely failing: the verdict must carry a measured delta
# above the bar. A red team that accepts any non-zero exit would pass on a typo.
if printf '%s\n' "$ARM_A" | grep -q 'FAIL: the deployed model does not compute'; then
	ok "arm A: the verdict names the disagreement rather than only exiting non-zero"
else
	bad "arm A: parity failed, but not with the delta verdict — check WHY it failed"
fi
ARM_A_DELTA="$(printf '%s\n' "$ARM_A" | sed -n 's/.*max |offline - online| = \([0-9.e+-]*\) minutes.*/\1/p' | tail -1)"
if [[ -n "$ARM_A_DELTA" ]] && awk -v d="$ARM_A_DELTA" 'BEGIN{exit !(d > 1e-6)}'; then
	ok "arm A: measured max |delta| = ${ARM_A_DELTA} minutes, far above the 1e-6 bar"
else
	bad "arm A: no measured delta above the bar was printed (read: '${ARM_A_DELTA:-none}')"
fi

say 'ARM B — the offline side loads version 1 while the wire still serves the champion'
set +e
ARM_B="$(uv run python -m taxi_mlops.serving.parity --against-version 1 --no-record 2>&1)"
ARM_B_RC=$?
set -e
printf '%s\n' "$ARM_B" | grep -Ev '^(Downloading artifacts|\[mlflow\])' | tail -20

if [[ $ARM_B_RC -eq 0 ]]; then
	bad "arm B: parity EXITED 0 while comparing the endpoint against a DIFFERENT registry version"
else
	ok "arm B: parity exited $ARM_B_RC (non-zero) against version 1"
fi
# Version 1 is the v1 feature set (5 columns) and version 2 is v2 (24), so the
# honest refusal arrives at the feature-set guard BEFORE any number is produced:
# the test declines to compute a delta between two models that do not eat the
# same matrix, rather than computing one and letting a reader believe it. Either
# that refusal or the version-mismatch verdict counts — both name the cause.
if printf '%s\n' "$ARM_B" | grep -Eq 'two different feature sets|is serving version'; then
	ok "arm B: the refusal names the cause (a different model, not a wider delta)"
else
	bad "arm B: parity failed without naming the model difference"
fi

say 'AFTER — nothing was mutated, and the real test is green again'
ALIAS_AFTER="$(alias_now)"
if [[ "$ALIAS_AFTER" == "$ALIAS_BEFORE" ]]; then
	ok "@champion still resolves to version $ALIAS_AFTER (unmoved across the drill)"
else
	bad "@champion moved: $ALIAS_BEFORE -> $ALIAS_AFTER"
fi

set +e
GREEN="$(uv run python -m taxi_mlops.serving.parity --record "$RECORD_DIR/parity.json" 2>&1)"
GREEN_RC=$?
set -e
printf '%s\n' "$GREEN" | grep -Ev '^(Downloading artifacts|\[mlflow\])' | tail -6
if [[ $GREEN_RC -eq 0 ]] && printf '%s\n' "$GREEN" | grep -q '\[parity\] PASS'; then
	ok "the untampered parity run is GREEN again (exit 0), so the drill left nothing behind"
else
	ok_rc="$GREEN_RC"
	bad "parity did NOT come back green after the drill (exit ${ok_rc}) — investigate before trusting either result"
fi

printf '\n[redteam] %d check(s), %d failure(s)\n' "$CHECKS" "$FAILURES"
if [[ $FAILURES -eq 0 ]]; then
	printf '[redteam] PASSED — `make parity` goes RED for a planted cause and GREEN without one.\n'
	exit 0
fi
printf '[redteam] FAILED — the parity test did not behave as a test.\n'
exit 1
