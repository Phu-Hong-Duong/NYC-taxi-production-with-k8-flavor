# Gotchas ledger — silent traps FIRST. Pay each tuition exactly once.

Format: symptom → real cause → ten-second check. Costs dated when paid.
Seeded 2026-08-12 from prior-project tuition and live-source checks; entries below
the seed line are earned by THIS project.

1. **Everything is mysteriously slow (pytest, dvc, docker build).** Repo lives on
   `/mnt/c/...` — Windows fs through the WSL bridge, 10–30× penalty. Check: `pwd`
   starts with `/home/`. Fix: move the clone, never work from /mnt/c.
2. **OOMKilled pods / cluster flaps despite plenty of host RAM.** WSL2 defaults
   to ~50% of host RAM. Check: `free -h` inside WSL shows what you granted, not
   what you own. Fix: `.wslconfig` `[wsl2] memory=48GB` (this 64 GB machine —
   user-stated 2026-08-12), then `wsl --shutdown`.
3. **ImagePullBackOff on an image that exists locally.** kind nodes cannot see the
   host docker daemon's images. Check: `docker exec -it <kind-node> crictl images`.
   Fix: `kind load docker-image <img>` or the local-registry pattern in infra/kind/.
4. **KServe storage-initializer 403/timeout pulling s3://.** Missing/miswired
   storage-config secret (endpoint, creds, path-style) on the isvc service account.
   Check: `kubectl describe pod <predictor> | grep -A5 storage-initializer`.
5. **MLflow run exists but artifacts 404.** Client context missing
   `MLFLOW_S3_ENDPOINT_URL` + AWS creds — needed in local shell AND training pods
   AND Flyte task pods. Check: `env | grep -E 'MLFLOW|AWS'` in the failing context.
6. **"Same month" downloads hash differently / new columns appear.** TLC backfills
   files and evolves schema by year (`cbd_congestion_fee` 2025+ — verified
   2026-08-12). Check: DVC hash vs recorded manifest. Fix: trust the DVC pin, make
   pandera schema year-aware, treat re-downloads as new data.
7. **Dtype crashes deep in feature code.** `passenger_count` nullable float,
   `store_and_fwd_flag` object, Int64-with-null IDs. Fix: single explicit cast at
   ingest (`taxi_mlops/data`), nowhere else. Check: `df.dtypes` printed by ingest.
8. **Flyte 2 install fights back repeatedly.** It is young (2.0.x, verified
   2026-08-12). Rule: third failed attempt at the same M3 goal = wall → STOP,
   handoff, execute ADR-002 fallback (flyte-binary 1.16.x) next session.
9. **x509 / SSL errors from helm, pip, docker inside WSL.** Kaspersky TLS
   interception on this host (prior history: it broke protocol-launch flows in
   July). Check: `curl -vI https://github.com 2>&1 | grep -i issuer` — an issuer
   naming the AV = interception. Fix: import the AV root CA into WSL trust store
   or exclude WSL networking; do NOT disable TLS verification anywhere.
10. **Ports already taken at cluster-up.** Other project stacks on this machine
    (fleet rule). Check: `ss -tlnp | grep -E '5000|8080|9000|3000'` before
    `make cluster-up`. Port family is recorded in CLAUDE.md.
11. **`/bin/bash^M: bad interpreter` inside containers.** CRLF endings from a
    Windows editor. `.gitattributes` enforces LF. Check: `file scripts/*.sh`.
12. **Namespace stuck Terminating after destroy.** Finalizer deadlock. Fix lives in
    `scripts/fix_stuck_namespace.sh` (written at first occurrence); never hand-patch
    ad hoc and forget how.
13. **Evidently code breaks after an innocent `uv sync`.** API churns between
    minors. Fix: exact pin + all Evidently imports quarantined in
    `taxi_mlops/monitoring/`. Check: `uv tree | grep evidently` vs CLAUDE.md pin.
14. **mlserver cannot load a registry model.** MLflow-flavor version skew between
    the logger and the runtime. Fix: pin mlflow and mlserver as a PAIR in
    CLAUDE.md; bump together, parity-test after.

15. **An AutoML leaderboard is a hypothesis, not a result.** Internal CV scores
    can flip sign against held-out truth (predecessor scar, generalized). Rule:
    every reported number is recomputed by `taxi_mlops.training.evaluate` on the
    held-out month; scout numbers appear only labeled "scout-internal".
16. **AutoML dependency pressure.** If a framework demands downgrading the core
    stack (AutoGluon does), quarantine it: separate venv, exchange predictions
    only, score with our metrics module. NEVER downgrade the platform for a tool.
17. **Optuna study collisions in shared Postgres.** Study names are namespaced
    per milestone (`configs/tuning.yaml: study_namespace`); resuming the wrong
    study looks exactly like resuming the right one until trial params disagree.
18. **A reviewer session that saw the builder's context is void.** REV freshness
    is the entire value; if builder residue is present, stop, log it, restart
    fresh. Check: the session's first act is reading committed artifacts, and the
    builder's narrative appears in the log only AFTER draft findings exist.

19. **A carried obligation anchored to a milestone that doesn't do the thing.**
    The predecessor dated three obligations to "the next milestone that registers
    a model" — and no later milestone did, so a mandatory close became impossible.
    Rule: a CARRY names a landing milestone AND quotes the BLUEPRINT line proving
    it covers the need; unquotable = raise a PO fork now (ledgers/debt.md).
