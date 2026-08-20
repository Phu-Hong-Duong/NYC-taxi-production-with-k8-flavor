#!/usr/bin/env bash
# Deploy the retrain task and its triggers, then READ THEM BACK OFF THE SERVER.
#
# M7-S4. The Flyte 2.x schedule question was answered by ASKING (gotcha #70's
# family, and M4-S2's `/healthz` precedent): `flyte create trigger --help` and
# `flyte.Trigger` both exist on SDK 2.6.1 against chart v2.0.42, so the kickoff's
# recorded cron fallback (the `automation/` watchdog precedent) is NOT executed
# and stays armed and unspent.
#
# TWO PROPERTIES THIS SCRIPT HAS AND A `flyte deploy` ONE-LINER DOES NOT:
#
#   * it reads the trigger list back off the CONTROL PLANE, not off the file it
#     just submitted. `deploy_serving.sh` reads KServe's deployment mode off the
#     live ConfigMap for the same reason: what was submitted and what the server
#     reconciled are two different facts, and only the second one fires.
#   * it refuses to deploy an image the tree has outgrown. A trigger registered
#     against a stale image is worse than a stale pipeline run — it fires
#     unattended, forever, on code nobody can identify (F-026 one cadence up).
#
# DRY_RUN=1 resolves, prints and deploys nothing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/flyte-flyte-binary-http}"
LOCAL_PORT="${FLYTE_LOCAL_PORT:-8094}"
REMOTE_PORT="${FLYTE_REMOTE_PORT:-8090}"
PROJECT="${FLYTE_PROJECT:-nyc-taxi}"
DOMAIN="${FLYTE_DOMAIN:-development}"
ENVIRONMENT="${RETRAIN_ENV:-train_env}"
DRY_RUN="${DRY_RUN:-0}"

MANIFEST="automation/runs/m4-image/image.json"
IMAGE_PATHS=(src pyproject.toml uv.lock docker scripts analytics pipelines)

if [[ ! -f "$MANIFEST" ]]; then
  echo "[schedule] FAIL: $MANIFEST is missing — run 'make image-load' first" >&2
  exit 1
fi
IMAGE_REF="$(python3 -c "import json,sys;print(json.load(open('$MANIFEST'))['image_ref'])")"
IMAGE_SHA="${IMAGE_REF##*:}"
echo "[schedule] task image: $IMAGE_REF"

# `pipelines/` IS guarded here and is deliberately NOT guarded by
# run_pipeline.sh. There, `pipelines/` is the code BUNDLE the CLI uploads per
# run, so guarding it would refuse the very drill that edits it. A trigger has no
# per-run bundle: it fires a task the server already holds, whose code came from
# the image at deploy time. So for a schedule the image is the only carrier of
# BOTH halves, and both must match the tree that is being deployed.
if [[ "$IMAGE_SHA" == *-dirty ]]; then
  echo "[schedule] FAIL: the image was built from a DIRTY tree ($IMAGE_SHA)." >&2
  echo "[schedule]       A schedule fires forever; what it carries must be identifiable." >&2
  exit 3
fi
drift="$(git diff --name-only "$IMAGE_SHA" HEAD -- "${IMAGE_PATHS[@]}" 2>/dev/null || true)"
dirty="$(git status --porcelain -- "${IMAGE_PATHS[@]}")"
if [[ -n "$drift$dirty" ]]; then
  echo "[schedule] FAIL: the task image predates the source it would run (F-026)." >&2
  { [[ -n "$drift" ]] && sed 's/^/[schedule]   committed:   /' <<<"$drift"; } >&2 || true
  { [[ -n "$dirty" ]] && sed 's/^/[schedule]   uncommitted: /' <<<"$dirty"; } >&2 || true
  echo "[schedule]       Fix: make image-load" >&2
  exit 3
fi
echo "[schedule] ok  image $IMAGE_SHA carries this tree's ${IMAGE_PATHS[*]}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[schedule] DRY_RUN=1 — nothing was deployed, no trigger was created or activated."
  exit 0
fi

kubectl -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" \
  >"automation/runs/m7-retrain/schedule-portforward.log" 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

code=000
for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${LOCAL_PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "$code" != "200" ]]; then
  echo "[schedule] FAIL: the Flyte API did not answer through the forward (got '$code')" >&2
  exit 1
fi
echo "[schedule] ok  control plane answers /healthz -> 200"

FLYTE=(uv run flyte --endpoint "localhost:${LOCAL_PORT}" --insecure)
SCOPE=(--project "$PROJECT" --domain "$DOMAIN")

echo "[schedule] deploying environment '$ENVIRONMENT' from pipelines/flyte/workflows.py"
"${FLYTE[@]}" deploy "${SCOPE[@]}" pipelines/flyte/workflows.py "$ENVIRONMENT"

echo
echo "[schedule] triggers, READ BACK OFF THE SERVER:"
"${FLYTE[@]}" get trigger "${SCOPE[@]}"
