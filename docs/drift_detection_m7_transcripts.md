# M7-S3 transcripts — pasted, not remembered

Companion to `docs/drift_detection_m7.md`. Every number in that document comes
from one of these.

---

## §1 The Evidently probe, run BEFORE anything was designed around the library

The M7 kickoff's risk table names this as the milestone's headline risk (gotcha
#36's shape: a resolver quietly downgrading the numeric cores, or the add
refusing outright). It was answered in an **isolated venv pinning this
project's four numeric cores exactly**, so the answer cost the real project
nothing either way (`automation/runs/m7s3-evprobe/`).

```
$ uv add --project automation/runs/m7s3-evprobe "evidently"
   … + statsmodels==0.14.6  + litestar==2.24.0  + nltk==3.10.3  … (40 packages)

$ uv run --project automation/runs/m7s3-evprobe python .../probe.py
{
  "pandas": "3.0.5",
  "numpy": "2.5.2",
  "evidently": "0.7.21",
  "import": "ok",
  "compute": "ok",
  "metric_count": 3
}
```

Resolves, imports, **and computes a real drift report on a pandas-3 frame**. The
recorded fallback (hand-rolled PSI/KS over scipy, a DIFFER from the blueprint's
named tool) is **not** taken, and the dependency-quarantine option (gotcha #16)
is not needed.

### §1.1 The real add, with gotcha #36's check pasted

```
$ uv add "evidently>=0.7.21,<0.8"
Resolved 243 packages in 3.91s
Prepared 1 package · Uninstalled 1 package · Installed 27 packages
 + evidently==0.7.21  + statsmodels==0.14.6  + litestar==2.24.0  + nltk==3.10.3
 + plotly==5.24.1  + uvloop==0.22.1  + watchfiles==1.2.0  + websockets==17.0.1  …
 ~ taxi-mlops==0.0.1 (from file:///home/longt/NYC-taxi-production-with-k8-flavor)

$ uv pip list | grep -E "^(pandas|numpy|scipy|scikit-learn|lightgbm|xgboost|mlflow-skinny|evidently) "
evidently                          0.7.21
lightgbm                           4.7.0
mlflow-skinny                      3.15.1
numpy                              2.5.2
pandas                             3.0.5
scikit-learn                       1.9.0
scipy                              1.18.0
xgboost                            3.4.1
```

**27 installed, 1 uninstalled (the project itself, rebuilt), no core moved.**
The one uninstall is the shape M4-S2's `flyte` add had and is not a downgrade.

---

## §2 `make backup` — the standing precedent, run before the new tenant landed

```
[backup] 6 database(s) on the server: flyte marts metabase mlflow optuna postgres
[backup] ok  flyte    ->  91.9KiB in   0s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  marts    ->   1.2GiB in 213s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  metabase -> 360.1KiB in   1s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  mlflow   ->  67.9KiB in   0s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  optuna   ->  27.0KiB in   0s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  postgres ->  392.0B  in   0s, gzip CRC clean, ends with pg_dump's completion marker
total on disk: 1.6GiB
[backup] done — /home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-20T04-07-22Z
```

---

## §3 The headroom leg — 2019 ONLY, and it ran before the bars were written

`make drift-headroom`. This is the measurement M7 law 4 requires to exist before
any threshold does.

```
[headroom] the two 2019 months the champion was JUDGED on, against the months it was
[headroom] FITTED on. Both have a verdict already: PROMOTE.

[drift] 2019-07  vs train-2019 (2019-01+…+2019-06, 43,987,422 rows)
[drift]   rows 6,189,748 · 199,669 trips/day against the reference's 243,024 · volume ratio 0.8216
[drift]   input  hour                   PSI   0.0006  unseen  0.000%  bins ref  24 / cur  24
[drift]   input  dayofweek              PSI   0.0323  unseen  0.000%  bins ref   7 / cur   7
[drift]          largest move: bin '1' 12.513% -> 15.789% (+3.275 pts)
[drift]   input  PULocationID           PSI   0.0091  unseen  0.000%  bins ref 263 / cur 261
[drift]   input  DOLocationID           PSI   0.0085  unseen  0.000%  bins ref 263 / cur 262
[drift]   input  passenger_count        PSI   0.0010  unseen  0.000%  bins ref  11 / cur  11
[drift]   TARGET trip_duration_minutes  PSI   0.0011  unseen  0.000%  bins ref  13 / cur  12

[drift] 2019-08  vs train-2019 (…)
[drift]   rows 5,950,708 · 191,958 trips/day · volume ratio 0.7899
[drift]   input  hour                   PSI   0.0009
[drift]   input  dayofweek              PSI   0.0077
[drift]   input  PULocationID           PSI   0.0137
[drift]   input  DOLocationID           PSI   0.0126
[drift]   input  passenger_count        PSI   0.0013
[drift]   TARGET trip_duration_minutes  PSI   0.0008

[headroom] recorded automation/runs/m7-drift/headroom.json
[headroom] highest INPUT-column PSI across both held-out months: 0.0323.
```

**0.0323 is `dayofweek` in July, i.e. five Mondays — calendar arithmetic.** The
largest behavioural number is `PULocationID` at 0.0137. Both are read into
`docs/slo_serving.md` §8.2 and the bar 0.10 is argued from them.

---

## §4 `make alert-rules` — 12 rules, 10 signals, no documented absence left

```
[alert-rules] ok  12 rule(s) validated in infra/monitoring/alerting_rules.yml
[alert-rules]     A-1  PredictorLatencySLOBurning             for=5m   severity=warning
[alert-rules]     A-2  ServingEdge5xxRateHigh                 for=5m   severity=critical
[alert-rules]     A-3  PredictorRequestRejectionRateHigh      for=2m   severity=warning
[alert-rules]     A-5  PredictorNoAvailableReplica            for=2m   severity=critical
[alert-rules]     A-5  PredictorRestartFlapping               for=0m   severity=warning
[alert-rules]     A-6  PredictorCpuThrottledSustained         for=10m  severity=warning
[alert-rules]     A-7  PredictorStorageInitializerNotReady    for=3m   severity=critical
[alert-rules]     A-8  ModelInputDrift                        for=5m   severity=warning
[alert-rules]     A-9  ScoringVolumeCollapse                  for=5m   severity=warning
[alert-rules]     A-10 DriftMetricsStale                      for=0m   severity=warning
[alert-rules]     A-3  QuoteHorizonRefusals                   for=1m   severity=warning
[alert-rules]     A-4  ServedVersionNotChampion               for=2m   severity=critical
```

`IMPLEMENTED_SIGNALS` holds all ten ids; `DOCUMENTED_ABSENCES` is empty.
`validate()` fails in **both** directions, so F-035's closure could not have
been claimed in prose without these rules existing.

---

## §5 The pushgateway landed, and the first address was wrong

The scrape target is the only thing that said so. Worth pasting because the
DOWN target is the *good* outcome of this mistake:

```
$ (before)  /api/v1/targets  ->  {'job': 'pushgateway'} down
            http://prometheus-pushgateway.monitoring.svc.cluster.local:9091/metrics

$ kubectl -n monitoring get svc | grep pushgateway
service/prometheus-prometheus-pushgateway   ClusterIP   10.96.139.142   <none>   9091/TCP

$ (after)   /api/v1/targets  ->  {'job': 'pushgateway'} up
            http://prometheus-prometheus-pushgateway.monitoring.svc.cluster.local:9091/metrics
```

The subchart's fullname template prefixes the helm RELEASE name (`prometheus`)
to its own chart name (`prometheus-pushgateway`). Had the gateway ALSO been
annotated for the chart's generic `kubernetes-service-endpoints` job, it would
have been scraped anyway — with its labels mangled, because that job does not
set `honor_labels` — and every drift rule would have sat quietly inactive
instead of one target reading `down`. Gotcha #70's family: ask the server what
its name is.

`make deploy-monitoring` accept check after the change: **GREEN 10/10**, all
11 board panel queries returning live series.

---

## §6 `make drift-drill` — the prediction, then the alerts

Prediction written first (`automation/runs/m7-drift/prediction.json`, committed
in `d113f26`, before any 2020 drift record exists in the repository).

```
[drift-drill] PREDICTION written FIRST -> automation/runs/m7-drift/prediction.json
[drift-drill]     PREDICT A-9 ScoringVolumeCollapse FIRES for 2020-03
[drift-drill]     PREDICT A-9 ScoringVolumeCollapse (2020-01) stays INACTIVE
[drift-drill]     PREDICT A-9 ScoringVolumeCollapse (2020-02) stays INACTIVE
[drift-drill]     PREDICT A-10 DriftMetricsStale stays INACTIVE
[drift-drill]     PREDICT A-4 ServedVersionNotChampion stays INACTIVE
[drift-drill]     PREDICT A-3 QuoteHorizonRefusals stays INACTIVE
[drift-drill]     PREDICT A-1 PredictorLatencySLOBurning stays INACTIVE
[drift-drill]     PREDICT A-2 ServingEdge5xxRateHigh stays INACTIVE
[drift-drill]     PREDICT A-5 PredictorNoAvailableReplica stays INACTIVE
[drift-drill]     PREDICT A-6 PredictorCpuThrottledSustained stays INACTIVE
[drift-drill]     PREDICT A-8 ModelInputDrift for 2020-03: DOES NOT FIRE at monthly grain
                          (confidence: low — this is the prediction most likely to be wrong)
[drift-drill] @champion before: 2
[drift-drill] reset: the gateway's drift groups are cleared; waiting for the rules to settle …
[drift-drill]     the board is clean
[drift-drill] ok  all 5 drift/client rules loaded, health ok
[drift-drill] ok  2020-01: 6,279,806 rows · volume ratio 0.8336 · max input PSI 0.0103 · 16 series pushed
[drift-drill] ok  2020-02: 6,185,309 rows · volume ratio 0.8776 · max input PSI 0.0087 · 16 series pushed
[drift-drill] ok  2020-03: 2,948,237 rows · volume ratio 0.3913 · max input PSI 0.0217 · 16 series pushed
[drift-drill] ok  Prometheus scraped the gateway: 3 month series visible
[drift-drill]     as Prometheus reads them: {'2020-01': 0.8335556483513884,
                                             '2020-02': 0.8776340568603828,
                                             '2020-03': 0.3913368667803675}
```

The verdict lines are in `automation/runs/m7-drift/drift_fire_drill.json`
(tracked). A-9 went `pending` and then `firing` one 5-minute sustain later, for
month **2020-03 only**; A-8 never fired; `@champion` read 2 before and after.

### §6.1 The judge was wrong before the system was — and it is a familiar shape

The drill's first run reported:

```
[drift-drill] ok  A-9 ScoringVolumeCollapse FIRED at T+341.5s — as predicted
…
[drift-drill] FAIL A-9 ScoringVolumeCollapse fired and was predicted INACTIVE
[drift-drill] FAIL A-9 ScoringVolumeCollapse fired and was predicted INACTIVE
[drift-drill] RED — 2 failure(s).
```

Both statements are about the same rule and both are correct readings of a
prediction the judge could not express: **A-9 is predicted to fire for 2020-03
AND to stay quiet for 2020-01 and 2020-02** — three statements about one rule
name — and `fired_at` was keyed on the name alone. Gotcha #67's family: a
checker whose unit of judgement is coarser than the fact it is judging.

The repair reads the per-series `alerts` array, which is also **strictly the
stronger claim**: a bar so low that an ordinary January trips it would pass a
name-level check and fails this one. **The PREDICTION object was not touched** —
the fix is in the judge, and `test_the_committed_prediction_still_equals_the_code`
would have gone red if it had been.

---

## §7 The second witness

`make drift-witness`. Evidently 0.7.21, 200,000 seeded rows per side.

```
[witness] 2020-03  (evidently 0.7.21, 200,000 sampled rows/side, seed 20200301)
[witness]   column                      our PSI    evidently   their verdict
[witness]   dayofweek                    0.0217       0.0512     not drifted
[witness]   passenger_count              0.0171       0.0324     not drifted
[witness]   DOLocationID                 0.0151       0.0554     not drifted
[witness]   PULocationID                 0.0143       0.0535     not drifted
[witness]   trip_duration_minutes        0.0125       0.1008         DRIFTED
[witness]   hour                         0.0098       0.0345     not drifted
[witness]   columns past OUR bar (PSI >= 0.10) : (none)
[witness]   columns past EVIDENTLY's own bar   : ['trip_duration_minutes']
[witness]   on the question the ALERT asks — did any INPUT column drift? —
            the two instruments AGREE: ours (none) vs theirs (none)
```

Same for 2020-01. **Two independent implementations, different statistics
(Wasserstein-normed for the numeric column, Jensen-Shannon for the
categoricals), one answer: no input column drifted.**

And read sceptically, which is what a second witness is for: Evidently flags the
TARGET at **0.1014 in January and 0.1008 in March** — essentially the same value
in an ordinary month and in the collapse, both barely over its 0.1 default. It
does not distinguish them either. "Evidently detected drift in March" would be
true and misleading.

### §7.1 Its first run reported total disagreement, and nothing had disagreed

```
[witness]   trip_duration_minutes        0.0127          nan     not drifted
[witness]   evidently ranking : []
[witness]   the two instruments DISAGREE on which column moved most
```

The parser looked for `metric_id` and a `status` field; Evidently's `.dict()`
has neither — it carries `metric_name`, a structured `config` (column, method,
threshold) and `value`. **A second witness that cannot be read reports maximum
disagreement**, which is simultaneously the most alarming thing it could say and
the least true. Fixed by reading the shape off a real snapshot
(`automation/runs/m7s3-evprobe/shape.py`) instead of assuming it.

---

## §8 What actually moved in 2020-03 — for M7-S5's memo, not for an alert

Every column's largest bin moves are in `drift-2020-03.json` under `top_moves`.
The aggregate PSI is flat; the *bins* are not, and this is where the domain
story lives:

```
hour              23:  4.099% -> 3.223%   (-0.877 pts)   22:  5.251% -> 4.435%  (-0.815)
dayofweek          6: 14.411% -> 10.687%  (-3.724 pts)    1: 12.513% -> 15.172% (+2.658)
PULocationID     138:  2.619% -> 1.741%   (-0.878 pts)  264:  0.970% -> 0.572%  (-0.398)
DOLocationID     264:  0.849% -> 0.368%   (-0.481 pts)  230:  3.006% -> 2.577%  (-0.429)
passenger_count    1: 69.956% -> 72.626%  (+2.670 pts)    2: 14.962% -> 13.594% (-1.368)
duration     [30,45):  5.909% -> 4.629%   (-1.281 pts)  [5,7.5): 15.376% -> 16.488% (+1.112)
```

Read as a city rather than as a table: **late-night trips fell** (hours 22 and
23 are the two largest hour moves), **Saturday fell hardest** (dow 6, −3.7
points, the single largest bin move anywhere), **LaGuardia's zone 138 lost a
third of its share** (2.619% → 1.741%), **groups shrank to singles**
(passenger_count 1 gained 2.7 points), and **long trips became short ones**
(the 30–45 minute band lost 1.28 points to the 5–7.5 minute band).

Every one of those is the pandemic, legible, in a month whose aggregate PSI is
0.0217. Which is the entire finding: **the signal was never absent, it was
averaged.**

`unseen_share` is **0.000% on every column in every month** — no category
arrived that the champion had never seen. What changed was the weights.

---

## §9 F-035's two pushers, proven

```
$ make push-serving-version A4_ARGS=--no-push
[a-4] served   : 2  ([quote] served by nyc-taxi-eta version 2 via
                     http://localhost:8081/v2/models/nyc-taxi-eta/infer)
[a-4] registry : 2  (models:/nyc-taxi-eta@champion)
[a-4] agree: the wire and the registry are both version 2
```

Two series where F-034 said there were none. The push itself and the quote
client's refusal counter are in §10.
