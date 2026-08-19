#!/usr/bin/env bash
# deploy_monitoring.sh — the eyes (M6-S1), behind `make deploy-monitoring`.
# Prometheus + Alertmanager + kube-state-metrics + Grafana, on the existing
# cluster, reached through the existing route. It installs NO alert rule (M6-S2
# owns thresholds) and NO model, and it never reads or moves `@champion`.
#
# THE CHOICE, ARGUED HERE BECAUSE THE KICKOFF ASKED FOR THE ARGUMENT.
# The obvious install is `kube-prometheus-stack`: one release, dashboards
# included, and ~10 CRDs plus the prometheus-operator whose job is to turn
# ServiceMonitor objects into a scrape config. This cluster has exactly two
# things worth scraping and one that annotates itself. So the plain
# `prometheus-community/prometheus` chart carries a nine-line scrape config in a
# values file a reviewer can read in a diff, and Grafana comes from its own chart
# with the board provisioned from checked-in JSON. Two costs are specific to this
# program and decided it: CRDs are cluster-scoped state on a cluster that is
# stateful and must not be rebuilt (a heavy install is a heavy thing to reverse),
# and M6-S2's alert rules would become PrometheusRule objects living in the
# cluster — when the rule since M1-S5 is that what renders is checked in and
# converged, never clicked. `kube-prometheus-stack` is the recorded fallback if
# this route hits its 3-attempt wall; nothing built here depends on the operator.
#
# THE CLUSTER IS STATEFUL AND THIS SCRIPT NEVER TAKES IT DOWN (M6 law 1). It
# publishes NO new host port and edits no kind config: Prometheus and Grafana are
# reached through the 8081 ingress by HOST (`prometheus.local`, `grafana.local`),
# which is what M5-S1's controller bought. The ports 3000 and 9091 in CLAUDE.md's
# port family stay reserved names, not routes, until a PO-sanctioned rebuild.
#
# IT MUTATES THE WIRE EXACTLY ONCE, ON THE FIRST RUN, AND SAYS SO (M6 law 2).
# `controller.metrics.enabled: true` in infra/helm/ingress-nginx/values.yaml
# rolls the ingress controller — the only route into this cluster — for a few
# seconds. That is why this script re-runs `deploy_serving.sh` rather than
# carrying its own copy of the ingress chart pin: ONE file owns the ingress
# values and ONE script owns the ingress release, so there is no pair to drift.
# The honest cost of that decision is ~1 minute of no-op helm upgrades on every
# re-run; the honest cost of the alternative is a second chart-version pin that
# would be right the day it was typed. The rolled controller lands in
# ledgers/deployments.md with its measured unavailability.
#
# SELF-SUFFICIENT (the M1-S5 rule, inherited a fourth time): namespaces, secrets
# and the route are converged here rather than documented as "run X first", so
# the target cannot be defeated by running order.
#
# NO SECRET REACHES A COMMAND LINE. Grafana's admin credential is a Secret that
# scripts/platform_secrets.sh converges from .env; the chart reads it by name.
# Nothing here echoes a value, and there is no `--set` for a password (which `ps`
# can read) and no chart default (which is published).
#
# Usage: scripts/deploy_monitoring.sh             (via `make deploy-monitoring`)
#        DRY_RUN=1 scripts/deploy_monitoring.sh   (prints the plan, mutates
#                                                  NOTHING — helm included, #30)
#        SKIP_ACCEPT=1 …                          (deploy only; the accept checks
#                                                  are also `make monitoring-accept`)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
HELM=(helm --kube-context "$CONTEXT")
DRY_RUN="${DRY_RUN:-0}"
SKIP_ACCEPT="${SKIP_ACCEPT:-0}"
# M4-S2's lesson, sized from a measurement and not from impatience: a 99 MB image
# took 9m49s to pull on this connection, so a 10m timeout failed an install whose
# pods were all healthy.
WAIT_TIMEOUT="${MONITORING_WAIT_TIMEOUT:-20m}"

# --- pins ---------------------------------------------------------------------
# Read LIVE 2026-08-19 with `helm search repo … --versions`. Bump here, in one
# diff, never by letting helm resolve a range.
PROM_REPO_NAME="prometheus-community"
PROM_REPO_URL="https://prometheus-community.github.io/helm-charts"
PROM_CHART="prometheus-community/prometheus"
PROM_CHART_VERSION="29.27.0"            # appVersion v3.14.0
PROM_RELEASE="prometheus"

GRAFANA_REPO_NAME="grafana"
GRAFANA_REPO_URL="https://grafana.github.io/helm-charts"
GRAFANA_CHART="grafana/grafana"
GRAFANA_CHART_VERSION="10.5.15"         # appVersion 12.3.1
GRAFANA_RELEASE="grafana"

NAMESPACE="monitoring"
DASHBOARD_DIR="$REPO_ROOT/analytics/grafana/dashboards"
DASHBOARD_CONFIGMAP="grafana-dashboards-crosstown"

say() { printf '[monitoring] %s\n' "$*"; }

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[monitoring] DRY-RUN would run: %s\n' "$*"
    return 0
  fi
  "$@"
}

