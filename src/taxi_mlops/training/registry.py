"""Promotion — the only module in this package allowed to touch the registry.

`gate.py` decides; this file acts, and only ever on a decision that passed. The
split is not tidiness: a decision is a pure function that can be unit-tested to
its boundaries, while everything here mutates shared state that outlives the
process. Keeping them apart means the interesting logic is testable without a
cluster and the dangerous logic is small enough to read in one sitting.

Three rules live here, all of them refusals:

- **A model without a signature and an input example is not promotable.** The
  MLE charter refuses "a model registered without signature + input example",
  and the reason is M5's: a served model whose inputs are undeclared fails at the
  serving boundary with a shape error against a payload nobody can check against
  anything. `promote()` reads the logged model's metadata back and refuses.

- **Promotion is idempotent BY RUN.** Re-running against a run that is already
  registered reuses that version instead of minting a second one, and an alias
  already pointing at it is left alone. `scripts/metabase_boards.py` converges by
  NAME for the same reason (M1-S5): a converging path that creates a duplicate on
  every invocation is not converging, it is accumulating.

- **Nothing here deletes.** Superseded versions stay; the alias moves. Destroying
  is `make destroy`'s job — the same asymmetry `scripts/postgres_databases.sh`
  keeps. A champion that was replaced is exactly what a rollback needs to find.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class PromotionError(RuntimeError):
    """The winner cannot be promoted honestly. Names the missing piece, never guesses."""


@dataclass(frozen=True)
class Promotion:
    """What promotion actually did — enough to tell a no-op from a change."""

    model_name: str
    alias: str
    version: str
    run_id: str
    version_created: bool
    alias_moved: bool
    previous_version: str | None

    @property
    def noop(self) -> bool:
        return not self.version_created and not self.alias_moved

    def lines(self) -> str:
        out = [
            f"[promote] registered model: {self.model_name}",
            f"[promote] version         : {self.version}"
            + ("  (created)" if self.version_created else "  (already registered for this run)"),
            f"[promote] run             : {self.run_id}",
        ]
        if self.alias_moved:
            was = self.previous_version or "unset"
            out.append(f"[promote] alias @{self.alias}   : {was} -> {self.version}")
        else:
            out.append(
                f"[promote] alias @{self.alias}   : already version {self.version} — NO-OP "
                "(re-running the gate on the same champion changes nothing)"
            )
        return "\n".join(out)


def _default_model_info(uri: str) -> Any:
    from mlflow.models import get_model_info

    return get_model_info(uri)


def assert_servable(model_uri: str, *, model_info: Callable[[str], Any] = _default_model_info):
    """Refuse a model that could not be served against a payload anyone can check.

    Reads the logged metadata BACK rather than trusting that the logging call
    passed a signature: the two are different claims, and only the second one is
    what a serving container will find.
    """
    try:
        info = model_info(model_uri)
    except Exception as exc:  # noqa: BLE001 — the cause is reported verbatim below
        raise PromotionError(
            f"{model_uri} cannot be read back: {exc}. Artifacts that 404 here are "
            "gotcha #5 (the tracking server does not proxy them; the client writes "
            "to MinIO itself) — check MLFLOW_S3_ENDPOINT_URL before the model."
        ) from exc
    if getattr(info, "signature", None) is None:
        raise PromotionError(
            f"{model_uri} has no signature. A registered model without one fails at "
            "M5's serving boundary with a shape error against a payload nobody can "
            "validate. Log it with `signature=infer_signature(...)`."
        )
    if getattr(info, "saved_input_example_info", None) is None:
        raise PromotionError(
            f"{model_uri} has no input example. The signature says what the model "
            "claims to accept; the example is the one payload we know it does."
        )
    return info


def promote(
    client: Any,
    *,
    model_name: str,
    alias: str,
    run_id: str,
    artifact_path: str = "model",
    description: str | None = None,
    version_tags: dict[str, str] | None = None,
    model_info: Callable[[str], Any] = _default_model_info,
) -> Promotion:
    """Register this run's model (once) and point `alias` at it (once). Idempotent."""
    source = f"runs:/{run_id}/{artifact_path}"
    assert_servable(source, model_info=model_info)

    _ensure_registered_model(client, model_name, description)

    existing = _version_for_run(client, model_name, run_id)
    if existing is None:
        created = client.create_model_version(name=model_name, source=source, run_id=run_id)
        version, version_created = str(created.version), True
    else:
        version, version_created = str(existing.version), False

    for key, value in (version_tags or {}).items():
        client.set_model_version_tag(name=model_name, version=version, key=key, value=str(value))

    previous = _alias_version(client, model_name, alias)
    alias_moved = previous != version
    if alias_moved:
        client.set_registered_model_alias(name=model_name, alias=alias, version=version)

    return Promotion(
        model_name=model_name,
        alias=alias,
        version=version,
        run_id=run_id,
        version_created=version_created,
        alias_moved=alias_moved,
        previous_version=previous,
    )


def _ensure_registered_model(client: Any, model_name: str, description: str | None) -> None:
    try:
        client.get_registered_model(model_name)
    except Exception:  # noqa: BLE001 — MlflowException subclasses; absence is the normal path
        client.create_registered_model(name=model_name, description=description)


def _version_for_run(client: Any, model_name: str, run_id: str) -> Any:
    """The version already minted from this run, if any — the idempotence hinge."""
    versions = client.search_model_versions(f"name='{model_name}'")
    matching = [v for v in versions if getattr(v, "run_id", None) == run_id]
    if not matching:
        return None
    # Newest first, so a registry that somehow holds two versions of one run
    # resolves deterministically instead of by iteration order.
    return sorted(matching, key=lambda v: int(v.version))[-1]


def _alias_version(client: Any, model_name: str, alias: str) -> str | None:
    try:
        return str(client.get_model_version_by_alias(model_name, alias).version)
    except Exception:  # noqa: BLE001 — an unset alias is the first-promotion path
        return None
