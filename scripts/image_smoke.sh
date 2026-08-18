#!/usr/bin/env bash
# image_smoke.sh — prove the task image runs OUR code, and that D-004 is dead.
# Behind `make image-smoke`. Owner story: M4-S3.
#
# WHY THIS EXISTS AND WHY IT IS NOT A COMMENT IN THE DOCKERFILE. Debt D-004 does
# not ask for `apt-get install libgomp1`; it asks for evidence that "the image's
# OpenMP is the system's, not a borrowed one" — because the borrowed one WORKS,
# and a shim that quietly keeps working is a debt that quietly never closes. The
# only difference visible from outside is a line on stdout. So check 3 asserts
# the absence of that line, and check 8 asserts the absence of the directory the
# shim would have created. Both are checks on a thing NOT happening, which is the
# only shape of check that can retire this debt (gotcha #51's question asked of
# ourselves: could this tell us if it were false? Yes — remove libgomp1 from the
# Dockerfile and checks 1, 2, 3 and 8 all go red).
#
# Every check runs INSIDE the image. Nothing here is inferred from the Dockerfile.
#
# Usage:
#   scripts/image_smoke.sh [image-ref]     # default: the ref make image-load recorded
#   SKIP_UNIT=1 scripts/image_smoke.sh     # skip check 6 only (the slow one)
# Exit: 0 all checks green · 1 one or more red · 2 preconditions missing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MANIFEST="automation/runs/m4-image/image.json"
IMAGE_REF="${1:-}"
if [[ -z "$IMAGE_REF" ]]; then
  [[ -f "$MANIFEST" ]] || { echo "FAIL  no image ref given and $MANIFEST is absent — run 'make image-load' first" >&2; exit 2; }
  IMAGE_REF="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_ref"])' "$MANIFEST")"
fi
command -v docker >/dev/null || { echo "FAIL  docker not found (gotcha #34)" >&2; exit 2; }
docker image inspect "$IMAGE_REF" >/dev/null 2>&1 \
  || { echo "FAIL  image $IMAGE_REF is not in the local daemon — run 'make image-load'" >&2; exit 2; }

PASS=0; FAILED=0
ok()   { printf 'ok    %s\n' "$*"; PASS=$(( PASS + 1 )); }
bad()  { printf 'FAIL  %s\n' "$*"; FAILED=$(( FAILED + 1 )); }
head2() { printf '\n-- %s\n' "$*"; }

# Every container is --rm, non-network by default, and runs as the image's own
# USER (uid 1000). No check needs the cluster: this is about the artifact.
run() { docker run --rm "$IMAGE_REF" "$@"; }

echo "== task image smoke ============================================"
echo "  image : $IMAGE_REF"

# ---------------------------------------------------------------- 1. the package
head2 "1. libgomp1 is a real apt package inside the image (D-004)"
if out="$(run bash -lc 'dpkg-query -W -f="${Package} ${Version} ${Status}\n" libgomp1 2>&1')"; then
  echo "     $out"
  if [[ "$out" == *"install ok installed"* ]]; then
    ok "libgomp1 installed by dpkg: ${out%% install*}"
  else
    bad "dpkg knows libgomp1 but it is not installed: $out"
  fi
else
  bad "dpkg-query found no libgomp1: $out"
fi
if out="$(run bash -lc 'ldconfig -p | grep -m2 "libgomp\.so\.1"')"; then
  echo "     $out"
  # The path matters: /usr/lib/... is the system's. Anything under
  # site-packages or /app/.venv would be a wheel's vendored copy, i.e. the shim.
  if grep -qE '=> */usr/lib' <<<"$out" && ! grep -q 'site-packages\|/app/\.venv' <<<"$out"; then
    ok "the loader resolves libgomp.so.1 from /usr/lib — not from a wheel"
  else
    bad "libgomp.so.1 resolves somewhere other than the system path: $out"
  fi
