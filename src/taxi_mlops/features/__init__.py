"""Feature transforms — THE single shared path for training AND serving. M1/M2.

Train/serve skew is prevented structurally: serving imports these same functions;
the M4 parity test then proves it. Keep transforms pure (DataFrame -> DataFrame),
config-driven, no I/O.
- build_features(df, cfg) -> DataFrame
- feature_names(cfg) -> list[str]

Landed at M2-S2 (role:MLE) as feature set v1, quote-time pure. The interesting
half is not what it builds but what it REFUSES to: `quote_time.EXCLUSIONS` names
every rejected column with its reason, and `FeatureLeakageError` is raised rather
than a warning printed, because the failure it prevents (a model that scores
beautifully and cannot be served) passes every offline check.
"""

from .quote_time import (
    EXCLUDED_COLUMNS,
    EXCLUSIONS,
    REQUEST_TIME_SOURCE,
    Exclusion,
    FeatureLeakageError,
    assert_quote_time_pure,
    build_features,
    categorical_names,
    feature_names,
)

__all__ = [
    "EXCLUDED_COLUMNS",
    "EXCLUSIONS",
    "REQUEST_TIME_SOURCE",
    "Exclusion",
    "FeatureLeakageError",
    "assert_quote_time_pure",
    "build_features",
    "categorical_names",
    "feature_names",
]
