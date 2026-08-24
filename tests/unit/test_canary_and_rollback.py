"""M6-S4 — the canary release, the alias rollback, and the prose that quotes them.

Same three families as M6-S3's suite, for the same reasons:

1. STRUCTURAL, parsed with `ast` and never grepped. Every file in this story
   argues its own hazards at length — F-038 is explained in three headers, F-039
   in two — so a word search matches the argument (#53/#68).
2. DERIVED ON BOTH SIDES. No literal that is a fact about today (a version, a
   measured share, an outage) is typed into an assertion; the record and the code
   are compared with each other (F-017, #49/#50).
3. PROSE AGAINST RECORDS. Every number the runbook now quotes must exist in the
   record it cites — the M5-S5 shape, which is the half of the M5 gate its red
   team could not walk around.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DRILL = REPO / "scripts/canary_release_drill.py"
REHEARSAL = REPO / "scripts/alias_rollback_rehearsal.py"
DEPLOY_CANARY = REPO / "scripts/deploy_canary.sh"
CANARY_ISVC = REPO / "infra/manifests/inferenceservice-canary.yaml"
CANARY_INGRESS = REPO / "infra/manifests/canary-ingress.yaml"
CANARY_BACKEND = REPO / "infra/manifests/canary-backend-service.yaml"
CHAMPION_ISVC = REPO / "infra/manifests/inferenceservice-champion.yaml"
RUNBOOK = REPO / "docs/runbooks/serving.md"
DRILL_RECORD = REPO / "automation/runs/m6-canary/release_drill.json"
ROLLBACK_RECORD = REPO / "automation/runs/m6-rollback/alias_rollback.json"
ATTEMPT1 = REPO / "automation/runs/m6-canary/attempt1-ingress-name-collision/release_drill.json"


def _record(path: Path) -> dict:
    """Read a tracked drill record, and REFUSE if it is not there — F-054.

    These reads used to sit under `skipif(not RECORD.exists())`, which made the
    in-image run green by SKIPPING. On the host that is the weaker answer: an
    absent record means the drill was never run, and a silent skip is how a check
    stops being one. The records are git-tracked from M5-S1 (F-029 option A), so
    a fresh clone has them and the only thing this assertion can catch is a
    deleted or lost record — loudly. Where a test can run is now the marker's job
    (`needs_records`, F-047); whether it must pass is not negotiable.
    """
    assert path.exists(), (
        f"{path.relative_to(REPO)} is a TRACKED record (F-029 option A) — its absence "
        "means it was deleted or lost, not that this clone lacks local artifacts"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _calls(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _string_args(path: Path, call_name: str) -> list[list[str]]:
    """Every string-literal argument list passed to `call_name`, positional only.

    Used to inspect what a script asks `kubectl` to do without reading prose:
    the hazards this story is about are all spelled out in comments, so a
    substring search over the file would match the warning as well as the deed.
    """
    out: list[list[str]] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != call_name:
            continue
        out.append([a.value for a in node.args if isinstance(a, ast.Constant)
                    and isinstance(a.value, str)])
    return out


# --------------------------------------------------------------- structural --

MUTATING_REGISTRY_VERBS = {
    "delete_registered_model_alias",
    "create_model_version",
    "create_registered_model",
    "delete_model_version",
    "delete_registered_model",
    "transition_model_version_stage",
    "register_model",
    "log_model",
    "promote",
}


def test_the_canary_drill_touches_no_registry_state() -> None:
    """It shifts traffic; it must not be able to mint, tag or point anything.

    `set_registered_model_alias` is NOT in this ban list for the rehearsal below
    — that script's whole job is to move the alias — but the traffic drill has no
    business anywhere near it, so the two are checked with different bans rather
    than one loose one.
    """
    offenders = _calls(DRILL) & (MUTATING_REGISTRY_VERBS | {"set_registered_model_alias"})
    assert not offenders, f"{DRILL.name} calls {sorted(offenders)}"


def test_the_rollback_moves_the_alias_and_promotes_nothing() -> None:
    calls = _calls(REHEARSAL)
    assert "set_registered_model_alias" in calls, (
        "the rehearsal must move the alias with the RAW client call the runbook §4.3 "
        "types — a rollback that went through registry.promote would be a gate bypass"
    )
    offenders = calls & MUTATING_REGISTRY_VERBS
    assert not offenders, (
        f"{REHEARSAL.name} calls {sorted(offenders)} — a rollback moves a pointer; it "
        "does not create a version, and registry.promote refuses it anyway (F-011)"
    )


def test_neither_script_annotates_an_inferenceservice() -> None:
    """F-038, inherited as a law rather than a memory.

    KServe copies an isvc's annotations onto its pod template, so `kubectl
    annotate isvc` is a Deployment change: at M6-S3 it rolled the champion's only
    predictor twice and cost 174 of 200 requests a 502. The M6-S3 handoff routed
    "S4 must not annotate an isvc" here explicitly.
    """
    isvc_nouns = {"isvc", "inferenceservice", "inferenceservices"}
    for path in (DRILL, REHEARSAL):
        for args in _string_args(path, "kubectl"):
            lowered = {a.lower() for a in args}
            assert not ("annotate" in lowered and lowered & isvc_nouns), (
                f"{path.name} annotates an InferenceService: {args}. F-038 — that is a "
                "pod-template edit, not metadata."
            )


def test_the_canary_route_is_not_a_kserve_generated_name() -> None:
    """F-039, pinned from BOTH sides so neither can drift alone.

    The generated Ingress for an InferenceService takes the isvc's own name, so a
    hand-authored route sharing it is silently reconciled away. The check derives
    the forbidden name from the canary isvc manifest rather than typing it.
    """
    isvc_name = yaml.safe_load(CANARY_ISVC.read_text())["metadata"]["name"]
    route_name = yaml.safe_load(CANARY_INGRESS.read_text())["metadata"]["name"]
    assert route_name != isvc_name, (
        f"the canary Ingress is named {route_name!r}, which is the name KServe generates "
        "for the InferenceService of that name — the annotations are accepted and then "
        "reverted, and the split reads 0% with no error anywhere (F-039)"
    )
    assert "refuse_an_owned_ingress" in _calls(DRILL), (
        "the drill must refuse to weight an Ingress that carries ownerReferences — the "
        "name is only half of F-039's fix, and the guard is the half that survives a rename"
    )


def test_the_drill_reads_the_split_from_counters_and_not_from_its_own_config() -> None:
    """gotcha #81/#85: an applied annotation is an intent, not a measurement.

    Both witnesses must be present in the queries the drill actually issues — the
    router's own counter AND the predictors' — because either alone can be true
    while the release mechanism is broken.
    """
    source = DRILL.read_text()
    queries = re.findall(r'"""|f?"([^"\n]*(?:_total|_requests)[^"\n]*)"', source)
    joined = " ".join(q for q in queries if isinstance(q, str))
    assert "nginx_ingress_controller_requests" in joined, "the router's own counter is absent"
    assert "rest_server_requests_total" in joined, "the predictors' own counter is absent"
    assert 'canary!=""' in source, (
        "the canary-labelled series is what attributes a request to the alternative "
        "backend; without it the drill cannot tell a split from an idle canary"
    )


def test_the_canary_backend_service_is_referenced_by_exactly_one_ingress() -> None:
    """ADR-011 condition 1, asserted over the manifests that implement it."""
    backend = yaml.safe_load(CANARY_BACKEND.read_text())["metadata"]["name"]
    ingress = yaml.safe_load(CANARY_INGRESS.read_text())
    named = {
        p["backend"]["service"]["name"]
        for rule in ingress["spec"]["rules"]
        for p in rule["http"]["paths"]
    }
    assert named == {backend}, (
        f"the canary Ingress routes to {named}, not to the dedicated backend {backend!r}. "
        "A backend some other Ingress also claims holds the ordinary role and the weight "
        "is discarded silently (ADR-011 condition 1)."
    )
    # And no OTHER Ingress in the repo may name it. Checked over parsed Ingress
    # documents rather than over file text: the Service's own manifest obviously
    # contains its name, and so does every paragraph explaining why it exists.
    for path in REPO.glob("infra/manifests/*.yaml"):
        if path == CANARY_INGRESS:
            continue
        for doc in yaml.safe_load_all(path.read_text()):
            if not isinstance(doc, dict) or doc.get("kind") != "Ingress":
                continue
            claimed = {
                p["backend"]["service"]["name"]
                for rule in doc["spec"]["rules"]
                for p in rule["http"]["paths"]
            }
            assert backend not in claimed, (
                f"{path.name}'s Ingress {doc['metadata']['name']!r} also routes to "
                f"{backend!r} — the dedicated Service exists so that exactly one Ingress "
                "refers to it, which is the whole of ADR-011 condition 1"
            )


def test_the_canary_serves_the_champions_model_name() -> None:
    """ADR-011 condition 2's remedy, pinned against the champion's own manifest."""
    champion = yaml.safe_load(CHAMPION_ISVC.read_text())["metadata"]["name"]
    env = {
        e["name"]: e["value"]
        for e in yaml.safe_load(CANARY_ISVC.read_text())["spec"]["predictor"]["model"]["env"]
    }
    assert env.get("MLSERVER_MODEL_NAME") == champion, (
        "the canary must answer to the CHAMPION's V2 model name — the name is in the URL "
        "path and a canary Ingress cannot rewrite it (measured: 404, and rewrite-target "
        "moved the share 0 points)"
    )


def test_the_canary_carries_the_champions_resources() -> None:
    """At 100% weight it carries the champion's load; a differently-sized canary
    would rehearse a release whose latency is not the one that ships."""
    def resources(path: Path) -> dict:
        return yaml.safe_load(path.read_text())["spec"]["predictor"]["model"]["resources"]

    assert resources(CANARY_ISVC) == resources(CHAMPION_ISVC)


def test_neither_manifest_carries_a_usable_placeholder() -> None:
    """A stray `kubectl apply -f` must fail rather than half-work (M5-S2's rule)."""
    for path, key in ((CANARY_ISVC, "storageUri"), (CANARY_INGRESS, "canary-weight")):
        text = path.read_text()
        assert "RESOLVED-AT-DEPLOY-TIME" in text or "SET-AT-RUN-TIME" in text, (
            f"{path.name} no longer carries a placeholder for {key}"
        )


# ------------------------------------------------------- derived, not typed --


@pytest.mark.needs_records
def test_the_recorded_split_agrees_with_the_weight_the_drill_applied() -> None:
    """The record must reconcile with the code that produced it, not with a number.

    The applied weights are read out of the drill's own events and the tolerance
    out of the module on disk, so loosening either shows up here.
    """
    record = _record(DRILL_RECORD)
    tolerance = float(
        re.search(r"^SHARE_TOLERANCE_POINTS\s*=\s*([\d.]+)", DRILL.read_text(), re.M).group(1)
    )
    applied = {
        int(e["action"].split(":")[1]): e["at_s"]
        for e in record["events"]
        if "action" in e and e["action"].startswith("canary-weight")
    }
    assert set(applied) == {10, 100}, f"the drill applied weights {sorted(applied)}"
    observed = record["phases"]["canary_10"]["ingress"]["canary_share_pct"]
    assert abs(observed - 10) <= tolerance, (
        f"the 90/10 window observed {observed}% against the applied weight 10 and the "
        f"module's own tolerance of {tolerance} points"
    )
    assert record["phases"]["canary_100"]["ingress"]["canary_share_pct"] >= 95.0
    assert record["phases"]["baseline"]["ingress"]["canary_share_pct"] == 0.0
    assert record["phases"]["reverted"]["ingress"]["canary_share_pct"] == 0.0


@pytest.mark.needs_records
def test_the_two_witnesses_agree_in_the_record() -> None:
    """A split claimed by the router and denied by the pods is not a measurement."""
    record = _record(DRILL_RECORD)
    for phase in ("canary_10", "canary_100"):
        ingress = record["phases"][phase]["ingress"]["canary_share_pct"]
        pods = record["phases"][phase]["pods"]["canary_share_pct"]
        assert abs(ingress - pods) <= 3.0, (
            f"{phase}: the ingress counter says {ingress}% and the predictors' own say "
            f"{pods}% — two processes counting the same requests must agree"
        )


@pytest.mark.needs_records
def test_the_revert_is_inside_the_budget_the_drill_declares() -> None:
    record = _record(DRILL_RECORD)
    budget = float(
        re.search(r"^REVERT_BUDGET_SECONDS\s*=\s*([\d.]+)", DRILL.read_text(), re.M).group(1)
    )
    assert record["revert"]["nginx_cleared_seconds"] <= budget
    assert record["revert"]["budget_seconds"] == budget, (
        "the record's budget and the module's must be the same number, or a later "
        "loosening leaves the record claiming the old bar"
    )


@pytest.mark.needs_records
def test_the_failed_first_attempt_is_kept_with_its_cause() -> None:
    """The M5-S4 `attempt1-at-the-ceiling` precedent, third milestone running."""
    record = _record(ATTEMPT1)
    assert record["verdict"] == "FAIL"
    assert "F-039" in record["why_this_run_is_kept"]["cause"]
    assert record["phases"]["canary_10"]["ingress"]["canary_share_pct"] == 0.0, (
        "the kept record must still show the 0% it measured — a corrected record is "
        "not evidence of what went wrong"
    )


@pytest.mark.needs_records
def test_the_rollback_record_ends_where_it_started() -> None:
    record = _record(ROLLBACK_RECORD)
    end = record["end_state"]
    assert end["alias_version"] == "2" and end["features_version"] == "v2"
    assert end["configs_train_yaml_sha_before"] == end["configs_train_yaml_sha_after"], (
        "configs/train.yaml must be byte-identical after a round trip — the file's edit "
        "is real in both directions and the end state is the declared one"
    )
    assert record["verdict"] == "PASS"


@pytest.mark.needs_records
def test_the_coherence_check_was_green_at_BOTH_states() -> None:
    """The point of the whole rehearsal, as a test.

    `verify-m5` §2 asserts the served version's `feature_set` tag equals
    `configs/train.yaml: features.version`. Green at v2 alone is satisfiable by a
    literal; green at v1 as well is what makes it a coherence check (F-017).
    """
    record = _record(ROLLBACK_RECORD)
    assert record["at_the_half_way_state"]["coherence_green"]
    assert record["at_the_end_state"]["coherence_green"]
    assert record["at_the_half_way_state"]["exit_code"] != 0, (
        "the gate must go RED at the half-way state — a gate that stayed green while the "
        "alias pointed somewhere else would not be watching the pointer at all"
    )
    assert record["at_the_end_state"]["exit_code"] == 0


# -------------------------------------------------- prose against the record --


@pytest.mark.needs_records
def test_the_runbook_declares_the_rollback_rehearsed_and_cites_a_record() -> None:
    body = re.search(r"##\s*4\..*?(?=\n---|\n##\s*5\.)", RUNBOOK.read_text(), re.S).group(0)
    heading = body.splitlines()[0]
    assert re.search(r"(?<!NOT )REHEARSED\s+\d{4}-\d{2}-\d{2}", heading), (
        f"§4's heading is {heading!r} — an operator must be able to tell argued from proven "
        "from the heading alone"
    )
    cited = re.findall(r"automation/runs/[\w./-]+\.json", body)
    assert any((REPO / c).exists() for c in cited), (
        f"§4 cites {cited}, none of which this repo holds — a claim of proof needs the proof"
    )


@pytest.mark.needs_records
def test_every_rollback_number_the_runbook_quotes_is_in_the_record() -> None:
    """The M5-S5 shape: a document quoting a number no record holds is fiction.

    Precision policy, gotcha #76: the runbook may round, so a quoted value must
    round-trip to the record's number at the precision it was written at — and
    the comparison is on whole TOKENS, because a bare substring search would find
    `14` inside `14.53`.
    """
    record = _record(ROLLBACK_RECORD)
    body = re.search(r"##\s*4\..*?(?=\n---|\n##\s*5\.)", RUNBOOK.read_text(), re.S).group(0)
    tokens = set(re.findall(r"\d+\.\d+", body))
    for label, value in (
        ("leg 1 outage", record["leg_1_rollback"]["route"]["outage_seconds"]),
        ("leg 2 outage", record["leg_2_roll_forward"]["route"]["outage_seconds"]),
        ("leg 1 make serve", record["leg_1_rollback"]["seconds"]["make_serve"]),
        ("leg 2 make serve", record["leg_2_roll_forward"]["seconds"]["make_serve"]),
    ):
        rounded = {f"{value:.{p}f}" for p in range(0, 4)}
        assert tokens & rounded, (
            f"the runbook quotes no value matching {label} = {value} from the record "
            f"(it writes {sorted(tokens)})"
        )


@pytest.mark.needs_records
def test_every_canary_number_the_runbook_quotes_is_in_the_record() -> None:
    record = _record(DRILL_RECORD)
    body = re.search(r"###\s*4\.5.*?(?=\n---|\n##\s*5\.)", RUNBOOK.read_text(), re.S).group(0)
    tokens = set(re.findall(r"\d+\.\d+", body))
    for label, value in (
        ("weight-10 ingress share", record["phases"]["canary_10"]["ingress"]["canary_share_pct"]),
        ("weight-10 pod share", record["phases"]["canary_10"]["pods"]["canary_share_pct"]),
        ("the revert", record["revert"]["nginx_cleared_seconds"]),
    ):
        rounded = {f"{value:.{p}f}" for p in range(0, 4)}
        assert tokens & rounded, (
            f"§4.5 quotes no value matching {label} = {value} (it writes {sorted(tokens)})"
        )
