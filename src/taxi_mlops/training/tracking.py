"""MLflow client wiring — the half of gotcha #5 that lives outside the cluster.

The tracking server does NOT proxy artifacts (infra/helm/mlflow/values.yaml:
`proxiedArtifactStorage: false`), so every client context needs the S3 endpoint
and credentials of its own. Getting that wrong does not look like an auth error:
the run appears in the UI and its artifacts 404 later, usually at the moment
something tries to serve the model.

Secrets are read from the gitignored `.env` that `scripts/platform_secrets.sh`
owns, exactly as `scripts/metabase_boards.py` does, and are never printed — the
banner names the KEYS it set, never their values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..data.config import repo_root

_S3_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION")


class TrackingConfigError(RuntimeError):
    """The client cannot be configured honestly. Names the fix, never the secret."""


def load_env(env_file: Path | None = None, *, missing_ok: bool = False) -> dict[str, str]:
    """Read the gitignored `.env` into a dict.

    `missing_ok` exists for the ONE caller that can legitimately run without the
    file: a process whose environment already carries every value. See
    `configure` for why that case is real and why it is not the default.
    """
    path = env_file or Path(os.environ.get("ENV_FILE", repo_root() / ".env"))
    if not path.exists():
        if missing_ok:
            return {}
        raise TrackingConfigError(
            f"no {path} — scripts/platform_secrets.sh owns it (`make deploy-platform`)"
        )
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def configure(cfg: dict[str, Any], *, env_file: Path | None = None) -> str:
    """Point the MLflow client at the tracking server AND at MinIO. Returns the URI.

    Precedence is deliberate: an already-exported environment variable wins over
    `.env`, which wins over the checked-in default. An in-cluster caller (M4's
    Flyte task) exports the cluster DNS names and needs no code change.

    THE FILE IS OPTIONAL, AND ONLY BECAUSE THE ENVIRONMENT CAN BE COMPLETE. That
    sentence above was written at M2-S2 and was not true until M4-S4: `load_env`
    refused before precedence could apply, so the first in-cluster caller died on
    `no /app/.env` with every value it needed already exported. The task image
    contains no `.env` and must not — secrets never enter an image (MLOps charter,
    and M4-S3 asserts it) — so requiring the file would have meant either baking
    credentials into the artifact or projecting the whole file into the pod.
    A missing file is now simply an empty source, and the refusal moved to where
    it belongs: a value that no source supplies. Nothing is looser — the same
    three keys are still mandatory, and the error now names which source is
    missing them.
    """
    path = env_file or Path(os.environ.get("ENV_FILE", repo_root() / ".env"))
    env = load_env(env_file, missing_ok=True)
    have_file = path.exists()

    tracking_uri = (
        os.environ.get("MLFLOW_TRACKING_URI")
        or env.get("MLFLOW_TRACKING_URI")
        or cfg["tracking_uri"]
    )
    os.environ["MLFLOW_TRACKING_URI"] = tracking_uri

    endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL") or cfg["s3_endpoint_url"]
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = endpoint

    missing = []
    from_env_var = []
    for key in _S3_KEYS:
        exported = os.environ.get(key)
        value = exported or env.get(key)
        if not value:
            missing.append(key)
            continue
        if exported:
            from_env_var.append(key)
        os.environ[key] = value
    if missing:
        source = (
            f"{path} has no value for"
            if have_file
            else f"nothing supplies (and there is no {path})"
        )
        raise TrackingConfigError(
            f"{source}: {', '.join(missing)}. Without them the run is "
            "created and its artifacts 404 later (gotcha #5). Run "
            "`scripts/platform_secrets.sh` — or, for an in-cluster caller, check "
            "that the task pod's environment carries them "
            "(infra/manifests/flyte-task-podtemplate.yaml)."
        )

    # The banner names the SOURCE and not just the keys, because "set from .env"
    # printed by a pod that has no .env is the kind of line that costs an hour:
    # it is the first thing a reader trusts and it was, until this story, wrong
    # for every in-cluster run.
    if not from_env_var:
        source = "from .env"
    elif len(from_env_var) == len(_S3_KEYS):
        source = "from the environment"
    else:
        source = f"from the environment ({', '.join(from_env_var)}) and .env"
    print(f"[mlflow] tracking: {tracking_uri}")
    print(f"[mlflow] artifacts: direct to {endpoint} (server does not proxy)")
    print(f"[mlflow] credentials set {source}: {', '.join(_S3_KEYS)}")
    return tracking_uri
