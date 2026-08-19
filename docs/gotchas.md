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

51. **A component printed a claim it was structurally incapable of checking, and
    it printed it on every verdict this program ever issued.** `gate.verdict_lines`
    said the holdout was "untouched by training **and by selection**". The first
    half the gate can vouch for — `decide()` refuses metrics from any split but
    the configured holdout. The second half is a fact about the *caller's*
    process: how the challenger being judged was chosen. For the whole of M3-S5
    it was false — `scripts/bakeoff_m3.py` ranked five arms by their holdout MAE
    and handed the winner to the very function that then certified the holdout
    selection-free. Nobody lied; the sentence simply lived in the one module that
    could not evaluate it. The cure is not a better sentence, it is moving the
    claim to whoever can make it: `holdout_untouched_by_selection` is now a
    caller-supplied argument **defaulting to the weaker, always-true form**, so a
    claim nobody made is never printed as if somebody had. Ask of any assertion
    a component prints about its own inputs: *could this component tell if it
    were false?* If not, it is documentation with a confident voice. Related:
    #15 (only one module may report a number), #50 (a guard that fires on
    correct behaviour).

52. **The fix that changes a value leaves the hazard in scope; the fix that
    changes the ORDER removes it.** F-018's obvious repair was one character —
    rank on `"val"` instead of `"test"`. It is correct, and it leaves the ranking
    sitting *after* both splits have been scored, where a holdout number exists
    and the only thing preventing its use is that nobody typed it. The repair
    that lands moved the selection *inside the val pass*, before the holdout
    parquet is loaded: there is no test number in existence to rank on, correctly
    or otherwise. **A property you can only violate by deleting code beats a
    property you can violate with a two-character edit.** The corollary is a
    testing one and cost this story a rewrite: the behavioural test must make the
    two splits **disagree**, because a fixture built from the real run (where val
    and test ranked identically — which is why the defect was harmless, and why
    it went unseen) passes under BOTH rules and proves nothing. And ordering
    itself is not behaviourally testable at all when the orderings agree, so the
    companion check is structural (AST: the call sits under the `split == "val"`
    guard). Related: #35 (the other place a structural test earned its keep).

53. **Two tests went red because they searched TEXT for a module name and found
    it in a docstring** — in the same file, within a minute of each other. One
    asserted the reporting stages do *not* import `taxi_mlops` (its docstring
    names `taxi_mlops.training.evaluate`, which is the point of the docstring);
    the other asserted `src/` does not import `pipelines` (`src/taxi_mlops/
    __init__.py` explains the dependency direction in prose). Both were fixed by
    reading Import/ImportFrom nodes off the AST. This is #35's lesson from the
    other side: **in a repo where the prose is load-bearing, a substring check
    answers a question about documentation while claiming to answer one about
    dependencies** — and it is green or red for reasons unrelated to the property
    either way. Any check whose subject is code structure should parse code.


54. **A backup verified itself with a check that could not detect the failure it
    named — and that hung.** The obvious shape for "prove the dump is readable"
    was `pg_dump -Fc` streamed back through
    `kubectl exec -i postgres-0 -- pg_restore --list`. Two things were wrong.
    First, a custom-format archive keeps its **table of contents at the FRONT**,
    so `--list` succeeds happily on a file whose tail was never written — i.e. on
    exactly the truncation the check existed to catch. It was #51's question
    ("could this component tell if it were false?") asked of a verifier instead
    of a claim, and the answer was no. Second, it did not terminate: with stdin
    redirected from a **1 MB** file the exec did not return after 120 s, twice,
    having worked once on a **1.2 GB** one — so the check was also
    non-deterministic in wall-clock. The replacement is entirely host-side and
    reads every byte: `gzip -t` (CRC over the whole archive) plus pg_dump's own
    `-- PostgreSQL database dump complete` line, and it was **proven against a
    deliberately truncated copy** before being trusted. **A verification step
    deserves the same negative control as the thing it verifies.**

