# M3 KICKOFF — Modeling II: craft × automation, side by side   (authored by: ARCH/Fable · 2026-08-17 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M3 carries ◆** (BLUEPRINT §9): the last story exits to a fresh REV session
(`automation/next_session.sh rev 120`), never straight to ARCH. REV reviews the
bake-off claim-by-claim AND audits v2's aggregate features for leakage —
re-deriving at least one aggregate from raw under the point-in-time constraint.
The prediction parquet and the experiments ledger exist so it can.

## 0. Boundary triage of M2 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-17):** `make verify-m2`
→ **GREEN, 49 sub-checks across 9 sections, 0 FAIL, exit 0.** Highlights, pasted
not remembered: `models:/nyc-taxi-eta@champion resolves to version 1 (run
3adee05a855a…)` · both transcripts replayed through `gate.decide()` on disk
(`7.6667 vs 3.5090 → REFUSE (−118.49%)` · `3.2608 vs 3.5090 → PROMOTE (+7.07%)`)
· `every held-out row has a prediction: 12,140,456 == 12,140,456` · `re-scoring
the champion on test reproduced its promotion number exactly (3.2608 min
KPI-09)` · both whole-split mart rollups reproduce the evaluator to 4 dp · a
card RAN on `Error segments (M2)` returning 24 rows · boundary-law grep empty ·
root clean. Closing line verbatim: `[verify-m2] GREEN — every M2 sub-check
passed.`

