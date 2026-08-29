# The stakeholder demo page — what it is, how it is routed, and what its accept may claim

**M9-S1.** The one non-optional M9 item (PO direction 2026-08-12, BLUEPRINT
§9/M9). One self-contained HTML page: two zone pickers, a date-time picker, a
party size, submit → a live ETA with the serving model version on it.

**Open it at <http://localhost:8081/demo/>** once the cluster is up. Nothing else
to run, no port-forward to hold open, no file to double-click.

---

## 0. What it talks to, and why it is not the champion's own endpoint

The page POSTs to **`nyc-taxi-eta-transformer`**, not to `nyc-taxi-eta`.

The champion's endpoint eats a **24-column feature matrix**. A browser cannot
build one: `taxi_mlops.features` is Python, it reads zone centroids and a federal
holiday table, and re-implementing it in JavaScript would give this program a
**second feature path** — precisely what the one-transform-path law forbids and
what every parity measurement since M5-S3 exists to make impossible. M8-S4 leg 3
built the raw boundary for exactly this shape of caller: send the four things a
dispatcher knows (a time, two zone ids, a party size) and the twenty-four
features are derived **inside the pod**, by the same code that trained the model,
with centroids and calendar flags read from the online feature store.

**This is not a cutover.** The champion's own wire remains the wire of record —
same InferenceService, same 24-column contract, same clients. The demo consumes
the boundary that exists *beside* it. Nothing in this story moves `@champion`,
mints a version, fits anything, or changes what serves.

## 1. The route decision: a host-less Ingress rule, and CORS never happened

**The wrinkle.** Every route in this cluster is host-based
(`nyc-taxi-eta-transformer-serving.local`, `grafana.local`) because that is how
KServe and the monitoring charts generate them. A browser cannot set a `Host`
header on `fetch()`. So the page as written could not have reached the model at
all without a decision.

**The decision: the demo's Ingress rule carries no `host:` field.**
ingress-nginx places a host-less rule in nginx's **default server block**, so
both paths answer under whatever host the browser happens to send —
`localhost:8081`, `127.0.0.1:8081`, the WSL IP — and the page and the model are
served from **one origin**.

**CORS therefore does not exist here, and that is a dissolution rather than a
configuration.** There is no cross-origin request to permit: the page is at
`http://localhost:8081/demo/` and it fetches `/v2/models/nyc-taxi-eta/infer` as
a *relative* URL. No `enable-cors` annotation was added, no preflight is issued,
no allow-list has to be maintained as the demo's origin changes — because it has
none. The kickoff offered this as an option; it is taken, and it is the reason
the "CORS wrinkle" section of this document is three sentences long.

### 1.1 The option that was measured and refused: `host: localhost`

`host: localhost` also works for a browser, and it would have **broken
`scripts/deploy_serving.sh`'s accept check** — which asserts
`GET localhost:8081/healthz -> 200`.

`location /healthz` lives **only in nginx's default server block**. Creating a
`server_name "localhost"` block would move the browser's (and that check's) Host
into a named block that does not carry it. Measured with two commands, before
anything was applied:

```
curl -H 'Host: totally-unrouted.invalid' localhost:8081/healthz   ->  200
curl -H 'Host: nyc-taxi-eta-serving.local' localhost:8081/healthz ->  404
```

The first is the default server answering (an unrouted host falls through to it);
the second is a named block that has no such location. A demo that turned M5's
serving accept red would have been a self-inflicted gotcha #50 — a guard going
red because the program did something correct — and the repair would have been to
edit an M5-era assertion, which is how guards become formalities. The host-less
rule is not a shortcut around the problem; it is the option under which **every
existing invariant stays standing**, and `deploy_demo.sh` asserts the two that
share the default server (`/healthz` 200, `/` 404) on every run.

### 1.2 What the rule claims — two paths, no rewrite, no wildcards

