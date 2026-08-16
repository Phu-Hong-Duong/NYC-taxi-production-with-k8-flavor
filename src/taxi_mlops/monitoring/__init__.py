"""Drift + metrics emission. Owner milestone: M6.

ALL Evidently imports quarantined here (gotcha #13 — API churn hits one file).
- drift_report(reference, current, cfg) -> report + drift_share float
- push_metrics(drift_share, labels): -> Pushgateway (fed to Grafana alert)
Schema drift is NOT handled here — pandera in data/ catches it earlier, with a
deliberately DIFFERENT failure signature (BLUEPRINT M6 accept-when).
"""
