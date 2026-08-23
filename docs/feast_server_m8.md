# The wall has a door — the Feast feature server, and the bar its answers are held to

**M8-S4 leg 2 (first slice). Status: the feature server is on the cluster and its
answers are measured. The TRANSFORMER is not built — see §6 for exactly where the
cut is and what leg 3 inherits.**

## 1. The shape, decided by measurement rather than by preference

The M8 kickoff names three shapes for getting stored features onto the request
path, in order, against an unspent 3-attempt wall:

> (i) Feast's feature server as its own quarantined pod, HTTP from the
> transformer → (ii) a thin direct read of the online store (no feast import), a
> recorded DIFFER naming the serialization risk → (iii) if the wall wins after 3
> attempts: the transformer builds from the image's committed lookups with Feast
> OFF the request path — a recorded DIFFER.

**Shape (i) landed, first attempt, and 1 of the 3 is spent.** It was PROBED
before anything was built: `make feast-serve-probe` starts `feast serve` on the
host inside the existing quarantine, against the real in-cluster Redis through
the 6380 forward `make feast-materialize` already uses, and asks it one
`/get-online-features`. Thirty seconds, against a build-and-load. It answered
zone 132 (JFK) at its real centroid and zone 264 with `null`. That is the M4-S4
`DRILL_STAGE=ingest` idiom, and it is the reason the first real defect this
slice hit was a missing execute bit rather than a question about Feast.

**Why (i) rather than (ii), beyond the kickoff's ordering.** (i) is the only
shape under which the wall stays a wall. The transformer runs OUR image — pandas
3.0.5, the project graph, `src/taxi_mlops` — and feast 0.66.0 pins `pandas<3`
(M8 law 4, measured at the milestone draft and re-measured by the S2 probe). In
(i) the two worlds never share an interpreter, a process or a lockfile; they
share a JSON document over a ClusterIP Service. `src/taxi_mlops` gains no
dependency, which is why **`uv.lock` is byte-identical at this slice's exit**
exactly as it was at every other M8 story's.

(ii) would have put the burden somewhere much worse. A "thin direct read" has to
reproduce, in our image, three things Feast owns: the entity-key serialization
(pinned at version 3 in `feature_store.yaml` precisely so it cannot move under
us), the field naming, and the protobuf value encoding. Leg 1's red team already
showed a non-Feast client CAN address this store — but it did so with Feast's own
`serialize_entity_key`, INSIDE the quarantine. Re-implementing that on the
pandas-3 side would mean this program owned a private copy of a vendor's internal
encoding, and the failure mode of getting it subtly wrong is a lookup that
returns *somebody else's* row: a confident wrong number with nothing red
anywhere. That is not a risk worth taking to avoid a 203 MB pod.

**This is not a weakening of ADR-012.** ADR-012 recorded that "there is no Feast
image and building one would move the wall into the cluster" — about the
MATERIALIZER, which writes the store from the host. That stays true: nothing in
this image materializes, and `make feast-materialize` is unchanged.

## 2. What the image contains, and the two things it deliberately does not

Built `--no-deps` from `infra/feast/requirements-feast.txt` — **the same pin
file `scripts/feast_quarantine.sh` uses**, so there is one pin file and no twin.
A resolver consulted at build time can legally answer differently from the one
that was reviewed, and an image is the worst place to discover that.

- **No registry.** `data/registry.db` is generated and gitignored on the host,
  because `definitions.py` in git is the source of truth and a registry checked
  in beside it would be the second home F-013 keeps deleting. The same argument
  forbids baking one into an image, so the entrypoint runs `feast apply` at every
  start: the pod's registry is a function of the image's git content, not of
  whatever the host happened to have applied the day the image was built. A
  definitions change that was never applied therefore cannot serve stale features
  here — there is no persisted registry to be stale.
- **No store address.** `${FEAST_REDIS_CONNECTION}` is expanded from the
  environment with **no default** (ADR-012's rule, F-048's rule): an unset
  variable fails loudly naming itself, where a default would connect to something
  wrong. The entrypoint refuses before `feast apply` if it is empty.

The container **mirrors the host's directory depth** rather than editing
`definitions.py`, which resolves its own sources with
`Path(__file__).resolve().parents[3]`. Flattening the repo into `/repo` would
make that walk off the top of the filesystem, and "fixing" it by editing the file
would give the program two definitions of where the offline sources live.