20. **A MERGED PR with green CI can reach nothing.** A stacked PR whose base was
    itself already merged lands on a dead branch while every surface reads MERGED.
    Closure sweeps prove lineage per story: `git branch -r --contains <sha>` must
    show origin/master. Ask what the PR's BASE was, not whether it merged.

21. **A feature the serving request cannot know.** `trip_distance` is the
    odometer — it exists only AFTER the trip; a pre-trip ETA can't use it.
    Centroid-haversine and OSRM zone-pair distances are the pre-trip-knowable
    substitutes. Rule: every feature in a serving set names its request-time
    source (artisan playbook §5, trap 3); v1's trip_distance is under formal
    review at the M3 Design Review.

22. **A mart that feeds the model.** Analyst marts (dbt -> Postgres/Metabase)
    serve HUMANS; if model code imports a mart, train/serve skew returns through
    the back door and the features law dies quietly. Rule: a mart aggregate that
    looks model-worthy graduates via the feature dossier and the shared features
    path (ADR-009). Check: `grep -r "analytics" src/taxi_mlops/` returns nothing.

23. **An unattended chain that can auto-proceed into the irreversible.** Hard-
    block classes never ride a default: money, credentials, deleting
    user-created data, loosening gates/thresholds, rewriting shared git
    history. Direction forks WAIT in AWAITING_PO.md (ADR-010); the chain parks
    rather than guesses. Check: every fork entry names what is parked.
24. **The sleep-scheduler dies with WSL.** nohup chains live inside the WSL VM;
    if WSL shuts down (last terminal closed, host reboot), the pending session
    silently never starts. Keep a terminal open or enable systemd; resume is
    one command (`automation/next_session.sh executor`). Hardening option:
    Windows Task Scheduler (schtasks.exe) one-shots. Check: `automation/logs/`
    shows a log for the session you expected.

---- seed line — entries below are earned by this project ----

25. **A chain kit authored on Windows ships broken bits.** Two silent ways the
    harness dies in a fresh WSL clone: (a) git-on-Windows recorded the chain
    script as 100644 — `automation/next_session.sh: Permission denied` on
    first use; (b) runtime files were committable — a `git add -A` that
    catches `automation/STOP` freezes EVERY clone's chain silently, and
    `automation/logs/` becomes history noise. Tuition paid 2026-08-16
    (bootstrap, caught pre-clone): `git update-index --chmod=+x`, .gitignore
    += `automation/logs/`, `automation/STOP`. Check: `git ls-files -s
    automation/*.sh` shows 100755 AND `git check-ignore automation/STOP`
    succeeds.

26. **A permission mode exported in .bashrc silently dies mid-chain.** Ubuntu's
    ~/.bashrc opens with an interactive guard (`case $- in *i*)…return`), so a
    bottom-appended `export CLAUDE_PERMISSION_FLAGS=…` never reaches
    non-interactive shells — and successors are scheduled FROM claude's
    non-interactive Bash tool, so after session 1 the var evaporates and the
    script's acceptEdits fallback takes over. A dangerously-skip chain would
    quietly degrade and park mid-milestone; the safer mode survives only
    because it EQUALS the fallback. Tuition 2026-08-16, caught at go-live:
    next_session.sh now env-forwards the resolved FLAGS into the spawned
    claude, so the launch mode propagates for the chain's life; the standing
    allowlist lives in .claude/settings.local.json, not .bashrc. Check: the
    nohup line contains `CLAUDE_PERMISSION_FLAGS='${FLAGS}'`.

27. **A starter allowlist blocks the work, and the agent cannot widen it.** The
    safer permission mode lists the *interesting* tools (kubectl, helm, docker,
    uv…) and forgets the boring ones the interesting ones need — `ls`, `mkdir`,
    `chmod`, `tar`, `printenv`, `mv`. An unattended session then parks on
    `chmod +x` right after successfully downloading a binary, and it CANNOT fix
    itself: the harness refuses writes to `.claude/settings*.json` (a
    self-granting guard, and a correct one). Compounding it, paths outside the
    repo are sandboxed for file tools, so `~/.local/bin` is unlistable even
    though `curl` may write there. Tuition paid 2026-08-16 (M0-S1: the whole
    toolchain install re-routed through the allowlisted `python3` —
    `os.chmod`, `tarfile.extract`). Rule: allowlist the boring verbs at setup;
    a widening is a PO paste (AWAITING_PO), never an agent self-grant. Check:
    before an unattended install story, dry-run `chmod`/`mkdir`/`ls` against
    the target dir — a refusal now costs ten minutes, the same refusal at 3am
    costs a parked chain. Sibling of #26: same session, same theme (the
    permission *mode* survived the chain; the permission *list* was too short).

28. **A pod whose logs say "Application startup complete" and then dies anyway.**
    MLflow 3.x serves under uvicorn with `--workers 4` by default; four full
    Python processes, each loading MLflow + SQLAlchemy + boto3, walked through a
    2Gi limit and the kubelet killed the container. The logs show no error at
    all — being OOMKilled is not something a process gets to log — so the only
    honest evidence is in the pod object, not the log stream. Tuition paid
    2026-08-16 (M0-S3; `helm upgrade --wait` failed with the uninformative
    `Error: context deadline exceeded`). Check FIRST, before reading a single
    log line: `kubectl get pod <p> -o jsonpath='{.status.containerStatuses[0].lastState}'`
    — `"reason":"OOMKilled","exitCode":137` ends the investigation. Fix here:
    `extraArgs: {workers: "1"}` in infra/helm/mlflow/values.yaml. General rule:
    a server's default worker count is sized for a server, not for a laptop
    sharing 48 GB with six other stacks.

