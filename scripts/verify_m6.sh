#!/usr/bin/env bash
# verify_m6.sh — the M6 gate, executable. BLUEPRINT §9/M6, quoted:
#
#   "M6 — Reliability: SLOs, shadow -> canary -> rollback, gameday (SRE A).
#    v1's M5 + an SLO document (latency p95, availability, error rate — targets
#    chosen and owned by SRE, numbers argued not copied) + shadow before canary
#    … only then canary 10% -> 100% + Gameday 1, predecessor-style: positive
#    control fired first, then staged failures … each with a distinguishable
#    signature predicted BEFORE injection and checked after.
#    Accept when: the shadow comparison table exists with a quantified
#    disagreement rate before the first traffic shift; v1's M5 gate (canary
#    90/10 observed, rollback <2min under load, alert fired in red-team); AND
#    the gameday record shows predicted-vs-observed signatures with at least one
#    prediction wrong and investigated (a gameday with all predictions right was
#    too easy). Show: the shadow disagreement table + Grafana during canary +
#    gameday record."
#
# The design rules are M2-S5's, M3-S5's, M4-S5's and M5-S5's, inherited whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50). This gate types no
#     champion version, no pod name, no alert threshold and no measured number.
#     Thresholds are READ from `infra/monitoring/alerting_rules.yml` and matched
#     against `docs/slo_serving.md`; the served version is compared to what the
#     ALIAS resolves to; every quoted prose number is compared to the record it
#     claims to quote.
#   * no skip flag, no fast mode. M1's rule, inherited a SIXTH time.
#
# RE-RUNS NOTHING EXPENSIVE AND MINTS NOTHING IT COUNTS. It does not run the
# gameday (~55 minutes and a deliberate ~5 minute outage), does not fire an
# alert, does not shift traffic, does not move the alias, does not restore a
# database, does not deploy. It reads: the tracked records M6-S1…S5 wrote, the
# live cluster, the live Prometheus, the live registry, the committed docs — and
# it asks the endpoint for exactly ONE prediction, for the reason `verify-m5` §2
# gives (gotcha #59, and #71 for why a Ready condition is not enough).
#
# WHY THE RECORDS AND NOT A FRESH RUN. Same argument as M4-S5's cache leg and
# M5-S5's load leg (gotcha #66's regime): every M6 number is a property of one
# injected event at one moment. Re-provoking any of them here would make the
# gate the thing that decides what a canary share or an outage is, and would
# cost an outage per run. The records are tracked (F-029), so a fresh clone runs
# these legs against the same bytes and a tampered record is a diff — which is
# exactly what `verify_m6_redteam.sh` plants.
#
# ONE LIVE QUESTION NO PREDECESSOR GATE COULD ASK (F-043). The gameday found
# that the predictor's own exporter starves under saturation — scrape duration
# 4 ms -> 4.613 s with one scrape failing outright — so the latency alert
# cleared itself in the middle of the event it was firing about. §1 therefore
# asks the live Prometheus whether that exporter is healthy RIGHT NOW. It is one
# query, and it is the signal that went dark during the one event it existed for.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m6.sh          (via `make verify-m6`)
#        scripts/verify_m6_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")

# The counting harness — the two counters, the four printers, `consume` and
# `expect_verdicts` — lives in ONE place from CU-S3 on. `consume` must still be
# called as `consume < <(...)` and never through a pipe; the reason, and what
# deliberately did NOT move (this gate's legs, its verdict block), are in the
# lib's own header.
# shellcheck source=lib/verify_harness.sh
source "$REPO_ROOT/scripts/lib/verify_harness.sh"

printf '\n\033[1m[verify-m6]\033[0m the M6 gate — the eyes, the judgement, shadow before canary,\n'
printf '            the split that moved, the rollback that was finally run, and a\n'
printf '            gameday graded on being wrong. It reads and it asks; it re-runs nothing.\n'

# ------------------------------------------------------------- 1. the eyes ----
section "1. the eyes — the stack is live, it answers, and the exporter is healthy RIGHT NOW"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

ROUTE = "http://localhost:8081"

def http_get(host, path, timeout=20):
    req = urllib.request.Request(ROUTE + path, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)

def kubectl(*args):
    return subprocess.run(["kubectl", "--context", "kind-mlops-taxi", *args],
                          capture_output=True, text=True).stdout.strip()

try:
    # The hosts are DERIVED from the deploy script's own values — a gate that
    # typed `prometheus.local` would keep passing after somebody renamed the
    # route and left the board unreachable.
    values = Path("infra/helm/monitoring/prometheus-values.yaml").read_text()
    gvalues = Path("infra/helm/monitoring/grafana-values.yaml").read_text()
    import re
    prom_host = re.search(r"-\s*(prometheus\.[a-z.]+)\s*$", values, re.M)
    graf_host = re.search(r"-\s*(grafana\.[a-z.]+)\s*$", gvalues, re.M)
    prom_host = prom_host.group(1) if prom_host else "prometheus.local"
    graf_host = graf_host.group(1) if graf_host else "grafana.local"

    status, _ = http_get(prom_host, "/-/healthy")
    if status == 200:
        ok(f"Prometheus answers through the EXISTING 8081 route as Host: {prom_host} "
           f"(/-/healthy -> 200) — M6 law 1, no new hostPort was ever needed")
    else:
        no(f"Prometheus did not answer on the 8081 route as {prom_host}: HTTP {status}")

    status, _ = http_get(graf_host, "/api/health")
    if status == 200:
        ok(f"Grafana answers on the same route as Host: {graf_host} (/api/health -> 200) — "
           f"'Show: Grafana during canary' has somewhere to be shown")
    else:
        no(f"Grafana did not answer on the 8081 route as {graf_host}: HTTP {status}")

    # The workloads themselves. Alertmanager is a StatefulSet and the rest are
    # Deployments; both are asked for READY replicas, so 'installed' cannot pass
    # for 'running'.
    for kind, name in (("deploy", "prometheus-server"),
                       ("deploy", "grafana"),
                       ("deploy", "prometheus-kube-state-metrics"),
                       ("statefulset", "prometheus-alertmanager")):
        ready = kubectl("-n", "monitoring", "get", kind, name,
                        "-o", "jsonpath={.status.readyReplicas}")
        if (ready or "0").isdigit() and int(ready or 0) >= 1:
            ok(f"monitoring/{name} ({kind}): {ready} ready replica(s)")
        else:
            no(f"monitoring/{name} ({kind}) has no ready replica — "
               f"{'alerts cannot be delivered' if 'alert' in name else 'nothing is being scraped'}")

    # ONE live PromQL query, answered. A monitoring gate that never asks the
    # server a question is a gate that passes against an empty TSDB.
    def promql(expr):
        status, body = http_get(prom_host, "/api/v1/query?" + urllib.parse.urlencode({"query": expr}))
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        payload = json.loads(body)
        if payload.get("status") != "success":
            raise RuntimeError(str(payload)[:120])
        return payload["data"]["result"]

    # The job name comes from the scrape config this repo ships, not from memory.
    job = re.search(r"job_name:\s*['\"]?(kserve-predictors)['\"]?", values)
    job = job.group(1) if job else "kserve-predictors"
    series = promql(f'up{{job="{job}"}}')
    if series:
        ok(f"Prometheus answered a live query: up{{job=\"{job}\"}} returns {len(series)} series "
           f"— the predictor job is DISCOVERED, which is a stronger statement than 'the target is up'")
    else:
        no(f"up{{job=\"{job}\"}} returns NO series — the predictor was never discovered, and an "
           f"undiscovered component is not even a target (gotcha #78)")

    # F-043's live question, and the one no predecessor gate could ask. The
    # champion's own exporter must be up AND answering quickly. Scoped to the
    # champion's InferenceService by name read off the manifest, never by
    # position: `prom_scalar`-style "take the first result" is exactly how the
    # gameday's storage record picked up the SHADOW's series.
    manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    isvc = re.search(r"^\s+name:\s*(\S+)", manifest, re.M).group(1)
    sel = f'{{job="{job}",inferenceservice="{isvc}"}}'
    up = promql(f"up{sel}")
    dur = promql(f"scrape_duration_seconds{sel}")
    if up and all(float(s["value"][1]) == 1.0 for s in up):
        ok(f"the CHAMPION's exporter is up right now (up{sel} == 1 on {len(up)} series) — "
           f"scoped to {isvc!r}, never 'the first result'")
    else:
        no(f"up{sel} is not 1: {[s['value'][1] for s in up] or 'no series'} — the predictor's "
           f"own metrics are missing, which is the F-043 condition")
    if dur:
        worst = max(float(s["value"][1]) for s in dur)
        # The bar is the scrape INTERVAL, derived from the values file: a scrape
        # that takes longer than the interval cannot keep up, which is the shape
        # F-043 measured (4.613 s against a 15 s interval was already a warning;
        # the failure came with the timeout). No number is typed here.
        interval = re.search(r"scrape_interval:\s*(\d+)s", values)
        interval = int(interval.group(1)) if interval else 15
        if worst < interval:
            ok(f"its scrape completes in {worst:.4f} s against the configured {interval} s "
               f"interval — the exporter is not starving (F-043's live question)")
        else:
            no(f"scrape_duration_seconds is {worst:.3f} s against a {interval} s interval — the "
               f"exporter cannot keep up, which is F-043 happening now")
    else:
        no(f"scrape_duration_seconds{sel} returns no series — the scrape is not being timed")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the eyes check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the eyes check"

