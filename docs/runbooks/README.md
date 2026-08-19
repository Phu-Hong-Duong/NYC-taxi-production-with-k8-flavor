# Runbooks — written at first successful execution, rehearsed once, traps first.
LIVE: **serving.md** (M5-S5) — the ETA endpoint: deploy · stop/start (rehearsed,
3.12 s / 18.24 s) · **rollback TYPED and NOT rehearsed** · cheapest-causes-first
failure table · what is refused on purpose · what a lost pod costs (14.53 s).
Its numbers are cross-checked against the records by `make verify-m5` §6, so a
quoted hope is a RED gate.
Planned: deploy.md (M4) · canary.md (M6, with the rehearsed revert — ADR-004's
spike decides the mechanism) · teardown.md (M0) · stuck-namespace.md (on first
occurrence).