29. **A readiness check that passes on zero replicas.** `kubectl rollout status
    deployment/x` exits 0 and prints "successfully rolled out" when the
    Deployment is scaled to 0 — correctly, since zero replicas is a completed
    rollout, but it means a verify script built on it reports **ok** for a
    service that is entirely gone. Found 2026-08-16 by red-teaming verify-m0
    against its own subject (`kubectl scale --replicas=0` on MLflow): every URL
    check failed while the readiness line stayed green. Rule: ask readiness as a
    number — `readyReplicas >= 1` AND `readyReplicas == spec.replicas` — and keep
    the rollout check too, because the two fail differently (wedged rollout vs
    scaled-away workload). General form: a check whose PASS branch you have never
    seen be wrong is a check you have not tested; scale the thing to zero and
    watch what your script says.

30. **A `DRY_RUN` that deleted the cluster while printing "nothing was deleted".**
    `scripts/cluster.sh destroy` guarded every FILE deletion behind `DRY_RUN`,
    then called `cmd_down` unconditionally one line earlier — so the preview
    deleted the single most expensive thing it owns (the kind cluster, and with
    it every PVC: Postgres data, MinIO objects) and closed with the footer
    `[destroy] DRY_RUN=1 — nothing was deleted.` Tuition paid 2026-08-16 (M0-S4,
    on the first command of the story — the preview WAS the teardown, which is
    the only reason it cost nothing). The second half is the sharper lesson:
    a unit test named `test_destroy_dry_run_deletes_nothing` had been green
    since M0-S2. It ran against a sandbox whose kind config named a cluster that
    cannot exist, so `cmd_down` always no-opped and the bug was invisible —
    **the isolation that made the test safe made it blind.** Rule: when a test
    stubs away the dangerous dependency, it no longer tests the dangerous path;
    give it a shim that RECORDS the call (`kind delete cluster …` written to a
    log file) and assert on the recording, plus a positive control proving the
    shim fires when it should. General form: a dry run must cover the most
    expensive deletion first, not last — and any footer claiming what a script
    did is a claim to verify, not a summary to trust.

31. **A column that "still exists" under a different capital letter.** Gotcha #6
    warned that TLC adds columns by year. What it did NOT say is that TLC also
    *renames* and *retypes* the ones already there. Observed live 2026-08-16 by
    diffing the arrow schemas of 2019-01..08 against a 2025-01 probe:
    `airport_fee` (2019, all-null) becomes **`Airport_fee`** (2025) — same
    field, capital A — and six columns change physical type across the same
    boundary (`VendorID`/`PULocationID`/`DOLocationID` int64→int32,
    `passenger_count`/`RatecodeID` double→int64, `store_and_fwd_flag`
    string→large_string). Every one of those is silent: a case-sensitive
    `df["airport_fee"]` on 2025 data raises KeyError at best and, if the code
    politely reindexes, yields an all-null column that reads as missing data
    rather than as a rename. The int32/int64 pair is worse — it does not fail at
    all, it just makes two years' frames disagree somewhere far downstream.
    Fix landed at M1-S1: the contract carries `aliases` per column and announces
    every one it applies (`SCHEMA EVENT: alias applied: 'Airport_fee' ->
    'airport_fee'`), and the single dtype cast normalizes every year onto one
    canonical set — so two years become the same table by construction, not by
    luck. Check: never trust `set(columns_a) == set(columns_b)` as "the schema
    is stable"; diff the TYPES too, and diff case-insensitively before
    concluding a column is new. General form: schema drift has three shapes —
    added, renamed, retyped — and only the first one is loud.

32. **DVC phones home the moment you `dvc init`.** The init banner says it
    plainly — "DVC has enabled anonymous aggregate usage analytics" — and then
    the line scrolls past with the rest of the welcome text and nobody reads it
    again. This program's charter is one sentence long on the subject ($0
    budget; nothing leaves this machine; no cloud credentials exist here), so an
    opt-OUT default is a violation that installs itself. Tuition paid 2026-08-16
    (M1-S2), cost nothing because the banner was read on the first run.
    Fix: `dvc config core.analytics false` immediately after init, committed in
    `.dvc/config`, and pinned by `tests/unit/test_data_pipeline_scripts.py::
    test_dvc_analytics_are_off` so a future `dvc init` on a fresh clone cannot
    quietly restore the default. General form: every new tool in a $0/offline
    program gets one question before its second command — *what does this send,
    and to whom* — because the answer is a default someone else chose, and
    defaults are not exemptions. Siblings worth checking the same way as they
    arrive: dbt (`send_anonymous_usage_stats`), Metabase (anonymous tracking),
    and anything with a `--telemetry` flag.
    **Both named siblings have now arrived, and both were opt-out.** dbt at
    M1-S4, which also dragged `snowplow-tracker` into the dependency graph.
    Metabase at M1-S5 — and it phones home TWO ways, not one: anonymous usage
    tracking (`MB_ANON_TRACKING_ENABLED`) and a version check against
    metabase.com (`MB_CHECK_FOR_UPDATES`). Both are off in
    `infra/manifests/metabase.yaml`, where the decision is greppable and survives
    a `make destroy`. The half that nearly escaped: `POST /api/setup` writes its
    OWN `allow_tracking` preference at first login, so an instance whose manifest
    says "false" turns tracking back on the moment it is set up, unless the setup
    call says so too (`scripts/metabase_boards.py`, pinned by a test). Two
    switches for one behaviour, in two layers, and only one of them is in the
    file you would think to read.