# ------------------------------------------------------- 2. the judgement -----
section "2. the judgement — every rule LOADED, every threshold argued in the SLO document"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

ROUTE = "http://localhost:8081"

def http_get(host, path, timeout=20):
    req = urllib.request.Request(ROUTE + path, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")

try:
    rules_path = Path("infra/monitoring/alerting_rules.yml")
    doc = yaml.safe_load(rules_path.read_text())
    on_disk = [r for g in doc["groups"] for r in g["rules"]]

    # (a) every rule in the file is LOADED in the live server, healthy. The file
    # is the claim; /api/v1/rules is the observation. A rules file that fails to
    # parse leaves the previous rules running and the deploy still succeeds.
    status, body = http_get("prometheus.local", "/api/v1/rules")
    live = []
    if status == 200:
        for g in json.loads(body)["data"]["groups"]:
            live.extend(g["rules"])
    live_by_name = {r["name"]: r for r in live}
    missing = [r["alert"] for r in on_disk if r["alert"] not in live_by_name]
    unhealthy = sorted(n for n, r in live_by_name.items() if r.get("health") != "ok")
    if on_disk and not missing and not unhealthy:
        ok(f"all {len(on_disk)} rule(s) in {rules_path} are LOADED and health=ok in the live "
           f"Prometheus — the checked-in file is what is judging the service")
    else:
        no(f"rules on disk but not loaded: {missing}; loaded but unhealthy: {unhealthy}")

    # (b) the SUSTAIN window travels too, and it is the half the gameday proved
    # load-bearing: F-041 found that what stops a self-heal paging is the `for:`,
    # not the threshold. Compared as seconds on both sides, both derived.
    def secs(text):
        m = re.fullmatch(r"(\d+)([smh])", str(text))
        return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)] if m else None
    drift = {r["alert"]: (r.get("for"), live_by_name[r["alert"]].get("duration"))
             for r in on_disk if r["alert"] in live_by_name
             and secs(r.get("for", "0m")) != live_by_name[r["alert"]].get("duration")}
    if not drift:
        shown = ", ".join(f"{r['alert']}={r.get('for')}" for r in on_disk)
        ok(f"every rule's `for:` sustain matches the loaded one ({shown}) — F-041 made this the "
           f"load-bearing half: what stops a self-heal paging is the sustain, not the threshold")
    else:
        no(f"the sustain windows disagree between the file and the server: {drift}")

    # (c) EVERY THRESHOLD IN A RULE MUST BE ARGUED IN THE SLO DOCUMENT. Both
    # sides derived: the numbers are parsed out of the rules' own expressions and
    # looked for in docs/slo_serving.md. This is what stops a threshold being
    # loosened in a diff nobody reads — the document is the review surface.
    slo = Path("docs/slo_serving.md").read_text()

    def quoted(value: str) -> bool:
        forms = {value}
        try:
            f = float(value)
            forms |= {f"{f:g}", f"{f:.0%}".rstrip("%"), f"{f * 100:g}"}
        except ValueError:
            pass
        return any(re.search(rf"(?<![\d.]){re.escape(v)}(?![\d.]?\d)", slo) for v in forms)

    unargued = {}
    for r in on_disk:
        # The comparison's right-hand side is the threshold; that is the number a
        # human is being asked to trust.
        nums = re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", r["expr"])
        absent = [n for n in nums if not quoted(n)]
        if absent:
            unargued[r["alert"]] = absent
    if on_disk and not unargued:
        ok(f"every threshold in every rule appears in docs/slo_serving.md — {sum(len(re.findall(r'[<>]=?\s*([0-9]*\.?[0-9]+)', r['expr'])) for r in on_disk)} "
           f"number(s) parsed out of the expressions and found in the document that owns them")
    else:
        no(f"threshold(s) with no argument in docs/slo_serving.md: {unargued}")

    # (d) a threshold whose reason is not written beside it is a number nobody
    # can review. `render_alert_rules.py` refuses one; the gate asserts the
    # property independently, because a checker and its subject can drift.
    bare = [r["alert"] for r in on_disk
            if not r.get("annotations", {}).get("why") or not r.get("labels", {}).get("signal")]
    if not bare:
        ok(f"every rule carries a `signal` label and an `annotations.why` — the argument travels "
           f"with the number ({len(on_disk)} rules)")
    else:
        no(f"rule(s) with no signal id or no `why`: {bare}")

    # (e) the implemented signal set and the DOCUMENTED ABSENCES must agree, and
    # neither may quietly change. F-035: two of the PRR's seven have no metric
    # source in this stack, and both the gap and its closure must be visible.
    # The sets are COMPUTED in that module (a comprehension over a range, and a
    # set difference), so they are read by IMPORTING it. `ast.literal_eval` used
    # to be enough and silently stopped being: it returned nothing, `implemented`
    # came back empty, and the leg then failed for a reason that had nothing to
    # do with the signals — gotcha #50's quieter cousin, a guard degrading into
    # a guard about its own parser.
    import importlib.util

    spec = importlib.util.spec_from_file_location("_rar", "scripts/render_alert_rules.py")
    rar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rar)
    known = set(rar.KNOWN_SIGNALS)
    implemented = set(rar.IMPLEMENTED_SIGNALS)
    in_rules = {r["labels"]["signal"] for r in on_disk if r.get("labels", {}).get("signal")}
    absent = known - implemented
    documented = {f"A-{n}" for n in re.findall(r"###\s*A-(\d)\b", slo)}
    # AN EMPTY ABSENCE LIST IS LEGAL, AND SAYING SO IS THE FIX FOR A REAL RED.
    # This leg used to require `absent` to be non-empty, which was true on the
    # day it was written and stopped being true the moment M7-S3 CLOSED F-035 by
    # giving A-3's client half and A-4 a metric source. A guard that fires
    # because the program did the right thing teaches the next session to edit
    # assertions (gotcha #50, sixth time). The property that holds at every
    # state is the AGREEMENT: the rules implement exactly what the renderer
    # declares, and whatever is still absent has a named section in the SLO doc.
    if in_rules == implemented and absent <= documented:
        closed = ("and the documented-absence list is EMPTY — every signal now has a metric "
                  "source (F-035 closed at M7-S3)" if not absent else
                  f"and the {len(absent)} absent one(s) {sorted(absent)} each have a named "
                  f"section in the SLO document")
        ok(f"the implemented signals {sorted(in_rules)} are exactly the ones with a metric source, "
           f"{closed} — the gap cannot be quietly forgotten OR quietly closed")
    else:
        no(f"signals in rules={sorted(in_rules)}, declared implemented={sorted(implemented)}, "
           f"absent={sorted(absent)}, documented absences={sorted(documented)}")

    # (f) the four SLO targets exist and each states its instrument and its load
    # shape. A percentile without its shape is not a target (M5-S4's lesson, in
    # document form).
    targets = re.findall(r"###\s*(SLO-[A-Z]\d)\s*·", slo)
    if len(targets) >= 4:
        ok(f"the SLO document declares {len(targets)} targets: {', '.join(targets)} — latency, "
           f"availability, rejections and saturation")
    else:
        no(f"the SLO document declares {len(targets)} target(s): {targets}")

    # (g) the 250 ms latency target must be a BUCKET EDGE of the histogram A-1
    # counts against, because §2.1 measured that this stack's quantiles are
    # interpolation. The check is that A-1 counts requests beyond an `le`
    # boundary rather than estimating a quantile.
    a1 = next((r for r in on_disk if r.get("labels", {}).get("signal") == "A-1"), None)
    if a1 and "histogram_quantile" not in a1["expr"] and "le=" in a1["expr"]:
        edge = re.search(r'le="([\d.]+)"', a1["expr"])
        ok(f"A-1 counts requests beyond the le=\"{edge.group(1) if edge else '?'}\" bucket edge "
           f"and never calls histogram_quantile — §2.1's finding, encoded in the rule")
    else:
        no("A-1 either estimates a quantile or does not select a bucket edge — docs/slo_serving.md "
           "§2.1 says this stack's quantiles overshoot by 32%")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the judgement check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the judgement check"

