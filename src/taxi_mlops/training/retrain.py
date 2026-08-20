"""The retrain challenger: the champion's configuration, re-derived at its own scale.

M7's loop is *drift seen -> retrain -> challenger -> the gate decides*. This module
owns the second arrow, and it exists because of one finding.

**F-020, in one sentence.** The tuned configuration that became the champion was
CHOSEN on 15% of train and APPLIED unchanged at 100%, including knobs whose
meaning is a row count. `min_data_in_leaf: 1293` is a leaf floor of 1 row in 5,105
on the 6,598,113-row search sample and 1 in 34,020 on the 43,987,422-row refit —
**the same integer is ~6.7x less regularising at the scale it was finally fitted
at**, and nothing re-derived it. The rounds budget travelled the same way and by
construction rather than by choice: `scripts/automl_refit.py` reads
`num_boost_round` from the sniper verdict's `max_rounds`, which the sniper wrote
as its own PER-TRIAL SEARCH CAP at 15% (800), and both full-data refits then ran
into it (800/800 and 791/800).

So a retrain that re-fitted the champion's params verbatim would inherit both
defects and would report its result as though it were the champion's
configuration at full scale. It is not. This module makes the transfer explicit:

1. **Count-scaled knobs are rescaled** to the fraction they expressed at the
   scale they were chosen at (`COUNT_SCALED`). A knob is on that list only if its
   LightGBM meaning is literally "a number of rows"; everything else — learning
   rate, leaf count, feature/bagging fractions, regularisation, category
   smoothing — is scale-invariant in the sense that matters here and is passed
   through untouched. Guessing which side a knob falls on is not allowed: the
   list carries a reason per entry and a test walks it.

2. **The round budget is RE-DERIVED, and the derivation is "let early stopping
   decide"** (`round_budget`). The re-derived cap is a COMPUTE bound, not a model
   choice, and the fit REPORTS whether the cap bound it. That report is the whole
   point: the champion's own refit stopped at 791/800 with the cap in play, which
   is indistinguishable in a results table from a fit that converged. A cap that
   binds is F-015's truncation; a cap that does not is a budget nobody spent.

**What this module does NOT decide.** Not the training window (the settled 2019
months, from `configs/train.yaml`, unchanged — a window that swallows 2020 changes
what the holdout MEASURES and is an ARCH/PO question, never an executor's edit).
Not the gate, its floor, or its bar: the resolved config's every block except
`model` is copied from `configs/train.yaml` byte-for-byte and a test asserts it,
so this file cannot become a second home for a threshold (F-013's rule, applied to
a config this program GENERATES rather than one a human edits). Not the alias:
`retrain()` never promotes, and the promoting caller is `make train`'s path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..data.config import repo_root

#: LightGBM knobs whose value IS a row count, with the reason each one is here.
#: Rescaling anything else would be a change of model rather than a change of
#: scale — `num_leaves` at 44M rows means what it meant at 6.6M, and multiplying
#: it by 6.67 would be inventing a different model and calling it a transfer.
COUNT_SCALED: dict[str, str] = {
    "min_data_in_leaf": (
        "the minimum number of TRAINING ROWS a leaf may hold. Its regularising "
        "strength is the FRACTION of the dataset it represents, so the same "
        "integer is weaker on more rows — this is F-020's own example"
    ),
    "min_data_in_bin": (
        "the minimum number of rows per histogram bin — the same argument one "
        "level down, on the feature binning rather than on the tree"
    ),
    "min_sum_hessian_in_leaf": (
        "a sum over the rows in a leaf. Under objective `l1` each row "
        "contributes a constant hessian, so this sum is a row count wearing a "
        "float's clothes"
    ),
}

#: Knobs read from the champion's run that are NOT hyperparameters at all — they
#: are what the fitting script recorded ABOUT the fit. Passing `best_iteration`
#: into LightGBM as a parameter would be silently ignored; passing `train_rows`
#: would not be. Both are dropped by name, loudly.
NOT_HYPERPARAMETERS = frozenset(
    {"best_iteration", "family", "feature_set", "n_features", "train_rows",
     "sample_fraction", "num_boost_round", "early_stopping_rounds"}
)

#: How much headroom the re-derived round budget gets over the budget the champion
#: was fitted under. It is a COMPUTE bound and never a bar: the fit stops when
#: early stopping says so, and this number only decides how long we are willing to
#: wait for that to happen. Three, because the champion's own refit ended at
#: 791 of 800 — the cap was in play, so a re-derivation that merely nudged it
#: could bind again and prove nothing; and because the rescaled leaf floor is ~6.7x
#: more regularising, which makes each tree weaker and MORE rounds the expected
#: direction. The honest cost is wall-clock and it is reported, not hidden.
ROUND_BUDGET_HEADROOM = 3


class RetrainError(RuntimeError):
    """The challenger cannot be built honestly. Names the fix, never a default."""


@dataclass
class Provenance:
    """Where every number in the challenger's configuration came from.

    Recorded rather than reconstructed: "the champion's params, rescaled" is a
    claim about three artifacts (a registry version, its run, and the tracked
    JSON of the search that produced it) and a reader who cannot see all three
    cannot check it.
    """

    champion_version: str
    champion_run_id: str
    champion_run_name: str
    feature_set: str
    tuned_params: dict[str, Any]
    #: The row count the count-scaled knobs were CHOSEN at (the sniper's sample),
    #: and the record that says so. None when the champion did not come from a
    #: sampled search — see `resolve_champion_configuration`.
    chosen_at_rows: int | None
    chosen_at_source: str | None
    #: The per-trial round cap the champion's refit inherited, and its record.
    inherited_round_cap: int | None
    inherited_round_cap_source: str | None
    notes: list[str] = field(default_factory=list)


def rescale(
    params: dict[str, Any], *, chosen_at_rows: int | None, target_rows: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rescale the count-scaled knobs from the scale they were CHOSEN at to `target_rows`.

    Returns the new params and one row per knob describing the move — including
    the knobs that were left alone, because "we considered it and it does not
    scale" and "we never looked at it" are different statements and only the
    first belongs in a record.

    `chosen_at_rows is None` means the configuration was chosen at the scale it is
    being fitted at (or by hand), so there is no transfer to make. That is a
    legitimate no-op and it is REPORTED as one; it is not silence.
    """
    if target_rows <= 0:
        raise RetrainError(f"target_rows must be positive, got {target_rows}")
    out = dict(params)
    moves: list[dict[str, Any]] = []
    factor = None if not chosen_at_rows else target_rows / chosen_at_rows
    for knob, value in sorted(params.items()):
        if knob not in COUNT_SCALED:
            continue
        if factor is None:
            moves.append({"knob": knob, "from": value, "to": value, "factor": None,
                          "reason": "no scale transfer: the value was chosen at the "
                                    "scale it is being fitted at"})
            continue
        scaled = value * factor
        # An integer knob stays an integer, rounded and floored at 1: LightGBM
        # takes `min_data_in_leaf` as an int, and a leaf floor of 0 would turn the
        # knob off rather than scale it.
        new = max(1, round(scaled)) if isinstance(value, int) else scaled
        out[knob] = new
        # The three ratios that make the finding legible, all as "1 row in N":
        # what the knob MEANT where it was chosen, what it would have meant here
        # unchanged, and what it means after the transfer. The first and the third
        # are equal by construction — that IS the transfer — and the second is
        # F-020's number.
        moves.append({
            "knob": knob, "from": value, "to": new, "factor": factor,
            "one_row_in_at_choice": (chosen_at_rows / value) if value else None,
            "one_row_in_if_unchanged": (target_rows / value) if value else None,
            "one_row_in_after": (target_rows / new) if new else None,
            "reason": COUNT_SCALED[knob],
        })
    return out, moves


