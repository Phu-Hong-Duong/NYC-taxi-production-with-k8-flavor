#!/usr/bin/env python
"""Read the applied Feast registry back and write it down. Runs INSIDE the quarantine.

M8-S2. This is the deploy-scripts idiom this program has used since M5-S1: read
the state back off the thing that holds it, never off the file that was
submitted (`deploy_serving.sh` reads KServe's mode out of the live ConfigMap;
`retrain_schedule.sh` reads the triggers off the control plane). A catalog page
that agreed with `definitions.py` would only be proving that two files in the
same commit say the same thing; this record is what the REGISTRY says after
`feast apply` has read the definitions, parsed them and stored its own copy.

It runs on the far side of the wall — this file imports `feast` and must not
import `taxi_mlops` — and it writes a plain JSON record that the project's own
tests read to assert the catalog and the registry agree on every verdict.

A READER: no apply, no materialize, no write to any source.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
from feast import FeatureStore

REPO_DIR = Path(__file__).resolve().parents[1] / "infra" / "feast" / "feature_repo"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="automation/runs/m8-feast/registry.json")
    args = parser.parse_args(argv)

    store = FeatureStore(repo_path=str(REPO_DIR))
    views = []
    for view in sorted(store.list_feature_views(), key=lambda v: v.name):
        path = Path(view.batch_source.path)
        # Row counts come from the parquet METADATA, not from a read: the point
        # is what the store is pointed at, and a 248k-row scan to learn a number
        # the footer already holds would make a reader expensive for nothing.
        rows = pq.ParquetFile(path).metadata.num_rows if path.exists() else None
        stamps = None
        if path.exists():
            column = pq.read_table(path, columns=["event_timestamp"])["event_timestamp"]
            distinct = sorted({str(v) for v in column.to_pylist()})
            stamps = distinct if len(distinct) <= 12 else [distinct[0], "...", distinct[-1]]
        views.append(
            {
                "name": view.name,
                "entities": list(view.entities),
                "join_keys": [k for e in view.entity_columns for k in [e.name]],
                "fields": [{"name": f.name, "dtype": str(f.dtype)} for f in view.features],
                "ttl_seconds": int(view.ttl.total_seconds()) if view.ttl else None,
                "online": bool(view.online),
                "source": path.name,
                "source_rows": rows,
                "event_timestamps": stamps,
                "tags": dict(view.tags or {}),
            }
        )

    entities = [
        {"name": e.name, "join_key": e.join_key, "value_type": str(e.value_type)}
        for e in sorted(store.list_entities(), key=lambda e: e.name)
    ]

    record = {
        "story": "M8-S2",
        "written_at": datetime.now(UTC).isoformat(),
        "read_from": "the applied Feast registry, never from definitions.py",
        "project": store.project,
        "feast_version": __import__("feast").__version__,
        "entities": entities,
        "feature_views": views,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")

    print(f"[registry] project {record['project']} on feast {record['feast_version']}")
    for entity in entities:
        print(f"[registry]   entity {entity['name']:<16s} join key {entity['join_key']}")
    for view in views:
        print(
            f"[registry]   view   {view['name']:<22s} {len(view['fields'])} field(s), "
            f"{view['source_rows']:>7,} row(s), ttl={view['ttl_seconds']}, "
            f"verdict={view['tags'].get('verdict', '(none)')}"
        )
    print(f"[registry] record: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
