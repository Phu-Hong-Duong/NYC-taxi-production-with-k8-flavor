#!/usr/bin/env bash
# verify_m7.sh — the M7 gate, executable. BLUEPRINT §9/M7, quoted:
#
#   "M7 — Drift, batch inference, & the retrain loop (SRE A; MLE R; DA R for the
#    memo). v1's M6 (Evidently -> Pushgateway -> alert; COVID-month statistical
#    drift vs 2025 schema-drift refusal, distinguishable; scheduled Flyte
#    retrain landing a challenger) + batch inference as a product: the scheduled
#    monthly workflow doesn't just score for drift — it WRITES a predictions
#    table (parquet in data-processed + a DuckDB view) that the DA queries like
#    any consumer … + surfaced as a Metabase predictions & drift board over the
#    predictions mart + DA drift memo: what ACTUALLY changed in 2020-03 (trip
#    mix? zones? durations?) — interpretation, not just detection.
#    Accept when: v1's M6 gate; the predictions table for the scored month
#    exists and the DA memo cites it; AND the memo explains the drift in domain
#    terms with numbers. Show: the two failure signatures + the predictions
#    table + the memo."
#
# The design rules are M2-S5's, M3-S5's, M4-S5's, M5-S5's and M6-S5's, inherited
# whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50). This gate types no
#     champion version, no month, no PSI, no volume ratio and no threshold.
#     Every number it compares is read from two places and matched — the
#     records against their own anchors, the rules against the document that
#     argues them, the prose against the records it cites;
#   * no skip flag, no fast mode. M1's rule, inherited a SEVENTH time.
#
# RE-RUNS NOTHING EXPENSIVE AND MINTS NOTHING IT COUNTS. It does not ingest a
# month (M7-S1 read 15.7M raw rows), does not score one (M7-S2 wrote 15.4M
# prediction rows and re-scored the holdout first), does not compute drift, does
# not push a metric, does not run the drift drill (~12 min), does not fit
# anything (M7-S4's challenger cost 1,618.4 s of CPU) and does not deploy or
# schedule. It reads: the tracked records M7-S1…S5 wrote, the analyst layer, the
# published mart, the live registry, the live Prometheus, the committed docs —
# and it asks the live system exactly THREE questions:
#
#     one prediction · one PromQL query · one rules read
#
# WHY THE RECORDS AND NOT A FRESH RUN, one milestone further on. M4's cache leg
# and M6's gameday leg made the argument from cost and from irreproducibility.
# M7 adds a third reason that is specific to a drift milestone: THE ORDER OF WORK
# IS PART OF THE EVIDENCE. The drift bars were argued from 2019 headroom BEFORE
# any 2020 month was compared (M7 law 4), and that ordering is checkable only
# from artifacts that already exist — from the records' own clocks and from git.
# A gate that recomputed the drift numbers would destroy the one property that
# makes the bars legitimate.
#
# THE ONE THING THIS GATE ASKS THAT NO PREDECESSOR COULD: the §9/M7 "Show" leg,
# §2 below. The two failure signatures — a month that is structurally fine and
# statistically alien, versus a month the contract refuses whole — must be
# DISTINGUISHABLE from the records, field by field, and the dangerous half is
# the one that produces no drift metric at all (gotcha #78's empty-panel disease
# with the panel removed entirely). That is asserted here as a difference
# between two record shapes, not as a sentence in a table.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m7.sh          (via `make verify-m7`)
#        scripts/verify_m7_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The counting harness — the two counters, the four printers, `consume` and
# `expect_verdicts` — lives in ONE place from CU-S3 on. `consume` must still be
# called as `consume < <(...)` and never through a pipe; the reason, and what
# deliberately did NOT move (this gate's legs, its verdict block), are in the
# lib's own header.
# shellcheck source=lib/verify_harness.sh
source "$REPO_ROOT/scripts/lib/verify_harness.sh"

printf '\n\033[1m[verify-m7]\033[0m the M7 gate — a scoring month that is not a fourth split, two\n'
printf '            failure signatures that must not look alike, a predictions table the DA\n'
printf '            queries, bars argued before the data was seen, and a retrain that said no.\n'

# --------------------------------------------------- 1. the scoring months ----
section "1. the scoring months — 2020 arrived, and the settled 2019 bytes did not move"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import duckdb
    import yaml

    data_cfg = yaml.safe_load(Path("configs/data.yaml").read_text())
    train_cfg = yaml.safe_load(Path("configs/train.yaml").read_text())

    # (a) The two month lists are DERIVED from their own files and must be
    # disjoint. Split months are a modelling fact and live in train.yaml; a
    # scoring month is the opposite. Neither list is typed here.
    scoring_months = list(data_cfg["scoring"]["months"])
    split_months = []
    for key in ("train_months", "val_months", "test_months", "val_month", "test_month"):
        value = train_cfg.get("data", {}).get(key) or train_cfg.get(key)
        if isinstance(value, str):
            split_months.append(value)
        elif isinstance(value, list):
            split_months.extend(value)
    overlap = sorted(set(scoring_months) & set(split_months))
    if scoring_months and split_months and not overlap:
        ok(f"{len(scoring_months)} scoring month(s) {scoring_months} are disjoint from the "
           f"{len(split_months)} split month(s) — a month cannot be both trained on and scored "
           f"for drift, because then its drift reference would contain itself")
    else:
        no(f"scoring={scoring_months} split={split_months} overlap={overlap}")

    # (b) …and the one mistake the separation makes possible is REFUSED, in a
    # type. Behavioural, not a grep: the config loader is handed a month in both
    # lists and must raise.
    import tempfile

    from taxi_mlops.data import config as config_mod

    doctored = json.loads(json.dumps(data_cfg))
    doctored["scoring"]["months"] = [split_months[0]] + list(scoring_months)
    raised = None
    with tempfile.TemporaryDirectory() as tmp:
        doctored_path = Path(tmp) / "data.yaml"
        doctored_path.write_text(yaml.safe_dump(doctored))
        try:
            config_mod.load_config(str(doctored_path))
        except Exception as exc:  # noqa: BLE001
            raised = exc
    if raised is not None and split_months[0] in str(raised):
        ok(f"load_config REFUSES a month that is in both lists — {type(raised).__name__} naming "
           f"{split_months[0]!r}. A scoring month that is also a split month is the one mistake "
           f"this separation makes possible, so it is checked in a type")
    else:
        no(f"a month in BOTH lists was accepted (raised={raised!r}) — the config guard is gone")

    con = duckdb.connect("data/analyst.duckdb", read_only=True)

    # (c) THE LAW OF THE TREES, asked of the data and not of the code. One 2020
    # row inside data/processed/ would reach the training matrix, the marts and
    # every board through globs written when that directory meant "the settled
    # 2019 months" — with no error anywhere.
    splits = sorted(r[0] for r in con.execute("SELECT DISTINCT split FROM trips_clean").fetchall())
    if splits == ["test", "train", "val"]:
        ok(f"trips_clean still returns exactly {{{', '.join(splits)}}} — no scoring row reached "
           f"the tree the program's numbers rest on (M7 law 2, asked of the rows)")
    else:
        no(f"trips_clean returns splits {splits} — a scoring month is inside the settled trees")

    # (d) The scoring views exist, carry the configured months and nothing else,
    # and their totals reconcile with the ingest reports that wrote them.
    rows = con.execute(
        "SELECT month, rows_in, rows_out, rows_rejected FROM scoring_months ORDER BY 1"
    ).fetchall()
    got = [r[0] for r in rows]
    scored_total = sum(r[2] for r in rows)
    view_total = con.execute("SELECT count(*) FROM trips_scoring").fetchone()[0]
    if got == sorted(scoring_months) and scored_total == view_total:
        ok(f"the scoring views hold exactly the configured months {got} and "
           f"{view_total:,} row(s) == {scored_total:,} the ingest reports claim — the "
           f"reconciliation `make duckdb` exits 1 on, re-asked here without rebuilding it")
    else:
        no(f"scoring views hold {got} against configured {sorted(scoring_months)}; "
           f"trips_scoring {view_total:,} vs reports {scored_total:,}")

    # (e) The settled pins are UNMODIFIED IN GIT. A changed 2019 byte is a
    # defect, not a refresh — and the cheapest place a reviewer sees it is a diff.
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "data/processed.dvc", "data/rejected.dvc"],
        capture_output=True, text=True).stdout.strip()
    tracked = subprocess.run(
        ["git", "ls-files", "data/scoring.dvc", "data/scoring_rejected.dvc"],
        capture_output=True, text=True).stdout.split()
    if not dirty and len(tracked) == 2:
        ok("data/processed.dvc and data/rejected.dvc are unmodified in git while the scoring trees "
           "carry their OWN pins (data/scoring.dvc, data/scoring_rejected.dvc) — new artifacts "
           "beside the settled ones, never inside them")
    else:
        no(f"2019 pins dirty={dirty!r}; scoring pins tracked={tracked}")

    # (f) The 2025 leg was a MEASUREMENT and it came back VALIDATED — the
    # blueprint's premise SURPASSED. The probe must also have acquired nothing.
    # The probe record is FOUND, not named — the month it covers is its own
    # field. A gate that typed the year would have to be edited before anybody
    # could probe a different one.
    probes = [json.loads(p.read_text())
              for p in sorted(Path("automation/runs/m7-s1").glob("contract_probe_*.json"))
              if "fixture" not in p.name]
    manifest = json.loads(Path("data/raw_manifest.json").read_text())
    keys = list(manifest.get("files", manifest))
    validated = [p for p in probes
                 if str(p.get("outcome", "")).upper().startswith("VALID") and p["exit_code"] == 0]
    acquired = sorted({p["month"] for p in probes
                       if any(p["month"][:4] in str(k) for k in keys)})
    if probes and len(validated) == len(probes) and not acquired:
        p = validated[0]
        events = p.get("schema_events") or []
        ok(f"the REAL {p['month']} file came back {p['outcome']} (exit {p['exit_code']}, "
           f"{p['rows_read']:,} rows, {len(p['columns_as_delivered'])} columns, "
           f"{len(events)} schema event(s)) and the probe acquired NOTHING — no entry for its "
           f"year in data/raw_manifest.json. A structural verdict, measured rather than assumed, "
           f"and a SURPASS over the blueprint's premise that a future year would refuse")
    else:
        no(f"{len(probes)} probe record(s), {len(validated)} validated; "
           f"probed year(s) that nevertheless entered the manifest: {acquired}")

    # (g) …and because it validated, the REFUSAL had to be watched somewhere
    # else. Three fixtures, three shapes, and the exit code is the assertion: a
    # refusal that exits 0 is a refusal a pipeline cannot hear.
    fixtures = sorted(Path("automation/runs/m7-s1").glob("contract_probe_fixture_*.json"))
    recs = [json.loads(p.read_text()) for p in fixtures]
    bad = [r for r in recs
           if r.get("exit_code") != 1 or r.get("error_type") != "SchemaEventError"
           or str(r.get("outcome", "")).upper() != "REFUSED"]
    # …and NOTHING was written. The record cannot say that about itself — a
    # refusal's whole signature is an absence — so it is asked of the places a
    # month would have to appear in if it had landed anywhere.
    refused_months = {r["month"] for r in recs}
    landed = sorted(refused_months & {
        m for (m,) in con.execute(
            "SELECT month FROM ingest_months UNION SELECT month FROM scoring_months").fetchall()})
    if len(recs) >= 3 and not bad and not landed:
        shapes = ", ".join(sorted(r["fixture"] for r in recs))
        ok(f"{len(recs)} refusal shapes on the record ({shapes}) — every one SchemaEventError, "
           f"REFUSED, exit 1, and {sorted(refused_months)} appears in NO ingest or scoring month. "
           f"The exit code is the assertion; the absence is the signature")
    else:
        no(f"{len(recs)} fixture record(s); non-conforming: "
           f"{[(r.get('fixture'), r.get('exit_code'), r.get('error_type'), r.get('outcome')) for r in bad]}; "
           f"refused month(s) that nevertheless landed: {landed}")

    # (h) The old accessors still mean "the settled months" — a dispatcher
    # hiding inside them would put a 2020 month wherever any of them is called.
    cfg = config_mod.load_config()
    refused = 0
    for attr in ("processed_path", "rejected_path", "rejections_path"):
        fn = getattr(cfg, attr, None)
        if fn is None:
            continue
        try:
            fn(scoring_months[0])
        except Exception:  # noqa: BLE001
            refused += 1
    if refused >= 1:
        ok(f"{refused} legacy path accessor(s) still RAISE for a scoring month — every existing "
           f"caller means the settled trees, and none of them silently learned a new destination")
    else:
        no("the legacy processed/rejected path accessors answer for a scoring month — a "
           "dispatcher is hiding inside an accessor whose callers all mean 2019")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the scoring-months check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the scoring-months check"