def round_budget(inherited_cap: int | None, configured: int) -> tuple[int, str]:
    """Re-derive the round budget instead of inheriting a search cap. F-020, half two.

    The rule, and it is a rule about who DECIDES rather than about a number: the
    budget must be large enough that early stopping is what ends the fit. So the
    re-derived cap is `ROUND_BUDGET_HEADROOM` times whatever cap the champion's
    refit ran under — and, since a cap can only ever be too small, never smaller
    than `configs/train.yaml: model.num_boost_round`.

    When no inherited cap is known the configured budget stands and says so: this
    function does not invent headroom for a fit whose budget nobody borrowed.
    """
    if inherited_cap is None:
        return configured, (
            f"no inherited search cap: the configured budget of {configured} rounds "
            "stands. There is nothing to re-derive."
        )
    derived = max(configured, inherited_cap * ROUND_BUDGET_HEADROOM)
    return derived, (
        f"re-derived: {inherited_cap} (the sniper's PER-TRIAL cap at its sample, which "
        f"the champion's refit inherited and then ran into) x {ROUND_BUDGET_HEADROOM} = "
        f"{derived}. It is a compute bound, not a model choice — the fit reports "
        "whether early stopping or the cap ended it."
    )


def resolve_champion_configuration(
    train_cfg: dict[str, Any], *, records_dir: str = "automation/runs/m3s4"
) -> Provenance:
    """Read what is SERVING and the scale its configuration was chosen at.

    Three artifacts, in this order, and the ORDER is the provenance:

    1. the registry alias -> the champion VERSION (never `search_model_versions`,
       whose `aliases` come back empty on server 3.15.1 — M2-S3);
    2. the version's RUN -> the hyperparameters actually fitted;
    3. the tracked refit record whose `run_id` IS that run -> the study that chose
       them -> the sniper record -> the SAMPLE the count-scaled knobs mean.

    Step 3 can legitimately find nothing: a champion fitted by hand at full scale
    has no sampled search behind it and therefore no scale transfer to make. That
    is recorded as a note and the rescale becomes an explicit no-op. What is NOT
    allowed is assuming a sample fraction — a wrong divisor produces a plausible
    configuration nobody can check.
    """
    import mlflow

    from . import tracking

    tracking.configure(train_cfg["mlflow"])
    client = mlflow.MlflowClient()
    reg = train_cfg["registry"]
    version = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    run = client.get_run(version.run_id)

    tuned: dict[str, Any] = {}
    dropped: list[str] = []
    for key, raw in sorted(run.data.params.items()):
        if key in NOT_HYPERPARAMETERS:
            dropped.append(key)
            continue
        tuned[key] = _number(raw)

    feature_set = (version.tags or {}).get("feature_set") or run.data.params.get("feature_set")
    if not feature_set:
        raise RetrainError(
            f"champion version {version.version} carries no `feature_set` tag and its run "
            "names no feature set. A retrain that guessed would build a matrix the model "
            "cannot eat — the same refusal `make shadow` makes about an untagged version."
        )

    notes = [
        f"champion version {version.version} -> run {version.run_id} ({run.info.run_name})",
        f"hyperparameters read from the RUN, not from a config file; dropped as "
        f"not-hyperparameters: {', '.join(dropped) or 'none'}",
    ]

    chosen_at, chosen_src, cap, cap_src = _search_scale(str(version.run_id), records_dir, notes)
    return Provenance(
        champion_version=str(version.version),
        champion_run_id=str(version.run_id),
        champion_run_name=str(run.info.run_name),
        feature_set=str(feature_set),
        tuned_params=tuned,
        chosen_at_rows=chosen_at,
        chosen_at_source=chosen_src,
        inherited_round_cap=cap,
        inherited_round_cap_source=cap_src,
        notes=notes,
    )


