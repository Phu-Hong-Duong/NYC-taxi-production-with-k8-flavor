#!/usr/bin/env bash
# The M1 gate's byte-identical rebuild, as a command anyone can re-run (M1-S2).
#
# The claim under test: `data/processed/` is a PURE FUNCTION of DVC-pinned raw
# bytes plus this repo. Not "close enough" — the same sha256, file by file.
#
#   1. record the sha256 of every processed output
#   2. prove the INPUT is the pinned bytes: `dvc status data/raw.dvc` must be
#      clean. Per gotcha #6 the proof pins RAW and rebuilds PROCESSED; TLC
#      backfills months in place, so a re-download is never trusted to be
#      byte-identical and is never part of this proof.
#   3. delete data/processed/ entirely
#   4. rebuild with ONE command (`make data`), with SKIP_DVC=1 so the pin is not
#      refreshed underneath the thing it is checking
#   5. diff the sha256 table, and independently ask DVC (`dvc status
#      data/processed.dvc`) whether the directory it pinned came back
#
# Two witnesses on purpose: our own hashes, and DVC's, computed by different
# code from different metadata. One of them agreeing with itself proves nothing.
#
# Exit 1 on ANY mismatch, a missing file, or drifted raw. This deletes and
# rebuilds ~1 GB; DRY_RUN=1 prints the plan and deletes nothing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BEFORE="$(mktemp)"
AFTER="$(mktemp)"
trap 'rm -f "$BEFORE" "$AFTER"' EXIT

hash_processed() {
  uv run python - "$1" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path("data/processed")
out = []
for p in sorted(root.rglob("*.parquet")):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    out.append(f"{p.relative_to(root)} {h.hexdigest()} {p.stat().st_size}")
pathlib.Path(sys.argv[1]).write_text("\n".join(out) + "\n")
print(f"[rebuild-proof] hashed {len(out)} processed parquet file(s)")
PY
}

echo "[rebuild-proof] 1/5 hashing the current outputs"
hash_processed "$BEFORE"
if [[ ! -s "$BEFORE" ]]; then
  echo "[rebuild-proof] FAIL: nothing in data/processed to prove anything about." >&2
  exit 1
fi

echo "[rebuild-proof] 2/5 the INPUT must be the pinned bytes"
if ! raw_status="$(uv run dvc status data/raw.dvc 2>&1)"; then
  echo "[rebuild-proof] FAIL: dvc status errored:" >&2
  echo "$raw_status" >&2
  exit 1
fi
if ! grep -q "up to date" <<<"$raw_status"; then
  echo "[rebuild-proof] FAIL: data/raw does not match its DVC pin — the rebuild would" >&2
  echo "                start from different bytes and prove nothing (gotcha #6):" >&2
  echo "$raw_status" >&2
  exit 1
fi
echo "  data/raw.dvc: $raw_status"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[rebuild-proof] DRY_RUN=1 — WOULD delete data/processed and re-run 'SKIP_DVC=1 make data'."
  echo "[rebuild-proof] nothing deleted, nothing rebuilt."
  exit 0
fi

echo "[rebuild-proof] 3/5 deleting data/processed"
rm -rf "${REPO_ROOT:?}/data/processed"
test ! -e data/processed && echo "  data/processed: gone"

echo "[rebuild-proof] 4/5 rebuilding with ONE command: SKIP_DVC=1 make data"
SKIP_DVC=1 make data

echo
echo "[rebuild-proof] 5/5 comparing"
hash_processed "$AFTER"

uv run python - "$BEFORE" "$AFTER" <<'PY'
import pathlib, sys

def read(path):
    rows = {}
    for line in pathlib.Path(path).read_text().splitlines():
        name, digest, size = line.rsplit(" ", 2)
        rows[name] = (digest, int(size))
    return rows

before, after = read(sys.argv[1]), read(sys.argv[2])
names = sorted(set(before) | set(after))
width = max(len(n) for n in names)
print(f"  {'output'.ljust(width)}  sha256 before     sha256 after      bytes         identical")
print(f"  {'-' * width}  ----------------  ----------------  ------------  ---------")
ok = True
for n in names:
    b, a = before.get(n), after.get(n)
    same = b is not None and a is not None and b[0] == a[0]
    ok &= same
    bs = b[0][:16] if b else "(absent)".ljust(16)
    as_ = a[0][:16] if a else "(absent)".ljust(16)
    size = f"{(a or b)[1]:,}"
    print(f"  {n.ljust(width)}  {bs}  {as_}  {size:>12}  {'yes' if same else 'NO':>9}")
print(f"\n[rebuild-proof] {len(names)} output(s), all byte-identical: {ok}")
sys.exit(0 if ok else 1)
PY

echo
echo "[rebuild-proof] second witness — DVC's own view of data/processed:"
proc_status="$(uv run dvc status data/processed.dvc 2>&1)"
echo "  $proc_status"
if ! grep -q "up to date" <<<"$proc_status"; then
  echo "[rebuild-proof] FAIL: our hashes matched but DVC says the directory changed." >&2
  exit 1
fi
echo "[rebuild-proof] GREEN — wiped, rebuilt by one command, byte-identical by two witnesses."