# --------------------------------------------- 3. shadow BEFORE canary --------
section "3. shadow before canary — a quantified disagreement rate, and a verdict, BEFORE the shift"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from datetime import datetime
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

def when(text):
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))

try:
    dis = json.loads(Path("automation/runs/m6-shadow/disagreement.json").read_text())
    canary = json.loads(Path("automation/runs/m6-canary/release_drill.json").read_text())
    memo = Path("docs/shadow_analysis_m6.md").read_text()

    # (a) the table is QUANTIFIED — §9/M6 asks for a rate, not for a paragraph.
    overall = dis["overall"]
    needed = ["rows", "mean_abs_delta_min", "median_abs_delta_min", "p90_abs_delta_min",
              "max_abs_delta_min", "champion_closer_pct"]
    absent = [k for k in needed if overall.get(k) is None]
    if not absent:
        ok(f"the disagreement table is quantified over {overall['rows']} rows: mean "
           f"{overall['mean_abs_delta_min']} min, median {overall['median_abs_delta_min']}, p90 "
           f"{overall['p90_abs_delta_min']}, max {overall['max_abs_delta_min']} — a distribution, "
           f"not an average")
    else:
        no(f"the disagreement record is missing {absent} — §9/M6 asks for a quantified rate")

    # (b) it is SEGMENTED, and the segments are what a memo can have an opinion
    # about. A single overall number cannot answer 'which segments diverge?'.
    segs = dis.get("by_segment", {})
    if len(segs) >= 4 and all(s.get("rows") for s in segs.values()):
        ok(f"it is segmented {len(segs)} ways ({', '.join(sorted(segs))}) — the question the "
           f"blueprint asks the DA is WHICH segments diverge")
    else:
        no(f"the record carries {len(segs)} segment(s) — too few to answer 'which segments diverge?'")

    # (c) two DIFFERENT models were compared. A shadow table between one model
    # and itself is the failure mode that looks perfect.
    served = dis.get("served_versions", {})
    if served.get("champion") and served.get("shadow") and served["champion"] != served["shadow"]:
        ok(f"the two endpoints served DIFFERENT versions (champion {served['champion']} vs shadow "
           f"{served['shadow']}) and different feature sets ({dis['champion']['feature_set']} vs "
           f"{dis['shadow']['feature_set']}) — read off the ANSWERS, not off the deploy")
    else:
        no(f"the record compared versions {served} — a disagreement table between one model and "
           f"itself measures nothing")

    # (d) THE ORDERING, which is the half of the accept-when that is about TIME:
    # "reviewed BEFORE any traffic shifts". Both records carry their own stamps.
    shifted = when(canary["load"]["measured_at"])
    measured = when(dis["generated_at"])
    if measured < shifted:
        ok(f"the shadow table was measured {measured:%Y-%m-%dT%H:%M:%SZ}, BEFORE the first traffic "
           f"shift at {shifted:%Y-%m-%dT%H:%M:%SZ} — the blueprint's ordering, checked against the "
           f"two records' own clocks rather than against the order they are written up in")
    else:
        no(f"the shadow table ({measured}) was not measured before the canary run ({shifted}) — "
           f"'shadow before canary' is an ordering, and this one is backwards")

    # (e) the DA memo exists and carries a VERDICT that is a go/no-go, because
    # §9/M6 makes it "a named input to the canary go/no-go".
    verdict = re.search(r"^##\s*Verdict:\s*\*\*(.+?)\*\*", memo, re.M)
    if verdict and re.search(r"\b(NO-GO|GO)\b", verdict.group(1)):
        ok(f"the DA memo states a verdict in its own heading: {verdict.group(1).strip()!r} — a "
           f"named input to the go/no-go, not a summary")
    else:
        no("docs/shadow_analysis_m6.md has no ## Verdict heading carrying GO or NO-GO")

    # (f) and the memo's numbers are the RECORD's numbers. A memo that quotes a
    # number no record holds is the failure this leg exists for (the M5-S5 shape).
    def written(value, digits=(1, 2, 3, 4)):
        forms = {f"{value:.{d}f}".rstrip("0").rstrip(".") for d in digits} | {f"{value:g}"}
        return any(re.search(rf"(?<![\d.]){re.escape(f)}(?![\d.]?\d)", memo) for f in forms)

    long_trip = segs.get("long_trip", {})
    quoted = {
        "the long-trip mean disagreement": long_trip.get("mean_abs_delta_min"),
        "the long-trip max": long_trip.get("max_abs_delta_min"),
        "champion closer on long trips (%)": long_trip.get("champion_closer_pct"),
        "the overall row count": float(overall["rows"]),
    }
    absent = {k: v for k, v in quoted.items() if v is None or not written(v)}
    if not absent:
        ok(f"every headline number the memo quotes is in the record it cites (long-trip mean "
           f"{quoted['the long-trip mean disagreement']} min, max {quoted['the long-trip max']}, "
           f"champion closer {quoted['champion closer on long trips (%)']}%, "
           f"{overall['rows']} rows)")
    else:
        no(f"the memo quotes number(s) no record holds: {absent}")

    # (g) and it says what it is NOT. The sample is stratified, so every overall
    # number over-weights hard rows by construction — a memo that let its MAE be
    # read as the model's is gotcha #15 in prose.
    if dis.get("what_this_is_not") and "bakeoff_m3" in memo:
        ok("the record and the memo both say what the sample is NOT — a stratified sample's MAE is "
           "not the holdout's, and docs/bakeoff_m3.md stays the measurement of record (gotcha #15)")
    else:
        no("neither the record nor the memo disclaims the stratified sample against the holdout "
           "measurement of record")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the shadow check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the shadow check"