def _search_scale(
    run_id: str, records_dir: str, notes: list[str]
) -> tuple[int | None, str | None, int | None, str | None]:
    """Follow refit-record -> study -> sniper-record for the scale and the cap."""
    root = repo_root() / records_dir
    refit = None
    for path in sorted(root.glob("refit-*.json")) if root.exists() else []:
        row = json.loads(path.read_text())
        if str(row.get("run_id")) == run_id:
            refit = (path, row)
            break
    if refit is None:
        notes.append(
            f"no tracked refit record under {records_dir} names run {run_id}, so this "
            "champion did not come from a sampled search: there is no scale transfer to "
            "make and the count-scaled knobs are passed through unchanged."
        )
        return None, None, None, None

    refit_path, refit_row = refit
    study = refit_row.get("study")
    sniper_path = root / f"sniper-{refit_path.stem.split('-', 1)[1]}.json"
    if not sniper_path.exists():
        raise RetrainError(
            f"{refit_path} names study {study!r} but {sniper_path} does not exist. The "
            "scale the count-scaled knobs were chosen at is only knowable from the "
            "sniper's own record, and F-020 is the finding that assuming it produces a "
            "plausible configuration nobody can check."
        )
    sniper = json.loads(sniper_path.read_text())
    if sniper.get("study") != study:
        raise RetrainError(
            f"{sniper_path} records study {sniper.get('study')!r}, not {study!r}"
        )
    rows = int(sniper["train_rows"])
    cap = int(sniper["max_rounds"])
    notes.append(
        f"scale: {refit_path.relative_to(repo_root())} -> study {study!r} -> "
        f"{sniper_path.relative_to(repo_root())}: chosen on {rows:,} rows "
        f"(sample_fraction {sniper.get('sample_fraction')}), per-trial cap {cap} rounds"
    )
    return rows, str(sniper_path.relative_to(repo_root())), cap, str(
        sniper_path.relative_to(repo_root())
    )


