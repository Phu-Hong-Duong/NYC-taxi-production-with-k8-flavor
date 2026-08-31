"""M3-S4 — the automation track's invariants, the ones a live run cannot check.

A 2.5-hour scout-and-sniper run proves that the code works on the data it was
pointed at. It cannot prove that the DSN never reaches a config file, that the
sniper refuses a family it cannot carry through to a contender, or that the
pruner's warm-up threshold is still expressible in the unit our callback reports
in. Those are the claims this file keeps true between runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import referenced_names

from taxi_mlops.data.config import load_yaml, repo_root
from taxi_mlops.tuning import fit as fit_mod
from taxi_mlops.tuning import space, storage

pytestmark = pytest.mark.unit

TUNING_CFG = load_yaml("configs/tuning.yaml")
AUTOML_CFG = load_yaml("configs/automl.yaml")
SCRIPTS = ("automl_scout.py", "optuna_sniper.py", "automl_refit.py", "sniper_resume_drill.py")


# ------------------------------------------------------------------- space ----


def test_a_centre_inside_the_range_narrows_the_search_around_it():
    knob = space.Knob("learning_rate", "float", 0.01, 0.30, log=True, span=3.0)
    low, high = knob.bounds(0.06)
    assert (low, high) == pytest.approx((0.02, 0.18))


def test_a_centre_outside_the_absolute_range_is_overruled_by_the_range():
    """FLAML found `num_leaves: 6` on an internal subsample in a real smoke run.

    Centring on it would have produced low >= high, i.e. an empty or inverted
    search. The absolute range wins, and the space is searched in full.
    """
    knob = space.Knob("num_leaves", "int", 31, 1023, log=True, span=3.0)
    assert knob.bounds(6) == (31, 1023)


def test_a_knob_with_no_meaningful_centre_says_so_rather_than_centring_on_zero():
    lambdas = [k for k in space.LGBM_KNOBS if k.name.startswith("lambda_")]
    assert lambdas, "the regularisation knobs disappeared from the LightGBM space"
    for knob in lambdas:
        assert not knob.centred
        assert knob.bounds(0.0) == (knob.low, knob.high)


def test_the_scouts_flaml_spelling_is_translated_and_not_silently_dropped():
    """`min_child_samples` IS `min_data_in_leaf`; an untranslated centre is no centre."""
    centre = space.centre_from_scout("lgbm", {"min_child_samples": 120, "learning_rate": 0.2})
    assert centre["min_data_in_leaf"] == 120.0
    assert centre["learning_rate"] == 0.2


def test_a_knob_the_scout_said_nothing_about_falls_back_to_its_declared_default():
    centre = space.centre_from_scout("lgbm", {})
    for knob in space.LGBM_KNOBS:
        assert centre[knob.name] == knob.default


def test_the_sniper_refuses_a_family_it_cannot_refit_and_log():
    """`rf` and `extra_tree` are in the scout's config on purpose and stop here."""
    for family in ("rf", "extra_tree"):
        assert family in AUTOML_CFG["estimator_list"]
        with pytest.raises(space.UnsupportedFamilyError) as raised:
            space.check_family(family)
        assert family in str(raised.value)


def test_every_family_the_sniper_supports_is_one_the_scout_can_actually_propose():
    """A supported family the scout may never name is a code path nothing reaches."""
    for family in space.SUPPORTED_FAMILIES:
        assert family in AUTOML_CFG["estimator_list"], f"{family} is not in configs/automl.yaml"


def test_the_objective_is_never_a_searchable_knob():
    """DR-03 gives this track hyperparameters, not the question being asked.

    `l1` is the loss because KPI-09 is MAE in minutes (M2-S2 argued it from the
    metric). A sniper that could swap the objective would be optimising a
    different promise and reporting it against this one.
    """
    for knobs in space.KNOBS.values():
        names = {knob.name for knob in knobs}
        assert not names & {"objective", "metric", "eval_metric"}


# ----------------------------------------------------------------- storage ----


def _env(tmp_path: Path, **values: str) -> Path:
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


def test_the_dsn_is_assembled_from_env_and_names_psycopg_explicitly(tmp_path):
    """SQLAlchemy's bare `postgresql://` means psycopg2, which this project has not got."""
    url = storage.storage_url(env_file=_env(tmp_path, OPTUNA_DB_USER="o", OPTUNA_DB_PASSWORD="p"))
    assert url == "postgresql+psycopg://o:p@127.0.0.1:5432/optuna"


def test_a_missing_credential_names_the_recipe_that_creates_it(tmp_path):
    with pytest.raises(storage.StorageConfigError) as raised:
        storage.storage_url(env_file=_env(tmp_path, OPTUNA_DB_USER="o"))
    message = str(raised.value)
    assert "platform_secrets.sh" in message and "postgres_databases.sh" in message


def test_what_a_log_may_say_about_the_storage_contains_no_password(tmp_path):
    env = _env(tmp_path, OPTUNA_DB_USER="o", OPTUNA_DB_PASSWORD="hunter2")
    assert "hunter2" in storage.storage_url(env_file=env)
    assert "hunter2" not in storage.describe()
    assert "redacted" in storage.describe()


def test_no_config_under_configs_carries_a_connection_string():
    """`configs/tuning.yaml` says `storage: postgres` and that must stay a WORD.

    A DSN in a config is a credential in git. The check is over every config, not
    just tuning.yaml, because the next stub will be called something else — the
    same shape as M3-S1's one-home-for-the-gate test.
    """
    offenders = []
    for path in sorted((repo_root() / "configs").glob("*.yaml")):
        body = path.read_text()
        for marker in ("postgresql://", "postgresql+", "psycopg://", "@localhost:5432"):
            if marker in body:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, offenders


