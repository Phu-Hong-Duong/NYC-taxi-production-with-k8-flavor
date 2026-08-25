#!/usr/bin/env bash
# verify_m3.sh — the M3 gate, executable. BLUEPRINT §9/M3, quoted:
#
#   "Two workflows, equal budgets, one impartial gate. […] Accept when: dossier
#    holds >=10 candidates each with source + leakage note; the ablation table
#    shows per-group deltas; the leakage red-team transcript exists (inflation
#    observed, then removed); S3's resumability and pruning arms pass as before;
#    all five gate verdicts printed from evaluator-traceable MLflow runs. Show:
#    the dossier, the ablation table, the 2x2 bake-off table."
#
# The three design rules are M2-S5's, inherited whole and not restated here at
# length: every check observes the THING and not a proxy; every sub-check asserts
# a POSITIVE count or a matched line, and every Python leg must EMIT a minimum
# number of verdicts so a leg that dies on import fails loudly instead of
# contributing zero silent passes; probes stay impatient.
#
# Two rules matter more at M3 than they did at M2, and they are why this file
# reads the way it does:
#
#   RE-FITS NOTHING. Every number M3 produced took hours (the artisan track
#   3,313.9 s of fitting, the automation track 9,133.8 s). A gate that re-derived
#   them would cost more than the milestone and would mint MLflow runs on every
#   verification. So this gate reads: committed docs, RECORDED JSON, the Optuna
#   storage, the registry — and it REPLAYS the recorded numbers through the
#   decision code that is on disk right now. Total wall clock is seconds.
#
#   RECORDED **AND COMMITTED** — and it took two corrections to get that
#   sentence right (F-029). M4-S5 leg 3 found the original "committed docs,
#   committed JSON" was false: `automation/runs/` was gitignored, so
#   `m3s5/bakeoff.json` and `m3s4/*.json` were MACHINE state — present here,
#   absent in a fresh clone, outside review, and editable (which is what this
#   gate's red team simulates) with no diff for a reviewer to see. The word was
#   corrected to "RECORDED" that day and the POLICY was routed to ARCH, because
#   what a gate reads being invisible to review is a direction call, not an
#   executor's. ARCH decided option A at the M4 boundary (2026-08-19) and M5-S1
#   landed the mechanics: the verdict JSONs are now TRACKED (logs and .status
#   stay ignored). So the inputs below are recorded by the drills, committed to
#   the repository, and a tampered record shows up in `git diff`.
#
#   ASSERTS PROPERTIES, NOT LITERALS. M3-S5 spent three of its sub-checks
#   learning this the expensive way: `verify-m2` §1 pinned the floor's NAME, the
#   champion's EXPERIMENT and read `do_not_promote` by presence, and all three
#   went RED on the first legitimate champion transition. A literal that goes red
#   when the program does the right thing teaches the next session to edit
#   assertions, which is how a guard becomes a formality. So: the keep/drop
#   verdicts are re-derived by re-applying DR-02's bar to the table's own
#   numbers; the bake-off's verdicts are re-derived by replaying its own numbers
#   through `gate.decide`; the champion is checked against whatever the bake-off
#   RECORDED as its winner. Change the numbers and this gate changes with them;
#   change the RULES and it goes red.
#
# There is no skip flag and no fast mode — M1's rule, inherited twice now. A gate
# with a fast mode is a gate that runs in fast mode.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m3.sh          (via `make verify-m3`)
#        scripts/verify_m3_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")

FAILS=0
CONSUMED=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# Reads `PASS|msg` / `FAIL|msg` lines from a leg and counts them here, so the
# tally lives in exactly one place. ALWAYS call as `consume < <(...)`: a pipeline
# would run this in a subshell and throw the counters away at the closing brace.
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

expect_verdicts() {
  local want="$1" label="$2"
  if [[ "$CONSUMED" -lt "$want" ]]; then
    fail "$label emitted $CONSUMED verdict(s), expected at least $want — the check did not run"
  fi
}

printf '\n\033[1m[verify-m3]\033[0m the M3 gate — dossier, ablation, leakage drill, tuning,\n'
printf '            the five bake-off verdicts, the guards, and the alias.\n'
printf '            It re-reads and re-replays; it re-fits NOTHING.\n'

