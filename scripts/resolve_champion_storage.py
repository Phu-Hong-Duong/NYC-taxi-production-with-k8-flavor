#!/usr/bin/env python3
"""Resolve `models:/<name>@<alias>` to the S3 prefix KServe must download (M5-S2).

THE ONE PLACE THE SERVING PATH RESOLVES THE ALIAS. `scripts/deploy_champion.sh`
calls this and renders its answer into the InferenceService; nothing else in the
serving path may name a bucket, a run id or a logged-model id. That is the same
rule `taxi_mlops.training.score.load_champion` follows for the training side, and
for the same reason: two places that resolve "what is champion?" is two answers
the day the alias moves.

--------------------------------------------------------------------------
F-009's LANDING — option (b), and this script is its evidence
--------------------------------------------------------------------------
The ledger row offers two closures. (a) make the bare alias URI loadable by
fixing what `registry.promote` records as `source`. (b) prove the resolution step
is what SERVING needs too, and record it as a documented property of MLflow 3
rather than a workaround one module happens to carry.

(a) is not available and this is why, not a preference: a version's `source` is
set when the version is CREATED and MLflow exposes no way to change it. Making it
right would mean registering a new version — and M5 is legislated alias-neutral
(kickoff law 2: `@champion` is version 2 and stays version 2), so the fix would
cost exactly the thing the milestone forbids. Worse, it would fix one version and
leave every earlier one — including version 1, the rollback target M5-S5's typed
rollback depends on — pointing at the same empty prefix.

(b) is what actually happened here, and it is a stronger statement than "the
workaround still works". The registry's `source` for the champion reads
`runs:/92b73bd4f77d…/model`, which resolves to
`s3://mlflow-artifacts/6/92b73bd4f77d…/artifacts/model` — a prefix with NOTHING
UNDER IT. Observed while writing this file, with the client MLflow itself
printing it:

    INFO mlflow.store.artifact.artifact_repo: No artifacts found to download at
    s3://mlflow-artifacts/6/92b73bd4f77d…/artifacts/model. Returning destination path.

A deploy that trusted `source` would hand KServe that prefix. The
storage-initializer would download zero objects and SUCCEED — there is no error
in "the prefix is empty" — and mlserver would then fail on a missing `MLmodel`.
That is F-009's exact signature at the serving boundary: an artifact-shaped error
about a model that is perfectly fine.

The property, stated so it can be checked rather than remembered: **on MLflow 3,
a registered model version's `source` is a RUN uri, while its artifacts live
under the LOGGED MODEL's `artifact_location`. Every consumer that needs bytes —
loader, scorer, serving runtime — must resolve alias -> logged model ->
`artifact_location`, and none of them may read `source`.** The discriminator that
tells this apart from its impostor (gotcha #39) costs one call and is run in
`--check` below: under F-009 `get_model_info` SUCCEEDS on the same uri that
`load_model` fails on; under missing MinIO credentials both fail.

Usage: uv run python scripts/resolve_champion_storage.py            (json)
       uv run python scripts/resolve_champion_storage.py --check    (+ the F-009
                                                                     discriminator)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

from taxi_mlops.training import tracking
from taxi_mlops.training.run import load_train_config


class ResolutionError(RuntimeError):
    """The champion cannot be located honestly. Names the reason, never a guess."""


def resolve(train_config: str = "configs/train.yaml") -> dict[str, object]:
    """alias -> {version, run_id, logged_model_id, storage_uri, source}.

    Reads through `get_model_version_by_alias`, never `search_model_versions` —
    on server 3.15.1 that call returns versions whose `aliases` field is EMPTY
    (M2-S3's finding), so a champion resolved that way is resolved by guessing.
    """
    import mlflow

    cfg = load_train_config(train_config)
    tracking.configure(cfg["mlflow"])
    name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]
    client = mlflow.MlflowClient()
    uri = f"models:/{name}@{alias}"
    try:
        version = client.get_model_version_by_alias(name, alias)
    except Exception as exc:  # noqa: BLE001 — an unset alias is a first-class refusal
        raise ResolutionError(
            f"{uri} does not resolve: {exc}. The alias is set by the promotion "
            "gate and by nothing else — there is no model to serve."
        ) from exc

    logged_model_uri = mlflow.models.get_model_info(uri).model_uri
    logged_model_id = logged_model_uri.rsplit("/", 1)[-1]
    location = client.get_logged_model(logged_model_id).artifact_location
    if not location or not location.startswith("s3://"):
        raise ResolutionError(
            f"the champion's artifacts are at {location!r}, which KServe's "
            "storage-initializer cannot fetch. It handles s3:// (among others); "
            "a local path means MLflow was configured without the artifact store."
        )
    return {
        "model_name": name,
        "alias": alias,
        "alias_uri": uri,
        "version": str(version.version),
        "run_id": str(version.run_id),
        "registry_source": str(version.source),
        "logged_model_uri": logged_model_uri,
        "logged_model_id": logged_model_id,
        "storage_uri": location,
    }


def check(resolved: dict[str, object]) -> int:
    """Run gotcha #39's one-call discriminator and print what it proves."""
    import mlflow

    uri = str(resolved["alias_uri"])
    try:
        mlflow.models.get_model_info(uri)
        info_ok = True
    except Exception as exc:  # noqa: BLE001
        info_ok, info_err = False, exc
    try:
        mlflow.lightgbm.load_model(uri)
        load_ok = True
    except Exception as exc:  # noqa: BLE001
        load_ok, load_err = False, exc

    if info_ok and not load_ok:
        print(  # noqa: T201 — redirected to stderr by main; see the note there
            f"[resolve] F-009 CONFIRMED (not its impostor): get_model_info({uri}) "
            f"SUCCEEDS while load_model on the SAME uri fails — {type(load_err).__name__}: "
            f"{str(load_err)[:80]}"
        )
        print(
            "[resolve] so this is MLflow 3's logged-model layout, NOT a credential "
            "problem (gotcha #39: under missing MinIO credentials BOTH calls fail)."
        )
        return 0
    if info_ok and load_ok:
        print(
            f"[resolve] the bare alias uri {uri} now LOADS. F-009's option (a) has "
            "become true — re-read the ledger row before keeping the resolution step."
        )
        return 0
    print(
        f"[resolve] FAIL: get_model_info({uri}) also failed — {info_err}. This is "
        "gotcha #39's IMPOSTOR, not F-009: check MinIO credentials and endpoint "
        "before touching anything about the model.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="also run gotcha #39's discriminator")
    parser.add_argument("--train-config", default="configs/train.yaml")
    args = parser.parse_args(argv)

    # STDOUT CARRIES THE PAYLOAD AND NOTHING ELSE. `tracking.configure` prints a
    # three-line banner naming where it got its credentials — worth having, and
    # it is diagnostics, not data. It used to land on stdout, where the caller's
    # `json.load` met it and died on `Expecting value: line 1 column 2`. Sending
    # every human-facing line to stderr means a shell can read this script with a
    # plain pipe and a human still sees the banner.
    with contextlib.redirect_stdout(sys.stderr):
        resolved = resolve(args.train_config)
        if args.check and check(resolved) != 0:
            return 1
    print(json.dumps(resolved, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make serve`
    raise SystemExit(main())