else
  bad "ldconfig cannot see libgomp.so.1 at all"
fi

# ------------------------------------------------------- 2 & 3. the probe & shim
head2 "2. openmp_status() is (True, 'system libgomp.so.1') on the FIRST line"
status_out="$(run python -c 'from taxi_mlops.training.openmp import openmp_status; print(openmp_status())')"
echo "     $status_out"
first_line="$(head -n1 <<<"$status_out")"
if [[ "$first_line" == "(True, 'system libgomp.so.1')" ]]; then
  ok "openmp_status() -> $first_line (first line, nothing printed before it)"
else
  bad "expected (True, 'system libgomp.so.1') as line 1, got: $first_line"
fi

head2 "3. ensure_openmp() takes the system path and announces NOTHING"
ensure_out="$(run python -c '
from taxi_mlops.training.openmp import ensure_openmp
print(ensure_openmp())')"
echo "     $ensure_out"
if [[ "$ensure_out" == "openmp: system libgomp.so.1" ]]; then
  ok "ensure_openmp() -> $ensure_out"
else
  bad "ensure_openmp() returned something else: $ensure_out"
fi
if grep -q '\[openmp\]' <<<"$ensure_out"; then
  bad "the shim ANNOUNCED itself — it fired in the image, which is exactly D-004"
else
  ok "no '[openmp]' announcement anywhere in the output — the shim never ran"
fi

# -------------------------------------------------------------- 4. the imports
head2 "4. the OpenMP consumers import clean, and the interpreter is recorded"
import_out="$(run python -c '
import sys
print("python:", sys.version.replace("\n", " "))
import lightgbm, xgboost, flaml, pandas, sklearn, pyarrow
import mlflow
print("lightgbm:", lightgbm.__version__)
print("xgboost:", xgboost.__version__)
print("flaml:", flaml.__version__)
print("pandas:", pandas.__version__)
print("sklearn:", sklearn.__version__)
print("pyarrow:", pyarrow.__version__)
print("mlflow:", mlflow.__version__)
import flyte
print("flyte SDK: importable")
')"
sed 's/^/     /' <<<"$import_out"
if grep -q '\[openmp\]' <<<"$import_out"; then
  bad "importing lightgbm/xgboost/flaml fired the shim"
else
  ok "lightgbm, xgboost, flaml, pandas, sklearn, pyarrow, mlflow, flyte imported with no shim line"
fi

# --------------------------------------- 5. the graph is the HOST's, not a fresh one
head2 "5. the installed dependency graph equals the host venv's (uv.lock, --frozen)"
graph_probe='
import json
from importlib.metadata import distributions
print(json.dumps({d.metadata["Name"].lower(): d.version for d in distributions()
                  if d.metadata["Name"]}, sort_keys=True))
'
host_graph="$(uv run python -c "$graph_probe")"
image_graph="$(run python -c "$graph_probe")"
if diff_out="$(python3 - "$host_graph" "$image_graph" <<'PY'
import json, sys
host, image = (json.loads(a) for a in sys.argv[1:3])
diffs = []
for name in sorted(set(host) | set(image)):
    if host.get(name) != image.get(name):
        diffs.append(f"{name}: host={host.get(name, '-')} image={image.get(name, '-')}")
print(f"{len(host)} host / {len(image)} image packages; {len(diffs)} disagreement(s)")
for line in diffs:
    print("  " + line)
raise SystemExit(1 if diffs else 0)
PY
)"; then
  sed 's/^/     /' <<<"$diff_out"
  ok "every package version in the image matches the host venv"
else
  sed 's/^/     /' <<<"$diff_out"
  bad "the image's dependency graph differs from the host's"
fi

# ------------------------------------------------------------ 6. the unit suite
head2 "6. the unit suite runs INSIDE the image"
if [[ "${SKIP_UNIT:-0}" == "1" ]]; then
  echo "     SKIP_UNIT=1 — skipped"
  bad "the unit suite was skipped (SKIP_UNIT=1 is a debugging lever, never a pass)"
