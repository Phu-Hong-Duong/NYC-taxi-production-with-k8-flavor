# verify-m9 transcripts — the M9 gate, and the program's last crossing

Pasted, never remembered. Two runs on the live cluster of 2026-08-24, from
story `m9-s4`: the gate GREEN, and its red team proving the gate can say no.

**The one thing to read before the numbers: §9/M9's last accept line stays OPEN
on purpose.** It asks for *one non-technical person to complete a query
unassisted, observed*. No unattended session can watch that happen, so the gate
asserts the box is recorded honestly — in `automation/runs/m9-demo/accept.json`
(`po_observed_run.status`) and at AWAITING_PO 2026-08-23-3, and the two must
agree on the URL — and prints it as an open item both in §2 and in its own GREEN
banner, where a reader who skims the verdict still sees it. It never renders it
green. This is the only place in the program where a gate passes *because*
something is unfinished, and the alternative would be the one dishonest artifact
in the repo. A unit test pins all three halves of that.

**Three live questions, not M8's five.** One quote through the demo's own
request path, one rules read at Prometheus, one DBSIZE at the online store. The
champion's own wire, the feature server's two-sided answer and the predictor
exporter's health belong to `verify-m5` and `verify-m8`, which the boundary runs
live as their own evidence. A gate that re-asks its predecessors' questions is
not stricter; it is a gate whose live footprint grows every milestone. The count
is stated in the header and pinned by `tests/unit/test_verify_m9.py`.

## §1. `make verify-m9` — GREEN, 45 `ok` sub-checks across 7 sections, 4.450 s