# --------------------------------------------------- 4. canary 90/10 ----------
section "4. canary 90/10 OBSERVED — from counters, by two witnesses, at no cost to the rider"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    rec = json.loads(Path("automation/runs/m6-canary/release_drill.json").read_text())
    phases, checks = rec["phases"], rec["checks"]

    if rec.get("verdict") == "PASS" and all(checks.values()):
        ok(f"the release drill recorded {len(checks)}/{len(checks)} checks passed")
    else:
        no(f"the release drill recorded failures: {[k for k, v in checks.items() if not v]}")

    # (a) 90/10 OBSERVED — and observed from a COUNTER, never from the annotation
    # the drill itself applied. ADR-011/gotcha #81: a canary that is linked,
    # logged clean and moving zero traffic is indistinguishable from a canary at
    # 0%, and the configuration is what looks right in both cases.
    ten = phases["canary_10"]
    share = ten["ingress"]["canary_share_pct"]
    if 5.0 <= share <= 15.0 and ten["ingress"]["requests"] > 0:
        ok(f"at canary-weight 10 the INGRESS counter attributed {ten['ingress']['to_canary']:.0f} of "
           f"{ten['ingress']['requests']:.0f} requests to the canary = {share}% — 90/10 observed "
           f"from traffic, never from the annotation (gotcha #81)")
    else:
        no(f"the weight-10 window moved {share}% of {ten['ingress']['requests']:.0f} requests — not "
           f"a tenth, and a configured-but-silent canary reads exactly like this")

    # (b) THE SECOND WITNESS. Two processes counting the same requests: nginx's
    # own counter and the two predictors'. Either alone is a claim; a
    # disagreement between them is a contradiction (M4-S5's rule).
    gap = abs(ten["ingress"]["canary_share_pct"] - ten["pods"]["canary_share_pct"])
    if gap <= 5.0:
        ok(f"the two witnesses agree at weight 10: ingress {ten['ingress']['canary_share_pct']}% vs "
           f"the predictors' own counters {ten['pods']['canary_share_pct']}% ({gap:.2f} points "
           f"apart) — different processes, same event")
    else:
        no(f"the witnesses disagree by {gap:.2f} points at weight 10 — one of them is not counting "
           f"the traffic the other is")

    # (c) 100, and back. A canary story that only ever shows 10% has not shown
    # that the mechanism can carry the whole service.
    hundred, reverted = phases["canary_100"], phases["reverted"]
    if hundred["ingress"]["canary_share_pct"] >= 95.0 and reverted["ingress"]["canary_share_pct"] == 0.0:
        ok(f"weight 100 moved {hundred['ingress']['canary_share_pct']}% and the revert returned the "
           f"split to {reverted['ingress']['canary_share_pct']}% over "
           f"{reverted['ingress']['requests']:.0f} requests — 10 -> 100 -> back")
    else:
        no(f"the shift did not complete or did not revert: 100%-window "
           f"{hundred['ingress']['canary_share_pct']}%, after-revert "
           f"{reverted['ingress']['canary_share_pct']}%")

    # (d) it cost the rider NOTHING, and the champion's pod was never touched.
    load = rec["load"]
    same_pod = rec["champion"]["predictor_pod_uid_before"] == rec["champion"]["predictor_pod_uid_after"]
    if load["requests"]["errors"] == 0 and same_pod:
        ok(f"{load['requests']['ok']}/{load['requests']['sent']} requests answered with 0 errors "
           f"across both weight changes and the revert, and the champion predictor kept the same "
           f"pod uid — an Ingress edit reloads nginx and touches no pod")
    else:
        no(f"the canary run had {load['requests']['errors']} error(s) and champion-pod-unchanged="
           f"{same_pod}")

    # (e) the revert is inside the budget §9/M6 sets, and the budget is READ from
    # the record rather than typed here.
    rev = rec["revert"]
    if rev["nginx_cleared_seconds"] <= rev["budget_seconds"]:
        ok(f"the traffic revert took {rev['nginx_cleared_seconds']} s against the record's own "
           f"{rev['budget_seconds']:.0f} s budget, measured on the controller's "
           f"/configuration/backends and not on the API call")
    else:
        no(f"the revert took {rev['nginx_cleared_seconds']} s against a {rev['budget_seconds']} s "
           f"budget")

    # (f) THE HONEST COST, asserted as a property: this canary carried the
    # champion's own bytes, so the version stamp proves nothing about the split.
    # A record that quietly dropped that sentence would read like a stronger
    # result than it is.
    if len(load["served_versions"]) == 1 and any(
            "version" in k and "proves_nothing" in k for k in rec["prediction"]):
        ok(f"the record states the honest cost in its own predictions: one version "
           f"({load['served_versions'][0]}) served throughout, because the canary carried the "
           f"champion's OWN bytes — the version stamp is NOT evidence about the split")
    else:
        no("the record does not carry the 'the version stamp proves nothing here' prediction — the "
           "honest limit of a same-bytes canary is missing")

    # (g) the alias never moved during a release rehearsal, which is M6 law 3.
    if rec["champion"]["alias_version_before"] == rec["champion"]["alias_version_after"]:
        ok(f"@champion was version {rec['champion']['alias_version_before']} before AND after the "
           f"canary — a release rehearsal that moved the pointer would be a promotion")
    else:
        no(f"the alias moved during the canary: {rec['champion']['alias_version_before']} -> "
           f"{rec['champion']['alias_version_after']}")

    # (h) ADR-011 exists and its two conditions are the ones the spike measured.
    adrs = sorted(Path("docs/decisions").glob("ADR-011-*.md"))
    spike = json.loads(Path("automation/runs/m6-spike/canary_spike.json").read_text())
    if adrs and spike.get("verdict") == "PASS" and all(spike["checks"].values()):
        ok(f"ADR-011 is committed ({adrs[-1].name}) and its evidence is the spike record — PASS "
           f"{len(spike['checks'])}/{len(spike['checks'])}, including the shared-Service canary "
           f"that moved nothing")
    else:
        no(f"ADR-011 missing or its spike evidence is not green: {adrs}, {spike.get('verdict')}")

    # (i) F-039, the failure that is kept rather than deleted: the first attempt
    # is on disk beside the green one and it moved essentially nothing.
    first = Path("automation/runs/m6-canary/attempt1-ingress-name-collision/release_drill.json")
    if first.exists():
        bad = json.loads(first.read_text())
        moved = bad["phases"]["canary_10"]["ingress"]["canary_share_pct"]
        ok(f"the FAILED first attempt is kept unedited beside the green one ({moved}% moved at "
           f"weight 10) — a red run deleted is a lesson deleted")
    else:
        no("the first canary attempt's record is absent — F-039's evidence was not kept")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the canary check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the canary check"

