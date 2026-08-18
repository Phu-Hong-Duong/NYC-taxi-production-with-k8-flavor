#!/usr/bin/env bash
# postgres_databases.sh — the ONE recipe that creates databases and roles in the
# one Postgres, and the answer to debt D-002.
#
# THE FAILURE THIS EXISTS TO PREVENT (D-002, raised M0-S3):
# `docker-entrypoint-initdb.d` runs exactly once, on an EMPTY data directory.
# The `mlflow` database and role arrived that way (the ConfigMap in
# infra/manifests/postgres.yaml). Adding a second database by editing that
# ConfigMap on a volume that already exists is a SILENT no-op: `kubectl apply`
# reports success, the manifest says the database is there, and it is not. The
# error surfaces hours later as a connection refused by a database nobody
# created. This script is the path that works on an existing volume.
#
# WHY THIS AND NOT A MIGRATION JOB (craft call, M1-S4). A Job would run
# in-cluster, which is architecturally tidier, but Jobs are immutable: re-running
# `make deploy-platform` means delete-then-recreate, and a half-deleted Job is a
# worse failure than the one being fixed. This script is invoked BY the deploy
# recipe (never by hand — MLOps charter refuses hand-typed psql), reaches the
# server over `kubectl exec` (no port is published: CLAUDE.md's port family
# annotates 5432 "in-cluster only"), and converges. Undo is one `git revert`;
# the Job form stays available if M4 ever needs this to run without a kubeconfig.
#
# IDEMPOTENCE IS BY CONSTRUCTION, NOT BY LUCK. Every statement is guarded:
#   role     — created only if absent, then ALTER'd to the .env password every
#              run, so .env stays the single source of truth (same contract as
#              scripts/platform_secrets.sh).
#   database — created only if absent. NEVER dropped, never recreated: this
#              script may not be able to destroy data. Destroying is `make
#              destroy`'s job and it says so out loud.
# `mlflow` is deliberately IN the list even though initdb already made it. The
# recipe describes the desired state of the server; initdb is then an
# optimisation for the empty-volume case rather than a second, divergent source
# of truth. Its presence is also the free proof that the guards really are
# no-ops — see the "already present" lines it prints on every run.
#
# No secret is ever echoed, and no password is passed in argv (it would show up
# in `ps` inside the pod and in a kubectl audit log): the credentials reach psql
# on stdin only, as \set variables.
#
# Usage: scripts/postgres_databases.sh          (called by deploy_platform.sh)
#        DRY_RUN=1 scripts/postgres_databases.sh   (print the plan, touch nothing)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
NAMESPACE="${POSTGRES_NAMESPACE:-platform}"
POD="${POSTGRES_POD:-postgres-0}"
KUBECTL=(kubectl --context "${KUBE_CONTEXT:-kind-mlops-taxi}")
DRY_RUN="${DRY_RUN:-0}"

# The desired state of the server: one line per database, "db:role:passwordkey".
# A new consumer adds a line here and nothing else — M1-S5 added `metabase` and
# that claim held: one line here, one ADDITIVE entry in platform_secrets.sh.
# M3-S4 added `optuna` (the sniper's study storage) and it held a THIRD time.
# `optuna` is the first consumer that is NOT a pod: the study driver runs on the
# host, so this database gets a role and no Kubernetes Secret. The credential
# still lives only in .env; scripts/optuna_storage.py reads it from there and
# builds the DSN in memory (configs/tuning.yaml says `storage: postgres` and
# carries no DSN, by its own law).
# M4-S2 added `flyte` and it held a FOURTH time. Worth recording precisely: the
# M4 kickoff budgeted TWO databases here ("flyteadmin/datacatalog … fourth and
# fifth consumers"), which is the Flyte 1.x shape. The 2.x unified binary reads
# a single `runs.database`, so it is one consumer, not two. One line, as always.
DATABASES=(
  "mlflow:${MLFLOW_DB_USER:-mlflow}:MLFLOW_DB_PASSWORD"
  "marts:${MARTS_DB_USER:-marts}:MARTS_DB_PASSWORD"
  "metabase:${METABASE_DB_USER:-metabase}:METABASE_DB_PASSWORD"
  "optuna:${OPTUNA_DB_USER:-optuna}:OPTUNA_DB_PASSWORD"
  "flyte:${FLYTE_DB_USER:-flyte}:FLYTE_DB_PASSWORD"
)

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[pg-db] FAIL: no $ENV_FILE — run scripts/platform_secrets.sh first (it owns .env)" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

# Re-expand now that .env is loaded (the defaults above cover a stripped .env).
DATABASES=(
  "mlflow:${MLFLOW_DB_USER:-mlflow}:MLFLOW_DB_PASSWORD"
  "marts:${MARTS_DB_USER:-marts}:MARTS_DB_PASSWORD"
  "metabase:${METABASE_DB_USER:-metabase}:METABASE_DB_PASSWORD"
  "optuna:${OPTUNA_DB_USER:-optuna}:OPTUNA_DB_PASSWORD"
  "flyte:${FLYTE_DB_USER:-flyte}:FLYTE_DB_PASSWORD"
)

psql_admin() {
  # -v ON_ERROR_STOP=1: a failed statement must fail the script, not scroll by.
  "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
    psql -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"
}

echo "== postgres databases (D-002: the post-initdb path) =="
for entry in "${DATABASES[@]}"; do
  IFS=":" read -r db role pwkey <<<"$entry"
  password="${!pwkey:-}"
  if [[ -z "$password" ]]; then
    echo "[pg-db] FAIL: $ENV_FILE has no value for $pwkey (needed by database '$db')" >&2
    exit 1
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[pg-db] DRY_RUN — WOULD converge role '$role' and database '$db' (password from $pwkey)"
    continue
  fi

  # State BEFORE, so the log shows which case each run actually took. This is
  # the line that proves the existing-volume path: 'marts' reads absent on the
  # first run of a volume that initdb finished with months ago.
  before=$(psql_admin -tAc \
    "SELECT (SELECT count(*) FROM pg_roles WHERE rolname = '$role')
          || '/' ||
            (SELECT count(*) FROM pg_database WHERE datname = '$db')")
  case "$before" in
    0/0) state="role absent, database absent" ;;
    1/0) state="role present, database absent" ;;
    1/1) state="role present, database present" ;;
    *)   state="unexpected ($before)" ;;
  esac
  echo "[pg-db] $db: before = $state"

  # \gexec runs the string a query RETURNS, which is how CREATE DATABASE — a
  # statement that cannot appear in a DO block or a transaction — gets a WHERE
  # NOT EXISTS guard. format()'s %I/%L quote the identifier and the literal.
  psql_admin >/dev/null <<SQL
\set role '$role'
\set db '$db'
\set pw '$password'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')\gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'role', :'pw')\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db')\gexec
SQL

  after=$(psql_admin -tAc \
    "SELECT d.datname || ' owner=' || pg_get_userbyid(d.datdba)
       FROM pg_database d WHERE d.datname = '$db'")
  if [[ -z "$after" ]]; then
    echo "[pg-db] FAIL: database '$db' still absent after converge" >&2
    exit 1
  fi
  echo "[pg-db] ok  $after"
done

echo "[pg-db] ${#DATABASES[@]} database(s) converged (no password printed, by design)"
