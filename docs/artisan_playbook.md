# Artisan playbook — M3-S2: the Kaggle-grade workflow, adapted for production

v1.0 — 2026-08-12. Pre-loaded curriculum authored by the Architect so the artisan
track imitates what is already proven best, rather than rediscovering it. The
competition record below was checked against live sources on 2026-08-12; S1's
dossier work re-verifies the details live and corrects any drift — trust, then
verify. This playbook is method; `docs/feature_dossier.md` is the live evidence
table it feeds.

## 0. The competition record (where the wisdom comes from)

Kaggle, *New York City Taxi Trip Duration* (2017; 1,257 teams; metric RMSLE —
root-mean-squared-log-error). Two leagues emerged:

- **With external data**: winner 0.28976 RMSLE. The decisive external sets were
  **OSRM road-network routes** (real driving distance/time per trip, not straight
  lines) and **weather**. Solutions in this league (e.g., 4th place, 0.31044)
  used heavy feature engineering plus 2-level stacking.
- **Without external data**: winner 0.36185; the famous 4th-place "beluga"
  approach (0.36331) — feature engineering, PCA, clustering, XGBoost — became
  the canonical public kernel for this problem.

The gap between leagues (~0.29 vs ~0.36) is itself the loudest lesson: **the
road network beat every modeling trick.** Features that encode reality outrank
algorithms that fit it harder.

## 1. The five lessons that made winners (and why each works)

1. **Model the target in log space.** `log1p(duration)`: durations are
   heavy-right-tailed and errors are multiplicative (being 5 min wrong on a
   10-min trip ≠ on a 2-hour trip). We train in log, invert predictions, and
   the MAE gate judges in natural minutes.
2. **Geometry beats raw position.** Distance alone is weak; *direction* matters
   because Manhattan's grid is anisotropic (north–south flows differently than
   crosstown): hence haversine + **bearing**. The comp's PCA-rotation trick
   (rotating coordinates ~30° so tree splits align with the street grid) and
   KMeans clustering (discretizing space into "places") were big — for us they
   are **already done by the data**: TLC zones ARE the clusters. We inherit the
   idea via zone-centroid distance/bearing and zone-pair identity.
3. **Road-network truth (OSRM) was the single biggest edge.** Straight lines
   don't know about rivers, bridges, and one-way grids. Bounded adaptation for
   us: a **one-time 263×263 zone-centroid matrix** (~69k routes) computed
   against a local OSRM container, joined by zone pair forever after. Optional
   story if S2 budget remains; otherwise the named M9 stretch.
4. **Traffic lives in aggregates.** Cluster/hour average speeds and trip counts
   acted as traffic proxies — powerful, and one step from disaster: *per-trip*
   speed is the target in disguise (speed = distance / duration). Aggregates
   are legal only when fit on TRAIN months, keyed point-in-time.
5. **Iteration is a discipline, not a mood.** The strong performers ran an
   experiment ledger: one change at a time, fixed seeds, early stopping on
   validation, groups of features admitted only when they paid measurable rent.

## 2. Adapted feature catalog (feeds the dossier; per-family "why")

| Family | Features | Why it works | Our adaptation | Leakage note |
|---|---|---|---|---|
| Temporal | hour, weekday, month, week-of-year; holiday; rush flags | demand & congestion cycles | direct | none |
| Spatial | centroid haversine; **bearing**; borough-pair; airport flags | grid anisotropy; airports have queue dynamics | zone-shapefile centroids | none |
| Route truth (opt.) | OSRM zone-pair drive distance/time | rivers & bridges are real | one-time 263×263 matrix, local OSRM | none (pre-trip knowable) |
| Traffic proxies | zone-pair median duration; PU-zone×hour mean speed; hourly trip counts | congestion memory | fit on TRAIN only | **HIGH** — §5 traps 1–2 |
| Trip shape | circuity = odometer ÷ centroid-straight-line | route directness signal | — | **serving-time caveat, §5 trap 3** |
| Target | log1p transform | multiplicative errors | invert before the MAE gate | none |
| Not transferable | PCA rotation; KMeans clusters; per-point geometry | (already achieved by zone discretization) | — | — |
| Deferred (M9) | weather joins | modest comp gains; another source to govern | NOAA, point-in-time | date-keyed only |

## 3. The iteration protocol (one loop ≈ 30–45 min; budget = automation track's)

0. Harness first, frozen: evaluator + gate untouched; val = 2019-07; test month
   sacred — **one** final shot at it.
1. **Sample-first**: iterate on a ~15% stratified sample; confirm winners at
   full scale before they enter the ledger as keeps.
2. **One change per experiment.** Fixed seeds. Early stopping on val.
3. **Ledger row per experiment** (MLflow run + a table in the story PR):
   id · what changed · Δval-MAE · keep/drop · one-line note. No row, no claim.
4. Features enter in **groups**; a group is kept only if it clears the
   keep-threshold declared at the Design Review (default: ≥0.5% relative
   val-MAE improvement). Enthusiasm is not a threshold.
5. After each loop: feature importance + error slicing against the M2 memo's
   weak segments (did airports get better, or just the average?).
6. **Stop rule**: budget exhausted OR two consecutive loops below threshold.
   Diminishing returns is a *result* — record it and stop like a professional.
7. Finalize: refit the winning config on train+val; single test-month
   evaluation through the gate; seed-average (3 seeds) if budget remains.

## 4. What we deliberately do NOT imitate (production ≠ competition)

- **Random K-fold CV → temporal splits.** The comp's test set was the same
  period as train, so random folds were honest there. Production predicts the
  *future*; our folds respect time. This single difference explains many
  "great CV, dead in prod" stories.
- **RMSLE → MAE gate.** We keep log-space *training* but judge in minutes —
  a gate the business can read.
- **Stacking → single model.** The comp's 4th place ran 20 models in 2 levels.
  We refuse: a stack breaks M5's 1e-6 parity story, muddies M6's canary and
  rollback, and buys the last 0.5% at the price of operability. Production
  optimizes for the system, not the leaderboard.

## 5. Leakage traps specific to this problem (read BEFORE writing S2 code)

1. **Per-trip speed or pace is the target wearing a mask** (speed =
   distance/duration). Never a feature. Aggregated historical speeds are the
   legal substitute.
2. **Aggregates fit on all months** inflate validation while the untouched test
   month stays honest — S2's red-team demonstrates exactly this on a disposable
   branch, then deletes it.
3. **A serving request cannot know the odometer.** `trip_distance` is measured
   *after* the trip ends; a true pre-trip ETA can't use it. Centroid-haversine
   and OSRM distances ARE knowable pre-trip. Consequence: v1's use of
   `trip_distance` (M2) gets formally revisited at the M3 Design Review —
   either reclassified as a quoted-distance proxy with the assumption recorded,
   or dropped from serving sets. Rule going forward: **every feature in a
   serving set names its request-time source** (gotcha #21).
4. **Filter asymmetry**: rows cleaned away in training (zero-distance,
   negative fares) will still arrive as live requests — serving must handle
   what training excluded, not crash on it.

## 6. S2 exit checklist

Dossier verdict column filled from ablation numbers · ablation table committed ·
leakage red-team transcript (inflation observed → removed) · experiments ledger
complete · winning artisan model registered as challenger · `configs/
features.yaml` v2 list updated to the survivors · field note written.
