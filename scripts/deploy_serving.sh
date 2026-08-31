#!/usr/bin/env bash
# deploy_serving.sh — the serving PLATFORM on the kind cluster (M5-S1 half 2),
# behind `make deploy-serving`. It installs the three things a model needs to be
# reachable and installs NO model: ingress-nginx (the declared route),
# cert-manager (KServe's webhook certificates), KServe in Standard/RawDeployment
# mode (ADR-004). The champion goes on the wire at M5-S2.
#
# Order matters and is not incidental:
#   namespaces -> ingress-nginx -> ready -> cert-manager -> ready
#              -> kserve-crd -> kserve-resources -> ready -> the route answers
# cert-manager before KServe because KServe's chart asks cert-manager for its
# webhook certificate; ingress-nginx first because it is the only leg whose
# failure mode is silent (a controller on the wrong node answers nothing and
# looks like a KServe fault).
#
# SELF-SUFFICIENT, the M1-S5 rule inherited a third time: it applies the
# namespace manifest itself rather than documenting "run make deploy-platform
# first". Converge-not-create, so a re-run costs a no-op and the target cannot be
# defeated by running order.
#
# THE CLUSTER IS STATEFUL AND THIS SCRIPT NEVER TAKES IT DOWN (M5 kickoff law 1).
# It publishes no NEW host port and edits no kind config: the route it uses
# (host 8081 -> container 80, 8443 -> 443, on the control-plane node) was
# pre-provisioned at cluster creation for exactly this milestone. It touches no
# PVC and no database. **It also never reads or moves `@champion`** (law 2) —
# nothing here knows the registry exists.
#
# WAITS ARE SIZED FROM A MEASUREMENT, NEVER FROM IMPATIENCE. M4-S2's first Flyte
# install failed `context deadline exceeded` at `--wait --timeout 10m` while
# every pod was healthy: a 99 MB image took 9m49s to pull on this connection.
# So every `--wait` below is 20m. If that is not enough, the answer is to detach
# the run (automation/run_detached.sh), never to shrink the timeout.
#
# NO SECRET IS INVOLVED. Unlike deploy_flyte.sh and deploy_metabase.sh this
# script needs no credential at all — the model store credential is M5-S2's, and
# it is a NEW read-only MinIO identity so a leaked serving credential cannot
# write the registry's artifacts. Nothing here reads .env, so nothing here can
# leak it.
#
# Usage: scripts/deploy_serving.sh            (via `make deploy-serving`)
#        DRY_RUN=1 scripts/deploy_serving.sh  (prints the plan, mutates NOTHING —
#                                              helm included, gotcha #30)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
HELM=(helm --kube-context "$CONTEXT")
# The deploy skeleton (CU-S5). This script installs the PLATFORM and no
# InferenceService, so it uses exactly one function from it — the route-port
# read, which is a fact about the kind config and not about any workload.
source "$REPO_ROOT/scripts/lib/isvc_deploy.sh"
DRY_RUN="${DRY_RUN:-0}"
WAIT_TIMEOUT="${SERVING_WAIT_TIMEOUT:-20m}"

# --- pins ---------------------------------------------------------------------
# Read LIVE 2026-08-19 (`helm search repo … --versions`, `gh`/`curl` against the
# KServe releases API, `helm show chart oci://…` for the two OCI charts). Bump
# here, in one diff, never by letting helm resolve a range.
INGRESS_REPO_URL="https://kubernetes.github.io/ingress-nginx"
INGRESS_CHART="ingress-nginx/ingress-nginx"
INGRESS_CHART_VERSION="4.15.1"          # appVersion 1.15.1
INGRESS_NAMESPACE="ingress-nginx"
INGRESS_RELEASE="ingress-nginx"

CERTMANAGER_REPO_URL="https://charts.jetstack.io"
CERTMANAGER_CHART="jetstack/cert-manager"
CERTMANAGER_CHART_VERSION="v1.21.1"     # appVersion v1.21.1
CERTMANAGER_NAMESPACE="cert-manager"
CERTMANAGER_RELEASE="cert-manager"

