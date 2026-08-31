"""The pre-publish audit's own laws — M9-S9.

The scan's expected answer is "nothing", which is also what a broken scanner
says. So these tests are almost entirely about the SCANNER and its record rather
than about the verdict:

1. **The one acknowledged finding is self-proving offline.** The table keys on the
   sha256 of the found bytes and claims a plaintext; encoding that plaintext and
   hashing it has to reproduce the key. A comment claiming a value is harmless is
   an assurance; this is a derivation, and it needs neither gitleaks nor a clone
   with the file still in it.
2. **The record carries no long high-entropy string.** The first draft wrote the
   full 64-hex digest under a field called `secret_sha256` and the next scan
   flagged its own tracked record thirteen times. The scanner was right; the fix
   was the artifact. This pins it so the field cannot grow back.
3. **The record never carries a working field.** `_`-prefixed keys are stripped at
   the write boundary; a leg added later must not be able to leak one.
4. **The scan is a READER** — it may inspect a docker image, and it may not run a
   verb that changes anything, asked of the AST rather than of the prose (this
   file's subject argues its own design at length; #53/#68/#99).
5. **The red team never writes the record it tests.** A drill that rewrote the
   tracked verdict with its own tampered run would be planting evidence.
6. **The pins and the record are twins**, and the record is the read-back.
7. **The image refs are DERIVED**, never typed — the record's refs must equal what
   the sources it names say today.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import re

import pytest
from conftest import REPO, read_record

SCANNER = REPO / "scripts" / "security_scan.py"
REDTEAM = REPO / "scripts" / "security_scan_redteam.sh"
TOOLS_SH = REPO / "scripts" / "security_tools.sh"
# Spelled in full rather than joined off a directory constant: F-047's marker guard
# resolves a record constant from the SOURCE of its assignment, and a name built
# from another name reads to it as an ordinary path. Naming the record here is
# also what makes the `needs_records` markers below self-explaining.
SCAN_RECORD = REPO / "automation/runs/m9-security/scan.json"
TOOLS_RECORD = REPO / "automation/runs/m9-security/tools.json"


def _module():
    spec = importlib.util.spec_from_file_location("security_scan", SCANNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 1. the acknowledgement proves itself, with no scanner and no clone
# --------------------------------------------------------------------------- #
def test_every_acknowledgement_reproduces_its_own_key():
    mod = _module()
    assert mod.ACKNOWLEDGED_SECRETS, "the table may be empty, but not by accident"
    for digest, entry in mod.ACKNOWLEDGED_SECRETS.items():
        assert entry["encoding"] == "base64", "the only encoding this check can re-derive"
        encoded = base64.b64encode(entry["decodes_to"].encode()).decode()
        assert hashlib.sha256(encoded.encode()).hexdigest() == digest, (
            f"the acknowledgement for {entry['expected_in']} claims the bytes decode to "
            f"{entry['decodes_to']!r}, but encoding that does not produce the sha256 it "
            "is filed under. The argument and the thing it argues about have parted."
        )


def test_every_acknowledgement_carries_an_argument_and_a_place():
    mod = _module()
    for entry in mod.ACKNOWLEDGED_SECRETS.values():
        for field in ("what", "decodes_to", "expected_in", "why_not_a_secret"):
            assert entry.get(field), f"an acknowledgement with no {field} is a suppression"
        assert (REPO / entry["expected_in"]).exists(), (
            f"{entry['expected_in']} is gone — the acknowledgement outlived the file it "
            "argues about, which is the stale-suppression case the scan fails on"
        )
        assert len(entry["why_not_a_secret"]) > 60, "the reason has to be a reason"


def test_the_acknowledged_value_is_still_in_the_file_it_names():
    """The offline half of the scan's both-directions rule."""
    mod = _module()
    for entry in mod.ACKNOWLEDGED_SECRETS.values():
        encoded = base64.b64encode(entry["decodes_to"].encode()).decode()
        assert encoded in (REPO / entry["expected_in"]).read_text(), (
            f"{entry['expected_in']} no longer contains the value the acknowledgement "
            "covers — delete the entry rather than leave it standing over nothing"
        )


