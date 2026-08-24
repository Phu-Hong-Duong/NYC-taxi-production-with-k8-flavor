# ADR-012 — The Feast online store is an in-cluster Redis

* **Status**: ACCEPTED — 2026-08-21 (M8-S4, role MLE A / SRE R)
* **Decides**: which online store Feast writes to and reads from in this program
* **Supersedes**: nothing. **Constrains**: M8-S4 leg 2 (the transformer), M8-S5
* **Evidence**: `automation/runs/m8-online/store.json` ·
  `automation/runs/m8-online/materialize.json` ·
  `automation/runs/m8-online/online_parity.json`

## The constraint that decides it, and it is two-sided

An online store in this program has to be reachable from **both** sides of a
boundary that already exists and is not negotiable:

| Side | Who | Where it runs | Why it cannot move |
|---|---|---|---|
| **Writer** | the materializer (`feast materialize`) | the HOST, inside `.venv-feast` | Feast pins `pandas<3` against this project's 3.0.5 (M8 law 4). There is no Feast in the task image and building one would put the wall inside the cluster instead of removing it |
| **Reader** | the transformer (M8-S4 leg 2) | a POD on the kind cluster | it must run OUR image (pandas 3) beside the champion; the boundary law forbids `taxi_mlops` importing an orchestrator or a store SDK |

That table is the whole decision. It eliminates the default before anything else
is considered:

* **Feast's default sqlite file** (`online_store.db`) satisfies **neither** side
  across the boundary. A file on the host is invisible to a kind node; a file in
  a pod is invisible to the host materializer. It is not a weaker option, it is
  an option that cannot be wired at all — and the way it fails is the dangerous
  one: `feast materialize` writes a local file and reports success, so the store
  is "full" and every in-cluster lookup returns null.
* **Redis, in-cluster, no hostPort** satisfies both: the pod reaches it at
  `redis.feast.svc.cluster.local:6379`, and the host writer reaches it through an
  ephemeral `kubectl port-forward` on **6380**. This is the same recorded
  deviation from the declared-route doctrine that Flyte's console (8080) and the
  pushgateway (9091) already carry — kind publishes host ports at cluster-CREATE
  only, and this cluster's PVCs are the only copy of the registry.

The address therefore cannot be a committed constant: it is
`${FEAST_REDIS_CONNECTION}`, expanded by Feast's own `os.path.expandvars` at
config load, with **no default** — an unset variable fails loudly at connect time
naming the variable, where a default would connect to something wrong. The
argument is in `infra/feast/feature_repo/feature_store.yaml`'s header.

**Attempts spent: 1 of the 3-attempt wall.** Redis worked first time; the wall is
unspent and stays armed.

## What was NOT chosen, and why

* **Postgres as the online store** (Feast supports it, and this program already
  runs exactly one Postgres — D-002 would have held a fifth time). Refused: the
  ONE Postgres holds the MLflow registry, the marts, Flyte's control-plane state,
  Metabase's app-db and Optuna's studies — every one of them irreplaceable and
  under a backup obligation. An online store is the opposite state class (see
  below), and giving a regenerable, request-path, rewritten-every-materialization
  tenant a seat inside the database whose loss would end the program trades a
  real risk for a saved deployment. The blast radius argument beats the
  "one fewer component" argument.
* **A Redis helm chart** (bitnami). Refused for the reason
  `infra/manifests/postgres.yaml` and `infra/manifests/metabase.yaml` already
  record: the chart brings a StatefulSet, a replica/sentinel story and a values
  surface we would spend the story overriding into one container, one volume, one
  ClusterIP. Fifty readable lines beat a chart we argue with.
* **Feast's feature server as the reader** (so the store type would not matter to
  the pod). Not refused — DEFERRED to leg 2, where it is candidate shape (i) and
  has to be measured. It does not change this decision: a feature server needs an
  online store behind it too.

## The state class, stated honestly