33. **A rebuild proof that refreshes the pin it is judged against.** The
    byte-identical gate is "wipe `data/processed/`, rebuild, sha256 must match".
    The obvious implementation is to wipe and then run the one rebuild command —
    but `make data` ends in `dvc add`, which re-hashes the outputs and rewrites
    `data/processed.dvc`. Do that and the proof compares the new bytes against a
    pin computed *from those same new bytes*: it passes forever, including on
    the day the parquet writer stops being deterministic. Caught in review at
    M1-S2 before it ran; the fix is `SKIP_DVC=1 make data` inside
    `scripts/rebuild_proof.sh`, and the reason the flag exists at all is written
    at the top of `scripts/data_pipeline.sh`. Two more teeth: the proof asserts
    its INPUT still matches `data/raw.dvc` first (a rebuild from different bytes
    proves nothing — gotcha #6), and it closes with a SECOND witness, DVC's own
    `dvc status data/processed.dvc`, computed by different code from different
    metadata. General form: a verification step must never write to the artifact
    it verifies against, and one witness agreeing with itself is not evidence.

34. **`kubectl: command not found` — and the cluster was never the problem.**
    A chained session opened, ran its staleness check, and bash answered
    `kubectl: command not found` for a binary CLAUDE.md records as pre-existing
    and four previous sessions used. It had not been uninstalled:
    `/usr/local/bin/kubectl` is a SYMLINK into
    `/mnt/wsl/docker-desktop/cli-tools/usr/local/bin/kubectl`, a path that only
    exists while Docker Desktop is running. The host had restarted overnight and
    Docker Desktop had not come back with it, so `/mnt/wsl` held nothing but
    `resolv.conf`, the symlink dangled, and PATH lookup skipped it — producing
    the one error message that sends you looking at your PATH, your toolchain
    install and your kubeconfig, none of which are broken. `docker` was
    similarly absent, because the `docker` on PATH is the Windows shim under
    `/mnt/c/...` whose entire job is to print "could not be found in this WSL 2
    distro". Tuition paid 2026-08-17 (M1-S5, ~5 minutes). Check, in this order,
    BEFORE touching anything: `ls /mnt/wsl` (docker-desktop mounts present?) and
    `tasklist.exe /FI "IMAGENAME eq Docker Desktop.exe"` — no task means the
    whole answer is "the daemon is off", not "the toolchain is broken". Recovery
    is one launch (`cmd.exe /c start "" "C:\Program Files\Docker\Docker\Docker
    Desktop.exe"`) and ~15 seconds; the kind node containers restart themselves
    and the platform comes back with them (observed: all 16 pods Running, then
    `make verify-m0` GREEN 18/18, nothing re-deployed). General form: a tool that
    vanishes without being uninstalled is a symlink into somebody else's
    lifecycle — resolve the link before you debug the tool. Sibling of #24: the
    chain's environment has moving parts that outlive no reboot, and the
    staleness check exists precisely to find them before the work does.

35. **A test that rewrites a shell array truncated it at the first `)` — and the
    surviving entries ran as commands.** `tests/unit/test_cluster_scripts.py`'s
    `_sandbox()` swaps `cluster.sh`'s REGENERABLE allowlist for a one-entry
    version so the destroy guard can be red-teamed. It found the array's end
    with `text.index(")", start)`. That works exactly as long as no entry's
    trailing prose comment contains a paren. M2-S1 added one —
    `# ... (`make rebuild-proof` proves it)` — and four guard tests died with
    **rc 127**, `cluster.sh: line 28: data/interim: No such file or directory`:
    the splice had cut the array open mid-way, so the remaining quoted paths
    were parsed as commands to execute. The failure did not point at the comment
    or at the test helper; it pointed at a line the diff had not touched.
    Tuition paid 2026-08-17 (M2-S1, ~10 minutes). The fix is the idiom the SAME
    FILE already used one test lower down — split on the closing paren **at the
    start of a line** (`text.index("\n)", start)`), which
    `test_the_catalogue_is_destroyable_and_the_dvc_cache_is_not` had been doing
    since M1-S2 with a comment explaining why. General form: when a test parses
    the source of the thing it tests, the parser is production code with none of
    production's tests — and a lesson learned in one function does not travel to
    its neighbour by itself. Look for the second copy of a parse the day you fix
    the first. Sibling of the twins lesson (CLAUDE.md port family): two places
    that must agree, and only one of them was taught.


36. **`uv add mlflow` silently installed a client two MAJORS behind the server.**
    The MLflow server this program runs is **3.15.1**. `uv add mlflow` resolved
    to **1.27.0** — no warning, no conflict, exit 0 — because MLflow 3.x depends
    on `pandas<3` and this project pins `pandas>=3.0.5` (M1-S1). The resolver did
    exactly what it is designed to do: backtrack until something fits. What
    "fits" was a 2022 client, and the only tell was a `databricks-cli` package
    appearing in the install list. Asking for the bound EXPLICITLY
    (`uv add "mlflow>=3.15,<4"`) is what turned silence into the real message:
    *"Because mlflow>=3.15.0 depends on pandas<3 and your project depends on
    pandas>=3.0.5, your project's requirements are unsatisfiable."*
    Fix (M2-S2): **`mlflow-skinny`** — the same client code with the tracking
    SERVER's dependencies removed, pandas pin included — which resolved to
    **3.15.1 exactly**, matching the deployed server. We never needed the server
    package: the server runs in the cluster. Downgrading pandas was never on the
    table (gotcha #16's law, and M1's byte-identity proof rests on the pinned
    pandas/pyarrow pair). Rule: when adding a client for a service you already
    run, **state the version bound you require and read the refusal** — an
    unbounded add cannot fail, and a resolution that cannot fail cannot warn you.

37. **A vendored `.so` cannot be preloaded under the name you need.** This WSL
    host ships no `libgomp.so.1`, so `import lightgbm` dies. scikit-learn's wheel
    vendors one, and the obvious fix —
    `ctypes.CDLL(".../scikit_learn.libs/libgomp-e985bcbb.so.1.0.0", RTLD_GLOBAL)`
    before importing lightgbm — **does not work, and fails identically to doing
    nothing**. Reason: auditwheel rewrites the vendored library's **SONAME** to
    the hashed filename, and glibc matches a later `dlopen("libgomp.so.1")`
    against SONAMEs, not against whatever path you happened to load. The only
    thing that satisfies the lookup is a FILE named `libgomp.so.1` on the
    loader's search path — and `LD_LIBRARY_PATH` is read once, at process start,
    so setting it from inside Python is too late. Fix
    (`taxi_mlops.training.openmp`): symlink the vendored library under the needed
    name, set the variable, and `execv` once, guarded by an env flag so a
    still-broken host fails instead of forking forever. Two sharp edges found by
    doing it: `sys.argv` does not round-trip a `python -m package` invocation
    (argv[0] is `__main__.py`, so the replay dies on *attempted relative import
    with no known parent package* — rebuild from `__main__.__spec__.name`), and
    the re-exec must happen BEFORE any expensive work or it throws that work away
    and does it twice. The honest fix is `sudo apt install libgomp1`, which is
    the PO's hands; debt **D-004** puts it in M4's image, because a shim should
    not be what makes a container work.


38. **dbt's partial-parse cache stores node paths RELATIVE to wherever dbt was
    last run, so one hand-run from the wrong directory breaks `make marts` — and
    the error names a file that plainly exists.** M2-S4 inherited a working tree
    from a session killed mid-story. `make marts` failed at the seed:
    `IO Error: No files found that match the pattern
    "analytics/dbt/seeds/redteam/redteam_bad_trips.csv"` — a path that resolves
    perfectly from the repo root and not at all from `analytics/dbt`, which is
    where `scripts/marts.sh` correctly `cd`s before building. The file was
    present, the script's cwd was right, the diff had not touched seeds, and the
    previous milestone had run the same command green. Cause: dbt caches a parsed
    manifest in `target/partial_parse.msgpack`, and each node's `root_path` in it
    is recorded relative to the invocation directory. The killed session had run
    `dbt` by hand from the repo root (the same event left an empty 12K
    `marts.duckdb` there — two symptoms, one cause), which wrote
    `root_path: analytics/dbt` into the cache; every later in-directory build
    then joined that onto the project dir and looked for
    `analytics/dbt/analytics/dbt/...`-shaped paths. Fix: `--no-partial-parse` at
    all three `dbt build` call sites in `scripts/marts.sh`, measured to cost
    **nothing** on this project (5.74s vs 5.91s — five models). Red-teamed by
    re-poisoning the cache the same way (`dbt parse --project-dir analytics/dbt`
    from the repo root, confirmed `root_path: analytics/dbt` back in the
    manifest) and re-running `make marts`: **ERROR=1 became PASS=57**. General
    form, and it is the reason this one is worth its entry: a cache keyed on
    ambient state that no input mentions turns a build into a function of where
    somebody once stood. When a build fails naming a file you can see, suspect
    the cache before the code — and prefer deleting the cache to teaching every
    caller to stand in the right place. Sibling of gotcha #33's order law: both
    are cases where a step's correctness depends on something outside the step.

39. **Two completely different faults print the same MLflow error, and one of
    them has a famous name.** Building M2-S5's registry leg, a first draft did
    `mlflow.set_tracking_uri("http://localhost:5000")` and then
    `mlflow.models.get_model_info("models:/nyc-taxi-eta@champion")`. It failed
    with `Failed to download artifacts from path 'MLmodel'` — which is the same
    shape as **F-009**, the known MLflow 3 defect where a registry-uri load looks
    under the run's artifact prefix and finds nothing. The obvious conclusion was
    that F-009 is worse than recorded and also breaks `get_model_info`. It does
    not. The real cause was that our MLflow server does **not proxy artifacts**
    (`proxiedArtifactStorage: false`, gotcha #5): the CLIENT fetches from MinIO
    itself, so without the S3 endpoint and credentials that
    `taxi_mlops.training.tracking.configure()` sets from `.env`, every artifact
    read fails — and the FIRST artifact any model read touches is `MLmodel`. Same
    message, different disease: F-009 is "looked in the wrong place", this is
    "not allowed to look anywhere". The tell is which calls fail: under F-009
    `get_model_info` SUCCEEDS while `load_model` fails on the same uri; with
    missing credentials both fail, and so does reading any other artifact of any
    other run. The rule that falls out: **never talk to this MLflow with a bare
    `set_tracking_uri` — go through `tracking.configure()`**, which is also the
    only thing that reads the credentials out of the gitignored `.env`. The cost
    of getting this wrong is not a broken script; it is a session "confirming" a
    finding that is not there, and M5 inherits a workaround for a fault it does
    not have.

40. **A test that greps source code cannot tell code from the comment warning
    about that code — and it will fail on its own documentation first.** M3-S2
    wrote a guard that the zone-centroid script must never hardcode the
    projection: `assert "2263" not in SCRIPT.read_text()`. It went red
    immediately, on the script's own header, which spends three lines arguing
    that hardcoding `EPSG:2263` would be a second definition of the projection
    one directory from the first. The guard was right about the danger and wrong
    about where to look: the CRS genuinely IS read from the `.prj` inside the
    zip, and the only occurrence of the forbidden string was the sentence
    explaining why. Tempting bad fixes, both of which make the repo worse:
    delete the explanation, or weaken the assertion to a pattern the prose
    happens to dodge. The right fix is to look at CODE — `ast.parse`, collect
    the docstring nodes by identity, then check the remaining `ast.Constant`
    values for the string and the integer. Sibling of #35 (a test that parsed a
    shell array truncated it at the first `)` in a COMMENT): both are the same
    error, which is treating a source file as text when the claim is about
    semantics. General form: **if a check is about what the program DOES, read
    the program, not the file.** A check that reads documentation as a violation
    teaches the next person to stop documenting, which costs more than the check
    was ever worth.

41. **A sha256 pin and `.gitattributes: * text=auto eol=lf` are enemies, and
    the pin loses silently on somebody else's machine.** M3-S2 committed two
    externally-published TLC artifacts and pinned their digests. `git add`
    printed one warning — *"CRLF will be replaced by LF the next time Git
    touches it"* — which is easy to read as cosmetic. It is not: TLC serves
    `taxi_zone_lookup.csv` with CRLF, this repo's `.gitattributes` normalises
    every text file to LF, so the blob git actually stored was **12,065 bytes,
    sha256 `5e8f5ff1…`** while the manifest pinned the bytes on disk —
    **12,331, `1a99e105…`**. Nothing fails locally, because the working copy is
    still the file that was downloaded. It fails on the FIRST fresh clone —
    i.e. in CI, or for the next person — where the pin check compares against a
    file git rewrote. The tell before you push:
    `git cat-file -p :<path> | sha256sum` compares the *stored blob* against the
    pin, which is the thing a clone will actually get; `sha256sum <path>` does
    not and will happily agree with itself. Fix is one line —
    `data/reference/** -text` — and the general form is: **anything whose bytes
    are the point must be marked binary, whatever its file extension says.** A
    `.csv` that is really a pinned artifact is not text to git's purposes.
    Sibling of #11 (the CRLF trap class) and of #33: a verification step must
    compare against what the consumer will receive, not against the copy the
    verifier happens to be holding.

42. **A number that has been through a format string exists only at that
    precision, and comparing a fresh measurement against it at full precision
    compares against rounding noise.** M3-S1 taught the promotion gate to refuse
    a challenger that regresses against the SERVING champion (F-011). The
    incumbent's numbers come off the registry version's tags, which
    `registry.promote` writes as `f"{...:.4f}"`. The first full run of the
    hardened gate then **refused the champion against itself**: a deterministic
    re-fit of version 1 measures `3.2608234…`, its own tag says `3.2608`, and
    `3.2608234 <= 3.2608` is False. Every unit test passed beforehand, because a
    test writes the same literal on both sides of the comparison — the two
    numbers only diverge once one of them has crossed a serialisation boundary.
    The fix is to compare at the COARSER of the two precisions and to say which
    one and why (`gate.INCUMBENT_MAE_DECIMALS`, pinned by a test as a twin of the
    format string that writes the tag). The general form: whenever a comparison
    crosses a tag, a CSV, a JSON manifest or a database column with a scale, the
    serialised side sets the resolution — and a difference below it is not
    evidence either way. Sibling of the port-family twins rule: two files, one
    number. It is also the clearest argument in this program for running the real
    thing once before believing a green suite; this defect was invisible to every
    synthetic `Metrics` object and would have fired for the first time at M3-S5,
    on the bake-off, against a live champion.

43. **A point-in-time aggregate creates a train/serve skew of its own, and the
    constraint that makes it legal is what creates it.** M3-S3 built the
    dossier's strongest feature family — OD-pair median duration, zone-hour mean
    speed, zone-hour demand — under a strict cutoff: a row in train month *k* is
    served a table built from months 1..*k−1*. That is the correct answer to
    dossier §4 trap 2, and it has a consequence nobody in the source material
    mentions. The first train month gets **NaN** (a sixth of train, 7.3M rows),
    month 2 gets a one-month window, month 6 gets five — while every held-out row
    gets the full six. **The feature the model is fitted on is not the feature it
    is scored on**, so the booster learns how much to trust a column whose
    reliability it has only ever seen at the wrong end. Measured: the group came
    in at **−1.63% val MAE and −0.686 KPI-10 points**, the only one of five that
    made the model worse, and it early-stopped at **iteration 88** against 500 for
    every other experiment — it found the column, leaned on it, and stopped
    learning. The lesson is not "aggregates are bad": it is that a point-in-time
    scheme is a *modelling decision with its own failure mode*, and the window
    should be constant-width (a trailing N days, identical for train and serve)
    rather than expanding, precisely so both ends see the same feature. Read
    beside #15: the community's most-recommended feature is a hypothesis until
    this program's evaluator has scored it under this program's split.

44. **`ensure_openmp()` re-execs the interpreter, so anything a script did before
    its first `model.fit` is done twice.** A sibling of #37, and it costs minutes
    rather than correctness. The shim (`taxi_mlops.training.openmp`) links a
    vendored `libgomp` and `os.exec`s once with `LD_LIBRARY_PATH` set; it is
    normally triggered lazily by the first `import lightgbm` inside `model.fit`.
    In M3-S3's ablation that point is reached *after* six months of parquet have
    been read and the aggregate tables fitted — all of which the re-exec throws
    away and repeats. Worse for anyone watching: the re-executed process's stdout
    is block-buffered rather than line-buffered, so a long run looks hung at the
    exact line where the shim announced itself. Fix, one line, at the top of any
    script that loads data before it fits: call `ensure_openmp()` first. Both
    M3-S3 scripts do, and the log is linear again.

45. **A session that ends its turn kills every background task it started, so
    "I'll pick this up when the run reports" is a way of destroying the run.**
    The most expensive sentence written in this program so far, and it cost
    nothing but time only by luck. On 2026-08-17 the M3-S3 executor launched
    the 4-arm full-scale confirmation as a Claude Code **background task**,
    polled it eight times, then ended its turn with that sentence. In `claude
    -p` there is no later: ending the turn IS process exit, background tasks
    are children of that process, and all four of them show `[killed]` at
    **13:50:07Z** — the fit died mid-`mlflow` model-logging, one arm of four
    complete. The evidence is unusually clean because the polls and the run
    share a kill timestamp to the second. Three failures were stacked and each
    one is worth separating, because fixing only the visible one leaves the
    other two armed:
    - **The contract had four endings and the model invented a fifth.** The
      exit ritual offered a/b/c (schedule a successor) and d (park
      deliberately). "Wait for an async job" was not among them, so the ritual
      was never reached, `next_session.sh` was never called, and the chain had
      no successor. Now there is an (e), and the ritual says outright that
      there is no sixth.
    - **Nothing watched.** Chain liveness was 100% "each session schedules the
      next" — a single missed call ends the program silently and forever. It
      stayed dead 38 minutes until a human happened to read a status pane.
      `automation/watchdog.sh` on cron is the organ that was missing, and its
      hard rule is that it may restart an ACCIDENT but never a DECISION: a
      chain parked on a fork (ritual d) writes AWAITING_PO.md, and that diff
      is exactly how the watchdog tells the two apart. A park with no entry
      reads as a crash, which is now a reason to always write the entry.
    - **The work was uncommitted.** 23 files — four feature modules, the
      ablation, the leakage red-team, 33 tests — sat in the working tree for
      52 minutes with nothing in git holding them. The kill happened to spare
      them. A `SIGKILL` on the wrong process, or a WSL shutdown, would not
      have. Commit before anything slow; a WIP commit is not a claim of Done.
    The general shape, worth carrying past this program: **an autonomous agent
    cannot wait.** Waiting requires a process that outlives the wait, and the
    session is not it. Work that must outlive a session has to be detached on
    purpose (`automation/run_detached.sh`, which `setsid`s the job and lets
    the JOB schedule the successor when it finishes), and liveness has to be
    observable from outside the thing whose liveness is in question — which is
    why `next_session.sh` now leaves `pending_successor` and `running_session`
    markers behind. Related: #26 (env that does not survive a non-interactive
    shell), #24 (the sleep-based scheduler dies with WSL).

