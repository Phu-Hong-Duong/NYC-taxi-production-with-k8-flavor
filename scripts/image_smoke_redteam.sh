#!/usr/bin/env bash
# image_smoke_redteam.sh — prove the D-004 checks are sensors, not decorations.
# Behind `make image-smoke-redteam`. Owner story: M4-S3.
#
# WHAT IT BREAKS, AND WHY THAT PARTICULAR THING. The program's red-team habit is
# to break the POINTER and never the state: `verify-m2-redteam` deletes the
# `@champion` alias and not a version; `verify-m3-redteam` rewrites one recorded
# NUMBER and restores it byte-identical. The equivalent here is to hide the
# system's libgomp from ONE container by bind-mounting an empty file over it. The
# IMAGE is untouched (the container is --rm, the mount lives for one process), the
# nodes are untouched, the cluster is never contacted — and inside that one
# container the world looks exactly as it looks on this WSL host, which is the
# state D-004 exists because of.
#
# It must produce three observations, all of them the opposite of the smoke's:
#   1. openmp_status() -> (False, 'not loadable yet; a vendored copy exists at …')
#   2. ensure_openmp() PRINTS the '[openmp] …' announcement and re-execs
#   3. after that, the shim directory /app/.venv/lib/openmp EXISTS
# If any of those does NOT flip, the corresponding smoke check is not measuring
# anything and the D-004 evidence is worthless — so this script exits 1 on a
# check that stayed green, i.e. its exit code is inverted the way
# `make marts-redteam` inverts dbt's.
#
# Usage: scripts/image_smoke_redteam.sh [image-ref]
# Exit: 0 the checks flipped as predicted (the sensors work) · 1 one did not · 2 preconditions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MANIFEST="automation/runs/m4-image/image.json"
IMAGE_REF="${1:-}"
if [[ -z "$IMAGE_REF" ]]; then
  [[ -f "$MANIFEST" ]] || { echo "FAIL  no image ref given and $MANIFEST is absent — 'make image-load' first" >&2; exit 2; }
  IMAGE_REF="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_ref"])' "$MANIFEST")"
fi
command -v docker >/dev/null || { echo "FAIL  docker not found (gotcha #34)" >&2; exit 2; }
docker image inspect "$IMAGE_REF" >/dev/null 2>&1 \
  || { echo "FAIL  image $IMAGE_REF is not in the local daemon" >&2; exit 2; }

# The mask: an EMPTY regular file. dlopen of an empty file fails the same way a
# missing one does, and a regular file is what docker will bind onto a library
# path. Deleted on EXIT — the M3-S5 restore-under-a-trap pattern, even though
# nothing outside /tmp is being touched.
MASK="$(mktemp /tmp/libgomp-mask.XXXXXX)"
trap 'rm -f "$MASK"' EXIT
: > "$MASK"

SOPATH="/lib/x86_64-linux-gnu/libgomp.so.1"
masked() { docker run --rm -v "${MASK}:${SOPATH}:ro" "$IMAGE_REF" "$@"; }

PASS=0; FAILED=0
ok()  { printf 'ok    %s\n' "$*"; PASS=$(( PASS + 1 )); }
bad() { printf 'FAIL  %s\n' "$*"; FAILED=$(( FAILED + 1 )); }

echo "== D-004 sensor red team ======================================="
echo "  image  : $IMAGE_REF"
echo "  masking: $SOPATH  (empty file, one container, --rm)"

echo ""
echo "-- baseline: the image itself is NOT modified by this drill ------"
baseline="$(docker run --rm "$IMAGE_REF" python -c \
  'from taxi_mlops.training.openmp import openmp_status; print(openmp_status())')"
echo "     unmasked: $baseline"
[[ "$baseline" == "(True, 'system libgomp.so.1')" ]] \
  && ok "unmasked container still reports the system library" \
  || bad "the unmasked baseline is already wrong — fix the smoke before reading this"

echo ""
echo "-- 1. openmp_status() must stop saying 'system' ------------------"
status_out="$(masked python -c \
  'from taxi_mlops.training.openmp import openmp_status; print(openmp_status())' 2>&1 || true)"