55. **The completion marker is not the last line, and the marker starts with
    `--`.** Two consecutive red runs of the same new check, each costing a
    3.5-minute re-dump of a 13 GB database. (a) Postgres 16.11's pg_dump closes
    with a `\unrestrict <token>` psql meta-command and trailing blank lines
    *after* `-- PostgreSQL database dump complete`, so `tail -n 1` returns an
    empty string — which is also what a truncated file returns, so the check
    failed closed rather than passing wrongly, which is the only reason this is a
    gotcha and not an incident. (b) `grep -qF "$MARKER"` then read the marker's
    leading `--` as an end-of-options flag and died with a usage message while
    the script reported "the dump was cut short". **A verifier that fails for its
    own reasons and blames the artifact teaches you to distrust the artifact** —
    the same disease as #50, one layer down. Guard patterns with `grep -- "$pat"`
    whenever the pattern is data, and test a new check against a real artifact
    *before* wiring it into something that takes minutes to reproduce.

56. **A container check reports "the module is missing" / "the shim left no
    trace" while the image is perfectly correct — because the check used
    `bash -lc`.** A LOGIN shell re-reads `/etc/profile`, which rebuilds `PATH`
    from scratch and throws away the image's own `ENV PATH=/app/.venv/bin:…`. So
    `python` becomes the base interpreter, every `import taxi_mlops` raises
    `ModuleNotFoundError`, and whatever the check was actually looking for is
    reported as absent. Cost 2026-08-18 (M4-S3): one wrong RED verdict in the
    D-004 sensor drill, which "proved" the shim had not fired when in fact its
    python had never started. Check: `docker run --rm <img> bash -lc 'which
    python'` vs `bash -c 'which python'` — if they differ, every `-l` in your
    checks is a lie. Use `bash -c`, or call the interpreter by absolute path.
    Related: `/sbin` is not on a non-root user's PATH either, so `ldconfig`
    needs its full path in the same containers.

57. **A `chown -R` at the end of a Dockerfile doubles the image.** The tutorial
    ordering — build everything as root, then `chown -R app:app /app` before
    `USER` — costs a full copy of every file it touches, because a layer records
    new metadata by storing the whole file again. Measured 2026-08-18 (M4-S3):
    the chown was a **1.7 GB layer** duplicating the venv beneath it and took
    **139 s**; creating the user BEFORE installing anything (plus
    `COPY --chown=`) produced the same image at **736 MiB** content instead of
    1408 MiB. It hid because `docker image inspect --format '{{.Size}}'` is the
    number everyone quotes and under Docker 29's containerd store it is the
    CONTENT size, not what the layers occupy unpacked. Check: `docker history
    <img> --format '{{.Size}}\t{{.CreatedBy}}'` and look for a layer as big as
    your dependencies that does not install anything.

58. **`.dockerignore` is not hygiene, and `data/` is not one thing.** Excluding
    `data/` wholesale is right for the trees DVC pins and wrong for anything
    committed under it: 1.1 MB of `data/reference/` in this repo is the lookup
    layer the feature path reads (zone centroids, the TLC zone lookup, the pinned
    shapefile, the holiday table), and a `.env.*` glob eats the committed
    `.env.example` template too. The resulting image imports every module
    perfectly and cannot build a feature. Cost 2026-08-18 (M4-S3): **28 failed +
    10 errors** in the first in-image test run — which is also the lesson: the
    thing that caught it was running the project's own unit suite INSIDE the
    artifact, not reading the Dockerfile. Rule adopted: *the image contains what
    git contains*, and a test asserts the ignore file against `data/.gitignore`
    in both directions.


59. **A CLI can exit 0 for a run that FAILED — assert positively on the artifact,
    never on the absence of an error.** `flyte run --follow` waits for the run to
    reach a terminal state and then exits **0 whether it succeeded or failed**.
    Cost 2026-08-18 (M4-S4): `make pipeline` printed `ok  run … completed; six
    stages on-cluster` over a run that had died on `ErrImagePull` before a single
    stage started. Every other signal agreed with the green line — exit code 0, a
    run name parsed out of the output, and a readable outputs blob from
    `flyte get io`. The ONLY difference was the outputs' content:
    `ActionOutputs(o0=None)`, because a failed workflow returns nothing. The fix
    is not a better error check, it is a POSITIVE one: assert that the run's
    output carries the thing the pipeline exists to produce (here a `"decision"`
    key). That assertion is strictly stronger than a phase string — a run can
    reach SUCCEEDED and still be caught if it stops emitting a verdict — and it
    caught the next three distinct failures immediately instead of painting them
    green. Gotcha #51's question ("could this component tell if it were false?")
    asked of a checker, and this time the checker was minutes old.

