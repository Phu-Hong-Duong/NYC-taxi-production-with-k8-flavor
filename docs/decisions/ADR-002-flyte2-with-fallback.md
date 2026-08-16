# ADR-002 — Flyte 2.x primary; flyte-binary 1.16.x is the pre-approved fallback
- Status: accepted
- Date: 2026-08-12
- Context: two maintained lines (v2.0.24 / v1.16.7, checked 2026-08-12); v2 is the
  docs default with a documented kind path, but young.
- Choice: build on 2.x. Fallback executes WITHOUT a new decision if M3 hits the
  three-attempt wall on deployment or MLflow interop.
- Honest cost: ~25% chance the fallback fires and costs a session; mitigated by the
  orchestrator-agnostic src/ rule making the swap decorator-deep only.
- Revisit trigger: the wall firing, or Flyte 1.x EOL announcement.