# ------------------------------------------------- 5. rollback under load -----
section "5. rollback <2 min under load — the runbook's own three moves, run for real, both ways"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    rec = json.loads(Path("automation/runs/m6-rollback/alias_rollback.json").read_text())
    leg1, leg2, end = rec["leg_1_rollback"], rec["leg_2_roll_forward"], rec["end_state"]
    checks = rec["checks"]

    if rec.get("verdict") == "PASS" and all(checks.values()):
        ok(f"the rollback rehearsal recorded {len(checks)}/{len(checks)} checks passed, both "
           f"directions")
    else:
        no(f"the rollback rehearsal recorded failures: {[k for k, v in checks.items() if not v]}")

    # (a) §9/M6's bar: under 2 minutes, under load. The bar is BLUEPRINT's own
    # number and the only literal in this leg; it is quoted in the gate header.
    BUDGET_S = 120.0
    if leg1["seconds"]["all_three_moves"] < BUDGET_S:
        ok(f"the rollback's three moves took {leg1['seconds']['all_three_moves']} s — inside "
           f"§9/M6's 2-minute bar, and measured while an open-loop client was sending")
    else:
        no(f"the rollback took {leg1['seconds']['all_three_moves']} s against a {BUDGET_S:.0f} s bar")

    # (b) all THREE moves, in both directions. F-032's whole point: an alias-only
    # rollback loads a 5-column model under a 24-column request stream and every
    # condition still says Ready.
    def three(leg):
        s = leg["seconds"]
        return all(k in s for k in ("move_the_alias", "move_the_config_line", "make_serve"))
    if three(leg1) and three(leg2) and leg1["to_feature_set"] != leg2["to_feature_set"]:
        ok(f"both legs moved all three things — the alias ({leg1['to_version']} then "
           f"{leg2['to_version']}), configs/train.yaml's features.version ({leg1['to_feature_set']} "
           f"then {leg2['to_feature_set']}) and a re-deploy. F-032's un-rehearsed half, run")
    else:
        no("a leg is missing one of the three moves — an alias-only rollback is the F-032 shape")

    # (c) the target really answered as the version it was rolled to. A rollback
    # that ends with the OLD model still serving is the failure that looks fine.
    if "1" in leg1["route"]["versions_seen"] and leg1["route"].get("first_answer_from_version_1_at_s") is not None:
        ok(f"version {leg1['to_version']} actually answered "
           f"{leg1['route']['first_answer_from_version_1_at_s']} s in — the rollback target served "
           f"traffic, it did not merely get pointed at")
    else:
        no(f"the record shows no answer from version {leg1['to_version']} during leg 1")

    # (d) F-040/gotcha #86, asserted as a DIRECTION rather than as a number: the
    # leg that REMOVES features costs materially more than the leg that adds
    # them. A record that lost this asymmetry would make "a rollback is a 0.5 s
    # re-deploy" look supportable.
    if leg1["route"]["outage_seconds"] > leg2["route"]["outage_seconds"]:
        ok(f"the asymmetry is recorded: rolling BACK cost {leg1['route']['outage_seconds']} s of "
           f"failing requests ({leg1['route']['failed']} of {leg1['route']['sent']}, classes "
           f"{leg1['route']['classes']}) against {leg2['route']['outage_seconds']} s rolling "
           f"forward — removing features refuses requests, adding them does not (F-040)")
    else:
        no(f"the record shows rolling back ({leg1['route']['outage_seconds']} s) no worse than "
           f"rolling forward ({leg2['route']['outage_seconds']} s) — F-040's asymmetry is absent")

    # (e) the M5 gate was run AT the half-way state and its coherence check was
    # GREEN there. Green at v2 alone is satisfiable by a literal; green at v1 is
    # what proves the check is coherence.
    half = rec["at_the_half_way_state"]
    if half["exit_code"] != 0 and half["coherence_green"]:
        ok(f"`verify-m5` at the half-way state exited {half['exit_code']} with "
           f"{len(half['failures'])} failure(s) while its coherence check stayed GREEN at "
           f"{leg1['to_feature_set']!r} — the gate noticed the pointer moved, and the check that "
           f"compares tag-to-config passed on the OTHER feature set")
    else:
        no(f"the half-way run does not show a RED gate with a green coherence line: {half}")

    # (f) and the end state is byte-identical, which is the story-exit invariant
    # M6 law 2 sets. Compared by git hash, not by eye.
    if end["configs_train_yaml_sha_before"] == end["configs_train_yaml_sha_after"] \
            and rec["at_the_end_state"]["exit_code"] == 0:
        ok(f"the end state is the declared one: @champion {end['alias_version']}, features.version "
           f"{end['features_version']}, configs/train.yaml byte-identical by git hash-object "
           f"({end['configs_train_yaml_sha_before'][:12]}…), and `verify-m5` GREEN again")
    else:
        no(f"the end state is not byte-identical or the gate did not come back green: {end}, "
           f"exit={rec['at_the_end_state']['exit_code']}")

    # (g) the runbook's REHEARSED claim must cite a record this repo holds, and
    # the claim is read off the SECTION HEADING (M5-S5's repair: §4 legitimately
    # contains both a dated rehearsal and a sentence about an UNPROVEN mitigation,
    # and a body search cannot tell them apart).
    runbook = Path("docs/runbooks/serving.md").read_text()
    body = re.search(r"##\s*4\..*?(?=\n---|\n##\s*5\.)", runbook, re.S)
    body = body.group(0) if body else ""
    heading = body.splitlines()[0] if body else ""
    rehearsed = re.search(r"(?<!NOT\s)REHEARSED\s+(\d{4}-\d{2}-\d{2})", heading, re.I)
    cited = [c for c in re.findall(r"automation/runs/[\w./-]+\.json", body) if Path(c).exists()]
    if rehearsed and cited:
        ok(f"the runbook's §4 heading declares REHEARSED {rehearsed.group(1)} and cites a record "
           f"this repo holds ({', '.join(cited)}) — M5's 'typed but not rehearsed' is discharged")
    else:
        no(f"the runbook's §4 heading ({heading.strip()!r}) does not claim a dated rehearsal backed "
           f"by an existing record (cited: {cited or 'nothing'})")

    # (h) F-040's remedy is NAMED and labelled UNPROVEN. Changing the order after
    # measuring the asymmetry would be a change made on the authority of the
    # number just seen; saying so is the honest half.
    if re.search(r"UNPROVEN|NOT (?:YET )?(?:PROVEN|REHEARSED)", body, re.I):
        ok("§4 names the reordered remedy (deploy first, move the config line last) and labels it "
           "UNPROVEN — a mitigation nobody has run must not be substituted mid-incident")
    else:
        no("§4 carries no UNPROVEN label on the reordered rollback remedy — F-040's untested "
           "mitigation reads as procedure")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the rollback check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the rollback check"

