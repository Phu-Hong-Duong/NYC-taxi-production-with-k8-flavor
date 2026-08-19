#!/usr/bin/env bash
# verify_m5.sh — the M5 gate, executable. BLUEPRINT §9/M5, quoted:
#
#   "M5 — Serving & release (MLOps A; SRE R). v1's M4 (KServe Standard,
#    mlserver, storage-config, THE parity test 1e-6, p95 measured, self-heal
#    under load) + the Production Readiness Review: SRE walks a written
#    checklist (runbook exists, rollback typed, alerts planned, capacity
#    sanity) BEFORE the champion serves; minutes committed; deployments ledger
#    opens. Accept when: v1's M4 gate AND the PRR minutes exist with every box
#    carrying pasted evidence. Show: parity output + PRR minutes."
#
# The design rules are M2-S5's, M3-S5's and M4-S5's, inherited whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50). This gate types no
#     champion version, no run id, no image tag and no pod name. The served
#     version is compared to what the ALIAS says; the parity tolerance comes
#     from `parity.TOLERANCE_MINUTES` on disk; the hazard count comes from
#     `parity.HAZARDS`; the runbook's quoted numbers are compared to the
#     records they claim to quote.
#   * no skip flag, no fast mode. M1's rule, inherited a fifth time.
#
# RE-RUNS NOTHING EXPENSIVE AND MINTS NOTHING IT COUNTS. It does not run the
# load drill (~6.5 min and a deliberate outage), does not re-run parity's full
# sweep, does not deploy, does not fit, and does not touch the registry except
# to READ. It reads: the tracked records M5-S3/S4/S5 wrote, the live cluster,
# the live registry, the committed docs — and it asks the endpoint for exactly
# ONE prediction, because a serving gate that never asks the service for the
# artifact it exists to produce is a gate that would pass against a dead model
# with a healthy `Ready` condition (gotcha #59, and #71 for why conditions are
# not enough).
#
# WHY THE RECORDS AND NOT A FRESH RUN (gotcha #66's lesson, transplanted). The
# load numbers are a property of one measured shape — a rate, a window, a
# concurrency, a mix. Re-measuring them here would produce different numbers on
# a busier laptop and turn the gate into a flake; worse, it would make the gate
# the thing that decides what p95 is. The records are tracked (F-029), so a
# fresh clone runs these legs against the same bytes, and a tampered record is
# a diff — which is exactly what `verify_m5_redteam.sh` plants.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m5.sh          (via `make verify-m5`)
#        scripts/verify_m5_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")

FAILS=0
CONSUMED=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# Reads `PASS|msg` / `FAIL|msg` lines from a leg and counts them here, so the
# tally lives in exactly one place. ALWAYS call as `consume < <(...)`: a pipeline
# would run this in a subshell and throw the counters away at the closing brace.
consume() {
  CONSUMED=0
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS|"*) pass "${line#PASS|}"; CONSUMED=$((CONSUMED + 1)) ;;
      "FAIL|"*) fail "${line#FAIL|}"; CONSUMED=$((CONSUMED + 1)) ;;
      *) note "$line" ;;
    esac
  done
}

expect_verdicts() {
  local want="$1" label="$2"
  if [[ "$CONSUMED" -lt "$want" ]]; then
    fail "$label emitted $CONSUMED verdict(s), expected at least $want — the check did not run"
  fi
}

printf '\n\033[1m[verify-m5]\033[0m the M5 gate — the route, the champion on the wire, parity,\n'
printf '            the load shape, self-heal, the runbook and the PRR, and the\n'
printf '            alias no M5 story may move. It reads and it asks; it re-runs nothing.\n'

# ------------------------------------------- 1. the route and the operator ----
section "1. the serving PLATFORM — the route answers, and the operator is where it must be"

route_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 localhost:8081/healthz)"
if [[ "$route_code" == "200" ]]; then
  pass "the declared route answers: GET localhost:8081/healthz -> 200 (the controller's OWN endpoint — gotcha #70)"
else
  fail "GET localhost:8081/healthz -> ${route_code:-no answer}: the 8081 route is not up"
fi