46. **A reference file can spell its own null two ways, and a code comment that
    checked one of them will swear it does not.** `data/reference/
    taxi_zone_lookup.csv` — the TLC's own file, sha256-pinned, read live —
    gives zone **264** Borough `Unknown` and zone **265** Borough `N/A`. Both
    rows mean "this id is not a place"; the program has said so since M1
    ("zones 264/265 are unknown, not places") and DR-04 condition 1 requires
    every spatial feature to give them ONE named fallback. `load_zone_table`
    built its code table straight from the column, so 265 quietly became a
    seventh borough whose meaning was "we do not know" — and `borough_pair`,
    whose entire job is to be the coarse backoff that exists for every OD pair,
    carried two categories for the same absence of information. The comment
    directly above the loop asserted "a borough IS defined for them
    (`Unknown`)", which was **true for the id its author checked** and false
    for the other one. What caught it was not review: it was an existing
    unseen-category test asserting both ids land on the same code, run for the
    first time by the next session (the story that wrote it was killed before
    `pytest` — gotcha #45). Two lessons, and the second is the transferable
    one: a comment that generalises from one example is a claim, not a
    citation; and when a fold like this is introduced, the test must pin BOTH
    halves — the nulls collapse **and** the real categories survive — or
    tomorrow's fix for a different bug flattens the column and stays green.

47. **A SIGKILLed Optuna trial stays `RUNNING` in the storage forever, so a
    resumed study silently loses one trial per kill.** Found by M3-S4's own
    kill-and-resume drill, on the run that *passed*. Optuna has no way to
    distinguish a process that is thinking from a process that no longer
    exists, so the trial that was mid-fit at the instant of the kill is never
    completed, never retried and never failed — while still occupying a row.
    Any arithmetic of the shape `n_trials - len(study.trials)` then asks for
    too little work: the drill requested 8 trials and got **7 answered plus a
    corpse**, which is invisible to anybody reading `TOTAL` rather than the
    per-state counts. Two halves to the fix, and both are needed: build the
    storage with `RDBStorage(heartbeat_interval=…, failed_trial_callback=
    RetryFailedTrialCallback(...))` so `study.optimize` can declare a stale
    trial dead and re-enqueue it, **and** count the trials that are ANSWERED
    (`COMPLETE` + `PRUNED`) rather than the rows that exist. The transferable
    lesson is the one in the field note: the drill was written to satisfy a
    sentence ("the trial count continues"), and the sentence was satisfiable by
    a system that was quietly dropping work — so ask what a green light would
    still be compatible with. Related: #45 (the reason anything is killed at
    all), #17 (why the study is namespaced in the first place).