```
[verify-m9] the M9 gate — a page generated from three sources, an accept
            answered line by line, two rules that carry no number, and one
            box that must stay open because only a human can close it.

== 1. the demo page — generated from three sources, and nothing about it retyped ==
  ok   the pickers carry 530 <option> elements — exactly 2 x the 265 distinct LocationIDs in taxi_zone_lookup.csv, so the list is derived from the lookup and not retyped beside it (gotcha #110's count, not its content)
  ok   the page's request schema is the SERVER's own declaration — 4 raw input(s), wire name AND datatype AND source field, equal to transformer.RAW_INPUTS. A wrong name is refused loudly by `decode_raw`; a wrong datatype is not, and would quote a plausible number nobody can see is wrong
  ok   the page opens on a PUBLISHED trip — zone 132 -> 48 at 2019-07-04T09:15:00 — the row automation/runs/m8-transformer/transformer-parity.json already holds under hazard 'federal-holiday', so the demo's first screen is checkable against a measurement
  ok   and TLC's non-place zone(s) [264, 265] are RENDERED rather than hidden — they have no row in the centroid table by design, and the accept quoted 264 -> 264 at 8.2445 min from the features that remain
  ok   the page a browser receives is byte-identical to the one in git (sha256 b1edd074b00f7c0c…, 47,147 bytes) — served, fetched back through the route, and re-hashed off disk by this gate, three readings of one file
  ok   the page posts to /v2/models/nyc-taxi-eta-transformer/infer — the RAW boundary ('nyc-taxi-eta-transformer'), NOT the champion's own model name ('nyc-taxi-eta'), which the accept proved 404s on this origin. A browser cannot build a 24-column matrix and a JS feature path would be the second transform path the law forbids

== 2. §9/M9's accept — answered line by line, including the box that must stay OPEN ==
  ok   the accept record carries 9 check(s), every one ok and its failure list empty — the demo answered on the route, in the shape the page sends
  ok   the bar is EXACT, parsed out of the section that argues it, and the accept met it: |delta| = 0.000e+00 minutes. Not 'within tolerance' — the demo's answer and the recorded one are the same float64
  ok   and the number is CROSS-ARTIFACT: the demo quoted 39.00193715359812 and automation/runs/m8-transformer/transformer-parity.json holds 39.00193715359812 for the same (at, pu, do) — matched on the trip, so neither side carries the other's literal
  ok   the serving model version is stamped on the ANSWER — '2', equal to the anchor record's — mlserver's own stamp forwarded verbatim, never a metadata call that could describe another moment
  ok   X-Taxi-Lookups on the demo's own response equals the recorded string: 2 group(s) came from the feature store and 2 did NOT cross the wall (airport_constant, borough_dictionary) — F-059 as a header, so the store is proved consulted THROUGH THIS PATH
  ok   an uncovered date is REFUSED and named: HTTP 422 for 2031-07-04T09:15:00, and the message contains the year 2031 plus the command that extends the table — a wrong quote there would be a number nobody could see was wrong
  ok   §9/M9's last accept line is recorded OPEN and honestly: the record says 'OPEN', AWAITING_PO carries the invitation with the same URL (http://localhost:8081/demo/), and THIS GATE DOES NOT RENDER IT GREEN — an unattended session cannot watch a human use a page, and a demo that marked its own human-observation box green would be the one dishonest artifact in this program
              OPEN ITEM (by design, not by omission): BLUEPRINT §9/M9: one non-technical person (the PO counts) completes a query unassisted, observed
  ok   the route decision is recorded in demo/README.md §1 and its property is asserted off the manifest: the Ingress rule carries NO `host:`, so it lives in nginx's default server block beside the /healthz that block already answers — same origin as the model, so CORS never happens rather than being configured. The accept re-checked both invariants it shares that block with (/healthz 200, / 404)

== 3. law 4 — every M9 bar argued BEFORE the record it judges, checked from git ==
  ok   the demo's EXACT bar was committed 133 s BEFORE the accept record it judges entered the repo — M8 law 4's ordering, tenth inheritance, read off `git log` and not off a sentence claiming it
  ok   the HEADROOM was recorded before the section that argues from it (0 s, same commit or earlier) — the store's key composition was measured first, and it is what killed the key-count threshold the kickoff expected: the transformer's whole dependency is 8% of the count
  ok   and §9's bars were argued 1878 s before the FIRST drill record — the drill that first crosses a bar cannot be the thing that chose it
  ok   and the drill's PREDICTION was committed 700 s before its first record — written to disk before the first FLUSHDB, so a prediction cannot be amended into agreement with an outcome (M6-S5's rule, and a test pins the committed file against the drill's own literal)

== 4. the watchdog — three rules, two of them carrying no number, and no series nobody pushes ==
  ok   3 online-store rule(s) under signal id(s) A-12, A-13: OnlineStoreCanaryFailing, OnlineStoreIncomplete, OnlineStoreWatchdogAbsent — and every one carries an `annotations.why`, which `render_alert_rules.py` REFUSES a rule without: a threshold whose argument is not beside it is a number nobody can review
  ok   OnlineStoreCanaryFailing compares a claim to 0 — a PROPERTY, not a threshold: each of the four claims either held or did not, and $labels.check names which. OnlineStoreIncomplete compares taxi_online_store_keys to taxi_online_store_keys_expected, so there is NO NUMBER ON EITHER SIDE and the rule self-updates when the sources legitimately change
  ok   the only bar-shaped number in all three rules is ['1800'] (A-12's freshness clause in seconds), and it is argued in §9 of slo_serving.md — parsed out of the rules and looked for in the section, so a loosened clause is a RED gate rather than a diff nobody read
  ok   OnlineStoreWatchdogAbsent is an `absent(...)` rule with a 10m sustain — A-11's argument one board along, because `time() - stamp < N` over ZERO series is zero series and not a stale reading; and 2 rule(s) name their own blind spot in an annotation, where an on-call reads it rather than in a document they do not have open
  ok   the renderer validates the whole file (16 rules, exit 0) and its two sets agree: ['A-12', 'A-13'] are in IMPLEMENTED_SIGNALS and DOCUMENTED_ABSENCES is empty — the store watchdog cannot be quietly forgotten OR quietly claimed
  ok   all 4 series the rules SELECT are produced by taxi_mlops.monitoring.store_health (4 declared, 0 unused) — a rule selecting a series nobody pushes stays `health=ok` and `inactive` forever, which is exactly what a healthy store looks like
  ok   scripts/store_watch.py (path DERIVED from the Makefile recipe, F-017) issues NO verdict — no fractional bar-shaped constant anywhere in its comparisons, asked of the AST. The bar lives in the SELECTOR of a rule, so the pushed numbers stay re-interpretable after the fact

== 5. the live system — THREE questions: the demo's own path, the rules, the store's size ==
  ok   the DEMO's own request path answered 39.00193715359812 minutes right now — equal to the recorded 39.00193715359812 at the bar the accept was held to, |delta| = 0.000e+00. Endpoint, schema and payload all read out of the committed page, posted with no Host override
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   and the version stamped on that answer is '2' — equal to what 'champion' resolves to in the registry this second. The demo shows the SERVING version because mlserver stamps it and the transformer forwards it, not because a page was told a number
  ok   and X-Taxi-Lookups still reports every group INCLUDING the two that did not cross the wall — identical to the recorded string, so the store was consulted through THIS path and F-059's committed groups stayed committed
  ok   PROMETHEUS has all 3 online-store rule(s) LOADED with health=ok and every `for:` equal to the file's (OnlineStoreCanaryFailing=inactive, OnlineStoreIncomplete=inactive, OnlineStoreWatchdogAbsent=inactive) — read off the server, never off the values that were submitted
  ok   the expected key count RECONCILES with its own parts: 263 + 4,383 + 46,938 + 6,104 = 57,688 across 4 view(s) — Feast writes one key per distinct entity key per view, so this side of A-12b's comparison is derived from the sources and not chosen
  ok   and the ONLINE STORE holds 57,688 keys right now — THREE WITNESSES agree (the sources' derivation, the materialization record, the live server). An empty store answers every lookup with null and nothing is red anywhere, because null is ALSO the correct answer for TLC's two non-places — which is why the gate asks

== 6. the drill that was predicted first, and the two findings M9-S3 closed — derived, never enumerated ==
  ok   the store-watch drill: 28 check(s) across 3 phase(s), 0 failure(s) — empty 19/19, health 5/5, unreachable 4/4
  ok   and every phase record's embedded prediction is FIELD-EQUAL to the committed prediction.json — written first (§3) AND unedited since, which are two different facts
  ok   2 rule(s) FIRED and reached Alertmanager (OnlineStoreCanaryFailing at T+162.2s, OnlineStoreIncomplete at T+162.2s) while all 5 must-not-fire negatives held inactive — the negatives are the load-bearing half, and one of them (the absence rule) is the whole reason the other rule exists
  ok   the rider's request against an EMPTY store came back HTTP 422 — the status the prediction named, and the kickoff's superseded 503 is KEPT beside it rather than quietly replaced. The store was refilled to 57,688 keys and the board ends carrying the truth, not a silence
  ok   and all 4 number(s) docs/store_watchdog_m9.md quotes about the store and the drill are the records' own (162.2 s, 4,646, 57,688, 9.9 s) — the write-up is the only witness a human reads, so a rewritten record has to contradict it too
  ok   F-057: all 66 pins carry PEP 503-normalised names and the body is sorted AS LINES — the property the regenerator now reproduces byte-for-byte against a file under review since M8-S2. The closure's evidence is that there was NOTHING to commit, which is why this leg asserts the file and not a diff
  ok   F-054: ZERO `skipif(not RECORD.exists())` decorators remain under tests/ — asked of the AST across 64 test file(s), never enumerated. 18 file(s) read a tracked record and 17 carry the `needs_records` marker, so an absent record is a loud assertion on the host and a deselection in the ONE place F-047 allows

== 7. the standing invariants — the pointer, the lock, the pins, and the finding M9 did NOT fix ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   NOT ONE of the 2 registry versions was created after the m7-closed tag — the strong form of M9 law 3, across M8 and M9 both. champion resolves to version 2
  ok   and F-032's invariant holds live: the served version eats 'v2', which is what configs/train.yaml tells every client to build — a half-finished rollback is a RED gate here rather than a 500 nobody can attribute
  ok   uv.lock is BYTE-IDENTICAL to the m7-closed tag — M8's five stories and M9's four, and the project's dependency graph has not moved since M7 closed
  ok   all 5 settled DVC pins are up to date (processed, raw, rejected, scoring, scoring_rejected) — M9 read no new month and wrote no tree (law 2)
  ok   the 9 inherited gates (verify-m0, verify-m1, verify-m2, verify-m3, verify-m4, verify-m5, verify-m6, verify-m7, verify-m8) are runnable as their OWN live targets and this gate invokes none of them — a nested gate turns one red predecessor into a red milestone and re-asks every question it owns
  ok   F-062 — a dead online store billed to the CALLER as a 4xx — is recorded OPEN with 4 costed options and a named recommendation, routed to the program close because fixing it changes what a live boundary returns and M9 law 3 keeps the wire still. The gate requires the row to be open rather than tidy
  ok   the deployments ledger carries a row for every M9 story whose records describe a cluster mutation (owes M9-S2; present: M9-S1, M9-S2) — read row by row, because the milestone's own prose names other stories

[verify-m9] GREEN — every M9 sub-check passed.
            Show: the demo      http://localhost:8081/demo/  (demo/README.md)
                  the accept    automation/runs/m9-demo/accept.json
                  the watchdog  docs/store_watchdog_m9.md · slo_serving.md §9
            OPEN BY DESIGN: §9/M9 asks for one non-technical person to complete a
            query unassisted, OBSERVED. No unattended session can close that box;
            it waits at AWAITING_PO and this gate only ever checks that it is
            recorded honestly.
```

