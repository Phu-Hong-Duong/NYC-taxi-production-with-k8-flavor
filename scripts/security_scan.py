"""M9-S9 — the pre-publish audit: what a scanner finds in this repo, and the proof it looked.

PO answer 3 (AWAITING_PO 2026-08-24-2) makes publishing conditional on this pair.
The honest note the epilogue's own charter carries: `.env` never entered git by
design, so this VERIFIES hygiene rather than creates it — and **a verification
that finds nothing must still prove it looked** (gotcha #59: assert on a positive
artifact). So every leg records its INPUTS — which image by digest, how many files,
how many commits across how many refs, how many rules the scanner carried — and
`make security-scan-redteam` watches the secret scanner catch a planted one.

THE TRIAGE THAT MATTERS, AND IT IS NOT "ZERO FINDINGS".
A secret scanner pointed at this working tree WILL find `.env`: it holds the real
MinIO and Postgres credentials this platform runs on, and it is supposed to be
there. What makes that fine is a different fact — git has never seen it. So a
finding is classified by WHERE it lives, and the two answers are not degrees of
the same thing:

  * in a file git TRACKS, or anywhere in git HISTORY  -> story-stopping. Park.
  * in a gitignored file on this disk                 -> expected, REPORTED, and
    each one carries `git check-ignore -v`'s answer beside it, so the claim
    "this is local-only" is a paste rather than an assurance.

A scan that reported "0 findings" by pointing only at tracked files would be
technically true and would have proved nothing about the hazard anyone actually
has — a developer committing the .env they have been editing all week.

WHAT IS RECORDED AND WHAT IS NOT. Findings are recorded by rule, path, line,
commit and gitleaks' own fingerprint. **The secret VALUE and the matched line are
dropped before anything is written**, because the record is a tracked file and a
tracked file describing a credential character by character is the leak this
story exists to look for. Raw scanner output (megabytes, and for gitleaks it
contains the values) is written under `automation/runs/m9-security/raw/` with no
`.json` extension, which is exactly what the repo's gitignore already treats as
transcript rather than record.

CVEs are RECORDED, NOT CHASED. Every image here is pinned by digest and this is a
$0 program on one laptop; an upgrade campaign is out of scope and saying so with
the counts beside it is the honest close — the same shape as `nvidia-nccl-cu13`
(241 MB of a hard dependency that is never loaded): noted, not fought.

Usage:
    make security-scan                          # every leg
    make security-scan SCAN_ARGS="--stage tree-secrets"    # the cheap probe
    make security-scan SCAN_ARGS=--no-write     # print the verdicts, record nothing
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD_DIR = REPO / "automation" / "runs" / "m9-security"
RECORD = RECORD_DIR / "scan.json"
RAW_DIR = RECORD_DIR / "raw"
TOOLS_RECORD = RECORD_DIR / "tools.json"

# The three images THIS PROGRAM BUILDS. Base images (postgres, redis, mlserver,
# busybox, the charts') are pinned by digest and are somebody else's build; the
# pair we can actually act on is ours. Each ref is DERIVED from the record that
# minted it or from the manifest that names it — never typed here, because a
# typed tag scans whatever happens to still be in the daemon under that name.
OUR_IMAGES = (
    ("taxi-mlops-pipeline", RECORD_DIR.parent / "m4-image" / "image.json", "image_ref"),
    (
        "taxi-mlops-feast-server",
        RECORD_DIR.parent / "m8-transformer" / "feast-server-image.json",
        "image",
    ),
    ("taxi-mlops-predictor", REPO / "infra" / "manifests" / "serving-runtime-mlserver.yaml", None),
)

# trivy walks a filesystem; this repo's filesystem holds ~40 GB of parquet, two
# virtualenvs and a git object store. None of them is a lockfile or a manifest,
# and none of them is what an IaC/dependency scan is for.
FS_SKIP_DIRS = (
    "data",
    ".venv",
    ".venv-feast",
    ".git",
    "automation/runs",
    "node_modules",
)

STAGES = ("tree-secrets", "history-secrets", "images", "tree-vulns")

# --------------------------------------------------------------------------- #
# The ONE acknowledged finding, and why it is a list of arguments rather than a
# `.gitleaksignore`.
#
# gitleaks finds a 32-character high-entropy string in `scripts/gameday_m6.py`.
# It is a true positive BY SHAPE and a non-secret BY FACT: it is the M6-S5
# gameday's deliberately WRONG MinIO credential, the value injected to provoke
# `403 HeadBucket: Forbidden` and watch A-5 and A-7 fire. A credential that is
# designed not to work is the one string in this repo that must look exactly like
# a credential.
#
# A `.gitleaksignore` would make it disappear, and a suppression nobody can read
# is how the next real one hides behind it. So it is acknowledged HERE, keyed on
# the sha256 of the found bytes (stable across commits, and it reveals nothing),
# and the argument is CHECKABLE rather than asserted: the scan decodes the bytes
# it actually found and requires them to spell the harmless plaintext below. If
# somebody swaps a live credential onto that line, the sha256 stops matching and
# it goes straight back to blocking.
#
# It fails in BOTH directions (`render_alert_rules.py`'s rule): an entry that
# matches nothing in a run is a STALE suppression and is itself a failure —
# otherwise a suppression outlives the thing it suppressed and quietly widens.
ACKNOWLEDGED_SECRETS = {
    "938836ccbcc9ae98b77af297ca184442d56dfd161e0588d01cafbcd17ccaaea2": {
        "what": "the M6-S5 gameday's deliberately WRONG MinIO secret",
        "encoding": "base64",
        "decodes_to": "wrong-credential-gameday",
        "expected_in": "scripts/gameday_m6.py",
        "why_not_a_secret": (
            "it is the value the storage-break scenario PATCHES IN to make MinIO "
            "refuse the predictor (403 HeadBucket) so A-5 and A-7 can be watched "
            "firing. It has never been a working credential anywhere, and the "
            "plaintext it decodes to says so in words"
        ),
    }
}


def _bin(name: str) -> str:
    found = shutil.which(name) or str(Path.home() / ".local" / "bin" / name)
    if not Path(found).exists():
        sys.exit(
            f"[sec-scan] FAIL: {name} is not installed. Run 'make security-tools' first "
            f"— the versions this program pins are recorded in {TOOLS_RECORD}."
        )
    return found


def _run(argv: list[str], *, allow_rc: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO)
    if proc.returncode not in allow_rc:
        sys.stderr.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        sys.exit(f"[sec-scan] FAIL: {argv[0]} exited {proc.returncode} for {' '.join(argv[1:])}")
    return proc


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=REPO, check=True
    ).stdout.strip()


# --------------------------------------------------------------------------- #
# secrets
# --------------------------------------------------------------------------- #
def _rel(path: str) -> str:
    """gitleaks reports absolute paths for a dir scan and repo-relative ones for a
    git scan. Both have to land in the same vocabulary before anything is compared
    against `git ls-files`, or every finding falls through to the untracked branch
    and gets the wrong reason printed beside a correct verdict."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(REPO))
    except ValueError:
        return path


