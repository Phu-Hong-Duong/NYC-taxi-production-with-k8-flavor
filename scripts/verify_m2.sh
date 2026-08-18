#!/usr/bin/env bash
# verify_m2.sh — the M2 gate, executable. BLUEPRINT §9/M2, quoted:
#
#   "As v1's M2 (baseline, LightGBM v1, signature, promotion gate red-teamed with
#    a hobbled model) + DA error-analysis memo (where does it fail: zones? hours?
#    long trips?). The memo's segment queries also become a Metabase
#    error-segment board [v2.5] ... Accept when: v1's M2 gate AND the memo cites
#    specific segments with numbers AND the error-segment board renders and is
#    linked from the memo. Show: refusal transcript + memo + board."
#
# Design rules inherited from verify_m0.sh and verify_m1.sh, and one new one:
#
#   1. Every check observes the THING, not a proxy. "docs/promotion_gate_m2.md
#      contains the word REFUSE" is a proxy; "the numbers written in that
#      transcript, replayed through the gate code that is on disk right now,
#      still produce REFUSE" is the thing — and it is the only version that goes
#      red when somebody loosens `configs/train.yaml: gate`.
#   2. Every sub-check asserts a POSITIVE count or a matched line. M1's gate
#      taught this the expensive way: a check wired to no sensor is a green
#      light. Here the law is applied one level up as well — each Python leg is
#      required to EMIT a minimum number of verdicts, so a leg that dies on
#      import fails loudly instead of contributing zero silent passes.
#   3. Probes stay impatient (60 s at most); nothing here deploys, so nothing
#      here waits patiently. The whole gate is seconds, not minutes: it re-reads
#      and re-reconciles, it never re-fits. Re-fitting the champion inside the
#      gate would mint MLflow runs on every verification, and a gate with side
#      effects on the registry it is checking is not a gate.
#
# What it deliberately does NOT do: run `make train`. The champion is a
# REGISTERED artifact; this gate's job is to check what was promoted, not to
# promote again. The gate's ability to refuse is proven by replaying M2-S3's
# recorded transcripts through the live decision function (§2), which costs
# milliseconds and catches the thing a re-run could not — a threshold edited
# after the fact.
#
# MEASURED 2026-08-17 (M2-S5): ~30 s green end to end on this machine.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m2.sh          (via `make verify-m2`)
#        scripts/verify_m2_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
METABASE_URL="${METABASE_URL:-http://localhost:3030}"

FAILS=0
CONSUMED=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# Reads `PASS|msg` / `FAIL|msg` lines from a Python leg and counts them here, so
# the tally lives in exactly one place. Anything else is printed as a note.
# ALWAYS call as `consume < <(...)`: a pipeline would run this in a subshell and
# throw the counters away at the closing brace.
consume() {
  CONSUMED=0
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS|"*) pass "${line#PASS|}"; CONSUMED=$((CONSUMED + 1)) ;;
      "FAIL|"*) fail "${line#FAIL|}"; CONSUMED=$((CONSUMED + 1)) ;;
      *) note "$line" ;;
    esac
  done
}

# Rule 2, applied to the checker itself.
expect_verdicts() {
  local want="$1" label="$2"
  if [[ "$CONSUMED" -lt "$want" ]]; then
    fail "$label emitted $CONSUMED verdict(s), expected at least $want — the check did not run"
  fi
}

# --------------------------------------- 1. the registry holds the champion ---
section "1. registry: the champion exists, with a signature and the verdict it was promoted on"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path


