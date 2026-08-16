"""Feature transforms — THE single shared path for training AND serving. M1/M2.

Train/serve skew is prevented structurally: serving imports these same functions;
the M4 parity test then proves it. Keep transforms pure (DataFrame -> DataFrame),
config-driven, no I/O.
- build_features(df, cfg) -> DataFrame
- feature_names(cfg) -> list[str]
"""