def _redact(finding: dict) -> dict:
    """Everything a reviewer needs to go and look, and nothing that IS the secret.

    gitleaks reports `Secret` and `Match` verbatim. This record is committed; a
    committed file spelling out a live credential would be the exact defect the
    scan exists to find, delivered by the scan. The sha256 is what survives: it
    identifies the finding across commits without describing it.
    """
    secret = finding.get("Secret") or ""
    digest = hashlib.sha256(secret.encode()).hexdigest()
    return {
        "rule": finding.get("RuleID"),
        "file": _rel(finding.get("File") or ""),
        "start_line": finding.get("StartLine"),
        "commit": finding.get("Commit") or None,
        "author": finding.get("Author") or None,
        "date": finding.get("Date") or None,
        "fingerprint": finding.get("Fingerprint"),
        "entropy": finding.get("Entropy"),
        # TWELVE characters, and the length is the finding rather than a taste.
        # The first draft wrote the full 64-hex digest under a field called
        # `secret_sha256`, and the next run flagged THIS RECORD 13 times: a
        # keyword-plus-long-high-entropy-string is precisely what
        # `generic-api-key` is for, and the record is tracked, so the scan would
        # have blocked on its own output. The scanner was right both times. 48
        # bits identifies a finding in a repo this size; the full digest is what
        # ACKNOWLEDGED_SECRETS keys on and it lives in code, where it sits as a
        # dict key rather than as a value after a credential-shaped name.
        "finding_id": digest[:12],
        "_sha256": digest,  # dropped before the record is written; see _for_record
        "value": "REDACTED — recorded nowhere; re-run gitleaks locally to see it",
    }