consume < <(
  # The node kind published 8081 on is DERIVED from the kind config's cluster
  # name, never typed (gotcha #52): a controller on a worker answers nothing and
  # looks exactly like a KServe fault.
  cluster="$(uv run python - <<'PY' 2>/dev/null
import re, pathlib
text = pathlib.Path("infra/kind/kind-config.yaml").read_text()
m = re.search(r"^name:\s*(\S+)", text, re.M)
print(m.group(1) if m else "")
PY
)"
  want_node="${cluster}-control-plane"
  got_node="$("${KUBECTL[@]}" -n ingress-nginx get pods -l app.kubernetes.io/component=controller \
    -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null)"
  if [[ -z "$cluster" ]]; then
    echo "FAIL|could not read the cluster name out of infra/kind/kind-config.yaml — the node name cannot be derived"
  elif [[ "$got_node" == "$want_node" ]]; then
    echo "PASS|ingress-nginx runs on ${got_node} — the one node whose port 80 kind publishes as 8081 (derived from the kind config, not typed)"
  else
    echo "FAIL|the ingress controller is on '${got_node:-nowhere}', not ${want_node} — the route cannot work from the host"
  fi

  for pair in kserve/kserve-controller-manager cert-manager/cert-manager; do
    ns="${pair%%/*}"; deploy="${pair##*/}"
    ready="$("${KUBECTL[@]}" -n "$ns" get deploy "$deploy" -o jsonpath='{.status.availableReplicas}' 2>/dev/null)"
    if [[ "${ready:-0}" -ge 1 ]]; then
      echo "PASS|${ns}/${deploy}: ${ready} available replica(s)"
    else
      echo "FAIL|${ns}/${deploy} has no available replica — the operator that owns the InferenceService is down"
    fi
  done

  # ADR-004's mode, read off the LIVE ConfigMap and compared with the values
  # file this repo submits. Two sides, both derived: a chart default silently
  # winning would show up as a disagreement rather than as a green literal.
  live_mode="$("${KUBECTL[@]}" -n kserve get configmap inferenceservice-config \
    -o jsonpath='{.data.deploy}' 2>/dev/null | tr -d ' \n' | sed 's/.*defaultDeploymentMode":"\([A-Za-z]*\)".*/\1/')"
  # PARSED, not grepped. The values file argues its own design in comments —
  # "The chart's default is `deploymentMode: Knative`" — and a regex over the
  # text reads that sentence as the setting, which is gotchas #53/#60 exactly:
  # prose sitting where a parser will read it as code. The first draft of this
  # leg went RED against a correct install for precisely that reason.
  want_mode="$(uv run python - <<'PY' 2>/dev/null
import pathlib
import yaml

def find(node, key):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                return v
            found = find(v, key)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find(item, key)
            if found:
                return found
    return None

doc = yaml.safe_load(pathlib.Path("infra/helm/kserve/values.yaml").read_text())
print(find(doc, "deploymentMode") or "")
PY
)"
  if [[ -n "$want_mode" && "$live_mode" == "$want_mode" ]]; then
    echo "PASS|KServe's live deploy mode is ${live_mode} — read off configmap/inferenceservice-config and equal to what infra/helm/kserve/values.yaml submits"
  else
    echo "FAIL|deployment mode disagrees: live '${live_mode:-unknown}' vs values '${want_mode:-unreadable}'"
  fi

  # The runtime is OURS and pinned in this repo (KServe v0.20.0 ships none).
  rt_name="$(uv run python - <<'PY' 2>/dev/null
import re, pathlib
text = pathlib.Path("infra/manifests/serving-runtime-mlserver.yaml").read_text()
m = re.search(r"^metadata:\s*$\s+name:\s*(\S+)", text, re.M)
print(m.group(1) if m else "")
PY
)"
  file_image="$(uv run python - <<'PY' 2>/dev/null
import re, pathlib
text = pathlib.Path("infra/manifests/serving-runtime-mlserver.yaml").read_text()
m = re.search(r"^\s+image:\s*(\S+)", text, re.M)
print(m.group(1) if m else "")
PY
)"
  live_image="$("${KUBECTL[@]}" get clusterservingruntime "$rt_name" \
    -o jsonpath='{.spec.containers[0].image}' 2>/dev/null)"
  if [[ -n "$rt_name" && "$live_image" == "$file_image" && -n "$live_image" ]]; then
    echo "PASS|ClusterServingRuntime ${rt_name} is applied and runs ${live_image} — the image the manifest pins, not a chart default"
  else
    echo "FAIL|runtime ${rt_name:-?}: live image '${live_image:-absent}' vs manifest '${file_image:-unreadable}'"
  fi
)
expect_verdicts 5 "the platform check"

