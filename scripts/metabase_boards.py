#!/usr/bin/env python3
"""Provision Metabase's boards from checked-in JSON — and verify them the same way.

WHY JSON IN GIT AND NOT CLICKS IN A BROWSER. A dashboard built by hand exists in
exactly one place: the app-db of the machine it was built on. It cannot be
reviewed in a PR, it cannot be rebuilt after `make destroy`, and nobody can say
what changed when a number moves. `docs/prior_art.md` records this as an ADOPT
(dashboards provisioned from checked-in JSON), and M1-S5 is where it lands: the
boards live in `analytics/metabase/boards/*.json`, this script converges Metabase
onto them, and the same script re-reads the live instance to check the result.

WHY THE STDLIB AND NOT `requests`. This is a $0, every-version-pinned program;
adding an HTTP dependency to the runtime graph to POST seventeen JSON documents
would be a dependency we then have to pin, scan and upgrade forever.

IDEMPOTENCE IS BY NAME. Cards and dashboards are matched on their `name`, then
updated in place (PUT) rather than recreated — so a second run leaves the same
ids, and a card someone has since put on another dashboard does not silently
become an orphan. Nothing here archives or deletes: this script may add and
update, and that asymmetry is deliberate (the same rule postgres_databases.sh
follows — destroying is `make destroy`'s job, out loud).

No credential is ever printed, including in an error path.

Usage:
    python scripts/metabase_boards.py            # converge (deploy_metabase.sh)
    python scripts/metabase_boards.py --verify   # read-only check (verify_m1.sh)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARDS_DIR = REPO_ROOT / "analytics" / "metabase" / "boards"
ENV_FILE = Path(os.environ.get("ENV_FILE", REPO_ROOT / ".env"))
BASE_URL = os.environ.get("METABASE_URL", "http://localhost:3030").rstrip("/")

# The warehouse connection Metabase reads. `marts` is the database D-002 created
# and `scripts/marts.sh` publishes into; Metabase connects as the `marts` role,
# never as the Postgres superuser.
MARTS_DB_NAME = "marts"
MARTS_DB_HOST = "postgres.platform.svc.cluster.local"
MARTS_DB_PORT = 5432


class MetabaseError(RuntimeError):
    """A failure that names what was being attempted, never what was sent."""


# --------------------------------------------------------------------- env ---
def load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        raise MetabaseError(f"no {ENV_FILE} — scripts/platform_secrets.sh owns it")
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    needed = [
        "METABASE_ADMIN_EMAIL",
        "METABASE_ADMIN_PASSWORD",
        "MARTS_DB_USER",
        "MARTS_DB_PASSWORD",
    ]
    missing = [k for k in needed if not env.get(k)]
    if missing:
        raise MetabaseError(
            f"{ENV_FILE} has no value for: {', '.join(missing)} "
            "— run scripts/platform_secrets.sh (it appends new consumers' keys)"
        )
    return env


# --------------------------------------------------------------------- http --
class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.session_id: str | None = None

    def request(self, method: str, path: str, body: Any = None, *, expect_json: bool = True) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.session_id:
            req.add_header("X-Metabase-Session", self.session_id)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:  # noqa: PERF203 - one call, one handler
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise MetabaseError(f"{method} {path} -> HTTP {exc.code}: {detail}") from None
        except urllib.error.URLError as exc:
            raise MetabaseError(f"{method} {path} -> unreachable: {exc.reason}") from None
        except OSError as exc:
            # ConnectionResetError and friends are NOT URLError — they come
            # straight up from the socket. Found by red-teaming verify-m1 with
            # `kubectl scale deployment/metabase --replicas=0`: the node port
            # still accepts and then resets, and this script answered with a
            # 30-line Python traceback instead of a sentence. Worse, the raw
            # exception blew past wait_for_health's retry loop, so a service that
            # was merely restarting failed instantly instead of being waited for.
            # A refusal that is not typed is a refusal nobody can act on.
            raise MetabaseError(f"{method} {path} -> connection failed: {exc}") from None
        if not expect_json or not raw:
            return None
        return json.loads(raw)

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.request("POST", path, body)

    def put(self, path: str, body: Any) -> Any:
        return self.request("PUT", path, body)


def wait_for_health(client: Client, timeout_s: int = 600) -> None:
    """Wait for the instance to answer — patiently when deploying, briefly when checking.

    These are two different questions and they deserve two different budgets.
    While CONVERGING (after a deploy), Metabase may still be migrating its app-db
    and ten minutes of patience is correct. While VERIFYING, the service is
    supposed to be up already: a gate that takes ten minutes to report a dead
    service is a gate nobody waits for, and "it might come back" is not a thing a
    gate is allowed to assume.
    """
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            client.get("/api/health")
            return
        except MetabaseError as exc:
            last = str(exc)
            time.sleep(5)
    raise MetabaseError(f"{BASE_URL}/api/health never answered within {timeout_s}s: {last}")


# -------------------------------------------------------------------- auth ---
def authenticate(client: Client, env: dict[str, str]) -> None:
    """Log in, running first-time setup if this instance has never been set up.

    The setup token exists exactly once per app-db. After M1-S5's cluster rebuild
    the `metabase` database is empty, so this path runs; on every later run the
    token is absent and we log in instead. Both are normal.
    """
    props = client.get("/api/session/properties")
    token = props.get("setup-token")
    if token:
        result = client.post(
            "/api/setup",
            {
                "token": token,
                "user": {
                    "first_name": "Crosstown",
                    "last_name": "MLOps",
                    "email": env["METABASE_ADMIN_EMAIL"],
                    "password": env["METABASE_ADMIN_PASSWORD"],
                    "site_name": "Crosstown Mobility",
                },
                "prefs": {
                    "site_name": "Crosstown Mobility",
                    # Second half of the manifest's MB_ANON_TRACKING_ENABLED=false.
                    # The setup call writes its own preference and would otherwise
                    # turn tracking back on at the moment of first login
                    # (gotcha #32: an opt-out default is a violation that installs
                    # itself).
                    "allow_tracking": False,
                },
            },
        )
        client.session_id = result["id"]
        print("[boards] first-time setup completed (admin from .env; tracking off)")
        return

    result = client.post(
        "/api/session",
        {"username": env["METABASE_ADMIN_EMAIL"], "password": env["METABASE_ADMIN_PASSWORD"]},
    )
    client.session_id = result["id"]
    print("[boards] authenticated as the .env admin (instance was already set up)")


# ---------------------------------------------------------------- database ---
def _database_list(client: Client) -> list[dict[str, Any]]:
    payload = client.get("/api/database")
    # The endpoint returned a bare list in old versions and {"data": [...]} in
    # current ones. Accept both rather than pin the board layer to one shape.
    return payload["data"] if isinstance(payload, dict) else payload


def ensure_marts_database(client: Client, env: dict[str, str]) -> int:
    details = {
        "host": MARTS_DB_HOST,
        "port": MARTS_DB_PORT,
        "dbname": MARTS_DB_NAME,
        "user": env["MARTS_DB_USER"],
        "password": env["MARTS_DB_PASSWORD"],
        "ssl": False,
        "tunnel-enabled": False,
    }
    for db in _database_list(client):
        if db.get("name") == MARTS_DB_NAME:
            client.put(
                f"/api/database/{db['id']}",
                {"name": MARTS_DB_NAME, "engine": "postgres", "details": details},
            )
            print(f"[boards] ok  database '{MARTS_DB_NAME}' (id {db['id']}) — connection converged")
            return int(db["id"])
    created = client.post(
        "/api/database",
        {"name": MARTS_DB_NAME, "engine": "postgres", "details": details, "is_full_sync": True},
    )
    print(f"[boards] ok  database '{MARTS_DB_NAME}' (id {created['id']}) — created")
    return int(created["id"])


# ------------------------------------------------------------------- cards ---
def _card_index(client: Client) -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in client.get("/api/card") if not c.get("archived")}


def card_payload(spec: dict[str, Any], database_id: int) -> dict[str, Any]:
    return {
        "name": spec["name"],
        "display": spec["display"],
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": spec["sql"], "template-tags": {}},
        },
        "visualization_settings": spec.get("visualization_settings", {}),
        "collection_id": None,
    }


def upsert_cards(
    client: Client, board: dict[str, Any], database_id: int, existing: dict[str, dict[str, Any]]
) -> list[tuple[dict[str, Any], int]]:
    out: list[tuple[dict[str, Any], int]] = []
    for spec in board["cards"]:
        payload = card_payload(spec, database_id)
        found = existing.get(spec["name"])
        if found:
            client.put(f"/api/card/{found['id']}", payload)
            card_id = int(found["id"])
            verb = "updated"
        else:
            card_id = int(client.post("/api/card", payload)["id"])
            verb = "created"
        print(f"[boards]     card {verb}: {spec['name']}  ({spec['kpi']}, {spec['display']})")
        out.append((spec, card_id))
    return out


# -------------------------------------------------------------- dashboards ---
def upsert_dashboard(
    client: Client, board: dict[str, Any], cards: list[tuple[dict[str, Any], int]]
) -> int:
    existing = {d["name"]: d for d in client.get("/api/dashboard") if not d.get("archived")}
    found = existing.get(board["name"])
    if found:
        dash_id = int(found["id"])
        client.put(
            f"/api/dashboard/{dash_id}",
            {"name": board["name"], "description": board["description"]},
        )
        verb = "updated"
    else:
        dash_id = int(
            client.post(
                "/api/dashboard", {"name": board["name"], "description": board["description"]}
            )["id"]
        )
        verb = "created"

    # Re-read so an existing dashboard keeps its dashcard ids across runs: a
    # dashcard replaced by a fresh negative id loses any per-placement setting.
    live = client.get(f"/api/dashboard/{dash_id}")
    by_card_id = {dc["card_id"]: dc for dc in live.get("dashcards", [])}
    dashcards = []
    for index, (spec, card_id) in enumerate(cards):
        prior = by_card_id.get(card_id)
        dashcards.append(
            {
                "id": prior["id"] if prior else -(index + 1),
                "card_id": card_id,
                "row": spec["row"],
                "col": spec["col"],
                "size_x": spec["size_x"],
                "size_y": spec["size_y"],
                "parameter_mappings": [],
                "visualization_settings": {},
            }
        )
    client.put(f"/api/dashboard/{dash_id}", {"dashcards": dashcards})
    print(
        f"[boards] ok  dashboard {verb}: '{board['name']}' (id {dash_id}) — {len(dashcards)} cards"
    )
    return dash_id


# ------------------------------------------------------------------ boards ---
def load_boards() -> list[dict[str, Any]]:
    files = sorted(BOARDS_DIR.glob("*.json"))
    if not files:
        raise MetabaseError(f"no board definitions under {BOARDS_DIR}")
    return [json.loads(f.read_text()) for f in files]


def converge(client: Client, env: dict[str, str]) -> None:
    database_id = ensure_marts_database(client, env)
    existing_cards = _card_index(client)
    for board in load_boards():
        print(f"[boards] board '{board['name']}' ({len(board['cards'])} cards)")
        cards = upsert_cards(client, board, database_id, existing_cards)
        upsert_dashboard(client, board, cards)


def verify(client: Client) -> int:
    """Read the LIVE instance back and check what the gate actually asks for.

    Deliberately not "the POST returned 200 earlier": that is a claim about a
    past request. This asks the running Metabase what it holds now, and runs one
    card's query through Metabase's own engine so a card that renders an error
    cannot pass as a card that renders.
    """
    failures = 0

    def ok(msg: str) -> None:
        print(f"  \033[32mok  \033[0m {msg}")

    def bad(msg: str) -> None:
        nonlocal failures
        print(f"  \033[31mFAIL\033[0m {msg}", file=sys.stderr)
        failures += 1

    databases = {db["name"]: db for db in _database_list(client)}
    if MARTS_DB_NAME in databases:
        ok(f"Metabase holds a connection to the '{MARTS_DB_NAME}' warehouse")
    else:
        bad(f"no Metabase database connection named '{MARTS_DB_NAME}' (found: {sorted(databases)})")
        return failures

    marts_db_id = int(databases[MARTS_DB_NAME]["id"])
    live_dashboards = {d["name"]: d for d in client.get("/api/dashboard") if not d.get("archived")}

    for board in load_boards():
        name = board["name"]
        if name not in live_dashboards:
            bad(f"dashboard '{name}' is absent from the live instance")
            continue
        detail = client.get(f"/api/dashboard/{live_dashboards[name]['id']}")
        dashcards = detail.get("dashcards", [])
        if len(dashcards) != len(board["cards"]):
            want = len(board["cards"])
            bad(f"dashboard '{name}' has {len(dashcards)} cards, the definition has {want}")
            continue
        ok(f"dashboard '{name}' exists with {len(dashcards)} cards")

        wrong_db = [
            dc["card"]["name"]
            for dc in dashcards
            if dc.get("card", {}).get("database_id") not in (marts_db_id, None)
        ]
        if wrong_db:
            bad(f"dashboard '{name}' has cards not querying the marts warehouse: {wrong_db}")
        else:
            ok(f"dashboard '{name}': every card queries the '{MARTS_DB_NAME}' warehouse")

        # gotcha #15, enforced where a human would break it: a BI card computing
        # a model-quality metric from a warehouse table would be a leaderboard
        # wearing a KPI's name.
        offenders = [
            dc["card"]["name"]
            for dc in dashcards
            if "KPI-09" in dc.get("card", {}).get("name", "")
            or "KPI-10" in dc.get("card", {}).get("name", "")
        ]
        if offenders:
            bad(f"dashboard '{name}' renders KPI-09/KPI-10 — no mart may hold them: {offenders}")
        else:
            ok(f"dashboard '{name}': no card claims KPI-09/KPI-10 (gotcha #15)")

        # Run the first card through Metabase's own query engine. A card whose
        # SQL is wrong looks identical to a working one until something asks it.
        probe = dashcards[0]["card"]
        result = client.post(f"/api/card/{probe['id']}/query", {"ignore_cache": True})
        status = result.get("status")
        rows = result.get("data", {}).get("rows", [])
        if status == "completed" and rows:
            ok(f"dashboard '{name}': card '{probe['name']}' RAN and returned {len(rows)} row(s)")
        else:
            bad(f"dashboard '{name}': card '{probe['name']}' status={status}, rows={len(rows)}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="read-only: check the live boards, change nothing"
    )
    args = parser.parse_args()

    try:
        env = load_env()
        client = Client(BASE_URL)
        wait_for_health(client, timeout_s=60 if args.verify else 600)
        authenticate(client, env)
        if args.verify:
            return 1 if verify(client) else 0
        converge(client, env)
    except MetabaseError as exc:
        print(f"[boards] FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"[boards] done — open {BASE_URL} (credentials: .env, never printed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
