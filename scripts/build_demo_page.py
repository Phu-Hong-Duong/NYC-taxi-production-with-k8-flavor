"""Generate `demo/index.html` from its template, the TLC zone lookup and the server's schema.

M9-S1. The kickoff's honesty requirement, in one sentence: *the zone list must be
DERIVED from `data/reference/taxi_zone_lookup.csv` — a hand-retyped list is a
twin that drifts.* This repo has spent whole sessions on twins (the port family,
`MARTS=(…)`, the two spellings of a record path), so the demo page does not get
to start life as one.

THREE THINGS ARE SUBSTITUTED, and each has a different failure mode if it drifts:

* **the 265 zone options** — from the lookup CSV, the same file
  `taxi_mlops.features.zones` reads. Drift here shows up as a picker offering a
  zone the model has never heard of, or omitting one it has.
* **the request schema** — from `taxi_mlops.serving.transformer.RAW_INPUTS`, the
  dict the SERVER decodes with. A page that misspelled a field NAME would be
  refused loudly (`decode_raw` refuses unknown inputs rather than ignoring them
  — that refusal exists for exactly this reason). A page that got a DATATYPE
  wrong would not be: it would quote a plausible number nobody could see was
  wrong, which is the failure class this program keeps finding and keeps
  refusing to leave available.
* **the default trip** — the hazard row every parity record in this repo already
  carries (JFK 132 -> Clinton East 48, 2019-07-04T09:15:00, one passenger),
  whose published answer is 39.0019 minutes at model version 2. It is here, and
  not in the template's markup, so that `scripts/demo_accept.py` can read the
  page's OWN opening payload instead of retyping it.

`--check` regenerates in memory and diffs against the committed file, which is
what `make demo-page-check` and the unit test both use. Regeneration is
deterministic: no timestamp, no host, no ordering that depends on a dict's
insertion history beyond the CSV's own row order.

TLC's two NON-PLACES (264 "Unknown", 265 "Outside of NYC") are RENDERED, in
their own group, labelled as what they are. The kickoff allowed either excluding
them with a note or letting them demonstrate the no-geometry path honestly, and
the second is the better demo: they are ~1% of every split, 264->264 is the
largest single OD "route" in the data, they carry no centroid by DR-04 condition
1, and F-030 was found on exactly this path. A picker that hides them would make
the demo look tidier than the world it quotes for.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.transformer import RAW_INPUTS  # noqa: E402

TEMPLATE = REPO / "demo" / "index.template.html"
OUTPUT = REPO / "demo" / "index.html"
LOOKUP = REPO / "data" / "reference" / "taxi_zone_lookup.csv"

#: The opening state of the form. Not arbitrary: `taxi_mlops.serving.parity`
#: hazard 1, whose answer is published in `docs/parity_m5.md`,
#: `docs/transformer_parity_table.md` and both M8 accept records.
DEFAULT_TRIP = {
    "pickup_datetime": "2019-07-04T09:15:00",
    "pu_location_id": 132,
    "do_location_id": 48,
    "passenger_count": 1,
}

#: Boroughs that name a place. Everything else in the CSV's Borough column is
#: TLC bookkeeping and goes in the last group under its own heading.
NON_PLACE_IDS = (264, 265)


def zone_rows() -> list[dict[str, str]]:
    with LOOKUP.open(newline="") as fh:
        return list(csv.DictReader(fh))


def render_options(rows: list[dict[str, str]]) -> str:
    """<optgroup> per borough in the CSV's own order, non-places last and named."""
    groups: dict[str, list[tuple[int, str]]] = {}
    non_places: list[tuple[int, str]] = []
    for row in rows:
        location_id = int(row["LocationID"])
        label = f"{row['Zone']} ({row['Borough']})"
        if location_id in NON_PLACE_IDS:
            non_places.append((location_id, row["Zone"]))
        else:
            groups.setdefault(row["Borough"], []).append((location_id, label))

    out: list[str] = [""]
    for borough in sorted(groups):
        out.append(f'      <optgroup label="{escape(borough)}">')
        for location_id, label in sorted(groups[borough], key=lambda pair: pair[1]):
            out.append(f'        <option value="{location_id}">{escape(label)}</option>')
        out.append("      </optgroup>")
    out.append('      <optgroup label="TLC bookkeeping — not places (no geometry)">')
    for location_id, zone in non_places:
        out.append(
            f'        <option value="{location_id}">{escape(zone)} '
            f"— zone {location_id}, no centroid</option>"
        )
    out.append("      </optgroup>")
    out.append("    ")
    return "\n".join(out)