# ----------------------------- 2. what is on the wire IS what the alias says --
section "2. the champion on the wire — resolved from the ALIAS, and asked for one prediction"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "src")

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow

    from taxi_mlops.features import quote_time
    from taxi_mlops.serving import client as client_mod
    from taxi_mlops.serving import parity as parity_mod
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    # Name and namespace come from the manifest this repo applies, never typed.
    manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    isvc_name = re.search(r"^\s+name:\s*(\S+)", manifest, re.M).group(1)
    isvc_ns = re.search(r"^\s+namespace:\s*(\S+)", manifest, re.M).group(1)

    def kubectl(*args):
        return subprocess.run(["kubectl", "--context", "kind-mlops-taxi", *args],
                              capture_output=True, text=True).stdout.strip()

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    mclient = mlflow.MlflowClient()
    champion = mclient.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    alias_version = str(champion.version)

    # (a) the InferenceService is Ready AND its predictor Deployment has a replica.
    ready = kubectl("-n", isvc_ns, "get", "inferenceservice", isvc_name,
                    "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}")
    avail = kubectl("-n", isvc_ns, "get", "deploy", f"{isvc_name}-predictor",
                    "-o", "jsonpath={.status.availableReplicas}")
    if ready == "True" and (avail or "0").isdigit() and int(avail or 0) >= 1:
        ok(f"{isvc_ns}/{isvc_name} is Ready and its predictor has {avail} available replica(s)")
    else:
        no(f"{isvc_ns}/{isvc_name}: Ready={ready!r}, availableReplicas={avail!r}")

    # (b) nothing has STOPPED it. The stop annotation is exactly reversible and
    # therefore exactly the thing a drill can leave behind (M5-S5's rehearsal).
    annots = json.loads(kubectl("-n", isvc_ns, "get", "inferenceservice", isvc_name,
                                "-o", "jsonpath={.metadata.annotations}") or "{}")
    stopped = [k for k in annots if k.endswith("serving.kserve.io/stop")]
    if not stopped:
        ok("no serving.kserve.io/stop annotation is on the InferenceService — nothing left it stopped")
    else:
        no(f"the InferenceService carries {stopped} — it is deliberately stopped")

    # (c) the storageUri on the wire is what the alias resolves to RIGHT NOW.
    # An alias moved without a `make serve` is the half-rollback the runbook
    # warns about, and this is the check that sees it.
    resolved = json.loads(subprocess.run(
        ["uv", "run", "python", "scripts/resolve_champion_storage.py"],
        capture_output=True, text=True).stdout or "{}")
    live_uri = kubectl("-n", isvc_ns, "get", "inferenceservice", isvc_name,
                       "-o", "jsonpath={.spec.predictor.model.storageUri}")
    if resolved.get("storage_uri") and live_uri == resolved["storage_uri"]:
        ok(f"the served storageUri IS what models:/{reg['model_name']}@{reg['champion_alias']} "
           f"resolves to (version {resolved.get('version')})")
    else:
        no(f"storageUri disagrees with the alias: wire={live_uri!r} vs "
           f"alias={resolved.get('storage_uri')!r} — run `make serve`")

    # (d) ONE live prediction, and it must be stamped with the ALIAS's version.
    # This is the only thing that proves a model is loaded and answering.
    hazard = parity_mod.HAZARDS[0]
    endpoint = client_mod.Endpoint(name=isvc_name, namespace=isvc_ns)
    response = client_mod.infer([hazard.request], endpoint)
    served_version = str(response.get("model_version", ""))
    minutes = float(client_mod.minutes_of(response)[0])
    if served_version == alias_version:
        ok(f"the endpoint answered and stamped model_version={served_version!r} — equal to what "
           f"the alias says (never the literal), quoting {minutes:.6f} minutes for hazard "
           f"{hazard.name!r}")
    else:
        no(f"the endpoint stamped model_version={served_version!r} while @{reg['champion_alias']} "
           f"is version {alias_version!r} — the wire and the registry disagree")

    # (e) and that live answer must equal what the parity RECORD wrote for the
    # same row: §9/M5's "Show: parity output", re-shown by the gate at the cost
    # of one request rather than a full sweep.
    record = json.loads(Path("automation/runs/m5-parity/parity.json").read_text())
    row = next((r for r in record["results"] if r["hazard"] == hazard.name), None)
    if row is None:
        no(f"the parity record has no row for hazard {hazard.name!r} — the record and the "
           f"declared set have drifted apart")
    elif abs(row["online_minutes"] - minutes) <= record["tolerance_minutes"]:
        no_delta = abs(row["online_minutes"] - minutes)
        ok(f"the live answer reproduces the recorded parity row to {no_delta:.3e} minutes "
           f"({minutes:.9f} vs {row['online_minutes']:.9f}) — the record describes THIS endpoint")
    else:
        no(f"the live answer {minutes:.9f} differs from the recorded {row['online_minutes']:.9f} "
           f"by more than the recorded tolerance")

    # (f) THE COHERENCE CHECK — the one that catches a half-finished rollback.
    # The served version's `feature_set` tag and configs/train.yaml's
    # features.version must be the same thing. If they are not, every quote
    # sends a matrix the loaded model was not fitted on, and every dashboard
    # still says Ready. Both sides derived: a tag, and a config line.
    tag_set = champion.tags.get("feature_set")
    cfg_set = cfg["features"].get("version")
    if tag_set and tag_set == cfg_set:
        ok(f"the served version's feature_set tag ({tag_set!r}) equals configs/train.yaml's "
           f"features.version — the client builds the matrix this model eats")
    else:
        no(f"HALF-ROLLBACK SHAPE: version {alias_version} eats feature set {tag_set!r} while "
           f"configs/train.yaml says {cfg_set!r} — see docs/runbooks/serving.md §4.1")

    # (g) ...and the width agrees with the record, so 'v2' is not just a string
    # that matches on both sides.
    width = len(quote_time.feature_names(cfg["features"]))
    if width == len(record["feature_names"]):
        ok(f"the configured feature set resolves to {width} features — the width the parity "
           f"record was measured at")
    else:
        no(f"the configured feature set is {width} features wide, the parity record was measured "
           f"at {len(record['feature_names'])}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the wire check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the wire check"

# --------------------------------------------------- 3. parity, from the record
section "3. THE parity test — offline == online, read from the record M5-S3 wrote"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    from taxi_mlops.serving import parity as parity_mod

    record = json.loads(Path("automation/runs/m5-parity/parity.json").read_text())

    # The bar comes from the module on disk, not from the record: a record that
    # loosened its own tolerance would otherwise pass against itself.
    bar = parity_mod.TOLERANCE_MINUTES
    if record["tolerance_minutes"] <= bar:
        ok(f"the record was measured against a tolerance of {record['tolerance_minutes']:.0e} "
           f"minutes, no looser than parity.TOLERANCE_MINUTES ({bar:.0e}) on disk")
    else:
        no(f"the record's tolerance {record['tolerance_minutes']:.0e} is LOOSER than the "
           f"module's {bar:.0e} — the bar was moved to fit the measurement")

    worst = max(abs(r["abs_delta_minutes"]) for r in record["results"])
    if record["passed"] and worst <= bar:
        ok(f"max |offline - online| = {worst:.3e} minutes over {record['rows']} rows — inside "
           f"the {bar:.0e} bar (recomputed from the rows, not read off the summary)")
    else:
        no(f"parity FAILED in the record: max delta {worst:.3e} against a {bar:.0e} bar")

    # Every declared hazard measured, and no row that is not a declared hazard.
    declared = {h.name for h in parity_mod.HAZARDS}
    measured = {r["hazard"] for r in record["results"]}
    if declared == measured and len(record["results"]) == len(parity_mod.HAZARDS):
        ok(f"all {len(declared)} declared hazards were measured and nothing else was — the set "
           f"is committed in parity.HAZARDS, so a shrunken record is a RED gate")
    else:
        no(f"the record's rows and parity.HAZARDS disagree: only-in-code={sorted(declared - measured)}, "
           f"only-in-record={sorted(measured - declared)}")

    # The rows that exist because they are hard: no geometry (F-030, ~1% of all
    # trips) and an OD pair unseen in train. Named by property, not by index.
    hard = [r for r in record["results"] if "no-geometry" in r["hazard"] or "unseen" in r["hazard"]]
    if hard and all(abs(r["abs_delta_minutes"]) <= bar for r in hard):
        ok(f"the {len(hard)} hardest rows ({', '.join(sorted(r['hazard'] for r in hard))}) are "
           f"inside the bar too — the missing-geometry path quotes at all (F-030)")
    else:
        no("the no-geometry / unseen-OD rows are absent or outside the bar")

    if record.get("versions_agree") and str(record["champion"]["version"]) == str(record["served"]["version"]):
        ok(f"the record's offline champion and its endpoint were the same version "
           f"({record['served']['version']}) — a parity number across two different models "
           f"would be meaningless")
    else:
        no(f"the record compared champion version {record['champion']['version']} against served "
           f"version {record['served']['version']}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the parity check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the parity check"

# ------------------------------------------------------ 4. the load shape ------
section "4. p95 with its shape attached — read from the record, never re-measured"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    head = json.loads(Path("automation/runs/m5-load/headline.json").read_text())
    ramp = json.loads(Path("automation/runs/m5-load/ramp.json").read_text())
    shape = head["shape"]

    # A percentile is not a number without its shape. The gate asserts the shape
    # is COMPLETE rather than asserting any particular value: what p95 should be
    # is an SLO, and the SLO document is M6's.
    needed = ["target_rate_per_second", "window_seconds", "concurrency", "mix",
              "rows_per_request", "achieved_rate_per_second"]
    missing = [k for k in needed if shape.get(k) in (None, "")]
    if not missing:
        ok(f"the headline carries its whole shape: {shape['target_rate_per_second']} req/s for "
           f"{shape['window_seconds']:.0f} s, concurrency {shape['concurrency']}, "
           f"{shape['mix']} mix, {shape['rows_per_request']} row(s)/request")
    else:
        no(f"the headline record is missing {missing} — a percentile without its shape")

    # The client kept up: an open-loop client that falls behind is measuring a
    # rate nobody asked for, and the achieved rate is how you can tell.
    drift = abs(shape["achieved_rate_per_second"] - shape["target_rate_per_second"]) \
        / shape["target_rate_per_second"]
    if drift <= 0.05:
        ok(f"achieved {shape['achieved_rate_per_second']} req/s against a target of "
           f"{shape['target_rate_per_second']} ({drift * 100:.1f}% off) — the client kept up, "
           f"so the percentiles belong to the stated rate")
    else:
        no(f"the client achieved {shape['achieved_rate_per_second']} req/s against a target of "
           f"{shape['target_rate_per_second']} — {drift * 100:.1f}% off")

    lat, svc = head["latency_ms"], head["service_ms"]
    ordered = lat["min"] <= lat["p50"] <= lat["p95"] <= lat["p99"] <= lat["max"]
    if ordered:
        ok(f"p50 {lat['p50']} - p95 {lat['p95']} - p99 {lat['p99']} - max {lat['max']} ms, "
           f"monotone and measured from the SCHEDULED instant")
    else:
        no(f"the percentiles are not monotone: {lat}")

    # Coordinated omission, made visible rather than assumed away: scheduled->
    # response can never be smaller than sent->response, and the gap IS the
    # queueing the open loop exists to expose.
    if all(lat[k] >= svc[k] for k in ("p50", "p95", "p99", "max")):
        ok(f"scheduled->response >= sent->response at every percentile (p95 gap "
           f"{lat['p95'] - svc['p95']:.3f} ms) — the omission the open loop exists to expose")
    else:
        no("service_ms exceeds latency_ms somewhere — the two clocks are inconsistent")

    if head["requests"]["errors"] == 0 and head["requests"]["ok"] == head["requests"]["sent"]:
        ok(f"{head['requests']['ok']}/{head['requests']['sent']} requests answered, 0 errors")
    else:
        no(f"the headline window had {head['requests']['errors']} error(s) — the percentiles "
           f"describe a window that was partly failing")

    # gotcha #74, pinned: the headline rate must sit BELOW the CPU ceiling, and
    # the ceiling must have been MEASURED rather than assumed. A rate at the
    # quota measures the quota.
    steps = {s["target_rate"]: s for s in ramp["steps"]}
    chosen = steps.get(shape["target_rate_per_second"])
    saturated = [s for s in ramp["steps"] if s["cpu_saturation"] >= 0.90]
    if chosen and chosen["cpu_saturation"] < 0.90:
        ok(f"the headline rate was chosen at {chosen['cpu_saturation'] * 100:.0f}% of the CPU "
           f"limit — under the 90% clause, so the p95 is the service's and not the quota's "
           f"(gotcha #74)")
    else:
        no(f"the headline rate {shape['target_rate_per_second']} req/s is not a ramp step under "
           f"90% CPU saturation: {chosen}")
    if saturated:
        ok(f"the ceiling was measured, not guessed: {len(saturated)} ramp step(s) reached >=90% "
           f"of the CPU limit (worst {max(s['cpu_saturation'] for s in saturated) * 100:.0f}%)")
    else:
        no("no ramp step ever reached 90% of the CPU limit — the ceiling in the PRR is an "
           "extrapolation")

    # The capacity box the PRR quotes must exist in the record it cites.
    cap = head.get("capacity", {})
    dep = cap.get("deployment", {}).get("resources", {})
    if cap.get("mean_cores") and cap.get("core_seconds_per_request") and dep.get("requests"):
        ok(f"the capacity block is present: {cap['mean_cores']} mean cores, "
           f"{cap['core_seconds_per_request']} core-s/request, request "
           f"{dep['requests'].get('cpu')} vs limit {dep.get('limits', {}).get('cpu')}")
    else:
        no("the headline record carries no capacity block — the PRR's box 4 has no source")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the load check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the load check"

# ------------------------------------------- 5. self-heal, and stop/start ------
section "5. losing the predictor — the outage measured, and the anchors that measure it"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    rec = json.loads(Path("automation/runs/m5-load/selfheal.json").read_text())
    kill, rcv = rec["kill"], rec["recovery"]

    if rec.get("passed") and all(c["passed"] for c in rec["checks"]):
        ok(f"the self-heal drill recorded {len(rec['checks'])}/{len(rec['checks'])} checks passed")
    else:
        failed = [c["check"] for c in rec["checks"] if not c["passed"]]
        no(f"the self-heal drill recorded failures: {failed}")

    # IDENTITY, never name (M4-S5's lesson): the k8s plugin recreates a pod under
    # the SAME name with a new uid, so a name comparison can report a correct
    # survival as a failure and vice versa.
    if kill["target"]["uid"] != kill["replacement"]["uid"] and kill["different_pod_object"]:
        ok(f"a DIFFERENT pod object served afterwards: uid {kill['target']['uid'][:8]}… -> "
           f"{kill['replacement']['uid'][:8]}… (node {kill['target']['node']} -> "
           f"{kill['replacement']['node']})")
    else:
        no("the record does not show a different pod object by uid — the kill proved nothing")

    # gotcha #75, replayed against the record's own numbers: the outage is
    # anchored on the first FAILURE after the kill and closed by the first
    # SUCCESS after that. `last_error - first_error` is the wrong quantity and
    # would read 14.251 s here for the same event; on the first attempt it read
    # 182 s for a 13-second outage.
    span = rcv["error_window"]["span_s"]
    derived = round(rcv["recovered_at_s"] - rcv["first_error_after_kill_s"], 2)
    if abs(derived - rcv["outage_seconds"]) <= 0.02:
        ok(f"the outage is {rcv['outage_seconds']} s and it reconciles: recovered_at "
           f"{rcv['recovered_at_s']} - first_error {rcv['first_error_after_kill_s']} = {derived} "
           f"(the error-span anchor would have said {span} s — gotcha #75)")
    else:
        no(f"the recorded outage {rcv['outage_seconds']} s does not equal recovered_at - "
           f"first_error ({derived} s) — the anchors and the number disagree")

    if rcv["first_error_after_kill_s"] >= rcv["kill_at_s"]:
        ok(f"the first failure ({rcv['first_error_after_kill_s']} s) is AFTER the kill "
           f"({rcv['kill_at_s']} s) — the outage is attributed to the event that caused it")
    else:
        no("the record's first failure precedes the kill — the anchor is not the kill's")

    # The control is the same run's own pre-kill segment: same client, same
    # rate, same minute. A residual error rate quoted without one is a number
    # with nothing to be compared to.
    if rcv["residual_error_rate"] <= rcv["pre_kill_error_rate"] and rcv["requests_after_recovery"] > 0:
        ok(f"after recovery {rcv['requests_after_recovery']} requests at "
           f"{rcv['residual_error_rate'] * 100:.1f}% errors against a pre-kill control of "
           f"{rcv['pre_kill_error_rate'] * 100:.1f}% over {rcv['requests_before_kill']} requests")
    else:
        no(f"residual error rate {rcv['residual_error_rate']} exceeds the pre-kill control "
           f"{rcv['pre_kill_error_rate']}")

    # ---- the stop/start rehearsal (M5-S5) ----
    ss = json.loads(Path("automation/runs/m5-s5/stop-start.json").read_text())
    if ss.get("passed") and ss["seconds_to_stop"] is not None and ss["seconds_to_serve_again"] is not None:
        ok(f"stop/start is REHEARSED: the route stopped answering {ss['seconds_to_stop']} s after "
           f"the annotation and answered again {ss['seconds_to_serve_again']} s after it was "
           f"removed")
    else:
        no("the stop/start rehearsal record does not record a completed stop AND start")

    if ss["after_stop"]["conditions"].get("Stopped") == "True" \
            and ss["after_start"]["conditions"].get("Stopped") == "False" \
            and ss["after_start"]["answering"]:
        ok("the rehearsal observed the mechanism, not just the clock: Stopped False->True->False "
           "and the route answering again at the end")
    else:
        no(f"the rehearsal's conditions do not show a clean stop and start: "
           f"{ss['after_stop']['conditions']} -> {ss['after_start']['conditions']}")

    if not [k for k in ss["after_start"]["annotations"] if k.endswith("serving.kserve.io/stop")]:
        ok("the rehearsal removed its own annotation — the drill left nothing on the object")
    else:
        no("the stop annotation is still on the InferenceService in the record's final state")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the self-heal check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the self-heal check"

# ------------------------------------------ 6. the runbook, the PRR, the ledger
section "6. the PRR — a runbook that runs, a rollback that is typed, boxes that carry evidence"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    runbook_path = Path("docs/runbooks/serving.md")
    prr = sorted(Path("docs/rituals").glob("*_prr-m5.md"))
    ledger = Path("ledgers/deployments.md").read_text()

    if runbook_path.exists():
        runbook = runbook_path.read_text()
        ok(f"{runbook_path} exists ({len(runbook.splitlines())} lines)")
    else:
        runbook = ""
        no(f"{runbook_path} does not exist — the PRR's box 1 has nothing behind it")

    # Every `make X` the runbook tells an operator to type must be a real target.
    # A runbook is only as good as its commands, and a renamed target turns an
    # incident procedure into a typo at the worst possible moment.
    makefile = Path("Makefile").read_text()
    targets = set(re.findall(r"^([a-zA-Z0-9_.-]+):", makefile, re.M))
    typed = set(re.findall(r"\bmake ([a-z0-9-]+)", runbook)) - {"holidays"}
    unknown = sorted(t for t in typed if t not in targets)
    if runbook and not unknown:
        ok(f"every make target the runbook types exists in the Makefile ({len(typed)} distinct: "
           f"{', '.join(sorted(typed))})")
    else:
        no(f"the runbook types make target(s) that do not exist: {unknown}")

    # The rollback must be TYPED (real commands) and must SAY it is not
    # rehearsed. Both halves, because either alone is a trap: an un-typed
    # rollback is useless in an incident, and a typed one presented as proven is
    # worse than none.
    rollback = re.search(r"##\s*4\..*?(?=\n---|\n##\s*5\.)", runbook, re.S)
    body = rollback.group(0) if rollback else ""
    if "set_registered_model_alias" in body and "features.version" in body and "make serve" in body:
        ok("the rollback is TYPED: it moves the alias, moves configs/train.yaml's "
           "features.version with it, and re-deploys — the three halves a rollback needs here")
    else:
        no("the runbook's rollback section does not type the alias move, the feature-set config "
           "line and the re-deploy")
    # THE ROLLBACK MUST DECLARE ITS REHEARSAL STATUS, AND THE CHECK IS THE
    # PROPERTY RATHER THAN THE WORD IT USED TO SAY (F-017, gotchas #49/#50).
    #
    # This asserted `NOT REHEARSED` until M6-S4 ran the rollback for real, at
    # which point a correct, honest, better runbook would have turned it RED —
    # the exact shape that trains the next session to edit assertions. What must
    # hold at every state is that the section says WHICH it is, and that a claim
    # of REHEARSED is backed by a record this repo holds (the M4-S2 backup
    # precedent, in the form that survives the rehearsal happening).
    #
    # The status is read off the section's own HEADING and nowhere else. A body
    # search cannot tell "this procedure has never been run" from "the mitigation
    # named in the last paragraph has never been run" — and §4 now legitimately
    # contains both sentences, which is exactly how the first version of this
    # repair reported a rehearsed rollback as un-rehearsed.
    heading = body.splitlines()[0] if body else ""
    unrehearsed = re.search(r"NOT\s+REHEARSED", heading, re.I)
    rehearsed = re.search(r"(?<!NOT\s)REHEARSED\s+(\d{4}-\d{2}-\d{2})", heading, re.I)
    cited = re.findall(r"automation/runs/[\w./-]+\.json", body)
    if unrehearsed:
        ok("the rollback's heading says NOT REHEARSED — the M4-S2 backup precedent")
    elif rehearsed and any(Path(c).exists() for c in cited):
        held = [c for c in cited if Path(c).exists()]
        ok(f"the rollback is declared REHEARSED {rehearsed.group(1)} and cites a record this "
           f"repo holds ({', '.join(held)}) — a rehearsal claim with evidence behind it")
    elif rehearsed:
        no(f"the rollback claims REHEARSED {rehearsed.group(1)} but cites no record that "
           f"exists (cited: {cited or 'nothing'}) — a claim of proof needs the proof")
    else:
        no(f"the rollback's heading ({heading.strip()!r}) declares neither NOT REHEARSED nor a "
           "dated rehearsal — an operator cannot tell argued from proven")

    # The numbers a runbook quotes must be the numbers the records hold. A
    # runbook quoting a hope is the failure mode this check exists for.
    heal = json.loads(Path("automation/runs/m5-load/selfheal.json").read_text())
    head = json.loads(Path("automation/runs/m5-load/headline.json").read_text())
    ss = json.loads(Path("automation/runs/m5-s5/stop-start.json").read_text())
    quoted = {
        "the outage": heal["recovery"]["outage_seconds"],
        "p95": head["latency_ms"]["p95"],
        "the stop": ss["seconds_to_stop"],
        "the start": ss["seconds_to_serve_again"],
    }

    def written(value: float) -> bool:
        """Is this record's number in the runbook, at ANY precision it holds?

        A prose document quotes `104.2 ms` for a record that holds 104.226, and
        that is not a discrepancy — a number that has been through a round trip
        exists only at the precision it was written at (gotcha #42). So the
        comparison is made at each precision the record's own value can be
        rendered to, which still refuses a number the record does not hold.

        The match is anchored on both sides. A bare substring search accepts
        `14` inside `14.53`, which would let a rewritten 14.251 pass against a
        runbook quoting 14.53 — i.e. the loosening would land exactly on the
        fault the red team plants.
        """
        forms = {f"{value:.{d}f}".rstrip("0").rstrip(".") for d in range(0, 4)}
        return any(re.search(rf"(?<![\d.]){re.escape(form)}(?![\d.]?\d)", runbook)
                   for form in forms)

    absent = {k: v for k, v in quoted.items() if not written(v)}
    if runbook and not absent:
        ok(f"every number the runbook quotes is in the record it cites: outage "
           f"{quoted['the outage']} s, p95 {quoted['p95']} ms, stop {quoted['the stop']} s, "
           f"start {quoted['the start']} s")
    else:
        no(f"the runbook quotes number(s) that no record holds: {absent}")

    # ---- the PRR minutes ----
    if prr:
        minutes = prr[-1].read_text()
        ok(f"the PRR minutes are committed: {prr[-1]}")
    else:
        minutes = ""
        no("no docs/rituals/*_prr-m5.md exists — BLUEPRINT §9/M5 accepts on the minutes existing")

    boxes = re.findall(r"###\s*Box\s*(\d)\s*[-—]\s*([^\n]+)", minutes)
    if len(boxes) == 4:
        ok(f"all four checklist boxes are present: {'; '.join(b[1].strip()[:38] for b in boxes)}")
    else:
        no(f"the minutes carry {len(boxes)} checklist box(es), not the four §9/M5 names "
           f"(runbook exists, rollback typed, alerts planned, capacity sanity)")

    # "every box carrying pasted evidence" — the accept-when, read literally: a
    # box with prose and no artifact is the box this check is for.
    sections = re.split(r"###\s*Box\s*\d\s*[-—]", minutes)[1:]
    bare = [s.splitlines()[0].strip()[:40] for s in sections
            if "```" not in s and "automation/runs/" not in s]
    if sections and not bare:
        ok(f"every box carries pasted evidence — a fenced block or a named record "
           f"({len(sections)} boxes checked)")
    else:
        no(f"box(es) with no pasted evidence: {bare}")

    signals = re.findall(r"^\|\s*A-(\d)\s*\|", minutes, re.M)
    if len(signals) >= 5:
        ok(f"the alert PLAN names {len(signals)} signals with sources — a plan with named "
           f"signals is an artifact; M6 sets their numbers")
    else:
        no(f"the alert plan names {len(signals)} signal(s) — too few to be a plan M6 can implement")

    if re.search(r"F-019", minutes) and re.search(r"422", minutes):
        ok("the F-019 policy's SRE reasoning is minuted here, with the 422 signal it bought "
           "(M5-S2's cross-reference)")
    else:
        no("the minutes do not carry the F-019 serving-policy reasoning the kickoff routes here")

    # ---- the deployments ledger ----
    if "M5-S5" in ledger and "runbook" in ledger.lower() and "PRR" in ledger:
        ok("the deployments ledger carries the M5-S5 serving row (runbook + PRR)")
    else:
        no("ledgers/deployments.md has no M5-S5 row naming the runbook and the PRR")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the PRR check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 10 "the PRR check"

# ------------------------------- 7. the alias no M5 story may move, and v1 -----
section "7. the alias law — serving READS the pointer, and the rollback target really exists"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])

    # M5's law 2, asserted WITHOUT typing a version: the alias must still point
    # at the run the M3 bake-off recorded as its winner. No M5 story may move
    # the pointer, and this is the form of the claim that cannot be satisfied by
    # not looking.
    bakeoff = json.loads(Path("automation/runs/m3s5/bakeoff.json").read_text())
    winner_label = bakeoff["winner"]
    winner_run = next((c["run_id"] for c in bakeoff["contenders"]
                       if c["label"] == winner_label), None)
    if winner_run and champion.run_id == winner_run:
        ok(f"@{reg['champion_alias']} is version {champion.version}, whose run is the winner the "
           f"M3 bake-off recorded — no M5 story moved the pointer (derived from the record, "
           f"never typed)")
    else:
        no(f"@{reg['champion_alias']} -> version {champion.version} (run {champion.run_id}) is not "
           f"the bake-off's recorded winner ({winner_run})")

    # Every registry version was created BY THE GATE. A version hand-registered
    # during a rollback — or by anything else — would carry no gate verdict.
    versions = client.search_model_versions(f"name='{reg['model_name']}'")
    ungated = [v.version for v in versions if v.tags.get("gate_verdict") != "PROMOTE"]
    if versions and not ungated:
        ok(f"all {len(versions)} registry version(s) carry gate_verdict=PROMOTE — every one was "
           f"created by the gate, none by hand")
    else:
        no(f"version(s) {ungated} carry no PROMOTE verdict — something registered a model "
           f"outside the gate")

    # The rollback target the runbook types must EXIST and must say what it
    # eats. A runbook pointing at a version that is not there is a runbook that
    # fails in the incident it was written for.
    others = [v for v in versions if str(v.version) != str(champion.version)]
    with_set = [v for v in others if v.tags.get("feature_set")]
    if with_set:
        ok(f"the rollback target exists: version(s) "
           f"{', '.join(str(v.version) + ' (' + v.tags['feature_set'] + ')' for v in with_set)} "
           f"— each one naming the feature set it eats, which is what makes §4's config step "
           f"derivable")
    else:
        no("no non-champion version carries a feature_set tag — there is nothing to roll back to")

    # And the serving code cannot move a pointer even by accident. Asserted over
    # CODE with `ast`, never over prose: these files argue about promotion at
    # length, and a grep would match the argument (gotchas #53/#68).
    mutating = {"set_registered_model_alias", "delete_registered_model_alias",
                "register_model", "create_model_version", "transition_model_version_stage"}
    offenders = {}
    for path in sorted(Path("src/taxi_mlops/serving").glob("*.py")):
        tree = ast.parse(path.read_text())
        hits = sorted({
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in mutating
        })
        if hits:
            offenders[path.name] = hits
    if not offenders:
        ok(f"no module in src/taxi_mlops/serving/ CALLS a registry-mutating verb "
           f"({len(list(Path('src/taxi_mlops/serving').glob('*.py')))} files parsed with ast, "
           f"not grepped)")
    else:
        no(f"serving code can mutate the registry: {offenders}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the alias check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 4 "the alias check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m5] GREEN — every M5 sub-check passed.\033[0m\n'
  printf '            Show: parity output      automation/runs/m5-parity/parity.json · docs/parity_m5.md\n'
  printf '                  the PRR minutes    docs/rituals/2026-08-19_prr-m5.md\n'
  printf '                  the runbook        docs/runbooks/serving.md\n'
  exit 0
fi
printf '\033[31m[verify-m5] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS"
exit 1