# ------------------------------------------- 1. the dossier is a dossier ------
section "1. the dossier: >=10 candidates, each with a source and a leakage note"
consume < <(uv run python - 2>/dev/null <<'PY'
import re

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

DOC = "docs/feature_dossier.md"
try:
    rows = []
    header = None
    for line in open(DOC, encoding="utf-8"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if cells and cells[0] == "#" and "Candidate" in cells:
                header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) == len(header) and re.fullmatch(r"\d+", cells[0]):
            rows.append(dict(zip(header, cells)))

    if len(rows) >= 10:
        ok(f"the dossier holds {len(rows)} candidates (the gate asks for >= 10)")
    else:
        no(f"the dossier holds only {len(rows)} parseable candidate row(s) — the gate asks for >= 10")

    # "each with source + leakage note", checked per row rather than in aggregate:
    # one candidate with a blank provenance is the one a later session cites.
    missing_src = [r["#"] for r in rows if len(r.get("Source", "")) < 3]
    if rows and not missing_src:
        ok(f"every one of the {len(rows)} candidates names where it came from (Source column)")
    else:
        no(f"candidate(s) {missing_src} name no source — a candidate with no provenance")
    missing_leak = [r["#"] for r in rows if len(r.get("Leakage risk", "")) < 3]
    if rows and not missing_leak:
        ok(f"every one of the {len(rows)} candidates carries a leakage note")
    else:
        no(f"candidate(s) {missing_leak} carry no leakage note")

    # The note has to bite. Every candidate the dossier itself calls HIGH-risk
    # must be constrained to TRAIN months in its adaptation note — that is the
    # playbook §5 trap, and a dossier that flags a risk without naming the
    # constraint has documented a worry rather than a rule.
    high = [r for r in rows if "HIGH" in r.get("Leakage risk", "")]
    unconstrained = [r["#"] for r in high
                     if "train months only" not in r.get("Adaptation note", "").lower()]
    if high and not unconstrained:
        ok(f"all {len(high)} HIGH-leakage candidate(s) are constrained to TRAIN months "
           f"in their adaptation note (playbook §5 trap 1)")
    elif not high:
        no("no candidate is marked HIGH leakage — the dossier's risk column is not being used")
    else:
        no(f"HIGH-leakage candidate(s) {unconstrained} carry no TRAIN-months-only constraint")

    # A dossier where everything was adopted is a wish list, not a review.
    refused = [r["#"] for r in rows
               if re.search(r"refus|drop", r.get("Verdict", ""), re.I)]
    if refused:
        ok(f"{len(refused)} candidate(s) carry a REFUSED/DROPPED verdict with a reason "
           f"(rows {', '.join(refused)}) — the dossier says no as well as yes")
    else:
        no("no candidate was refused or dropped — a dossier that adopts everything is a wish list")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the dossier check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the dossier check"

# ---------------------------- 2. the ablation table, and its bar re-applied ---
section "2. the ablation: per-group deltas, and DR-02's bar re-applied to them"
consume < <(uv run python - 2>/dev/null <<'PY'
import re

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

DOC = "docs/ablation_m3.md"
KEEP_BAR_PCT = 0.50   # Design Review DR-02, re-argued as a maintenance-cost bar
try:
    from taxi_mlops.features import sets

    declared = sets.group_names()
    text = open(DOC, encoding="utf-8").read()

    # Parse the ablation rows: | `v1_g1` | g1 temporal extras | 15 | 3.4312 |
    # **+1.78%** | 80.145% | +0.594 | 500 | 119 | **KEEP** |
    row_re = re.compile(
        r"^\|\s*\**`?(v1(?:_g\d)?)`?\**\s*\|"          # experiment
        r"\s*([^|]*?)\s*\|"                            # groups
        r"\s*\**(\d+)\**\s*\|"                         # features
        r"\s*\**([\d.]+)\**\s*\|"                      # val MAE
        r"\s*\**([-−+][\d.]+)%\**\s*\|"                # delta val MAE
        r"\s*\**([\d.]+)%\**\s*\|"                     # KPI-10
        r"\s*\**([-−+][\d.]+)\**\s*\|"                 # delta KPI-10
        r"\s*\**(\d+)\**\s*\|"                         # best iter
        r"\s*\**([\d.]+)\**\s*\|"                      # fit s
        r"\s*\**([^|]*?)\**\s*\|\s*$", re.M)           # verdict
    rows = []
    for m in row_re.finditer(text):
        rows.append({
            "experiment": m.group(1), "groups": m.group(2),
            "d_mae": float(m.group(5).replace("−", "-")),
            "kpi10": float(m.group(6)),
            "d_kpi10": float(m.group(7).replace("−", "-")),
            "verdict": m.group(10).strip(),
        })
    single = {r["experiment"]: r for r in rows if re.fullmatch(r"v1_g\d", r["experiment"])}

    if len(single) == len(declared) == 5:
        ok(f"all {len(declared)} declared groups have an ablation row "
           f"({', '.join(sorted(single))}) — every group tried is reported")
    else:
        no(f"configs/features.yaml declares {len(declared)} group(s) and the table has "
           f"{len(single)} single-group row(s): {sorted(single)} vs {sorted(declared)}")

    # "the ablation table shows per-group deltas" — both of them. DR-02 added
    # KPI-10 per group because a mean over 6M rows can improve while more riders
    # are quoted wrongly, and a table carrying only MAE cannot see that.
    if single and all(r["d_mae"] is not None and r["d_kpi10"] is not None
                      for r in single.values()):
        ok("every group row carries BOTH deltas — relative val MAE and KPI-10 points (DR-02)")
    else:
        no("a group row is missing one of its two deltas")

    # The thing, not the proxy: re-apply the bar to the table's OWN numbers and
    # demand the printed verdicts come back. This goes red if a verdict is edited
    # without its number, if a number is edited without its verdict, or if
    # somebody quietly lowers the bar to admit a group that lost.
    disagree = []
    for name, r in sorted(single.items()):
        earned = r["d_mae"] >= KEEP_BAR_PCT and r["d_kpi10"] > 0
        printed = "KEEP" in r["verdict"].upper()
        if earned != printed:
            disagree.append(f"{name}: {r['d_mae']:+.2f}%/{r['d_kpi10']:+.3f}pts "
                            f"-> {'KEEP' if earned else 'drop'}, table says {r['verdict']!r}")
    if single and not disagree:
        ok(f"re-applying DR-02's >= {KEEP_BAR_PCT:.2f}% bar to the table's own numbers "
           f"reproduces all {len(single)} verdicts")
    else:
        no(f"the bar re-applied disagrees with the printed verdict(s): {disagree}")

    drops = [n for n, r in single.items() if "KEEP" not in r["verdict"].upper()]
    if drops:
        ok(f"{len(drops)} group(s) LOST and are in the table anyway ({', '.join(sorted(drops))}) "
           f"— a table of winners only would imply a 100% hit rate")
    else:
        no("no group was dropped — either nothing lost, or the losers are not reported")

    # ...and the set that is actually registered must be exactly the survivors.
    # A v2 assembled feature-by-feature from the winners of a GROUP experiment
    # would report a number nothing was ever measured at.
    kept = sorted(single[n]["groups"] for n in single if n not in drops)
    v2_groups = sorted(sets.resolve_set("v2")["groups"])
    kept_keys = sorted(g.replace(" ", "_").replace("-", "") for g in
                       [single[n]["groups"] for n in single if n not in drops])
    matched = len(v2_groups) == len(kept) and all(
        any(k.split()[0] in g for g in v2_groups) for k in kept)
    if matched:
        ok(f"feature set v2 in the registry is exactly the surviving group(s): {v2_groups}")
    else:
        no(f"v2 is {v2_groups} but the table's survivors are {kept} ({kept_keys})")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the ablation check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the ablation check"

# ------------------------------- 3. the leakage red-team, and its live switch --
section "3. the leakage red-team: inflation observed, and the switch still leaks"
consume < <(uv run python - 2>/dev/null <<'PY'
import inspect
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

DOC = "docs/leakage_redteam_m3.md"
try:
    text = Path(DOC).read_text(encoding="utf-8")
    m = re.search(
        r"the leak BOUGHT ([-−+][\d.]+) min on the month it saw.*?"
        r"and ([-−+][\d.]+) min\s*\n?\s*on the month it did not", text, re.S)
    infl = re.search(r"inflation = ([-−+][\d.]+) min", text)
    if m and infl:
        seen = float(m.group(1).replace("−", "-"))
        unseen = float(m.group(2).replace("−", "-"))
        inflation = float(infl.group(1).replace("−", "-"))
        ok(f"the drill's transcript is on file and its three numbers parse: "
           f"seen {seen:+.4f}, unseen {unseen:+.4f}, inflation {inflation:+.4f} min")
        # The finding IS the difference; if the three numbers stop reconciling,
        # one of them was retyped.
        if abs((seen - unseen) - inflation) <= 0.0005:
            ok(f"they reconcile: {seen:+.4f} - ({unseen:+.4f}) = {seen - unseen:+.4f} "
               f"= the recorded inflation (within 4-dp rounding)")
        else:
            no(f"they do NOT reconcile: {seen:+.4f} - ({unseen:+.4f}) = {seen - unseen:+.4f}, "
               f"the doc says {inflation:+.4f}")
        # ...and the inflation must be in the direction the drill exists to show.
        if seen > 0 > unseen:
            ok("the leak flattered the month it saw and hurt the month it did not — "
               "which is the whole finding, and the direction a green drill must have")
        else:
            no(f"the drill records seen={seen:+.4f} unseen={unseen:+.4f} — that is not "
               "the inflation shape the transcript claims")
    else:
        no(f"{DOC} holds no parseable inflation transcript — the drill is not on file")

    # The switch itself, live: honest by default, and exactly one caller may flip
    # it. A red team whose lever quietly stopped moving proves nothing, and the
    # thing that would silently disarm it is a changed default.
    from taxi_mlops.features import aggregates
    default = inspect.signature(aggregates.fit).parameters["point_in_time"].default
    if default is True:
        ok("aggregates.fit(point_in_time=True) is still the DEFAULT — the honest path "
           "is the one you get by not thinking about it")
    else:
        no(f"aggregates.fit's point_in_time default is {default!r}, not True")

    # CALLERS only. `aggregates.py` is where the switch is defined and is the one
    # file that must contain `point_in_time=False` — it is the branch that
    # implements it. Every other occurrence in the tree is somebody using it.
    DEFINITION = "src/taxi_mlops/features/aggregates.py"
    flippers = sorted(
        str(p) for p in list(Path("src").rglob("*.py")) + list(Path("scripts").rglob("*.py"))
        if str(p) != DEFINITION
        and re.search(r"point_in_time\s*=\s*False", p.read_text(encoding="utf-8")))
    allowed = {"scripts/leakage_redteam.py"}
    if set(flippers) == allowed:
        ok(f"exactly one CALLER may flip it, and it is the red team: {flippers[0]} "
           f"(the switch itself is defined in {DEFINITION})")
    else:
        no(f"point_in_time=False is passed by {flippers or 'nobody'} — expected {sorted(allowed)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the leakage check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the leakage check"

# ------------------- 4. Optuna: studies in Postgres, pruned, and resumed -------
section "4. tuning: the studies live in Postgres, one PRUNED, one survived a kill"
optuna_states="$("${KUBECTL[@]}" -n platform exec -i postgres-0 -- \
  psql -U postgres -d optuna -tAF'|' -c \
  "select s.study_name, t.state, count(*) from trials t
     join studies s on s.study_id = t.study_id group by 1,2 order by 1,2" 2>/dev/null)"
consume < <(OPTUNA_STATES="$optuna_states" uv run python - 2>/dev/null <<'PY'
import json
import os
from collections import defaultdict
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    states = defaultdict(dict)
    for line in os.environ.get("OPTUNA_STATES", "").splitlines():
        if line.count("|") == 2:
            study, state, n = line.split("|")
            states[study][state] = int(n)

    if not states:
        no("no Optuna trial rows came back from the `optuna` database in the ONE Postgres "
           "— the studies are not where gotcha #17 says they are")
    else:
        ok(f"the `optuna` database in the ONE Postgres holds {len(states)} study/studies "
           f"with {sum(sum(v.values()) for v in states.values())} trial(s) total")

    # The two sniper studies M3-S4 ran, found by the NAME its JSON records — a
    # study read by guessing is not the study the numbers came from (gotcha #17).
    for phase in ("sniper-v1", "sniper-v2"):
        rec = json.loads(Path(f"automation/runs/m3s4/{phase}.json").read_text())
        name = rec["study"]
        live = states.get(name)
        if live and sum(live.values()) == rec["trials_total"]:
            no_ = None
            ok(f"{phase}: study {name!r} is in Postgres with {sum(live.values())} trial(s), "
               f"the count its JSON records ({dict(sorted(live.items()))})")
        else:
            no(f"{phase}: study {name!r} holds {live} in Postgres against "
               f"{rec['trials_total']} in its JSON — the record and the storage disagree")

    # ">= 1 pruned trial", read off the storage and not off a log. The v1 study
    # pruned NONE (9 trials, all complete) and that is on the record — so this
    # leg is about the pruner being ARMED and having fired somewhere, which it
    # did on v2 six times.
    pruned = {s: v["PRUNED"] for s, v in states.items() if v.get("PRUNED")}
    if pruned:
        ok(f"the pruner FIRED and the storage remembers: "
           f"{', '.join(f'{s} {n} pruned' for s, n in sorted(pruned.items()))}")
    else:
        no("no trial in any study is PRUNED — the pruner is either disarmed or never ran")

    # Resumability, from the drill's own artifact AND from the storage it wrote
    # to. The drill's point is that a study is state in a database, not state in
    # a process: it was SIGKILLed mid-trial and the same command reopened it.
    drill = json.loads(Path("automation/runs/resume-drill-v1.json").read_text())
    live = states.get(drill["study"], {})
    total_live = sum(live.values())
    if (drill["arm2_opened_with"] == drill["trials_at_kill"]
            and drill["still_running"] == 0
            and total_live == drill["trials_after_resume"]):
        ok(f"a study outlived its process: killed at {drill['trials_at_kill']} trial(s), "
           f"reopened with {drill['arm2_opened_with']}, finished with "
           f"{drill['trials_after_resume']} and {drill['reaped_by_heartbeat']} dead trial(s) "
           f"reaped — and Postgres still holds all {total_live}")
    else:
        no(f"the resume drill's record does not describe a survived kill: {drill} "
           f"vs {total_live} trial(s) live in Postgres")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the tuning check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the tuning check"

# ------------------- 5. the five bake-off verdicts, replayed through the gate --
section "5. the bake-off: five verdicts replayed through gate.decide as it is on disk NOW"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

BAKEOFF = Path("automation/runs/m3s5/bakeoff.json")
DOC = Path("docs/bakeoff_m3.md")
try:
    from taxi_mlops.training import gate_eras
    from taxi_mlops.training.evaluate import Metrics
    from taxi_mlops.training.gate import Incumbent, decide
    from taxi_mlops.training.run import load_train_config

    rec = json.loads(BAKEOFF.read_text())
    cfg = load_train_config("configs/train.yaml")["gate"]
    holdout = rec["holdout_split"]
    contenders = rec["contenders"]
    LEG = "verify-m3 §5"
    # M9-S10 (F-016/F-068). This record was written under an incumbent condition
    # with NO margin, and two of its five verdicts — the floor judged against
    # itself and `champion v1`, both at exactly +0.0000% — flip under the landed
    # 0.50%. A replay that judged them by today's bar would report the gate
    # "moving under the transcript" when what moved is the transcript's era. So
    # the margin comes from the RECORD when it declares one (every bake-off from
    # here on writes `gate.incumbent_min_improvement_pct`) and otherwise from
    # the ENUMERATED pre-B set — never from a default, since the only default
    # that would work is zero and zero is the loosest bar there is (F-048).
    recorded_margin = rec.get("gate", {}).get("incumbent_min_improvement_pct")

    if len(contenders) == 5:
        ok(f"the bake-off recorded all {len(contenders)} contenders on {holdout!r} — "
           f"{', '.join(c['label'] for c in contenders)}")
    else:
        no(f"the bake-off recorded {len(contenders)} contender(s), not five")

    floor = next(c for c in contenders if c["track"] == "floor")
    inc = rec["incumbent"]

    def metrics(name, mae, within, n):
        return Metrics(contender=name, split=holdout, n=n, mae=mae,
                       within_tolerance_rate=within, tolerance_minutes=5.0,
                       rmse=0.0, median_ae=0.0, p90_ae=0.0)

    # The replay. Not "the doc contains the word REFUSE" — the recorded numbers
    # fed back through the decision function that exists right now. This is the
    # only version that goes red when somebody loosens `configs/train.yaml: gate`
    # after the transcript was written.
    replayed = {"PROMOTE": 0, "REFUSE": 0}
    eras_seen = []
    for c in contenders:
        n = c["test_rows"]
        try:
            era = gate_eras.in_force_margin(
                LEG, str(BAKEOFF), c["label"], recorded=recorded_margin)
        except gate_eras.GateEraError as exc:
            no(f"{c['label']} cannot be replayed: {str(exc).splitlines()[0]}")
            continue
        eras_seen.append(era)
        block_cfg = {**cfg, "floor": floor["name"], "incumbent_min_improvement_pct": era}
        incumbent = Incumbent(
            version=inc["version"], mae=inc["mae"],
            within_tolerance_rate=inc["within_tolerance_rate"], split=holdout,
            source=f"the bake-off record in {BAKEOFF}")
        d = decide(
            metrics(c["name"], c["test_mae"], c["test_within_rate"], n),
            metrics(floor["name"], floor["test_mae"], floor["test_within_rate"], n),
            block_cfg, incumbent)
        if d.verdict == c["verdict"]:
            replayed[d.verdict] += 1
            ok(f"replayed {c['label']}: {c['test_mae']:.4f} vs floor {floor['test_mae']:.4f} "
               f"min, incumbent v{inc['version']} {inc['mae']:.4f} -> {d.verdict} "
               f"({c['observed_pct']:+.2f}%), as the bake-off recorded")
        else:
            no(f"replaying {c['label']} through today's gate gives {d.verdict}, "
               f"the bake-off recorded {c['verdict']} — the gate moved under the transcript")

    if replayed["REFUSE"] >= 2 and replayed["PROMOTE"] >= 1:
        ok(f"the replayed set is not all-passing: {replayed['PROMOTE']} PROMOTE, "
           f"{replayed['REFUSE']} REFUSE — including the floor judged against itself")
    else:
        no(f"the replay produced {replayed} — a bake-off nobody was refused in "
           "is a bake-off nobody was judged in")

    # ...and the era those five were judged under is stated rather than assumed,
    # with the live bar required to be no lower. Two of the five sit at exactly
    # +0.0000% against the incumbent, so this leg is the one that would report
    # the flip if the enumeration or the era logic were wrong.
    ties = [c["label"] for c in contenders
            if inc and round(c["test_mae"], 4) == round(inc["mae"], 4)]
    try:
        required = gate_eras.assert_margin_never_decreased(
            cfg["incumbent_min_improvement_pct"], eras_seen)
        ok(f"all {len(eras_seen)} verdict(s) replayed ERA-AWARE at the "
           f"{sorted(set(f'{e:.2f}%' for e in eras_seen))} margin in force when the "
           f"bake-off ran — including {len(ties)} judged against the incumbent's own "
           f"number ({', '.join(ties)}) — while the live bar is "
           f"{float(cfg['incumbent_min_improvement_pct']):.2f}% (>= the sanctioned "
           f"{required:.2f}%)")
    except gate_eras.GateEraError as exc:
        no(f"the live incumbent margin is below one this record's verdicts were taken "
           f"against: {str(exc).splitlines()[0]}")

    # "printed from evaluator-traceable MLflow runs" — every non-floor contender
    # must name a run, and that run must name the evaluator as its metric source.
    models = [c for c in contenders if c["track"] != "floor"]
    unsourced = [c["label"] for c in models if not c.get("run_id")]
    if models and not unsourced:
        ok(f"all {len(models)} model contenders name the MLflow run their numbers came "
           f"from ({', '.join(c['run_id'][:8] + '…' for c in models)})")
    else:
        no(f"contender(s) {unsourced} carry no run_id — a number with no run behind it")

    # And the doc that Shows it must carry the same five rows.
    text = DOC.read_text(encoding="utf-8")
    missing = [c["name"] for c in contenders if c["name"] not in text]
    if not missing:
        ok(f"docs/bakeoff_m3.md names all five contenders by run name (the gate's 'Show')")
    else:
        no(f"the bake-off table does not name {missing}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the bake-off replay check itself raised {type(exc).__name__}: {exc}")
PY
)
# 10 from M9-S10 (the era-aware summary, plus one the old bound under-declared).
# Re-DERIVED by running the leg, never widened: the bound is "at least", so its
# job is to fail a leg that died on import rather than to describe the leg.
expect_verdicts 10 "the bake-off replay"

# ------------------------------------ 6. the guards, each provably armed ------
section "6. the guards: incumbent, val, flattering floor, and the sampled run"
consume < <(uv run python - 2>/dev/null <<'PY'
def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    from taxi_mlops.training import registry
    from taxi_mlops.training.evaluate import Metrics
    from taxi_mlops.training.gate import (
        GateError, Incumbent, assert_full_train_months, decide,
    )
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    gate_cfg = cfg["gate"]
    holdout = gate_cfg["holdout_split"]
    N = 5_950_708

    def metrics(name, mae, within, split=holdout):
        return Metrics(contender=name, split=split, n=N, mae=mae,
                       within_tolerance_rate=within, tolerance_minutes=5.0,
                       rmse=0.0, median_ae=0.0, p90_ae=0.0)

    floor = metrics(gate_cfg["floor"], 3.3518, 80.733)

    # F-011, armed: a challenger that CLEARS the floor bar and is still worse
    # than what is serving must be refused, by name. This is the condition that
    # can only ever be checked with an incumbent in hand.
    incumbent = Incumbent(version="1", mae=3.2403, within_tolerance_rate=81.577,
                          split=holdout, source="verify-m3, synthetic")
    d = decide(metrics("worse-than-champion", 3.2603, 81.400), floor, gate_cfg, incumbent)
    # Matched on "champion"/"incumbent" because the condition names what is
    # SERVING, and the reader-facing wording is allowed to be the friendlier one.
    named = [c for c in d.checks if not c.passed
             and ("incumbent" in c.name.lower() or "champion" in c.name.lower())]
    clears_floor = [c for c in d.checks if c.passed and "floor" in c.name.lower()]
    if d.verdict == "REFUSE" and named and clears_floor:
        ok(f"F-011 armed: a challenger 0.02 min worse than the incumbent is REFUSED by "
           f"name ({named[0].name!r}) while it still clears the floor bar "
           f"({clears_floor[0].detail})")
    else:
        no(f"the incumbent condition did not refuse a worse-than-champion challenger: "
           f"{d.verdict}, failing checks {[c.name for c in d.checks if not c.passed]}")

    # ...and the other half of F-011, which lives in the mutating module: a
    # promotion whose decision never read the live alias is refused outright.
    #
    # Safe to call for real, and deliberately so: `promote` runs the incumbent
    # check FIRST, before it reads the artifact or touches the registry, because
    # it is the one refusal there that protects something already serving. If
    # that ordering ever changed, this sub-check would create a version — which
    # is exactly the ordering the gate wants to be sensitive to.
    import mlflow
    from taxi_mlops.training import tracking
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    try:
        registry.promote(client, model_name=cfg["registry"]["model_name"],
                         alias=cfg["registry"]["champion_alias"],
                         run_id="0" * 32, incumbent_version=None)
    except registry.PromotionError as exc:
        ok(f"registry.promote REFUSES a promotion that did not read the incumbent "
           f"(incumbent_version=None) — {str(exc).splitlines()[0][:90]}…")
    except Exception as exc:  # noqa: BLE001
        no(f"registry.promote raised {type(exc).__name__} rather than PromotionError: {exc}")
    else:
        no("registry.promote accepted incumbent_version=None — the F-011 bypass is OPEN")

    # The gate refuses to judge on the month early stopping read.
    try:
        decide(metrics("x", 3.0, 82.0, split="val"), floor, gate_cfg)
    except GateError:
        ok("the gate REFUSES to judge on val (early stopping read it) — GateError, not a warning")
    else:
        no("the gate judged a val challenger — a model scored against a month it was fitted to")

    # ...and refuses the flattering floor as the bar.
    try:
        decide(metrics("x", 3.0, 82.0), metrics("baseline-constant-median", 7.6667, 48.0),
               gate_cfg)
    except GateError:
        ok("the gate REFUSES the flattering constant-median floor as the bar")
    else:
        no("the gate accepted baseline-constant-median as the bar — every model looks good")

    # F-008: a run fitted on fewer months than the config names cannot be judged.
    configured = list(cfg["data"]["train_months"])
    try:
        assert_full_train_months([configured[0]], configured)
    except GateError:
        ok(f"F-008 armed: a run fitted on 1 of {len(configured)} configured train months "
           f"is gate-DISQUALIFIED before a row is read (a shrunken train degrades the "
           f"BAR faster than the model)")
    else:
        no("a sampled train-month list passed the F-008 guard — sampling makes this gate easier")

    # The bar itself. Tightening is the MLE's to argue; loosening is a PO fork.
    if float(gate_cfg["min_improvement_pct"]) >= 2.0 and gate_cfg.get("require_no_kpi10_regression"):
        ok(f"the bar is unchanged: KPI-09 margin >= {gate_cfg['min_improvement_pct']}% and the "
           f"KPI-10 no-regression condition still armed")
    else:
        no(f"the gate has been LOOSENED: {gate_cfg['min_improvement_pct']}% margin, "
           f"require_no_kpi10_regression={gate_cfg.get('require_no_kpi10_regression')}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the guards check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the guards check"

# ------------- 7. the registry agrees with what the bake-off printed ----------
section "7. the alias: the registry is coherent with the bake-off's recorded outcome"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    from taxi_mlops.features import quote_time
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    rec = json.loads(Path("automation/runs/m3s5/bakeoff.json").read_text())
    cfg = load_train_config("configs/train.yaml")
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]

    by_label = {c["label"]: c for c in rec["contenders"]}
    winner = by_label[rec["winner"]]
    losers = [c for c in rec["contenders"] if c["verdict"] == "REFUSE"]

    if winner["verdict"] == "PROMOTE":
        ok(f"the bake-off's winner {rec['winner']!r} ({winner['name']}) carries a PROMOTE "
           f"verdict — the alias decision followed the gate, not the ranking")
    else:
        no(f"the recorded winner {rec['winner']!r} carries verdict {winner['verdict']!r}")

    mv = client.get_model_version_by_alias(name, alias)
    if mv.run_id == winner["run_id"]:
        ok(f"models:/{name}@{alias} -> version {mv.version}, run {mv.run_id[:12]}… — the run "
           f"the bake-off named as winner")
    else:
        no(f"@{alias} resolves to run {mv.run_id[:12]}… but the bake-off's winner is "
           f"{str(winner['run_id'])[:12]}… — the alias and the decision disagree")

    # The numbers on the version must be the numbers the bake-off measured. This
    # is what makes "what was this promoted on?" a registry question rather than
    # a transcript question.
    tags = dict(mv.tags or {})
    want = {"gate_challenger_mae": f"{winner['test_mae']:.4f}",
            "gate_floor_mae": f"{rec['floor_fit']['gate_floor_mae']:.4f}"
            if "gate_floor_mae" in rec["floor_fit"] else None,
            "gate_floor": rec["gate"]["floor"],
            "gate_verdict": "PROMOTE"}
    want = {k: v for k, v in want.items() if v is not None}
    wrong = {k: (tags.get(k), v) for k, v in want.items() if tags.get(k) != v}
    if not wrong:
        ok(f"the version carries the bake-off's own numbers: KPI-09 {tags['gate_challenger_mae']} "
           f"vs floor {tags['gate_floor']} — the registry answers 'measured against what?'")
    else:
        no(f"the version's tags do not match the bake-off record: {wrong}")

    # Nothing the bake-off refused may be aliased or registered.
    versions = client.search_model_versions(f"name='{name}'")
    refused_runs = {c["run_id"] for c in losers if c.get("run_id")}
    polluting = [v.version for v in versions if v.run_id in refused_runs]
    if refused_runs and not polluting:
        ok(f"none of the {len(refused_runs)} REFUSED contender(s) is a registry version "
           f"({len(versions)} version(s) total) — a refusal leaves the registry as it found it")
    else:
        no(f"refused contender(s) are registered as version(s) {polluting}")

    # The config line moves as part of a promotion or not at all: what is served
    # and what `make train` would fit next must be the same feature set. Read
    # from the RAW yaml, not from `load_train_config`: that loader has already
    # run the registry expansion, and asking the expanded object which version it
    # came from would be asking the answer.
    import yaml
    configured_set = yaml.safe_load(Path("configs/train.yaml").read_text())["features"]["version"]
    if configured_set == winner["feature_set"]:
        ok(f"configs/train.yaml names feature set {configured_set!r} — the winner's set, so a "
           f"re-fit today starts from what is serving")
    else:
        no(f"the config names {configured_set!r} and the champion was fitted on "
           f"{winner['feature_set']!r} — train/serve skew by config drift")

    # ...and the signature must be over exactly that set, expanded by the ONE
    # expansion in the program. `cfg["features"]` is what `sets.resolve` returned
    # for `configured_set`, so this compares the artifact against the registry
    # rather than against a list typed twice.
    info = mlflow.models.get_model_info(f"models:/{name}@{alias}")
    expected = quote_time.feature_names(cfg["features"])
    got = [c.name for c in info.signature.inputs.inputs] if info.signature else None
    if got and got == expected:
        ok(f"the champion's signature is exactly the {len(got)} feature(s) "
           f"features.sets.resolve expands {configured_set!r} to, in order")
    elif got:
        no(f"the signature has {len(got)} feature(s) and the registry resolves "
           f"{configured_set!r} to {len(expected)}: {sorted(set(got) ^ set(expected))}")
    else:
        no("the champion carries NO signature — M5 would discover its schema by crashing")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the registry-coherence check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the registry-coherence check"

# ---------------------------- 8. F-013: the gate and the features have ONE home
section "8. F-013: the stubs are really gone, and each thing has exactly one home"
consume < <(uv run python - 2>/dev/null <<'PY'
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

# Knobs, not filenames: the next stub will be called something else.
GATE_KNOBS = ("gate_ratio", "min_improvement_pct", "require_no_kpi10_regression",
              "holdout_split")
try:
    from taxi_mlops.features import sets

    stub = Path("configs/promotion.yaml")
    if not stub.exists():
        ok(f"{stub} is gone — the bar that agreed with nothing in the program "
           f"(gate_ratio: 0.85) is not there to be found first")
    else:
        no(f"{stub} is back — a second home for the gate")

    offenders = {}
    for path in sorted(Path("configs").rglob("*.yaml")):
        if path.name == "train.yaml":
            continue
        text = path.read_text(encoding="utf-8")
        found = [k for k in GATE_KNOBS if re.search(rf"^\s*{k}\s*:", text, re.M)]
        if found:
            offenders[str(path)] = found
    if not offenders:
        ok(f"no file under configs/ except train.yaml names a gate knob "
           f"({len(GATE_KNOBS)} knob(s) checked across "
           f"{len(list(Path('configs').rglob('*.yaml'))) - 1} other config file(s))")
    else:
        no(f"gate knob(s) live outside configs/train.yaml: {offenders}")

    # The features half. `train.yaml: features` holds a pointer and a version and
    # NOTHING else — a column list growing back there would be a second registry.
    import yaml
    features_cfg = yaml.safe_load(Path("configs/train.yaml").read_text())["features"]
    if set(features_cfg) == {"version", "registry"}:
        ok(f"configs/train.yaml: features holds only {sorted(features_cfg)} — the column "
           f"lists live in {features_cfg['registry']} and nowhere else")
    else:
        no(f"configs/train.yaml: features has grown extra key(s): {sorted(features_cfg)}")

    # ...and the expansion refuses to be bypassed, live.
    try:
        sets.resolve({**features_cfg, "columns": ["hour", "dayofweek"]})
    except Exception as exc:
        if isinstance(exc, sets.FeatureSetError):
            ok("features.sets.resolve RAISES on a column list in train.yaml — the one "
               "expansion in the program cannot be walked around")
        else:
            no(f"resolve raised {type(exc).__name__} rather than FeatureSetError: {exc}")
    else:
        no("features.sets.resolve accepted an inline column list — a second definition "
           "of the feature set, one file from the first")

    # The marts boundary law, restated at M3 because v2 added an aggregate family
    # whose legal version looks exactly like a mart.
    leaks = [str(p) for p in Path("src/taxi_mlops").rglob("*.py")
             if "analytics" in p.read_text(encoding="utf-8")]
    if not leaks:
        ok("grep -r 'analytics' src/taxi_mlops/ is EMPTY — model code reads no mart "
           "(ADR-009, gotcha #22)")
    else:
        no(f"model code references the analytics layer: {leaks}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the F-013 check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the F-013 check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m3] GREEN — every M3 sub-check passed.\033[0m\n'
  printf '            Show: the dossier      docs/feature_dossier.md\n'
  printf '                  the ablation     docs/ablation_m3.md\n'
  printf '                  the bake-off     docs/bakeoff_m3.md (2x2 + floor, five verdicts)\n'
  printf '                  the leakage drill docs/leakage_redteam_m3.md\n'
  exit 0
fi
printf '\033[31m[verify-m3] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS"
exit 1