# KServe publishes OCI charts, so there is no `helm repo add` for these two and
# no repo index that could drift under us — the version IS the tag.
KSERVE_CRD_CHART="oci://ghcr.io/kserve/charts/kserve-crd"
KSERVE_CHART="oci://ghcr.io/kserve/charts/kserve-resources"
KSERVE_CHART_VERSION="v0.20.0"          # appVersion v0.20.0, released 2026-08-06
KSERVE_NAMESPACE="kserve"
KSERVE_CRD_RELEASE="kserve-crd"
KSERVE_RELEASE="kserve"

# ADR-004's pre-approved fallback, written here so the next reader meets it at
# the wall instead of going looking: if KServe cannot be made to work against
# Kubernetes v1.36 inside three attempts, a plain mlserver Deployment+Service
# behind THIS SAME ingress is legal without a new decision. Parity (S3), load
# (S4) and the PRR (S5) test the WIRE, not the operator, so they survive it
# unchanged. Record it as a dated decision note if it is ever executed.

# --- the route, derived and not typed -----------------------------------------
# gotcha #52's rule: the fix that changes a VALUE leaves the hazard in scope.
# The node name that must appear in the ingress values is a FUNCTION of the kind
# config's cluster name, so it is computed here and the values file is asserted
# against it. A rename of the cluster then fails loudly at deploy time rather
# than scheduling an ingress controller onto a node with no published ports.
KIND_CONFIG="$REPO_ROOT/infra/kind/kind-config.yaml"
CLUSTER_NAME="$(awk '/^name:/ {print $2; exit}' "$KIND_CONFIG")"
INGRESS_NODE="${CLUSTER_NAME}-control-plane"
# The host port the kind config publishes for container port 80, read from the
# same file rather than remembered — it is also what the accept-check curls.
ROUTE_PORT="$(isvc_route_port "$KIND_CONFIG")"

echo "== serving platform =="
echo "   route        host :$ROUTE_PORT -> container :80 on $INGRESS_NODE (published at cluster CREATE)"
echo "   ingress      $INGRESS_CHART $INGRESS_CHART_VERSION"
echo "   certificates $CERTMANAGER_CHART $CERTMANAGER_CHART_VERSION"
echo "   kserve       $KSERVE_CHART $KSERVE_CHART_VERSION (Standard/RawDeployment — ADR-004)"

# The values file and the derived node name must agree. Asserted, not assumed:
# a nodeSelector pointing at a node that does not exist leaves the pod Pending
# with a message about scheduling and nothing about ports.
INGRESS_VALUES="$REPO_ROOT/infra/helm/ingress-nginx/values.yaml"
if ! grep -q "kubernetes.io/hostname: $INGRESS_NODE" "$INGRESS_VALUES"; then
  echo "FAIL: $INGRESS_VALUES does not pin scheduling to '$INGRESS_NODE'," >&2
  echo "      which is the node $KIND_CONFIG publishes port 80 from." >&2
  exit 2
fi
echo "   ok  the ingress values pin scheduling to $INGRESS_NODE (derived from $KIND_CONFIG)"

if ! "${KUBECTL[@]}" get node "$INGRESS_NODE" >/dev/null 2>&1; then
  echo "FAIL: node $INGRESS_NODE does not exist in context $CONTEXT." >&2
  exit 2
fi
echo "   ok  node $INGRESS_NODE exists"