echo "     $status_out"
if [[ "$status_out" == "(False,"* && "$status_out" == *"vendored copy exists"* ]]; then
  ok "check 2 flipped: the probe now reports the system library unusable"
else
  bad "check 2 did NOT flip — openmp_status() is not reading the system library"
fi

echo ""
echo "-- 2. ensure_openmp() must ANNOUNCE the shim --------------------"
# `-m`, not `-c`: F-024 (found by this very drill) means the `-c` form cannot
# re-exec and now refuses instead, which would make this check assert the refusal
# rather than the shim. A throwaway module run with `-m` takes the real path — the
# one every entry point in the program uses.
ensure_out="$(masked python -m taxi_mlops.training.openmp_probe 2>&1 || true)"
sed 's/^/     /' <<<"$ensure_out"
if grep -q '\[openmp\]' <<<"$ensure_out"; then
  ok "check 3 flipped: the shim fired and said so on stdout"
else
  bad "check 3 did NOT flip — a masked libgomp produced no announcement, so the"
  bad "  smoke's 'no [openmp] line' assertion proves nothing"
fi

echo ""
echo "-- 4. the shim must leave the directory check 8 looks for -------"
# Same container, both actions: fire the shim, then look for its directory. Two
# containers would prove nothing, since each starts from the pristine image.
#
# `bash -c`, NEVER `bash -lc`. A LOGIN shell re-reads /etc/profile, which rebuilds
# PATH from scratch and throws away the image's `ENV PATH=/app/.venv/bin:…` — so
# `python` becomes the base interpreter and every import of taxi_mlops fails. The
# first version of this drill used -lc, got ModuleNotFoundError into /dev/null, and
# reported "the shim left no directory" — a red verdict about the wrong thing.
trace_out="$(masked bash -c '
python -m taxi_mlops.training.openmp_probe >/dev/null 2>&1 || true
test -e /app/.venv/lib/openmp && echo "PRESENT: /app/.venv/lib/openmp" || echo "absent: /app/.venv/lib/openmp"
ls -l /app/.venv/lib/openmp 2>/dev/null || true' 2>&1 || true)"
sed 's/^/     /' <<<"$trace_out"
if grep -q '^PRESENT' <<<"$trace_out"; then
  ok "check 8 flipped: the shim created /app/.venv/lib/openmp"
else
  bad "check 8 did NOT flip — its absence in the smoke is not evidence of anything"
fi

echo ""
# Single quotes: backticks inside a double-quoted echo are command substitution,
# which printed `-c: command not found` above its own header on the first run.
echo '-- 5. F-024: the `-c` form must REFUSE, not exec a broken argv ---'
dash_c_out="$(masked python -c \
  'from taxi_mlops.training.openmp import ensure_openmp; ensure_openmp()' 2>&1 || true)"
sed 's/^/     /' <<<"$dash_c_out"
if grep -q 'OpenMPUnavailableError' <<<"$dash_c_out" \
   && grep -q 'python -c' <<<"$dash_c_out" \
   && ! grep -q 'Argument expected for the -c option' <<<"$dash_c_out"; then
  ok "the -c path raises OpenMPUnavailableError naming the situation (F-024 fixed)"
else
  bad "the -c path did not refuse cleanly — F-024 has regressed"
fi

echo ""
echo "-- 6. and the image on disk is unchanged ------------------------"
after="$(docker run --rm "$IMAGE_REF" bash -c \
  'test -e /app/.venv/lib/openmp && echo PRESENT || echo absent' 2>&1)"
echo "     a fresh container from the same image: $after"
[[ "$after" == "absent" ]] \
  && ok "the drill left no trace in the image — every mutation lived in one --rm container" \
  || bad "a fresh container HAS the shim directory — the drill modified the image"

echo ""
echo "== verdict ====================================================="
echo "  $PASS flipped-as-predicted · $FAILED did not"
if (( FAILED > 0 )); then
  echo "RED — at least one D-004 check is not a sensor. The smoke's green means less"
  echo "      than it claims; fix the check before trusting the debt closure."
  exit 1
fi
echo "GREEN — all $PASS observations flipped. The smoke's D-004 checks measure something."