# ------------------------------------------------------------ 6. gameday ------
section "6. Gameday 1 — the control first, the predictions on disk first, and one of them wrong"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
from datetime import datetime
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

def when(t):
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))

try:
    base = Path("automation/runs/m6-gameday")
    preds = json.loads((base / "predictions.json").read_text())
    summary = json.loads((base / "gameday.json").read_text())
    scen = {n: json.loads((base / f"{n}.json").read_text())
            for n in ("control", "kill", "storage", "saturation")}

    # (a) THE PREDICTIONS WERE WRITTEN FIRST, and it is checked against clocks
    # rather than against the file's own claim to have been. A prediction amended
    # after the fact is the one thing that would make this whole exercise a
    # description of what happened.
    written = when(preds["written_at"])
    first = min(when(s["measured_at"]) for s in scen.values())
    if written < first and preds.get("written_before_any_injection"):
        ok(f"the predictions were written {written:%H:%M:%SZ}, before the first scenario was "
           f"measured at {first:%H:%M:%SZ} — checked on the records' own clocks, not on the file's "
           f"claim about itself")
    else:
        no(f"the prediction file is stamped {written} against a first measurement at {first} — a "
           f"prediction written after the event is a description")

    # (b) every scenario's per-scenario prediction is BYTE-EQUAL to the one in
    # the committed predictions file. This is what makes (a) worth anything: a
    # prediction can be written first and then quietly edited into the record.
    drifted = [n for n, s in scen.items()
               if n != "control" and s.get("prediction") != preds["predictions"].get(n)]
    if not drifted:
        ok(f"each scenario record carries the SAME prediction the committed file holds "
           f"({len(scen) - 1} compared field-by-field) — amending one to match an outcome is a diff")
    else:
        no(f"scenario(s) {drifted} carry a prediction that differs from predictions.json")

    # (c) THE POSITIVE CONTROL RAN FIRST, and it was green. Three of the four
    # scenarios make a claim of the form "alert X did not fire", which is worth
    # nothing from an instrument nobody has just watched work.
    order = summary["scenario_order"]
    control = scen["control"]
    control_ok = control.get("verdict") == "GREEN" and all(c["passed"] for c in control["checks"])
    if order and order[0] == "control" and summary.get("positive_control_first") and control_ok:
        ok(f"the positive control ran FIRST and was GREEN {len(control['checks'])}/"
           f"{len(control['checks'])} — the negatives that follow are made by an instrument that "
           f"was just watched working")
    else:
        no(f"the control was not first or was not green: order={order}, verdict="
           f"{control.get('verdict')}")

    # (d) "alert fired in a red-team" — §9/M6's clause, and it is satisfied by
    # observations at ALERTMANAGER, not at Prometheus's own UI. A rule that
    # evaluates and never reaches a receiver has not alerted anybody.
    fired = control["observed"]["fired_at_s"]
    received = control["observed"]["alertmanager_received"]
    if len(fired) >= 2 and set(received) >= set(fired):
        ok(f"alerts FIRED and were RECEIVED: {', '.join(f'{k} at T+{v}s' for k, v in fired.items())}"
           f" — all reaching Alertmanager, not merely evaluating")
    else:
        no(f"the control fired {list(fired)} and Alertmanager received {received}")

    # (e) the must-not-fire list is the load-bearing half. A drill that predicts
    # only 'something fires' cannot be wrong.
    never = control["observed"]["never_fired"]
    # The prediction names each alert with its signal id and its reason, so the
    # comparison takes the alert name out of the object rather than assuming the
    # list is of strings.
    predicted_silent = [p["alert"] if isinstance(p, dict) else p
                        for p in control["prediction"]["must_not_fire"]]
    if set(predicted_silent) <= set(never):
        ok(f"all {len(predicted_silent)} must-NOT-fire alerts stayed inactive — the negative "
           f"predictions are what make the positive one falsifiable")
    else:
        no(f"alert(s) {sorted(set(predicted_silent) - set(never))} were predicted silent and were "
           f"not")

    # (f) THE ACCEPT BAR: at least one prediction wrong AND investigated. Wrong
    # is read off the scenario verdicts; investigated is read off the write-up
    # having a section for it.
    wrong = [n for n, s in scen.items() if s.get("verdict") == "PREDICTION WRONG"]
    doc = Path("docs/gameday_m6.md").read_text()
    investigated = doc.count("prediction that was wrong") + doc.count("wrong prediction") \
        + doc.count("predictions was wrong")
    if wrong and summary.get("accept_bar_met") and investigated:
        ok(f"{len(wrong)} prediction(s) were WRONG ({', '.join(wrong)}) and the write-up "
           f"investigates them in {investigated} named passage(s) — §9/M6's bar, met without "
           f"engineering a surprise")
    else:
        no(f"wrong predictions={wrong}, accept_bar_met={summary.get('accept_bar_met')}, "
           f"investigated passages={investigated} — a gameday with all predictions right was too easy")

    # (g) every scenario read the alias before and after and it never moved. M6
    # law 3, asserted per scenario rather than once at the end.
    moved = {n: s["observed"]["alias"] for n, s in scen.items()
             if "alias" in s.get("observed", {})
             and s["observed"]["alias"]["before"] != s["observed"]["alias"]["after"]}
    checked = [n for n, s in scen.items() if "alias" in s.get("observed", {})]
    if checked and not moved:
        ok(f"@champion was read before AND after {len(checked)} scenario(s) ({', '.join(checked)}) "
           f"and never moved — a gameday that promoted something would be the defect")
    else:
        no(f"alias moved during scenario(s) {moved} (checked: {checked})")

    # (h) the storage scenario's signature is DISTINGUISHABLE from the kill's,
    # which is the property the kickoff asks for by name. Both are outages; only
    # one produces a 5xx ratio, and only one fires A-7's class.
    kill_fired = set(scen["kill"]["observed"]["alerts"]["ever_fired"])
    storage_fired = set(scen["storage"]["observed"]["alerts"]["ever_fired"])
    if storage_fired and storage_fired != kill_fired:
        ok(f"the two outages have DISTINGUISHABLE signatures: the kill fired {sorted(kill_fired) or 'nothing'} "
           f"while the broken credential fired {sorted(storage_fired)} — the kickoff's requirement, "
           f"measured")
    else:
        no(f"the kill and the storage break produced the same alert set ({sorted(kill_fired)}) — "
           f"the signatures are not distinguishable")

    # (i) THE KILL'S OUTAGE MUST RECONCILE WITH ITS OWN PER-REQUEST ANCHORS.
    # gotcha #75, replayed against the gameday's record the way `verify-m5` §5
    # replays it against M5-S4's: an outage is anchored on the first FAILURE and
    # closed by the first SUCCESS after it, so it is strictly LONGER than the
    # span from the first error to the last one — and by at most the gap between
    # two arrivals, because the next sample is what closes it. The bound is
    # derived from the run's own rate; no number is typed. `last_error -
    # first_error` is the wrong quantity and it once reported 182 s for a
    # 13-second outage.
    kill_obs = scen["kill"]["observed"]
    ew = kill_obs["load"]["error_window"]
    rate = kill_obs["load"]["shape"]["target_rate_per_second"]
    outage = kill_obs["outage_seconds"]
    slack = 2.0 / rate
    if ew["span_s"] < outage <= ew["span_s"] + slack:
        ok(f"the kill's {outage} s outage reconciles with its own anchors: strictly longer than the "
           f"{ew['span_s']} s error SPAN and inside one arrival gap of it (2/{rate:g} req/s = "
           f"{slack:g} s) — the span itself is gotcha #75's wrong quantity")
    else:
        no(f"the recorded outage {outage} s does not reconcile with the run's anchors: the error "
           f"span is {ew['span_s']} s and recovery closes on the next success, so the outage must "
           f"lie in ({ew['span_s']}, {ew['span_s'] + slack:g}] at {rate:g} req/s")

    # (j) the undo was STAGED BEFORE the injection and it worked. A drill with no
    # rehearsed undo is a gamble (the M2 red-team rule).
    st = scen["storage"]["observed"]
    if st.get("undo_exit_code") == 0 and all(v == "inactive" for v in st["after_undo_states"].values()):
        ok(f"the storage scenario's undo ran clean (exit {st['undo_exit_code']}) and left all "
           f"{len(st['after_undo_states'])} rules inactive — the injection was reversible before it "
           f"was made")
    else:
        no(f"the undo exited {st.get('undo_exit_code')} and left {st.get('after_undo_states')}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the gameday check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 10 "the gameday check"

# ------------------------------------------- 7. the restore, the prose, the alias
section "7. the restore's honest label, the prose against the records, and the alias law"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    rec = json.loads(Path("automation/runs/m6-restore/restore_drill.json").read_text())

    if rec.get("verdict") == "GREEN" and all(c["passed"] for c in rec["checks"]):
        ok(f"the restore drill recorded {len(rec['checks'])}/{len(rec['checks'])} checks passed "
           f"across {len(rec['databases'])} database(s) and a MinIO bucket")
    else:
        no(f"the restore drill recorded failures: "
           f"{[c['check'] for c in rec['checks'] if not c['passed']]}")

    # (a) it restored into SCRATCH and the live databases were only counted. A
    # restore drill that wrote over a live database would be the incident it
    # rehearses for.
    scratch = [d["scratch_database"] for d in rec["databases"].values()]
    live_same = rec["live_database_sizes"]["before"] == rec["live_database_sizes"]["after"]
    if live_same and all(s.endswith("_restore_drill") for s in scratch) and not rec["minio"]["kept"]:
        ok(f"every restore landed in a scratch database ({', '.join(scratch)}) and a scratch "
           f"bucket, the live database sizes are byte-identical before and after, and no scratch "
           f"survived")
    else:
        no(f"live sizes unchanged={live_same}, scratch names={scratch}, "
           f"bucket kept={rec['minio']['kept']}")

    # (b) THE SECOND WITNESS, and it is what separates 'this restored' from
    # 'something restored': the restored studies carry the trial counts a
    # DIFFERENT record (M3-S4's) wrote months of milestones ago. Live-vs-restored
    # alone is also what restoring the wrong backup into the wrong place shows.
    expected = rec["optuna_studies"]["expected_from_repo"]
    restored = rec["optuna_studies"]["restored"]
    if expected and all(restored.get(k) == v for k, v in expected.items()):
        ok(f"the restored studies carry the trial counts a DIFFERENT record holds "
           f"({', '.join(f'{k}={v}' for k, v in expected.items())}, from "
           f"{rec['expected_from_repo']['sources']['optuna']}) — a witness that is not the live "
           f"database")
    else:
        no(f"the restored studies {restored} do not match what the repo's own records expect "
           f"{expected}")

    if rec["mlflow_alias"]["restored"] == rec["mlflow_alias"]["live"]:
        ok(f"the restored registry carries the same pointer as the live one "
           f"({rec['mlflow_alias']['restored']}) — a backup that loses the alias loses the rollback")
    else:
        no(f"the restored alias {rec['mlflow_alias']['restored']} differs from live "
           f"{rec['mlflow_alias']['live']}")

    art = rec["minio"]["artifact_byte_identity"]
    if art["restored_sha256"] == art["live_sha256"]:
        ok(f"one MLflow artifact came back byte-identical by sha256 "
           f"({art['restored_sha256'][:12]}…, {art['bytes']} bytes) — object counts prove a "
           f"transfer, a hash proves the bytes")
    else:
        no("the restored artifact's sha256 differs from the live object")

    # (c) THE LABEL MOVED EXACTLY ONE NOTCH, EVERYWHERE IT EXISTS — including the
    # line an operator actually SEES when the backup runs. Every artifact that
    # claimed a rehearsal status is checked, and the claim must be the compound
    # one: scratch-rehearsed AND full-restore-still-not.
    labelled = {
        "scripts/platform_backup.sh": Path("scripts/platform_backup.sh").read_text(),
        "docs/gameday_m6.md": Path("docs/gameday_m6.md").read_text(),
        "ledgers/deployments.md": Path("ledgers/deployments.md").read_text(),
    }
    bad = {}
    for name, text in labelled.items():
        has_scratch = re.search(r"scratch[- ]rehearsed", text, re.I)
        # ...and the honest other half, in the same artifact.
        has_limit = re.search(r"full restore.{0,80}(still )?not|not rehearsed.{0,60}full", text, re.I | re.S)
        if not (has_scratch and has_limit):
            bad[name] = f"scratch={bool(has_scratch)} limit={bool(has_limit)}"
    # The runtime line is checked separately BECAUSE it is the one a human reads
    # at 3am rather than in review.
    runtime = [ln for ln in labelled["scripts/platform_backup.sh"].splitlines()
               if ln.lstrip().startswith("echo") and re.search(r"rehears", ln, re.I)]
    stale = [ln.strip()[:90] for ln in runtime if not re.search(r"scratch", ln, re.I)]
    if not bad and runtime and not stale:
        ok(f"the label moved one notch in all {len(labelled)} artifacts that carry it — including "
           f"the {len(runtime)} line(s) the backup PRINTS at runtime, and each says both halves "
           f"(scratch-rehearsed AND full restore still not)")
    else:
        no(f"stale or one-sided rehearsal labels: files={bad or 'none'}; runtime echo(s) still "
           f"claiming un-rehearsed: {stale or 'none'} (runtime lines found: {len(runtime)})")

    # (d) THE PROSE AGAINST THE RECORDS. Every headline number the gameday
    # write-up quotes must be one the scenario records hold. Both sides derived,
    # and matched at every precision the record's own value renders to (gotcha
    # #42 in prose; the anchors are #76's).
    doc = Path("docs/gameday_m6.md").read_text()
    base = Path("automation/runs/m6-gameday")
    kill = json.loads((base / "kill.json").read_text())
    storage = json.loads((base / "storage.json").read_text())
    saturation = json.loads((base / "saturation.json").read_text())
    control = json.loads((base / "control.json").read_text())

    def written(value):
        """Is this record's number in the write-up, at any precision it holds?

        A prose document sensibly writes `13.75 s` for a record holding 13.75
        and `844.3` for 844.3 — a number that has been through a round trip
        exists only at the precision it was written at (gotcha #42). So the
        comparison is made at every precision the record's own value renders to.

        THE FLOOR IS ONE DECIMAL, AND THAT IS NOT A DETAIL. Allowing `d=0` lets
        13.75 render as "14", and "14" appears in almost any document — so the
        check passed against a record whose outage had been rewritten to 13.501,
        which is exactly the fault `verify_m6_redteam.sh` plants. Its own red
        team found this on its first run: gotcha #76 a second time, in the
        ROUNDING direction rather than the substring one. An integer-valued
        record (an error count) still renders as "55" because the trailing zero
        is stripped, so nothing legitimate is lost.

        The match is anchored on both sides for #76's original reason: a bare
        substring search accepts `13` inside `13.75`.
        """
        forms = {f"{value:.{d}f}".rstrip("0").rstrip(".") for d in range(1, 5)}
        return any(re.search(rf"(?<![\d.]){re.escape(f)}(?![\d.]?\d)", doc) for f in forms)

    quoted = {
        "the kill's outage": kill["observed"]["outage_seconds"],
        "the kill's failed requests": float(kill["observed"]["error_count"]),
        "the edge 5xx peak": kill["observed"]["edge_5xx_share_peak"],
        "A-5's firing time": storage["observed"]["alerts"]["first_firing_at_s"]["PredictorNoAvailableReplica"],
        "A-7's firing time": storage["observed"]["alerts"]["first_firing_at_s"]["PredictorStorageInitializerNotReady"],
        "A-6's firing time": saturation["observed"]["alerts"]["first_firing_at_s"]["PredictorCpuThrottledSustained"],
        "the saturation error count": float(saturation["observed"]["error_count"]),
        "A-3's firing time in the control": control["observed"]["fired_at_s"]["PredictorRequestRejectionRateHigh"],
    }
    absent = {k: v for k, v in quoted.items() if not written(v)}
    if not absent:
        outage = quoted["the kill's outage"]
        peak = quoted["the edge 5xx peak"]
        a6 = quoted["A-6's firing time"]
        ok(f"every headline number docs/gameday_m6.md quotes is in the record it cites "
           f"({len(quoted)} checked: outage {outage} s, 5xx peak {peak}, A-6 at T+{a6} s)")
    else:
        no(f"the write-up quotes number(s) no record holds: {absent}")

    # (e) the deployments ledger carries a row for every M6 story that mutated
    # the wire. The ledger is the only place a reader can see what was done TO
    # the running service, and M6 law 2 makes it mandatory.
    ledger = Path("ledgers/deployments.md").read_text()
    rows = {s for s in re.findall(r"M6-S(\d)", ledger)}
    if rows >= {"1", "2", "3", "4", "5"}:
        ok(f"the deployments ledger carries a row for every M6 story that touched the wire "
           f"(M6-S{', M6-S'.join(sorted(rows))})")
    else:
        no(f"the deployments ledger names only M6-S{sorted(rows)} — a wire mutation with no row is "
           f"a change nobody can review")

    # (f) THE ALIAS LAW, in its strong form and live. M6 promotes nothing, so the
    # pointer must still be the run the M3 bake-off recorded as its winner — a
    # claim that cannot be satisfied by not looking, and one that is NOT the
    # literal '2'.
    import mlflow

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    bakeoff = json.loads(Path("automation/runs/m3s5/bakeoff.json").read_text())
    winner_run = next((c["run_id"] for c in bakeoff["contenders"]
                       if c["label"] == bakeoff["winner"]), None)
    if winner_run and champion.run_id == winner_run:
        ok(f"@{reg['champion_alias']} is version {champion.version}, whose run is still the winner "
           f"the M3 bake-off recorded — M6's two sanctioned alias moves round-tripped, and nothing "
           f"else moved the pointer (derived from the record, never typed)")
    else:
        no(f"@{reg['champion_alias']} -> version {champion.version} is not the bake-off's recorded "
           f"winner ({winner_run})")

    versions = client.search_model_versions(f"name='{reg['model_name']}'")
    ungated = [v.version for v in versions if v.tags.get("gate_verdict") != "PROMOTE"]
    if versions and not ungated:
        ok(f"all {len(versions)} registry version(s) still carry gate_verdict=PROMOTE — M6 minted "
           f"nothing, and the rollback rehearsal registered nothing by hand")
    else:
        no(f"version(s) {ungated} carry no PROMOTE verdict — something registered a model outside "
           f"the gate")

    # (g) ONE LIVE PREDICTION, stamped with what the alias says. The verify-m5 §2
    # shape, re-asked here because M6 ends where M5 did and the cheapest proof of
    # that is the service answering as the right model.
    from taxi_mlops.serving import client as client_mod
    from taxi_mlops.serving import parity as parity_mod

    manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    isvc = re.search(r"^\s+name:\s*(\S+)", manifest, re.M).group(1)
    ns = re.search(r"^\s+namespace:\s*(\S+)", manifest, re.M).group(1)
    hazard = parity_mod.HAZARDS[0]
    response = client_mod.infer([hazard.request], client_mod.Endpoint(name=isvc, namespace=ns))
    served = str(response.get("model_version", ""))
    minutes = float(client_mod.minutes_of(response)[0])
    parity = json.loads(Path("automation/runs/m5-parity/parity.json").read_text())
    row = next((r for r in parity["results"] if r["hazard"] == hazard.name), None)
    if served == str(champion.version) and row and abs(row["online_minutes"] - minutes) <= parity["tolerance_minutes"]:
        ok(f"the endpoint answered {minutes:.6f} minutes stamped model_version={served!r} — equal "
           f"to what the alias says, and reproducing the parity record's row for {hazard.name!r} "
           f"to {abs(row['online_minutes'] - minutes):.3e} minutes. M6 ended where M5 did")
    else:
        no(f"the endpoint stamped {served!r} against alias version {champion.version}, quoting "
           f"{minutes:.6f} against the record's {row['online_minutes'] if row else 'no row'}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the closing check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 10 "the closing check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m6] GREEN — every M6 sub-check passed.\033[0m\n'
  printf '            Show: the shadow table    automation/runs/m6-shadow/disagreement.json · docs/shadow_analysis_m6.md\n'
  printf '                  Grafana at canary   http://localhost:8081 (Host: grafana.local) · analytics/grafana/dashboards/serving.json\n'
  printf '                  the gameday record  automation/runs/m6-gameday/ · docs/gameday_m6.md\n'
  exit 0
fi
printf '\033[31m[verify-m6] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS"
exit 1
