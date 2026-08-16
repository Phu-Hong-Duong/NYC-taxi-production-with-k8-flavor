"""Flyte workflow definitions — thin wrappers ONLY. Owner milestone: M3.

Rule: every task body is `return taxi_mlops.<fn>(...)` plus resource/cache
declarations. Zero logic lives here — this is what makes ADR-002's fallback (and
any future orchestrator swap) decorator-deep instead of a rewrite.

Shape (implement at M3 against the Flyte version pinned in CLAUDE.md):
  ingest(month) -> validate -> features -> train -> evaluate -> maybe_promote
Cache: ingest/features keyed on (month, code version). Retries: 2 on transient.
"""
