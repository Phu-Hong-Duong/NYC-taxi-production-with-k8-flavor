# demo/ — the stakeholder demo page (M9 story; MLOps R, DA C)

Contract (build at M9, per BLUEPRINT §9/M9 [v2.6]):
- ONE self-contained HTML file (inline CSS/JS, no build step, no framework):
  pickup + dropoff zone pickers (human names from the TLC zone lookup CSV),
  date-time picker, submit -> POST to the InferenceService (V2 infer protocol)
  -> ETA in minutes + serving model version displayed.
- CORS wrinkle decided at execution (ingress annotation vs mlserver config);
  record the choice here and in the deploy runbook.
- Acceptance includes a usability observation: one non-technical person (the
  PO counts) completes a query unassisted.
- NEVER on the M5 acceptance path — the terminal parity/latency gates own
  serving truth; this page is the stakeholder face and interview artifact.