## 3. THE BAR, ARGUED BEFORE THE COMPARISON RAN

*(This section and `scripts/feast_server_parity.py` are committed BEFORE any
comparison record exists — M8 law 4's ordering, checkable from git rather than
asserted here. M8-S3 and leg 1 each re-argued their bar for their own path; this
one is a third path and gets a third argument, because inheriting a sentence
written about a different seam is a hedge, not an argument.)*

**The bar is EXACT — zero difference, on every column, on every row.**

The path a value takes to reach an HTTP caller is: parquet `float64` →
(materialize, which SELECTS rather than aggregates) → protobuf `double`, a
fixed-width IEEE-754 carrier → Redis bytes → protobuf `double` → **JSON**.

Only the last hop is new against leg 1, and it is the only one that could
plausibly round. It does not, for a reason about the grammar and not about our
data: JSON's number production is arbitrary-precision decimal, and every JSON
encoder in this stack emits a float with Python's shortest-round-trip `repr`,
which is by construction the shortest decimal string that parses back to the
same 64 bits. Nothing on the server's side of the wall performs arithmetic — the
feature server's whole job is to remember a value and pick the right row.

The other columns have no numeric path at all: `is_airport`, `is_holiday`,
`is_near_holiday` and `is_business_day` are booleans, and JSON carries `true` and
`false` exactly.

So a float bar would be a hedge against a hazard that does not exist on this
path. **A nonzero result is a finding to investigate — which encoder truncated —
never a bar to widen.**

**And the load-bearing count is not the delta, it is `one missing`.** `NaN != NaN`,
so a comparison that counted both-missing as agreement while ignoring
one-missing would print a perfect `0.000e+00` and be blind to the ~1% of rows
that carry no geometry — the class F-030 was found on, and the class this store
answers `null` for by design. One side missing where the other has a value is a
MISMATCH, counted and named.

## 4. What is compared, and against what

The rows are the **16 declared parity hazards** — `taxi_mlops.serving.parity.HAZARDS`,
imported and never retyped, so the wire seam (`make parity`), the store seam
(leg 1), the offline seam (M8-S3) and this HTTP seam are all measured against one
row set. Their distinct pickup zones, dropoff zones and pickup dates are what the
feature server is asked for.

The anchor is **the champion's own lookup**: `taxi_mlops.features.zones` and
`taxi_mlops.features.calendar`, the functions `quote_time.build_features` calls
when it builds the matrix the champion eats. That is what stops this being two
Feast reads agreeing with each other — the same objection leg 1's static anchor
answers, one hop further out.

## 4b. The result

```
[server-parity] 16 declared hazards -> 23 distinct zones, 15 distinct pickup dates
[server-parity] bar: EXACT (docs/feast_server_m8.md §3, argued before this ran)

[server-parity] ok  the store declines EXACTLY the zones our path has no geometry for: [264, 265]

[server-parity] ok  zone_static:centroid_lat            compared= 21  mismatched=0  one_missing=0  max|d|=0.000e+00
[server-parity] ok  zone_static:centroid_lon            compared= 21  mismatched=0  one_missing=0  max|d|=0.000e+00
[server-parity] ok  zone_static:is_airport              compared= 21  mismatched=0  one_missing=0  max|d|=0.000e+00
[server-parity] ok  calendar_day_flags:is_holiday       compared= 15  mismatched=0  one_missing=0  max|d|=0.000e+00
[server-parity] ok  calendar_day_flags:is_near_holiday  compared= 15  mismatched=0  one_missing=0  max|d|=0.000e+00
[server-parity] ok  calendar_day_flags:is_business_day  compared= 15  mismatched=0  one_missing=0  max|d|=0.000e+00

[server-parity] max |ours - server| = 0.000e+00 across 6 columns and 108 comparisons, bar EXACT
[server-parity] one missing = 0 (the load-bearing count)
[server-parity] GREEN — the feature server's answers ARE the champion's own lookup.
```

**The door is lossless.** The projection leg 1 measured through Redis survives
the HTTP hop unchanged, and `one missing` is zero — the two sides agree about
which values do not exist, not merely about the ones that do.

### The first run went RED, and what it was actually saying

It reported `is_airport` mismatched on 2 of 23 zones — `ours=False,
store='missing'` for 264 and 265 — while every numeric column sat at
`0.000e+00`. Nothing had rounded and nothing was broken. The comparison was
holding a **total** function against a **partial** one:

