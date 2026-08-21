#!/usr/bin/env python
"""Plant one wrong-but-valid value in the ONLINE store, and put it back. (M8-S4)

Runs INSIDE the quarantine (imports `feast` and `redis`, never `taxi_mlops`).
Driven by `scripts/feast_online_parity_redteam.sh`, which is the thing that
judges; this module only mutates and restores.

**What it plants, and why that shape.** It copies the serialized feature bytes of
one OD pair onto ANOTHER OD pair's Redis key. The result is a store that returns
a real, well-formed, plausible `od_median_duration_min` for a pair it does not
belong to — a wrong-stamp/wrong-row materialization is exactly what this looks
like from the outside, and it is the one failure the offline store cannot detect
for itself. It is not a corruption: every byte written was written by Feast, the
protobuf parses, the dtype is right and nothing logs an error. A drill that
planted garbage would prove the parser works, not that the table does.

**The target is row 92 of the declared set** — the OD pair whose median moves most
across its point-in-time windows (`docs/feast_online_m8.md` §3). That is the row
declared in advance as the one where a wrong value shows up by the largest
margin, so the drill plants against the hazard the row set already names rather
than against a row chosen after the fact.

**Restoring is byte-exact and is checked by the caller.** The target hash is read
whole before anything is written and written back field by field afterwards, with
any field the plant introduced removed. The caller compares a sha256 of the hash
before and after, which is the M4-S5/M6-S5 restore discipline applied to a store
instead of to a JSON file.

It touches ONE Redis hash. It moves no alias, mints no run, deploys nothing,
re-materializes nothing, and writes no file except the save-file it is told to.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import redis
from feast.infra.key_encoding_utils import serialize_entity_key
from feast.protos.feast.types.EntityKey_pb2 import EntityKey
from feast.protos.feast.types.Value_pb2 import Value

PROJECT = "crosstown_eta"
SERIALIZATION_VERSION = 3


def _key(pu: int, do: int) -> bytes:
    """The Redis key Feast writes an OD pair's features under.

    Built with Feast's OWN encoder rather than by reimplementing the layout: the
    encoding is a pinned contract (`entity_key_serialization_version: 3` in
    `feature_store.yaml`), and a red team that hand-rolled it would be testing its
    own guess about the store rather than the store.
    """
    entity_key = EntityKey(
        join_keys=["PULocationID", "DOLocationID"],
        entity_values=[Value(int64_val=pu), Value(int64_val=do)],
    )
    return serialize_entity_key(
        entity_key, entity_key_serialization_version=SERIALIZATION_VERSION
    ) + PROJECT.encode("utf8")


def _digest(mapping: dict[bytes, bytes]) -> str:
    hasher = hashlib.sha256()
    for field in sorted(mapping):
        hasher.update(field)
        hasher.update(mapping[field])
    return hasher.hexdigest()


def _client() -> redis.Redis:
    connection = os.environ.get("FEAST_REDIS_CONNECTION", "")
    if not connection or "${" in connection:
        raise SystemExit(
            "[redteam] FEAST_REDIS_CONNECTION is unset — the online store's address is "
            "deliberately not a committed constant (ADR-012)."
        )
    host, _, port = connection.partition(":")
    return redis.Redis(host=host, port=int(port or 6379))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("plant", "restore", "digest"))
    parser.add_argument("--target", required=True, help="PU,DO of the pair to tamper with")
    parser.add_argument("--donor", help="PU,DO of the pair whose bytes are copied (plant only)")
    parser.add_argument("--save", required=True, help="where the untampered hash is kept")
    args = parser.parse_args(argv)

    client = _client()
    target_pu, target_do = (int(part) for part in args.target.split(","))
    target = _key(target_pu, target_do)
    save = Path(args.save)

    if args.mode == "digest":
        print(_digest(client.hgetall(target)))
        return 0

    if args.mode == "plant":
        donor_pu, donor_do = (int(part) for part in args.donor.split(","))
        donor = _key(donor_pu, donor_do)
        before = client.hgetall(target)
        donor_fields = client.hgetall(donor)
        if not before or not donor_fields:
            raise SystemExit(
                f"[redteam] the store has no hash for {args.target} or {args.donor}. "
                "Materialize first: make feast-materialize"
            )
        save.write_text(
            json.dumps(
                {
                    "target": args.target,
                    "donor": args.donor,
                    "digest_before": _digest(before),
                    "fields": {
                        field.hex(): value.hex() for field, value in sorted(before.items())
                    },
                },
                indent=2,
            )
            + "\n"
        )
        client.hset(target, mapping=donor_fields)
        after = client.hgetall(target)
        print(f"[redteam] planted {args.donor}'s bytes onto {args.target}")
        print(f"[redteam]   digest before {_digest(before)}")
        print(f"[redteam]   digest after  {_digest(after)}")
        if _digest(before) == _digest(after):
            raise SystemExit(
                "[redteam] the plant changed NOTHING — the donor's bytes are identical to "
                "the target's. A drill that tampers with nothing goes green and proves "
                "nothing; choose a donor whose value differs."
            )
        return 0

    saved = json.loads(save.read_text())
    fields = {bytes.fromhex(field): bytes.fromhex(value) for field, value in saved["fields"].items()}
    current = client.hgetall(target)
    for field in current:
        if field not in fields:
            client.hdel(target, field)
    client.hset(target, mapping=fields)
    restored = _digest(client.hgetall(target))
    print(f"[redteam] restored {args.target}")
    print(f"[redteam]   digest before plant {saved['digest_before']}")
    print(f"[redteam]   digest after restore {restored}")
    if restored != saved["digest_before"]:
        print("[redteam] FAIL — the restore is not byte-identical", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