| path | pathType | backend | why exactly this |
|---|---|---|---|
| `/demo` | Prefix | `taxi-demo-page:80` | The page. Mounted at `/www/demo` inside the pod so busybox's `httpd` resolves `/demo/` natively — **no `rewrite-target` anywhere in this story**, which this repo has learned to treat as a moving part (ADR-011's spike measured `rewrite-target` changing a canary share by 0 points). |
| `/v2/models/nyc-taxi-eta-transformer/infer` | Exact | `nyc-taxi-eta-transformer-transformer:80` | The V2 model name is in the URL path (ADR-011 condition 2), and this boundary answers to **its own isvc name**. `Exact` and not `Prefix`: the demo claims **one** API path, not the `/v2` tree. |

**The first deploy of this route claimed the CHAMPION's name** —
`/v2/models/nyc-taxi-eta/infer` — and every quote came back **404**, with the
transformer's own error naming the path it does answer to. ADR-011 condition 2
for the third time in this program, and the cheap part was the error message: a
service that had silently answered to both names would have made "which boundary
produced this number?" unanswerable, which is the question every measurement in
M8-S4 rests on. The champion's name is now **deliberately unrouted on this
origin**, and the accept asserts that 404 — its absence is what proves a number
the page shows came through the raw boundary rather than off the 24-column wire.
The path is derived from `scripts/transformer_accept.py`'s own `ISVC` constant
in `tests/unit/test_demo_page.py`, so a rename breaks one place loudly instead of
two places quietly.

`/` is deliberately **not** claimed, so `GET localhost:8081/` keeps answering 404
("route up, nothing behind it") — the sentence `deploy_serving.sh` asserts.

**F-039 is honoured by construction and then checked anyway.** `taxi-demo-page`
and `taxi-demo-route` are names KServe never generates (it generates `<isvc>`,
`<isvc>-predictor`, `<isvc>-transformer`), and `deploy_demo.sh` refuses to write
to any of its four objects if it finds `ownerReferences` on them. A hand-authored
object that takes a generated name is accepted, works for seconds, and is then
reverted with no error anywhere — which cost M6-S4 a six-minute run.

## 2. Where the page's contents come from — three derivations, zero retyping

`demo/index.html` is **generated** (`make demo-page`) and committed. Its template
is `demo/index.template.html`, and three things are substituted:

| substituted | source | what drift would look like |
|---|---|---|
| the 265 zone options | `data/reference/taxi_zone_lookup.csv` — the same file `taxi_mlops.features.zones` reads | a picker offering a zone the model has never heard of, or hiding one it has |
| the request schema | `taxi_mlops.serving.transformer.RAW_INPUTS` — the dict the **server** decodes with | a wrong field *name* is refused loudly by `decode_raw`; a wrong *datatype* is not, and would quote a plausible number nobody could see was wrong |
| the default trip | `scripts/build_demo_page.py: DEFAULT_TRIP` | the opening quote would stop being checkable against a published record |

`tests/unit/test_demo_page.py` regenerates the page and requires the result to be
**byte-identical to the committed file**, so neither source can move without a
red test. The kickoff's honesty requirement was "derived, or pinned by a test
that diffs it"; this is both.

**TLC's two non-places are rendered, not hidden.** Zones **264** ("Unknown") and
**265** ("Outside of NYC") are bookkeeping, not locations: they carry no centroid
by DR-04 condition 1, they are ~1% of every split, and `264 -> 264` is the
largest single OD "route" in the data. They sit in their own picker group,
labelled *"TLC bookkeeping — not places (no geometry)"*. Quoting one exercises
the no-geometry fallback — the path **F-030** was found on — and returns a real
number built from the features that remain. A picker that hid them would make the
demo tidier than the world it quotes for.

## 3. The three error classes the page renders differently, and why that is not cosmetic