# --------------------------------------------------------------------------- #
# 2-3. what the record may and may not carry
# --------------------------------------------------------------------------- #
# `generic-api-key` fires on a long high-entropy VALUE under a credential-shaped
# KEY. Both halves are required, and that is the whole finding: the record is full
# of long hex — commit shas, image ids, the tools' sha256s — and none of it reads
# as a credential, because none of it sits under a name like this. The first draft
# put the finding digest under `secret_sha256` and had both halves.
CREDENTIAL_SHAPED_KEY = re.compile(
    r"(secret|passwd|password|token|api[_-]?key|access[_-]?key|credential|auth)", re.I
)


@pytest.mark.needs_records
def test_the_record_carries_no_long_value_under_a_credential_shaped_key():
    offenders: list[str] = []

    def walk(node, where="root"):
        if isinstance(node, dict):
            for k, v in node.items():
                if (
                    CREDENTIAL_SHAPED_KEY.search(str(k))
                    and isinstance(v, str)
                    and len(v) >= 32
                    and " " not in v
                ):
                    offenders.append(f"{where}.{k}")
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    walk(read_record(SCAN_RECORD))
    assert not offenders, (
        f"the tracked scan record has a long unbroken value under {offenders} — that is "
        "exactly what `generic-api-key` matches, and the record is tracked, so the next "
        "scan blocks on its own output. This is the defect the 12-character finding_id "
        "fixed; do not widen this test, shorten the field."
    )


def test_the_scanner_itself_carries_no_credential_shaped_value():
    """The same property, one artifact along — the scanner is tracked too.

    No `needs_records` marker: it reads a source file, not a record, and F-047's
    guard was right to say so on its first run.
    """
    for line in SCANNER.read_text().splitlines():
        m = re.match(r'\s*"?(\w+)"?\s*[:=]\s*"([A-Za-z0-9+/=]{32,})"', line)
        if m and CREDENTIAL_SHAPED_KEY.search(m.group(1)):
            pytest.fail(f"credential-shaped assignment in the scanner: {line.strip()}")


@pytest.mark.needs_records
def test_the_record_carries_no_working_fields():
    def walk(node, where="root"):
        if isinstance(node, dict):
            for k, v in node.items():
                assert not str(k).startswith("_"), f"working field {k!r} survived at {where}"
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    walk(read_record(SCAN_RECORD))


@pytest.mark.needs_records
def test_no_finding_carries_a_value():
    rec = read_record(SCAN_RECORD)
    for leg in rec["legs"].values():
        for bucket in ("blocking", "local_only", "acknowledged"):
            for finding in leg.get(bucket, []):
                assert finding["value"].startswith("REDACTED")
                assert len(finding["finding_id"]) == 12


def test_strip_runs_at_the_write_boundary_and_is_recursive():
    mod = _module()
    stripped = mod._strip_working_fields(
        {"keep": 1, "_drop": 2, "nested": [{"_drop": 3, "keep": 4}]}
    )
    assert stripped == {"keep": 1, "nested": [{"keep": 4}]}


# --------------------------------------------------------------------------- #
# 4. the scan is a reader
# --------------------------------------------------------------------------- #
MUTATING = ("kubectl", "helm", "docker run", "docker rm", "docker push", "docker build")


def test_the_scan_runs_no_mutating_command():
    """Asked of the argv lists in the AST, never of the file's words.

    The module argues its own design in prose that names the things it does not
    do; a grep for "kubectl" would match the argument rather than an invocation
    (gotcha #99, third-and-more occurrence in this repo).
    """
    tree = ast.parse(SCANNER.read_text())
    invoked: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name not in {"run", "_run"}:
                continue
            for arg in node.args:
                if isinstance(arg, ast.List):
                    parts = [e.value for e in arg.elts if isinstance(e, ast.Constant)]
                    invoked.append(" ".join(str(p) for p in parts))
    assert invoked, "the AST walk found no subprocess invocation — the walk is broken"
    joined = " | ".join(invoked)
    for verb in MUTATING:
        assert verb not in joined, f"the scan invokes {verb!r}: {joined}"
    assert any("image" in i and "inspect" in i for i in invoked), (
        "the image leg is supposed to read each image's id back off the daemon"
    )


def test_the_scan_never_pushes_a_metric_or_touches_the_registry():
    text = SCANNER.read_text()
    for forbidden in ("mlflow", "pushgateway", "set_registered_model_alias"):
        assert forbidden not in text.lower(), f"the audit has no business with {forbidden}"


