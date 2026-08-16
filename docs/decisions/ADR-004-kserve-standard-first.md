# ADR-004 — KServe Standard mode first; canary mechanism decided by M5 spike
- Status: accepted
- Date: 2026-08-12
- Context: KServe v0.18 (checked 2026-08-12) documents Standard install as
  lightweight explicitly WITHOUT canary/autoscaling; Knative install provides them.
- Choice: Standard at M4 (model on the wire, minimal ops). M5 opens with a
  timeboxed 30-min spike — enable Knative profile vs two-isvc split — outcome
  recorded as ADR-006.
- Honest cost: serving gets re-deployed once at M5; accepted for M4 simplicity.