| HTTP | what the page says | why it must not be collapsed into the others |
|---|---|---|
| **422** | *"Refused — this trip cannot be quoted"*, with the service's own text | The typed boundary said no rather than guessing. A 2031 date hits it: the committed federal-holiday table runs to 2030 (F-019), and the store has no calendar row. **The horizon is a feature to demo, not to hide** — degrading to a quote would return a wrong number nobody can see is wrong. |
| **503** | *"The quote service is temporarily unavailable… nothing is wrong with your request"* | A dependency outage. The caller did nothing and has nothing to fix. Collapsing it into 422 would make an outage look like a malformed request in every panel that splits 4xx from 5xx — the transformer refuses in these two classes *precisely* so they stay distinguishable. |
| anything else | *"Unexpected answer (HTTP n)"* | An answer the page does not know how to read is reported as such rather than rendered as a blank result. Gotcha #78's rule at the UI: an empty panel and a quiet system must not look the same. |

## 4. THE BAR THE ACCEPT IS HELD TO, ARGUED BEFORE THE MEASUREMENT

*(This section is committed before `automation/runs/m9-demo/accept.json` exists —
M8 law 4's ordering, ninth inheritance, checkable from `git log --diff-filter=A`
rather than asserted here.)*

**The bar is EXACT: the demo's answer for the page's own default trip must equal
the number already recorded for that row, to every bit a float64 holds.**

The recorded row is `automation/runs/m8-transformer/transformer-parity.json`'s
`federal-holiday` hazard — JFK (132) → Clinton East (48) at
`2019-07-04T09:15:00`, one passenger — measured at **39.00193715359812** minutes,
`model_version` **2**. The accept **reads that row out of the record** and matches
it on `(at, pu, do)`; it does not carry the number as a literal.

**Why exact is the honest bar rather than a hedge.** The demo's request reaches
*the same transformer pod*, which builds the features with *the same code*, from
*the same store*, and forwards *the same champion's* answer verbatim. The only
difference between this path and the recorded one is **which nginx `location`
block matched** — a host-less rule in the default server instead of a named
server block — and an nginx location does not touch the request body. There is
no dtype round trip, no re-serialisation, no arithmetic anywhere on the new
segment. A tolerance here would be a hedge against a hazard that does not exist,
and it would hide the one failure this check is for: **a page that reached
something other than the champion through the transformer.**

If it ever comes back non-zero, that is a **finding to investigate** — which
segment introduced a difference — and not a bar to widen. This is the same
argument M8-S4 leg 3 made for its own 16-hazard bar, re-made for this path rather
than inherited from it, because a sentence about an in-cluster JSON hop is not an
argument about an ingress route.

**The other four accept claims and their bars:**
- the page a browser receives is **byte-identical** (sha256) to `demo/index.html`
  in git — fetched back through the route, not asserted from the ConfigMap;
- `X-Taxi-Lookups` on the demo's own response must equal the recorded
  `lookup_sources` string — so the store is proved consulted **through this
  path**, and F-059's two committed groups are proved *not* to have crossed;
