#!/usr/bin/env bash
# M9-S13 — install the tracked git hooks into this clone, and read them back.
#
# THE THREE HALVES, AND ONLY TWO OF THEM ARE VERIFIABLE.
#   verifiable   the tracked script exists and says what it says (git holds it)
#   verifiable   this installer copies it and sets the execute bit (tests run it
#                into a temp directory and read the mode back)
#   NOT          that it is installed in YOUR clone. `.git/hooks` is untracked,
#                by git's design and for good reason, so no gate here can see it.
#                `--check` is how you ask; `make security-scan` is the audit of
#                record either way.
#
# THE EXECUTE BIT IS THE WHOLE REASON THIS IS A SCRIPT AND NOT A `cp` IN THE
# README. M8-S4 leg 2 lost a build to exactly this: `COPY` preserves the source's
# 0644, and the failure surfaces as `exec: permission denied` from containerd,
# which reads like a missing binary or a broken PATH. Git records the mode of a
# tracked file, so `scripts/hooks/pre-commit` is 100755 in the index — but a
# `cp` from a tarball, a `curl`, or a checkout on a filesystem that drops the bit
# all produce a hook git silently ignores. Ignored hooks fail SILENTLY: there is
# no error, there is just no scan. So the bit is set explicitly and then READ
# BACK off the installed file (`deploy_serving.sh`'s idiom — never trust the
# thing you just submitted).
#
# It never destroys: a pre-existing hook that is not ours is left alone and named
# (postgres_databases.sh's asymmetry — destroying is somebody's explicit call).
#
# Usage:
#   make install-hooks          # install (or re-install) and read back
#   make install-hooks-check    # answer only: installed? current? executable?
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SRC_DIR="scripts/hooks"
HOOKS=(pre-commit)
# Overridable so the tests can install into a temp directory and read the mode
# back — a test that asserted "the script contains chmod" would pass on a script
# that chmods the wrong file.
DEST_DIR="${HOOKS_DIR:-$(git rev-parse --git-path hooks)}"
FORCE="${FORCE:-0}"
MODE="install"
[[ "${1:-}" == "--check" ]] && MODE="check"

failures=0
say() { printf '[hooks] %s\n' "$*"; }

for hook in "${HOOKS[@]}"; do
  src="$SRC_DIR/$hook"
  dest="$DEST_DIR/$hook"
  [[ -f "$src" ]] || { say "FAIL: $src is missing from this checkout"; exit 2; }
  src_sha="$(sha256sum "$src" | awk '{print $1}')"

  if [[ "$MODE" == "check" ]]; then
    if [[ ! -e "$dest" ]]; then
      say "NOT INSTALLED  $dest — run 'make install-hooks'"
      failures=$((failures + 1))
      continue
    fi
    dest_sha="$(sha256sum "$dest" | awk '{print $1}')"
    if [[ "$dest_sha" != "$src_sha" ]]; then
      say "STALE          $dest differs from $src — run 'make install-hooks'"
      failures=$((failures + 1))
    elif [[ ! -x "$dest" ]]; then
      # The silent-failure case: git skips a non-executable hook without a word,
      # so "the file is there" is not the claim that matters.
      say "NOT EXECUTABLE $dest — git SKIPS it silently. Run 'make install-hooks'"
      failures=$((failures + 1))
    else
      say "ok  $hook installed, current (sha256 ${src_sha:0:12}…) and executable"
    fi
    continue
  fi

  mkdir -p "$DEST_DIR"
  if [[ -e "$dest" ]]; then
    dest_sha="$(sha256sum "$dest" | awk '{print $1}')"
    if [[ "$dest_sha" == "$src_sha" ]]; then
      say "$hook already current — re-setting the execute bit anyway (cheap, idempotent)"
    elif [[ "$FORCE" != "1" ]]; then
      say "REFUSED: $dest exists and is NOT the tracked $src."
      say "         Something else owns your pre-commit hook. Read it, then either"
      say "         merge it by hand or re-run with FORCE=1 to overwrite."
      exit 2
    else
      say "overwriting a DIFFERENT existing $hook (FORCE=1)"
    fi
  fi

  cp "$src" "$dest"
  chmod +x "$dest"

  # Read back, off the installed file, never off what was copied.
  dest_sha="$(sha256sum "$dest" | awk '{print $1}')"
  [[ "$dest_sha" == "$src_sha" ]] || { say "FAIL: $dest does not match $src after copy"; exit 2; }
  [[ -x "$dest" ]] || { say "FAIL: $dest is not executable after chmod +x"; exit 2; }
  say "ok  $hook -> $dest  (sha256 ${dest_sha:0:12}…, mode $(stat -c '%a' "$dest"))"
done

if [[ "$MODE" == "check" ]]; then
  if [[ $failures -eq 0 ]]; then
    say "OK — ${#HOOKS[@]} hook(s) installed and current in this clone."
    exit 0
  fi
  say "$failures hook(s) not installed or not current."
  exit 1
fi

say "Installed into $DEST_DIR — which git does not track, so nothing in this"
say "repository can prove it stayed there. 'make install-hooks-check' asks;"
say "'make security-scan' is the audit of record, hook or no hook."