**Every byte in this store is REGENERABLE.** Its entire content is a projection
of `data/feast/*.parquet`, which is itself derived read-only from the DVC-pinned
settled trees, and `make feast-materialize` rebuilds it in **7 seconds**. So:

* **Ledger row: YES** — `ledgers/deployments.md` carries it like every other
  tenant; a component nobody wrote down is a component nobody can find.
* **Backup obligation: NO** — it is a `data/predictions/`-class tenant (M2-S4's
  argument, verbatim: model/derived output, regenerable from pinned inputs, and a
  pin that must be refreshed on every rebuild is worse than no pin because it
  looks like provenance). `make backup` enumerates databases and buckets from the
  server and will not see Redis; that is correct and is written down here so
  nobody later reads the absence as an omission.
* **A volume anyway, and the two are not the same question.** Backup is about
  losing the machine; the PVC is about losing the POD, which is the normal
  behaviour of a Deployment. F-050 is the measured local reason: the pushgateway
  lost its whole surface twice in fourteen hours on this machine, to host
  restarts, and an empty store that nobody notices is worse than a missing one
  that pages. RDB snapshots onto a 1Gi PVC cost nothing.
* **`maxmemory-policy noeviction`, and it is a correctness setting.** An evicting
  store drops the key the next request asks for, the lookup returns null, the
  transformer builds a NaN feature and the model quotes a confident wrong number
  with nothing red anywhere. With `noeviction` a write past the 512mb cap FAILS
  the materialization instead. Measured working set: **57,688 keys / 14.32 MiB**,
  read off the server after materializing, so the margin is a number.

## The residual, recorded rather than netted out — CLOSED 2026-08-23 (M9-S2)

**There is no alert on an empty or stale online store.** Nothing reads it on the
request path yet — leg 2 is what puts a reader in front of it — so the signal
belongs to the story that creates the exposure, and inventing a threshold here
would be setting a bar before the thing it watches exists (M8 law 4's family).
What exists today instead: `make feast-materialize` REFUSES to report success
against a store that is empty afterwards, which catches the failure at the moment
it is created rather than at the moment a rider meets it.

> **CLOSED 2026-08-23 (M9-S2), and the paragraph above is left standing because
> its reasoning is why the signal waited.** The exposure now exists (M8-S4 leg 3's
> transformer, M9-S1's demo page), so the signal landed with it: **A-12**
> (`OnlineStoreCanaryFailing` + `OnlineStoreIncomplete`, SLO-S1) and **A-13**
> (`OnlineStoreWatchdogAbsent`, SLO-S2), argued in `docs/slo_serving.md` §9 and
> watched firing end to end in `docs/store_watchdog_m9.md`. Two things this ADR
> predicted are now measured rather than argued: the store's **57,688 keys** turn
> out to be exactly the sum of distinct entity keys across the published sources,
> which is what let A-12b compare the store against its own sources and hold **no
> threshold at all**; and the failure mode this ADR names — *the transformer
> builds a NaN feature and the model quotes a confident wrong number with nothing
> red anywhere* — was measured and does **not** happen, for a reason worth
> knowing: the geometry half cannot refuse (an all-null centroid table is exactly
> what zones 264/265 legitimately produce) but the CALENDAR half does, so an
> emptied store comes back **HTTP 422** rather than a wrong number. The thing
> standing between an empty store and a confident wrong quote is F-019's guarantee,
> carried onto the store's wire two stories earlier for a different reason.

## Consequences

* `make deploy-feast-store` installs it; `TEARDOWN=1` removes it **and its PVC**,
  which is safe precisely because of the state class above.
* `make destroy` takes it with everything else. Recovery is two commands and is
  printed by the teardown itself.
* The port family is unchanged: Redis gets no hostPort and is not a required
  port. The host-side 6380 is deliberately **off 6379** so a materialization can
  never write into a developer's own local Redis if the forward were to die.