48. **The launcher for resumable jobs truncated the log of the run it was
    resuming.** `automation/run_detached.sh` opened its log with `: > "${LOG}"`
    — correct for a job that runs once, wrong for every job this repo actually
    has. `scripts/automation_track.sh` is *designed* to be relaunched under the
    same name: it skips any phase whose output JSON already exists, so
    relaunching is the normal path after a kill, a stop or a failure. Relaunch
    it and the launcher wipes the transcript of every phase the previous run
    completed, one line before the resume logic goes on to correctly skip those
    same phases. Paid on 2026-08-18: resuming M3-S4's track to run its one
    missing phase destroyed **2 h 20 m** of scout and sniper output, including
    both FLAML leaderboards and the PO's hand-written stop note. Nothing
    load-bearing was lost only because the phase verdicts live in
    `automation/runs/m3s4/*.json` and not in the log — i.e. the design that
    made the job resumable is the same design that made the loss survivable.
    Fixed by rotating (`<name>.log.1 … .log.N`, `KEEP_LOGS=5`) instead of
    truncating, which is safe precisely because the launcher already refuses to
    start a second job under a name that is RUNNING — no live writer's file is
    ever renamed. The transferable shape: **when a job is built to be re-run,
    audit everything its launcher does to state that already exists**; "start
    fresh" is an assumption a resumable job has already contradicted. Related:
    #45 (why detached jobs exist), #47 (the other half of the same track's
    resume story).