def render_schema() -> str:
    """`RAW_INPUTS` as the JS array the page encodes with — order preserved."""
    entries = [
        {"name": name, "datatype": datatype, "field": field}
        for name, (datatype, field) in RAW_INPUTS.items()
    ]
    body = ",\n".join("  " + json.dumps(entry, sort_keys=True) for entry in entries)
    return "[\n" + body + "\n]"


#: token -> how many times it may legitimately appear in the template. The counts
#: are asserted, not assumed, because this generator's FIRST run substituted the
#: tokens inside the template's own explanatory comment and produced a page with
#: three copies of every picker — a page that renders, scrolls oddly, and is
#: wrong in a way no assertion about "the zone list matches the CSV" would catch.
#: Prose sitting where a parser reads it as code is gotcha #53/#60; this is the
#: cheapest possible guard against it recurring.
TOKEN_COUNTS = {"ZONE_OPTIONS": 2, "RAW_INPUT_SCHEMA": 1, "DEFAULT_TRIP": 1}


def build() -> str:
    rows = zone_rows()
    page = TEMPLATE.read_text()
    values = {
        "ZONE_OPTIONS": render_options(rows),
        "RAW_INPUT_SCHEMA": render_schema(),
        "DEFAULT_TRIP": json.dumps(DEFAULT_TRIP, indent=2, sort_keys=True),
    }
    for name, expected in TOKEN_COUNTS.items():
        token = "{{" + name + "}}"
        found = page.count(token)
        if found != expected:
            raise SystemExit(
                f"[demo-page] FAIL: the template contains {token} {found} time(s), "
                f"expected {expected}. If that is a deliberate change, move the count in "
                "TOKEN_COUNTS; if it is a mention in a comment, name the token without "
                "its braces — the generator cannot tell prose from a slot."
            )
        page = page.replace(token, values[name])
    if "{{" in page:
        leftover = page[page.index("{{") : page.index("{{") + 40]
        raise SystemExit(f"[demo-page] FAIL: an unsubstituted token remains: {leftover!r}")
    return page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and diff against the committed page; write nothing",
    )
    args = parser.parse_args()

    page = build()
    rows = zone_rows()
    if args.check:
        if not OUTPUT.exists():
            print(f"[demo-page] FAIL: {OUTPUT.relative_to(REPO)} does not exist")
            return 1
        current = OUTPUT.read_text()
        if current != page:
            print(
                f"[demo-page] FAIL: {OUTPUT.relative_to(REPO)} is not what the template plus "
                f"{LOOKUP.relative_to(REPO)} plus transformer.RAW_INPUTS generate.\n"
                "[demo-page]   Run 'make demo-page' and commit the result — the page is "
                "generated so the zone list cannot be a twin of the CSV."
            )
            return 1
        print(f"[demo-page] ok  {OUTPUT.relative_to(REPO)} matches its sources ({len(rows)} zones)")
        return 0

    OUTPUT.write_text(page)
    print(
        f"[demo-page] wrote {OUTPUT.relative_to(REPO)} — {len(rows)} zones from "
        f"{LOOKUP.relative_to(REPO)}, {len(RAW_INPUTS)} raw inputs from transformer.RAW_INPUTS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
