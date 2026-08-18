"""Can a pod built from the task image reach the one Postgres? (M4-S5 probe)

This answers the single fact leg 2 of M4-S5 — D-003's marts tail task — has to be
designed around, and it is a fact this repo could not have assumed. `make marts`
publishes over `kubectl exec` into the postgres pod, on purpose: nothing of ours
publishes 5432 on the host (CLAUDE.md's port family annotates it "in-cluster
only"), so the host has no TCP route to it at all. A TASK POD cannot use that
transport — it has neither kubectl nor a kubeconfig, and giving it one would put
cluster credentials in a pipeline stage.

In-cluster the service name resolves and the port is open, so a pod should be able
to connect directly with psycopg — which the image already carries, as Optuna's
driver (M3-S4). "Should" is not measured, so this measures it, in one throwaway
pod built from the actual task image, and prints the numbers D-003 needs anyway.

It is a PROBE: it opens a connection, reads three values and exits. It creates no
table, writes no row and leaves no pod behind (`--rm`).

    uv run python scripts/marts_reach_probe.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    env: dict[str, str] = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()

    image = json.loads((REPO / "automation/runs/m4-image/image.json").read_text())["image_ref"]

    # The DSN carries the plain `postgresql://` scheme deliberately: the
    # `postgresql+psycopg://` spelling this repo pins everywhere else is
    # SQLAlchemy's (M3-S4 pinned it because SQLAlchemy reads a bare scheme as
    # psycopg2). This is psycopg's own connect, which takes the plain one.
    #
    # The credentials arrive as env vars, never on the command line — a pod spec
    # is readable by anything that can `kubectl get pod -o yaml`.
    probe = "\n".join(
        [
            "import os, psycopg",
            "dsn = 'postgresql://%s:%s@postgres.platform.svc.cluster.local:5432/marts' % (",
            "    os.environ['PROBE_PGUSER'], os.environ['PROBE_PGPASSWORD'])",
            "with psycopg.connect(dsn) as conn:",
            "    who = conn.execute('select current_user, current_database()').fetchone()",
            "    size = conn.execute(",
            "        \"select pg_size_pretty(pg_total_relation_size('marts.trips_clean'))\"",
            "    ).fetchone()",
            "    kpis = conn.execute('select count(*) from marts.monthly_kpis').fetchone()",
            "print('PROBE-OK', who, 'trips_clean total size', size[0], 'monthly_kpis rows', kpis[0])",
        ]
    )

    overrides = {
        "spec": {
            "containers": [
                {
                    "name": "marts-reach-probe",
                    "image": image,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["python", "-c", probe],
                    "env": [
                        {"name": "PROBE_PGUSER", "value": env["MARTS_DB_USER"]},
                        {"name": "PROBE_PGPASSWORD", "value": env["MARTS_DB_PASSWORD"]},
                    ],
                }
            ],
            "restartPolicy": "Never",
        }
    }

    result = subprocess.run(
        [
            "kubectl", "-n", "flyte", "run", "marts-reach-probe", "--rm", "--attach",
            "--restart=Never", "--image", image, "--overrides", json.dumps(overrides),
            "--command", "--", "python", "-c", probe,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return 0 if "PROBE-OK" in result.stdout else 1


if __name__ == "__main__":  # pragma: no cover — needs a cluster
    raise SystemExit(main())
