# M9 KICKOFF — Stretch: the demo page & the program's close   (authored by: ARCH/Fable · 2026-08-23 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M9 carries no ◆** (BLUEPRINT §9: M9 lists no REV ritual). M9 is the LAST
milestone in §9, so its boundary is the program's close: the last story exits to
`automation/next_session.sh architect 120` and that architect session closes the
program, not the next milestone.

**M9's committed scope is ONE story — the stakeholder demo page — by PO
direction 2026-08-12** (BLUEPRINT §9/M9: "opt-in per story, EXCEPT the demo —
committed"). Every other §9/M9 stretch item (Ray/KubeRay, CI nightly smoke,
trivy + secret-scan, README portfolio polish) **requires PO opt-in and is
routed to AWAITING_PO 2026-08-23-2** — an opt-in menu, non-blocking, because
the committed demo plus this boundary's chartered closure work fill the
milestone. The other three stories below are boundary-chartered closure work
(open findings and the routed residual R-2), which is ARCH's planning
authority, not stretch.

**The four laws this milestone lives under, stated once at the top.**
(1) **THE CLUSTER IS STATEFUL AND NO M9 STORY MAY TAKE IT DOWN** — unchanged
since M2. No new hostPort (kind publishes host ports at cluster-CREATE only);
anything new is reached through the EXISTING 8081 route or by ephemeral
port-forward. `make backup` before any story that adds cluster state.
(2) **THE DATA IS SETTLED — 2019 AND 2020 BOTH.** `dvc status` on every
settled pin is the story-exit invariant. Nothing in M9 reads a new month.
(3) **THE ALIAS DOES NOT MOVE AND NOTHING IS FITTED.** `@champion` is version
2 / feature set v2 before and after every story; no story invokes the gate,
mints a registry version, or cuts the champion's wire over. The demo CONSUMES
the transformer's raw boundary; it does not change what serves. **`uv.lock`
stays byte-identical to the `m7-closed` tag** — no M9 story adds a project
dependency (F-057's fix touches the QUARANTINE pin file, not `uv.lock`).
(4) **A BAR IS ARGUED BEFORE THE MEASUREMENT IT JUDGES** (M8 law 4, ninth
inheritance). M9-S2's watchdog thresholds get their own headroom leg, argued
from RECORDED facts and committed BEFORE the drill that first crosses them —
checkable from git, the M7-S3/M8 idiom.

## 0. Boundary triage of M8 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-23):** `make verify-m8`
→ **GREEN — 51 `ok` sub-checks across 7 sections, exit 0** (counted live:
`grep -cE "ok  "` → 51, run twice). Closing line verbatim:
`[verify-m8] GREEN — every M8 sub-check passed.` Highlights, pasted not
remembered: §5's five live questions all answered — the champion's wire, the
transformer answering the same hazard from four RAW fields at
`|Δ| = 0.000e+00` with `X-Taxi-Lookups` naming the two groups that did NOT
cross, the feature server two-sided, **57,688 keys at `noeviction`** read off
the running Redis, and F-043's PromQL question reading
`every scraped predictor exporter in namespace 'serving' reads up==1 (2 target(s))`
(F-061's fix holding live); §7's alias law in its strong form — `NOT ONE of
the 2 registry versions was created after the m7-closed tag`; all 5 settled
DVC pins `up to date`. **`make verify-m7` re-run the same session → GREEN**,
closing line verbatim `[verify-m7] GREEN — every M7 sub-check passed.` —
§9/M8's accept-when inherits it ("v1's M7 gate AND the comparison page
exists"), and both halves are green: the page is
`docs/feast_side_by_side.md` (12 rows, 3 ADOPT · 4 DIFFER · 5 SURPASS), the
Show artifacts are the parity table + the page, both committed.

**Lineage spot-check (gotcha #20):** `git branch -r --contains 9e39d2a`
(M8-S5's story commit, PR #60) → `origin/main`. M8 landed as PRs
**#52–#56, #58–#60** (S1 in two PRs, S4 in three legs).

**Red team:** `make verify-m8-redteam` PASSED at M8-S5 leg 2 (one
`both_missing` count 13 → 0 — a correct-looking measurement of the wrong
population — RED exit 1 with 3 FAILs from three artifacts, 48 sub-check lines
still passing, sha256-identical restore `153c4399deab…`, GREEN 51/51).

**Dispositions — every open finding, condition, and residual, none silent:**
- **F-058** (FixedRate trigger back-fills missed windows; OPEN—mitigated) →
  **DECIDED option (a) at this boundary, CLOSED**: `retrain-schedule-proof`
  stays inactive permanently. Its proof is delivered and recorded
  (`automation/runs/m8-provenance/proof.json` — the pod resolving
  `rescale_factor` 6.6667 / `round_cap` 2400), so a standing FixedRate proof
  on a laptop that restarts buys nothing and costs a stampede per restart
  (measured: ~100 pods in a 17-second burst). Option (c) — a Flyte
  concurrency/backfill policy — stays the named probe for whoever next needs
  a schedule; **M9 legislates: no story registers a Flyte trigger** (M9-S2's
  cadence, if any, is a push from an existing command). `retrain-monthly`
  remains registered-and-inactive (a PO compute decision, unchanged since
  M7-S4). Evidence: control-plane readback in HANDOFF (cb) (`retrain-schedule-proof
  False`), the drained backlog, and the AWAITING_PO 2026-08-23-1 entry, which
  asked for no answer and gets this ratification.
- **F-057** (quarantine pin-file regenerator emits non-normalized names) →
  **INTAKEN → M9-S3**, exactly the row's own recommended fix: normalize in
  `_freeze`, regenerate ONCE in a commit that does nothing else, add the
  round-trip test, and re-prove the from-pins rebuild (the M8-S2 idiom) so
  the regenerated file's reproducibility claim is re-earned, not inherited.
- **F-054** (twelve `skipif(not RECORD.exists())` tests) → **DECIDED option
  (a) at this boundary, INTAKEN → M9-S3.** The deciding fact, verified live
  this session: the drill records those twelve tests read are **git-tracked**
  (`git ls-files automation/runs/m6-canary automation/runs/m6-shadow` →
  present — F-029's option A covered them at M5-S1), so option (a)'s stated
  cost ("a fresh clone cannot go green until the drills run") is void — a
  fresh clone HAS the records, and the assertion catches exactly one new
  thing: a deleted or lost record, loudly. This is the F-029/`test_bakeoff`
  precedent applied to its own residue.
- **F-016** (incumbent-margin gate fork) → **standing at AWAITING_PO
  2026-08-18-1, DORMANT in M9** (law 3: nothing is fitted, no gate invocation,
  no alias move — nothing rides on the answer).
- **R-1** (Feast `FeatureService` as the feature contract) → **DECLINED at
  this boundary, with the reason recorded**: applying it mutates the registry
  three artifacts are pinned against, needs a feature-server redeploy, and
  invalidates M8-S4's three parity records — a re-measurement story in the
  program's final milestone, purchased to replace a constant
  (`ZONE_FEATURES`) that is already pinned by tests on both sides of the
  wall. The idea stays recorded in `docs/feast_side_by_side.md` §3 as future
  work — visible, not silent. Not a fork: additive craft refused on cost.
- **R-2** (an alert on an empty or stale online store — the residual M8-S4
  legs 1, 2 and 3 each restated) → **INTAKEN → M9-S2**, with its own headroom
  leg per law 4. The demo (M9-S1) is the first PO-visible reader in front of
  the store; the watchdog lands in the same milestone.
- **R-3** (per-value lookup trace) → noted, unscheduled — stands as recorded
  in the page; the machine-checkable half (`X-Taxi-Lookups`) already exists.
- **AWAITING_PO 2026-08-16-2** (allowlist paste) and **2026-08-17-1**
  (libgomp one-liner) → standing with the PO, non-blocking, unchanged.
- **Error memo §7 row 2** (airport gap) → stays open in the memo with its
  three measurements; M8-S2's catalog named `airport_regime_flag` as the
  candidate reader; nothing in M9 fits, so it passes to the program close as
  documented future work.

**Debt: NONE DUE — the register is fully closed** (D-001…D-004). D-001's
registry-pattern deferral stands (trigger: image churn; landing: the next
PO-sanctioned rebuild) — M9 does not trigger it (the demo adds no image; S2/S3
rebuild none).

**README Status row flipped** (M8 → closed, M9 → in progress) in the same
commit as this kickoff. **Verdict: M8 CLEANLY CLOSED — tagged `m8-closed`.**

## Preconditions (verified LIVE at draft time — pastes, not memory)
| Precondition | Check run | Observed |
|---|---|---|
| M8 gate green | `make verify-m8` | GREEN, 51 `ok`, exit 0 (closing line verbatim above) |
| M7 gate green (inherited) | `make verify-m7` | GREEN, closing line verbatim above |
| Champion on the wire | `kubectl get isvc -n serving` | `nyc-taxi-eta` READY True, AGE 4d9h |
| Transformer live (the demo's endpoint) | same | `nyc-taxi-eta-transformer` READY True, AGE 59m — M8-S5 left it up deliberately, and M9-S1 depends on it |
| Online store + feature server | `kubectl -n feast get deploy,pvc` | `redis` 1/1 (PVC Bound 1Gi), `feast-server` 1/1 |
| Store holds features | `verify-m8` §5 live question | 57,688 keys, `noeviction` |
| The route | `curl localhost:8081/healthz` | 200 |
| Zone names for the pickers | `ls data/reference/` | `taxi_zone_lookup.csv` committed (with `taxi_zone_centroids.csv`, holidays) |
| Alias law | `verify-m8` §7 live | `@champion` → 2, `feature_set v2`, versions `['1','2']`, no version created after `m7-closed` |
| Chain state | `ls automation/STOP` | absent — the 2026-08-21 park was lifted by the PO; sessions ran 2026-08-23 |

## Debt intake (every ledgers/debt.md row landing here, by id)
| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **NONE DUE — the register is fully closed** (D-001…D-004, all with closing evidence) | — |

## Stories (4; each independently finishable, safe stopping point after each)

### M9-S1 — The stakeholder demo page (role:MLOps · DA C for stakeholder legibility)
**Committed by PO direction 2026-08-12 — the one non-optional M9 item.** One
self-contained HTML page under `demo/`: two zone pickers (names from the TLC
zone lookup), a date-time picker, submit → a live ETA with the serving model
version shown. Dependency-free by design (no JS framework, no build step).

**The design input the blueprint predates, stated so nobody rediscovers it:
the page targets the TRANSFORMER (`nyc-taxi-eta-transformer`), not the
champion's own wire.** The champion's endpoint eats a 24-column feature
matrix; a browser cannot run `taxi_mlops.features`, and re-implementing the
feature path in JavaScript is exactly what the one-transform-path law forbids.
M8-S4 leg 3 built the raw boundary for precisely this shape of caller: POST
four raw fields, get minutes back with mlserver's `model_version` stamp
forwarded verbatim. The demo is NOT a cutover (M8 law 3 carried): the
champion's wire remains the wire of record; the demo consumes the boundary
that exists beside it.

**The two execution wrinkles, named with their hazards (decide and RECORD,
per BLUEPRINT §9/M9):**
- **Host-based routing vs the browser.** Both isvc routes are host-based
  (`nyc-taxi-eta-transformer-serving.local`) and `fetch()` cannot set a Host
  header. Options: an Ingress rule on a host the browser naturally sends
  (`localhost` — a browser hitting `localhost:8081` sends exactly that), or
  serving the page itself through the same origin (one static route + one API
  route under one host — which also dissolves CORS entirely). Laws that bind
  the route: **F-039** (a hand-authored Ingress must never take a name KServe
  generates), **F-060/gotcha #106** (an accept on a new route must prove
  presence before asserting any absence; wait on the ROUTE under the Host
  header the next step will send).
- **CORS** — only exists if the page is served cross-origin. If the same-origin
  option is taken, record that the wrinkle dissolved and why; if not, decide
  ingress annotation vs server config and record it.

**Honesty requirements:** the zone list must be DERIVED from
`data/reference/taxi_zone_lookup.csv` (generated into the page by a small
committed script, or pinned by a test that diffs the embedded list against the
CSV) — a hand-retyped list is a twin that drifts. Zones 264/265 are "Unknown",
not places: either exclude them from the pickers with a note, or let them
demonstrate the no-geometry path honestly. Error classes render
distinguishably: an uncovered date (e.g. 2031) shows F-019's 422 refusal text
— the horizon is a feature to demo, not hide; a 503 (store unreachable) says
so rather than rendering as a broken page.

**Accept when:** the zone list renders from the lookup (derived, and checked);
a submitted trip returns a live prediction with the serving model version
visible; the demo reproduces a recorded number on the wire (the
federal-holiday hazard — zone 132 → 48 at 2019-07-04T09:15 → **39.0019
minutes**, `model_version: 2` — through the page's own request path, recorded);
the 2031 refusal renders as a named refusal; the route/CORS decision is
recorded in `demo/README.md` or the page's own header. **The final §9/M9 box —
"one non-technical person (the PO counts) completes a query unassisted,
observed" — CANNOT be closed by an unattended session: the story ends by
writing the AWAITING_PO entry inviting the PO to the observed run (with the
exact URL and the one command, if any, to run first). That box stays open in
the story record, named, non-blocking to the chain.**
**Evidence plan:** the page committed under `demo/`; an accept record
(`automation/runs/m9-demo/accept.json`) built from real requests through the
page's own request path (curl with the page's exact payloads); the recorded
route decision; the AWAITING_PO entry for the observed run.

### M9-S2 — The online-store watchdog (R-2) (role:SRE)
The residual three M8 stories restated and none closed: **there is no alert on
an empty or stale online store.** An all-null store yields an all-NaN geometry
table and a confident wrong quote no client can refuse (null is CORRECT for
264/265); `verify-m8` §5's DBSIZE question is the hand-run form; this story
makes it standing — right after M9-S1 put a PO-visible reader in front of it.

**Headroom leg FIRST (law 4):** argue the bars from recorded facts and commit
the argument BEFORE the drill — the expected key count from the
materialization record (57,688, `automation/runs/m8-online/materialize.json`),
what "stale" means for a store holding SETTLED 2019 windows (the
materialized-at stamp, not the data's own dates), and what the transformer
does when the store dies (503, measured — M8-S4 leg 3's refusal classes).

**The instrumentation hazard, named:** Redis exports no Prometheus metrics.
Two costed options, executor decides with a probe first (the
`DRILL_STAGE=ingest` idiom): **(i)** a `redis_exporter` (a NEW pinned
image — tag AND digest, the Metabase precedent — and a standing scrape);
**(ii)** a reader that asks Redis (DBSIZE + one canary lookup, e.g. zone 132
must answer and zone 264 must answer null-not-error) and PUSHES gauges with a
freshness stamp — the `push_serving_version.py`/A-4 idiom the repo already
owns, on the pushgateway that now has a PersistentVolume (F-050 (a)), covered
by the absence family (A-11's precedent). Option (ii) adds no image and no new
dependency; its honest cost is the freshness-clause discipline A-4 already
carries. **No Flyte trigger for the cadence (F-058's law, this kickoff §0).**

**Accept when:** the headroom/argument record is committed with an earlier
git-added commit than the first drill record (checkable from git, the M8 gate
idiom); the new signal id(s) land through `render_alert_rules.py` with their
`why` (a threshold whose argument is not beside it is refused by the
renderer); `docs/slo_serving.md` gains the section arguing them; a
prediction-first drill empties or stales the store, watches the alert(s) fire
and reach Alertmanager, watches the transformer refuse with 503 (not a wrong
number — the noeviction design proving itself end to end), re-materializes
(~7 s, recorded) and watches the clear; the must-not-fire negatives are
predicted and held; the residual sentence in `docs/transformer_m8.md` §6 /
ADR-012 / the side-by-side page gets a dated closure note naming the id.
**Evidence plan:** headroom record + drill record under
`automation/runs/m9-store-watch/`, prediction committed first and pinned by a
test; rules read back off `/api/v1/rules`.

### M9-S3 — Closure: F-057 and F-054 (role:MLOps)
Two open findings, both DECIDED at this boundary (§0), landed exactly as
decided — small, mechanical, and the program does not close over open rows it
could have shut.
- **F-057:** normalize in `feast_probe_record.py::_freeze`
  (`name.lower().replace('_','-')` per the row), then regenerate
  `infra/feast/requirements-feast.txt` in a commit that does NOTHING else (so
  the diff is reviewable alone), add the round-trip test (generate twice,
  diff empty; regenerated == committed), and re-prove the from-pins venv
  rebuild (delete `.venv-feast`, `uv pip install --no-deps -r …`, same
  package set — the M8-S2 proof, re-earned for the regenerated file).
  `uv.lock` untouched, asserted.
- **F-054, option (a):** the twelve `skipif(not RECORD.exists())` tests in
  `test_canary_and_rollback.py` (8) and `test_shadow_and_spike.py` (4) become
  assertions under the F-047 `needs_records` marker; update
  `test_record_marker.py`'s docstring (it argued against the older form —
  the older form is now gone) and its guard so the marker-coverage check
  stays derived, not enumerated. One full host suite run pasted; then delete
  one record locally (unstaged) and paste the RED to prove the assertion is
  real, restore, GREEN.
**Accept when:** round-trip test green; pin file regenerated in its own
commit with the rebuild re-proved; zero `skipif`-on-record-existence remain
under `tests/` (asked of the AST or grep with the two known files named);
host suite green with the new count; the two findings rows CLOSED with this
evidence. **Evidence plan:** the two commits, the suite transcripts, updated
`ledgers/findings.md` rows.

### M9-S4 — The M9 gate, the program's last crossing (role:MLOps)
`make verify-m9` + `make verify-m9-redteam`. **Ninth and final inheritance of
M1's rule: no skip flag, no fast mode, and it RE-RUNS NOTHING** — it reads the
demo's accept record and the committed page, the watchdog's headroom + drill
records and the live rules, S3's closure evidence (round-trip test present and
green in the suite; the skipif form absent — DERIVED, never enumerated), and
the program's standing invariants (`@champion` 2 / `feature_set v2`, versions
`['1','2']` with none created after `m7-closed`, `uv.lock` byte-identical to
`m7-closed`, settled DVC pins up to date, `verify-m5/-m6/-m7/-m8` runnable as
separate live targets — the inherited-precondition treatment, not nested).
**Its live-question count is pinned by its own test** (the M8 precedent): one
request through the demo's own request path, one rules read, one store
question — and no more. The PO-observed demo box is checked as a NAMED OPEN
ITEM (the gate asserts the AWAITING_PO entry exists and is honest), never
silently green. The red team plants one number chosen from a record, expects
RED with multiple independent witnesses while unrelated legs stay green,
sha256 restore, GREEN.
**Accept when:** GREEN with every sub-check enumerable; red team PASSED; the
gate's own test file pins the live count and the no-re-run property.
**Evidence plan:** transcript pasted into `docs/verify_m9_transcripts.md`;
CLAUDE.md command rows; the boundary inherits a runnable gate.

## Out of scope (named now so creep is visible later)
- **Ray Tune on KubeRay, CI nightly smoke on kind, trivy + secret-scan,
  README portfolio polish** — PO opt-in per BLUEPRINT §9/M9, routed to
  **AWAITING_PO 2026-08-23-2** (menu with costs). If the PO opts in, the
  item(s) get chartered as M9-S5+ by an ARCH touch — not improvised by an
  executor mid-chain.
- **Publishing the repo publicly** — the PO's queued §12 question; surfaces
  again at the program close.
- **R-1** (FeatureService) — declined at this boundary with reason (§0).
- Any alias move, any fit, any registry version, any cluster rebuild, any new
  Flyte trigger, any change to the champion's wire.
- The transformer cutover (champion's wire stays the wire of record) — a
  PO/boundary decision if ever, not a story's.

## Risks & walls (carried counts restated; fallbacks cite ADRs/laws)
| Risk / wall | Count | Fallback |
|---|---|---|
| Host-header/CORS wrinkle eats the demo session | 3 attempts per approach | Same-origin serving through the existing ingress dissolves CORS by construction; if a dedicated Ingress rule fights the controller, F-039's precondition check (refuse ownerReferences; require `noServer`/backend registration) diagnoses in seconds. Record the losing attempt, switch approach. |
| Redis instrumentation (no native /metrics) | 3 attempts | Option (ii) (push + freshness) reuses machinery that exists (pushgateway + PVC + absence family); if (i)'s exporter image misbehaves, (ii) is the recorded fallback, not a compromise — say so in the record. |
| S2's drill stales/empties a store the transformer reads | — | The champion's own wire never touches the store (committed tables) — rider path of record unaffected; transformer 503s by DESIGN (the drill's prediction says so); re-materialize is 7 s, recorded. Prediction-first, undo staged before injection (M6-S5's rule). |
| Demo accept needs a human | — | Not a wall: the PO-observed box parks in AWAITING_PO by design. The technical boxes close unattended. |
| A long drill outlives the session | — | `automation/run_detached.sh <name> --then-schedule executor -- <command…>` (gotcha #45); S2's drill is minutes, but if any leg waits on sustained `for:` windows, detach it rather than sitting. |
| F-058's shape recurs through a new cadence | — | Legislated: no M9 Flyte trigger. A cadence is a push from a command a human or the gate runs. |

## Open PO questions (options · recommendation · default-with-date)
1. **The stretch opt-in menu** — AWAITING_PO 2026-08-23-2 (Ray/KubeRay · CI
   nightly · trivy+secret-scan · README polish, each costed). Recommendation
   there: README polish + trivy/secret-scan are cheap and portfolio-aligned;
   Ray is a real platform story (KubeRay operator + images) priced honestly.
   Default: none proceed without opt-in; the milestone completes on S1–S4.
2. **The observed demo run** — raised by M9-S1's exit entry; the PO completes
   one query unassisted, observed. No default: it waits.
3. **Publish the repo publicly** — queued (§12); surfaces at program close.

## ARCH self-check (v3.0)
model stated Fable: **yes** · every story sized for one short executor
session: **yes** (S1 page+route decision; S2 headroom+rule+drill; S3 two
mechanical closures; S4 the gate — each with a safe stop) · debt intake
diffed against ledgers/debt.md: **yes — register closed, none due** · forks
routed to AWAITING_PO: **yes** (2026-08-23-2 opt-in menu; observed-demo box;
F-016 standing; nothing blocks the chain).
