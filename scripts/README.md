# scripts/ — the shell behind the Makefile. Nothing here is meant to be run
# directly by a human: `make` is the interface, these are its implementation.
# They are committed NON-executable on purpose (gotcha #25): a script that is
# only ever invoked as `bash scripts/x.sh` cannot be broken by a lost exec bit
# in a fresh clone. The one exception, automation/next_session.sh, is 100755
# because it IS called directly.
#
# Live (M0):
#   cluster.sh            make cluster-up | cluster-down | destroy   (S2)
#   port_precheck.sh      make ports — gotcha #10, refuses a busy family port (S2)
#   deploy_platform.sh    make deploy-platform — MinIO + Postgres + MLflow      (S3)
#   platform_secrets.sh   .env -> Kubernetes Secrets; generates .env once       (S3)
#   verify_m0.sh          make verify-m0 — the M0 gate, 18 sub-checks           (S3)
#   check_charters.sh     "every charter carries >= 3 refusals", standalone so
#                         it can be unit-tested against a deliberately short one (S3)
#
# Written when first needed:
#   port_forwards.sh (only if a service ever needs a route the kind config
#   cannot declare — M0-S3 chose declared nodePorts instead) · seed_data.sh (M1)
#   · fix_stuck_namespace.sh (on first occurrence, per gotcha #12) ·
#   load_test.sh (M4).