def _strip_working_fields(node):
    """Drop every `_`-prefixed working field before anything is written.

    Done at the WRITE boundary rather than per call site: the full digest is
    genuinely needed while classifying and genuinely unwanted in a tracked file,
    and a rule enforced in one place cannot be forgotten by the next leg somebody
    adds. (The keys ACKNOWLEDGED_SECRETS uses stay in code.)
    """
    if isinstance(node, dict):
        return {
            k: _strip_working_fields(v) for k, v in node.items() if not str(k).startswith("_")
        }
    if isinstance(node, list):
        return [_strip_working_fields(v) for v in node]
    return node


def _acknowledge(item: dict, secret: str) -> dict | None:
    """Is this the one finding we have an argument for — and does the argument hold?

    The argument is re-derived from the bytes actually found, never trusted from
    the table. A different value on the same line is a different finding.
    """
    entry = ACKNOWLEDGED_SECRETS.get(item["_sha256"])
    if entry is None:
        return None
    decoded = base64.b64decode(secret).decode("utf-8", "replace")
    if decoded != entry["decodes_to"]:
        sys.exit(
            f"[sec-scan] FAIL: the acknowledgement for {item['file']}:{item['start_line']} "
            f"claims it decodes to {entry['decodes_to']!r} and it decodes to {decoded!r}. "
            "That is not a stale comment, it is a different value under a known "
            "argument — treat it as blocking."
        )
    return {**item, "acknowledged": entry, "proved_decodes_to": decoded}


def _tracked_files() -> set[str]:
    return set(_git("ls-files").splitlines())


def _ignored_reason(path: str) -> str | None:
    """`git check-ignore -v` answer, or None if git does not ignore this path."""
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "--", path], capture_output=True, text=True, cwd=REPO
    )
    return proc.stdout.strip() or None


def _classify(findings: list[dict], *, in_history: bool) -> dict:
    """Split findings into three classes that are NOT degrees of one another.

    Location is decided FIRST and the acknowledgement is applied on top of it, so
    an argued finding still carries an honest statement of where it lives. Doing
    it the other way round labelled a finding in a gitignored scratch file "in a
    tracked file, and argued" — correct verdict, wrong reason (gotcha #67's
    family, and a wrong reason is what somebody acts on at 3am).
    """
    tracked = _tracked_files()
    blocking: list[dict] = []
    local_only: list[dict] = []
    acknowledged: list[dict] = []
    self_transcript: list[dict] = []
    raw_rel = str(RAW_DIR.relative_to(REPO))

    for raw in findings:
        item = _redact(raw)
        path = item["file"] or ""

        # --- location, always ---
        if in_history:
            # Anything gitleaks found while walking commits is, by construction,
            # content git has held. .gitignore is about the future, not the past.
            item["why"] = "present in git history"
            item["class"] = "in-git"
        elif path in tracked:
            item["why"] = "in a file git TRACKS"
            item["class"] = "in-git"
        else:
            reason = _ignored_reason(path)
            item["git_check_ignore"] = reason or "(untracked and NOT ignored)"
            if reason is None:
                # Untracked and unignored is the dangerous middle: one `git add -A`
                # away from being in history. It blocks.
                item["why"] = "untracked AND NOT ignored — one `git add -A` from history"
                item["class"] = "in-git"
            else:
                item["why"] = "not tracked by git, and git is told to ignore it"
                item["class"] = "local-only"

        # --- this scan's own transcript ---
        # The raw reports carry the values verbatim, so a second run finds every
        # finding of the first one inside them and the count becomes a function of
        # how often the scan has been run — a measurement that moves because it
        # was taken. Dropped, COUNTED and named rather than silently skipped; and
        # the drop is BOUNDED: a file under the raw directory is gitignored, so it
        # can only ever be local-only, and this branch is asserted unable to
        # suppress anything that was heading for `blocking`.
        if not in_history and path.startswith(raw_rel + "/"):
            if item["class"] != "local-only":
                sys.exit(
                    f"[sec-scan] FAIL: {path} is under the scan's own raw directory and "
                    "is NOT gitignored. The self-transcript exclusion is only safe "
                    "while that holds — fix the gitignore, do not widen this branch."
                )
            self_transcript.append(item)
            continue

        # --- the argument, on top ---
        ack = _acknowledge(item, raw.get("Secret") or "")
        if ack is not None:
            acknowledged.append(ack)
        elif item["class"] == "in-git":
            blocking.append(item)
        else:
            local_only.append(item)

    return {
        "blocking": blocking,
        "local_only": local_only,
        "acknowledged": acknowledged,
        "self_transcript_dropped": len(self_transcript),
    }