## §2. `make verify-m9-redteam` — PASSED

**The plant.** One number in `automation/runs/m9-store-watch/headroom.json`: the
store's EXPECTED key count, shortened by exactly the size of one view — and the
view is CHOSEN from the record as the smallest, which today is `zone_static`,
the 263 rows carrying every centroid the champion's nine geometry features are
built from.

It is not a lie about a measurement. It is what a correct-looking expectation of
the wrong POPULATION reports, and it looks like nothing at all:

* it is derived from the record's own fields (total minus one view), so it is
  exactly the number a tidying edit would produce;
* **A-12b compares `keys < keys_expected` and neither side is a literal**, so
  the rule is not loosened, not renamed, and stays `health=ok` and `inactive` —
  the live alerting stack reads identically before and after;
* the drill's records, the demo, the alias, the lock and the pins are untouched,
  so 42 sub-checks have no reason to complain;
* and the store it describes could lose every centroid it holds — breaking every
  JFK quote on the wire — while still satisfying the alert that exists to notice.

**Three independent artifacts contradicted it**: the record's own per-view
arithmetic, the live `DBSIZE` beside the M8-S4 materialization record, and
`docs/store_watchdog_m9.md`. The third had to be built for this drill — the gate
gained the prose leg every predecessor since `verify-m5` carries, comparing
every number the write-up quotes about the store and the drill with the record
it came from.