# ------------------------------------------------------------------ DRY_RUN --
# gotcha #30: a preview that "only" re-runs the helm upgrades is a preview that
# restarts things. Nothing below this branch mutates anything.
if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "== [1/6] helm repos ==     DRY_RUN — WOULD add/update ingress-nginx and jetstack"
  echo "== [2/6] namespaces ==     DRY_RUN — WOULD apply infra/manifests/namespaces.yaml"
  echo "== [3/6] ingress-nginx ==  DRY_RUN — WOULD helm upgrade --install $INGRESS_RELEASE $INGRESS_CHART $INGRESS_CHART_VERSION -n $INGRESS_NAMESPACE"
  echo "== [4/6] cert-manager ==   DRY_RUN — WOULD helm upgrade --install $CERTMANAGER_RELEASE $CERTMANAGER_CHART $CERTMANAGER_CHART_VERSION -n $CERTMANAGER_NAMESPACE"
  echo "== [5/6] kserve ==         DRY_RUN — WOULD helm upgrade --install $KSERVE_CRD_RELEASE $KSERVE_CRD_CHART $KSERVE_CHART_VERSION -n $KSERVE_NAMESPACE"
  echo "                           DRY_RUN — WOULD helm upgrade --install $KSERVE_RELEASE $KSERVE_CHART $KSERVE_CHART_VERSION -n $KSERVE_NAMESPACE"
  echo "== [6/6] read back ==      DRY_RUN — WOULD wait for rollouts and curl http://localhost:$ROUTE_PORT/"
  echo
  echo "DRY_RUN — nothing was installed, nothing was upgraded, no namespace was created."
  exit 0
fi

echo
echo "== [1/6] helm repos (idempotent) =="
"${HELM[@]}" repo add ingress-nginx "$INGRESS_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo add jetstack "$CERTMANAGER_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo update ingress-nginx jetstack >/dev/null
echo "   ok  ingress-nginx + jetstack indexes refreshed"

echo
echo "== [2/6] namespaces =="
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/namespaces.yaml"

echo
echo "== [3/6] ingress-nginx — the DECLARED route (host :$ROUTE_PORT) =="
"${HELM[@]}" upgrade --install "$INGRESS_RELEASE" "$INGRESS_CHART" \
  --version "$INGRESS_CHART_VERSION" \
  --namespace "$INGRESS_NAMESPACE" --create-namespace \
  --values "$INGRESS_VALUES" \
  --wait --timeout "$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$INGRESS_NAMESPACE" rollout status \
  deploy/ingress-nginx-controller --timeout="$WAIT_TIMEOUT"
# Where it landed, printed rather than assumed: this is the check that would have
# caught the wrong-node failure the kickoff's R2 warned about, and it is one line.
"${KUBECTL[@]}" -n "$INGRESS_NAMESPACE" get pods -o wide \
  -l app.kubernetes.io/component=controller

echo
echo "== [4/6] cert-manager — KServe's webhook certificates =="
"${HELM[@]}" upgrade --install "$CERTMANAGER_RELEASE" "$CERTMANAGER_CHART" \
  --version "$CERTMANAGER_CHART_VERSION" \
  --namespace "$CERTMANAGER_NAMESPACE" --create-namespace \
  --values "$REPO_ROOT/infra/helm/cert-manager/values.yaml" \
  --wait --timeout "$WAIT_TIMEOUT"
for deploy in cert-manager cert-manager-webhook cert-manager-cainjector; do
  "${KUBECTL[@]}" -n "$CERTMANAGER_NAMESPACE" rollout status \
    "deploy/$deploy" --timeout="$WAIT_TIMEOUT"
done

echo
echo "== [5/6] KServe (Standard / RawDeployment — ADR-004) =="
# The CRDs are their own release ON PURPOSE. Helm does not upgrade CRDs that live
# in a chart's crds/ directory, so KServe ships them as a separate chart; keeping
# that separation means a KServe upgrade is two explicit steps instead of one
# step and a surprise.
"${HELM[@]}" upgrade --install "$KSERVE_CRD_RELEASE" "$KSERVE_CRD_CHART" \
  --version "$KSERVE_CHART_VERSION" \
  --namespace "$KSERVE_NAMESPACE" --create-namespace \
  --wait --timeout "$WAIT_TIMEOUT"