def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    from taxi_mlops.features import quote_time
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]

    # Read through get_model_version_by_alias and never off search_model_versions:
    # on server 3.15.1 the latter returns versions whose `aliases` field is EMPTY
    # (M2-S3), so a champion resolved that way is a champion resolved by guessing.
    try:
        mv = client.get_model_version_by_alias(name, alias)
    except Exception as exc:
        no(f"models:/{name}@{alias} does not resolve ({type(exc).__name__}) — nothing is champion")
        raise SystemExit(0)
    ok(f"models:/{name}@{alias} resolves to version {mv.version} (run {mv.run_id[:12]}…)")

    tags = dict(mv.tags or {})
    # The verdict travels ON the version: "what was this measured against?" is a
    # question the registry answers, not one you answer from a transcript.
    #
    # M3-S5 note — why the FLOOR is asserted by property and not by name. Until
    # this story these three were literals, and `gate_floor` read
    # "baseline-group-median". That was the M2 floor; M3-S1 replaced it with a
    # NEW name (F-010, `…-od-fallback`) precisely because the config legislated
    # that a floor change is a new name and never an edit — so the first
    # legitimate champion transition turned this leg RED for doing the right
    # thing. A literal that goes red on every correct promotion teaches the next
    # session to edit assertions, which is how a guard becomes a formality (the
    # same argument M3-S5 applied to the two feature tests). What holds at EVERY
    # champion is the property below, and it is stricter than the literal was:
    # the name must be one `baselines.fit_floor` can actually rebuild — a floor
    # nobody can re-fit is a number, not a bar — which also excludes
    # `baseline-constant-median`, the flattering floor `gate.decide` refuses.
    expected = {"gate_verdict": "PROMOTE", "gate_holdout_split": "test"}
    wrong = {k: (tags.get(k), v) for k, v in expected.items() if tags.get(k) != v}
    from taxi_mlops.training.baselines import GroupMedian, GroupMedianODFallback
    honest_floors = {GroupMedian.name, GroupMedianODFallback.name}
    floor_name = tags.get("gate_floor")
    if floor_name not in honest_floors:
        wrong["gate_floor"] = (floor_name, f"one of {sorted(honest_floors)}")
    if wrong:
        no(f"the champion's gate tags are wrong or missing: {wrong}")
    else:
        ok(f"the version carries its verdict: PROMOTE, floor={floor_name} "
           f"(re-fittable by baselines.fit_floor), holdout=test")

    # ...and the floor named on the VERSION must be the floor the published rows
    # were actually scored beside. F-012 makes `make predictions` re-fit the
    # champion's own `gate_floor` rather than the config's; this is the other end
    # of that wire, and it is a cross-system check the literal could not make.
    try:
        manifest = json.loads(Path("data/predictions/predictions.json").read_text())
        published_floor = manifest["floor"]["name"]
        stamped_floor = manifest["model"]["gate_tags"]["gate_floor"]
    except (OSError, KeyError, ValueError) as exc:
        no(f"predictions.json does not name the floor it published against ({exc})")
    else:
        if published_floor == stamped_floor == floor_name:
            ok(f"the published rows were scored beside the champion's OWN floor: "
               f"{floor_name} on the version, in the manifest, and re-fitted (F-012)")
        else:
            no(f"floor mismatch — version says {floor_name!r}, the manifest stamped "
               f"{stamped_floor!r} and published {published_floor!r}")

    try:
        challenger = float(tags["gate_challenger_mae"])
        floor = float(tags["gate_floor_mae"])
        observed = float(tags["gate_observed_pct"])
        required = float(tags["gate_required_pct"])
    except (KeyError, ValueError) as exc:
        no(f"the champion carries no readable gate numbers ({exc}) — an unfalsifiable promotion")
    else:
        margin = 100.0 * (floor - challenger) / floor
        if abs(margin - observed) < 0.01 and observed >= required > 0:
            ok(f"both numbers are ON the version and re-derive: {challenger:.4f} vs "
               f"{floor:.4f} min = +{margin:.2f}% (required >= {required:.2f}%)")
        else:
            no(f"the version's numbers do not re-derive: {challenger} vs {floor} gives "
               f"{margin:+.2f}%, the tag says {observed:+.2f}% (required {required})")

    if tags.get("metric_source") == "taxi_mlops.training.evaluate":
        ok("the version names its metric source: taxi_mlops.training.evaluate (gotcha #15)")
    else:
        no(f"metric_source tag is {tags.get('metric_source')!r}, expected the evaluator")

    # F-009: `mlflow.lightgbm.load_model("models:/<name>@<alias>")` raises on this
    # server because MLflow 3 writes logged-model artifacts under models/m-<id>/
    # while the version's `source` still says runs:/<run>/model. get_model_info
    # resolves the alias to the address the bytes are actually at, which is the
    # same step src/taxi_mlops/training/score.py takes. NOTE: without
    # tracking.configure() above, this call fails with a message about MLmodel
    # that reads exactly like F-009 but is really absent MinIO credentials.
    info = mlflow.models.get_model_info(f"models:/{name}@{alias}")
    configured = quote_time.feature_names(cfg["features"])
    if info.signature is None:
        no("the champion has NO signature — M5 would discover its input schema by crashing")
    else:
        got = [c.name for c in info.signature.inputs.inputs]
        if got == configured:
            ok(f"the champion carries a signature over exactly the configured features: {', '.join(got)}")
        else:
            no(f"the signature's inputs {got} are not configs/train.yaml's {configured}")
    if info.saved_input_example_info:
        ok("the champion carries an input example (the MLE charter refuses a version without one)")
    else:
        no("the champion has no input example")

    run = client.get_run(mv.run_id)
    exp = client.get_experiment(run.info.experiment_id)
    # Also a property since M3-S5, and for the same reason as the floor above:
    # the champion legitimately came from `m3-automl` (M3-S4's full-data refit),
    # not from `configs/train.yaml`'s current `experiment`. What gotcha #17
    # actually demands is that the run be FINISHED and live in a NAMESPACED
    # experiment — never MLflow's `Default`, where a collision has no name.
    namespaced = re.fullmatch(r"m\d+-[a-z0-9-]+", exp.name or "") is not None
    if run.info.status == "FINISHED" and namespaced:
        ok(f"the champion's run is FINISHED and lives in a namespaced experiment "
           f"{exp.name!r} (gotcha #17)")
    else:
        no(f"the champion's run is {run.info.status} in experiment {exp.name!r} "
           f"(namespaced={namespaced})")

    # The one thing that must never be true of a champion.
    #
    # Read by VALUE, not by presence — M3-S5's finding. Every run this program
    # writes carries `do_not_promote`, and the value is what says which way:
    # `"yes — 15% sample (F-008)"` on a scout trial, `"no — full-data fit; the
    # gate sees it at M3-S5"` on the four bake-off contenders. A presence test
    # read the second one as a refusal and called the legitimately promoted
    # champion hobbled. `red_team` and `hobbled` carry descriptive values
    # (`"M2-S3"`, `"shuffled-target"`), so one rule covers both families: a mark
    # counts unless its value says no.
    hobbled = [k for k in ("red_team", "hobbled", "do_not_promote")
               if k in run.data.tags
               and not str(run.data.tags[k]).strip().lower().startswith("no")]
    if hobbled:
        marks = {k: run.data.tags[k] for k in hobbled}
        no(f"the CHAMPION run is marked {marks} — a hobbled model is aliased as champion")
    else:
        ok(f"the champion's run carries no live red_team/hobbled/do_not_promote mark "
           f"(do_not_promote={run.data.tags.get('do_not_promote')!r})")
