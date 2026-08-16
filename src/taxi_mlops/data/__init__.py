"""Ingestion, validation, splitting. Owner milestone: M1 (S1 landed the ingest path).

Entry point: `python -m taxi_mlops.data ingest` (`make ingest`).

Implemented contracts:
- `download.ensure_month(cfg, month, manifest) -> str`
    TLC parquet from the configured URL pattern; skip-if-present; retried with
    backoff; sha256 pinned in `data/raw_manifest.json`. Bytes that disagree with
    the pin are an EVENT (ChecksumDriftError), never a silent refresh.
- `contract.validate_input(df, month, cfg) -> (DataFrame, events)`
    Year-aware pandera structure check (gotcha #6) and THE dtype cast — all
    casting happens here and nowhere else in the codebase (gotcha #7).
    Unknown/renamed/vanished columns are announced or refused, never silent.
- `clean.clean(df, month, cfg) -> (DataFrame, RejectionReport)`
    Target derived; impossible rows dropped against NAMED rules with counts on
    both attributions; a month that loses more than the configured fraction is
    refused outright.
- `contract.validate_output(df, month, cfg) -> DataFrame`
    What downstream is promised — and a live check on the cleaning rules.

Departure from the M0 stub signature, recorded on purpose: the stub specified
`clean_and_split(df) -> dict[str, DataFrame]`, written before the data was
observed. Splits here are month-partitioned (configs/train.yaml assigns whole
months), so a month IS its split and concatenating ~60M rows to re-partition
them would buy nothing but memory pressure. Cleaning is therefore per month, and
`config.Splits.split_of()` routes the output to `data/processed/<split>/`.
"""
