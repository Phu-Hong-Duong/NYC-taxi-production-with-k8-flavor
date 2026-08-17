"""Watch the gate refuse a challenger that beats the FLOOR and is worse than the
model riders are already getting (F-011, M3-S1).

Why this red team is not `--hobble`. M2-S3's drill fitted a challenger on
permuted labels: it scored 7.6667 and every condition refused it by a mile, which
proves the gate is wired up and proves nothing about the incumbent condition.
F-011's failure lives in a window about 0.02 minutes wide — a challenger that
clears a 2.00% margin over the floor and is a hair worse than the champion — and
no hobbled FIT lands in a window that narrow on purpose. So the challenger here
is BUILT rather than fitted: the champion's own booster with a fixed +0.06 min
(3.6 s) bias added to every quote, which is what an ordinary regression looks
like from the outside. Same class of instrument as a permuted label — a
deliberate, stated degradation — aimed at a narrower defect.

WHERE 0.06 CAME FROM: `data/predictions/test` was queried for the MAE and the
within-5-min rate of `predicted + delta` at several deltas (0.02 … 0.10). That
query CHOSE a constant; it reports nothing. Every number printed below is
computed by `taxi_mlops.training.evaluate` on the spot (gotcha #15), and the
drill FAILS if the constructed challenger does not really land in the window — a
red team that quietly tests something easier than it claims is worse than none.

The two refusals it watches, both live:

1. `gate.decide` REFUSES the challenger, naming the incumbent and printing both
   models' KPI-09 and KPI-10 — while the FLOOR conditions pass, which is what
   makes this a test of the new condition rather than of the old ones.
2. `registry.promote` REFUSES a promotion that never consulted the incumbent —
   the bypass. `decide` takes its incumbent optionally (the first promotion has
   none; M2's replayed verdicts carry none), so this is the half that stops
   "optional" from meaning "skippable".

It mutates NOTHING: the alias and the versions are snapshotted before and after
and must be identical (the M2-S3 shape). The bypass attempt deliberately uses the
CHAMPION's OWN run id — if the guard ever failed, the worst case is a no-op
re-promotion of the model that is already champion, rather than a hobbled run
becoming a version.

It is a .py and not a heredoc inside a .sh for a reason that cost one run: the
OpenMP shim (gotcha #37) RE-EXECS the interpreter, and a script fed on stdin
cannot be re-executed — the source is gone. A file path replays verbatim.

Usage: `make gate-redteam` · runtime ~6 min (it fits the configured floor on the
six train months, because a gate transcript with a floor quoted from a document
instead of re-derived is exactly what this program refuses).
"""

from __future__ import annotations

import sys

BIAS_MINUTES = 0.06

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'ok  ' if condition else 'FAIL'} {message}")
    if not condition:
        FAILURES.append(message)


