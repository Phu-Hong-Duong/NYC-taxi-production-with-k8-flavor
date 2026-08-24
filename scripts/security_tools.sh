#!/usr/bin/env bash
# M9-S9 — pin the two scanners this program audits itself with.
#
# trivy (images + filesystem CVEs/misconfig) and gitleaks (secrets, including the
# FULL git history) land as VERSIONED binaries in ~/.local/bin, the same place and
# the same way kind, helm and uv arrived at M0-S1: sudo-free, on the PATH the
# session already has, with the version pinned in this file rather than resolved
# from `latest` at install time. A scanner resolved from `latest` makes every scan
# record un-reproducible for the most boring possible reason.
#
# WHAT THE CHECKSUM CHECK ACTUALLY PROVES, said out loud because the honest answer
# is "less than it looks like". We download the artifact and the publisher's own
# `*_checksums.txt` from the SAME origin over the SAME TLS session. That detects a
# truncated or corrupted download; it is NOT a chain of trust, because anything
# able to serve a tampered tarball can serve a matching checksum line. The real
# pin is the sha256 this script RECORDS: a future run of the same version that
# gets different bytes is a loud mismatch against a tracked file. Upstream ships
# sigstore attestations (`*.sigstore.json`); verifying them needs `cosign`, which
# is a third pinned binary this $0 program is not adding to check two developer
# tools it runs read-only against its own laptop — recorded as a limit, not
# smuggled past as if it were done.
#
# `DRY_RUN=1` resolves, prints and installs nothing (gotcha #30's rule).
# `--check` reads the installed versions back and writes no record.
# `FORCE=1` re-downloads even when the pinned version is already installed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- the pins -----------------------------------------------------------------
# Newest stable at pin time, read live from each project's releases API on
# 2026-08-24 (the Metabase precedent: read the tag list, do not remember it).
TRIVY_VERSION="0.74.0"
GITLEAKS_VERSION="8.30.1"

BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
RECORD="automation/runs/m9-security/tools.json"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"

installed_version() {  # $1 = binary name
  case "$1" in
    trivy)    "$BIN_DIR/trivy" --version 2>/dev/null | head -1 | awk '{print $2}' ;;
    gitleaks) "$BIN_DIR/gitleaks" version 2>/dev/null | tr -d 'v \n' ;;
  esac
}

if [[ "${1:-}" == "--check" ]]; then
  echo "[sec-tools] reading back what is installed in $BIN_DIR"
  for b in trivy gitleaks; do
    if [[ -x "$BIN_DIR/$b" ]]; then
      echo "  ok  $b $(installed_version "$b")"
    else
      echo "  FAIL $b is not installed" >&2
      exit 1
    fi
  done
  exit 0
fi

echo "[sec-tools] pinned: trivy $TRIVY_VERSION · gitleaks $GITLEAKS_VERSION -> $BIN_DIR"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[sec-tools] DRY_RUN=1 — nothing was downloaded, nothing was installed, no record written."
  exit 0
fi

mkdir -p "$BIN_DIR" "$(dirname "$RECORD")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

declare -A SHA256 SOURCE CHECKSUM_OK

