"""The M4 gate, tested as a thing that can be wrong (M4-S5 leg 3).

Third in the line after `test_verify_m2.py` and `test_verify_m3.py`, same
premise: `scripts/verify_m4.sh` is the only artifact whose job is to say whether
M4 happened, and nothing else checks IT. So these tests pin the properties that
would fail SILENTLY — a leg that stops reading the records keeps printing `ok`;
a parse that returns nothing keeps printing `ok` unless somebody demanded a
positive count.

M4 adds two properties its predecessors did not need, and both were paid for:

  * RE-RUNS NOTHING, which is a stronger claim than M3's re-fits-nothing. M4's
    evidence took ~95 minutes of on-cluster work (a 31-minute full-data fit, the
    cache drill's two runs, the kill drill, the marts run). A gate that launched
    a pipeline would also MINT MLflow runs — and the count of those runs is the
    strongest leg the cache check has. This gate would corrupt its own evidence.

  * THE CACHE LEG READS A RECORD, NOT THE LATEST RUN (gotcha #66). The Flyte
    cache key covers the whole task spec and the image tag is the git short sha,
    so one commit under src/ turns every stage of the next run into
    CACHE_POPULATED. A gate that re-asked the control plane would go red for a
    commit — #50's disease with a new cause.

House rule inherited from gotcha #35: match the INVOCATION, never the word. This
script talks ABOUT pipelines, publishes and promotions in its comments and in the
lines it prints, so every assertion about what it DOES is made against a
comment-stripped copy.
"""

from __future__ import annotations

import re

from conftest import REPO, invokes, phony_targets, without_comments

VERIFY_M4 = REPO / "scripts" / "verify_m4.sh"
REDTEAM = REPO / "scripts" / "verify_m4_redteam.sh"
MAKEFILE = REPO / "Makefile"