- `zone_static` has a row for the 263 real zones and none at all for TLC's two
  non-places, so *every* column of 264/265 comes back `null`;
- `zones.load_zone_table()` matches that for the centroids — NaN, the same fact
  in the same vocabulary — but `zones.airport_flags` is a lookup into a constant
  array built from three integers in code, so it answers a definite `False` for a
  zone the store has never heard of.

The repair is the shape M8-S3 and leg 1 already established, inherited rather
than reinvented: **partition the entities, assert the partition two-sidedly, then
compare columns only where both sides claim an answer.** The assertion is the
strong half and it runs in both directions — a store declining a REAL zone would
be a missing feature, and a store answering for a non-place would be inventing a
location. Observed: `declines EXACTLY [264, 265]`.

What was *not* done is widen the bar. The bar is the same EXACT it was argued at
in §3; what changed is that the reader now compares like with like.

## 5. The finding this slice produced: an encoding is not a per-entity feature

**`zone_static` stores `borough` as a STRING, and the champion eats a borough
CODE — and the code cannot be reconstructed from the store.**

`zones.load_zone_table()` assigns borough codes by first-appearance order while
iterating `taxi_zone_lookup.csv`, and `borough_pair` multiplies by
`len(table.boroughs)`. So a zone's code is not a property of that zone: it is a
property of the whole table's iteration order. A transformer that fetched
`borough` for the two zones in a request and numbered what came back would
produce codes that agree with training only by accident — a silent, total
category re-map, with every value individually correct.

The generalisable form: **a feature store stores per-entity VALUES; an encoding
whose meaning depends on the whole table is not a per-entity value.** Storing the
CODE instead would embed a training artifact in the store and make the store a
second home for the dictionary. Storing the STRING, as this repo does, is right —
and it means the *dictionary* must travel with the model, not with the store.

The consequence for leg 3, stated now so it is a design input rather than a
discovery: the transformer sources from Feast exactly the stored columns that are
per-entity values with no cross-row encoding — the centroid coordinates and the
calendar flags — and takes the borough dictionary from the committed table that
defines it. That is not a shortcut; it is where the boundary actually falls.

**`is_airport` belongs on the same list, for a different reason** (§4b found it):
the feature path does not read it from a table at all. It is three integers in
code, total over every id, and the store's copy is a projection of it. For the
263 zones that exist the projection is exact — measured above — so the store can
CORROBORATE it, which is worth having, but it cannot be the source: sourcing a
total function from a partial store turns "not an airport" into "no answer" for
precisely the ~1% of rows that already carry no geometry.

So the rule the two findings share, and it is the one worth carrying out of this
slice: **a feature store is a good home for a per-entity measurement and a bad
home for anything a program computes** — an encoding, a constant, a total
function. All three look identical in a schema.

## 6. Where the cut is

**Landed and verified:** the shape decision with its probe · the image (203 MB,
`--no-deps` from the one pin file) on all three nodes by each node's own
`crictl` · the Deployment and Service, with an accept check that is an ANSWER
asked from a DIFFERENT pod (Service DNS under test) and that asserts the null
half too · this bar, argued before the comparison · the parity of the feature
server's answers against the champion's own lookup · the borough finding.

**NOT built:** the transformer InferenceService, the hazard parity through the
transformer seam, and the p95 at M5-S4's shape. Leg 3 inherits:

- a feature server answering at `feast-server.feast.svc.cluster.local:6566`,
  stateless, rebuilt by `make feast-server-image && make deploy-feast-server`;
- **2 of the 3-attempt wall still unspent** — shape (i) worked first time;
- the `lookups` seam in `quote_time.build_features` is **NOT** written; §5 says
  precisely which columns may cross it and which may not;
- one thing worth knowing before writing the client: **Feast's response does not
  preserve the request's column order.** The accept run asked for
  `centroid_lat, centroid_lon, is_airport` and got back
  `zone_id, centroid_lat, is_airport, centroid_lon`. Pair by name. This is
  M5-S3's positional-vs-named lesson (gotcha #73) arriving on a different wire,
  and a client that zipped by position would be individually-valid values under
  the wrong names — arm A of the parity red team, self-inflicted.

**The residual leg 1 named is still open and still belongs to the story that
puts a reader in front of the store**: there is no alert on an empty or stale
online store. This slice adds a second consumer of that store and does not close
it.