def _number(raw: str) -> Any:
    """MLflow stores every param as a string. Give it back its type, or leave it."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    return int(value) if value.is_integer() and "." not in raw and "e" not in raw.lower() \
        else value


#: Every top-level block of the resolved config that MUST be identical to
#: `configs/train.yaml`. The `model` block is the one thing a retrain changes; the
#: gate, its floor, its bar, the training window, the feature set pointer, the
#: registry and the tracking server are not this file's to re-decide, and a
#: generated config that could quietly carry a different bar would be exactly the
#: second home F-013 deleted.
COPIED_VERBATIM = ("data", "target", "features", "baselines", "evaluate", "gate",
                   "registry", "mlflow")


def build_config(
    train_cfg_raw: dict[str, Any],
    provenance: Provenance,
    *,
    target_rows: int,
    name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Synthesize the retrain's training config. Returns (config, the record of how).

    `train_cfg_raw` is the RAW `configs/train.yaml` (not the feature-resolved one):
    the output is written back as YAML and read by the ordinary loader, so it must
    carry the same `features: {version, registry}` pointer rather than an expanded
    column list — which `sets.resolve` would refuse anyway.
    """
    model = dict(train_cfg_raw["model"])
    base = dict(model["lightgbm"])
    tuned = {k: v for k, v in provenance.tuned_params.items()}

    scaled, moves = rescale(tuned, chosen_at_rows=provenance.chosen_at_rows,
                            target_rows=target_rows)
    rounds, rounds_note = round_budget(provenance.inherited_round_cap,
                                       int(model["num_boost_round"]))

    # The champion's tuned params sit ON TOP of the configured base, never instead
    # of it: `objective`, `metric`, `num_threads`, `seed`, `deterministic` and
    # `verbose` are this program's settings and were never searched. A tuned dict
    # used as the whole param set would silently drop `objective: l1` and fit a
    # different loss from the one KPI-09 measures.
    merged = {**base, **scaled}

    model["lightgbm"] = merged
    model["num_boost_round"] = rounds
    model["name"] = name

    cfg = {block: train_cfg_raw[block] for block in COPIED_VERBATIM}
    cfg["model"] = model

    record = {
        "challenger": name,
        "target_rows": target_rows,
        "champion": {
            "version": provenance.champion_version,
            "run_id": provenance.champion_run_id,
            "run_name": provenance.champion_run_name,
            "feature_set": provenance.feature_set,
        },
        "rescale": {
            "chosen_at_rows": provenance.chosen_at_rows,
            "chosen_at_source": provenance.chosen_at_source,
            "factor": None if not provenance.chosen_at_rows
            else target_rows / provenance.chosen_at_rows,
            "moves": moves,
            "count_scaled_knobs": sorted(COUNT_SCALED),
        },
        "round_budget": {
            "inherited_cap": provenance.inherited_round_cap,
            "inherited_cap_source": provenance.inherited_round_cap_source,
            "configured": int(train_cfg_raw["model"]["num_boost_round"]),
            "headroom": ROUND_BUDGET_HEADROOM,
            "derived": rounds,
            "note": rounds_note,
        },
        "params": {"base": base, "tuned": tuned, "merged": merged},
        "provenance_notes": provenance.notes,
    }
    return cfg, record


def write_config(cfg: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# GENERATED by taxi_mlops.training.retrain — DO NOT EDIT, and do not move\n"
        "# it under configs/. Every block except `model` is copied verbatim from\n"
        "# configs/train.yaml (retrain.COPIED_VERBATIM); the `model` block is the\n"
        "# champion's own tuned params with F-020's count-scaled knobs rescaled to\n"
        "# this fit's row count and the round budget re-derived. The record beside\n"
        "# this file says where every number came from.\n"
    )
    path.write_text(header + yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False))
    return path


def print_plan(record: dict[str, Any]) -> None:
    """The whole transfer, before a row is read. A plan nobody can read is a guess."""
    print("=" * 78)
    print(f"[retrain] challenger : {record['challenger']}")
    ch = record["champion"]
    print(f"[retrain] champion   : version {ch['version']} ({ch['run_name']}, run "
          f"{ch['run_id'][:12]}…), feature set {ch['feature_set']}")
    rs = record["rescale"]
    if rs["chosen_at_rows"]:
        print(f"[retrain] F-020 (1)  : count-scaled knobs chosen on {rs['chosen_at_rows']:,} "
              f"rows, fitting on {record['target_rows']:,} -> factor {rs['factor']:.4f} "
              f"({rs['chosen_at_source']})")
    else:
        print("[retrain] F-020 (1)  : no sampled search behind this champion — no scale "
              "transfer to make")
    for move in rs["moves"]:
        if move["factor"] is None:
            print(f"[retrain]              {move['knob']}: {move['from']} (unchanged)")
        else:
            print(f"[retrain]              {move['knob']}: {move['from']} -> {move['to']} "
                  f"— 1 row in {move['one_row_in_at_choice']:,.0f} where it was chosen; "
                  f"unchanged here it would be 1 in {move['one_row_in_if_unchanged']:,.0f} "
                  f"(F-020); rescaled it is 1 in {move['one_row_in_after']:,.0f}")
    rb = record["round_budget"]
    print(f"[retrain] F-020 (2)  : rounds {rb['configured']} configured / "
          f"{rb['inherited_cap']} inherited -> {rb['derived']}")
    print(f"[retrain]              {rb['note']}")
    untouched = sorted(k for k in record["params"]["tuned"] if k not in COUNT_SCALED)
    print(f"[retrain] passed through unchanged (not row counts): {', '.join(untouched)}")
    print("=" * 78)
