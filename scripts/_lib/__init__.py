"""Shared python plumbing for `scripts/` — the cluster-facing half (CU-S4).

Four modules, each the ONE home for a thing that was previously re-implemented
per script:

  `ports`       the ephemeral port-forward REGISTRY (was: coordinated by comments)
  `k8s`         the `kubectl` wrapper and the `port_forward` context manager
  `monitoring`  the Prometheus / Alertmanager / pushgateway readers
  `records`     `load_record` — read a tracked record, refuse when it is absent

**How a caller reaches this package.** These scripts are executed as FILES
(`uv run python scripts/foo.py`), not as a package, and several are loaded by
tests through `spec_from_file_location`, which puts nothing on `sys.path` at
all. So each entry point declares where its libraries live, immediately before
importing them, exactly as it already declares `src`:

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _lib.monitoring import prom_rules

That is the idiom `feast_online_parity.py`, `marts_publish.py` and
`rotate_credentials.py` already used before this package existed.

WHAT DELIBERATELY DOES NOT LIVE HERE, and must not move here later:

  * **Accept checks.** Every deploy and drill argues its own case; an accept
    check is that argument (M5-S2's prediction, M8-S4's two-sided assertion).
    A shared accept check would make two witnesses one.
  * **Predictions and plants.** A drill's prediction is written before its run
    and a red team's plant IS its argument (CU-S3 kept the plants bespoke for
    this reason).
  * **DRY_RUN narrations** — the audit's own do-not-consolidate row: each says
    what THAT script would have done.
  * **Verdict/threshold logic.** No bar, no `for:` sustain and no gate condition
    is computed here. `docs/slo_serving.md` owns every serving threshold and
    `configs/` owns every knob (F-013); a library that could decide would be a
    second home for a number.
  * **Bespoke record shape-checks and fail messages.** `load_record` answers
    "is it there?"; a reader whose refusal argues about its own artifact keeps
    that refusal beside the artifact (CU-S4's stated stopping line — see
    `records.py`).
"""