fetch_and_install() {  # $1 name  $2 version  $3 tarball  $4 checksums  $5 url_base  $6 member
  local name="$1" version="$2" tar="$3" sums="$4" base="$5" member="$6"

  if [[ -x "$BIN_DIR/$name" && "$(installed_version "$name")" == "$version" && "$FORCE" != "1" ]]; then
    echo "[sec-tools] $name $version already installed — no-op (FORCE=1 re-downloads)"
    SHA256[$name]="$(sha256sum "$BIN_DIR/$name" | awk '{print $1}')"
    SOURCE[$name]="$base/$tar"
    CHECKSUM_OK[$name]="not re-checked (binary already present at the pinned version)"
    return
  fi

  echo "[sec-tools] fetching $name $version"
  curl -fsSL --retry 3 -o "$WORK/$tar"  "$base/$tar"
  curl -fsSL --retry 3 -o "$WORK/$sums" "$base/$sums"

  local want got
  want="$(grep -F " $tar" "$WORK/$sums" | awk '{print $1}' | head -1)"
  got="$(sha256sum "$WORK/$tar" | awk '{print $1}')"
  if [[ -z "$want" ]]; then
    echo "[sec-tools] FAIL: $tar is not listed in $sums — the asset name moved." >&2
    exit 2
  fi
  if [[ "$want" != "$got" ]]; then
    echo "[sec-tools] FAIL: sha256 mismatch for $tar" >&2
    echo "  publisher: $want" >&2
    echo "  downloaded: $got" >&2
    exit 2
  fi
  echo "  ok  $tar matches the publisher's checksums file ($got)"

  tar -xzf "$WORK/$tar" -C "$WORK" "$member"
  install -m 0755 "$WORK/$member" "$BIN_DIR/$name"

  SHA256[$name]="$(sha256sum "$BIN_DIR/$name" | awk '{print $1}')"
  SOURCE[$name]="$base/$tar"
  CHECKSUM_OK[$name]="verified against $sums (same origin, same TLS session)"
}

fetch_and_install trivy "$TRIVY_VERSION" \
  "trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" \
  "trivy_${TRIVY_VERSION}_checksums.txt" \
  "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}" \
  trivy

fetch_and_install gitleaks "$GITLEAKS_VERSION" \
  "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
  "gitleaks_${GITLEAKS_VERSION}_checksums.txt" \
  "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}" \
  gitleaks

# --- read the versions back OFF THE INSTALLED BINARIES ------------------------
# Never off the constants above: the point of a read-back is that it can disagree
# (the deploy_serving.sh idiom — ask the thing, not the values you submitted).
TRIVY_OBSERVED="$(installed_version trivy)"
GITLEAKS_OBSERVED="$(installed_version gitleaks)"
echo "[sec-tools] installed: trivy $TRIVY_OBSERVED · gitleaks $GITLEAKS_OBSERVED"

for pair in "trivy:$TRIVY_VERSION:$TRIVY_OBSERVED" "gitleaks:$GITLEAKS_VERSION:$GITLEAKS_OBSERVED"; do
  IFS=: read -r n want got <<<"$pair"
  if [[ "$want" != "$got" ]]; then
    echo "[sec-tools] FAIL: $n reports $got, the pin says $want" >&2
    exit 2
  fi
done

python3 - "$RECORD" <<PY
import json, subprocess, sys, datetime
record = sys.argv[1]
payload = {
    "story": "M9-S9",
    "recorded_at": datetime.datetime.now(datetime.UTC)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    "bin_dir": "$BIN_DIR",
    "checksum_verification_limit": (
        "the artifact and the publisher's checksums file come from the same origin "
        "over the same TLS session, so a match detects corruption and not tampering; "
        "the sigstore attestations upstream also ships are NOT verified (that needs "
        "cosign, a third pinned binary this program is not adding). The durable pin "
        "is sha256_installed below, recorded in a tracked file."
    ),
    "tools": {
        "trivy": {
            "version": "$TRIVY_OBSERVED",
            "pinned": "$TRIVY_VERSION",
            "sha256_installed": "${SHA256[trivy]}",
            "source": "${SOURCE[trivy]}",
            "checksum": "${CHECKSUM_OK[trivy]}",
        },
        "gitleaks": {
            "version": "$GITLEAKS_OBSERVED",
            "pinned": "$GITLEAKS_VERSION",
            "sha256_installed": "${SHA256[gitleaks]}",
            "source": "${SOURCE[gitleaks]}",
            "checksum": "${CHECKSUM_OK[gitleaks]}",
        },
    },
}
with open(record, "w") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
print(f"[sec-tools] wrote {record}")
PY

echo "[sec-tools] OK — both scanners pinned and recorded."