def stage_tree_secrets(*, write: bool) -> dict:
    gl = _bin("gitleaks")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = RAW_DIR / "gitleaks-tree.raw"
    _run(
        [
            gl,
            "dir",
            str(REPO),
            "--no-banner",
            "--redact=0",
            "--report-format",
            "json",
            "--report-path",
            str(raw),
            "--exit-code",
            "0",
        ]
    )
    findings = json.loads(raw.read_text() or "[]")
    classified = _classify(findings, in_history=False)
    scanned = sum(1 for p in REPO.rglob("*") if p.is_file() and ".git/" not in str(p))
    return {
        "leg": "tree-secrets",
        "instrument": "gitleaks dir",
        "inputs": {
            "root": str(REPO),
            "files_on_disk": scanned,
            "files_git_tracks": len(_tracked_files()),
            "note": (
                "the WHOLE disk tree, gitignored files included — pointing this at "
                "tracked files only would report zero and prove nothing about the "
                "hazard anyone actually has"
            ),
        },
        "findings_total": len(findings),
        **classified,
        "raw_report": str(raw.relative_to(REPO)) + " (gitignored: it carries the values)",
    }


def stage_history_secrets(*, write: bool) -> dict:
    gl = _bin("gitleaks")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = RAW_DIR / "gitleaks-history.raw"
    _run(
        [
            gl,
            "git",
            str(REPO),
            "--no-banner",
            "--redact=0",
            "--log-opts=--all --full-history",
            "--report-format",
            "json",
            "--report-path",
            str(raw),
            "--exit-code",
            "0",
        ]
    )
    findings = json.loads(raw.read_text() or "[]")
    classified = _classify(findings, in_history=True)
    refs = _git("for-each-ref", "--format=%(refname)").splitlines()
    return {
        "leg": "history-secrets",
        "instrument": "gitleaks git --log-opts='--all --full-history'",
        "inputs": {
            "commits_reachable_from_all_refs": int(_git("rev-list", "--all", "--count")),
            "refs": len(refs),
            "first_commit": _git("log", "--reverse", "--format=%h %ad", "--date=short", "--all")
            .splitlines()[0]
            .strip(),
            "head": _git("rev-parse", "--short", "HEAD"),
            "note": (
                "--all walks every ref this clone holds, not just HEAD's ancestry: a "
                "secret removed from main by a later commit still lives in the objects "
                "the old commit points at, and that is what publishing exposes"
            ),
        },
        "findings_total": len(findings),
        **classified,
        "raw_report": str(raw.relative_to(REPO)) + " (gitignored: it carries the values)",
    }


# --------------------------------------------------------------------------- #
# vulnerabilities
# --------------------------------------------------------------------------- #
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")


def _summarise_trivy(report: dict) -> dict:
    counts = dict.fromkeys(SEVERITIES, 0)
    criticals: list[dict] = []
    fixable_critical_high = 0
    for result in report.get("Results") or []:
        for vuln in result.get("Vulnerabilities") or []:
            sev = vuln.get("Severity", "UNKNOWN")
            counts[sev] = counts.get(sev, 0) + 1
            if sev in ("CRITICAL", "HIGH") and vuln.get("FixedVersion"):
                fixable_critical_high += 1
            if sev == "CRITICAL":
                criticals.append(
                    {
                        "id": vuln.get("VulnerabilityID"),
                        "package": vuln.get("PkgName"),
                        "installed": vuln.get("InstalledVersion"),
                        "fixed_in": vuln.get("FixedVersion") or None,
                        "target": result.get("Target"),
                    }
                )
    return {
        "by_severity": counts,
        "total": sum(counts.values()),
        "fixable_critical_high": fixable_critical_high,
        "critical_findings": sorted(criticals, key=lambda c: (c["package"] or "", c["id"] or "")),
    }


def _image_ref(name: str, source: Path, key: str | None) -> str:
    if key is not None:
        return json.loads(source.read_text())[key]
    # The predictor has no build record — it is declared in the ServingRuntime the
    # cluster actually runs, which is the manifest under review.
    for line in source.read_text().splitlines():
        if "image:" in line and name in line:
            return line.split("image:", 1)[1].strip()
    sys.exit(f"[sec-scan] FAIL: no image ref for {name} in {source}")