# ------------------------------------------ 2. the two failure signatures -----
section "2. the two failure signatures — DISTINGUISHABLE from the records, not from a table"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import duckdb
    import yaml

    data_cfg = yaml.safe_load(Path("configs/data.yaml").read_text())
    scoring_months = sorted(data_cfg["scoring"]["months"])
    con = duckdb.connect("data/analyst.duckdb", read_only=True)

    # The two shapes, each read from ITS OWN records. Nothing below is typed:
    # the statistical month is the one with the lowest volume ratio among the
    # configured months, and the schema shape is whatever the fixture records
    # say happened.
    drift_records = {p.stem.replace("drift-", ""): json.loads(p.read_text())
                     for p in Path("automation/runs/m7-drift").glob("drift-*.json")}
    worst = min(drift_records.values(), key=lambda r: r["volume_ratio"])
    month = worst["month"]

    stat = dict(
        exit_code=0,
        rows_written=con.execute(
            "SELECT rows_out FROM scoring_months WHERE month = ?", [month]).fetchone()[0],
        report_exists=True,
        drift_metric=True,
    )
    fixtures = [json.loads(p.read_text())
                for p in Path("automation/runs/m7-s1").glob("contract_probe_fixture_*.json")]
    # `rows_written` for a refusal is NOT a field of the fixture record — the
    # record is a report of a refusal and would have to claim its own absence.
    # It is counted where a landed month would have to show up.
    landed = con.execute(
        "SELECT coalesce(sum(rows_out), 0) FROM ("
        "  SELECT month, rows_out FROM ingest_months"
        "  UNION ALL SELECT month, rows_out FROM scoring_months) t "
        "WHERE month IN (SELECT unnest(?))",
        [sorted({f["month"] for f in fixtures})]).fetchone()[0]
    schema = dict(
        exit_code=max(f["exit_code"] for f in fixtures),
        rows_written=int(landed),
        report_exists=False,
        drift_metric=False,
    )

    # (a) The statistical signature: the contract PASSED and a month of rows
    # exists to be compared.
    if stat["exit_code"] == 0 and stat["rows_written"] > 0 and month in drift_records:
        ok(f"statistical drift ({month}): contract passed, exit 0, {stat['rows_written']:,} rows "
           f"written, and a drift record exists for the month — there is something to compare, "
           f"and it moved")
    else:
        no(f"the statistical signature does not read as one: {stat}")

    # (b) The schema signature, and the field that matters is the LAST one.
    if schema["exit_code"] == 1 and schema["rows_written"] == 0 and not schema["drift_metric"]:
        ok(f"schema drift (fixtures): SchemaEventError, exit 1, ZERO rows written — no output, no "
           f"sidecar, no report, and therefore NO DRIFT METRIC AT ALL. That last clause is the "
           f"dangerous one: a drift board showing 'no alert' looks identical to a healthy month")
    else:
        no(f"the schema signature does not read as one: {schema}")

    # (c) They must differ in EVERY discriminating field. A pair of failures that
    # agree on three of four fields is a pair an operator will confuse at 3am.
    differs = [k for k in stat if stat[k] != schema[k]]
    if sorted(differs) == sorted(stat):
        ok(f"the two signatures differ in all {len(differs)} discriminating fields "
           f"({', '.join(sorted(differs))}) — this is §9/M7's 'Show', asserted as a difference "
           f"between record shapes rather than as a sentence in a table")
    else:
        no(f"the signatures agree on {sorted(set(stat) - set(differs))} — they are not "
           f"distinguishable on those fields")

    # (d) The drift instrument saw the configured months and NOTHING ELSE. A
    # fourth record would mean a month was compared that nobody ingested; a
    # missing one would mean the absence the schema case produces.
    if sorted(drift_records) == scoring_months:
        ok(f"exactly {len(drift_records)} drift record(s) exist, one per configured scoring month "
           f"{scoring_months} — the absence a refused month produces is countable, because the "
           f"present ones are")
    else:
        no(f"drift records {sorted(drift_records)} against configured months {scoring_months}")

    # (e) The only guard that can see the absence is staleness, and it must
    # exist as a rule. The doc says so; the rules file is where it is true.
    rules = yaml.safe_load(Path("infra/monitoring/alerting_rules.yml").read_text())
    all_rules = [r for g in rules["groups"] for r in g["rules"]]
    # A rule whose ONLY metric is a freshness stamp. A-4 also reads one, but as
    # a guard on a comparison it makes about something else — so "mentions a
    # timestamp" would find two rules and prove neither. Derived, not named.
    def metrics_in(expr):
        return set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\{", expr)) or \
            set(re.findall(r"\b(taxi_[a-z0-9_]+)\b", expr))
    stale = [r for r in all_rules
             if metrics_in(r["expr"])
             and all(m.endswith("_last_run_timestamp_seconds") for m in metrics_in(r["expr"]))]
    if stale:
        ok(f"the absence has exactly one guard and it exists: {', '.join(r['alert'] for r in stale)} "
           f"— a schema refusal produces no metric, so the only signal that a month SHOULD have "
           f"been compared and was not is staleness. Slow, and honest about being slow")
    else:
        no("no rule reads a *_last_run_timestamp_seconds against time() — nothing can see a month "
           "that was never compared")

    # (f) Both write-ups carry the pair side by side, and their exit codes agree
    # with the records. A table that contradicts the record it summarises is
    # worse than no table.
    tables = {}
    for path in ("docs/scoring_months_m7.md", "docs/drift_detection_m7.md"):
        text = Path(path).read_text()
        tables[path] = ("SchemaEventError" in text and "exit" in text.lower()
                        and f"{stat['rows_written']:,}" in text)
    missing = [p for p, good in tables.items() if not good]
    if not missing:
        ok(f"both write-ups tabulate the pair and quote the record's own row count "
           f"({stat['rows_written']:,}) beside the refusal — {', '.join(tables)}")
    else:
        no(f"write-up(s) whose signature table does not reconcile with the records: {missing}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the signatures check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the signatures check"

# ------------------------------------------------ 3. the predictions table ----
section "3. batch inference as a product — the table the DA queries, and its three-way reconciliation"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import calendar
import json
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

def psql(sql, db="marts"):
    out = subprocess.run(
        ["kubectl", "--context", "kind-mlops-taxi", "-n", "platform", "exec", "-i", "postgres-0",
         "--", "psql", "-U", "postgres", "-d", db, "-tAF|", "-c", sql],
        capture_output=True, text=True)
    return [line.split("|") for line in out.stdout.strip().splitlines() if line]

try:
    import duckdb
    import mlflow

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    manifest = json.loads(Path("data/scoring_predictions/scoring_predictions.json").read_text())

    # (a) The rows were scored by what the ALIAS resolves to, and the alias is
    # what it was. Both sides live: the registry answers, the manifest recorded.
    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    if manifest["model"]["version"] == str(champion.version) \
            and manifest["model"]["run_id"] == champion.run_id \
            and manifest["model"]["alias"] == reg["champion_alias"]:
        ok(f"every published row is stamped with version {manifest['model']['version']}, which is "
           f"what @{reg['champion_alias']} resolves to RIGHT NOW (run {champion.run_id[:12]}…) — "
           f"resolved by alias, never by `source` (F-009's two hops)")
    else:
        no(f"the manifest says version {manifest['model']['version']}/"
           f"{manifest['model']['run_id'][:12]}… against a live alias of {champion.version}/"
           f"{champion.run_id[:12]}…")

    # (b) THE SELF-CHECK IS THIS STORY'S CENTRE, and it is the one thing these
    # rows could be checked against. A scoring month has no gate tag; the HOLDOUT
    # does. So the path re-scored a month with a known answer first, and the
    # answer must still be the champion's own tag.
    self_check = manifest["self_check"]
    tag = champion.tags.get("gate_challenger_mae")
    decimals = len(str(tag).split(".")[-1]) if tag and "." in str(tag) else 4
    measured = round(float(self_check["measured_kpi_09"]), decimals)
    if tag and measured == round(float(tag), decimals):
        ok(f"the path proved itself on a month with a KNOWN answer before writing one with none: "
           f"re-scoring the {self_check['split']} split ({self_check['rows']:,} rows) measured "
           f"{measured} against the champion's own gate_challenger_mae tag of {tag} — read off the "
           f"registry, not off the manifest that claims it")
    else:
        no(f"the self-check recorded {self_check.get('measured_kpi_09')} against the version's "
           f"gate_challenger_mae of {tag}")

    # (c)…(e) THE THREE-WAY RECONCILIATION, and the three sides are three
    # systems: the ingest reports (DuckDB), the scoring manifest (a file), and
    # the published mart (Postgres). Comparing the mart against the predictions
    # alone would prove SQL can sum a column.
    con = duckdb.connect("data/analyst.duckdb", read_only=True)
    reports = dict(con.execute("SELECT month, rows_out FROM scoring_months").fetchall())
    from_manifest = {m["month"]: m["rows"] for m in manifest["months"]}
    mart = {r[0]: (int(r[1]), int(r[2]), int(r[3]), r[4])
            for r in psql("SELECT month, count(*), sum(kpi_17_scored_trips), "
                          "max(model_versions_seen), max(model_version) "
                          "FROM marts.scoring_daily GROUP BY month ORDER BY 1")}
    mismatched = [m for m in reports
                  if reports[m] != from_manifest.get(m) or reports[m] != mart.get(m, (None,))[1]]
    if reports and not mismatched:
        total = sum(reports.values())
        ok(f"ingest -> predictions -> mart reconcile for every month, {total:,} rows across "
           f"{len(reports)} month(s) — three systems (DuckDB, a manifest file, Postgres), and the "
           f"AUTHORITY is the ingest report: a job that scored 14 of 15.4M rows would have the "
           f"other two agreeing and both wrong")
    else:
        no(f"month(s) where ingest/manifest/mart disagree: "
           f"{[(m, reports[m], from_manifest.get(m), mart.get(m, (None, None))[1]) for m in mismatched]}")

    spliced = [m for m, v in mart.items() if v[2] != 1]
    if mart and not spliced:
        ok(f"model_versions_seen is 1 on every month of the mart ({', '.join(sorted(mart))}) — "
           f"M7's alias may legitimately move through the gate, and a spliced series would average "
           f"two champions into invisibility")
    else:
        no(f"month(s) whose daily rows carry more than one model version: {spliced}")

    wrong_days = [m for m, v in mart.items()
                  if v[0] != calendar.monthrange(int(m[:4]), int(m[5:7]))[1]]
    if mart and not wrong_days:
        shown = ", ".join(f"{m}={mart[m][0]}" for m in sorted(mart))
        ok(f"the mart carries a row for every calendar day of every month ({shown}) — derived from "
           f"the calendar, so a February that lost a day cannot pass")
    else:
        no(f"month(s) with the wrong number of daily rows: "
           f"{[(m, mart[m][0], calendar.monthrange(int(m[:4]), int(m[5:7]))[1]) for m in wrong_days]}")

    # (f) THE ID LAW. A monitoring window gets monitoring ids, and the
    # promotion ids may not appear anywhere near them (gotcha #15).
    kpi_doc = Path("docs/kpi_definitions.md").read_text()
    ids = sorted(set(re.findall(r"###\s*(KPI-1[4-7])\b", kpi_doc)))
    marked = [i for i in ids
              if "MONITORING" in kpi_doc.split(f"### {i}", 1)[1].split("### KPI-")[0].upper()]
    cols = [c[0] for c in psql(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='marts' "
        "AND table_name='scoring_daily' ORDER BY ordinal_position")]
    promo = [c for c in cols if re.search(r"kpi_(09|10)", c)]
    if len(ids) == 4 and marked == ids and not promo:
        ok(f"{len(ids)} monitoring ids are defined and every one is labelled MONITORING "
           f"({', '.join(ids)}), and NO column of marts.scoring_daily names KPI-09 or KPI-10 — the "
           f"window is new, so the ids are new, and the evaluator's holdout ids stay the "
           f"evaluator's")
    else:
        no(f"monitoring ids defined={ids} marked={marked}; promotion-id columns in the mart={promo}")

    # (g) §9.7 row 5's condition, honoured by REFUSING the comparison: the honest
    # floor is fitted on 2019 train months, so a 2020 margin would publish a
    # comparison no gate ever made against a bar chosen for a different world.
    forbidden = [c for c in cols if re.search(r"floor|margin|kpi_13", c)]
    if not forbidden:
        ok(f"the mart carries no floor and no margin column ({len(cols)} columns checked) — a 2020 "
           f"margin against a 2019-fitted floor is a comparison no gate ever made, and the way to "
           f"honour that is to refuse to publish it")
    else:
        no(f"the monitoring mart carries comparison column(s) no gate made: {forbidden}")

    # (h) The batch path READS the registry and cannot write it. ast, never grep:
    # the module argues its own design in prose that names the verbs.
    mutators = {"set_registered_model_alias", "delete_registered_model_alias", "register_model",
                "create_model_version", "transition_model_version_stage", "delete_model_version",
                "create_registered_model", "set_model_version_tag"}
    offenders = []
    for path in Path("src/taxi_mlops/training").glob("batch*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name in mutators:
                    offenders.append(f"{path.name}:{node.lineno} {name}")
    if not offenders:
        ok("no registry-mutating verb is CALLED anywhere in the batch scoring path (ast over the "
           "module, never a word search) — it resolves the alias, stamps the version and mints "
           "nothing")
    else:
        no(f"the batch path can mutate the registry: {offenders}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the predictions-table check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the predictions-table check"

# --------------------------------------------------- 4. the drift judgement ---
section "4. the judgement — the drift signals LOADED, argued in §8, and holding no bar of their own"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

ROUTE = "http://localhost:8081"

def http_get(host, path, timeout=20):
    req = urllib.request.Request(ROUTE + path, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)

try:
    import yaml

    rules_path = Path("infra/monitoring/alerting_rules.yml")
    doc = yaml.safe_load(rules_path.read_text())
    # The M7 signals are DERIVED: whatever lives in the group whose rules read
    # the pushgateway's job label, plus everything that reads a taxi_* series.
    m7_rules = [r for g in doc["groups"] for r in g["rules"]
                if re.search(r'job="taxi-[a-z-]+"', r["expr"])]
    m7_signals = sorted({r["labels"]["signal"] for r in m7_rules})

    # (a) THE ONE RULES READ. The file is the claim; /api/v1/rules is the
    # observation — a rules file that fails to parse leaves the previous rules
    # running and the deploy still succeeds.
    prom_values = Path("infra/helm/monitoring/prometheus-values.yaml").read_text()
    host = re.search(r"-\s*(prometheus\.[a-z.]+)\s*$", prom_values, re.M)
    host = host.group(1) if host else "prometheus.local"
    status, body = http_get(host, "/api/v1/rules")
    live = {}
    if status == 200:
        for g in json.loads(body)["data"]["groups"]:
            for r in g["rules"]:
                live[r["name"]] = r
    missing = [r["alert"] for r in m7_rules if r["alert"] not in live]
    unhealthy = [r["alert"] for r in m7_rules
                 if r["alert"] in live and live[r["alert"]].get("health") != "ok"]
    if m7_rules and not missing and not unhealthy:
        ok(f"all {len(m7_rules)} M7 rule(s) across signals {m7_signals} are LOADED and health=ok "
           f"in the live Prometheus ({', '.join(sorted(r['alert'] for r in m7_rules))})")
    else:
        no(f"M7 rules not loaded: {missing}; loaded but unhealthy: {unhealthy} (HTTP {status})")

    # (b) EVERY DRIFT THRESHOLD IS ARGUED IN §8 SPECIFICALLY — a strictly
    # stronger claim than `verify-m6`'s "somewhere in the SLO document". A number
    # argued in the latency section is not an argument for a drift bar.
    slo = Path("docs/slo_serving.md").read_text()
    def section_of(text, heading_pattern):
        m = re.search(heading_pattern, text)
        if not m:
            return ""
        rest = text[m.start():]
        nxt = re.search(r"\n## ", rest[3:])
        return rest[: nxt.start() + 3] if nxt else rest
    # §6 (F-035's two landings) and §8 (the drift bars) are the sections that
    # argue M7's signals, and both are searched — §8.5 legitimately states A-4's
    # 1800 s window beside SLO-D3's 3456000 because the two are the same kind of
    # freshness argument. What this still refuses is a threshold argued in the
    # LATENCY section standing as the argument for a drift bar, which is what
    # `verify-m6`'s whole-document search would accept.
    m7_home = section_of(slo, r"\n##\s*6\.") + "\n" + section_of(slo, r"\n##\s*8\.")

    def quoted(value: str, haystack: str) -> bool:
        forms = {value}
        try:
            f = float(value)
            forms |= {f"{f:g}", f"{f * 100:g}"}
        except ValueError:
            pass
        return any(re.search(rf"(?<![\d.]){re.escape(v)}(?![\d.]?\d)", haystack) for v in forms)

    unargued = {}
    for r in m7_rules:
        nums = re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", r["expr"])
        absent = [n for n in nums if not quoted(n, m7_home)]
        if absent:
            unargued[r["alert"]] = absent
    if m7_rules and not unargued:
        counted = sum(len(re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", r["expr"])) for r in m7_rules)
        ok(f"{counted} threshold(s) parsed out of the M7 rules and found in the SECTIONS that own "
           f"them (§6 and §8, {len(m7_home):,} characters of the document, not all of it) — a bar "
           f"argued in the latency section is not an argument for a drift bar")
    else:
        no(f"threshold(s) with no argument in §6 or §8: {unargued}")

    # (c) The argument travels with the number, and every M7 rule names a signal.
    bare = [r["alert"] for r in m7_rules
            if not r.get("annotations", {}).get("why") or not r.get("labels", {}).get("signal")]
    if not bare:
        ok(f"every M7 rule carries a `signal` label and an `annotations.why` — a threshold whose "
           f"argument is not written beside it is a number nobody can review")
    else:
        no(f"M7 rule(s) with no signal id or no `why`: {bare}")

    # (d) F-035 CLOSED, and the closure is ENFORCED rather than asserted:
    # `validate()` fails in BOTH directions, so the absence list cannot be
    # quietly emptied and a rule cannot be quietly deleted.
    # The sets are COMPUTED in that module (a set comprehension over a range and
    # a difference), so they are read by importing it rather than by literal-eval
    # — which would silently return nothing and let this leg pass on an empty set.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_rar", "scripts/render_alert_rules.py")
    rar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rar)
    known = set(rar.KNOWN_SIGNALS)
    implemented = set(rar.IMPLEMENTED_SIGNALS)
    in_file = {r["labels"]["signal"] for g in doc["groups"] for r in g["rules"]
               if r.get("labels", {}).get("signal")}
    absences = known - implemented
    if known and in_file == known and not absences:
        ok(f"every one of the {len(known)} known signals {sorted(known)} now has a rule and the "
           f"documented-absence list is EMPTY — F-035 closed by landing, not by prose, and "
           f"`render_alert_rules.py` fails in both directions so it cannot be re-opened quietly")
    else:
        no(f"known={sorted(known)} in rules={sorted(in_file)} absences={sorted(absences)}")

    # (e) A-8 EXCLUDES THE TARGET BY NAME, and that is the distinction that makes
    # the alert actionable: inputs steady + target moved means the RELATIONSHIP
    # changed; both moved means the world did.
    target_col = None
    monitored = Path("src/taxi_mlops/monitoring/drift.py").read_text()
    a8 = next((r for r in m7_rules if r["labels"]["signal"] == "A-8"), None)
    excluded = re.search(r'column!="([^"]+)"', a8["expr"]) if a8 else None
    if excluded and excluded.group(1) in monitored:
        target_col = excluded.group(1)
        ok(f"A-8's selector excludes {target_col!r} BY NAME — the target is monitored and pushed "
           f"but is not an input, and averaging it into the share would destroy exactly the "
           f"distinction that makes the alert actionable")
    else:
        no("A-8 does not exclude the target column by name — a moved target and a moved input "
           "would be averaged into one number")

    # (f) A-9 IS A DIFFERENT MARGINAL, NOT A REFINEMENT. PSI is a distance
    # between shares; halve every count and it is exactly zero. So A-9 must read
    # a quantity A-8's expression does not mention at all.
    a9 = next((r for r in m7_rules if r["labels"]["signal"] == "A-9"), None)
    if a9 and "psi" not in a9["expr"] and a8 and "volume" not in a8["expr"]:
        ok("A-9 reads a volume series and A-8 reads a PSI series, and neither expression mentions "
           "the other's — the marginal PSI is structurally blind to is measured separately rather "
           "than folded in")
    else:
        no("A-8 and A-9 read overlapping series — the volume signal is not independent of the "
           "shape signal")

    # (g) THE JOB PUSHES RAW QUANTITIES AND ISSUES NO VERDICT. The bar lives in
    # the rule's SELECTOR, so the pushed numbers stay re-interpretable after the
    # fact. ast, because these modules argue their own design at length (#53/#68).
    bars = {n for r in m7_rules for n in re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", r["expr"])}
    # NO SILENT CAP: the small integers among the thresholds (A-8's "two columns",
    # A-3's "> 0") are excluded and SAID SO, because they are ordinary arithmetic
    # in any module and a check that hunted them would go red on a loop bound.
    # What remains is every bar that could plausibly be a second home for a
    # threshold — the fractions and the durations.
    bar_values = {float(b) for b in bars}
    ignored = {v for v in bar_values if float(v).is_integer() and v < 1000}
    bar_values -= ignored
    planted = []
    for path in sorted(Path("src/taxi_mlops/monitoring").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                    and not isinstance(node.value, bool) and float(node.value) in bar_values:
                planted.append(f"{path.name}:{node.lineno} {node.value}")
    if bar_values and not planted:
        ok(f"no bar-shaped constant ({sorted(bar_values)}) appears anywhere under "
           f"src/taxi_mlops/monitoring/ — the job computes and pushes, the RULE judges, and one "
           f"home for a threshold means the pushed numbers can be re-read against a different bar "
           f"later. Excluded and said so: {sorted(ignored)}, which are ordinary arithmetic")
    else:
        no(f"a threshold value is hard-coded in the drift job: {planted}")

    # (h) `honor_labels: true` IS THE FLAG THE WHOLE THING RESTS ON. Without it
    # Prometheus overwrites the pushed `job` with the target's, every drift rule
    # selects a job that matches nothing, and the rules sit `inactive` forever —
    # indistinguishable from a healthy system.
    scrape = yaml.safe_load(prom_values)
    jobs = {j["job_name"]: j for j in scrape.get("extraScrapeConfigs", [])} \
        if isinstance(scrape.get("extraScrapeConfigs"), list) else {}
    if not jobs:
        found = re.search(r"job_name:\s*pushgateway(.*?)(?=\n  - job_name:|\Z)",
                          prom_values, re.S)
        honored = bool(found and re.search(r"honor_labels:\s*true", found.group(1)))
    else:
        honored = any(j.get("honor_labels") is True for n, j in jobs.items() if "pushgateway" in n)
    selectors = {m for r in m7_rules for m in re.findall(r'job="(taxi-[a-z-]+)"', r["expr"])}
    if honored and selectors:
        ok(f"the pushgateway's scrape job sets honor_labels: true, which is what lets the rules "
           f"select {sorted(selectors)} at all — without it every pushed sample arrives as "
           f"job=\"pushgateway\", every rule matches nothing, and nothing errors")
    else:
        no(f"honor_labels on the pushgateway job = {honored}; rules select {sorted(selectors)}")

    # (i) The freshness guard exists in a TYPE as well as in a rule: the pusher
    # REFUSES a payload with no timestamp metric. Behavioural, not a grep.
    from taxi_mlops.monitoring import pushgateway as pg

    refused = None
    try:
        pg.push_metrics([pg.Metric(name="taxi_drift_psi", value=0.0, help="probe")],
                        url="http://127.0.0.1:1", job="taxi-drift",
                        grouping={"month": "1970-01"})
    except Exception as exc:  # noqa: BLE001
        refused = exc
    if refused is not None and pg.FRESHNESS_SUFFIX in str(refused):
        ok(f"push_metrics REFUSES a payload with no *_last_run_timestamp_seconds "
           f"({type(refused).__name__}) — a pushed metric persists after its producer dies, so "
           f"'drift is fine' and 'the drift job died in March' would otherwise render identically")
    else:
        no(f"a payload with no freshness stamp was accepted (raised={refused!r}) — the guard is "
           f"only a rule, and a rule cannot fire on a number nobody pushed")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the drift-judgement check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the drift-judgement check"

# ------------------------------- 5. the order of work, and the drill ----------
section "5. the order of work — the bars argued before the data was seen, and the drill that judged them"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

ROUTE = "http://localhost:8081"

def http_get(host, path, timeout=20):
    req = urllib.request.Request(ROUTE + path, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)

def when(text):
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))

try:
    root = Path("automation/runs/m7-drift")
    headroom = json.loads((root / "headroom.json").read_text())
    prediction = json.loads((root / "prediction.json").read_text())
    drill = json.loads((root / "drift_fire_drill.json").read_text())
    drift = {p.stem.replace("drift-", ""): json.loads(p.read_text())
             for p in root.glob("drift-*.json")}

    # (a) THE HEADROOM LEG READ 2019 ONLY. That is what makes it legal to argue a
    # bar from it: the two held-out months are the only data here KNOWN not to
    # have warranted action, because the champion was measured on them and
    # promoted.
    years = {m[:4] for m in headroom}
    if years == {"2019"} and len(headroom) >= 2:
        biggest = max(
            ((m, c["column"], c["psi"]) for m, rec in headroom.items() for c in rec["columns"]),
            key=lambda t: t[2])
        ok(f"the headroom leg read {sorted(headroom)} and nothing else — 2019 only. Its largest "
           f"input distance is {biggest[1]} at {biggest[2]:.4f} in {biggest[0]}, a month whose "
           f"verdict already exists (the champion was measured on it and PROMOTED)")
    else:
        no(f"the headroom record covers {sorted(headroom)} — a bar argued from a 2020 month is a "
           f"bar chosen to make an alert agree")

    # (b) …and it ran FIRST, on the records' own clocks.
    latest_headroom = max(when(r["computed_at"]) for r in headroom.values())
    earliest_2020 = min(when(r["computed_at"]) for r in drift.values())
    if latest_headroom < earliest_2020:
        ok(f"the headroom ran at {latest_headroom.isoformat()} and the first 2020 comparison at "
           f"{earliest_2020.isoformat()} — the order of work checked on the records' own stamps, "
           f"never on the order the write-ups are arranged in")
    else:
        no(f"the headroom ({latest_headroom}) does not precede the first 2020 comparison "
           f"({earliest_2020})")

    # (c) …and the PREDICTION was committed before any 2020 drift record was. The
    # strongest available form of "written first": git, not a field in a file
    # claiming something about itself.
    def added(path):
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ct", "--", path],
            capture_output=True, text=True).stdout.split()
        return int(out[-1]) if out else None
    pred_at = added(str(root / "prediction.json"))
    firsts = [added(str(root / f"drift-{m}.json")) for m in drift]
    firsts = [f for f in firsts if f]
    if pred_at and firsts and pred_at < min(firsts):
        ok(f"the prediction was COMMITTED before any 2020 drift record was — git's own commit "
           f"clocks, {min(firsts) - pred_at} s apart. A prediction written after the outcome is "
           f"not a prediction, and the only witness that cannot be edited into agreement is the "
           f"history")
    else:
        no(f"prediction added at {pred_at}, first drift record at {min(firsts) if firsts else None}")

    # (d) A prediction can be written first and then quietly edited into the
    # record it is judged against. The M6 gameday idiom, transplanted.
    if drill.get("prediction") == prediction:
        ok(f"the drill's embedded prediction is field-by-field equal to the committed "
           f"{root / 'prediction.json'} — the record was judged against the file, and the file "
           f"has not moved since")
    else:
        no("the drill's embedded prediction differs from the committed prediction file")

    # (e) The must-fire clause: ONE alert, ONE month, and it reached the thing
    # that would page a human — not just Prometheus's own UI.
    fired = {k: v for k, v in drill["fired_at_seconds"].items()}
    must_fire = {f"{p['alert']}@{p['month']}" for p in prediction["must_fire"]}
    at_am = set(drill.get("alertmanager_received", []))
    if set(fired) == must_fire and {k.split("@")[0] for k in fired} <= at_am:
        key = sorted(fired)[0]
        ok(f"exactly the predicted alert fired, for exactly the predicted month: {key} at "
           f"T+{fired[key]:.1f} s, and it reached ALERTMANAGER — a rule that goes red only in "
           f"Prometheus's own UI has not alerted anybody")
    else:
        no(f"fired={sorted(fired)} against predicted {sorted(must_fire)}; "
           f"alertmanager saw {sorted(at_am)}")

    # (f) The negative predictions are the load-bearing half — a drill that
    # predicts only "something fires" cannot be wrong.
    states = drill["states_after"]
    should_be_quiet = {p["alert"] for p in prediction["must_not_fire"]} - {k.split("@")[0] for k in fired}
    noisy = sorted(a for a in should_be_quiet if states.get(a, "inactive") != "inactive")
    if should_be_quiet and not noisy:
        ok(f"all {len(should_be_quiet)} must-not-fire alert(s) stayed inactive "
           f"({', '.join(sorted(should_be_quiet))}) — the negative half, which is what makes the "
           f"drill falsifiable")
    else:
        no(f"alert(s) predicted inactive that were not: {noisy}")

    # (g) The pre-registered OPEN QUESTION, and its outcome. It was tagged as the
    # prediction most likely to be wrong before the run; a milestone that only
    # records the predictions it got right has learned nothing.
    oq = drill.get("open_question_outcome", {})
    declared = prediction.get("the_open_question", {})
    if oq.get("prediction_correct") is not None and declared.get("confidence", "").startswith("low"):
        ok(f"the open question was pre-registered at confidence '{declared['confidence']}' — "
           f"{oq['alert']} predicted {oq['predicted']!r}, observed {oq['observed']!r}, correct="
           f"{oq['prediction_correct']}. The monthly window's blind spot is a recorded result, "
           f"not a footnote")
    else:
        no(f"the open question is not recorded with a confidence and an outcome: {oq}")

    # (h) THE ANCHOR LEG. Every volume ratio must re-derive from the record's OWN
    # numerator and denominator. A ratio is a RATE — trips per DAY — and the
    # tempting wrong quantity is a ratio of totals, which is F-045's own mistake
    # wearing a summary field's clothes.
    off = {}
    for month, rec in sorted(drift.items()):
        derived = rec["current_trips_per_day"] / rec["reference_trips_per_day"]
        if abs(derived - rec["volume_ratio"]) > 1e-9:
            off[month] = (rec["volume_ratio"], derived)
    if drift and not off:
        shown = ", ".join(f"{m}={drift[m]['volume_ratio']:.4f}" for m in sorted(drift))
        ok(f"every recorded volume ratio re-derives from its own anchors — trips/DAY over "
           f"trips/DAY, not rows over rows ({shown}). A month is not a unit of demand; a day is")
    else:
        no(f"volume ratio(s) that do not reconcile with the run's anchors "
           f"(recorded vs current_trips_per_day/reference_trips_per_day): {off}")

    # (i) THE SECOND WITNESS, and it is a different tracked record: what the
    # drill saw on the gateway must equal what the per-month records hold.
    disagree = {m: (drill["prometheus_series"].get(m), rec["volume_ratio"])
                for m, rec in drift.items()
                if abs((drill["prometheus_series"].get(m) or -1) - rec["volume_ratio"]) > 1e-9}
    if not disagree:
        ok(f"the drill's observed gateway series agree with all {len(drift)} per-month drift "
           f"records — two tracked artifacts written by two phases of the work, and a claim only "
           f"one of them makes is not a measurement")
    else:
        no(f"the drill record and the per-month records disagree on the ratio: {disagree}")

    # (j) THE BAR HAS DAYLIGHT ON BOTH SIDES, and both sides are derived: above
    # every accepted 2019 month, below the month that fired.
    bar = None
    rules_text = Path("infra/monitoring/alerting_rules.yml").read_text()
    m = re.search(r"taxi_drift_volume_ratio\{[^}]*\}\s*<\s*([0-9.]+)", rules_text)
    if m:
        bar = float(m.group(1))
    accepted = [r["volume_ratio"] for r in headroom.values()]
    fired_month = sorted(fired)[0].split("@")[1]
    if bar and min(accepted) > bar > drift[fired_month]["volume_ratio"]:
        ok(f"the bar {bar} sits below the quietest ACCEPTED month ({min(accepted):.4f}) and above "
           f"the month that fired ({drift[fired_month]['volume_ratio']:.4f}) — daylight on both "
           f"sides, and both sides read from records rather than typed here")
    else:
        no(f"bar={bar}, quietest accepted={min(accepted) if accepted else None}, "
           f"fired month ratio={drift.get(fired_month, {}).get('volume_ratio')}")

    # (k) THE ONE PROMQL QUERY, and it is asked in the form that can only fail
    # for a REASON — F-050, found by this gate on its first run.
    #
    # The obvious question is "are the drift series on the board?". It is the
    # wrong one to make a verdict of: a pushgateway is a bulletin board with no
    # persistence, so a pod restart takes every pushed sample with it, and the
    # only way to put them back is to RE-RUN the drift job — which this gate is
    # forbidden to do. Demanding the samples would turn the M7 gate red for a
    # laptop reboot with no defect in M7's work (gotcha #50).
    #
    # So the question asked is the PAIR: either the series are there, or the
    # gateway has restarted since the drill pushed them and the absence is
    # accounted for. That degrades in the correct direction — an absence with no
    # restart behind it is still a FAIL — and it makes the gap visible, which is
    # the point: A-10 exists to catch a STALE number, and it cannot fire on an
    # ABSENT one, because `time() - max by (month) (...)` over no series is no
    # series (F-050, routed at the M7 boundary).
    prom_values = Path("infra/helm/monitoring/prometheus-values.yaml").read_text()
    host = re.search(r"-\s*(prometheus\.[a-z.]+)\s*$", prom_values, re.M)
    host = host.group(1) if host else "prometheus.local"
    expr = 'taxi_drift_volume_ratio{job="taxi-drift"}'
    status, body = http_get(host, "/api/v1/query?" + urllib.parse.urlencode({"query": expr}))
    series = json.loads(body)["data"]["result"] if status == 200 else []
    months_live = sorted(s["metric"].get("month", "") for s in series)
    started = subprocess.run(
        ["kubectl", "--context", "kind-mlops-taxi", "-n", "monitoring", "get", "pod",
         "-l", "app.kubernetes.io/name=prometheus-pushgateway", "-o",
         "jsonpath={.items[*].status.containerStatuses[*].state.running.startedAt}"],
        capture_output=True, text=True).stdout.split()
    restarted_after_push = bool(started) and max(when(s) for s in started) > when(drill["pushed_at"])
    if months_live == sorted(drift):
        ok(f"the live gateway carries {len(series)} volume series, one per scoring month "
           f"{months_live}, each still labelled job=\"taxi-drift\" — honor_labels observed on the "
           f"SERVER rather than read off the values file that asks for it")
    elif not months_live and restarted_after_push:
        ok(f"the gateway holds no drift series and the reason is accounted for: its container "
           f"started {max(when(s) for s in started).isoformat()}, AFTER the drill pushed at "
           f"{drill['pushed_at']} — a bulletin board keeps nothing across a restart. **F-050**: "
           f"A-10 catches a STALE number and cannot fire on an ABSENT one, so this state is "
           f"silent. Re-push with `make drift DRIFT_ARGS=\"--push\"`; the gate may not")
    else:
        no(f"{expr} returns months {months_live} against the recorded {sorted(drift)} "
           f"(HTTP {status}), and the gateway has NOT restarted since the push — the samples went "
           f"missing for a reason nothing accounts for")

    # (l) "Then cleared" needed an argument, not a copy: nothing was injected, so
    # the clearing was demonstrated on the MECHANISM and then UNDONE. The board
    # must end carrying the truth.
    if drill.get("cleared_after_seconds") and drill.get("states_after", {}).get(
            sorted(fired)[0].split("@")[0]) in {"firing", "pending"}:
        ok(f"the rule was shown to CLEAR ({drill['cleared_after_seconds']:.1f} s after its series "
           f"was deleted) and the real numbers were then pushed straight back — March 2020 really "
           f"did lose most of its trips, and latching that off to tidy a transcript would publish "
           f"a false board")
    else:
        no(f"the clearing is not demonstrated-then-undone: cleared_after="
           f"{drill.get('cleared_after_seconds')}, states_after={drill.get('states_after')}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the order-of-work check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 11 "the order-of-work check"

# ------------------------------------------------------------- 6. the retrain -
section "6. the retrain — the loop closed, the transfer made, and the pointer that did not move"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
from datetime import datetime
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

def when(text):
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))

try:
    import mlflow

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    rec = json.loads(Path("automation/runs/m7-retrain/latest.json").read_text())
    verdict = rec["verdict"]

    # (a) A REFUSE IS A WORKING LOOP. The gate said no, and it said no on the
    # conditions F-011 added — the floor conditions passed.
    failed = [r["check"] for r in verdict["reasons"] if not r["passed"]]
    passed = [r["check"] for r in verdict["reasons"] if r["passed"]]
    if verdict["verdict"] == "REFUSE" and rec["promoted"] is False and failed and passed:
        ok(f"the challenger was {verdict['verdict']}D and promoted={rec['promoted']}: "
           f"{len(passed)} condition(s) passed ({verdict['observed_pct_vs_floor']:.2f}% against a "
           f"{verdict['required_pct_vs_floor']:.2f}% floor bar) and {len(failed)} failed — "
           f"{'; '.join(failed)}. A refusal is a working gate, not a failed story")
    else:
        no(f"verdict={verdict['verdict']} promoted={rec['promoted']} failed={failed}")

    # (a2) ...and that REFUSE is STABLE ACROSS THE ERA BOUNDARY (M9-S10, F-016).
    # This leg reads a recorded verdict; it does not replay one through
    # `gate.decide` the way verify-m2 §2 and verify-m3 §5 do, so it needs no era
    # table — but that is a claim worth asserting rather than assuming, because
    # the record predates the incumbent margin and carries no bar of its own.
    # The refusal here is by −0.03% against the serving champion, so it fails the
    # incumbent condition under the pre-B era (plain non-regression) AND under
    # every positive margin. A record whose meaning depended on the era would
    # show up as a POSITIVE percentage with a REFUSE beside it.
    from taxi_mlops.training.gate import INCUMBENT_MAE_DECIMALS, improvement_pct

    vs_incumbent = improvement_pct(
        round(verdict["challenger_mae"], INCUMBENT_MAE_DECIMALS), verdict["incumbent_mae"])
    incumbent_failed = [r for r in verdict["reasons"]
                        if not r["passed"] and "serving champion" in r["check"]]
    if vs_incumbent < 0 and incumbent_failed:
        ok(f"this recorded verdict needs no era table: it is {vs_incumbent:+.2f}% against the "
           f"serving champion, so it is REFUSED under the non-regression bar in force when it "
           f"was taken AND under M9-S10's {float(load_train_config('configs/train.yaml')['gate']['incumbent_min_improvement_pct']):.2f}% margin — "
           f"{len(incumbent_failed)} incumbent condition(s) failed then and would fail now")
    else:
        no(f"the retrain's recorded refusal is era-DEPENDENT: {vs_incumbent:+.4f}% vs the "
           f"incumbent with failing incumbent condition(s) {[r['check'] for r in incumbent_failed]} "
           "— a verdict whose meaning changed under the F-016 landing is a finding, never an edit")

    # (b) F-020's TRANSFER, re-derived on both sides. A hyperparameter is a
    # number PLUS the scale it means it at, and the check is that the FRACTION
    # the knob represents is preserved.
    rescale = rec["rescale"]
    factor = rec["target_rows"] / rescale["chosen_at_rows"]
    moves = rescale["moves"]
    bad = [m for m in moves
           if abs(m["from"] * factor - m["to"]) > 1
           or abs(m["one_row_in_at_choice"] - m["one_row_in_after"]) > 1e-3]
    if moves and abs(factor - rescale["factor"]) < 1e-6 and not bad:
        mv = moves[0]
        ok(f"the count-scaled knob was re-derived at the scale it is USED at: {mv['knob']} "
           f"{mv['from']} -> {mv['to']} (x{factor:.4f} = {rec['target_rows']:,} / "
           f"{rescale['chosen_at_rows']:,}), i.e. 1 row in {mv['one_row_in_at_choice']:.0f} where "
           f"it was chosen and 1 in {mv['one_row_in_after']:.0f} after — against 1 in "
           f"{mv['one_row_in_if_unchanged']:.0f} if it had travelled unchanged")
    else:
        no(f"the rescale does not reconcile: recorded factor {rescale['factor']}, derived "
           f"{factor}, non-conforming moves {bad}")

    # (c) …and everything NOT count-scaled is recorded as passed through.
    # "Considered and it does not scale" and "never looked" are different
    # statements, and only one of them is checkable.
    scaled = set(rescale["count_scaled_knobs"])
    tuned = set(rec["params"]["tuned"])
    moved = {m["knob"] for m in moves}
    passthrough = tuned - moved
    if moved <= scaled and passthrough:
        ok(f"{len(moved)} knob(s) rescaled and {len(passthrough)} recorded as passed through "
           f"({', '.join(sorted(passthrough))}) — the rule is declared as a named set, so a knob "
           f"nobody thought about cannot be mistaken for one that was considered")
    else:
        no(f"knobs moved={sorted(moved)} outside the declared count-scaled set {sorted(scaled)}")

    # (d) The round budget was RE-DERIVED, and the fit reports which end it hit —
    # the half a metrics table cannot show. The champion's own refit ended
    # 791/800 and cannot tell converged from truncated; this one can.
    rb, fit = rec["round_budget"], rec["fit"]
    if rb["inherited_cap"] * rb["headroom"] == rb["derived"] \
            and fit["best_iteration"] < rb["derived"] and fit["ended_by"] == "early_stopping" \
            and fit["truncated"] is False:
        ok(f"the round budget re-derives ({rb['inherited_cap']} x {rb['headroom']} = "
           f"{rb['derived']}, floored at the configured {rb['configured']}) and the fit reports "
           f"ended_by={fit['ended_by']!r} at {fit['best_iteration']} of {rb['derived']} — "
           f"{rb['derived'] - fit['best_iteration']} rounds unspent, so this challenger is "
           f"unambiguously NOT truncated")
    else:
        no(f"round budget {rb} vs fit {fit}")

    # (e) THE PREDICTION WAS WRITTEN BEFORE THE FIT, and that is the only thing
    # that makes a repeat of a 27-minute fit evidence rather than a do-over.
    # The two files are different SHAPES on purpose — one is a human's claim,
    # the other a machine's report — so the mapping between them lives in
    # `scripts/retrain_prediction_check.py` and is imported rather than
    # re-implemented. A second copy of that map would be a twin, and the gate
    # would be checking its own convention instead of the number.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_rpc", "scripts/retrain_prediction_check.py")
    rpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rpc)

    pred = json.loads(Path("automation/runs/m7-retrain/rerun-prediction.json").read_text())
    exact = pred["predicted_exactly"]
    broken = []
    for key, expected in exact.items():
        resolver = rpc.EXACT_RESOLVERS.get(key)
        if resolver is None:
            if key in rpc.STRUCTURAL:
                shape = rpc.STRUCTURAL[key]
                if shape == "incumbent_only":
                    held, detail = rpc._structural_incumbent_only(rec)
                    if not held:
                        broken.append((key, detail, expected))
            continue
        try:
            actual = resolver(rec)
        except Exception as exc:  # noqa: BLE001
            broken.append((key, f"unresolvable: {exc}", expected))
            continue
        if isinstance(expected, float) and isinstance(actual, (int, float)):
            if round(float(actual), rpc._decimals(expected)) != expected:
                broken.append((key, actual, expected))
        elif actual != expected:
            broken.append((key, actual, expected))
    resolved = sum(1 for k in exact if k in rpc.EXACT_RESOLVERS or k in rpc.STRUCTURAL)
    if when(pred["written_at"]) < when(rec["generated_at"]) and resolved >= 15 and not broken:
        ok(f"all {resolved} claims written at {pred['written_at']} hold in a record generated at "
           f"{rec['generated_at']} — compared at the precision the PREDICTION was written to, and "
           f"two MLflow runs of one configuration agreeing to the last kept digit is this "
           f"program's second determinism observation")
    else:
        no(f"prediction written {pred['written_at']} vs record {rec['generated_at']}; "
           f"{resolved} claim(s) resolvable; claims that did not hold: {broken}")

    # (f) IT CANNOT PROMOTE, AND THAT IS STRUCTURAL. A law with a keyword
    # argument is a default. ast, never a grep: the module argues this at length.
    src = Path("src/taxi_mlops/training/retrain_run.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "retrain")
    params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    forced = [n for n in ast.walk(fn)
              if isinstance(n, ast.keyword) and n.arg == "promote"
              and isinstance(n.value, ast.Constant) and n.value.value is False]
    if "promote" not in params and forced:
        ok(f"retrain() has NO `promote` parameter and passes promote=False unconditionally "
           f"({len(forced)} call site(s)) — an unattended job that can move @champion can put an "
           f"unreviewed model in front of riders at 04:00, so the refusal is in the signature")
    else:
        no(f"retrain() parameters {sorted(params)}; forced promote=False call sites: {len(forced)}")

    # (g) THE ALIAS LAW IN ITS STRONG FORM, live. "Is @champion still 2?" is
    # satisfiable by not looking. This is not: a promotion must CREATE a version,
    # and a version carries its run.
    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    exp = client.get_experiment_by_name(rec["experiment"])
    runs = client.search_runs([exp.experiment_id], max_results=1000) if exp else []
    versions = client.search_model_versions(f"name='{reg['model_name']}'")
    version_runs = {v.run_id for v in versions}
    leaked = [r.info.run_id for r in runs if r.info.run_id in version_runs]
    if runs and not leaked:
        ok(f"not one of the {len(runs)} run(s) the retrain fitted in experiment "
           f"{rec['experiment']!r} is a registry version — a promotion cannot hide from that, "
           f"because it must create a version and a version carries its run")
    else:
        no(f"run(s) from the retrain experiment are registry versions: {leaked}")

    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    bakeoff = json.loads(Path("automation/runs/m3s5/bakeoff.json").read_text())
    winner_run = next((c["run_id"] for c in bakeoff["contenders"]
                       if c["label"] == bakeoff["winner"]), None)
    ungated = [v.version for v in versions if v.tags.get("gate_verdict") != "PROMOTE"]
    if winner_run and champion.run_id == winner_run and not ungated:
        ok(f"@{reg['champion_alias']} is version {champion.version}, still the run the M3 bake-off "
           f"recorded as its winner, and all {len(versions)} version(s) carry gate_verdict=PROMOTE "
           f"— the challenger stayed a run, and the pointer never moved (derived, never typed)")
    else:
        no(f"@{reg['champion_alias']} -> {champion.run_id[:12]}… against the bake-off's "
           f"{str(winner_run)[:12]}…; versions with no PROMOTE verdict: {ungated}")

    # (h) F-022: the bake-off's incumbent cell reads its feature set off the
    # LOADED model. Pre-registration is right for a thing declared before its
    # number existed and exactly wrong for a pointer designed to move.
    bake_src = Path("scripts/bakeoff_m3.py").read_text()
    bake_tree = ast.parse(bake_src)
    derives = any(isinstance(n, ast.FunctionDef) and n.name == "_feature_set_of"
                  for n in ast.walk(bake_tree))
    alias_specs = [n for n in ast.walk(bake_tree)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "Spec"
                   and any(k.arg == "feature_set" and isinstance(k.value, ast.Constant)
                           and k.value.value is None for k in n.keywords)]
    if derives and alias_specs:
        ok(f"the bake-off derives the incumbent's feature set from the loaded artifact "
           f"(_feature_set_of) and its alias row pre-registers feature_set=None — F-022's cause "
           f"was a pointer designed to move carrying a label true only on the day it was written")
    else:
        no(f"bake-off: derives-from-artifact={derives}, alias rows with feature_set=None="
           f"{len(alias_specs)}")

    # (i) The schedule is declared IN CODE with its inputs, and the expensive
    # trigger is registered INACTIVE on purpose. `flyte create trigger` cannot
    # pass inputs, so a CLI-created trigger would fire the retrain with defaults.
    wf = ast.parse(Path("pipelines/flyte/workflows.py").read_text())
    triggers = {}
    for node in ast.walk(wf):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and getattr(node.value.func, "attr", "") == "Trigger":
            kw = {k.arg: k.value for k in node.value.keywords}
            name = getattr(kw.get("name"), "value", None)
            triggers[name] = {
                "inputs": kw.get("inputs") is not None,
                "auto_activate": getattr(kw.get("auto_activate"), "value", True),
            }
    inactive = [n for n, t in triggers.items() if t["auto_activate"] is False]
    inputless = [n for n, t in triggers.items() if not t["inputs"]]
    if len(triggers) >= 2 and inactive and not inputless:
        ok(f"{len(triggers)} trigger(s) are declared in code WITH their inputs "
           f"({', '.join(sorted(triggers))}) and {len(inactive)} is registered inactive "
           f"({', '.join(inactive)}) — hours of CPU on a laptop nobody watches is a PO's call "
           f"about compute, and turning it on is one field")
    else:
        no(f"triggers={triggers}; inactive={inactive}; declared without inputs={inputless}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the retrain check itself raised {type(exc).__name__}: {exc}")
PY
)
# 10 from M9-S10: the era-stability sub-check (a2). Re-DERIVED by running the
# leg; the bound is "at least" and exists to catch a leg that died on import.
expect_verdicts 10 "the retrain check"

# ------------------------------------- 7. the memo, the board, the champion ---
section "7. the memo against the records, the board that renders it, and the champion still on the wire"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import yaml

    memo_path = Path("docs/drift_memo_m7.md")
    memo = memo_path.read_text()
    root = Path("automation/runs/m7-drift")
    drift = {p.stem.replace("drift-", ""): json.loads(p.read_text())
             for p in root.glob("drift-*.json")}
    headroom = json.loads((root / "headroom.json").read_text())

    # (a) THE PROSE LEG. Every number the memo's instrument table quotes must be
    # in the record it cites, compared AT THE PRECISION THE DOCUMENT WROTE, with
    # a floor of one decimal for non-integers.
    #
    # The floor is gotcha #90's, learned by `verify-m6`'s own first run: 13.75
    # rendered at zero decimals is `14`, which appears in almost any document, so
    # a planted value rendered the same way matches too. The precision rule is
    # gotcha #76's sibling from the other side: DuckDB prints 1.061 where a
    # padded table writes 1.0610, so trailing zeros are stripped on both sides.
    def written(value, text, minimum_decimals=1):
        forms = {f"{value}"}
        for dp in range(minimum_decimals, 7):
            rendered = f"{value:.{dp}f}"
            if float(rendered) == 0 and value != 0:
                continue
            forms.add(rendered)
            # Trailing zeros stripped on BOTH sides: DuckDB prints 1.061 where a
            # padded table writes 1.0610, and the document is allowed either.
            forms.add(rendered.rstrip("0").rstrip("."))
            # …and a document is allowed to group its thousands. A number the
            # memo writes as 202,574.4 is the same number.
            whole, _, frac = rendered.partition(".")
            forms.add(f"{int(whole):,}" + (f".{frac}" if frac else ""))
            forms.add(f"{int(whole):,}" + (f".{frac.rstrip('0')}" if frac.rstrip("0") else ""))
        forms.discard("")
        return any(re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d])", text) for f in forms)

    checked, absent = 0, []
    for month, rec in sorted(drift.items()):
        for label, value, dp in (("volume ratio", rec["volume_ratio"], 1),
                                 ("max input PSI", rec["max_input_psi"], 1),
                                 ("trips/day", rec["current_trips_per_day"], 1)):
            checked += 1
            if not written(value, memo, dp):
                absent.append(f"{month} {label}={value}")
        checked += 1
        if f"{rec['current_rows']:,}" not in memo:
            absent.append(f"{month} rows={rec['current_rows']:,}")
    for month, rec in sorted(headroom.items()):
        checked += 1
        if not written(rec["volume_ratio"], memo, 1):
            absent.append(f"{month} headroom volume ratio={rec['volume_ratio']}")
    if not absent:
        ok(f"all {checked} instrument number(s) {memo_path} quotes are held by the record it "
           f"cites, at the precision the document wrote them (floor: one decimal — gotcha #90, "
           f"because 13.75 rendered at zero decimals is `14` and matches anything)")
    else:
        no(f"the memo quotes number(s) no record holds: {absent}")

    # (b) §9/M7 asks the memo to CITE the predictions table. It must name the
    # mart, not merely describe an error series.
    kpi_cited = sorted(set(re.findall(r"KPI-1[4-7]", memo)))
    if "scoring_daily" in memo and len(kpi_cited) >= 3:
        ok(f"the memo cites the predictions table by name (marts.scoring_daily) and reads it "
           f"through {len(kpi_cited)} monitoring ids ({', '.join(kpi_cited)}) — §9/M7's 'the DA "
           f"memo cites it', answered with the mart rather than with a re-computation")
    else:
        no(f"the memo names scoring_daily={('scoring_daily' in memo)}, monitoring ids cited="
           f"{kpi_cited}")

    # (c) …and it never PUBLISHES A VALUE under a promotion id. The ban is not on
    # the string: a monitoring memo is entitled — obliged, really — to say out
    # loud that KPI-09/KPI-10 belong to the held-out split and are not what is
    # being reported here. What it may not do is attach a number to one, which is
    # what would make a board's history stop meaning one thing (gotcha #15).
    # The ids themselves are stripped out of the window first — otherwise the
    # sentence "KPI-09/KPI-10 belong to the held-out split" reads as a value,
    # because `KPI-10` contains `10`. Gotcha #76's family: the needle must not
    # match inside the token that names it.
    valued = []
    for m in re.finditer(r"KPI-(?:09|10)\b[^.\n]{0,60}", memo):
        window = re.sub(r"KPI-\d\d", "", m.group(0))
        if re.search(r"\d+\.\d+|\d{2,}", window):
            valued.append(m.group(0))
    if not valued:
        mentions = len(re.findall(r"KPI-(?:09|10)\b", memo))
        ok(f"no value is published under a promotion id anywhere in the memo ({mentions} mention(s), "
           f"all of them saying those ids belong to the held-out split) — the ban is on attaching "
           f"a number, not on naming the id it may not be attached to")
    else:
        no(f"the memo attaches a value to a promotion id: {valued}")

    # (d) The memo has a TWIN SCRIPT (the M2-S4 precedent). A memo nobody can
    # re-run is a memo nobody can check.
    twin = Path("scripts/drift_memo_numbers.py")
    memo_sections = set(re.findall(r"^##\s*§(\d)", memo, re.M))
    twin_sections = set(re.findall(r"§?(\d)", twin.read_text())) if twin.exists() else set()
    if twin.exists() and memo_sections <= twin_sections:
        ok(f"the memo has a runnable twin ({twin}) covering all {len(memo_sections)} of its "
           f"numbered sections — every figure comes from a named view or mart, and the script "
           f"prints the SQL it ran")
    else:
        no(f"twin exists={twin.exists()}; memo sections {sorted(memo_sections)} not all covered "
           f"by {sorted(twin_sections)}")

    # (e) THE BOARD. Checked-in JSON, monitoring ids only, and the two laws that
    # are specific to a monitoring board.
    board = json.loads(Path("analytics/metabase/boards/predictions_drift.json").read_text())
    cards = board["cards"]
    # The forbidden-column scan reads the SQL and ONLY the SQL. A card's own
    # description legitimately writes prose about the daily series being "flat at
    # its floor from the 22nd", and a check that searched the whole card object
    # would go red on an English word — gotchas #53/#68, in a JSON document.
    sql_all = " ".join(c.get("sql", "") for c in cards)
    labels_all = " ".join(json.dumps(c) for c in cards)
    board_ids = sorted(set(re.findall(r"KPI-1[4-7]", labels_all)))
    board_promo = sorted(set(re.findall(r"KPI-(?:09|10)\b", labels_all)))
    forbidden = sorted(set(re.findall(r"\b(floor|margin|kpi_13)\b", sql_all)))
    if cards and not board_promo and not forbidden:
        ok(f"the board carries {len(cards)} cards citing only monitoring ids ({', '.join(board_ids)}), "
           f"no KPI-09/KPI-10 anywhere, and no floor/margin/kpi_13 column in any card's SQL — the "
           f"comparison §6.1 refuses to publish cannot arrive through a card")
    else:
        no(f"board promotion ids={board_promo}; forbidden columns={forbidden}")

    # (f) KPI-16 must be present AND be a series. An absolute error cannot tell a
    # model quoting three minutes too long from one quoting three minutes too
    # short, and in a collapsed month those are opposite diagnoses.
    bias_cards = [c for c in cards if "KPI-16" in json.dumps(c)]
    daily = [c for c in cards
             if re.search(r"pickup_date", json.dumps(c))
             and not re.search(r"group\s+by\s+month\b", json.dumps(c), re.I)]
    if bias_cards and len(daily) >= 3:
        ok(f"KPI-16 (signed bias) is on the board ({len(bias_cards)} card(s)) and {len(daily)} "
           f"card(s) plot the DAILY grain — a monthly row is a GROUP BY away from daily rows and "
           f"the reverse is not true, which is the whole finding this board exists to render")
    else:
        no(f"KPI-16 cards={len(bias_cards)}, daily-grain cards={len(daily)}")

    # (g) THE ONE LIVE PREDICTION. A gate that never asks the service for the
    # artifact it exists to produce would pass against a dead model with a
    # healthy Ready condition (gotchas #59/#71).
    import mlflow

    from taxi_mlops.serving import client as client_mod
    from taxi_mlops.serving import parity as parity_mod
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    champion = mlflow.MlflowClient().get_model_version_by_alias(
        reg["model_name"], reg["champion_alias"])
    isvc_manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    isvc = re.search(r"^\s+name:\s*(\S+)", isvc_manifest, re.M).group(1)
    ns = re.search(r"^\s+namespace:\s*(\S+)", isvc_manifest, re.M).group(1)
    hazard = parity_mod.HAZARDS[0]
    response = client_mod.infer([hazard.request], client_mod.Endpoint(name=isvc, namespace=ns))
    served = str(response.get("model_version", ""))
    minutes = float(client_mod.minutes_of(response)[0])
    parity = json.loads(Path("automation/runs/m5-parity/parity.json").read_text())
    row = next((r for r in parity["results"] if r["hazard"] == hazard.name), None)
    if served == str(champion.version) and row \
            and abs(row["online_minutes"] - minutes) <= parity["tolerance_minutes"]:
        ok(f"the endpoint answered {minutes:.6f} minutes stamped model_version={served!r} — equal "
           f"to what the alias resolves to, reproducing the parity record's {hazard.name!r} row to "
           f"{abs(row['online_minutes'] - minutes):.3e} minutes. M7 ended where M6 did")
    else:
        no(f"the endpoint stamped {served!r} against alias version {champion.version}, quoting "
           f"{minutes:.6f} against the record's {row['online_minutes'] if row else 'no row'}")

    # (h) F-032's invariant, still live: the served version's feature set must be
    # the one every client builds its matrix from. A half-finished rollback is
    # otherwise a 500 nobody can attribute.
    train_cfg = yaml.safe_load(Path("configs/train.yaml").read_text())
    configured = train_cfg["features"]["version"]
    if champion.tags.get("feature_set") == configured:
        ok(f"the served version's feature_set tag ({champion.tags['feature_set']}) equals "
           f"configs/train.yaml's features.version ({configured}) — the invariant F-032 found "
           f"nothing enforcing, and M7 did not move either half")
    else:
        no(f"version {champion.version} eats {champion.tags.get('feature_set')!r} while every "
           f"client builds {configured!r} — a half-finished rollback")

    # (i) The ledgers carry M7. A wire mutation with no row is a change nobody
    # can review, and a milestone with no signoff row is a milestone nobody owned.
    deployments = Path("ledgers/deployments.md").read_text()
    rows = {s for s in re.findall(r"M7-S(\d)", deployments)}
    if rows >= {"1", "3", "4", "5"}:
        ok(f"the deployments ledger carries a row for every M7 story that touched the wire "
           f"(M7-S{', M7-S'.join(sorted(rows))}) — S2 is host-side batch scoring and mutated "
           f"nothing on the cluster")
    else:
        no(f"the deployments ledger names only M7-S{sorted(rows)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the closing check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the closing check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m7] GREEN — every M7 sub-check passed.\033[0m\n'
  printf '            Show: the two signatures    docs/scoring_months_m7.md §8 · docs/drift_detection_m7.md §8\n'
  printf '                  the predictions table marts.scoring_daily · data/scoring_predictions/scoring_predictions.json\n'
  printf '                  the memo              docs/drift_memo_m7.md · scripts/drift_memo_numbers.py\n'
  exit 0
fi
printf '\033[31m[verify-m7] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS"
exit 1