def main() -> int:
    # FIRST, before anything imports lightgbm: the shim may re-exec this process,
    # and re-execing after loading 44M rows would do that work twice (M2-S2).
    from taxi_mlops.training.openmp import ensure_openmp

    print(f"[openmp] {ensure_openmp()}")

    import mlflow

    from taxi_mlops.data.config import load_config
    from taxi_mlops.training import baselines, gate, registry, score
    from taxi_mlops.training.datasets import load_split
    from taxi_mlops.training.evaluate import evaluate, results_table
    from taxi_mlops.training.run import _resolve_incumbent, load_train_config

    print("\n\033[1m[red team] F-011: a challenger that clears the floor and regresses "
          "on the incumbent\033[0m\n")

    train_cfg = load_train_config("configs/train.yaml")
    data_cfg = load_config(train_config="configs/train.yaml")
    features_cfg, eval_cfg = train_cfg["features"], train_cfg["evaluate"]
    gate_cfg = train_cfg["gate"]
    holdout, target = gate_cfg["holdout_split"], train_cfg["target"]

    # The client is built AFTER load_champion, which calls tracking.configure():
    # one built before it reads whatever tracking URI the environment happened to
    # hold, and fails with a message about MLmodel that reads exactly like F-009
    # but is really absent MinIO credentials (gotcha #39).
    champion = score.load_champion(train_cfg)
    client = mlflow.MlflowClient()
    model_name = train_cfg["registry"]["model_name"]
    alias = train_cfg["registry"]["champion_alias"]

    def snapshot() -> dict:
        """Alias + versions. The alias is read through get_model_version_by_alias
        and never off search_model_versions, whose `aliases` field is EMPTY on
        server 3.15.1 (M2-S3) — a snapshot built from it would be blind to the
        exact mutation this drill is checking for."""
        try:
            pointed = str(client.get_model_version_by_alias(model_name, alias).version)
        except Exception:  # noqa: BLE001 — an unset alias is a legitimate state
            pointed = None
        versions = sorted(
            int(v.version) for v in client.search_model_versions(f"name='{model_name}'")
        )
        return {"alias": pointed, "versions": versions}

    before = snapshot()
    print(f"[registry] before: @{alias} -> version {before['alias']}, "
          f"versions {before['versions']}\n")

    train = load_split("train", data_cfg, features_cfg, target)
    print(f"[data] train {len(train):>12,} rows  months={','.join(train.months)}")
    floor = baselines.fit_floor(
        gate_cfg["floor"], train.features, train.y, train_cfg["baselines"]
    )
    print(f"[baseline] {floor.name}: {floor.groups:,} groups")
    del train

    held = load_split(holdout, data_cfg, features_cfg, target)
    print(f"[data] {holdout:<5} {len(held):>12,} rows  months={','.join(held.months)}\n")

    y = held.y.to_numpy()
    champion_pred = score._as_trained(champion).predict(held.features)
    challenger_pred = champion_pred + BIAS_MINUTES
    floor_pred = floor.predict(held.features)

    name = f"champion-v{champion.version}-plus-{BIAS_MINUTES:g}min"
    challenger_metrics = evaluate(name, holdout, y, challenger_pred, eval_cfg)
    floor_metrics = evaluate(
        floor.name, holdout, y, floor_pred.values, eval_cfg, unseen_rate=floor_pred.unseen_rate
    )
    champion_metrics = evaluate(
        f"champion-v{champion.version}-as-served", holdout, y, champion_pred, eval_cfg
    )

    print("[evaluate] every number below came from taxi_mlops.training.evaluate\n")
    print(results_table([champion_metrics, challenger_metrics, floor_metrics]))

    incumbent = _resolve_incumbent(train_cfg, holdout)
    print()
    check(
        incumbent is not None,
        f"the registry names an incumbent to defend "
        f"(version {incumbent.version if incumbent else '—'})",
    )
    if incumbent is None:
        return 1

    # The premise. If the constructed challenger does not clear the floor bar,
    # this drill is exercising the margin condition while claiming the incumbent
    # one — so it is checked out loud rather than assumed.
    floor_only = gate.decide(challenger_metrics, floor_metrics, gate_cfg)
    check(
        floor_only.passed,
        f"PREMISE: the floor conditions ADMIT this challenger "
        f"({floor_only.observed_pct:+.2f}% vs {floor.name})",
    )
    check(
        challenger_metrics.mae > incumbent.mae,
        f"PREMISE: the challenger is worse than what is serving "
        f"({challenger_metrics.mae:.4f} vs {incumbent.mae:.4f} min)",
    )

    print("\n" + "=" * 78)
    print("[gate] THE SAME GATE, with the incumbent condition live")
    decision = gate.decide(challenger_metrics, floor_metrics, gate_cfg, incumbent=incumbent)
    print(gate.verdict_lines(decision))
    print("=" * 78 + "\n")

    check(not decision.passed, "the gate REFUSED the challenger (VERDICT REFUSE; the CLI exits 1)")
    failed = [c for c in decision.checks if not c.passed]
    check(
        bool(failed) and all("serving champion" in c.name for c in failed),
        f"every failed condition is an INCUMBENT condition: {[c.name for c in failed]}",
    )
    check(
        any("KPI-09" in c.name for c in failed),
        "KPI-09 against the incumbent is in the transcript with both models' numbers",
    )
    check(
        all(c.passed for c in decision.checks if "serving champion" not in c.name),
        "the floor conditions still PASSED — this refusal is the new condition's",
    )

    print()
    try:
        registry.promote(
            client,
            model_name=model_name,
            alias=alias,
            run_id=champion.run_id,
            incumbent_version=None,
        )
        check(False, "registry.promote accepted a promotion that never read the alias")
    except registry.PromotionError as exc:
        check("F-011" in str(exc), f"registry.promote REFUSED the bypass: {str(exc)[:88]}…")

    after = snapshot()
    print()
    check(after == before, f"the registry is IDENTICAL after the drill: {after}")

    print()
    if FAILURES:
        print(f"\033[31m[red team] FAILED — {len(FAILURES)} check(s) did not hold.\033[0m")
        return 1
    print("\033[32m[red team] GREEN — the gate refused a challenger the floor admitted, named")
    print("           the incumbent, and moved nothing. F-011 cannot happen silently.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
