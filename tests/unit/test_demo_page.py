"""The demo page's laws — M9-S1.

The page is a stakeholder artifact, which makes it the *easiest* thing in this
repo to let drift: nobody's gate fails when a zone list goes stale, and a picker
offering a zone the model never heard of renders perfectly. So the properties
that keep it honest are asserted here rather than trusted.

1. **It is GENERATED, and regeneration is byte-identical.** The zone list, the
   request schema and the default trip are derived from three sources; a
   hand-edited `index.html` is a twin of all three.
2. **The zone list IS the lookup table** — every id, no extras — and TLC's two
   non-places are present and labelled, not quietly dropped.
3. **The page's request schema is the SERVER's schema.** A wrong field name would
   be refused loudly by `decode_raw`; a wrong DATATYPE would not be, and would
   quote a plausible number nobody could see was wrong.
4. **The page's default trip is a row this repo has already published**, so the
   first thing a stakeholder sees is checkable against a tracked record.
5. **The route claims two paths and neither is `/`**, has no `host:`, and no
   `rewrite-target` — the three properties `demo/README.md` §1 argues for.
6. **The demo knows nothing about the registry.** No alias, no `models:/`, no
   mlflow — asked of the code, the M5-S1 `deploy-serving` precedent.
7. **The busybox pin is not a twin** of the one the data stager already carries.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.transformer import RAW_INPUTS  # noqa: E402

pytestmark = pytest.mark.unit

PAGE = REPO / "demo" / "index.html"
TEMPLATE = REPO / "demo" / "index.template.html"
GENERATOR = REPO / "scripts" / "build_demo_page.py"
MANIFEST = REPO / "infra" / "manifests" / "demo.yaml"
STAGER = REPO / "infra" / "manifests" / "flyte-data-stager.yaml"
DEPLOY = REPO / "scripts" / "deploy_demo.sh"
ACCEPT = REPO / "scripts" / "demo_accept.py"
LOOKUP = REPO / "data" / "reference" / "taxi_zone_lookup.csv"
README = REPO / "demo" / "README.md"


def page_text() -> str:
    return PAGE.read_text()


def page_const(name: str) -> object:
    match = re.search(rf"^const {name} = (.*?);$", page_text(), re.MULTILINE | re.DOTALL)
    assert match, f"demo/index.html has no `const {name}`"
    return json.loads(match.group(1))


def manifest_docs() -> list[dict]:
    return [d for d in yaml.safe_load_all(MANIFEST.read_text()) if d]


def _docstrings(tree: ast.AST) -> set[int]:
    """The id()s of every docstring Constant, so prose can be excluded from a scan.

    Gotcha #99, and it bit twice while this file was being written: the first
    version of the two tests below searched for words, and both matched the
    scripts' own arguments — `demo_accept.py`'s docstring says outright that it
    does not import mlflow, and quotes the demo's URL. A needle must sit where an
    interpreter would EXECUTE it, never merely where a reader would find it.
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                out.add(id(body[0].value))
    return out