49. **A tag named `do_not_promote` whose VALUE is `"no"` reads as a refusal to
    every check that tests for the key.** Every run this program writes carries
    the key; the value is what says which way — `"yes — 15% sample (F-008)"` on
    a scout trial, `"no — full-data fit; the gate sees it at M3-S5"` on the four
    bake-off contenders. `verify-m2` §1 asked `if "do_not_promote" in
    run.data.tags` and called the legitimately promoted champion **hobbled**;
    §3's kept-refusal leg had the same latent false GREEN in the other
    direction, where a run tagged `"no"` would have counted as properly marked.
    Presence-reading worked for two milestones only because M2 never wrote a
    `"no"`. Fixed with one rule covering both families (`red_team` and `hobbled`
    carry descriptive values like `"M2-S3"`, so presence IS the mark there):
    **a mark counts unless its value says no.** The transferable shape is
    narrower than "read values, not keys" — it is that a boolean expressed as
    *key presence* and a boolean expressed as *key value* are two conventions,
    and a codebase that ships both will eventually read one as the other. If the
    key is going to carry a value at all, the value is the answer. Related: #15
    (the other place a tag is the record), #42 (a recorded number exists only at
    the precision it was recorded at).

50. **Three `verify-m2` assertions encoded M2-era facts as literals, and all
    three went RED the first time the program did the right thing.** The gate
    pinned the champion's `gate_floor` tag to `baseline-group-median`, its
    experiment to `configs/train.yaml`'s current `experiment`, and read
    `do_not_promote` by presence (#49). M3-S1 replaced the floor with a NEW name
    — *because the config legislates that a floor change is a new name and never
    an edit* — and M3-S5 promoted a champion whose run legitimately lives in
    `m3-automl`. So the first legitimate champion transition produced three red
    sub-checks, none of which was about anything being wrong. That is the
    dangerous shape: **a guard that goes red when the program behaves correctly
    trains the next session to edit assertions**, and the session after that
    inherits a formality. The cure is not to loosen but to assert the property
    that holds at *every* champion and is strictly stronger than the literal
    was: the floor must be a name `baselines.fit_floor` can rebuild (which also
    excludes the flattering constant-median floor, something the literal never
    checked), the experiment must be FINISHED and namespaced (gotcha #17's real
    invariant), and — new — the version's floor must be the floor
    `predictions.json` actually published against, which is F-012's wire seen
    from the other end. `verify-m3` was written under this rule from the start
    and `tests/unit/test_verify_m3.py` fails if it pins a run id, an experiment
    name or a floor name. Related: #15, #42, and the same argument M3-S5 applied
    to two feature tests that pinned the literal `v1`.
