"""Ingestion, validation, splitting. Owner milestone: M1.

Contracts (implement at M1; signatures are the spec):
- download_month(month: str, dest: Path) -> Path
    TLC parquet from the verified URL pattern; checksum recorded; retry w/ backoff.
- validate(df: DataFrame, month: str) -> DataFrame
    pandera, YEAR-AWARE schema (gotcha #6/#7); rejects loudly with counted reasons.
    All dtype casting happens HERE and nowhere else.
- clean_and_split(df) -> dict[str, DataFrame]
    duration target derived; impossible rows rejected WITH COUNTS; deterministic.
"""