"${HELM[@]}" upgrade --install "$KSERVE_RELEASE" "$KSERVE_CHART" \
  --version "$KSERVE_CHART_VERSION" \
  --namespace "$KSERVE_NAMESPACE" --create-namespace \
  --values "$REPO_ROOT/infra/helm/kserve/values.yaml" \
  --wait --timeout "$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$KSERVE_NAMESPACE" rollout status \
  deploy/kserve-controller-manager --timeout="$WAIT_TIMEOUT"

echo
echo "== [6/6] read it back =="
"${HELM[@]}" list -A --filter 'ingress-nginx|cert-manager|kserve'
echo
# The deployment mode is a VALUE somebody could set and forget. Read it back off
# the live ConfigMap the controller actually consumes, not off the values file
# that was submitted.
DEPLOY_MODE="$("${KUBECTL[@]}" -n "$KSERVE_NAMESPACE" get configmap inferenceservice-config \
  -o jsonpath='{.data.deploy}' 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("defaultDeploymentMode","?"))' 2>/dev/null || echo '?')"
echo "   kserve defaultDeploymentMode (read from the live configmap): $DEPLOY_MODE"
if [[ "$DEPLOY_MODE" != "RawDeployment" ]]; then
  echo "FAIL: KServe is not in RawDeployment mode — ADR-004 chose Standard, and" >&2
  echo "      Knative mode expects a control plane this cluster does not have." >&2
  exit 1
fi

# THE ACCEPT CHECK, in two parts, because "it answered" and "the right thing
# answered" are different questions and only the second one is worth having.
#
#   (a) GET /            must ANSWER. A 404 here is the PASS: the route is up and
#                        no Ingress matches yet, which is the correct state until
#                        M5-S2 puts a model behind it. Connection refused is the
#                        fail — and its first suspect is scheduling, not KServe.
#   (b) GET /healthz     must be 200. This is the CONTROLLER'S OWN health
#                        endpoint, served by its nginx on the same port, i.e. a
#                        positive artifact of the thing that is supposed to be
#                        answering (gotcha #59: assert on the artifact, never on
#                        the absence of an error). It is also the shape M4-S2
#                        settled on for Flyte — ask the server what it serves.
#
# NOT the `Server:` header, which is what the first version of this check used
# and which cost this story a RED run over a perfectly good install: modern
# ingress-nginx omits `Server:` entirely, so the discriminator was testing for a
# header its own chart suppresses on purpose. The body's `<center>nginx</center>`
# is printed below as corroboration and is deliberately NOT the discriminator —
# it would pass for any nginx on earth.
echo
echo "   curl -sS -o /dev/null -D - http://localhost:$ROUTE_PORT/"
ROUTE_HEADERS="$(curl -sS -D - --max-time 15 "http://localhost:$ROUTE_PORT/" 2>/dev/null || true)"
if [[ -z "$ROUTE_HEADERS" ]]; then
  echo "FAIL: nothing answered on http://localhost:$ROUTE_PORT/ — the declared route is dead." >&2
  echo "      Check WHERE the controller scheduled first (kubectl -n $INGRESS_NAMESPACE get pods -o wide):" >&2
  echo "      a controller on a worker answers nothing and looks exactly like a KServe fault." >&2
  exit 1
fi
printf '%s\n' "$ROUTE_HEADERS" | sed 's/^/     /'

HEALTHZ_CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  "http://localhost:$ROUTE_PORT/healthz" 2>/dev/null || echo 000)"
echo "   GET /healthz -> $HEALTHZ_CODE"
if [[ "$HEALTHZ_CODE" != "200" ]]; then
  echo "FAIL: something answered on :$ROUTE_PORT but it does not serve the ingress" >&2
  echo "      controller's own /healthz. A foreign holder of this port is gotcha" >&2
  echo "      #10's territory — run make ports." >&2
  exit 1
fi
echo
echo "ok  the declared route ANSWERS FROM THE CONTROLLER on http://localhost:$ROUTE_PORT/"
echo "    GET / -> 404 (the pass: the route is up and no InferenceService is behind it yet — that is M5-S2)"
echo "    GET /healthz -> 200 (the controller's own endpoint, asked of the server rather than remembered)"