def code_strings(path: Path) -> list[str]:
    """Every string literal a Python file EXECUTES with — docstrings excluded."""
    tree = ast.parse(path.read_text())
    skip = _docstrings(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------- generated ---
def test_the_committed_page_is_what_the_generator_produces() -> None:
    """`--check` is the round trip: regenerate in memory, diff against git."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, (
        "demo/index.html has drifted from its sources. Run 'make demo-page' and commit.\n"
        f"{result.stdout}{result.stderr}"
    )


def test_regenerating_twice_is_deterministic(tmp_path: Path) -> None:
    """No timestamp, no host, no dict-ordering surprise — else the check above flaps."""
    before = PAGE.read_bytes()
    subprocess.run([sys.executable, str(GENERATOR)], capture_output=True, check=True)
    once = PAGE.read_bytes()
    subprocess.run([sys.executable, str(GENERATOR)], capture_output=True, check=True)
    twice = PAGE.read_bytes()
    assert once == twice == before, "regeneration is not deterministic"


def test_the_template_never_mentions_a_token_it_does_not_mean() -> None:
    """The generator's first run substituted its own explanatory comment.

    That produced a page with three copies of every picker — it rendered, and it
    was wrong in a way no 'the zone list matches the CSV' assertion would catch
    (each copy matched). Gotcha #53/#60: prose must not sit where a parser reads
    it as code. The counts live in TOKEN_COUNTS and are asserted here too, so a
    template edit that adds a slot has to say so in both places.
    """
    source = GENERATOR.read_text()
    counts = re.search(r"TOKEN_COUNTS = (\{[^}]*\})", source)
    assert counts, "build_demo_page.py no longer declares TOKEN_COUNTS"
    declared = ast.literal_eval(counts.group(1))
    template = TEMPLATE.read_text()
    for name, expected in declared.items():
        assert template.count("{{" + name + "}}") == expected, (
            f"the template contains {{{{{name}}}}} a different number of times than "
            f"TOKEN_COUNTS declares ({expected})"
        )


# --------------------------------------------------------------- the zones ---
def test_the_pickers_are_exactly_the_lookup_table() -> None:
    with LOOKUP.open(newline="") as fh:
        expected = [int(row["LocationID"]) for row in csv.DictReader(fh)]
    ids = [int(v) for v in re.findall(r'<option value="(\d+)"', page_text())]
    # Two pickers, so every id appears exactly twice and in the same set.
    assert sorted(set(ids)) == sorted(expected), "the picker's zone set is not the CSV's"
    assert len(ids) == 2 * len(expected), "the zone options are not rendered once per picker"


def test_the_two_non_places_are_rendered_and_labelled() -> None:
    """264/265 carry no centroid by DR-04 condition 1 — hiding them would make the
    demo tidier than the data. They must be present AND flagged as bookkeeping."""
    text = page_text()
    for zone_id in (264, 265):
        assert f'<option value="{zone_id}">' in text, f"zone {zone_id} is missing from the pickers"
        assert f"zone {zone_id}, no centroid" in text, f"zone {zone_id} is not labelled honestly"
    assert "not places" in text


# -------------------------------------------------------------- the schema ---
def test_the_pages_request_schema_is_the_servers() -> None:
    schema = page_const("RAW_INPUTS")
    expected = [
        {"name": name, "datatype": datatype, "field": field}
        for name, (datatype, field) in RAW_INPUTS.items()
    ]
    assert schema == expected, (
        "the page encodes with a schema the transformer does not decode with. A wrong "
        "NAME would be refused by decode_raw; a wrong DATATYPE would be quoted."
    )


@pytest.mark.needs_records
def test_the_default_trip_is_a_published_row() -> None:
    """The opening quote must be checkable against a tracked record, not a guess."""
    trip = page_const("DEFAULT_TRIP")
    record = json.loads(
        (REPO / "automation" / "runs" / "m8-transformer" / "transformer-parity.json").read_text()
    )
    matches = [
        row
        for row in record["rows"]
        if row["at"] == trip["pickup_datetime"]
        and row["pu"] == trip["pu_location_id"]
        and row["do"] == trip["do_location_id"]
    ]
    assert matches, f"the page's default trip {trip} matches no recorded parity row"


def test_the_endpoint_is_relative_which_is_what_dissolves_cors() -> None:
    endpoint = page_const("ENDPOINT")
    assert isinstance(endpoint, str) and endpoint.startswith("/"), (
        "the page's endpoint must be a RELATIVE url: same origin is the whole route "
        "decision, and an absolute one would reintroduce the cross-origin request "
        "demo/README.md §1 argues does not exist here"
    )
    assert "://" not in endpoint


# --------------------------------------------------------------- the route ---
def _transformer_names() -> tuple[str, str]:
    """(transformer isvc, champion isvc) read from M8's accept, not retyped here.

    The V2 model name is in the URL path (ADR-011 condition 2), so the demo's api
    path is a FUNCTION of the transformer's isvc name — and the first deploy of
    this route proved it by claiming the champion's name and 404ing on every
    quote. Deriving it from a constant M8-S4's own accept already depends on
    means a rename breaks one place loudly instead of two places quietly.
    """
    tree = ast.parse((REPO / "scripts" / "transformer_accept.py").read_text())
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"ISVC", "CHAMPION"}:
                    found[target.id] = node.value.value
    assert {"ISVC", "CHAMPION"} <= set(found), "transformer_accept.py's names moved"
    return found["ISVC"], found["CHAMPION"]


def test_the_route_has_no_host_and_claims_two_paths_neither_of_them_root() -> None:
    transformer, champion = _transformer_names()
    api_path = f"/v2/models/{transformer}/infer"
    ingress = [d for d in manifest_docs() if d["kind"] == "Ingress"]
    assert len(ingress) == 1
    rules = ingress[0]["spec"]["rules"]
    assert len(rules) == 1
    assert "host" not in rules[0], (
        "a `host:` would create a named nginx server block, and `location /healthz` "
        "lives only in the DEFAULT block — deploy_serving.sh's accept would go red "
        "for a correct system (demo/README.md §1.1)"
    )
    paths = {p["path"]: p for p in rules[0]["http"]["paths"]}
    assert set(paths) == {"/demo", api_path}
    assert "/" not in paths, "claiming / would break `GET localhost:8081/` -> 404"
    assert f"/v2/models/{champion}/infer" not in paths, (
        "the CHAMPION's own model name must stay unrouted on this origin — its "
        "absence is what proves a quote came through the raw boundary"
    )
    assert paths[api_path]["pathType"] == "Exact", "the demo claims ONE api path, not the /v2 tree"
    assert (
        paths[api_path]["backend"]["service"]["name"] == f"{transformer}-transformer"
    ), "the demo must target the TRANSFORMER — a browser cannot build the 24-column matrix"


def test_the_pages_endpoint_is_the_path_the_route_claims() -> None:
    """The page and the Ingress must agree, or the demo 404s in a browser only."""
    ingress = [d for d in manifest_docs() if d["kind"] == "Ingress"][0]
    claimed = {p["path"] for p in ingress["spec"]["rules"][0]["http"]["paths"]}
    assert page_const("ENDPOINT") in claimed


def test_the_accepts_negative_is_the_champions_own_name() -> None:
    _, champion = _transformer_names()
    source = (REPO / "scripts" / "demo_accept.py").read_text()
    match = re.search(r'^UNCLAIMED_PATH = "(.*)"$', source, re.MULTILINE)
    assert match and match.group(1) == f"/v2/models/{champion}/infer", (
        "the accept's negative must be the champion's own model name: a 404 there is "
        "what says the page reached the raw boundary and not the 24-column wire"
    )


def test_no_rewrite_target_anywhere() -> None:
    for doc in manifest_docs():
        annotations = (doc.get("metadata") or {}).get("annotations") or {}
        assert not any("rewrite" in key for key in annotations), (
            "no rewrite-target: the page is mounted at /www/demo so busybox resolves "
            "/demo/ natively (demo/README.md §1.2)"
        )


def test_the_names_are_not_ones_kserve_generates() -> None:
    """F-039: a hand-authored object taking a generated name is reverted silently."""
    generated = {
        "nyc-taxi-eta",
        "nyc-taxi-eta-predictor",
        "nyc-taxi-eta-transformer",
        "nyc-taxi-eta-transformer-predictor",
        "nyc-taxi-eta-transformer-transformer",
    }
    for doc in manifest_docs():
        assert doc["metadata"]["name"] not in generated
        assert doc["metadata"]["name"].startswith("taxi-demo-")


def test_the_deploy_refuses_owned_objects_and_honours_dry_run() -> None:
    text = DEPLOY.read_text()
    assert "ownerReferences" in text, "F-039's precondition check is gone"
    assert 'DRY_RUN:-0}" == "1"' in text, "gotcha #30: DRY_RUN must mutate nothing"
    # The DRY_RUN branch must sit BEFORE the first mutation.
    assert text.index("DRY_RUN") < text.index("kubectl -n \"$NAMESPACE\" create configmap")


# ------------------------------------------------------------ what it isn't ---
def test_the_demo_never_touches_the_registry() -> None:
    """M5-S1's precedent: the demo cannot reach the registry — asked of the AST.

    A word-search here greps these scripts' own arguments about not reaching the
    registry (gotchas #53/#68/#99 — it did, on this test's first run). So: no
    mlflow import, and no registry-shaped string among the literals the file
    actually executes with.
    """
    banned = ("models:/", "@champion", "set_registered_model_alias")
    for path in (ACCEPT, GENERATOR):
        assert "mlflow" not in imported_modules(path), f"{path.name} imports mlflow"
        for literal in code_strings(path):
            for needle in banned:
                assert needle not in literal, f"{path.name} executes with {needle!r}: {literal!r}"
    # The deploy is shell, so the AST route is unavailable — but the property is
    # the same, and the comment lines that argue it are excluded explicitly.
    for number, line in enumerate(DEPLOY.read_text().splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        for needle in (*banned, "mlflow"):
            assert needle not in line, f"deploy_demo.sh:{number} names {needle!r}: {line.strip()}"


def test_the_accept_reads_the_page_rather_than_retyping_it() -> None:
    """The check's whole claim is that it sends what the PAGE sends."""
    source = ACCEPT.read_text()
    for name in ("ENDPOINT", "RAW_INPUTS", "DEFAULT_TRIP"):
        assert f'_const(page, "{name}")' in source, (
            f"demo_accept.py no longer reads {name} out of the page — it would then be "
            "measuring a second client that merely resembles the demo"
        )
    urls = {literal for literal in code_strings(ACCEPT) if "://" in literal}
    assert urls <= {"http://localhost:8081"}, f"unexpected absolute url(s) in the accept: {urls}"


def test_the_accept_sends_no_host_header_override() -> None:
    """The one thing a browser cannot do, and every other client here does."""
    source = ACCEPT.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            assert "Host" not in keys, (
                "demo_accept.py sets a Host header — then it is not testing the "
                "same-origin path the browser uses"
            )


def test_the_busybox_pin_is_not_a_twin() -> None:
    demo_pin = re.findall(r"image: (busybox:[^\s]+)", MANIFEST.read_text())
    stager_pin = re.findall(r"image: (busybox:[^\s]+)", STAGER.read_text())
    assert demo_pin and stager_pin, "a busybox pin went missing"
    assert set(demo_pin) == set(stager_pin), (
        "the demo pins a different busybox than the data stager. Two copies of a pin is "
        "a twin; the demo reuses the program's existing one precisely so it adds no image."
    )


def test_every_element_the_script_addresses_exists_in_the_markup() -> None:
    """A typo'd id is a demo that renders perfectly and silently does nothing.

    No test here runs JavaScript, so this is the cheapest thing that catches the
    most likely browser-only failure: the script reaches for an element by id,
    gets null, and the button does nothing at all with no error a user can see.
    """
    text = page_text()
    addressed = set(re.findall(r'getElementById\("([^"]+)"\)', text))
    assert addressed, "the page addresses no elements — did the script move?"
    declared = set(re.findall(r'\bid="([^"]+)"', text))
    missing = addressed - declared
    assert not missing, f"the script addresses element(s) that do not exist: {sorted(missing)}"


def test_the_three_error_classes_render_differently() -> None:
    """422, 503 and 'anything else' must not collapse into one message.

    A refusal is the guard working, a 503 is a dependency outage the caller
    cannot fix, and an unreadable answer is neither. `demo/README.md` §3 argues
    why; this is the check that the page's branches actually exist and carry
    distinguishable words rather than one shared 'something went wrong'.
    """
    text = page_text()
    assert "response.status === 422" in text, "no 422 branch"
    assert "response.status === 503" in text, "no 503 branch"
    for phrase in ("Refused", "temporarily unavailable", "Unexpected answer"):
        assert phrase in text, f"the page never says {phrase!r}"
    # The refusal must show the SERVICE's own reason, not a substitute sentence —
    # F-019's horizon text is the thing worth reading.
    assert "payload.error" in text, "the page invents its own error text"


def test_the_readme_records_the_route_decision_and_the_po_box() -> None:
    text = README.read_text()
    assert "host-less" in text.lower()
    assert "CORS" in text
    assert "unassisted" in text, "the PO-observed box must be named, not implied"
    assert "EXACT" in text, "§4 must state the accept's bar"


# --------------------------------------------------------------------------
# F-067 — the accept may not close the human box, and may not re-open it.
# --------------------------------------------------------------------------

def test_the_accept_can_never_close_the_human_box() -> None:
    """It writes OPEN or it carries a closure forward; it never authors one.

    The asymmetry is the whole point: closing §9/M9's last accept line requires
    a person, so the only CLOSED status this script may ever put in a record is
    one it read out of the record it is overwriting.

    Asked of the AST, and asked NARROWLY: a search for the word finds the
    script comparing against it (`startswith("CLOSED")`) and the field name it
    prints (`closed_on`), which is the code RECOGNISING a closure — the opposite
    of authoring one, and gotcha #99 for the third time in this file. The
    question is whether any dict this script builds carries a `status` whose
    value it wrote itself and which reads as closed.
    """
    tree = ast.parse(ACCEPT.read_text())
    authored = {
        value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "status"
        and isinstance(value, ast.Constant) and isinstance(value.value, str)
        and value.value.upper().startswith("CLOSED")
    }
    assert not authored, (
        f"demo_accept.py AUTHORS a closed status {authored} — an unattended "
        "check must never be able to write the one verdict that needs a human; "
        "the only CLOSED block it may hold is one it read out of the record it "
        "is replacing"
    )


def _human_box():
    """`scripts/` is not a package; load the one decision under test by path."""
    spec = importlib.util.spec_from_file_location("demo_accept_under_test", ACCEPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.human_box


def test_the_accept_carries_a_human_closure_forward_rather_than_re_opening_it(
    tmp_path: Path,
) -> None:
    """F-067, exercised rather than asserted about.

    The record is rewritten in full on every run, so before M9-S5 a second
    `make demo-accept` would have deleted the PO's closure and left the M9 gate
    correctly reporting a box that had just silently re-opened — the failure
    with no symptom, since the re-opened record is internally perfect.
    """
    human_box = _human_box()
    url = "http://localhost:8081/demo/"
    closed = {
        "status": "CLOSED — observed 2026-08-24, cited at AWAITING_PO 2026-08-23-3",
        "cites": "2026-08-23-3",
        "closed_on": "2026-08-24",
        "po_note": "This is okay, I get the gist of it. Improvement can be done later.",
        "box": "BLUEPRINT §9/M9: … completes a query unassisted, observed",
        "url": url,
    }
    prior = tmp_path / "accept.json"
    prior.write_text(json.dumps({"po_observed_run": closed}))
    assert human_box(prior, url) == closed, (
        "a human's closure did not survive the run that rewrote the record — "
        "every field must be carried VERBATIM, since the citation is what makes "
        "the closure honest and a rebuilt block is the accept authoring one"
    )

    # Every other state produces the OPEN block: no record (a fresh clone),
    # an unreadable one, and an already-open one.
    for name, body in (
        ("absent.json", None),
        ("torn.json", "{not json at all"),
        ("open.json", json.dumps({"po_observed_run": {"status": "OPEN — …"}})),
    ):
        path = tmp_path / name
        if body is not None:
            path.write_text(body)
        assert human_box(path, url)["status"].startswith("OPEN"), (
            f"{name}: the accept did not fall back to the OPEN block, so a run "
            "against a damaged or missing record would say nothing about the box"
        )
