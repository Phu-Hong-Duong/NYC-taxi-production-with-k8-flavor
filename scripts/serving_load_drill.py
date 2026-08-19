"""M5-S4: what the endpoint costs under load, and what losing it costs.

Four phases, in one order, each writing a tracked JSON under
`automation/runs/m5-load/`:

  0. preflight  — the route answers, and WHO is answering (pod name AND uid,
                  the deployment's requests/limits, the cgroup counters)
  1. ramp       — several stated rates for short windows, so the headline rate
                  is CHOSEN from a measurement instead of guessed. A capacity
                  number picked by taste is a capacity number nobody can defend.
  2. headline   — the stated rate for the stated window; p50/p95/p99 recorded
                  with the shape beside them, and the container's CPU/memory
                  delta measured ACROSS it for the PRR's capacity box.
  3. self-heal  — the predictor pod is deleted mid-load. The prediction is
                  written to disk BEFORE the kill (M4-S5's drill learned that
                  the expensive way and kept its wrong prediction), the error
                  window is measured off the same clock the load runs on, and
                  the assertion is IDENTITY — a different pod uid, never a
                  different name.

WHY THE KILL IS TIMED FROM INSIDE THE LOAD
------------------------------------------
`run_load(..., on_second=)` calls back once a second from the driver thread, so
the kill fires at a known offset in the SAME timeline the latencies are recorded
in. A kill scheduled by a separate `sleep` in a shell would land at an offset
nobody measured, and "the error window was 43 s" would be 43 s from an event
whose position is a guess.

WHAT THIS DRILL WILL SHOW, AND IT IS NOT FLATTERING
---------------------------------------------------
The predictor runs at ONE replica (`infra/manifests/inferenceservice.yaml`), and
its pod has an init container that pulls the model out of MinIO before mlserver
starts. So losing the pod is a real outage, not a blip, and the number this
drill produces is the honest input to M6's SLO conversation rather than a
rehearsal of a result somebody wanted. It is reported at the size it happens.

This script drives the endpoint and deletes ONE pod that a controller
immediately replaces. It moves no alias, changes no manifest, scales nothing and
touches no other namespace.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taxi_mlops.serving.client import DEFAULT_ROUTE, Endpoint  # noqa: E402
from taxi_mlops.serving.load import (  # noqa: E402
    DEFAULT_RECORD_DIR,
    LoadResult,
    run_load,
    summary_lines,
    write_record,
)

NAMESPACE = "serving"
ISVC = "nyc-taxi-eta"
DEPLOY = f"{ISVC}-predictor"
CONTAINER = "kserve-container"


def sh(*args: str, check: bool = True, timeout: float = 120.0) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} -> {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout.strip()


@dataclass(frozen=True)
class PodIdentity:
    """A pod is its UID. The name is a label a controller may legitimately reuse.

    M4-S5's kill drill predicted a pod NAME and reported a correct survival as a
    failure, because the k8s plugin recreated the pod under the same name with a
    new uid. The property that is true under every controller's naming scheme is
    that a DIFFERENT POD OBJECT ran afterwards.
    """

    name: str
    uid: str
    node: str
    started: str

    def as_record(self) -> dict[str, Any]:
        return {"name": self.name, "uid": self.uid, "node": self.node, "started": self.started}


def predictor_pods() -> list[PodIdentity]:
    raw = sh(
        "kubectl", "-n", NAMESPACE, "get", "pod",
        "-l", f"app=isvc.{DEPLOY}", "-o", "json",
    )
    pods = []
    for item in json.loads(raw).get("items", []):
        pods.append(
            PodIdentity(
                name=item["metadata"]["name"],
                uid=item["metadata"]["uid"],
                node=item["spec"].get("nodeName", "?"),
                started=item["status"].get("startTime", "?"),
            )
        )
    return sorted(pods, key=lambda p: p.started)


def ready_pod() -> PodIdentity | None:
    for pod in predictor_pods():
        raw = sh(
            "kubectl", "-n", NAMESPACE, "get", "pod", pod.name,
            "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
            check=False,
        )
        if raw == "True":
            return pod
    return None


def cgroup_counters() -> dict[str, float]:
    """CPU-seconds and current memory, read from the container's own cgroup.

    `kubectl top` is unavailable on this cluster (no metrics-server — checked:
    "Metrics API not available"), and installing one to measure a capacity box
    would be a platform change inside a measurement story. The cgroup files ARE
    the source metrics-server samples, read directly and differenced across the
    load window, which is a stronger number than a 15-second scrape average:
    `cpu.stat`'s usage_usec is cumulative, so the delta over a known wall time
    is exactly the mean cores used, with no sampling error at all.
    """
    raw = sh(
        "kubectl", "-n", NAMESPACE, "exec", f"deploy/{DEPLOY}", "-c", CONTAINER, "--",
        "sh", "-c", "cat /sys/fs/cgroup/cpu.stat; echo mem $(cat /sys/fs/cgroup/memory.current); "
        "echo peak $(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)",
    )
    out: dict[str, float] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0]] = float(parts[1])
    return out


def resources() -> dict[str, Any]:
    raw = sh(
        "kubectl", "-n", NAMESPACE, "get", "deploy", DEPLOY,
        "-o", f"jsonpath={{.spec.template.spec.containers[?(@.name=='{CONTAINER}')].resources}}",
    )
    replicas = sh(
        "kubectl", "-n", NAMESPACE, "get", "deploy", DEPLOY, "-o", "jsonpath={.spec.replicas}"
    )
    return {
        "container": CONTAINER,
        "resources": json.loads(raw or "{}"),
        "replicas": int(replicas or 0),
    }


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(record: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[drill] record -> {path}")
    return path


# --------------------------------------------------------------------------
# phases
# --------------------------------------------------------------------------
def phase_preflight(endpoint: Endpoint, out: Path) -> dict[str, Any]:
    print("\n=== phase 0 — preflight: who is answering, and with what ===")
    pod = ready_pod()
    if pod is None:
        raise SystemExit("[drill] no READY predictor pod — `make serve` first")
    warm = run_load(endpoint, rate=2, seconds=3, concurrency=1, label="preflight-warm")
    if warm.errors:
        raise SystemExit(f"[drill] the endpoint is not healthy: {warm.error_window()}")
    res = resources()
    record = {
        "story": "M5-S4",
        "phase": "preflight",
        "measured_at": stamp(),
        "pod": pod.as_record(),
        "deployment": res,
        "cgroup": cgroup_counters(),
        "warmup": {
            "requests": len(warm.attempts),
            "errors": len(warm.errors),
            "served_versions": warm.served_versions,
        },
    }
    print(f"[drill] serving pod {pod.name} uid={pod.uid} on {pod.node}")
    print(f"[drill] replicas={res['replicas']} resources={json.dumps(res['resources'])}")
    print(f"[drill] warm: {len(warm.attempts)} requests, 0 errors, version {warm.served_versions}")
    write(record, out / "preflight.json")
    return record


def phase_ramp(
    endpoint: Endpoint, rates: list[float], seconds: float, concurrency: int, out: Path
) -> dict[str, Any]:
    print(f"\n=== phase 1 — ramp: {rates} req/s x {seconds:g}s each ===")
    steps = []
    for rate in rates:
        result = run_load(
            endpoint, rate=rate, seconds=seconds, concurrency=concurrency,
            label=f"ramp-{rate:g}rps",
            note="ramp step: short window, run to CHOOSE the headline rate rather than guess it",
        )
        for line in summary_lines(result):
            print(line)
        write_record(result, out / f"ramp-{rate:g}rps.json")
        steps.append(
            {
                "target_rate": rate,
                "achieved_rate": round(result.achieved_rate, 3),
                "errors": len(result.errors),
                "latency_ms": {k: round(v, 3) for k, v in result.percentiles("latency_ms").items()},
                "service_ms": {k: round(v, 3) for k, v in result.percentiles("service_ms").items()},
            }
        )
        time.sleep(2)
    record = {
        "story": "M5-S4",
        "phase": "ramp",
        "measured_at": stamp(),
        "window_seconds": seconds,
        "concurrency": concurrency,
        "steps": steps,
    }
    write(record, out / "ramp.json")
    return record


def phase_headline(
    endpoint: Endpoint, rate: float, seconds: float, concurrency: int, out: Path
) -> LoadResult:
    print(
        f"\n=== phase 2 — headline: {rate:g} req/s for {seconds:g}s "
        f"at concurrency {concurrency} ==="
    )
    before = cgroup_counters()
    result = run_load(
        endpoint, rate=rate, seconds=seconds, concurrency=concurrency,
        label=f"headline-{rate:g}rps-{seconds:g}s",
        note="THE quoted load shape. Percentiles are scheduled->response (latency_ms); "
             "service_ms is beside them so the coordinated-omission gap is visible.",
    )
    after = cgroup_counters()
    for line in summary_lines(result):
        print(line)
    cpu_seconds = (after.get("usage_usec", 0) - before.get("usage_usec", 0)) / 1e6
    mean_cores = cpu_seconds / result.wall_seconds if result.wall_seconds else 0.0
    ok = len(result.ok_attempts) or 1
    # THROTTLING IS THE DIRECT EVIDENCE OF THE CEILING. `cpu.stat` counts the
    # periods in which the kernel stopped this container because it had spent its
    # quota, and for how long. A mean-cores figure near the limit is suggestive;
    # a non-zero `nr_throttled` delta across the window is the limit being HIT,
    # measured by the thing that enforces it. `memory.peak` is cumulative since
    # the container started, so it is reported as a high-water mark and NOT as a
    # window measurement — a delta of it would mean nothing.
    capacity = {
        "cpu_seconds_during_window": round(cpu_seconds, 3),
        "wall_seconds": round(result.wall_seconds, 3),
        "mean_cores": round(mean_cores, 3),
        "core_seconds_per_request": round(cpu_seconds / ok, 4),
        "cpu_throttled_periods_during_window": int(
            after.get("nr_throttled", 0) - before.get("nr_throttled", 0)
        ),
        "cpu_throttled_seconds_during_window": round(
            (after.get("throttled_usec", 0) - before.get("throttled_usec", 0)) / 1e6, 3
        ),
        "memory_current_bytes_after": after.get("mem"),
        "memory_peak_bytes_since_container_start": after.get("peak"),
        "deployment": resources(),
    }
    print(
        f"[drill] capacity: {cpu_seconds:.1f} CPU-seconds over {result.wall_seconds:.1f}s "
        f"= {mean_cores:.2f} mean cores of a "
        f"{capacity['deployment']['resources'].get('limits', {}).get('cpu')} CPU limit "
        f"({capacity['core_seconds_per_request']:.3f} core-s/request); throttled "
        f"{capacity['cpu_throttled_periods_during_window']} period(s) for "
        f"{capacity['cpu_throttled_seconds_during_window']:.1f}s; memory now "
        f"{after.get('mem', 0) / 2**20:.0f} MiB, peak since start "
        f"{after.get('peak', 0) / 2**20:.0f} MiB"
    )
    record = result.as_record()
    record["capacity"] = capacity
    write(record, out / "headline.json")
    return result


def phase_selfheal(
    endpoint: Endpoint, rate: float, seconds: float, concurrency: int, kill_at: float, out: Path
) -> dict[str, Any]:
    print(
        f"\n=== phase 3 — self-heal: kill the predictor at T+{kill_at:g}s "
        f"of a {seconds:g}s load ==="
    )
    before = ready_pod()
    if before is None:
        raise SystemExit("[drill] no READY pod to kill")

    # THE PREDICTION, WRITTEN BEFORE THE KILL. M4-S5's drill wrote one, got it
    # wrong (it predicted a pod NAME), and kept the wrong prediction rather than
    # quietly correcting it. A prediction written afterwards is a description.
    prediction = {
        "story": "M5-S4",
        "written_at": stamp(),
        "written_before_the_kill": True,
        "target": before.as_record(),
        "kill_at_seconds": kill_at,
        "load_shape": {"rate": rate, "seconds": seconds, "concurrency": concurrency},
        "expected": [
            "the deleted pod's UID never serves again; a pod with a DIFFERENT uid does "
            "(identity, not name — the controller is free to reuse a name)",
            "an error window opens at or shortly after the kill and CLOSES inside this "
            "load window, with the load still arriving at the stated rate throughout",
            "the replacement answers with the SAME model version, because the alias did "
            "not move and the pod pulls the same storageUri",
            "the tail of the window is error-free at a p95 comparable to the headline run",
        ],
        "honest_expectation": (
            "one replica plus an init container that downloads the model from MinIO means "
            "this is a real outage of tens of seconds, not a blip. The number is the PRR's "
            "input, not a result to be flattered."
        ),
    }
    write(prediction, out / "kill-prediction.json")

    killed = {"at": None, "output": None}

    def on_second(elapsed: int) -> None:
        if killed["at"] is None and elapsed >= kill_at:
            killed["at"] = elapsed
            print(f"[drill] T+{elapsed}s: deleting pod {before.name} (uid {before.uid})")
            killed["output"] = sh(
                "kubectl", "-n", NAMESPACE, "delete", "pod", before.name,
                "--wait=false", check=False,
            )

    result = run_load(
        endpoint, rate=rate, seconds=seconds, concurrency=concurrency,
        label=f"selfheal-{rate:g}rps-{seconds:g}s",
        note=f"the predictor pod was deleted at T+{kill_at:g}s of this window",
        on_second=on_second,
    )
    for line in summary_lines(result):
        print(line)

    after = ready_pod()
    window = result.error_window()
    buckets = result.buckets()
    tail = [b for b in buckets if b["second"] >= seconds - 30]
    tail_errors = sum(b["errors"] for b in tail)
    tail_p95 = max((b["p95_latency_ms"] or 0.0) for b in tail) if tail else None

    checks: list[tuple[bool, str]] = []
    checks.append(
        (
            killed["at"] is not None,
            f"the kill fired inside the load window (T+{killed['at']}s)",
        )
    )
    checks.append(
        (
            after is not None and after.uid != before.uid,
            f"a DIFFERENT pod object serves afterwards: uid {before.uid} -> "
            f"{after.uid if after else 'NONE'} (names {before.name} -> "
            f"{after.name if after else 'NONE'})",
        )
    )
    # A drill that disturbs nothing proves nothing. With one replica the kill
    # MUST cost requests; zero errors here would mean the load was not actually
    # in flight across the kill, and the drill says so rather than going green.
    checks.append(
        (
            window["errors"] > 0,
            f"the kill was actually felt: {window['errors']} failed request(s), "
            f"classes {window.get('classes')}",
        )
    )
    checks.append(
        (
            window["last_error_s"] is not None and window["last_error_s"] < seconds,
            f"the error window CLOSED inside the load: last error at "
            f"T+{window['last_error_s']}s of {seconds:g}s",
        )
    )
    checks.append((tail_errors == 0, f"the last 30s are error-free ({len(tail)} bucket(s))"))
    checks.append(
        (
            len(result.served_versions) == 1,
            f"one model version served the whole window: {result.served_versions}",
        )
    )
    ok_after = run_load(endpoint, rate=2, seconds=3, concurrency=1, label="selfheal-after")
    checks.append((not ok_after.errors, "the endpoint answers cleanly after the drill"))

    record = result.as_record()
    record["kill"] = {
        "target": before.as_record(),
        "fired_at_seconds": killed["at"],
        "kubectl": killed["output"],
        "replacement": after.as_record() if after else None,
        "different_pod_object": bool(after and after.uid != before.uid),
    }
    record["recovery"] = {
        "error_window": window,
        "outage_seconds_measured": window["span_s"],
        "bucket_resolution_seconds": 1,
        "tail_30s_errors": tail_errors,
        "tail_30s_p95_latency_ms": tail_p95,
    }
    record["checks"] = [{"passed": ok, "check": text} for ok, text in checks]
    record["passed"] = all(ok for ok, _ in checks)
    write(record, out / "selfheal.json")

    print()
    for ok, text in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--name", default=ISVC)
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--ramp", default="5,10,15,20", help="ramp rates, req/s")
    parser.add_argument("--ramp-seconds", type=float, default=20.0)
    parser.add_argument(
        "--rate", type=float, default=0.0, help="headline rate; 0 = choose from the ramp"
    )
    parser.add_argument("--seconds", type=float, default=60.0, help="the headline window")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--selfheal-seconds", type=float, default=180.0)
    parser.add_argument("--kill-at", type=float, default=30.0)
    parser.add_argument("--out", default=str(DEFAULT_RECORD_DIR))
    parser.add_argument(
        "--skip-selfheal", action="store_true", help="phases 0-2 only (a probe, not the drill)"
    )
    args = parser.parse_args(argv)

    endpoint = Endpoint(name=args.name, namespace=args.namespace, route=args.route)
    out = Path(args.out)
    started = time.perf_counter()

    phase_preflight(endpoint, out)
    ramp = phase_ramp(
        endpoint, [float(r) for r in args.ramp.split(",")], args.ramp_seconds, args.concurrency, out
    )

    rate = args.rate
    if rate <= 0:
        # Choose the highest ramp step that both held its stated rate and stayed
        # error-free. "Held its rate" is the honest criterion: a step whose
        # achieved rate fell short did not measure what it claims to have.
        clean = [
            step for step in ramp["steps"]
            if step["errors"] == 0 and step["achieved_rate"] >= 0.95 * step["target_rate"]
        ]
        rate = max((step["target_rate"] for step in clean), default=ramp["steps"][0]["target_rate"])
        print(f"\n[drill] headline rate CHOSEN from the ramp: {rate:g} req/s "
              f"(highest step that held its rate with no errors)")

    headline = phase_headline(endpoint, rate, args.seconds, args.concurrency, out)

    selfheal = None
    if not args.skip_selfheal:
        selfheal = phase_selfheal(
            endpoint, rate, args.selfheal_seconds, args.concurrency, args.kill_at, out
        )

    latency = headline.percentiles("latency_ms")
    summary = {
        "story": "M5-S4",
        "measured_at": stamp(),
        "wall_seconds": round(time.perf_counter() - started, 1),
        "headline": {
            "rate_per_second": rate,
            "window_seconds": args.seconds,
            "concurrency": args.concurrency,
            "mix": headline.mix,
            "achieved_rate_per_second": round(headline.achieved_rate, 3),
            "errors": len(headline.errors),
            "latency_ms": {k: round(v, 3) for k, v in latency.items()},
        },
        "selfheal": None
        if selfheal is None
        else {
            "passed": selfheal["passed"],
            "different_pod_object": selfheal["kill"]["different_pod_object"],
            "outage_seconds_measured": selfheal["recovery"]["outage_seconds_measured"],
            "errors": selfheal["recovery"]["error_window"]["errors"],
            "tail_30s_errors": selfheal["recovery"]["tail_30s_errors"],
        },
    }
    write(summary, out / "summary.json")

    print()
    print(f"[drill] headline p95 {latency['p95']:.1f} ms / p99 {latency['p99']:.1f} ms at "
          f"{rate:g} req/s for {args.seconds:g}s, concurrency {args.concurrency}, "
          f"{headline.mix} mix, {len(headline.errors)} error(s)")
    if selfheal is not None:
        print(f"[drill] self-heal {'PASSED' if selfheal['passed'] else 'FAILED'}: "
              f"{selfheal['recovery']['error_window']['errors']} failed request(s) over "
              f"{selfheal['recovery']['outage_seconds_measured']}s, "
              f"different pod object = {selfheal['kill']['different_pod_object']}")
        return 0 if selfheal["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