# ------------------------------------------------------- the Makefile contract --
def test_the_m4_targets_are_real_and_no_longer_echo_todo():
    """A target that echoes TODO after its milestone landed is a lie with a tab
    character in front of it. `verify-m4` echoed exactly that until this story."""
    text = MAKEFILE.read_text()
    for target in ("verify-m4:", "verify-m4-redteam:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m4.sh" in text
    assert "bash scripts/verify_m4_redteam.sh" in text
    # Membership across EVERY `.PHONY` declaration, continuation lines joined the
    # way GNU make joins them (F-083, CU-S1). The idiom this replaces read one
    # line at a time — blind to a wrapped declaration — and compared by SUBSTRING,
    # so a longer target name merely containing this one would have satisfied it.
    assert "verify-m4-redteam" in phony_targets(text), (
        "verify-m4-redteam is not declared .PHONY"
    )


# ----------------------------------------------- the gate has no side effects ---
def test_the_gate_reruns_no_pipeline_and_no_drill():
    """M4's evidence cost ~95 minutes on-cluster. Re-running any of it would cost
    more than the milestone AND would mint MLflow runs — which §4's strongest leg
    counts. This gate would corrupt the evidence it exists to read."""
    body = without_comments(VERIFY_M4)
    for invocation in (
        "make pipeline", "make pipeline-local", "make pipeline-cache-drill",
        "make pipeline-kill-drill", "make marts", "make train", "make predictions",
        "make image-build", "make image-load", "make image-smoke", "make stage-data",
        "make flyte-hello", "make boards", "flyte run", "taxi_mlops.training train",
    ):
        assert not invokes(body, invocation), (
            f"verify_m4.sh invokes {invocation!r} — the gate re-runs what it is meant to read"
        )
    for script in (
        "scripts/run_pipeline.sh", "scripts/pipeline_cache_drill.sh",
        "scripts/pipeline_kill_drill.sh", "scripts/marts.sh",
        "scripts/image_build_load.sh", "scripts/stage_pipeline_data.sh",
        "pipelines/tasks.py", "pipelines/flyte/workflows.py",
    ):
        for runner in ("bash ", "sh ", "uv run python ", "python ", "python3 ", "$(", "`"):
            assert f"{runner}{script}" not in body, (
                f"verify_m4.sh runs {script!r} — the gate re-runs what it is meant to read"
            )


def test_the_marts_leg_reconciles_and_never_publishes():
    """§6 imports the publisher on purpose — `reconcile` is the check D-003's row
    asks for, and re-implementing it in the gate would be the twin that story went
    out of its way not to create. What it may NOT do is publish: a gate with side
    effects on the warehouse it checks is not a gate, and a full refresh costs
    228 s and a 2.075x volume peak."""
    body = without_comments(VERIFY_M4)
    assert "mp.reconcile(" in body, "§6 no longer calls the publisher's own reconcile"
    for mutator in ("mp.publish(", "publish(transport", "--duckdb", "marts_publish.py"):
        assert mutator not in body, (
            f"verify_m4.sh reaches for {mutator!r} — the gate would republish the marts"
        )
    # The transport it builds is the read-only host one. `psycopg` would need the
    # marts password on this side for a read the kubectl route already gets free.
    assert 'make_transport("kubectl"' in body


def test_the_gate_mutates_no_registry_state():
    """M4's standing law is that no M4 run moves `@champion`. A gate that could
    move it would be the first exception, and §7 is where such a call would live."""
    body = without_comments(VERIFY_M4)
    for mutator in (
        "set_registered_model_alias", "delete_registered_model_alias",
        "create_model_version", "delete_model_version", "delete_run",
        "registry.promote", "transition_model_version_stage",
    ):
        assert mutator not in body, (
            f"verify_m4.sh calls {mutator} — a gate that edits what it checks"
        )
    # It reads the alias the way M2-S3 established, and the reason is live:
    # `search_model_versions` returns `aliases` EMPTY on server 3.15.1, so a
    # snapshot built from that field would be blind to the mutation §7 checks for.
    assert "get_model_version_by_alias" in body


def test_the_gate_mutates_no_cluster_state():
    """It reads pods, deployments, a PodTemplate and a PVC. It applies, scales,
    patches and deletes nothing — the M4 kickoff's standing law is that the
    cluster never goes down, and a gate is not an exception to it."""
    body = without_comments(VERIFY_M4)
    for verb in ("kubectl apply", "kubectl delete", "kubectl scale", "kubectl patch",
                 "kubectl create", "helm upgrade", "helm install", "kind delete",
                 "docker rmi", "docker build"):
        assert verb not in body, f"verify_m4.sh runs {verb!r} — it mutates the cluster it checks"
    # The one container it starts is `--rm` and runs a read-only probe: D-004's
    # closure is only observable from INSIDE the image.
    starts = re.findall(r"\"docker\", \"run\"[^\]]*\]", body)
    assert starts, "the in-container D-004 probe is gone — the debt's closure is unobserved"
    for call in starts:
        assert '"--rm"' in call, f"a container is started without --rm: {call}"


def test_the_gate_has_no_fast_mode_or_skip_flag():
    """M1's rule, inherited a third time. This gate runs in seconds; there is
    nothing to excuse. A gate with a skip flag is a gate that runs with it."""
    body = without_comments(VERIFY_M4)
    for flag in ("SKIP_", "FAST=", "QUICK=", "--quick", "--fast", "NO_CLUSTER"):
        assert flag not in body, f"verify_m4.sh grew a {flag} escape hatch"


# ------------------------------------------- every leg must actually have run ---
def test_every_python_leg_is_guarded_by_a_minimum_verdict_count():
    """The 'green light wired to no sensor' lesson, applied to the checker.

    A leg that dies on import contributes zero FAIL lines and the gate sails past
    it. `expect_verdicts` makes under-running a failure in its own right.
    """
    body = without_comments(VERIFY_M4)
    legs = body.count("consume < <(")
    guards = body.count("expect_verdicts ")
    assert legs >= 6, f"only {legs} leg(s) found — the parse is looking at the wrong thing"
    assert guards >= legs, f"{legs} leg(s) but only {guards} expect_verdicts guard(s)"
    for want in re.findall(r"expect_verdicts (\d+)", body):
        assert int(want) >= 1, "an expect_verdicts guard demands zero verdicts — it guards nothing"


def test_consume_is_never_called_through_a_pipe():
    """`… | consume` runs the function in a SUBSHELL, so every FAIL it counts is
    discarded at the closing brace and the gate exits 0 with failures on screen."""
    body = without_comments(VERIFY_M4)
    assert "| consume" not in body
    assert body.count("consume < <(") == body.count("consume <")


def test_every_python_leg_catches_its_own_exception_and_reports_it_as_a_failure():
    """A leg that raises past its own handler prints a traceback to a stream the
    counter never reads, and `expect_verdicts` would be the only thing that
    noticed. Each leg says so itself, by name."""
    body = without_comments(VERIFY_M4)
    python_legs = body.count("uv run python - 2>/dev/null <<'PY'")
    handlers = body.count("check itself raised")
    assert python_legs >= 5, f"only {python_legs} Python leg(s) found — the parse is wrong"
    assert handlers >= python_legs, (
        f"{python_legs} Python leg(s) but only {handlers} self-naming exception handler(s)"
    )


# --------------------------------------- properties, not literals (F-017) -------
def test_the_gate_pins_no_run_id_no_version_and_no_image_tag():
    """The rule this program paid for three times (gotchas #49/#50, and again at
    M4-S5 leg 2). Every number this gate compares must be derived on BOTH sides.

    The needles are shapes, not the specific values that happen to be on this
    machine: a Flyte run name, an MLflow run id, a tagged image reference.
    """
    body = without_comments(VERIFY_M4)
    for pattern, what in (
        (r"\br[a-z0-9]{15,}\b", "a Flyte run name"),
        (r"\b[0-9a-f]{32}\b", "an MLflow run id"),
        (r"taxi-mlops-pipeline:[0-9a-f]{6,}", "a task image tag"),
    ):
        found = re.findall(pattern, body)
        assert not found, f"verify_m4.sh pins {what}: {found[:3]} — read it from the record"


def test_the_experiment_name_is_read_from_the_source_not_typed_into_the_gate():
    """`verify-m2` pinned the champion's EXPERIMENT and went red on the first
    legitimate transition. The same hazard exists here — §3 and §7 both ask MLflow
    what the pipeline fitted — so the name lives in `pipelines/tasks.py` and the
    gate imports it."""
    import ast

    # Read the constant out of the source rather than importing the module:
    # `pipelines/` is not an installed package (it is the code bundle), which is
    # the same reason `test_pipeline_tasks.py` loads it by file location.
    cli = (REPO / "pipelines" / "tasks.py").read_text()
    experiment = next(
        node.value.value
        for node in ast.walk(ast.parse(cli))
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "DEFAULT_EXPERIMENT" for t in node.targets)
        and isinstance(node.value, ast.Constant)
    )
    assert isinstance(experiment, str) and experiment

    body = without_comments(VERIFY_M4)
    assert "tasks.DEFAULT_EXPERIMENT" in body, "the gate stopped importing the name"
    assert experiment not in body, (
        f"verify_m4.sh types {experiment!r} instead of importing it"
    )
    # ...and the CLI must not have a second copy of it either.
    assert cli.count(f'"{experiment}"') == 1, (
        "the experiment name is written twice in pipelines/tasks.py — the twin it was "
        "extracted to prevent"
    )


