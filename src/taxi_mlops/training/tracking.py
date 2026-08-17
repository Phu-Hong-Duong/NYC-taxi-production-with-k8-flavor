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


def load_env(env_file: Path | None = None) -> dict[str, str]:
    path = env_file or Path(os.environ.get("ENV_FILE", repo_root() / ".env"))
    if not path.exists():
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
    """
    env = load_env(env_file)

    tracking_uri = (
        os.environ.get("MLFLOW_TRACKING_URI")
        or env.get("MLFLOW_TRACKING_URI")
        or cfg["tracking_uri"]
    )
    os.environ["MLFLOW_TRACKING_URI"] = tracking_uri

    endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL") or cfg["s3_endpoint_url"]
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = endpoint

    missing = []
    for key in _S3_KEYS:
        value = os.environ.get(key) or env.get(key)
        if not value:
            missing.append(key)
            continue
        os.environ[key] = value
    if missing:
        raise TrackingConfigError(
            f".env has no value for: {', '.join(missing)}. Without them the run is "
            "created and its artifacts 404 later (gotcha #5). Run "
            "`scripts/platform_secrets.sh`."
        )

    print(f"[mlflow] tracking: {tracking_uri}")
    print(f"[mlflow] artifacts: direct to {endpoint} (server does not proxy)")
    print(f"[mlflow] credentials set from .env: {', '.join(_S3_KEYS)}")
    return tracking_uri