**Two legs deliberately stayed GREEN**: the no-number leg (the plant loosens no
rule's argument) and law 4's ordering leg (the plant is a value, not a history).
That is what separates a gate that fails on a wrong number from a checksum.

```
[verify-m9-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m9-store-watch/headroom.json  sha256 b875049f8289…

[verify-m9-redteam] 1. shorten the EXPECTED key count by exactly one view — the arithmetic a tidying edit produces
  expected_keys.total: 57,688 -> 57,425 — short by exactly the 263 keys of 'zone_static' (0.46% of the store, and the smallest view there is). UNTOUCHED: per_view {'zone_static': 263, 'calendar_day_flags': 4383, 'od_window_stats': 46938, 'pu_hour_window_stats': 6104}, transformer_dependency_keys 4,646, the live_store block, the materialization block and three_witnesses_agree=True.
  A-12b compares keys < keys_expected with NO LITERAL on either side, so the rule is not loosened and stays inactive — but a store that lost every one of 'zone_static''s keys would now satisfy it, and 'zone_static' is where the centroids live.

[verify-m9-redteam] 2. make verify-m9 — expected RED, from the record's arithmetic, the live store AND the write-up
[verify-m9] the M9 gate — a page generated from three sources, an accept
  FAIL the headroom record's per-view counts sum to 57,688 against its own total of 57,425 — the expected side of A-12b does not reconcile, and a short expectation is a store that can lose a whole view and still pass
  FAIL the store holds 57,688 keys against 57,425 derived and 57,688 recorded — the three witnesses disagree
  FAIL the write-up quotes no record for: {'57,425': "the store's expected key count"} — either the prose drifted from the records or a record was rewritten and the document was not
[verify-m9] RED — 3 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose expected count no longer reconciles
  ok   the ARITHMETIC leg fired: the record's own per-view counts do not sum to its total, so the expected side of A-12b is not derived from the sources it claims
  ok   the LIVE leg fired: DBSIZE and the M8-S4 materialization record both still say what the store really holds, and they are not the same number any more
  ok   the PROSE leg fired: docs/store_watchdog_m9.md renders an expected count the record no longer holds — the only witness a human reads
  ok   42 sub-check line(s) still passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: <option> elements
  ok   unaffected leg still green: PUBLISHED trip
  ok   unaffected leg still green: recorded OPEN and honestly
  ok   unaffected leg still green: BEFORE the accept record
  ok   unaffected leg still green: compares a claim to 0
  ok   unaffected leg still green: series the rules SELECT are produced by
  ok   unaffected leg still green: DEMO's own request path answered
  ok   unaffected leg still green: LOADED with health=ok
  ok   unaffected leg still green: FIRED and reached Alertmanager
  ok   unaffected leg still green: NOT ONE of the
  ok   unaffected leg still green: BYTE-IDENTICAL to the m7-closed tag
  ok   the NO-NUMBER leg is STILL GREEN — the plant leaves every rule's argument intact, which is what makes this a test of the gate's reasoning rather than a checksum
  ok   and law 4's ordering leg is still green — the plant is a value, not a history, and the gate distinguishes the two

[verify-m9-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m9-store-watch/headroom.json (sha256 b875049f8289…)
  ok   automation/runs/m9-store-watch/headroom.json is byte-identical to what the drill found (sha256 b875049f8289…)
[verify-m9] GREEN — every M9 sub-check passed.
  ok   the gate is GREEN again (45 sub-check line(s), exit 0) — the drill left nothing behind
  ok   git status is clean for automation/runs/m9-store-watch/headroom.json — the restore is byte-identical to the committed record

[verify-m9-redteam] PASSED: the M9 gate went RED on ONE rewritten expected
                    key count — short by exactly the view that holds every
                    centroid, derived from the record own fields, leaving
                    A-12b unloosened and every alert inactive — and named
                    the record own arithmetic, the live store AND the
                    write-up a human reads, while the demo, the rules, the
                    drill and the pointer stayed green. GREEN on restore.
```

## §3. What this gate's own first runs cost, and what they were about

Three RED runs, and **every one was the gate's defect rather than the program's**
— the family pattern, and the third is worth a finding.

1. **`AttributeError: 'str' object has no attribute 'name'`.** The schema leg
   assumed `transformer.RAW_INPUTS` was a list of dataclasses; it is a `dict`
   mapping wire name to `(datatype, field)`. The repair made the check
   *stronger* rather than merely working: it now compares all THREE fields, so a
   correct wire name carrying the wrong source field — two individually valid
   values under each other's names, gotcha #73's shape self-inflicted — cannot
   pass.

2. **`KeyError: 'keys'`** — see §4.

3. **A guard that fired on correct behaviour.** The F-054 leg asked "does any
   test skip on a `.exists()`?" and flagged
   `test_feast_repo.py::test_rewriting_the_pins_reproduces_the_committed_file_exactly`,
   which skips on `.venv-feast/bin/python` — a **gitignored build artifact**,
   absent in CI, where skipping is correct and is the idiom this suite already
   uses for `ss`, `git`, `make` and `docker`. F-054 is about **records**: paths
   under `automation/runs`, which are TRACKED (F-029 option A), so their absence
   means deleted-or-lost and never this-clone-lacks-artifacts. The leg now
   resolves each file's record constants from their own assignments and only
   counts a skip gated on one of *those*. **Gotcha #50, and the correction is
   narrowing to the right property, not widening the bar** — a guard that fires
   when the program behaves correctly teaches the next session to edit
   assertions.

## §4. F-064 — a clause that had already shipped green

The `KeyError` above was a copy of `verify_m8.sh`'s own online-store leg, and
the reason it raised here is the reason that leg was never really checking
anything:

```python
expected = materialize["store"].get("keys")      # the record says `dbsize`
if dbsize > 0 and (expected is None or dbsize == expected):
    ok("… the count the materialization recorded, survived on its PVC")
```

`.get("keys")` returned `None`, the `expected is None` branch fired, and the
comparison the message *claims* to make was never made. The leg tested
`dbsize > 0` alone — it would have passed a store holding one key, while telling
its reader the live count equalled the recorded one. Shipped green at M8-S5 and
at every re-run since.

Fixed in the same story that found it (the key is read, and an absent field is a
FAIL rather than a licence), and `make verify-m8` re-run **GREEN** with the real
comparison — `57,688 keys right now — EQUAL to the count the materialization
recorded`. The generalisable form is #51's question asked of a *passing* check:
*could this component tell if it were false?* A branch that treats a missing
field as "no expectation was recorded" answers no, and reads exactly like a
check.

## §5. M9-S5 (epilogue) — the box changed state, so the assertion had to change shape

The PO completed the observed run on 2026-08-24. §2's box leg had been written
against the literal `OPEN`, so the honest flip of the record would have turned
the gate RED for a program behaving correctly — gotcha #50, in the check whose
entire job is to stop this one box being rounded up. It was re-derived to the
property that holds in **both** states.

**The pre-flip state, unchanged (this is still what a fresh OPEN record gets):**

```
  ok   §9/M9's last accept line is recorded OPEN and honestly: … AWAITING_PO
       carries the invitation with the same URL … and THIS GATE DOES NOT RENDER
       IT GREEN
       OPEN ITEM (by design, not by omission): BLUEPRINT §9/M9: …
```

**The post-flip state, live:**

```
  ok   §9/M9's last accept line is recorded CLOSED and CITED — closed 2026-08-24
       against AWAITING_PO 2026-08-23-3, an entry this inbox really holds, and
       the observer's note is quoted there VERBATIM rather than paraphrased
       here. The gate still renders nothing green on its own authority: a CLOSED
       status with no citation, or one the inbox does not carry, is RED
       CLOSED BY A HUMAN (AWAITING_PO 2026-08-23-3, 2026-08-24): This is okay, I
       get the gist of it. Improvement can be done later.

[verify-m9] GREEN — every M9 sub-check passed.
            CLOSED BY A HUMAN, 2026-08-24: §9/M9's last accept line — one
            non-technical person completing a query unassisted, OBSERVED — was
            closed by the PO and is cited at AWAITING_PO 2026-08-23-3, where
            their note is quoted verbatim. No gate closed it; this one checks
            the citation.
```

**45 sub-checks before and after.** The leg was re-derived, not removed, and the
banner's paragraph is now read out of the record §2 just judged rather than
typed underneath it — otherwise the last four lines a skimmer reads would keep
saying "open by design" about a box a human had closed.

### The two plants, because a flip is one keystroke and reads as housekeeping

Both derived from the record, both leaving the verdict, the URL and every other
field intact — the edit somebody makes with no bad intent at all:

```
# (1) status flipped, citation absent
  FAIL the PO-observed box is not honestly recorded: it is CLOSED and cites no
       AWAITING_PO entry; it is CLOSED and quotes no note from the observer
[verify-m9] RED — 1 sub-check(s) failed.          ← 44 sub-checks still passed

# (2) the more plausible lie: an entry id one day off, and a paraphrase
  FAIL the PO-observed box is not honestly recorded: it cites AWAITING_PO
       2026-08-23-9, an entry this inbox does not hold; the note it quotes
       appears nowhere in AWAITING_PO
[verify-m9] RED — 1 sub-check(s) failed.          ← 44 sub-checks still passed
```

Restored from a byte copy and verified by sha256 (`ceec3ca26dbea2d9…` before the
first plant and after the last), `git status --porcelain` clean, **GREEN 45/45**.

### The first run went RED on an honest record, and the repair is the lesson

The citation leg's first version asked `note in awaiting` — a raw substring.
`AWAITING_PO.md` is markdown: the PO's note lives inside a blockquote and is
wrapped at the column the file is written to, so it is **never contiguous
there**. A perfectly honest citation failed. Both sides are flattened now
(blockquote markers dropped, whitespace runs collapsed): the claim under test is
that the inbox holds these **words**, never that it holds these **bytes** — the
same distinction #76 drew for prose-vs-record checks, arriving through wrapping
instead of through rounding.

### F-067, which this story found by asking what else touches the field

`scripts/demo_accept.py` rewrites the whole record on every run and wrote
`po_observed_run` as a literal `OPEN` block. Correct for four days. The instant
the closure was recorded, that literal became a deletion: the next
`make demo-accept` — the demo's own acceptance test, which anyone is encouraged
to re-run — would have dropped the citation, the date and the PO's words, and
this gate would then have reported the box OPEN again, **correctly, about a
record that had just lost the fact**. The decision is `human_box()` now: a
CLOSED block is carried forward verbatim, everything else produces OPEN, and an
AST test asks whether the script ever *authors* a closed status — narrowly,
because searching for the word finds `startswith("CLOSED")` and `closed_on`,
which is the code recognising a closure and the opposite of writing one.