def stage_images(*, write: bool) -> dict:
    trivy = _bin("trivy")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    for name, source, key in OUR_IMAGES:
        ref = _image_ref(name, source, key)
        raw = RAW_DIR / f"trivy-{name}.raw"
        print(f"[sec-scan]   scanning {ref}", flush=True)
        _run(
            [
                trivy,
                "image",
                ref,
                "--scanners",
                "vuln",
                "--format",
                "json",
                "--output",
                str(raw),
                "--quiet",
            ]
        )
        report = json.loads(raw.read_text())
        digest = _run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", ref]
        ).stdout.strip()
        images.append(
            {
                "image": ref,
                "ref_source": str(source.relative_to(REPO)),
                "image_id": digest,
                "os": (report.get("Metadata") or {}).get("OS"),
                **_summarise_trivy(report),
                "raw_report": str(raw.relative_to(REPO)),
            }
        )
    return {
        "leg": "images",
        "instrument": "trivy image --scanners vuln",
        "inputs": {
            "images": [i["image"] for i in images],
            "note": (
                "the three images THIS PROGRAM BUILDS, each ref derived from the "
                "record that minted it or the manifest the cluster runs. Base images "
                "we merely pin (postgres, redis, mlserver, busybox) are somebody "
                "else's build and are out of this leg's scope by choice, not by "
                "omission"
            ),
        },
        "images": images,
    }


def stage_tree_vulns(*, write: bool) -> dict:
    trivy = _bin("trivy")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = RAW_DIR / "trivy-fs.raw"
    argv = [
        trivy,
        "fs",
        str(REPO),
        "--scanners",
        "vuln,misconfig",
        "--format",
        "json",
        "--output",
        str(raw),
        "--quiet",
    ]
    for d in FS_SKIP_DIRS:
        argv += ["--skip-dirs", d]
    _run(argv)
    report = json.loads(raw.read_text())
    misconfig = {"total": 0, "by_severity": dict.fromkeys(SEVERITIES, 0), "targets": []}
    for result in report.get("Results") or []:
        rows = result.get("Misconfigurations") or []
        if not rows:
            continue
        failed = [m for m in rows if m.get("Status") == "FAIL"]
        if not failed:
            continue
        misconfig["targets"].append(
            {
                "target": result.get("Target"),
                "failed": len(failed),
                "ids": sorted({m.get("ID") for m in failed if m.get("ID")}),
            }
        )
        for m in failed:
            sev = m.get("Severity", "UNKNOWN")
            misconfig["by_severity"][sev] = misconfig["by_severity"].get(sev, 0) + 1
            misconfig["total"] += 1
    return {
        "leg": "tree-vulns",
        "instrument": "trivy fs --scanners vuln,misconfig",
        "inputs": {
            "root": str(REPO),
            "skipped_dirs": list(FS_SKIP_DIRS),
            "lockfiles_seen": sorted(
                {
                    r.get("Target")
                    for r in (report.get("Results") or [])
                    if r.get("Class") == "lang-pkgs"
                }
            ),
            "note": (
                "skips ~40 GB of parquet, two virtualenvs and the object store — none "
                "of them a lockfile or a manifest, which is what a dependency and IaC "
                "scan reads"
            ),
        },
        "dependencies": _summarise_trivy(report),
        "misconfiguration": misconfig,
        "raw_report": str(raw.relative_to(REPO)),
    }