- a 2031 quote returns **422** and its text names the date;
- a **negative, and it is conditional on the positive** (gotcha #105/#106): the
  **champion's own model name** must 404 on this origin, proving the number came
  through the raw boundary and not off the 24-column wire. It is only asserted
  *after* a real quote has succeeded — a 404 because nothing is routed and a 404
  because a path is unclaimed are the same bytes, which is how F-060 passed for
  the wrong reason.

## 5. What this story could not close, and where it is parked

BLUEPRINT §9/M9's last accept box is **"one non-technical person (the PO counts)
completes a query unassisted, observed."** An unattended session cannot close it
and must not pretend to. It is raised as an **AWAITING_PO** entry with the exact
URL and the one command to run first, and it stays **open and named** in the story
record. `make verify-m9` is chartered to assert that the entry exists and is
honest — never to render the box silently green.

## 6. Commands

| intent | command |
|---|---|
| regenerate the page from its sources | `make demo-page` |
| check the committed page still matches its sources (no write) | `make demo-page-check` |
| deploy it (page + route); `DRY_RUN=1` / `TEARDOWN=1` | `make deploy-demo` |
| the accept check — real requests through the page's own request path | `make demo-accept` |
| open it | <http://localhost:8081/demo/> |

## 7. The analytics companion page (post-close, PO-directed)

**<http://localhost:8081/demo/analytics.html>** — the program's story told from its
own records: the M3 bake-off, the 91-day March-2020 collapse (daily volume, MAE
and signed bias with a shared crosshair and a play scrub), the F-045
silent-PSI/loud-volume pair, the hour-of-day shift, and the M5 kill drill.

Three properties keep it inside this demo's discipline:

- **Static by design, provenance in the file.** Every number was exported once
  from the analyst layer and the tracked records — the HTML's own header comment
  names each source. The page computes nothing and calls nothing: quoting is
  `index.html`'s job, and this page only links back to it.
- **Same ConfigMap, same route, no new object.** It rides `/demo`'s existing
  Prefix rule as a second key in `taxi-demo-page` — no new port, no new Ingress,
  no new image. The pod-roll annotation covers BOTH pages (a pod rolled only on
  `index.html`'s sha would serve a stale analytics page until kubelet's refresh
  window), and the deploy fetches the page back through the route and requires a
  sha256 match with git.
- **Not generated, and deliberately outside `make demo-page`'s byte-identity
  contract** — that contract binds `index.html` to the zone lookup and the
  server's schema, neither of which this page consumes. Its numbers are a dated
  snapshot of closed-program records, which do not move; if they ever do, the
  page is re-exported by hand and the diff IS the review.

### 7.1 The link is TWO-WAY from 2026-08-29, and the accept pins moved with it

PR #77 shipped the back-link only (`analytics.html` → `./`), and ARCH declined
the forward half at triage because `index.html` is bound into M9's CLOSED accept
record by sha256, so adding one line to the page forces that record to be
rewritten. The PO read that cost and asked for the link anyway (AWAITING_PO
**2026-08-29-1**), and it landed as story **PP-S1**.

What moved, stated because a closed milestone's record was rewritten on purpose
and that must never look like the mistake F-063 named:

- `demo/index.template.html` gained one relative anchor (`analytics.html`) and
  one CSS rule; `demo/index.html` was **regenerated** by `make demo-page`, never
  hand-edited. `TOKEN_COUNTS` did not move — the link is static markup, not a
  placeholder token.
- `automation/runs/m9-demo/accept.json` was rewritten by `make demo-accept`
  **with** the write (the `--no-write` habit suspended for exactly one run, by
  charter). Three fields are functions of the page's bytes and all three moved:
  `page.bytes` 47,147 → 47,461 and both `page.committed_sha256` /
  `page.served_sha256` `b1edd074…` → **`f5f0bde9…`**.
- A fourth field moved and is **not** this story's doing: the recorded 2031
  refusal text gained M9-S7's F-062 sentence (*"The store IS answering — it
  served the sentinel…"*). Every accept since M9-S7 ran `--no-write`, so the
  record had been carrying pre-F-062 wording; this write is it catching up to
  the code that has been shipped since `8b6d5c0`.
- `po_observed_run` is **untouched** — still `CLOSED — observed 2026-08-24,
  cited at AWAITING_PO 2026-08-23-3` with the PO's note verbatim. That is
  `human_box()` doing its one job (F-067): it carries a CLOSED block forward and
  can never author one.

The pair is asserted, not assumed: `test_the_two_pages_link_to_each_other_and_
both_hrefs_are_relative` requires the forward link in the TEMPLATE *and* in the
generated page (a template edit never regenerated, and a hand-edit of the output,
fail differently), the back-link in `analytics.html`, and every `href` on the
generated page relative. Both sides were also fetched through the route —
`GET /demo/` and `GET /demo/analytics.html`, 200 each, each body carrying its
link — because "two-way" is a property of the pair as served, not of the diff.