60. **Backticks in an UNQUOTED heredoc are command substitution, including in
    comments.** A pod manifest was embedded as `<<EOF` (unquoted, because it
    needed `$NAMESPACE` interpolated) and its own explanatory comments referred to
    `` `tar -x` ``, `` `du` `` and a `` `docker image inspect …` `` command. The
    shell RAN all three: tar read the script's stdin and printed "This does not
    look like a tar archive", docker printed a usage error, and both were spliced
    into the YAML, which then failed with `error converting YAML to JSON: yaml:
    line 15: could not find expected ':'` — a parse error pointing at a line that
    had nothing to do with the cause. Cost 2026-08-18 (M4-S4), one run. This is
    #35 (a test parsing a shell array truncated at a `)` in a comment) and #53
    (assertions matching prose in a docstring) a third time: **in a repo where
    comments are load-bearing, prose must not sit anywhere a shell or a parser
    will read it as code.** The fix is also the better design — the manifest
    became a file, which is where cluster objects belong and which cannot be
    command-substituted. If a heredoc must stay, quote the delimiter (`<<'EOF'`)
    and pass values another way.

61. **Setting a security allow-list REPLACES its default, and host-header
    matching includes the port.** MLflow 3.x serves under uvicorn with
    DNS-rebinding protection; its allow-list (`MLFLOW_SERVER_ALLOWED_HOSTS`,
    chart value `serverAllowedHosts`) is auto-derived from an ingress, so a
    deployment with no ingress silently allows only the loopback names — which is
    invisible for as long as every client is host-side, four milestones here. The
    first in-cluster client gets `403 'Invalid Host header - possible DNS
    rebinding attack detected'` from an endpoint that reads like an application
    fault. Then the fix bites twice: writing the value at all replaces MLflow's
    default list, and the middleware compares the **whole Host header, port
    included** — so a list of bare hostnames repairs the pod and gives every
    host-side client the identical 403. The two-line experiment that separates
    them: `curl -H 'Host: localhost' 127.0.0.1:5000/health` → OK while
    `curl localhost:5000/api/...` → 403. List every name with AND without its
    port, and never reach for `["*"]` — that deletes the protection rather than
    configuring it.

62. **An apostrophe inside `${VAR:+word}` opens a quote, and the error is
    reported five lines away on an innocent statement.** M4-S4's cache drill
    opened with
    `echo "== drill: $MONTH${DRILL_STAGE:+ (PROBE) — not the milestone's evidence} =="`.
    Inside a `${var:+word}` expansion the word is still subject to quote
    processing, so that apostrophe in "milestone's" began a single-quoted string;
    bash swallowed the following four lines hunting for its close and then blamed
    the first thing that broke — **`line 72: $!: unbound variable`**, pointing at
    a `pf_pid=$!` after a port-forward that was entirely correct. `bash -n`
    reported it as `unexpected EOF while looking for matching '}'`, which is the
    honest message, and bisecting the file by prefix is what surfaced it. Sibling
    of #35, #53 and #60 — the fourth time this program has paid for prose sitting
    where a parser reads it as code, and the first time the parser was the shell's
    parameter expansion rather than a heredoc or a comment. Rule, now with four
    data points: **explanatory prose goes in a comment or its own `echo`, never
    inside an expansion, a heredoc body or an array literal.** And when a shell
    error names a variable you can see is fine, suspect the LINES ABOVE, not the
    line named.