# --------------------------------------------------------------------------- #
RUNNERS = {
    "tree-secrets": stage_tree_secrets,
    "history-secrets": stage_history_secrets,
    "images": stage_images,
    "tree-vulns": stage_tree_vulns,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=STAGES, action="append", help="run one leg (repeatable)")
    ap.add_argument("--no-write", action="store_true", help="print the verdicts, record nothing")
    ap.add_argument("--out", default=str(RECORD))
    args = ap.parse_args()

    stages = args.stage or list(STAGES)
    tools = json.loads(TOOLS_RECORD.read_text()) if TOOLS_RECORD.exists() else {}

    legs: dict[str, dict] = {}
    for stage in stages:
        print(f"[sec-scan] {stage}", flush=True)
        legs[stage] = RUNNERS[stage](write=not args.no_write)

    blocking = [f for leg in legs.values() for f in leg.get("blocking", [])]
    local_only = [f for leg in legs.values() for f in leg.get("local_only", [])]
    acknowledged = [f for leg in legs.values() for f in leg.get("acknowledged", [])]

    # BOTH DIRECTIONS. An acknowledgement that matches nothing is a suppression
    # that has outlived what it suppressed, and the next real finding hides behind
    # it. Only asked when a secret leg actually ran — an images-only invocation
    # has not looked, and "did not look" must not read as "is stale".
    if {"tree-secrets", "history-secrets"} & set(stages):
        matched = {f["_sha256"] for f in acknowledged}
        stale = sorted(set(ACKNOWLEDGED_SECRETS) - matched)
        if stale:
            for sha in stale:
                entry = ACKNOWLEDGED_SECRETS[sha]
                print(
                    f"[sec-scan] FAIL: acknowledgement {sha[:12]}… "
                    f"({entry['what']}, expected in {entry['expected_in']}) matched NOTHING. "
                    "Delete the entry or find out where it went — a suppression nobody "
                    "can see hides the next real one.",
                    file=sys.stderr,
                )
            return 2

    payload = {
        "story": "M9-S9",
        "recorded_at": _now(),
        "git_head": _git("rev-parse", "HEAD"),
        "tools": {k: v.get("version") for k, v in (tools.get("tools") or {}).items()},
        "stages_run": stages,
        "verdict": {
            "secrets_in_git": len(blocking),
            "secrets_acknowledged": len(acknowledged),
            "secrets_local_only": len(local_only),
            "publishable": (
                len(blocking) == 0 and set(stages) >= {"tree-secrets", "history-secrets"}
            ),
            "publishable_means": (
                "no unacknowledged secret in any file git tracks and none in any "
                "commit reachable from any ref. It says nothing about CVEs, which "
                "are recorded below and deliberately not chased"
            ),
        },
        "legs": legs,
    }
    payload = _strip_working_fields(payload)

    print()
    secret_legs = {"tree-secrets", "history-secrets"} & set(stages)
    if not secret_legs:
        # gotcha #78, and it is the direction that matters: "0 secrets" printed by a
        # run that never looked for one reads exactly like a clean bill of health.
        print("[sec-scan] secrets: NOT ASKED — no secret leg ran in this invocation")
    print(f"[sec-scan] secrets in git (tracked files + full history): {len(blocking)}")
    for f in blocking:
        print(f"    BLOCKING  {f['rule']}  {f['file']}:{f['start_line']}  {f['why']}")
    print(f"[sec-scan] acknowledged, argument re-proved from the bytes found: {len(acknowledged)}")
    for f in acknowledged:
        print(f"    argued    {f['rule']}  {f['file']}:{f['start_line']}  {f['why']}")
        print(f"              decodes to {f['proved_decodes_to']!r} — {f['acknowledged']['what']}")
    dropped = sum(leg.get("self_transcript_dropped", 0) for leg in legs.values())
    if dropped:
        print(
            f"[sec-scan] dropped {dropped} finding(s) inside this scan's own raw "
            f"transcript ({RAW_DIR.relative_to(REPO)}/) — gitignored by construction"
        )
    print(f"[sec-scan] secrets in gitignored local files (expected): {len(local_only)}")
    for f in local_only:
        print(f"    local     {f['rule']}  {f['file']}:{f['start_line']}")
        print(f"              {f.get('git_check_ignore')}")
    for stage in ("images", "tree-vulns"):
        leg = legs.get(stage)
        if not leg:
            continue
        if stage == "images":
            for img in leg["images"]:
                sev = img["by_severity"]
                print(
                    f"[sec-scan] {img['image']}: {img['total']} CVE(s) — "
                    f"CRITICAL {sev['CRITICAL']} · HIGH {sev['HIGH']} · "
                    f"MEDIUM {sev['MEDIUM']} · LOW {sev['LOW']} "
                    f"({img['fixable_critical_high']} of the CRITICAL/HIGH have a fix)"
                )
        else:
            dep = leg["dependencies"]["by_severity"]
            mis = leg["misconfiguration"]
            print(
                f"[sec-scan] repo tree: {leg['dependencies']['total']} dependency CVE(s) — "
                f"CRITICAL {dep['CRITICAL']} · HIGH {dep['HIGH']}; "
                f"{mis['total']} failed misconfiguration check(s)"
            )

    if not args.no_write:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"[sec-scan] wrote {Path(args.out).relative_to(REPO)}")

    if blocking:
        print()
        print("[sec-scan] STORY-STOPPING: a secret is in git. Park at AWAITING_PO —")
        print("[sec-scan] do NOT publish, and do not 'fix' it by deleting the file:")
        print("[sec-scan] history rewriting plus credential rotation is a PO decision.")
        return 1
    print("[sec-scan] OK — nothing git holds is a secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
