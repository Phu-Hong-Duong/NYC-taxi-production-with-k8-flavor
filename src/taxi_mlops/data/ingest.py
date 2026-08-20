"""Ingest orchestration: acquire -> read -> contract -> clean -> contract -> write.

Write discipline: the parquet lands on a temp sibling and is renamed only after
everything upstream of it succeeded. A refusal therefore leaves NOTHING behind —
no half month, no stale month wearing a fresh timestamp.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .clean import RejectionReport, clean, sort_deterministically
from .config import DataConfig, load_config, repo_root
from .contract import dtypes_table, validate_input, validate_output
from .download import ensure_month, load_manifest, save_manifest
from .errors import CorruptSourceError


def read_raw(path: Path) -> pd.DataFrame:
    """Read raw parquet, converting any reader failure into a typed refusal that names the file."""
    try:
        return pq.read_table(path).to_pandas()
    except Exception as exc:  # pyarrow raises several unrelated types for bad bytes
        raise CorruptSourceError(
            f"{path}: not readable as parquet ({type(exc).__name__}: {exc}). "
            "Nothing was written. Delete the file and re-run to re-download, or "
            "investigate the source before trusting it."
        ) from exc


def write_processed(df: pd.DataFrame, dest: Path, cfg: DataConfig) -> None:
    """Atomic, option-pinned write (S2 proves byte-identity against these options).

    Used for the rejected sidecar too (M2-S1): ONE writer contract, so the
    sidecar is re-derivable on exactly the same terms as the output it explains.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        tmp,
        compression=cfg.write["compression"],
        row_group_size=cfg.write["row_group_size"],
    )
    tmp.replace(dest)


def _display(path: Path) -> str:
    """Repo-relative when it is under the repo, absolute otherwise.

    The absolute branch is not decoration: the unit suite runs ingest against a
    throwaway config under /tmp, and a printer that ASSUMED the repo root used
    to raise ValueError from inside a success message.
    """
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)


def ingest_month(
    month: str, cfg: DataConfig, manifest: dict[str, dict], *, show_dtypes: bool = True
) -> RejectionReport:
    """One month, end to end. Raises an IngestError subclass rather than writing bad data."""
    label = cfg.label_of(month)
    print(f"\n=== {month} ({label}) ===")

    action = ensure_month(cfg, month, manifest)
    raw = cfg.raw_path(month)
    print(f"  raw: {raw.name} [{action}] {raw.stat().st_size:,} bytes")
    print(f"  sha256: {manifest[month]['sha256']}")

    df = read_raw(raw)
    df, events = validate_input(df, month, cfg)
    for event in events:
        print(f"  SCHEMA EVENT: {event}")
    if show_dtypes:
        print("  dtypes after THE cast (contract.cast, the only cast in the codebase):")
        print(dtypes_table(df))

    kept, rejected, report = clean(df, month, cfg)
    print("  rejections (first-violated rule attributed; matched = independent hits):")
    print(report.table())

    kept = sort_deterministically(kept, cfg)
    kept = validate_output(kept, month, cfg)

    # Which TREE this month lands in is the only thing the scoring months change
    # (M7-S1). The acquisition, the contract, the one cast, the rules, the
    # refusals and the writer options above are identical — a scoring month is
    # not a second pipeline, it is the same pipeline pointed somewhere else.
    dest = cfg.output_path(month)
    sidecar = cfg.sidecar_path(month)
    write_processed(kept, dest, cfg)
    report.write(cfg.report_path(month))
    # The sidecar is written LAST and only once the month has survived every
    # refusal above it: a month that is refused leaves nothing behind at all,
    # and that includes its rejects (F-005's own condition, configs/data.yaml).
    # Sorted by the same pinned keys as the output so it is re-derivable too;
    # rows whose timestamps are missing sort last, deterministically.
    rejected = sort_deterministically(rejected, cfg)
    write_processed(rejected, sidecar, cfg)
    print(f"  wrote {_display(dest)}")
    print(f"  wrote {cfg.report_path(month).name}")
    print(f"  wrote {_display(sidecar)} ({len(rejected):,} rejected row(s) retained)")
    return report


def summary_table(reports: list[RejectionReport]) -> str:
    lines = [
        "  month     rows_in       rows_out    rejected      pct",
        "  -------  ------------  ------------  ----------  -------",
    ]
    total_in = total_out = 0
    for r in reports:
        total_in += r.rows_in
        total_out += r.rows_out
        lines.append(
            f"  {r.month}  {r.rows_in:>12,}  {r.rows_out:>12,}  {r.rows_rejected:>10,}"
            f"  {100 * r.rejected_fraction:>6.3f}%"
        )
    pct = 100 * (total_in - total_out) / total_in if total_in else 0.0
    dropped = total_in - total_out
    lines.append("  -------  ------------  ------------  ----------  -------")
    lines.append(f"  {'ALL':<7}  {total_in:>12,}  {total_out:>12,}  {dropped:>10,}  {pct:>6.3f}%")
    return "\n".join(lines)


def ingest(
    months: list[str] | None = None,
    cfg: DataConfig | None = None,
    *,
    scoring: bool = False,
) -> list[RejectionReport]:
    """Ingest the configured months (or a subset). One command, all 8 split months.

    `scoring=True` swaps the DEFAULT work list to `configs/data.yaml:
    scoring.months` (M7-S1). It is a work-list selector and nothing more — an
    explicit `--month` resolves its own tree from config membership either way,
    so the two lists cannot be crossed by a flag.
    """
    cfg = cfg or load_config()
    default = cfg.scoring_months if scoring else cfg.splits.months
    months = list(months) if months else list(default)
    if not months:
        raise ValueError(
            "no months to ingest: configs/data.yaml `scoring.months` is empty"
            if scoring
            else "no months to ingest: configs/train.yaml names no split months"
        )
    manifest_path = cfg.path_for("manifest_path")
    manifest = load_manifest(manifest_path)

    print(f"[ingest] {len(months)} month(s): {', '.join(months)}")
    print(f"[ingest] manifest: {manifest_path}")

    reports: list[RejectionReport] = []
    try:
        for index, month in enumerate(months):
            # The dtypes table is the same for every month of a year; print it once.
            reports.append(ingest_month(month, cfg, manifest, show_dtypes=index == 0))
    finally:
        # Whatever happened, the months that DID land stay pinned.
        save_manifest(manifest_path, manifest)

    print("\n[ingest] per-month summary")
    print(summary_table(reports))
    print(f"[ingest] GREEN — {len(reports)} month(s) ingested, contract enforced, drops counted.")
    return reports
