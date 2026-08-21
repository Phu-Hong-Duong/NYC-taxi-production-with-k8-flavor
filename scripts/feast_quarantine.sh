#!/usr/bin/env bash
# Build the Feast quarantine, prove it is one, and record what it holds. (M8-S2)
#
# THE WALL, measured rather than feared (M8 law 4): feast 0.66.0 declares
# `pandas<3,>=1.4.3` and this project runs pandas 3.0.5. There is no resolution
# that satisfies both, so there is no `uv add feast` in this repository and never
# will be — the isolated interpreter IS the design. gotcha #16's quarantine, and
# the M7-S3 Evidently probe idiom taken one step further: Evidently could be
# adopted, so it was; Feast cannot be, so it is not.
#
# The strongest thing this script does is REFUSE. Its exit invariant is that
# `uv.lock` is byte-identical across the run — checked by sha256 before and after,
# and a difference aborts. A quarantine that quietly re-resolved the project's own
# graph would be the exact failure it exists to prevent (gotcha #36: an unbounded
# `uv add mlflow` once silently landed a version two majors behind the server).
#
#   bash scripts/feast_quarantine.sh              build + verify + record
#   bash scripts/feast_quarantine.sh --resolve    re-resolve and REWRITE the pin file
#   bash scripts/feast_quarantine.sh --check      verify + record, build nothing
#
# It touches no cluster, no registry, no alias and no data tree.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV=".venv-feast"
PINS="infra/feast/requirements-feast.txt"
# The `[redis]` extra is M8-S4's: the ONLINE store is an in-cluster Redis
# (ADR-012), and feast's redis driver raises at config load without the `redis`
# and `hiredis` distributions. It is declared HERE, in the resolver's input, so a
# future `--resolve` produces the set the pin file already holds rather than
# silently dropping two lines somebody added by hand.
FEAST_PIN="feast[redis]==0.66.0"
RECORD_DIR="automation/runs/m8-feast"
RECORD="$RECORD_DIR/probe.json"
REPO_DIR="infra/feast/feature_repo"

MODE="build"
case "${1:-}" in
  --resolve) MODE="resolve" ;;
  --check)   MODE="check" ;;
  "")        ;;
  *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

LOCK_BEFORE="$(sha256sum uv.lock | cut -d' ' -f1)"
echo "[quarantine] uv.lock before: $LOCK_BEFORE"

if [[ "$MODE" == "resolve" ]]; then
  echo "[quarantine] RE-RESOLVING $FEAST_PIN into a fresh venv — the pin file will be rewritten"
  rm -rf "$VENV"
  uv venv "$VENV" --python 3.12
  uv pip install --python "$VENV" "$FEAST_PIN"
  uv run python scripts/feast_probe_record.py --rewrite-pins
elif [[ "$MODE" == "build" ]]; then
  if [[ ! -x "$VENV/bin/feast" ]]; then
    echo "[quarantine] building $VENV from $PINS (exact pins — no resolution)"
    uv venv "$VENV" --python 3.12
    # `--no-deps` is deliberate: the pin file is the COMPLETE transitive set, so
    # asking the resolver again would let a fresh sdist metadata read change the
    # answer. The file is the lock; this line is its installer.
    uv pip install --python "$VENV" --no-deps -r "$PINS"
  else
    echo "[quarantine] $VENV already exists — reusing it (idempotent)"
  fi
fi

LOCK_AFTER="$(sha256sum uv.lock | cut -d' ' -f1)"
echo "[quarantine] uv.lock after : $LOCK_AFTER"
if [[ "$LOCK_BEFORE" != "$LOCK_AFTER" ]]; then
  echo "[quarantine] FAIL — uv.lock changed. The quarantine reached the project graph." >&2
  exit 1
fi
echo "[quarantine] ok  uv.lock byte-identical across the run"

echo "[quarantine] the two sides of the wall:"
uv run python -c "import pandas; print(f'[quarantine]   project    pandas {pandas.__version__}')"
uv run --no-project --python "$VENV/bin/python" python -c \
  "import pandas, feast; print(f'[quarantine]   quarantine pandas {pandas.__version__}  feast {feast.__version__}')"

# The project graph must not contain feast. `uv pip list` on the project env is
# the direct question, and it is asked rather than assumed.
if uv pip list 2>/dev/null | grep -qiE '^feast[[:space:]]'; then
  echo "[quarantine] FAIL — feast is present in the PROJECT environment." >&2
  exit 1
fi
echo "[quarantine] ok  feast absent from the project environment"

mkdir -p "$RECORD_DIR"
uv run python scripts/feast_probe_record.py --out "$RECORD" \
  --venv "$VENV" --pins "$PINS" --repo-dir "$REPO_DIR" --lock-sha "$LOCK_AFTER"

echo "[quarantine] record: $RECORD"