def test_a_study_carries_its_milestone_namespace_and_refuses_to_go_without_one():
    assert storage.study_name("m3", "sniper-v1") == "m3-sniper-v1"
    with pytest.raises(storage.StorageConfigError):
        storage.study_name("", "sniper-v1")


def test_the_configured_study_namespace_is_the_milestone(tmp_path):
    """Gotcha #17, pinned: one Postgres, so M7's retune must not land in M3's study."""
    assert TUNING_CFG["study_namespace"] == "m3"


# --------------------------------------------------------- pruner / reporter ----


def test_the_pruners_warmup_is_reachable_in_the_unit_our_callback_reports_in():
    """`n_warmup_steps` counts whatever the reporter counts — here, boosting rounds.

    These two numbers are twins: `taxi_mlops.tuning.fit` reports every
    REPORT_EVERY_ROUNDS rounds, so a warm-up threshold that is not a multiple of
    that stride is a threshold no report ever lands on, and the first prunable
    step silently moves. Change one, change the other.
    """
    warmup = int(TUNING_CFG["pruner"]["n_warmup_steps"])
    assert warmup % fit_mod.REPORT_EVERY_ROUNDS == 0 or warmup < fit_mod.REPORT_EVERY_ROUNDS, (
        f"n_warmup_steps={warmup} vs a {fit_mod.REPORT_EVERY_ROUNDS}-round reporting stride"
    )


def test_the_scout_budget_is_the_one_the_design_review_pinned():
    """DR-01 recorded `time_budget_s: 1800` and explicitly did not edit it."""
    assert AUTOML_CFG["time_budget_s"] == 1800
    assert TUNING_CFG["n_trials"] == 60


@pytest.mark.parametrize("family", space.SUPPORTED_FAMILIES)
def test_a_pruned_trial_really_raises_out_of_the_boosters_callback(family):
    """The pruner is armed, and the proof is that a vote to prune STOPS the fit.

    A 16-trial smoke study finished with **zero** pruned trials. That is a fine
    outcome — nothing was worse than the running median — and terrible evidence,
    because it is exactly what a pruner wired to nothing also looks like. So the
    propagation path is pinned here: report -> should_prune -> TrialPruned, out
    through LightGBM's callback list and XGBoost's `TrainingCallback`, through
    `fit`'s `finally`, to Optuna. Both families, because they are two different
    callback protocols and the live smoke only ever exercised one.

    It runs in a CHILD process for gotcha #37's reason: `fit` calls
    `ensure_openmp()`, which on this host re-execs the interpreter — and
    re-execing pytest restarts the test session in the middle of itself. That is
    not a hypothetical; the first draft of this test did exactly that.
    """
    import subprocess
    import sys

    probe = repo_root() / "tests" / "unit" / "_prune_probe.py"
    done = subprocess.run(
        [sys.executable, str(probe), family], cwd=repo_root(),
        capture_output=True, text=True, check=False, timeout=300,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    last = [line for line in done.stdout.splitlines() if line.startswith(("PRUNED", "NOT_"))][-1]
    outcome, _, reports = last.partition(" ")
    assert outcome == "PRUNED", f"the fit ran to completion despite a vote to prune: {last}"
    assert reports.startswith(f"[{fit_mod.REPORT_EVERY_ROUNDS},") or reports == (
        f"[{fit_mod.REPORT_EVERY_ROUNDS}]"
    ), f"the first report did not land on the configured stride: {reports}"


# ------------------------------------------------------- the story's refusal ----


REGISTRY_API = {
    "register_model",
    "create_model_version",
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "transition_model_version_stage",
    "promote",
}


def test_no_automation_script_can_touch_the_registry():
    """M3-S4 promotes nothing. The gate sees these contenders at S5, or never."""
    for name in SCRIPTS:
        path = repo_root() / "scripts" / name
        overlap = referenced_names(path) & REGISTRY_API
        assert not overlap, f"{name} names the registry API: {sorted(overlap)}"
    for module in ("storage.py", "space.py", "fit.py"):
        path = repo_root() / "src" / "taxi_mlops" / "tuning" / module
        assert not referenced_names(path) & REGISTRY_API, module


def test_no_automation_script_reads_the_test_month():
    """DR-05: TEST is opened once per contender, at S5, by the gate."""
    for name in SCRIPTS:
        body = (repo_root() / "scripts" / name).read_text()
        assert '"test"' not in body.replace('"test_month"', ""), (
            f"{name} appears to load the test split — the gate has one measurement and "
            "this story may not spend it"
        )


# ------------------------------------------------- D-002's third-consumer claim ----


def test_the_optuna_database_arrived_by_one_line_and_one_additive_key():
    """M1-S5 claimed a new database costs exactly that; M3-S4 is the third test of it."""
    databases = (repo_root() / "scripts" / "postgres_databases.sh").read_text()
    secrets = (repo_root() / "scripts" / "platform_secrets.sh").read_text()
    assert databases.count('"optuna:${OPTUNA_DB_USER:-optuna}:OPTUNA_DB_PASSWORD"') == 2, (
        "the DATABASES list is declared twice (once before .env is sourced, once after) "
        "and both copies are twins — a database in one and not the other is worse than none"
    )
    assert "OPTUNA_DB_USER=optuna OPTUNA_DB_PASSWORD=" in secrets, "no ADDITIVE entry"
    assert "OPTUNA_DB_USER OPTUNA_DB_PASSWORD" in secrets, "not promoted to REQUIRED"
