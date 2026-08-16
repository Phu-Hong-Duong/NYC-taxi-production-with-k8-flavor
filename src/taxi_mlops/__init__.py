"""taxi_mlops — orchestrator-agnostic core.

Structural rule (BLUEPRINT §5): this package NEVER imports Flyte, KServe, or any
orchestrator/server SDK. pipelines/ and serving deployments import us — never the
reverse. MLflow is the one platform client permitted (training/ only).
"""