63. **A threshold is only as good as the clock it is measured on — and a rerun's
    wall-clock is mostly the cost of launching at all.** The cache drill's first
    bar said "run 2 must be under 50% of run 1's wall-clock". The stage it was
    watching went **15.2s → 0.2s, a 98.7% saving**, and the drill went RED:
    `wall-clock 17s -> 9s (52.9%)`, because a one-stage rerun is dominated by the
    constant overhead of bundling, uploading and launching, which no cache can
    touch. The fix was not a looser bar — a looser bar would have hidden a real
    regression later — it was **the right clock**: the sum of the cached stages'
    own durations, which is the quantity the cache actually changes and the only
    one comparable between a one-stage probe and a six-stage pipeline. The
    wall-clock stayed, as the corroborating number a human notices, asserted only
    where it means something. General form: when a check goes red on something you
    can see working, ask what quantity the check is actually measuring before
    touching its threshold — the two are different questions and only one of them
    is about the bar.

64. **A protobuf answers `getattr` for its own fields only — so a misspelled
    field name is not an error, it is a confident default.** `flyte_run_actions.py`
    collected `int(getattr(status, "attempt", 0) or 0)`. The message
    (`flyteidl2.workflow.run_definition_pb2.ActionStatus`) calls that field
    **`attempts`**, plural. Nothing raised, nothing warned, and the reader reported
    `attempts: 0` for every action of every run it was ever pointed at — including
    the cache drill's recorded evidence — because `0` is exactly what an
    un-retried action should say. It surfaced only when something was SUPPOSED to
    be non-zero: a task with `retries=2` that raises on its first line still read
    `attempts: 0` while kubernetes had a pod named `…-a0-2` and the server said
    `attempts: 3`. This is gotcha #59's family one layer down — a signal
    consistent with success no matter what happened — and the defence is the same
    shape: pin the reader against the message's own DESCRIPTOR, so the test fails
    on the next typo in the next field rather than on this one only (F-027).

65. **`--follow` follows the LOG STREAM, and the stream ends when the first
    attempt's container exits.** `flyte run --follow` on a task with retries
    returned after **7 seconds** with the action still `RUNNING` and two retries
    still to come — so a check that read the action's state the moment the CLI
    returned saw `attempts=0, phase=RUNNING` and reported that the declared retry
    budget was not being honoured. It was; the observation was early. Sibling of
    #59 (`--follow` also exits 0 for a run that FAILED): the CLI's return is not a
    statement about the run's outcome OR about its completeness. Poll the server
    for a terminal phase and assert on that.

66. **Rebuilding the task image invalidates every cached Flyte stage — the cache
    key is not just code, inputs and data.** The pipeline's cache salt was built to
    cover the data (`_data_pin`, M4-S4) because the stages declare a month string
    and read a 1.8 GB volume Flyte cannot see. Observed 2026-08-18 (M4-S5 leg 2,
    run `rw98pj84z4jh5ldqrxqp`): `ingest`, `validate`, `build_features`, `train` and
    `evaluate` all came back **`CACHE_POPULATED`** — not `CACHE_HIT` — on a month
    they had each been populated for by earlier runs, with the same data pin and
    with function bodies this story never touched. What changed was the IMAGE: its
    tag is the git short sha, so every commit produces a new one, and it reaches a
    task two ways at once (the `TaskEnvironment`'s image, and `TAXI_PIPELINE_IMAGE`
    in `env_vars`) — either is part of the spec Flyte keys on. Which of the two did
    it is not separable here: they move together by construction.
    It is arguably CORRECT, and it agrees with F-026 from the other side — the image
    is where the model code comes from, so a hit against a previous image would be a
    result computed by code this tree does not contain. The trap is the unpriced
    cost: **one commit under `src/`, `scripts/`, `analytics/`, `docker/`,
    `pyproject.toml` or `uv.lock` turns the next full-data run back into a 31-minute
    fit**, not M4-S4's 11 seconds. Two consequences worth carrying: a cache drill
    must hold the image CONSTANT (ours does, deliberately), and a gate must read
    RECORDED cache evidence rather than re-asking the control plane about the latest
    run — whose stages are `CACHE_POPULATED` in any session that rebuilt.

