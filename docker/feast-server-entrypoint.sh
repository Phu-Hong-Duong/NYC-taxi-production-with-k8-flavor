#!/usr/bin/env bash
# The feature server's start-up, and the one thing it does before serving.
#
# `feast apply` FIRST, every start. The registry is generated and gitignored on
# the host for a reason `docs/feast_catalog.md` §2 argues at length — the
# definitions in git are the source of truth and a registry checked in beside
# them would be the second home F-013 keeps deleting — and the same argument
# forbids baking one into this image. So the pod DERIVES its registry from the
# `definitions.py` it carries, at every start, which makes the registry a
# function of the image's git content rather than of whatever the host happened
# to have applied on the day the image was built.
#
# It also means a definitions change that was never applied cannot serve stale
# features here: there is no persisted registry to be stale.
#
# `feast apply` is loud on failure and this script does not swallow it — `set -e`
# means a repo that cannot be applied never reaches `serve`, rather than serving
# an empty registry that answers every lookup with null. That failure direction
# matters: an empty registry and a healthy one are indistinguishable from the
# outside (gotcha #78's disease), so the pod must die instead.
set -euo pipefail

: "${FEAST_SERVE_PORT:=6566}"

if [[ -z "${FEAST_REDIS_CONNECTION:-}" ]]; then
  echo "[feast-server] FAIL: FEAST_REDIS_CONNECTION is unset." >&2
  echo "[feast-server]   The online store's address is deliberately not defaulted" >&2
  echo "[feast-server]   (ADR-012): a default would be a wrong address that connects" >&2
  echo "[feast-server]   to something, and 'I cannot see the store' must never read" >&2
  echo "[feast-server]   the same as 'the store said no'." >&2
  exit 2
fi

echo "[feast-server] store=${FEAST_REDIS_CONNECTION} port=${FEAST_SERVE_PORT}"
echo "[feast-server] applying the git-defined repo (the registry is DERIVED, never baked)"
feast apply

echo "[feast-server] serving"
exec feast serve --host 0.0.0.0 --port "${FEAST_SERVE_PORT}" --no-access-log