def test_the_stage_set_and_the_cache_policy_are_derived_from_code():
    """The two most tempting literals in this gate are the list of stages and the
    list of stages that refuse a cache. Both are read out of the source with `ast`
    — so a stage added to the graph and never wrapped, or a stage that quietly
    starts declaring cache='disable', turns the gate RED instead of being
    accommodated by a list somebody edits."""
    body = without_comments(VERIFY_M4)
    assert "tasks.STAGES" in body, "the gate no longer reads the stage list from tasks.py"
    assert body.count("ast.parse") >= 3, (
        "the gate stopped parsing the source for its wrappers, its cache policy and its "
        "retry budget"
    )
    assert 'kw.value.value == "disable"' in body, (
        "the uncached set is no longer derived from the task decorators"
    )
    assert "_STAGE_RETRIES" in body, "the retry budget is no longer read from workflows.py"


def test_the_cache_leg_reads_the_record_and_never_the_latest_run():
    """Gotcha #66, made structural. An image rebuild invalidates every cached
    stage, so the newest run reads CACHE_POPULATED in any session that committed
    — and a gate re-asking the control plane would go red for a commit."""
    body = without_comments(VERIFY_M4)
    assert "automation/runs/m4-cache/cache_drill.json" in body
    for live_reader in ("flyte_run_actions.py", "make flyte-actions", "flyte_actions.sh"):
        assert live_reader not in body, (
            f"verify_m4.sh reads live run state via {live_reader!r} — gotcha #66 makes that "
            f"red for a commit"
        )
    # `flyte get` is matched as an INVOCATION, never as a substring: the control-plane
    # leg runs `kubectl -n flyte get deploy`, which contains those two words.
    assert not invokes(body, "flyte get"), "verify_m4.sh asks the CLI about a live run"