# --------------------------------------------------------------------------- #
# 5. the red team plants, it does not write
# --------------------------------------------------------------------------- #
def test_the_redteam_only_ever_scans_with_no_write():
    text = REDTEAM.read_text()
    invocations = re.findall(r"security_scan\.py[^\n\"]*", text)
    assert len(invocations) >= 3, "arm A, arm B and the restored re-ask"
    for inv in invocations:
        assert "--no-write" in inv, (
            f"{inv.strip()!r} would rewrite the tracked verdict with a tampered run — "
            "a drill that plants evidence is not a drill"
        )


def test_the_redteam_carries_no_credential_shaped_literal():
    """It generates its plant at run time, or it becomes a finding in its own scan.

    The property is "generated", not "generated HERE". Until M9-S13 the draw was an
    inline heredoc and this assertion named `secrets.choice`; when the hook drill
    needed the same plant, the generator moved to `scripts/redteam_plant.py` so
    F-071's lesson could live in one place, and a literal-hunting assertion went
    red for the change that made it stronger (gotcha #50). Re-derived, not widened:
    the drill must OBTAIN its plant from a generator, in this file or in that one.
    """
    text = REDTEAM.read_text()
    assert "secrets.choice" in text or "redteam_plant.py" in text, (
        "the plant must be generated, not typed — inline, or from the shared generator"
    )
    for hit in re.findall(r"[A-Za-z0-9+/]{20,}", text):
        assert not re.match(r"^AKIA[A-Z0-9]{16}$", hit), f"a typed AWS-shaped key id: {hit}"


def test_the_redteam_restores_and_proves_the_object_is_gone():
    text = REDTEAM.read_text()
    assert "gc --prune=now" in text, "deleting a branch is not destroying an object"
    assert "cat-file -e" in text, "and the destruction has to be asked about, not assumed"


# --------------------------------------------------------------------------- #
# 6-7. twins, and the derivations
# --------------------------------------------------------------------------- #
@pytest.mark.needs_records
def test_the_pinned_versions_and_the_record_are_twins():
    rec = read_record(TOOLS_RECORD)
    sh = TOOLS_SH.read_text()
    for tool, key in (("trivy", "TRIVY_VERSION"), ("gitleaks", "GITLEAKS_VERSION")):
        pinned = re.search(rf'^{key}="([^"]+)"', sh, re.M)
        assert pinned, f"{key} is not pinned in {TOOLS_SH.name}"
        assert rec["tools"][tool]["version"] == pinned.group(1), (
            f"{tool}: the script pins {pinned.group(1)} and the record was written by "
            f"{rec['tools'][tool]['version']} — the record is a READ-BACK, so a "
            "disagreement means the binary on this machine is not the pinned one"
        )
        assert len(rec["tools"][tool]["sha256_installed"]) == 64


@pytest.mark.needs_records
def test_the_image_refs_in_the_record_are_the_ones_their_sources_name():
    mod = _module()
    rec = read_record(SCAN_RECORD)
    recorded = {i["image"] for i in rec["legs"]["images"]["images"]}
    derived = {mod._image_ref(name, src, key) for name, src, key in mod.OUR_IMAGES}
    assert recorded == derived, (
        "the scan's images must be the ones the build records and the ServingRuntime "
        f"name today: recorded {sorted(recorded)} vs derived {sorted(derived)}"
    )


@pytest.mark.needs_records
def test_the_verdict_is_publishable_and_says_what_that_excludes():
    rec = read_record(SCAN_RECORD)
    verdict = rec["verdict"]
    assert verdict["secrets_in_git"] == 0
    assert verdict["publishable"] is True
    assert "CVE" in verdict["publishable_means"], (
        "a publish verdict that does not say what it is silent about invites the "
        "reading that the CVE counts below it were cleared"
    )
    assert set(rec["stages_run"]) == set(mod_stages()), "the recorded run covered every leg"


def mod_stages():
    return _module().STAGES


@pytest.mark.needs_records
def test_every_leg_recorded_the_inputs_it_looked_at():
    """gotcha #59: a scan that found nothing has to prove it looked."""
    rec = read_record(SCAN_RECORD)
    legs = rec["legs"]
    assert legs["history-secrets"]["inputs"]["commits_reachable_from_all_refs"] > 400
    assert legs["history-secrets"]["inputs"]["refs"] >= 1
    assert legs["tree-secrets"]["inputs"]["files_git_tracks"] > 500
    assert len(legs["images"]["inputs"]["images"]) == 3
    assert "uv.lock" in " ".join(legs["tree-vulns"]["inputs"]["lockfiles_seen"])