# --- 0. preflight -------------------------------------------------------------
say "context $CONTEXT · namespace $NAMESPACE · dry-run=$DRY_RUN"
if ! "${KUBECTL[@]}" get nodes >/dev/null 2>&1; then
  say "FAIL: cannot reach the cluster with context '$CONTEXT'." >&2
  say "      Is Docker Desktop running? (gotcha #34: kubectl's symlink lives in" >&2
  say "      /mnt/wsl/docker-desktop/, which only exists while the daemon does.)" >&2
  exit 1
fi

# --- 1. the route, and its metrics -------------------------------------------
# Re-running the serving platform deploy is what turns `controller.metrics.enabled`
# into a rolled controller exporting nginx_ingress_controller_* — and it is a
# no-op on every subsequent run (proved by pod age, the M4-S2 shape).
say "step 1/6 — the route (deploy_serving.sh; owns the ingress release and its values)"
DRY_RUN="$DRY_RUN" bash "$REPO_ROOT/scripts/deploy_serving.sh"

# --- 2. namespace + secrets ---------------------------------------------------
say "step 2/6 — namespaces and secrets"
run "${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/namespaces.yaml"
if [[ "$DRY_RUN" == "1" ]]; then
  say "DRY-RUN would run: scripts/platform_secrets.sh (converges monitoring/grafana-admin from .env)"
else
  bash "$REPO_ROOT/scripts/platform_secrets.sh"
fi

# --- 3. helm repos ------------------------------------------------------------
say "step 3/6 — helm repos"
run "${HELM[@]}" repo add "$PROM_REPO_NAME" "$PROM_REPO_URL" --force-update
run "${HELM[@]}" repo add "$GRAFANA_REPO_NAME" "$GRAFANA_REPO_URL" --force-update
run "${HELM[@]}" repo update "$PROM_REPO_NAME" "$GRAFANA_REPO_NAME"

# --- 4. prometheus ------------------------------------------------------------
say "step 4/6 — prometheus $PROM_CHART_VERSION (+ alertmanager, kube-state-metrics)"
run "${HELM[@]}" upgrade --install "$PROM_RELEASE" "$PROM_CHART" \
  --version "$PROM_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values "$REPO_ROOT/infra/helm/monitoring/prometheus-values.yaml" \
  --wait --timeout "$WAIT_TIMEOUT"

# --- 5. the dashboards, from checked-in JSON ---------------------------------
# The ConfigMap is BUILT FROM THE FILES every run, so the board in the cluster is
# the board in git — the Metabase-boards property (M1-S5) reached by a different
# mechanism. `create --dry-run=client | apply` is the idempotent form: it
# converges an existing ConfigMap instead of failing, and it never deletes.
say "step 5/6 — dashboards from $(cd "$DASHBOARD_DIR" && ls *.json | tr '\n' ' ')"
if [[ "$DRY_RUN" == "1" ]]; then
  say "DRY-RUN would build configmap/$DASHBOARD_CONFIGMAP from $DASHBOARD_DIR/*.json"
else
  cm_args=()
  for f in "$DASHBOARD_DIR"/*.json; do cm_args+=(--from-file="$(basename "$f")=$f"); done
  "${KUBECTL[@]}" -n "$NAMESPACE" create configmap "$DASHBOARD_CONFIGMAP" \
    "${cm_args[@]}" --dry-run=client -o yaml \
    | "${KUBECTL[@]}" label --local -f - grafana_dashboard=1 -o yaml \
    | "${KUBECTL[@]}" apply -f - >/dev/null
  say "ok  configmap/$DASHBOARD_CONFIGMAP labelled grafana_dashboard=1"
fi

# --- 6. grafana ---------------------------------------------------------------
say "step 6/6 — grafana $GRAFANA_CHART_VERSION"
run "${HELM[@]}" upgrade --install "$GRAFANA_RELEASE" "$GRAFANA_CHART" \
  --version "$GRAFANA_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values "$REPO_ROOT/infra/helm/monitoring/grafana-values.yaml" \
  --wait --timeout "$WAIT_TIMEOUT"

if [[ "$DRY_RUN" == "1" ]]; then
  say "DRY-RUN complete — nothing was installed, nothing was upgraded, no Secret was read."
  exit 0
fi

"${KUBECTL[@]}" -n "$NAMESPACE" get pods -o wide
"${HELM[@]}" -n "$NAMESPACE" list

# --- accept -------------------------------------------------------------------
# The accept check is a MEASUREMENT, not a target list (gotcha #59): a scrape
# target that is `up` proves Prometheus can reach a port, and proves nothing at
# all about whether a rider's request becomes a number. So the check sends one
# real quote and requires the counter to move.
if [[ "$SKIP_ACCEPT" == "1" ]]; then
  say "SKIP_ACCEPT=1 — deployed, NOT accepted. Run `make monitoring-accept`."
  exit 0
fi
say "accept — scrape targets, then one real request through the whole pipeline"
uv run --directory "$REPO_ROOT" python "$REPO_ROOT/scripts/monitoring_accept.py"