67. **A checker's "every X must have Y" goes red on the one X that was BUILT
    without Y — and the repair is to derive what counts as an X, never to add an
    exclusion list.** `verify-m4` §3 asserts that every recorded on-cluster run has
    a `main` parent action (the stages ran as ONE workflow, not as seven launches).
    Its first run went RED naming `rklz7vdv2d59bn8kbp8d` — the **retry probe**
    (`pipelines/flyte/retry_probe.py`), a single task that always raises. It is
    *supposed* to have no parent and *supposed* to have failed; §5 reads it as the
    evidence that the retry budget is finite. So a guard fired because a component
    behaved exactly as designed, which is #50's disease, caught inside the gate
    written to honour #50. The tempting repair is `if "retry-probe" not in name` —
    a string match on a naming convention the next probe will not follow. The
    repair taken instead was to DERIVE the class: a *pipeline* run is one whose
    actions include at least one stage of this graph (and the stage set is itself
    derived from `tasks.STAGES` and the task decorators in `workflows.py`), so the
    probe falls out by what it IS. Sibling of #52 — change the mechanism, not the
    value. The excluded record is PRINTED rather than silently dropped: a filter
    nobody can see is how a gate quietly stops checking half its inputs.

68. **A test that forbids RUNNING a command will catch the message that tells a
    human to run it, and will catch a namespace named after a CLI.** Three
    assertions in `tests/unit/test_verify_m4.py` went red in one run, all three on
    the checker rather than the checked: `"make pipeline" not in body` caught the
    gate's own advice line ``run `make pipeline-cache-drill` `` — exactly what the
    reader of a RED cache leg needs — and `"flyte get" not in body` caught
    `kubectl -n flyte get deploy`, two words that are only a Flyte CLI call if you
    read them without the `kubectl` in front. This is #35's house rule ("match the
    INVOCATION, never the word") failing in the direction nobody expects: the
    earlier cases were prose being parsed as code, this one is a TEST parsing prose
    as code. The fix is a shared `invokes(body, cmd)` helper requiring the needle to
    sit where a shell would START a command — line start, or after `|`, `&&`, `;`,
    `$(`. A backtick is deliberately NOT a command position in this repo: backticks
    appear inside message strings far more often than in command substitutions, and
    #60 already established which of those two mistakes costs more.

69. **A milestone gate can be replaying evidence that is not in the repository —
    and say the opposite in its own header.** `automation/runs/` is gitignored
    wholesale (`git ls-files automation/runs/` is EMPTY), so `verify-m3`'s bake-off
    replay and every record `verify-m4` reads are MACHINE state: absent from a
    fresh clone, and — the part that matters — invisible to review, so an edit to
    one leaves no diff. Both gates' red teams simulate exactly that edit. Two
    artifacts had already written the false version down: `verify_m3.sh`'s header
    listed "committed JSON" among its inputs, and its red team's failure path
    advised `git checkout -- automation/runs/m3s5/bakeoff.json`, a command that
    cannot restore an untracked file — which is the tell that the belief was held
    rather than merely mistyped. Run `git check-ignore -v <the file your gate
    reads>` before writing "committed" anywhere near a verifier. Filed as **F-029**
    (the policy fork is open to ARCH); the false statements were corrected the day
    it was found. #51's question — *could this component tell if its own claim were
    false?* — asked of a gate's INPUTS rather than of its outputs.

    *Resolved 2026-08-19 (M5-S1): ARCH decided option A and the mechanics landed —
    `automation/runs/**/*.json` is tracked, logs and `.status` stay ignored. The
    STATE is fixed; the GOTCHA is not retired, because it is about the check, not
    about this one directory. Two mechanics worth carrying forward. (1) gitignore
    semantics: a bare `automation/runs/` exclusion makes git stop descending into
    the directory, so a `!automation/runs/**/*.json` rule beneath it does NOTHING —
    the exclusion must be pattern-based (`automation/runs/**`), the directories
    re-included (`!automation/runs/**/`), and the files re-included last. (2) both
    red teams now edit TRACKED files, which makes a clean drill's clean tree a
    checkable property and gives a crashed drill the `git checkout --` its own
    recovery line used to promise falsely.*
