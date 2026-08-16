"""Typed refusals. Ingest says no with a named error and a filename in it.

A bare ValueError from deep in pandas is not a refusal, it is an accident. Every
way this package can decline to hand data downstream has a class here, and every
message names the artifact that caused it.
"""


class IngestError(Exception):
    """Base: ingest refused. Any subclass = nonzero exit, nothing written."""


class CorruptSourceError(IngestError):
    """The raw file cannot be read as parquet (truncated, wrong bytes, empty)."""


class ChecksumDriftError(IngestError):
    """A raw file on disk no longer matches its manifest sha256.

    Gotcha #6: TLC backfills months in place. A silent overwrite would break
    every rebuild proof downstream, so the drift is an event, not a refresh.
    """


class SchemaEventError(IngestError):
    """A column appeared, vanished, or was renamed (DE charter: a schema change is an EVENT)."""


class DataContractError(IngestError):
    """The pandera contract rejected the frame (dtype/range/nullability)."""


class RejectionThresholdError(IngestError):
    """More rows were dropped than configs/data.yaml allows for one month."""
