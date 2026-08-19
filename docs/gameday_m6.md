# Gameday 1 — what we predicted, what happened, and the one we got wrong

M6-S5 · 2026-08-19 · role:SRE (Accountable), MLOps (R)
Evidence: `automation/runs/m6-gameday/*.json` (predictions written before any
injection) · `automation/runs/m6-restore/restore_drill.json`
Commands: `make gameday` · `make restore-drill`

---

## 0. What this exercise is graded on, and why the bar is strange

§9/M6's accept bar is **"at least one prediction wrong and investigated"**, with
the reason written into the kickoff: *a gameday with all predictions right was
too easy*. That is not a licence to engineer a surprise. It is a bar on the
DIFFICULTY of the predictions: a drill that predicts only "something will break"
is satisfied by almost any behaviour and teaches nothing, so the predictions here
are quantitative, name specific alerts by id, and include what must **not** fire.

Every prediction in this document was written to
`automation/runs/m6-gameday/predictions.json` by
`make gameday GAMEDAY_ARGS="--scenario predict"` **before the first injection**,
and the file is committed. Two of them deliberately contradict the M6 kickoff's
own expectation (§1.2 below) — which is the honest way to make one of us wrong in
public rather than after the fact.

## 1. The positive control, and why it comes first

Three of the four scenarios make a claim of the form *alert X did NOT fire*. That
sentence is worth nothing from an instrument nobody has just watched work: a
Prometheus that lost its rules, an Alertmanager whose route broke, a scrape
config that silently stopped discovering the predictor would each produce a
flawless run of silent alerts. So scenario 0 fires two real alerts end to end
first. It is the prior-art ADOPT, and it is the reason the kill scenario's
"nothing fired" below is evidence rather than an absence of evidence.

<!-- SCENARIO-0 -->

## 2. Scenario 1 — kill the predictor under load

<!-- SCENARIO-1 -->

## 3. Scenario 2 — break the storage credential, then delete the pod

<!-- SCENARIO-2 -->

## 4. Scenario 3 — saturate the CPU

<!-- SCENARIO-3 -->

## 5. The restore rehearsal — the label moves one notch, not to green

Every backup artifact this program has written since M4-S2 carried the same
sentence: **RESTORE IS NOT REHEARSED.** The dumps were proven COMPLETE (a gzip
CRC over every byte plus pg_dump's own completion marker, both legs red-teamed
against a deliberately truncated copy of the real 1.2 GiB file) and the object
mirror was proven by count AND bytes — but "these files restore a working
platform" stayed a hypothesis, and a hypothesis in a lifeboat is the worst place
to keep one.

`make restore-drill` (`scripts/restore_rehearsal.py`) is that hypothesis tested
as far as a stateful cluster allows. **GREEN 17/17**, record
`automation/runs/m6-restore/restore_drill.json`, backup
`2026-08-19T05-59-36Z`.

| what | result |
|---|---|
| `mlflow` → `mlflow_restore_drill` | restored in **2.34 s**, `ON_ERROR_STOP=1`, exit 0 |
| `optuna` → `optuna_restore_drill` | restored in **0.78 s** |
| `metabase` → `metabase_restore_drill` | restored in **7.29 s** |
| counted tables vs the LIVE database | mlflow `experiments=8 runs=101 registered_models=1 model_versions=2` · optuna `studies=5 trials=59` · metabase `report_card=67 report_dashboard=4 core_user=2` — every one equal |
| the restored registry's alias | `champion\|2`, identical to live |
| the restored studies vs `automation/runs/m3s4/sniper-*.json` | `m3-sniper-v1: 9` · `m3-sniper-v2: 21` — the trial counts M3-S4 recorded |
| the restored boards vs `analytics/metabase/boards/*.json` | all **3 dashboards / 28 cards** present BY NAME |
| objects | `flyte-data` restored **whole** — 184 objects / 783,327 bytes into a scratch bucket in 31.7 s, count AND bytes equal to the mirror on disk |
| one MLflow artifact | restored and **byte-identical to the live object by sha256** (`1/models/m-c6ba7243…/artifacts/MLmodel`) |
| the live platform | database list unchanged, bucket list unchanged, **no scratch survives** |

**What this claims.** The three small, irreplaceable dumps load into a running
Postgres and produce databases whose contents match both the live platform and
records committed in this repository, and the object mirror uploads back
byte-identically.

**What it refuses to claim, and this is the point.** Nothing was restored OVER
anything. Every database was created fresh under a `_restore_drill` suffix and
dropped; every object went into a scratch bucket that was deleted. **A full
restore over a dead platform is still un-rehearsed** and needs a PO-sanctioned
rebuild to try. So every artifact that read *NOT REHEARSED* now reads
*scratch-rehearsed 2026-08-19; full restore over a dead platform still not* —
one notch, and no further. A drill that overstated itself would be worse than
the sentence it replaced.

**Why `marts` is not in it.** 1.2 GiB of the 1.6 GiB backup, and the ONE database
already provably rebuildable from DVC pins plus `make marts` (M1-S5's
fresh-volume proof, which republished 56,127,878 rows onto a brand-new volume and
matched M1-S4's counts to the row). Restoring it into a scratch database would
cost the peak M4-S5 measured — 2.075× the database size — to re-prove a path
another proof already covers.

**The transport is the one `make marts` already uses**, and for the same reason:
`zcat` on the host piped into `kubectl exec -i psql` inside the pod. Nothing of
ours publishes 5432, and a restore procedure that first needs a port opened is a
procedure nobody can run during an incident.

### 5.1 The check that was wrong, kept because it found something real

The drill's first run went **RED on one check of seventeen**, and the restore was
not what was wrong. The check compared the restored Metabase app-db against
`analytics/metabase/boards/*.json` by COUNT and expected 3 dashboards / 28 cards.
It found **4 / 67**.

The extra content is Metabase's own: an `E-commerce Insights` dashboard and its
example questions, created by Metabase's setup from the bundled Sample Database
(`creator_id 13371338`, its internal user). Nothing was broken, and nothing had
drifted — **`scripts/metabase_boards.py` converges by name and never deletes**,
which M1-S5 stated as a deliberate asymmetry, so the app-db is a SUPERSET of the
repo's boards by design.

The check is now a subset check by NAME: every dashboard and every card this
repository commits must survive the restore, and what else the app-db holds is
recorded rather than judged. Worth keeping because of what it corrects in the
prose elsewhere: *"the boards are checked-in JSON"* is a claim about **our**
boards. It was never a claim that the app-db mirrors the repository, and a check
written as though it were would have gone red on a correct backup of a correct
platform every time it ran.

<!-- ACCEPT -->