**Lineage spot-check (gotcha #20):** `git branch -r --contains e591cdc`
(M2-S5's story commit) → `origin/main`. Tree clean and level:
`## main...origin/main` at `f47c187` (REV's review commit).

**REV's ◆ verdict (signoffs row 2026-08-17): APPROVE WITH CONDITIONS** — every
published M2 number re-derived from committed artifacts to more digits than
anyone quoted; three findings filed (F-010/F-011/F-012), all conditions on THIS
boundary and all landed below by id. REV closes nothing (charter); ARCH
dispositions everything here.

**Every open finding, condition, and due debt from M2, dispositioned:**

| Item | Disposition |
|---|---|
| **F-010** (REV cond. 1: the gate's real headroom is **+2.71%**, not the +7.07% the gate doc argues — a one-level OD backoff on the SAME floor collapses the margin) | **INTAKEN → M3-S1.** The bake-off must be judged against a bar whose distance is stated honestly. S1 implements the stronger floor as a NEW named baseline through the evaluator (`configs/train.yaml: baselines` already legislates: a deeper hierarchy "is a NEW baseline with a new name, never an edit"), measures it, and the MLE makes the gate decision the row's closing conditions name: adopt it as the gate's floor with the bar re-argued, or keep the published floor with the bar re-argued against **2.71%**. Either is tightening or honesty, not loosening — MLE's to argue, no PO fork. This kickoff deliberately does not re-quote 7.07% as headroom anywhere. |
| **F-011** (REV cond. 2: `gate.decide()` never consults the incumbent; a challenger WORSE than the serving champion can take the alias) | **INTAKEN → M3-S1, and S1 is sequenced BEFORE any story that can promote** — REV's condition verbatim: closed before the bake-off promotes anything, not after. Closes only by its ledger conditions: a WATCHED refusal of a challenger that clears the floor bar and regresses against the incumbent, both models' KPI-09 AND KPI-10 in the transcript, alias proven unmoved (the M2-S3 snapshot-before-and-after shape). |
| **F-012** (REV cond. 3: `make predictions` checks the challenger half against the registry and never the floor half — every published KPI-13 rests on the unchecked half) | **INTAKEN → M3-S1** (REV: cheapest beside F-011). Closes only by its ledger conditions: the floor's re-scored MAE checked against `gate_floor_mae` as a refusal to write, plus a red-team showing the write REFUSED when the floor is fitted on different months. Not closable by a manifest field — `predictions.json` already records it and nothing reads it back. |
| **F-008** (a sampled run makes the gate EASIER to pass — floor degrades faster than the model; measured 7.07%→16.85% on a 1-month sample) | **INTAKEN → M3-S1**, its named landing ("lands M3"). This is the milestone whose scout and sniper sample BY DESIGN (ADR-007/008), so the trap is now load-bearing: S1 closes it by the row's option (a) or (b) — gate-disqualify non-full train sets, or stamp the sample on verdict and version tags — BEFORE S3/S4 produce sampled runs. Rule for the bake-off either way: **contenders are refit on the full configured train months before they face the gate**; scout/sniper numbers are scout-internal (gotcha #15). |
| **F-007(b)** (`trip_distance` is the meter's DRIVEN distance; the dossier must resolve the quote-time substitute) | **INTAKEN → M3-S2**, its named landing (row: "(b) remains M3's"; §9/M3-S1 scope quoted: "distance/bearing features come from TLC zone-shapefile centroids"). Resolved AT the Design Review with minutes committed — either the zone-centroid substitute (haversine/bearing from the shapefile) or a recorded assumption. Closing this closes the whole F-007 row (condition (a) discharged at M2-S2). |
| **F-013** (NEW, filed this triage: two bootstrap-era config stubs contradict the live truth — `configs/promotion.yaml` carries `gate_ratio: 0.85`, a SECOND gate definition that agrees with nothing, and `configs/features.yaml` names `trip_distance` inside "v1", a column `EXCLUSIONS` refuses by law) | **INTAKEN → M3-S1 (promotion.yaml) and M3-S3 (features.yaml).** The port-family twins lesson: two definitions one directory apart, one of them stale, is how a future session trains against the wrong bar or re-admits leakage "per the config". The gate has ONE home (`configs/train.yaml: gate`, pinned by verify-m2 §2); feature sets get ONE home at S3 when v2 is named. Ledger row added this session. |
| **F-009** (alias-URI load fails on MLflow 3.15.1; `get_model_info` resolution is the localized workaround; narrowed at M2-S5 by gotcha #39's impostor) | **CARRY, not due — landing M5**, quoted scope re-verified: §9/M5 *"v1's M4 (KServe Standard, mlserver, storage-config, THE parity test 1e-6, p95 measured, self-heal under load)"* — the serving story that resolves `models:/nyc-taxi-eta@champion` is the story that closes it by its row's (a) or (b). M3 keeps using the one-place resolution in `score.load_champion`; nothing else learns the logged-model id. |
| **F-001** (starter allowlist; agent cannot self-widen) | **PO fork standing** — AWAITING_PO 2026-08-16-2, non-blocking, unchanged through M1 and M2. This session hit the same wall (a `\| tail` pipe refused); worked inside it. Nothing new owed; the paste is the PO's. |
| AWAITING_PO 2026-08-17-1 (libgomp one-liner) | **Standing, non-blocking, PO's hands.** The shim keeps training alive; M3 adds `xgboost` (another OpenMP consumer) so the shim's coverage is a named risk below, not a new fork. |
| D-001 (images → kind nodes) | **CARRY, not due — landing M4**, quoted scope re-verified: §9/M4 *"v1's M3 unchanged: Flyte 2 per docs, **containerized**, ingest→validate→features→train→evaluate→register"*. Ledger row unchanged. |
| D-003 (23 GB full-refresh peak when the publish becomes scheduled) | **CARRY, not due — landing M4**, quoted scope re-verified: §9/M1-S6 *"From M4 the build+publish runs as the tail task of the monthly Flyte pipeline"*. Ledger row unchanged. |
| D-004 (the M4 image owes a real `libgomp1`; the shim must be proven dead in the container) | **CARRY, not due — landing M4**, quoted scope: same §9/M4 sentence as D-001 — the story that builds the training image installs the real package. Ledger row unchanged. |

**Verdict: M2 CLEANLY CLOSED — tagged `m2-closed`.** All §9/M2 accept-when legs
green against the quoted text (gate + memo with segment numbers + board rendered
and linked), verify re-run green at the boundary by the approver, ◆ REV done
with mandatory findings filed and re-derivation performed, sign-off row added
(producer EXEC S1–S5, PRs #10–#14; approver ARCH/Fable — producer ≠ approver
holds), no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-17 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M2 gate green at the boundary | `make verify-m2` | GREEN, 49/49, exit 0 (paste in §0) |
| Cluster up | `kubectl get nodes` | 3/3 Ready, v1.36.1, age 6h |
| Champion exists and re-derives | verify-m2 §1 (8 sub-checks) | `nyc-taxi-eta` v1 `@champion`, run `3adee05a855a…`, signature over exactly the 5 configured features, verdict tags on the version, +7.07% vs the floor AS TAGGED at promotion (a historical record; the REAL current headroom is F-010's +2.71%) |
| MLflow up, experiment namespaced | verify-m2 §3 | `m2-modeling` holds 10 runs, all FINISHED, hobbled run kept and marked |
| Predictions + mart + board coherent | verify-m2 §5–§7 | 12,140,456 == 12,140,456; both whole-split rollups match the evaluator to 4 dp; a card RAN (24 rows) |
| Analyst layer live | verify-m2 §5 leg 1 | `[duckdb] GREEN — 8 month(s), every count reconciled: True` (12 views, 3 reconciliations) |
| M3 deps not yet present | `grep -E "flaml\|optuna\|xgboost" pyproject.toml` | empty — S4 adds them via `uv add` (resolve LIVE, never pre-pin from memory; pins → CLAUDE.md; gotcha #36's silent-downgrade shape is the named risk) |
| Scout/sniper knobs exist | `configs/automl.yaml` · `configs/tuning.yaml` | time_budget_s 1800 · study_namespace m3, n_trials 60, TPE + MedianPruner, storage postgres (no DSN in file) — re-verified at the Design Review, not edited silently |
| Artisan curriculum committed | `docs/artisan_playbook.md` | 122 lines, v1.0: catalog + iteration protocol + stop rule + leakage traps §5 |
| Dossier stub awaiting S2 | `docs/feature_dossier.md` | 26-line stub — S2 fills it from live sources |
| Disk headroom | `df -h /home/longt` | 947 G free |
| Tree clean, level with origin | `git status --short --branch` | `## main...origin/main`, clean, HEAD `f47c187`, tag `m2-closed` |

## Debt intake (every ledgers/debt.md row landing here, by id — or a PO fork, never a silent re-carry)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No debt row lands at M3.** D-001, D-003, D-004 all land M4 (each quoted in §0). Restated so the carries are visible, not silent. | — |
| (findings intake) | F-008 · F-010 · F-011 · F-012 · F-013 · F-007(b) | Findings are not debt, but their landings are honored the same way: F-008/F-010/F-011/F-012 + F-013(gate half) → S1 · F-007(b) → S2 · F-013(features half) → S3. Each closes ONLY by its ledger row's own evidence conditions. | S1, S2, S3 |

## Gate being served (BLUEPRINT §9/M3, quoted)

> Two workflows, equal budgets, one impartial gate. […] Accept when: dossier
> holds ≥10 candidates each with source + leakage note; the ablation table shows
> per-group deltas; the leakage red-team transcript exists (inflation observed,
> then removed); S3's resumability and pruning arms pass as before; all five
> gate verdicts printed from evaluator-traceable MLflow runs. Show: the dossier,
> the ablation table, the 2×2 bake-off table. ◆ REV reviews the bake-off
> claim-by-claim AND audits v2's aggregate features for leakage — re-deriving at
> least one aggregate from raw under the point-in-time constraint.

Standing law restated for every story: reported numbers come from
`taxi_mlops.training.evaluate` ONLY — scout/sniper/leaderboard numbers are
"scout-internal", quoted as hypotheses (gotcha #15, BLUEPRINT §5) · `month` is
never a feature · aggregates are legal only fit on TRAIN months, keyed
point-in-time (playbook §5 traps 1–2) · marts boundary law: `grep -r
"analytics" src/taxi_mlops/` stays empty · every feature in a serving set names
its request-time source (gotcha #21) · gates loosen only via PO fork;
tightening is the MLE's to argue.

## Stories (5; each independently finishable, safe stopping point after each)

### M3-S1 — The gate learns about the incumbent, the honest floor, and samples  (role:MLE)
Sequenced FIRST on purpose: everything M3 fields is judged by this gate, and
REV's condition is that F-011 closes before anything can promote.
Do, four findings by their own closing conditions:
- **F-011**: `gate.decide` gains an incumbent condition fed from the resolved
  `@champion` version's own tags (KPI-09 AND KPI-10), or promotion becomes a
  second explicit comparison `registry.promote` refuses to bypass — executor's
  craft call between the row's (a)/(b), recorded. The M2-S3 purity law holds:
  decide stays pure, registry stays the only mutator, the test that keeps them
  apart stays green. **Watched red-team**: a challenger that clears the floor
  bar and regresses against the incumbent → REFUSED with both models' KPI-09 and
  KPI-10 in the transcript, registry snapshot identical before/after (read the
  alias via `get_model_version_by_alias` — gotcha: `search_model_versions`
  returns `aliases` empty on 3.15.1).
- **F-012**: `score.score` checks the re-fitted floor's re-scored MAE against
  the version's `gate_floor_mae` tag on the SAME terms as the challenger check —
  a refusal to write, not a note. **Red-team**: floor fitted on a different
  month set → write REFUSED, `data/predictions/` untouched.
- **F-008**: the `--train-months` override becomes gate-disqualifying (row
  option (a), recommended — it matches how decide already raises on the wrong
  split), or the sample is stamped on verdict + version tags (option (b)).
  Either way a sampled run can never read as a full-data promotion.
- **F-010**: implement `baseline-group-median-od-fallback` as a NEW named
  baseline (global median → OD-pair median → global; never an edit to the
  published floor) through the SAME evaluator, measure val + test, then make
  the gate decision in `configs/train.yaml: gate` with the reasoning in the
  comment: adopt it as the floor (bar re-argued against ITS margin) or keep the
  current floor (bar re-argued against **+2.71%** real headroom, F-010's
  measured number, quoted in the comment). Expected ≈3.3518 test MAE for the
  new baseline — a large disagreement with REV's derivation is a bug, not a
  discovery.
- **F-013 (gate half)**: delete `configs/promotion.yaml`. The gate has one
  home; a test may pin that no second file under `configs/` names a gate knob.
Wall, named: `make verify-m2` §2 replays M2's transcripts through
`gate.decide` ON DISK — it must stay GREEN. Design the incumbent/floor changes
so historical verdicts still replay (e.g. incumbent metrics an optional input,
M2 replays carrying none; floor name checked against the version's OWN tags,
which is where verify-m2 §1 already reads it). If a replay leg's calling
convention must change, the leg is updated in the same PR, never weakened —
verify-m2 red at any point in this story is a stop-and-fix, not a note.
Accept when: all four ledger rows closed by their own conditions (each needs
its transcript/red-team named above); `promotion.yaml` gone; `make verify-m2`
GREEN 49/49 after the change; unit tests cover the new refusals; PR green +
lineage.
Evidence plan: the watched incumbent refusal + the floor-mismatch write
refusal + the sampled-run disqualification transcript + the new baseline's
val/test numbers + the gate-config diff with its re-argued comment.
Safe stop: after merge; the gate is honest and incumbent-aware, nothing new
promoted, M2's record untouched.

### M3-S2 — The feature dossier and the Design Review  (role:DA + MLE hat for the review)
Do: harvest community wisdom LIVE — the 2017 Kaggle NYC taxi-trip-duration
competition's documented top solutions plus current write-ups — via `curl` /
`gh api` (WebFetch is off the allowlist; M1-S3's prior-art path is the
precedent) into `docs/feature_dossier.md`: **≥10 candidate features**, each
with source, rationale, leakage-risk note, and an adaptation note where the
data shape changed (2019 TLC files carry zone ids, not coordinates — the
playbook's catalog §2 is the map; verify its 2026-08-12 claims live, correct
drift). Acquire the **TLC taxi-zone shapefile**, sha256-pin the download (the
`raw_manifest` pattern), derive the 263-zone centroid table as a committed or
DVC-tracked artifact with its derivation script — the source for
haversine/bearing at S3 and the quote-time distance substitute. Then hold the
**Design Review ritual** (minutes to `docs/rituals/`, the M1 Data Contract
Review's shape): (1) equal budgets — automation's `time_budget_s: 1800`
re-affirmed or re-pinned, artisan wall-clock set EQUAL (playbook §3); (2) the
keep-threshold for feature groups (playbook default ≥0.5% relative val-MAE —
adopted or re-argued); (3) both tracks' search plans; (4) **F-007(b) resolved
formally**: `trip_distance` stays excluded, the zone-centroid distance is the
quote-time substitute (or a differently-evidenced recorded assumption —
playbook §5 trap 3); (5) bake-off comparability rules: contenders are
FULL-DATA, TRAIN-ONLY fits (playbook §3.7's train+val refit is NOT used at M3,
so all five contenders and the floor share one fitting window — recorded); (6)
the bar the bake-off is judged against, quoting S1's outcome.
Accept when: dossier holds ≥10 candidates each with source + leakage note (the
§9 gate leg); centroid artifact pinned and queryable; Design Review minutes
committed covering the six agenda items with named owners; F-007 row CLOSED in
the ledger (condition (b) evidence: the minuted resolution) in the same PR;
PR green + lineage.
Evidence plan: the dossier table + the shapefile manifest entry + the minutes
+ the F-007 ledger diff.
Safe stop: after merge; pure docs + one pinned artifact, no model code touched.

### M3-S3 — The artisan track: feature-set v2, earned group by group  (role:MLE)
Do: executed **per the committed `docs/artisan_playbook.md`** — the curriculum
is law, the dossier is the menu, the Design Review's budget and keep-threshold
bind. Implement the dossier's survivors as feature-set v2 in the ONE shared
transform path (`src/taxi_mlops/features` — training AND serving, gotcha #21:
every feature names its request-time source). Iterate under the protocol:
sample-first (~15% stratified; winners confirmed at full scale before "keep"),
one change per experiment, fixed seeds, a ledger row per experiment (MLflow
run in experiment `m3-artisan` + a table in the story PR — no row, no claim),
groups admitted only past the keep-threshold, stop rule enforced (budget
exhausted or two consecutive loops below threshold — diminishing returns is a
result, record it and stop). **Ablation table** committed: per-group val-MAE
deltas proving which families earn their keep. **Leakage red-team, on a
disposable branch**: fit one aggregate across ALL months on purpose, watch val
inflate while the untouched test month doesn't, document the gap with numbers,
delete the branch (transcript survives in the PR). Train-only, point-in-time
aggregates that survive ablation are named as M8 Feast candidates in the
dossier's verdict column. **F-013 (features half)**: feature-set definitions
get ONE home — either `configs/features.yaml` becomes the real versioned
registry that `configs/train.yaml` references, or it is deleted and the
version registry lives in `train.yaml`; the stale line naming `trip_distance`
in v1 must not survive the story, and the exclusions law (`EXCLUSIONS` +
`FeatureLeakageError`) keeps refusing at both ends. Final v2 config fitted on
full train, logged with signature + input example. **Nothing promotes here** —
the registry API stays out of this story's diff; the gate sees v2 at S5.
Accept when: ablation table committed with per-group deltas (the §9 gate leg);
experiments ledger complete; leakage red-team transcript exists (inflation
observed, then removed, branch deleted); v2 named in ONE config home with the
stale stub resolved; v2 model logged (signature + input example) in
`m3-artisan`; unseen-category paths tested for every new categorical/aggregate
feature (the ~0.017% unseen-OD law); registry untouched; PR green + lineage.
Evidence plan: the ablation table + the experiments ledger + the red-team
transcript + the MLflow run listing.
Safe stop: after merge; v2 exists and is measured, nothing promoted.

### M3-S4 — The automation track: FLAML scout, Optuna sniper, run twice  (role:MLE)
Do: deps live (`uv add` FLAML, Optuna, xgboost + Optuna's Postgres driver —
resolve against pandas 3.0.5/numpy 2.5.2 LIVE; gotcha #36's silent-downgrade
shape and the 3-attempt quarantine wall below). The Optuna storage database is
created by **D-002's proven recipe**: one line in
`scripts/postgres_databases.sh` + one ADDITIVE key in
`scripts/platform_secrets.sh` (the M1-S5 Metabase precedent — before/after
paste required; no DSN ever enters `configs/tuning.yaml`). Then per BLUEPRINT
§5: **FLAML scout** under `configs/automl.yaml`'s budget, run TWICE — once on
feature-set v1, once on v2 — output = winning family + starting params, every
internal number labeled **scout-internal** (gotcha #15). **Optuna sniper**:
search space centered on each scout winner, TPE + MedianPruner per
`configs/tuning.yaml`, study namespaced `m3` (gotcha #17), storage in the one
Postgres, every trial an MLflow nested run under one parent in `m3-automl`;
**≥1 pruned trial shown**; **kill-and-resume demonstrated** — the study killed
mid-run, resumed from Postgres, trial count continuing, transcript pasted.
Scout/sniper iterate on samples BY DESIGN — S1's F-008 machinery is now live,
so sampled runs are visibly non-gateable (or sample-stamped): this story
EXERCISES that guard once and pastes it. The two best configs (auto-on-v1,
auto-on-v2) are then **refit on the full configured train months** through the
one evaluator, logged with signature + input example. Nothing promotes here.
Accept when: scout ran twice under budget with scout-internal labeling; sniper
resumability + pruning arms pass (kill-and-resume transcript, ≥1 pruned trial
— the §9 gate leg); the `optuna` database converged by the recipe (run-1/run-2
paste); both auto contenders refit full-data and logged in `m3-automl`; the
F-008 guard exercised on a real sampled run (transcript); registry untouched;
new pins recorded in CLAUDE.md; PR green + lineage.
Evidence plan: the two scout summaries + the Optuna study listing from
Postgres + the kill-and-resume transcript + the MLflow parent/nested run ids.
Safe stop: after merge; four measured contenders exist, nothing promoted.

### M3-S5 — The bake-off, the alias decision, and verify-m3  (role:MLE; MLOps hat for the verify half)
Do, first half — **the 2×2 (+ floor) bake-off**: five contenders — the gate's
floor baseline (per S1's decision) · M2 champion v1 (hand, v1 features) ·
artisan (hand, v2) · auto-tuned on v1 · auto-tuned on v2 — every number from
`taxi_mlops.training.evaluate` on the untouched test month, **all five gate
verdicts printed** (floor vs itself is an expected REFUSE; that is the point of
printing it). The table isolates WHERE improvement came from: features, tuning,
or both — an automation loss (or an artisan loss) is a valid, reportable
result, stated as such. Winner → challenger → **the S1-hardened, unchanged
gate decides the alias**, incumbent condition live. **If the alias moves**, the
published-champion chain must follow it, in order: `make predictions` (F-012's
floor check now guards the write) → `make duckdb` → `make marts` → `make
boards`, and the error memo gains a dated M3 section carrying the new
champion's whole-split numbers via `scripts/error_memo_numbers.py` (a memo
describing a model nobody serves is no longer "visible to everyone"); `make
verify-m2` is then re-run — its "champion right now" and memo-twin legs are
exactly the tripwires this refresh exists to satisfy. If the alias does not
move, nothing is refreshed and that too is stated.
Do, second half — **`make verify-m3` becomes real**, superseding the stub, the
M2-S5 discipline inherited whole: every §9/M3 accept-when leg gets a sub-check
that asserts a POSITIVE count or a matched line (dossier ≥10 with source +
leakage columns · ablation table present with per-group deltas · leakage
red-team transcript exists AND its inflation numbers parse · Optuna study in
Postgres with ≥1 pruned trial and a resumed run · five verdicts replayed
through `gate.decide` on disk, the M2 replay law · the incumbent/floor/sample
guards each provably armed · registry state coherent with the bake-off's
printed outcome · F-013's stubs really gone) — no skip flag, no fast mode,
`expect_verdicts` per leg, re-fits NOTHING. Then **red-team it once**: break
one leg → RED naming exactly that leg, others still counted → restore → GREEN
(both pasted).
Accept when: the five-row bake-off table committed, every number
evaluator-traceable to an MLflow run (the §9 gate leg); the alias decision
transcript (moved with the refresh chain green, or held with the refusal
printed); `make verify-m3` GREEN exit 0 with every sub-check printing;
red-teamed to RED once naming the broken leg, restored GREEN (both pasted);
`make verify-m2` still GREEN; PR green + lineage.
Evidence plan: the bake-off table + the gate/alias transcript + both verify-m3
transcripts (+ the refresh-chain pastes if the alias moved).
**Sizing honesty**: if the alias MOVES, the refresh chain makes this two
sessions' work — the declared mid-story safe stop is after the bake-off +
transition merge; verify-m3 and the ◆ exit then finish in a follow-on session
on this same story card. A story that spills a session is fine; a gate built
in a hurry is not.
Safe stop: the M3 exit. **Ritual: M3 carries ◆ →
`automation/next_session.sh rev 120`** (fresh REV session, artifacts only,
mandatory finding; reviews the bake-off claim-by-claim AND re-derives ≥1 of
v2's aggregate features from raw under the point-in-time constraint). REV
exits to `automation/next_session.sh architect 120` for the M3 boundary.

## Out of scope (named now so creep is visible later)

Flyte / containerized pipelines (M4; D-001/D-003/D-004 land there) · serving,
KServe, parity tests (M5; F-009 lands there) · Ray Tune / KubeRay (M9 stretch,
by design — §5) · weather joins (deferred, playbook catalog) · the OSRM
263×263 zone matrix — optional ONLY inside S3's budget per the playbook, else
it stays the named M9 stretch; never a reason to blow the equal-budget law ·
AutoGluon (quarantine pattern pre-approved by ADR-007 if the PO ever asks;
not fielded) · stacking/ensembles (refused, playbook §4 — operability) · a new
error memo or new boards beyond the champion-transition refresh (M7 owns the
next analysis wave) · widening the session allowlist (PO's hands, AWAITING_PO
2026-08-16-2) · `sudo apt install libgomp1` (PO's hands, AWAITING_PO
2026-08-17-1) · loosening any gate or threshold (PO fork, ever).

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| FLAML/xgboost/Optuna resolution against pandas 3.0.5 / numpy 2.5.2 — the mlflow precedent was a SILENT two-major downgrade (gotcha #36) | 1 (M2-S2) | Bounded ranges at `uv add`, read the resolution before accepting it; 3-attempt wall → ADR-007's quarantine (separate venv, exchanges predictions only, scored by OUR evaluator) — never downgrade the core stack (gotcha #16) |
| xgboost needs OpenMP too, and this host has none (gotcha #37) | 1 (M2-S2) | The shim's `LD_LIBRARY_PATH` covers any consumer in-process; if xgboost's loader wants more, quote AWAITING_PO 2026-08-17-1 and drop xgboost from `estimator_list` for the session rather than park (FLAML runs the remaining families; D-004 fixes the class at M4) |
| Sampled runs meet the gate (F-008) — scout/sniper sample by design | measured (M2-S3: margin 7.07%→16.85% on 1 month) | S1 closes it BEFORE S3/S4 run; bake-off contenders refit full-data (Design Review rule 5) |
| A tuned challenger worse than the incumbent takes the alias (F-011) | 0 live, filed by REV | S1 closes it before S5 can promote; the watched refusal is its evidence |
| Gate replay legs in verify-m2 break when the gate learns new conditions | 0 | Named wall in S1: historical verdicts must still replay; legs updated in the same PR if signatures force it, never weakened; verify-m2 red = stop-and-fix |
| Champion transition leaves predictions/mart/board/memo describing the OLD model | 0 (anticipated — F-012's exact failure shape) | S5's ordered refresh chain; verify-m2's "champion right now" + memo-twin legs are the tripwires; F-012's floor check refuses a stale-window write |
| Optuna study/experiment collisions in shared Postgres (gotcha #17) | 0 | `study_namespace: m3` pinned in tuning.yaml; experiments `m3-artisan`/`m3-automl` namespaced from the first run |
| Optuna's Postgres DSN leaks into a config or argv | 0 | tuning.yaml law: `storage: postgres` resolved via env; D-002's recipe passes credentials on stdin only |
| Live harvest without WebFetch (allowlist, F-001) | 1 (M1-S3) | `curl` + `gh api` precedent (eight sources read live for prior_art.md); if a source refuses curl, cite what IS reachable and record the gap |
| Artisan loops overrun the session (42M-row full-scale confirms) | 0 | Playbook §3 sample-first law; the Design Review budget binds; stop rule is a result, not a failure |
| Leakage red-team branch survives / pollutes | 0 | Playbook §5 trap 2: disposable branch, transcript in PR, branch deleted — S3 accept-when names the deletion |
| Docker Desktop down after host restart — `kubectl: command not found` | 1 (M1-S5) | Gotcha #34: the chain PARKS naming the gotcha; recovery is one launch + ~15s; never self-launch Windows processes |
| Kaspersky TLS on new PyPI wheels (gotcha #9) | 0 | Import AV root CA into WSL trust — never disable verification |
| Two writers on append-only docs | 1 (M0-S1) | Rebase onto origin/main, keep theirs, renumber yours; never force-push main |

## Open PO questions (options · recommendation · default-with-date)

None blocking — the chain continues. Standing, non-blocking, both restated in
§0: **AWAITING_PO 2026-08-16-2** (allowlist paste, Option A recommended) ·
**AWAITING_PO 2026-08-17-1** (libgomp one-liner, Option A recommended — now
mildly more valuable, since M3 adds a second OpenMP consumer).

## ARCH self-check (v3.0)

model stated Fable: **yes** (claude-fable-5, first line) · every story sized
for one short executor session: **yes** (S5 is the fattest and carries a
DECLARED mid-story safe stop + two-session allowance if the alias moves; S1–S4
each ride proven patterns — the gate/registry test seams, the prior-art
harvest path, the playbook protocol, the D-002 recipe) · debt intake diffed
against ledgers/debt.md: **yes** (no row lands here; D-001/D-003/D-004
restated not-due with quoted M4 landings; findings F-008/F-010/F-011/F-012/
F-013 → S1, F-007(b) → S2, F-013(features) → S3, F-009 restated → M5) · forks
routed to AWAITING_PO: **yes** (none new; two standing non-blocking entries
restated; F-010's floor decision is tightening/honesty, MLE's to argue, per
CLAUDE.md — not a fork)