def test_the_gate_names_the_gitignored_dependency_rather_than_hiding_it():
    """F-029, stated where a reader meets it. The records are machine state, not
    repo state; a gate that quietly depended on them would look portable and go
    red on a fresh clone with no explanation."""
    header = VERIFY_M4.read_text().split("set -uo pipefail")[0]
    assert "gitignored" in header
    assert "F-029" in header


# ------------------------------------------------------------- the red team ----
def test_the_redteam_restores_from_a_byte_copy_under_a_trap():
    """A drill that damages the evidence is worse than no drill. The restore must
    survive a Ctrl-C, so it hangs off EXIT and is verified by sha256, not assumed.

    Re-derived at CU-S3: the scaffold lives in `scripts/lib/redteam_restore.sh`
    and `test_script_libs.py` watches it do both — restore after an abnormal
    exit, and refuse to call a failed put-back a restore. This test keeps the
    half that is about THIS drill: it uses the scaffold on the record it edits."""
    body = without_comments(REDTEAM)
    assert "scripts/lib/redteam_restore.sh" in body
    assert 'redteam_snapshot "$RECORD"' in body
    assert "redteam_assert_restored" in body


def test_the_redteam_breaks_a_record_and_never_the_cluster():
    """The M2/M3 shape: break the POINTER-class thing. It edits one field of one
    JSON file — no pod, no image, no MLflow run, no registry version, no mart."""
    body = without_comments(REDTEAM)
    for forbidden in ("kubectl delete", "kubectl scale", "docker rmi", "delete_run",
                      "delete_registered_model_alias", "DROP TABLE", "make pipeline"):
        assert not invokes(body, forbidden), f"the M4 drill touches real state: {forbidden!r}"
    assert body.count("scripts/verify_m4.sh") >= 2, (
        "the drill must run the gate twice — RED under the tamper, GREEN after the restore"
    )


def test_the_redteam_asserts_the_untampered_legs_still_pass():
    """What separates a red-team from a checksum: the gate must go red on a WRONG
    number, not on ANY edit. So the drill demands the other sections still ran."""
    body = without_comments(REDTEAM)
    assert "still ran and passed" in body
    assert "unaffected leg still green" in body
    assert "not collateral" in body


def test_the_redteam_targets_the_cross_system_contradiction():
    """The tamper is chosen so TWO independent witnesses disagree — the control
    plane's cache_status and MLflow's run count. A gate reading only the first
    would have believed the file, and the drill asserts the second leg fired."""
    body = without_comments(REDTEAM)
    assert "two witnesses CONTRADICT each other" in body, (
        "the drill no longer requires the cross-system leg to fire"
    )
    # ...and the target is chosen from the record rather than typed, so the drill
    # keeps aiming at the most expensive stage when the numbers change.
    assert "max(" in body and "duration_ms" in body


def test_the_redteam_changes_exactly_one_field():
    """One field, and the ones that would make the lie obvious are left alone: the
    duration stays at its cached value and MLflow's counts stay equal. A tamper
    that broke three fields at once would prove the gate notices vandalism, not
    that it notices a plausible error.

    Asserted by parsing the embedded tamper, not by grepping it: the script prints
    the untouched fields in its own message, so a substring test would be reading
    the report rather than the edit (gotcha #53).
    """
    import ast

    source = REDTEAM.read_text().split("<<'PY'", 1)[1].split("\nPY\n", 1)[0]
    tree = ast.parse(source)
    written = {
        ast.unparse(node.targets[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Subscript)
    }
    assert written == {"target['cache_status']"}, (
        f"the drill rewrites {sorted(written)} — the lie must be ONE field, or the gate is "
        f"only being shown that it notices vandalism"
    )
