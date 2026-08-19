#!/usr/bin/env python3
"""The alias rollback, RUN — F-032's un-rehearsed half (M6-S4).

`docs/runbooks/serving.md` §4 has said "TYPED, **NOT REHEARSED**" since M5-S5,
for a reason that was correct at the time: M5 was legislated alias-neutral, so
rehearsing the rollback would have cost exactly the thing the milestone forbade.
The M5 PRR routed the rehearsal here and M6's kickoff sanctions the two alias
moves. This script runs the runbook's OWN three moves, both ways, and times them.

    LEG 1  v2 -> v1     move the alias (raw) · move features.version · make serve
    LEG 2  v1 -> v2     the same three moves, the other way

WHY IT ROLLS FORWARD AGAIN, AND WHY THAT IS NOT WINDOW-DRESSING. M6 law 2 says
every story ends where it started, so leg 2 is mandatory. It is also the better
half of the evidence: `§4.4` claims "rolling forward is the same procedure with
'2'" and nothing had ever checked that. Two legs also make the coherence check
falsifiable in both directions — `verify-m5` §2 asserting `feature_set == config`
is only a coherence check if it passes at v1 as well as at v2. Passing once, at
the state it was written in, is satisfiable by a literal.

--------------------------------------------------------------------------
THE PART THE RUNBOOK DID NOT KNOW: A ROLLBACK IS NOT ZERO-DOWNTIME HERE
--------------------------------------------------------------------------
A model re-deploy costs 0.5 s (gotcha #80): at one replica `maxUnavailable`
floors to zero, so a surge pod must be ready before the old one goes. A ROLLBACK
is not that, and the difference is the SECOND move. `configs/train.yaml:
features.version` is what every client — `make quote`, the load client, a
rider — builds its matrix from. The moment it moves to `v1`, every request on
the wire carries 5 columns while the pod still holds the 24-column model, and
MLflow's logged signature refuses them. That is F-032's shape, arriving from the
other side, and it lasts until the replacement pod is serving.

So this rehearsal probes the route THROUGHOUT each leg with the matrix a real
client would be building at that instant — v2 before the config move, v1 after —
and measures the error window with the kill drill's anchors (first failure ->
first success, gotcha #75). That window is the true cost of a rollback, it is
not 0.5 s, and it is the number the runbook has been missing.

--------------------------------------------------------------------------
WHAT IT REFUSES TO DO
--------------------------------------------------------------------------
* It will not start from a state that is not the program's declared one
  (`@champion` version 2 AND `features.version: v2`). A rehearsal that begins
  half-rolled-back measures something nobody can name.
* It moves the alias with a RAW `set_registered_model_alias`, exactly as §4.3
  argues: `registry.promote()` refuses an alias move with no gate Decision
  (F-011), and a human overriding the gate should look unusual. Nothing here
  calls `promote`, registers a version, or deletes anything.
* It restores `configs/train.yaml` to `v2` and leaves the tree clean. The file's
  round trip is a real edit both ways; the end state is byte-identical and the
  script checks it.

Usage: uv run python scripts/alias_rollback_rehearsal.py       (via `make rollback`)
       uv run python scripts/alias_rollback_rehearsal.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import mlflow

from taxi_mlops.features import quote_time, sets
from taxi_mlops.serving.client import Endpoint, QuoteRequest, build_matrix, v2_payload
from taxi_mlops.training import tracking
from taxi_mlops.training.run import load_train_config

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "automation/runs/m6-rollback/alias_rollback.json"
TRAIN_CONFIG = REPO_ROOT / "configs/train.yaml"

MODEL = "nyc-taxi-eta"
ALIAS = "champion"
NAMESPACE = "serving"
ROUTE = "http://localhost:8081"

START_VERSION = "2"
START_SET = "v2"
TARGET_VERSION = "1"

#: The probe's request, and it is deliberately the parity record's own row —
#: 2019-07-04T09:15:00, zone 132 -> 48 — so leg 2's final answer can be checked
#: against a number this program has published rather than against itself.
PROBE_AT = "2019-07-04T09:15:00"
PROBE_PU, PROBE_DO = 132, 48
PROBE_INTERVAL_S = 0.5

#: What the champion answers for that row — `automation/runs/m5-parity/parity.json`,
#: measured at M5-S3 and reproduced by every serving check since. The end state is
#: checked against a number this program has PUBLISHED, not against itself.
PARITY_ROW_MINUTES = 39.001937154

#: WHAT THE RUN GOT WRONG, KEPT (the M5-S4 / M6-S3 precedent, third milestone).
SUPERSEDED_PREDICTIONS = {
    "p5_only_about_the_bake_off_winner": {
        "predicted": (
            "at the half-way state verify-m5's failures are ONLY about the alias not being "
            "the M3 bake-off's recorded winner"
        ),
        "observed": (
            "THREE failures, and only one of them names the pointer: the live answer "
            "10.291528327 differs from the parity record's 10.665224429, the configured "
            "feature set is 5 features wide where parity was measured at 24, and @champion is "
            "not the bake-off's recorded winner"
        ),
        "why_it_was_wrong": (
            "the M5 gate ASKS THE SERVED MODEL for a prediction and checks it against the "
            "parity record (M5-S5 §2, deliberately: a serving gate that never asks for the "
            "artifact would pass against a dead model). Rolling the alias back changes that "
            "answer, so two of the three failures are the gate noticing a different model is "
            "serving — the same fact as the third, through a different instrument. The check "
            "was replaced by a property that survives BOTH states rather than by a wider "
            "keyword list: gotcha #50, and a check that greps a gate's prose is #53/#68."
        ),
    },
}

PREDICTION: dict[str, Any] = {
    "written_before_the_alias_moved": True,
    "p1_the_three_moves_all_succeed_both_ways": (
        "The runbook's §4.2 sequence runs end to end with no edit, in both directions. "
        "§4.4's claim that rolling forward is the same procedure with '2' has never been "
        "checked and is checked here."
    ),
    "p2_a_rollback_is_NOT_a_0_5_s_re_deploy": (
        "The error window is measured in TENS OF SECONDS, not the 0.5 s a model re-deploy "
        "costs (gotcha #80), because the config move changes the request schema on the wire "
        "while the old pod is still serving. Requests fail from the config move until the "
        "replacement pod answers. This is a prediction about the MECHANISM; the magnitude is "
        "unknown and the runbook's own guess ('expect longer than 18.24 s') is the only prior."
    ),
    "p3_leg_1_is_slower_than_leg_2": (
        "Leg 1 takes longer than leg 2: version 1's artifacts are a different MinIO prefix "
        "that no node has cached, while version 2's have been downloaded on this cluster "
        "many times. The runbook says so and nothing has measured it."
    ),
    "p4_the_coherence_check_passes_at_v1_TOO": (
        "`verify-m5` §2's feature_set-vs-config check is GREEN at the half-way state. If it "
        "is not, it was never a coherence check — it was a literal that happened to hold at "
        "v2 (F-017, gotchas #49/#50)."
    ),
    "p5_the_gate_goes_RED_at_v1_and_GREEN_again_at_the_end": (
        "`verify-m5` as a whole goes RED at the half-way state and GREEN again at the end "
        "state. The red is the check doing its job: the rehearsal is a sanctioned deviation "
        "from the gated champion, and a gate that stayed green through it would not be "
        "watching the pointer at all. What the failures SAY is recorded verbatim rather than "
        "pattern-matched — a check that greps a gate's prose is the shape #53/#68 warn about."
    ),
    "p6_the_end_state_is_byte_identical": (
        "@champion is version 2, configs/train.yaml is unchanged by sha, one quote stamps "
        "version 2, and its value reproduces the parity record's own row."
    ),
}


def flip_key(version: str) -> str:
    return f"first_answer_from_version_{version}_at_s"


def sh(*args: str, timeout: float = 1800.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        list(args), capture_output=True, text=True, check=False, cwd=REPO_ROOT, timeout=timeout
    )


def client() -> mlflow.MlflowClient:
    tracking.configure(load_train_config()["mlflow"])
    return mlflow.MlflowClient()


def alias_version(mlflow_client: mlflow.MlflowClient) -> str:
    return str(mlflow_client.get_model_version_by_alias(MODEL, ALIAS).version)


def config_feature_version() -> str:
    pattern = r"^features:\n(?:\s.*\n)*?\s+version:\s*(\S+)"
    match = re.search(pattern, TRAIN_CONFIG.read_text(), re.M)
    if not match:
        raise RuntimeError(f"{TRAIN_CONFIG} no longer carries features.version")
    return match.group(1)


def set_config_feature_version(value: str) -> None:
    """Runbook §4.2 step 4, as an edit to the one line it names.

    Deliberately a line edit and not a YAML round trip: `configs/train.yaml`
    argues its own knobs at length and rewriting it through a serialiser would
    drop every comment in the file — including the ones a person reads during
    the incident this procedure exists for.
    """
    text = TRAIN_CONFIG.read_text()
    new, count = re.subn(
        r"(^features:\n(?:\s.*\n)*?\s+version:\s*)(\S+)",
        rf"\g<1>{value}",
        text,
        count=1,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"{TRAIN_CONFIG}: features.version was not edited exactly once")
    TRAIN_CONFIG.write_text(new)


def bodies() -> dict[str, bytes]:
    """One pre-encoded body per feature set — what a client of each era sends."""
    request = QuoteRequest(PROBE_AT, PROBE_PU, PROBE_DO, 1.0)
    out = {}
    for name in ("v1", "v2"):
        cfg = sets.resolve_set(name)
        matrix = build_matrix([request], cfg)
        out[name] = json.dumps(
            v2_payload(matrix, quote_time.feature_names(cfg)), allow_nan=False
        ).encode()
    return out


class RouteProbe:
    """Fire one request every `PROBE_INTERVAL_S` and record what came back.

    Open-loop in the sense that matters here: the interval is wall-clock, not
    "when the last one returned", so a stalled server produces gaps in the
    record rather than a quietly slower probe (M5-S4's argument, one instrument
    down). The matrix it sends is switched by the caller at the exact moment the
    config line moves, because that is when a real client's matrix would change.
    """

    def __init__(self, endpoint: Endpoint, encoded: dict[str, bytes], features: str) -> None:
        self._endpoint = endpoint
        self._bodies = encoded
        self.features = features
        self.samples: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._t0 = 0.0

    def _run(self) -> None:
        while not self._stop.is_set():
            at = time.perf_counter() - self._t0
            request = urllib.request.Request(  # noqa: S310 — a fixed http:// route
                self._endpoint.infer_url,
                data=self._bodies[self.features],
                headers={"Content-Type": "application/json", "Host": self._endpoint.host},
            )
            sample: dict[str, Any] = {"at_s": round(at, 3), "features": self.features}
            try:
                with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                    payload = json.loads(response.read())
                sample.update(
                    ok=True,
                    status=response.status,
                    model_version=str(payload.get("model_version")),
                    minutes=round(float(payload["outputs"][0]["data"][0]), 6),
                )
            except urllib.error.HTTPError as exc:
                sample.update(ok=False, status=exc.code, error=f"HTTP {exc.code}")
            except Exception as exc:  # noqa: BLE001 — a probe must survive its own faults
                sample.update(ok=False, status=None, error=f"{type(exc).__name__}: {exc}")
            self.samples.append(sample)
            self._stop.wait(PROBE_INTERVAL_S)

    def start(self) -> None:
        self._t0 = time.perf_counter()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=15)

    def summary(self, target_version: str) -> dict[str, Any]:
        failures = [s for s in self.samples if not s["ok"]]
        window: dict[str, Any] = {"failed": len(failures), "sent": len(self.samples)}
        if failures:
            first = failures[0]["at_s"]
            after = [s for s in self.samples if s["ok"] and s["at_s"] > failures[-1]["at_s"]]
            # gotcha #75: anchor on the FIRST failure and close on the first
            # success after the LAST one. `last_error - first_error` is what
            # called a 13 s outage 182 s at M5-S4.
            recovered = after[0]["at_s"] if after else None
            window.update(
                first_failure_at_s=first,
                last_failure_at_s=failures[-1]["at_s"],
                recovered_at_s=recovered,
                outage_seconds=round(recovered - first, 3) if recovered is not None else None,
                classes=sorted({str(s.get("error")) for s in failures}),
            )
        served = [s for s in self.samples if s["ok"]]
        flipped = next((s["at_s"] for s in served if s["model_version"] == target_version), None)
        window[flip_key(target_version)] = flipped
        window["versions_seen"] = sorted({s["model_version"] for s in served})
        return window


def move_alias(mlflow_client: mlflow.MlflowClient, version: str) -> float:
    """Runbook §4.2 step 3, verbatim in intent: a RAW alias set (see §4.3)."""
    started = time.perf_counter()
    mlflow_client.set_registered_model_alias(name=MODEL, alias=ALIAS, version=version)
    landed = alias_version(mlflow_client)
    if landed != version:
        raise RuntimeError(f"@{ALIAS} is {landed} after asking for {version}")
    return time.perf_counter() - started


def leg(
    mlflow_client: mlflow.MlflowClient,
    *,
    name: str,
    to_version: str,
    encoded: dict[str, bytes],
    from_features: str,
) -> dict[str, Any]:
    target = mlflow_client.get_model_version(MODEL, to_version)
    to_features = target.tags.get("feature_set")
    if not to_features:
        raise RuntimeError(
            f"version {to_version} carries no feature_set tag — §4.2 step 2 has no answer, "
            "and this script will not type one (that is the whole of F-032)"
        )
    print(f"\n== leg {name}: @{ALIAS} -> version {to_version}, feature set {to_features} ==")
    print("   (read from the registry, never typed — runbook §4.2 step 2)")

    endpoint = Endpoint(name=MODEL, namespace=NAMESPACE, route=ROUTE)
    probe = RouteProbe(endpoint, encoded, from_features)
    probe.start()
    time.sleep(5)  # a few seconds of the pre-rollback steady state, as the control

    leg_started = time.perf_counter()
    alias_seconds = move_alias(mlflow_client, to_version)
    print(f"   [1/3] alias moved in {alias_seconds:.3f}s")

    config_started = time.perf_counter()
    set_config_feature_version(to_features)
    probe.features = to_features  # every client's matrix changes HERE
    config_seconds = time.perf_counter() - config_started
    print(f"   [2/3] configs/train.yaml features.version -> {to_features} in {config_seconds:.3f}s")

    serve_started = time.perf_counter()
    serve = sh("make", "serve")
    serve_seconds = time.perf_counter() - serve_started
    print(f"   [3/3] make serve in {serve_seconds:.1f}s (exit {serve.returncode})")
    if serve.returncode != 0:
        print(serve.stdout[-3000:])
        print(serve.stderr[-3000:])
        raise RuntimeError(f"make serve failed during leg {name}")
    total = time.perf_counter() - leg_started

    time.sleep(8)  # let the probe record the recovered steady state
    probe.stop()

    quote = sh("uv", "run", "python", "-m", "taxi_mlops.serving", "--at", PROBE_AT)
    return {
        "to_version": to_version,
        "to_feature_set": to_features,
        "seconds": {
            "move_the_alias": round(alias_seconds, 3),
            "move_the_config_line": round(config_seconds, 3),
            "make_serve": round(serve_seconds, 3),
            "all_three_moves": round(total, 3),
        },
        "route": probe.summary(to_version),
        "one_quote_afterwards": quote.stdout.strip().splitlines(),
        "samples": probe.samples,
    }


def verify_m5_at_this_state() -> dict[str, Any]:
    """Run the M5 gate here and read it HONESTLY, not for a green light.

    §2's coherence sub-check must pass — that is p4, and the whole reason for
    running the gate at a state it was not written in. The gate as a WHOLE is
    expected to go red, because §7 asks whether the alias is still the M3
    bake-off's recorded winner and during a rollback it deliberately is not.
    Both facts are recorded; neither is smoothed over.
    """
    proc = sh("make", "verify-m5", timeout=900.0)
    plain = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
    fails = [line.strip() for line in plain.splitlines() if line.strip().startswith("FAIL")]
    coherence = [
        line.strip()
        for line in plain.splitlines()
        if "feature_set tag" in line and "features.version" in line
    ]
    return {
        "exit_code": proc.returncode,
        "coherence_lines": coherence,
        "coherence_green": bool(coherence) and all(line.startswith("ok") for line in coherence),
        "failures": fails,
    }


def judge(record: dict[str, Any]) -> dict[str, bool]:
    """Every check, derived from the record and NOTHING else.

    Separated from the run for a reason this story paid for: the first version of
    `r4` demanded that every half-way failure name the bake-off winner, and the
    gate — correctly — also reported that the served model no longer reproduces
    the parity record, because M5-S5 §2 asks the endpoint for a real prediction.
    A wrong assertion about a correct system (gotcha #50) is repaired by fixing
    the property and RE-JUDGING the evidence, exactly as `verify-m3` replays
    recorded verdicts rather than re-running a bake-off. Re-running this
    rehearsal would have cost two more alias moves, and M6's kickoff sanctions
    exactly two.
    """
    leg1, leg2 = record["leg_1_rollback"], record["leg_2_roll_forward"]
    half, end_gate = record["at_the_half_way_state"], record["at_the_end_state"]
    end = record["end_state"]
    final = end["last_champion_answer_minutes"]
    checks = {
        "r1_leg1_moved_all_three_and_v1_answered": leg1["route"][flip_key(TARGET_VERSION)]
        is not None,
        "r2_leg2_moved_all_three_and_v2_answered": leg2["route"][flip_key(START_VERSION)]
        is not None,
        "r3_the_coherence_check_was_green_at_v1": half["coherence_green"],
        # The coherence check is only a coherence check if it holds on BOTH
        # sides. Green at v2 alone is satisfiable by a literal.
        "r4_the_coherence_check_is_green_at_v2_too": record["at_the_end_state"]["coherence_green"],
        "r5_the_gate_went_RED_at_the_half_way_state": half["exit_code"] != 0
        and bool(half["failures"]),
        "r6_the_gate_is_GREEN_again_at_the_end_state": end_gate["exit_code"] == 0
        and not end_gate["failures"],
        "r7_the_end_state_is_the_declared_one": (
            end["alias_version"],
            end["features_version"],
        )
        == (START_VERSION, START_SET),
        "r8_configs_train_yaml_is_byte_identical": end["configs_train_yaml_sha_before"]
        == end["configs_train_yaml_sha_after"],
        "r9_the_final_answer_reproduces_the_parity_row": final is not None
        and abs(final - PARITY_ROW_MINUTES) < 1e-6,
        # A rollback that reported zero cost would be the finding, not the pass:
        # the config move changes the request schema while the old pod serves.
        "r10_the_rollback_leg_has_a_measured_outage": leg1["route"].get("outage_seconds")
        is not None,
    }
    record["checks"] = {k: bool(v) for k, v in checks.items()}
    record["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    return record["checks"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--rejudge",
        action="store_true",
        help="re-derive the verdict from the existing record and re-run verify-m5 at the "
        "CURRENT state; moves no alias and edits no config (the verify-m3 replay idiom)",
    )
    args = parser.parse_args(argv)

    if args.rejudge:
        record = json.loads(RECORD.read_text())
        record["prediction"] = PREDICTION
        record["superseded_predictions"] = SUPERSEDED_PREDICTIONS
        record["at_the_end_state"] = verify_m5_at_this_state()
        record["judged_by"] = (
            "--rejudge: the checks were corrected after the run (gotcha #50) and re-applied "
            "to the recorded evidence. The two alias moves in this record are the only two "
            "M6 sanctions; re-running would have spent two more."
        )
        judge(record)
        RECORD.write_text(json.dumps(record, indent=2) + "\n")
        for name, ok_ in record["checks"].items():
            print(f"  {'ok  ' if ok_ else 'FAIL'} {name}")
        print(
            f"[rollback] {record['verdict']} — "
            f"{sum(record['checks'].values())}/{len(record['checks'])} checks (re-judged)"
        )
        return 0 if record["verdict"] == "PASS" else 1

    RECORD.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "story": "M6-S4",
        "what": "docs/runbooks/serving.md §4 run for real, both ways — F-032's un-rehearsed half",
        "sanctioned_by": "M6 kickoff law 3: the alias moves exactly twice, inside this rehearsal",
        "prediction": PREDICTION,
        "superseded_predictions": SUPERSEDED_PREDICTIONS,
    }
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[rollback] prediction written to {RECORD} — the alias has not moved")

    if args.dry_run:
        print("[rollback] --dry-run: would run the runbook's three moves v2->v1, verify at that")
        print("           state, then the same three moves v1->v2. Nothing was changed.")
        return 0

    mlflow_client = client()
    config_sha_before = sh("git", "hash-object", str(TRAIN_CONFIG)).stdout.strip()
    start_alias, start_set = alias_version(mlflow_client), config_feature_version()
    if (start_alias, start_set) != (START_VERSION, START_SET):
        print(
            f"REFUSING: this rehearsal starts from @{ALIAS}={START_VERSION} and "
            f"features.version={START_SET}; found {start_alias} and {start_set}. A rehearsal "
            "that begins half-rolled-back measures something nobody can name."
        )
        return 2
    print(f"[rollback] start state: @{ALIAS} version {start_alias}, features.version {start_set}")

    encoded = bodies()
    try:
        record["leg_1_rollback"] = leg(
            mlflow_client, name="1 (rollback)", to_version=TARGET_VERSION,
            encoded=encoded, from_features=START_SET,
        )
        print("\n== the half-way state: run the M5 gate where it was never written to run ==")
        record["at_the_half_way_state"] = verify_m5_at_this_state()
        half = record["at_the_half_way_state"]
        print(f"   verify-m5 exit {half['exit_code']}, {len(half['failures'])} FAIL(s)")
        for line in half["coherence_lines"]:
            print(f"   {line}")
    finally:
        # M6 law 2: this ends where it started, whatever happened above.
        if config_feature_version() != START_SET or alias_version(mlflow_client) != START_VERSION:
            record["leg_2_roll_forward"] = leg(
                mlflow_client, name="2 (roll forward)", to_version=START_VERSION,
                encoded=encoded, from_features=record["leg_1_rollback"]["to_feature_set"],
            )

    config_sha_after = sh("git", "hash-object", str(TRAIN_CONFIG)).stdout.strip()
    end_alias, end_set = alias_version(mlflow_client), config_feature_version()
    leg1, leg2 = record["leg_1_rollback"], record["leg_2_roll_forward"]
    half = record["at_the_half_way_state"]
    final_minutes = [s["minutes"] for s in leg2["samples"] if s["ok"] and s["model_version"] == "2"]

    record["end_state"] = {
        "alias_version": end_alias,
        "features_version": end_set,
        "configs_train_yaml_sha_before": config_sha_before,
        "configs_train_yaml_sha_after": config_sha_after,
        "last_champion_answer_minutes": final_minutes[-1] if final_minutes else None,
    }
    print("\n== the end state: run the M5 gate again, where it WAS written to run ==")
    record["at_the_end_state"] = verify_m5_at_this_state()
    judge(record)
    RECORD.write_text(json.dumps(record, indent=2) + "\n")

    print("\n== the rehearsal, measured ==")
    for label, data in (("leg 1  v2 -> v1", leg1), ("leg 2  v1 -> v2", leg2)):
        seconds, route = data["seconds"], data["route"]
        print(
            f"  {label}: alias {seconds['move_the_alias']}s · config "
            f"{seconds['move_the_config_line']}s · make serve {seconds['make_serve']}s "
            f"= {seconds['all_three_moves']}s"
        )
        print(
            f"           route: {route['failed']}/{route['sent']} probes failed, outage "
            f"{route.get('outage_seconds')}s, first answer from version "
            f"{data['to_version']} at t+{route[flip_key(data['to_version'])]}s"
        )
    print(f"\n[rollback] {RECORD}")
    for name, ok_ in record["checks"].items():
        print(f"  {'ok  ' if ok_ else 'FAIL'} {name}")
    print(
        f"[rollback] {record['verdict']} — "
        f"{sum(record['checks'].values())}/{len(record['checks'])} checks"
    )
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