else
  # The image has no cluster and no data; pyproject's addopts already exclude the
  # integration and smoke markers, so this is the same subset CI runs on a PR.
  if unit_out="$(run python -m pytest tests/unit -q 2>&1)"; then
    tail -n 3 <<<"$unit_out" | sed 's/^/     /'
    ok "tests/unit green in-image: $(grep -oE '[0-9]+ passed[^ ]*' <<<"$unit_out" | tail -n1)"
  else
    tail -n 25 <<<"$unit_out" | sed 's/^/     /'
    bad "tests/unit FAILED inside the image"
  fi
fi

# ---------------------------------------------- 7. one real pipeline stage runs
head2 "7. pipelines/tasks.py validate() runs in-image over real pinned data"
# data/ is NOT in the image and must not be (see .dockerignore's argument): it is
# DVC's to pin, and a copy in a layer would be a second unpinned dataset. So the
# host's DVC-pinned tree is mounted READ-ONLY, which also proves the non-root
# user can read it. How data reaches tasks ON-CLUSTER is M4-S4's decision (MinIO
# or a staged PVC) — a bind mount is not that answer and is not offered as one;
# kind extraMounts would need a config edit, which the statefulness law forbids.
MONTH="${SMOKE_MONTH:-2019-01}"
if [[ ! -f "data/processed/train/yellow_tripdata_${MONTH}.parquet" ]]; then
  bad "no processed parquet for $MONTH on the host — 'make data' first (nothing to validate against)"
else
  if validate_out="$(docker run --rm \
        -v "${REPO_ROOT}/data:/app/data:ro" \
        "$IMAGE_REF" python -c "
import pipelines.tasks as tasks
result = tasks.validate('${MONTH}')
print('validate:', result.month, result.rows, 'rows,', 'contract_year', result.contract_year,
      ',', len(result.columns), 'columns')
" 2>&1)"; then
    sed 's/^/     /' <<<"$validate_out"
    if grep -qE 'validate: '"$MONTH"' [0-9]+ rows' <<<"$validate_out"; then
      ok "validate($MONTH) passed the output contract inside the image"
    else
      bad "validate($MONTH) printed something unexpected"
    fi
  else
    sed 's/^/     /' <<<"$validate_out"
    bad "validate($MONTH) failed inside the image"
  fi
fi

# -------------------------------------------- 8. the shim left no trace anywhere
head2 "8. the shim's directory does not exist in the image"
# taxi_mlops.training.openmp._shim_dir() is <repo>/.venv/lib/openmp, created only
# when the shim fires. Its absence after checks 2-7 is the negative evidence
# D-004's row asks for.
trace_out="$(run bash -lc '
test -e /app/.venv/lib/openmp && echo "PRESENT: /app/.venv/lib/openmp" || echo "absent: /app/.venv/lib/openmp"
find /app/.venv -name "libgomp.so.1" -print 2>/dev/null | sed "s/^/venv-soname: /"
echo "vendored copies still shipped by wheels (harmless, unused):"
find /app/.venv -name "libgomp*.so*" -print 2>/dev/null | head -n3
')"
sed 's/^/     /' <<<"$trace_out"
if grep -q '^PRESENT' <<<"$trace_out" || grep -q '^venv-soname' <<<"$trace_out"; then
  bad "the shim left a trace in /app/.venv — it fired at some point"
else
  ok "no shim directory and no libgomp.so.1 SONAME inside the venv"
fi

# ---------------------------------------------------------------------- verdict
echo ""
echo "== verdict ====================================================="
echo "  $PASS ok · $FAILED FAIL"
if (( FAILED > 0 )); then
  echo "RED — the image does not satisfy M4-S3's conditions."
  exit 1
fi
echo "GREEN — $PASS/$PASS checks passed for $IMAGE_REF."