except SystemExit:
    raise
except Exception as exc:  # noqa: BLE001 — a broken check must fail loudly, not silently
    print(f"FAIL|the registry check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the registry check"

# ------------------------------ 2. the gate can say no, and has not been loosened
section "2. the gate: M2-S3's transcripts replayed through the gate code on disk NOW"
consume < <(uv run python - 2>/dev/null <<'PY'
import re

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

DOC = "docs/promotion_gate_m2.md"
DOC_M3 = "docs/promotion_gate_m3.md"
try:
    from taxi_mlops.training.evaluate import Metrics
    from taxi_mlops.training.gate import GateError, Incumbent, decide
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")["gate"]

    # The bar itself. Tightening is the MLE's; loosening is a PO fork, ever
    # (CLAUDE.md). These are the values M2-S3 argued for in the config comments,
    # so a quiet edit is a red gate rather than a diff nobody read.
    if float(cfg["min_improvement_pct"]) >= 2.0:
        ok(f"the KPI-09 margin bar is still >= 2.00% (configs/train.yaml: {cfg['min_improvement_pct']})")
    else:
        no(f"the margin bar has been LOOSENED to {cfg['min_improvement_pct']}% — that is a PO fork, not an edit")
    if cfg.get("require_no_kpi10_regression"):
        ok("the KPI-10 no-regression condition is still armed (it can refuse what the margin admits)")
    else:
        no("require_no_kpi10_regression is off — the rider-facing condition was switched off")
    # M3-S1 (F-010) changed this floor, and the change is a TIGHTENING: the same
    # lookup with one more backoff level, measured lower on the same month. The
    # pin below moved with it in the same PR — never weakened, and the sub-check
    # after the replays proves the DIRECTION from two committed transcripts, so
    # swapping in an easier floor is red rather than a diff nobody read.
    if cfg["floor"] == "baseline-group-median-od-fallback" and cfg["holdout_split"] == "test":
        ok(f"the bar is still an HONEST floor on the untouched holdout ({cfg['floor']}, test)")
    else:
        no(f"the gate now judges against {cfg['floor']!r} on {cfg['holdout_split']!r} — "
           "the flattering floor, a touched month, or a floor nobody argued for")

    # Parse M2-S3's pasted transcripts and replay them. A transcript is evidence
    # about a past run; replaying its numbers through today's decision function
    # is evidence about today's gate. Both are wanted, and only the second can
    # notice that the bar moved after the transcript was written.
    line_re = re.compile(
        r"\[gate\] (challenger|floor)\s*: (\S+)\s+KPI-09 ([\d.]+) min\s+·\s+KPI-10 ([\d.]+)%")
    # A transcript that records an incumbent must be replayed WITH it, or the
    # replay is asking a different question from the one the verdict answered —
    # M3-S1's watched refusal is a REFUSE only because of the incumbent, and a
    # replay that dropped it would have reported PROMOTE and called the doc wrong.
    inc_re = re.compile(
        r"\[gate\] incumbent\s*: version (\S+)\s+KPI-09 ([\d.]+) min\s+·\s+KPI-10 ([\d.]+)%")

    def transcripts(path):
        text = open(path, encoding="utf-8").read()
        rows = int(re.search(r"holdout\s+: \w+ — ([\d,]+) rows", text).group(1).replace(",", ""))
        blocks, current = [], {}
        for line in text.splitlines():
            m = line_re.match(line)
            i = inc_re.match(line)
            if i:
                current["incumbent"] = (i.group(1), float(i.group(2)), float(i.group(3)))
            elif m:
                current[m.group(1)] = (m.group(2), float(m.group(3)), float(m.group(4)))
            elif line.startswith("[gate] VERDICT"):
                current["verdict"] = line.split(":", 1)[1].strip()
                current["doc"] = path
                blocks.append(current)
                current = {}
        return rows, blocks

    rows, blocks = transcripts(DOC)
    rows_m3, blocks_m3 = transcripts(DOC_M3)
    blocks += blocks_m3

    def metrics(triple, split):
        name, mae, within = triple
        return Metrics(contender=name, split=split, n=rows, mae=mae,
                       within_tolerance_rate=within, tolerance_minutes=5.0,
                       rmse=0.0, median_ae=0.0, p90_ae=0.0)

    if not blocks:
        no(f"{DOC} holds no parseable gate transcript — the refusal is not on file")
    replayed = {"REFUSE": 0, "PROMOTE": 0}
    for b in blocks:
        if not {"challenger", "floor", "verdict"} <= b.keys():
            no(f"a transcript block in {b.get('doc', DOC)} is missing one of its two numbers")
            continue
        holdout = cfg["holdout_split"]
        # The floor NAME comes from the block, not from the config: a verdict is
        # replayed against the bar it was actually taken against, or it is not a
        # replay. Since M3-S1 the two legitimately differ — M2's verdicts were
        # argued against `baseline-group-median` and the live gate judges against
        # the stronger `baseline-group-median-od-fallback`. The floor's IDENTITY
        # is guarded separately and unweakened: the pinned name above, the
        # flattering-floor refusal below, and the direction check after this loop.
        block_cfg = {**cfg, "floor": b["floor"][0]}
        version, mae, within = b.get("incumbent", (None, 0.0, 0.0))
        inc = None if version is None else Incumbent(
            version=version, mae=mae, within_tolerance_rate=within, split=holdout,
            source=f"the transcript in {b['doc']}")
        d = decide(metrics(b["challenger"], holdout), metrics(b["floor"], holdout), block_cfg,
                   incumbent=inc)
        if d.verdict == b["verdict"]:
            replayed[d.verdict] = replayed.get(d.verdict, 0) + 1
            ok(f"replayed {b['challenger'][0]}: {b['challenger'][1]:.4f} vs "
               f"{b['floor'][1]:.4f} min -> {d.verdict} ({d.observed_pct:+.2f}%), as the transcript records")
        else:
            no(f"{b['challenger'][0]} was recorded as {b['verdict']} but the gate on disk now says "
               f"{d.verdict} ({d.observed_pct:+.2f}%)")
    if replayed["REFUSE"] >= 1:
        ok(f"the refusal transcript exists WITH BOTH NUMBERS and still refuses ({replayed['REFUSE']} block(s))")
    else:
        no("no transcript in the doc replays to REFUSE — the gate is not watched saying no")
    if replayed["PROMOTE"] >= 1:
        ok(f"the promotion transcript exists with both numbers and still promotes ({replayed['PROMOTE']} block(s))")
    else:
        no("no transcript in the doc replays to PROMOTE")

    # A floor swap is only NOT a loosening if the new floor is harder, so the
    # direction is measured rather than asserted — from two committed transcripts,
    # each carrying a floor measured by the evaluator on the same holdout month.
    m2_floor = min(b["floor"][1] for b in blocks if b["doc"] == DOC)
    m3_floor = min(b["floor"][1] for b in blocks_m3)
    if m3_floor < m2_floor:
        ok(f"the gate's floor only ever got HARDER: {m2_floor:.4f} min (M2) -> "
           f"{m3_floor:.4f} min ({cfg['floor']}) on the same holdout month")
    else:
        no(f"the configured floor scores {m3_floor:.4f} min against M2's {m2_floor:.4f} — a "
           "floor that predicts WORSE is a looser gate wearing a new name (F-010)")
    if rows_m3 == rows:
        ok(f"both floors were measured over the same {rows:,} holdout rows")
    else:
        no(f"the M3 transcript scored {rows_m3:,} rows and M2's {rows:,} — not a comparison")

    # The incumbent condition, live on disk (F-011). It defends M2's champion
    # directly: without it a challenger worse than version 1 takes the alias.
    # The PROMOTE block, not the last one: the M3 document also carries the
    # red team's REFUSE transcript, whose challenger is a deliberately degraded
    # model. Building "0.02 worse than that" would fail the MARGIN condition and
    # this sub-check would pass while testing something else entirely.
    promoted = next(b for b in blocks_m3 if b["verdict"] == "PROMOTE")
    inc_floor = promoted["floor"]
    champ = promoted["challenger"]
    worse = (champ[0] + "-but-worse", champ[1] + 0.02, champ[2] - 0.05)
    holdout = cfg["holdout_split"]
    inc = Incumbent(version="1", mae=champ[1], within_tolerance_rate=champ[2],
                    split=holdout, source="the transcript being replayed")
    d_worse = decide(metrics(worse, holdout), metrics(inc_floor, holdout),
                     {**cfg, "floor": inc_floor[0]}, incumbent=inc)
    if not d_worse.passed and any("serving champion" in c.name for c in d_worse.checks if not c.passed):
        ok("the incumbent condition is ARMED: a challenger 0.02 min worse than the champion "
           "is refused by name, even when it clears the floor bar")
    else:
        no("a challenger worse than the serving champion still PASSES — F-011 is open again")

    # The two comparisons the gate must DECLINE to make at all.
    good = blocks[-1]
    try:
        decide(metrics(good["challenger"], "val"), metrics(good["floor"], "val"), cfg)
        no("the gate judged VAL metrics — it would score a model against a month it was fitted to")
    except GateError:
        ok("the gate REFUSES to judge on val (early stopping read it) — GateError, not a warning")
    try:
        flattering = ("baseline-constant-median", 7.6667, 48.303)
        decide(metrics(good["challenger"], cfg["holdout_split"]),
               metrics(flattering, cfg["holdout_split"]), cfg)
        no("the gate accepted the FLATTERING constant-median floor as the bar")
    except GateError:
        ok("the gate REFUSES the flattering constant-median floor as the bar")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the gate replay itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 13 "the gate replay"

# -------------------------------------- 3. MLflow holds the runs behind it all --
section "3. MLflow: experiment 'm2-modeling' holds the runs, including the refused one"
consume < <(uv run python - 2>/dev/null <<'PY'
def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    name = cfg["mlflow"]["experiment"]
    exp = client.get_experiment_by_name(name)
    if exp is None:
        no(f"experiment {name!r} does not exist — M2's runs are somewhere else or nowhere")
        raise SystemExit(0)
    runs = client.search_runs([exp.experiment_id], max_results=200)
    if len(runs) >= 4:
        ok(f"experiment {name!r} holds {len(runs)} run(s) (namespaced from the start — gotcha #17)")
    else:
        no(f"experiment {name!r} holds only {len(runs)} run(s)")

    finished = [r for r in runs if r.info.status == "FINISHED"]
    if len(finished) == len(runs):
        ok(f"all {len(runs)} run(s) are FINISHED — no half-written experiment")
    else:
        no(f"{len(runs) - len(finished)} run(s) are not FINISHED")

    # Every contender the gate ever compared must be present, by name: a run that
    # produced a quoted number and then vanished makes the number unverifiable.
    names = {r.data.tags.get("mlflow.runName", "") for r in runs}
    for want in ("baseline-constant-median", "baseline-group-median", "lightgbm-v1"):
        if want in names:
            ok(f"run {want!r} is on file")
        else:
            no(f"no run named {want!r} — a contender the reports cite has no run behind it")

    hobbled = [r for r in runs if "hobbled" in r.data.tags]
    if not hobbled:
        no("the hobbled red-team run is GONE — a deleted refusal cannot be checked by anyone "
           "who was not watching")
    else:
        for r in hobbled:
            # Value-aware for the same reason §1 is: a run tagged
            # `do_not_promote: "no — …"` is NOT marked, and counting it would be a
            # false GREEN in the leg whose whole job is to prove the refusal was kept.
            marks = {k: r.data.tags[k] for k in ("red_team", "hobbled", "do_not_promote")
                     if k in r.data.tags
                     and not str(r.data.tags[k]).strip().lower().startswith("no")}
            verdict = r.data.tags.get("gate_verdict")
            if len(marks) == 3 and verdict == "REFUSE":
                ok(f"the refused challenger is KEPT and marked {sorted(marks)} with gate_verdict=REFUSE")
            else:
                no(f"the hobbled run {r.info.run_id[:12]}… is marked {sorted(marks)} / verdict={verdict}")

    # ...and it must never have become a version.
    versions = client.search_model_versions(f"name='{cfg['registry']['model_name']}'")
    hobbled_ids = {r.info.run_id for r in hobbled}
    polluting = [v.version for v in versions if v.run_id in hobbled_ids]
    if polluting:
        no(f"hobbled run(s) are registered as version(s) {polluting} — the registry is polluted")
    else:
        ok(f"no hobbled run is a registry version ({len(versions)} version(s) total, none of them it)")
except SystemExit:
    raise
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the MLflow check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the MLflow check"

# ------------------------ 4. KPI-09/KPI-10 come from the evaluator and nowhere else
section "4. KPI-09/KPI-10 have exactly one source: taxi_mlops.training.evaluate (gotcha #15)"
# The doc-contract tests are the standing sensor; the gate runs them rather than
# restating them, because two copies of a rule drift apart (the port-family lesson).
kpi_tests="$(uv run python -m pytest tests/unit/test_docs_contracts.py -q -k "model_quality or measured_value or sql_reference" 2>&1)"
n_passed="$(printf '%s\n' "$kpi_tests" | sed -n 's/^\([0-9]\+\) passed.*/\1/p' | tail -1)"
if [[ -n "$n_passed" && "$n_passed" -ge 3 ]]; then
  pass "the doc-contract tests that forbid a SQL-measured KPI-09/KPI-10 pass ($n_passed of them)"
else
  fail "the KPI-09/KPI-10 doc-contract tests did not report >=3 passing (got '${n_passed:-none}')"
  note "$(printf '%s\n' "$kpi_tests" | tail -8)"
fi
# And the mart layer must not be carrying them under any name. `error_segments`
# is licensed to hold model-error numbers precisely because it uses NEW ids
# (KPI-11/12/13) whose whole-split row reproduces the evaluator's.
kpi_cols="$("${KUBECTL[@]}" -n platform exec -i postgres-0 -- psql -U postgres -d marts -tAc \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='marts' AND (column_name LIKE '%kpi_09%' OR column_name LIKE '%kpi_10%')" 2>/dev/null)"
if [[ "$kpi_cols" == "0" ]]; then
  pass "no published mart carries a kpi_09/kpi_10 column (0 of them across schema 'marts')"
else
  fail "the marts schema holds ${kpi_cols:-<unreadable>} kpi_09/kpi_10 column(s) — a SQL-measured model metric"
fi
seg_ids="$("${KUBECTL[@]}" -n platform exec -i postgres-0 -- psql -U postgres -d marts -tAc \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='marts' AND table_name='error_segments' AND column_name IN ('kpi_11_mae_min','kpi_12_within_tol_pct','kpi_13_margin_vs_floor_pct')" 2>/dev/null)"
if [[ "$seg_ids" == "3" ]]; then
  pass "the segment metrics carry their OWN ids instead (KPI-11/12/13 — a new window is a new id)"
else
  fail "error_segments carries ${seg_ids:-<unreadable>} of the 3 expected KPI-11/12/13 columns"
fi

# ---------------------------------------- 5. the predictions reconcile, exactly --
section "5. predictions: one row per held-out row, describing the model that was promoted"
duck_log="$(uv run python -m taxi_mlops.data duckdb 2>&1)"
duck_rc=$?
if [[ "$duck_rc" -eq 0 ]] && printf '%s\n' "$duck_log" | grep -q '\[duckdb\] GREEN'; then
  pass "$(printf '%s\n' "$duck_log" | grep '\[duckdb\] GREEN' | tail -1)"
else
  fail "make duckdb did not come back GREEN (rc=$duck_rc) — a reconciliation disagrees"
  note "$(printf '%s\n' "$duck_log" | tail -12)"
fi
# Anchored on the THIRD reconciliation's own ALL line, and on a number > 0. The
# first draft of M1's gate counted every line ending in 'yes' and reported 16 for
# 8 files; the number quoted here is the number this reconciliation compared.
pred_all="$(printf '%s\n' "$duck_log" | sed -n '/published predictions vs the held-out rows/,$p' \
  | sed -n 's/^ *ALL *\([0-9,]*\) *\([0-9,]*\) *yes *$/\1 \2/p' | tail -1)"
if [[ -n "$pred_all" ]]; then
  left="${pred_all%% *}"; right="${pred_all##* }"
  if [[ "$left" == "$right" && "${left//,/}" -gt 0 ]]; then
    pass "every held-out row has a prediction: $left == $right (exit 1 if they ever differ)"
  else
    fail "the predictions reconciliation compared '$left' against '$right'"
  fi
else
  fail "the predictions reconciliation printed no ALL row — the third reconciliation did not run"
fi
consume < <(uv run python - 2>/dev/null <<'PY'
import json

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    man = json.load(open("data/predictions/predictions.json", encoding="utf-8"))
    if man.get("metric_source") == "taxi_mlops.training.evaluate":
        ok("predictions.json names the evaluator as its metric source")
    else:
        no(f"predictions.json's metric_source is {man.get('metric_source')!r}")

    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    live = client.get_model_version_by_alias(cfg["registry"]["model_name"],
                                            cfg["registry"]["champion_alias"])
    if str(man["model"]["version"]) == str(live.version) and man["model"]["run_id"] == live.run_id:
        ok(f"the published rows are stamped with the version that IS champion right now "
           f"(v{live.version}, run {live.run_id[:12]}…)")
    else:
        no(f"the rows are stamped v{man['model']['version']}/{man['model']['run_id'][:12]}… but "
           f"champion is v{live.version}/{live.run_id[:12]}… — they describe a model nobody serves")

    # The strongest line in this section: the gate's promotion number, the
    # scoring run's number and the champion's own tag must be one number. If they
    # are not, the rows describe a model that loads differently from the one that
    # was gated — a defect with no other symptom.
    holdout = cfg["gate"]["holdout_split"]
    scored = next(s for s in man["splits"]
                  if s["split"] == holdout and s["contender"].endswith("@champion"))
    claimed = live.tags.get("gate_challenger_mae")
    if claimed is not None and f"{scored['kpi_09_mae_minutes']:.4f}" == claimed:
        ok(f"re-scoring the champion on {holdout} reproduced its promotion number exactly "
           f"({claimed} min KPI-09)")
    else:
        no(f"the published rows score {scored['kpi_09_mae_minutes']:.4f} on {holdout}; the "
           f"version's own tag says it was promoted at {claimed}")
    rows = sum(s["rows"] for s in man["splits"] if s["contender"].endswith("@champion"))
    if rows > 0:
        ok(f"the manifest accounts for {rows:,} scored rows across the held-out splits")
    else:
        no("the manifest accounts for 0 scored rows")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the predictions provenance check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 4 "the predictions provenance check"

# ------------------------------- 6. the error_segments mart, rolled up honestly --
section "6. marts: error_segments is queryable and its whole-split row IS the evaluator's"
psql_marts() { "${KUBECTL[@]}" -n platform exec -i postgres-0 -- psql -U postgres -d marts -tAc "$1" 2>/dev/null; }
seg_rows="$(psql_marts "SELECT count(*) FROM marts.error_segments")"
if [[ -n "$seg_rows" && "$seg_rows" =~ ^[0-9]+$ && "$seg_rows" -gt 0 ]]; then
  pass "marts.error_segments is queryable in the ONE Postgres — $(printf "%'d" "$seg_rows") rows"
else
  fail "marts.error_segments is missing or empty (got '${seg_rows:-<nothing>}')"
fi
families="$(psql_marts "SELECT count(DISTINCT segment) FROM marts.error_segments")"
if [[ -n "$families" && "$families" =~ ^[0-9]+$ && "$families" -ge 6 ]]; then
  pass "it segments the error $families ways (the memo's question: zones? hours? long trips?)"
else
  fail "error_segments holds only '${families:-<nothing>}' segment families, expected >= 6"
fi
tail_band="$(psql_marts "SELECT count(*) FROM marts.error_segments WHERE segment='duration_band' AND segment_value LIKE '%100%'")"
if [[ -n "$tail_band" && "$tail_band" =~ ^[0-9]+$ && "$tail_band" -gt 0 ]]; then
  pass "the 100-120 min tail the contract admits has its own row(s) ($tail_band) — the ceiling finding is visible"
else
  fail "no duration_band row covers the 100-120 min tail"
fi
consume < <(KUBE_CONTEXT="$CONTEXT" uv run python - 2>/dev/null <<'PY'
import json, os, subprocess

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

SQL = ("SELECT split, trips, round(kpi_11_mae_min::numeric,4), "
       "round(kpi_12_within_tol_pct::numeric,3) FROM marts.error_segments "
       "WHERE segment='overall' ORDER BY split")
try:
    out = subprocess.run(
        ["kubectl", "--context", os.environ["KUBE_CONTEXT"], "-n", "platform", "exec", "-i",
         "postgres-0", "--",
         "psql", "-U", "postgres", "-d", "marts", "-tAF|", "-c", SQL],
        capture_output=True, text=True, timeout=60)
    published = {}
    for line in out.stdout.strip().splitlines():
        split, trips, mae, within = line.split("|")
        published[split] = (int(trips), float(mae), float(within))
    if not published:
        no("the mart has no whole-split 'overall' row — nothing to roll the segments up to")
        raise SystemExit(0)

    man = json.load(open("data/predictions/predictions.json", encoding="utf-8"))
    evaluator = {s["split"]: (s["rows"], s["kpi_09_mae_minutes"], s["kpi_10_within_tolerance_pct"])
                 for s in man["splits"] if s["contender"].endswith("@champion")}
    for split, (trips, mae, within) in sorted(published.items()):
        if split not in evaluator:
            no(f"the mart publishes split {split!r}, the evaluator's manifest does not")
            continue
        e_rows, e_mae, e_within = evaluator[split]
        agree = (trips == e_rows and f"{mae:.4f}" == f"{e_mae:.4f}"
                 and f"{within:.3f}" == f"{e_within:.3f}")
        if agree:
            ok(f"{split}: the mart's whole-split row reproduces the evaluator to 4 dp — "
               f"{mae:.4f} min / {within:.3f}% over {trips:,} rows")
        else:
            no(f"{split}: the mart says {mae:.4f}/{within:.3f}% over {trips:,} rows, the "
               f"evaluator says {e_mae:.4f}/{e_within:.3f}% over {e_rows:,} — a segmentation "
               "that does not roll up to the thing it segments")
except SystemExit:
    raise
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the rollup check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 2 "the rollup check"

# ---------------------------------------------- 7. the error-segment board -----
section "7. BI: the error-segment board renders through the API, and a card RUNS"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$METABASE_URL/api/health" || true)"
if [[ "$code" == "200" ]]; then
  pass "$METABASE_URL/api/health -> 200 (the URL the memo links)"
else
  fail "$METABASE_URL/api/health returned '$code'"
fi
# --verify is the read-only twin of `make boards`: it asserts existence, the
# warehouse each card queries, the gotcha #15 rule, and that one card per board
# actually EXECUTES. A dashboard that exists but whose cards error is a board
# nobody can act on.
boards_log="$(timeout 60 uv run python scripts/metabase_boards.py --verify 2>&1)"
boards_rc=$?
board_name="$(uv run python -c "import json;print(json.load(open('analytics/metabase/boards/error_segments.json'))['name'])" 2>/dev/null)"
if [[ "$boards_rc" -eq 0 ]]; then
  pass "every checked-in board verified through the Metabase API (rc=0)"
else
  fail "the Metabase board check failed (rc=$boards_rc)"
  note "$(printf '%s\n' "$boards_log" | tail -20)"
fi
exists_line="$(printf '%s\n' "$boards_log" | grep -F "dashboard '$board_name' exists with" \
  | sed 's/.*dashboard/dashboard/' | tail -1)"
if [[ -n "$exists_line" ]]; then
  pass "$exists_line"
else
  fail "no dashboard named '$board_name' in the running Metabase — the board is JSON on disk only"
fi
ran="$(printf '%s\n' "$boards_log" | grep -F "dashboard '$board_name'" | grep -oE "RAN and returned [0-9]+ row" | grep -oE '[0-9]+' | tail -1)"
if [[ -n "$ran" && "$ran" -gt 0 ]]; then
  pass "a card on '$board_name' RAN against the marts warehouse and returned $ran row(s)"
else
  fail "no card on '$board_name' was executed with a positive row count"
fi

# ------------------------------------- 8. the memo, and the twin that checks it --
section "8. the memo cites segments with numbers, links the board, and can be re-run"
MEMO=docs/error_memo_m2.md
if [[ -s "$MEMO" ]]; then
  pass "$MEMO present ($(wc -l < "$MEMO") lines) — the gate's 'Show'"
else
  fail "$MEMO is missing or empty"
fi
if grep -qF "$board_name" "$MEMO" && grep -q "$METABASE_URL/dashboard/" "$MEMO"; then
  pass "the memo links the board BY NAME and by URL ('$board_name' — the name is the address that survives)"
else
  fail "the memo does not link the error-segment board by both name and URL"
fi
cited="$(grep -coE 'KPI-1[123]' "$MEMO")"
if [[ "$cited" -ge 3 ]]; then
  pass "the memo cites the new segment ids by id ($cited mentions of KPI-11/12/13)"
else
  fail "the memo mentions KPI-11/12/13 only $cited time(s) — segment numbers without ids"
fi
# The memo's twin. Every number in the doc is re-derivable from the published
# mart; running one section proves the path still works and that the doc's
# headline is not a number typed once and never checked again.
memo_log="$(uv run python scripts/error_memo_numbers.py 1 2>&1)"
memo_rc=$?
data_rows="$(printf '%s\n' "$memo_log" | grep -cE '^\s*(test|val)\s')"
if [[ "$memo_rc" -eq 0 && "$data_rows" -gt 0 ]]; then
  pass "scripts/error_memo_numbers.py reproduced the memo's headline section live ($data_rows data row(s))"
else
  fail "the memo's twin failed (rc=$memo_rc, $data_rows data row(s))"
  note "$(printf '%s\n' "$memo_log" | tail -10)"
fi
# ...and the number it just printed must be the number the memo states.
headline="$(printf '%s\n' "$memo_log" | awk '$1=="test" && $2=="true" {print $(NF-1)}')"
if [[ -n "$headline" ]] && grep -qF "$headline" "$MEMO"; then
  pass "the headline the twin computed ($headline% margin where the floor falls back) is the number in the memo"
else
  fail "the twin computed a headline ('${headline:-nothing}') that the memo does not state"
fi

# ------------------------- 9. the boundary law and the repo root stays a repo root
section "9. boundary law, and no stray artefact at the repo root"
if leak="$(grep -rn "analytics" src/taxi_mlops/ 2>/dev/null)"; then
  fail "model code references the analytics layer — train/serve skew through the back door"
  note "$leak"
else
  pass "grep -r 'analytics' src/taxi_mlops/ is EMPTY — marts read model output, model code reads no mart"
fi
# The (u) near-miss and (z)'s two strays, made into a sensor. Widened past the
# named `_handoff_entry.md` on purpose: (z) found an empty `marts.duckdb` at the
# root, which was the FINGERPRINT of a live bug (gotcha #38) and would have been
# hidden by a .gitignore entry. Anything at the root that git does not track and
# this list does not expect gets named here.
consume < <(uv run python - 2>/dev/null <<'PY'
import os, subprocess

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

# Untracked things that BELONG at the root of a working clone. Everything else
# is a stray until somebody commits it or deletes it.
EXPECTED = {".git", ".venv", ".env", ".pytest_cache", ".ruff_cache", ".mypy_cache",
            ".idea", ".vscode", ".DS_Store"}
try:
    tracked = {p.split("/")[0] for p in
               subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                              check=True).stdout.split("\n") if p}
    strays = sorted(set(os.listdir(".")) - tracked - EXPECTED)
    if strays:
        no(f"{len(strays)} stray artefact(s) at the repo root: {', '.join(strays)} — "
           "a handoff fragment, a database written from the wrong cwd, or a log nobody meant to keep")
    else:
        ok(f"the repo root holds nothing but its {len(tracked)} tracked entries and the expected "
           "working-clone directories (no _handoff_entry.md, no stray *.duckdb)")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the root-stray check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 1 "the root-stray check"

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m2] GREEN — every M2 sub-check passed.\033[0m\n'
  echo "            Show: refusal transcript docs/promotion_gate_m2.md §3"
  echo "                  error memo      docs/error_memo_m2.md"
  echo "                  board           $METABASE_URL ($board_name)"
  exit 0
fi
printf '\033[31m[verify-m2] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS" >&2
exit 1
