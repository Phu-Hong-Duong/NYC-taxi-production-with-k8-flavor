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
   user-stated 2026-08-12), then `wsl --shutdown`. *(Amended 2026-08-24, program
   close: the PO re-granted to `memory=40GB` on 2026-08-22 — `free -h` reads 39Gi
   live, the full platform runs inside it. The check is unchanged; only the number
   this machine grants moved.)*
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

70. **A positive discriminator can name a signature the deployed thing
    deliberately suppresses — and then it goes RED over a perfectly good
    install.** M5-S1's accept check for the serving route did everything #59
    asks: it refused to read "no error" as success, and demanded a POSITIVE
    artifact from the component that was supposed to answer — `Server: nginx` in
    the response headers. Modern ingress-nginx omits that header on purpose, so
    a healthy controller, correctly scheduled, serving a correct 404, failed a
    check that was structurally right and factually wrong. #59 tells you to
    assert on an artifact; it does not tell you to check that the artifact
    EXISTS. So the follow-up question is: *does this thing actually emit the
    signature I am about to require?* — and the way to answer it is to ask the
    server, not to remember. `GET /healthz -> 200` is the controller's own
    endpoint (`/nginx-health` returns 404, checked); it is the same shape M4-S2
    settled on for Flyte, where `/healthcheck` — the 1.x path everyone types —
    404s and `/healthz` answers. Two rejected candidates are worth naming
    because both look reasonable: correlating the request with the controller's
    ACCESS LOG (its default backend does not log 404s, so a correct install
    produces silence — a discriminator that fails precisely on success), and
    matching the 404 body's `<center>nginx</center>`, which would pass for any
    nginx anywhere. Sibling of #55: a verifier that fails for its own reasons
    and blames the artifact.

71. **A wait that the thing you are REPLACING can satisfy is not a wait.**
    M5-S2's deploy applied a changed InferenceService and then waited with
    `kubectl wait --for=condition=Ready inferenceservice/nyc-taxi-eta`. On a
    first install that is exactly right. On a RE-deploy it returns in
    milliseconds — because the condition is about the InferenceService, and the
    InferenceService is Ready: the OLD predictor is still serving while the new
    ReplicaSet rolls out. The accept check that follows then interrogates the
    pod being replaced and passes, and the script's own `get pods` printed the
    evidence in plain sight (`Init:0/1`, AGE `0s`) without anything reading it.
    What made it visible at all was luck of subject matter: the change under
    test was a version stamp, so the predecessor answered `(unversioned)` where
    the successor would say `2`. Had the change been a resource limit, a
    tolerance, or a model swap between two artifacts that both load, the deploy
    would have printed a green line about a pod that no longer exists.
    The fix is one line and it is about WHICH object: `rollout status
    deploy/<isvc>-predictor` waits for the new ReplicaSet specifically, and the
    parent condition stays as a second leg because it is what KServe itself
    considers serving. Family: #59 ("assert on the artifact this thing exists to
    produce") and #65 ("`--follow` returns when the FIRST attempt's container
    exits") — three shapes of one mistake, *the signal I am waiting on is not
    about the thing I am waiting for*. The general question to ask of any
    readiness wait: **could this condition be true right now for a reason that
    has nothing to do with my change?**

72. **A NaN cannot travel as JSON, and Python will let you try.**
    `json.dumps(float('nan'))` returns the bare token `NaN` — valid Python
    output, invalid JSON, emitted BY DEFAULT because `allow_nan=True` is the
    default. So a client can serialise a perfectly correct feature matrix into a
    document no conforming parser will accept, and the failure arrives from the
    far side as a byte offset: `HTTP 422 {"type":"json_invalid",
    "loc":["body",1241],"msg":"JSON decode error","ctx":{"error":"unexpected
    character"}}`. Nothing in that names the feature, the row, the zone, or the
    word NaN. At M5-S3 this had been live since the endpoint existed: zones
    264/265 are TLC's "Unknown" and have no centroid by design, so nine geometry
    features are NaN — LightGBM's documented missing path, exactly what the model
    was fitted on — and every one of those requests, ~1% of all trips including
    the single most common OD pair in the data, came back 422. It was latent
    because every earlier client passed a DataFrame straight to LightGBM (where
    NaN is ordinary) and because the one accept-check row had full geometry.
    Missing goes on the wire as `null`, which the runtime decodes back to NaN;
    an infinity is REFUSED rather than encoded, because it is equally
    unrepresentable but is not a missing value and mapping it to `null` would
    launder a broken feature into a plausible quote. Then set
    `allow_nan=False` on the dump: the encoding is the fix, and that flag is the
    guard that makes the NEXT such path fail loudly on this side rather than
    quietly on the other. **The general shape: a serialiser whose permissive
    default produces output its own format forbids will fail at the receiver, in
    the receiver's vocabulary, about a byte.** Family with #59 — the error you
    get is not about the thing that is wrong.

73. **A red team that goes GREEN under its own tampering has found something —
    read it before you loosen it.** M5-S3's parity drill planted its first cause
    by rotating the ORDER of the inference request's inputs, on a property the
    client's docstring had asserted since the previous story: that a V2 payload
    is positional, so a reordering swaps `PULocationID` for `DOLocationID` and
    returns a plausible number. The measured delta was `0.000e+00` on all 16
    rows. The tempting readings are both wrong — "the tampering was too weak, use
    a bigger one" and "the test is broken". The true reading is that **the
    documented property was false**: mlserver hands MLflow a NAMED frame and the
    logged signature reorders it, so wire order is not load-bearing here. Two
    consequences, and the second is the point. The plant was moved to a cause
    this runtime CAN express (every feature under its own name and dtype carrying
    its neighbour's values → 42.10 minutes of skew, every input individually
    valid). And the false claim was CORRECTED rather than deleted, because the
    practice it prescribed — send the model's own column order — is still right
    for reasons that survive: a positional V2 runtime is legal, M7's transformer
    may be one, and the ordering costs nothing. What changed is what is claimed
    to be protecting us, which is now known to be the logged signature. Sibling
    of #51 — *could this component tell if it were false?* — asked of a drill
    instead of a component.

74. **A load test run at the CPU limit measures the QUOTA, not the service — and
    a throttle counter says so where a mean utilisation does not.** M5-S4's ramp
    picked its headline rate with the obvious rule: the highest step that held
    its stated rate and returned no errors. It chose **8 req/s**, at which the
    predictor's container ran at **2.003 of its 2-core limit** and was
    CPU-throttled in **601 of ~601 periods**; p50 went from 18 ms at 6 req/s to
    **115 ms**, and every millisecond of that was the kernel stopping the
    process rather than the model taking longer. Held-its-rate and no-errors are
    both satisfied *at the ceiling* — saturation shows up as latency, not as
    failure, which is exactly why those two clauses cannot find it. Two further
    consequences: the p95 published from such a run is a property of the cgroup
    and moves the day somebody edits `limits.cpu`, and the next phase becomes
    unreadable, because a pod with no headroom drops the occasional request all
    by itself and the drill goes red for a reason unrelated to what it is
    testing. **Read `cpu.stat`'s `nr_throttled` across the window, not just the
    mean.** They are different statements: mean utilisation is a budget, the
    throttle counter is a latency — at 2 req/s this container averaged 35% of
    its limit and was still throttled 46 times, because CFS accounts in 100 ms
    periods and one inference burst wider than the quota inside one period is
    enough. `kubectl top` cannot answer this (and was unavailable here anyway,
    no metrics-server); the cgroup files can, read straight out of the container
    and differenced.

75. **An outage is not the span from the first error to the last one.** The same
    drill reported `outage_seconds_measured: 182.4` for a kill at T+25 of a 210 s
    window — computed, reasonably enough, as `last_error - first_error`. What had
    actually happened was a **13-second** unavailability followed by 1,400
    successful requests with about ten sporadic 502/503s scattered through them
    (a consequence of #74, above). Folding the two together invents a
    three-minute outage that never occurred, and it was headed for a runbook.
    The failure is the same species as #63 — a bar measured on the wrong clock —
    and so is the fix: **the right quantity, never a looser threshold.** Separate
    them: the *outage* is anchored on the first FAILURE after the kill and closed
    by the first SUCCESS after that, and the residual error rate afterwards is a
    second number with the pre-event segment of the same run as its control. Two
    anchoring traps sit either side of the correct one: anchoring the start at
    the kill overstates it (a pod takes a moment to stop answering), and
    anchoring recovery on "the first success after the kill" *understates* it
    catastrophically — it finds one of those still-succeeding requests 50 ms in
    and reports a 0.05-second outage for a service about to be down for fourteen
    seconds. Both were written and both were caught by replaying the real
    timeline as a test fixture, which is the cheapest way to find out what a
    definition actually computes.

76. **A number quoted in prose exists only at the precision it was written at —
    and a substring is not a number.** `verify-m5` cross-checks the serving
    runbook against the records it cites, so that a document an operator acts on
    at 3 a.m. cannot drift from the measurement it claims to quote. The first
    version demanded the record's value verbatim and went RED against a runbook
    sensibly writing **`104.2 ms`** for a recorded **104.226** — #42's rule
    (a number through a `%.Nf` exists at that precision) arriving in a new place,
    prose instead of a registry tag. The fix — accept the value rendered at any
    precision the record can produce — was then written as a bare substring
    search, which is worse than the bug: `"14"` is a substring of `"14.53"`, so
    a rewritten `14.251` would have passed against a runbook quoting `14.53`,
    i.e. the loosening landed exactly on the fault the red team plants. **Anchor
    the match on both sides** (`(?<![\d.])14(?![\d.]?\d)`). The general shape:
    when a check compares a machine's number with a human's sentence, the
    comparison needs a precision policy AND a tokenisation policy, and the second
    one is the easier to get silently wrong.


77. **A rollout that can never complete looks exactly like a system with nothing
    wrong with it.** Enabling metrics on ingress-nginx changed the controller's
    pod template, and the rollout deadlocked: the values file pins the controller
    to ONE node (it has to — that is the node whose port 80 kind publishes as
    8081) with `hostPort` and `replicaCount: 1`, and the chart's default
    `RollingUpdate` at one replica means *start the new pod, then stop the old
    one*. The new pod can never bind port 80 while the old one holds it —
    `0/3 nodes are available: 1 node(s) didn't have free ports for the requested
    pod ports`. It sat Pending for **10 minutes**. Meanwhile the OLD pod served
    perfectly, an availability probe recorded **840/840 ok**, and the only thing
    that would eventually have gone wrong is a `helm upgrade` timing out twenty
    minutes later with a healthy cluster underneath it. The "zero outage" was the
    most convincing possible evidence for the wrong conclusion. `hostPort` +
    `replicaCount: 1` + a single-node `nodeSelector` **forces**
    `updateStrategy: Recreate`, and the honest cost — every future change to that
    Deployment is a real outage of the only route in — is not a choice, because
    no strategy that keeps the old pod alive can schedule the new one. Ask of any
    green rollout: *did the thing I changed actually get replaced?* Pod AGE
    answers it in one command (F-033).

78. **A scrape target being `up` says nothing about whether anything is being
    measured — and a component that was never DISCOVERED is not even a target.**
    The monitoring accept check's first run was green with every target up, and
    three of the board's panels returned zero series. Each zero was a different
    real defect: (a) ingress-nginx's metrics Service exists but the chart
    annotates it with nothing, and endpoint discovery keys on exactly that
    annotation — so the component was absent from the target list rather than red
    in it; (b) the chart's default 1-minute scrape interval makes `rate(x[1m])`
    evaluate to **nothing at all**, because a rate needs two samples inside its
    window; (c) a genuinely down target (KServe's controller behind
    kube-rbac-proxy over HTTPS) that a reader would learn to ignore. What made
    all three visible was executing **every panel's own query** out of the
    checked-in dashboard JSON and treating **zero series as a FAILURE**. An empty
    panel is indistinguishable from a quiet system, which means green must not be
    the default rendering of "no data" — this is #59 ("assert on the positive
    artifact") applied to a dashboard, where the artifact is a series and not a
    rectangle (F-034's neighbourhood).

79. **`kubectl wait --for=condition=X` silently requires the controller to have
    updated `observedGeneration`, so a perfectly healthy resource can be
    unwaitable forever.** `make serve` hung for fifteen minutes and then FAILED
    over an InferenceService whose every condition read `True` and whose pod was
    `Running 1/1`. kubectl v1.36 ignores a resource's conditions while
    `status.observedGeneration < metadata.generation` — which is *correct*: a
    condition describing the previous spec is not evidence about this one. But
    KServe v0.20.0 reconciles the new spec completely (`PredictorReady`
    transitions, naming the NEW ReplicaSet) and then leaves `observedGeneration`
    behind; observed at `generation=3` / `observedGeneration=2`. The tell is that
    `--for=condition=` times out for **every** condition on the object while the
    `--for=jsonpath=` form reading the same condition returns `condition met` on
    the same object in the same second — so the question to ask is not "is my
    condition true?" but "does this controller maintain observedGeneration?", and
    a single `kubectl get <res> -o jsonpath` over `.metadata.generation` and
    `.status.observedGeneration` answers it. Worst part: under `set -e` the
    timeout takes the deploy's accept check with it, so the ONE failure mode is
    that a correct deploy reports as a broken one — #55's family, a verifier
    failing for its own reasons and blaming the artifact (F-036).

80. **A 15-second outage is what a *destroyed* pod costs, not what a *deploy*
    costs, and quoting one for the other overstates a release by 30x.** This
    program had measured three serving mutations at 14.53 s (killed pod), 15.0 s
    (ingress roll) and 18.24 s (stop/start), and an SLO document written from
    them predicted "a model re-deploy ~15-18 s" by analogy. Measured across a
    real `make serve`: **0.5 s**, one failed request of 400. The mechanism is the
    one thing the analogy ignored — at ONE replica `RollingUpdate`'s
    `maxUnavailable: 25%` floors to **zero**, so the Deployment is *forbidden*
    from having no available pod and a surge pod must become ready before the old
    one is removed. All three of the slower numbers destroy the only pod first (a
    kill has nothing waiting, a stop removes `spec.replicas`, and ingress-nginx
    was FORCED onto `Recreate` by a `hostPort` its surge pod could never bind —
    F-033). Before quoting an outage as the cost of a *class* of change, ask what
    the rollout strategy is allowed to do: three numbers agreeing with each other
    is not evidence about a fourth mechanism (docs/slo_serving.md §4.1).

81. **A canary that is configured, linked, logged clean and moving zero traffic
    looks exactly like a canary at 0%.** ingress-nginx keys backends by
    `<namespace>-<service>-<port>` and a backend may hold exactly ONE role. Point
    a canary Ingress at a Service that some *non-canary* Ingress also routes to
    and the ordinary registration wins: the link is created — the main backend
    really does list it under `alternativeBackends` — while `noServer` stays
    false and `trafficShapingPolicy` comes back `{weight: 0, weightTotal: 0}`.
    Measured at weight 50: **0 of 200 requests moved**, with no error, no warning
    and no event anywhere. It bites this program specifically because **KServe
    RawDeployment generates an Ingress for every InferenceService**, so the
    natural canary target always already has one and the natural implementation
    is the broken one. The fix is a dedicated Service selecting the same pods and
    referenced by the canary Ingress alone (**100 of 200 moved**,
    `noServer: true`, `{weight: 50, weightTotal: 100}`). The rule that generalises:
    **verify a traffic split from traffic counters, never from its own
    configuration** — #59 asked of a release mechanism (ADR-011 condition 1).

82. **`kubectl annotate isvc` is not a metadata edit — it rolls the pod.** A
    spike needed the KServe controller to reconcile and reached for the cheapest
    "spec-neutral" nudge there is: an annotation on the InferenceService, added
    and then removed. KServe propagates an isvc's annotations onto its pod
    template, so both edits were Deployment changes and the champion's only
    predictor was replaced twice. The probe's own end-state batch caught it —
    **174 of 200 requests returned 502** — with the controller logging
    `connect() failed (111: Connection refused)` against the replaced pod's dead
    IP. Same family as #77 (pod AGE is the one-command answer to "did the thing I
    changed get replaced?"), and the lesson is narrower and more useful: on a
    resource an operator templates from, **there is no such thing as a metadata-only
    field** until you have checked what the operator copies downstream (F-038).

83. **In the Open Inference (V2) protocol the model name is in the URL PATH, so
    two InferenceServices cannot share a traffic split without extra work.** A
    canary that correctly moved half the traffic returned **404 on every single
    canary-routed request** — `/v2/models/nyc-taxi-eta/infer` reaching a backend
    whose mlserver serves `nyc-taxi-eta-shadow`. It is not the schema mismatch
    everyone predicts (that wall is real and is *behind* this one, never reached),
    and it cannot be papered over at the ingress: **ingress-nginx applies only
    `canary-*` annotations from a canary Ingress and inherits the rest from the
    main one**, so `rewrite-target` on the canary changed the share by 0 points.
    Ask of any traffic-split design: do both backends answer to the same NAME, in
    whatever the protocol makes the routing key? (ADR-011 condition 2.)

84. **A readiness wait can be about a different OBJECT than the thing your next
    step uses.** A first shadow deploy passed `rollout status` (the ReplicaSet)
    AND the InferenceService's `Ready` condition (the predictor), and its accept
    check then got a bare nginx **404** — because KServe creates the Ingress as a
    separate object and ingress-nginx has to observe it and reload. The Ingress
    was **6 seconds old** at the 404 and the same quote succeeded on retry. This
    is #71's family with a genuinely different mechanism: #71 was "a wait the
    thing you are REPLACING can satisfy", and there is no predecessor on a first
    deploy. Wait on the route by ASKING it — `/v2/models/<name>/ready` through the
    real host header is the only instrument that answers the question the accept
    check is about to ask (F-037).

85. **A hand-authored object must not take a name an operator generates — the
    collision is accepted, works for seconds, and then undoes itself.** The
    first canary release drill named its Ingress `nyc-taxi-eta-canary`, which is
    exactly what KServe RawDeployment generates for the InferenceService of that
    name. `kubectl apply` returned success, the canary annotations sat on the
    **controller-owned** object, and the controller reconciled them away —
    **0 of 420 requests moved at weight 10, 3 of 300 at weight 100**, no error
    anywhere. The three that moved are the window between the apply and the
    reconcile, which is the only tell there is. Worse, the symptom is
    byte-for-byte #81's (a canary pointed at a Service some other Ingress
    claims), and this program had just spent a story learning #81 — so the
    obvious diagnosis was the wrong one. Two cheap habits close it:
    `kubectl get <kind> <name> -o jsonpath='{.metadata.ownerReferences[*].name}'`
    before writing to anything you did not create, and a precondition that reads
    the CONTROLLER's runtime state (`noServer: true` plus the applied weight)
    rather than the annotation you just applied. **What caught it was measuring
    the split from counters instead of from its own configuration** — the same
    discipline #81 bought, paying for itself against a different cause (F-039).

86. **"A deploy costs 0.5 s" is not "a rollback costs 0.5 s" — and the
    asymmetry is in the SCHEMA, not the pod.** #80 established that re-deploying
    a model costs 0.5 s at one replica. A rollback is three moves, and the second
    one — moving `configs/train.yaml: features.version` — changes what every
    client on the wire SENDS, while the pod still holds the old model. Measured:
    **v2 → v1 cost 27.93 s of failing requests** (55 of 85 probes, almost all
    `HTTP 500` at MLflow's logged signature), against **0.501 s and a single 502**
    for v1 → v2. The direction that hurts is the one that REMOVES features: a
    24-column request sent to a 5-column model is tolerated, because the
    signature takes the columns it names and ignores the rest, while a 5-column
    request to a 24-column model is missing inputs and is refused. So the cost of
    a config-coupled rollback is bounded by the DEPLOY, not by the swap — and the
    remedy that follows (deploy first, move the config line last) is a
    consequence of the measurement and must be rehearsed before it is trusted,
    not substituted mid-incident (F-040).

87. **A `rate(...[5m])` window is EMPTY when an event begins, so a threshold
    argued from the steady-state ratio is an argument about the wrong quantity.**
    `docs/slo_serving.md` justified A-2's 10% edge-5xx bar arithmetically: at
    4 req/s a ~15 s outage costs ~60 of the ~1,200 requests a 5-minute window
    carries, so *"10% is unreachable by any single recovery ever measured here"*.
    Gameday 1 killed the predictor at exactly that shape and the share **peaked
    at 0.5000** — `ServingEdge5xxRateHigh` went `pending` at T+89.2 s and back at
    T+103.2 s, `PredictorNoAvailableReplica` at T+59.1 s → T+74.1 s. Thirty
    seconds into a load run the window holds thirty seconds of traffic, so the
    denominator is small and nearly all of it is the outage; 6.1% is what the
    ratio decays TO. **What prevents a self-heal from paging is the `for:`
    sustain, not the threshold.** The same mechanism runs backwards on the way
    up: A-6's throttled fraction needed **244 s** to climb 0.41 → 1.00 as its
    window filled, so its 10-minute sustain started four minutes after the load
    did and it fired at T+844.3 s = 244.1 + 600.2. When you write a bar, ask what
    the denominator holds at t=0 — and write down that an on-call will watch
    alerts sit `pending`, in red, through every ordinary self-heal (F-041).

88. **Two alerts' arrival ORDER is decided by their `for:` windows, never by the
    causal story about which condition happens first.** A-7's own `why`
    annotation claimed it fires before A-5 *"because a pod that never initialises
    never had a replica to lose"* — true about the cause, silent about the
    sustains. Breaking the storage credential made both expressions true in the
    SAME scrape (pending together at T+30.1 s); the 2m rule fired at T+150.2 s
    and the 3m rule at T+210.2 s, sixty seconds later, deterministically. What a
    pair of alerts actually buys is a SIGNATURE rather than an ordering (*A-5
    alone* = the replica is gone; *A-5 then A-7* = the replacement cannot fetch
    its model), and that holds whichever arrives first — so correct the claim,
    not the threshold (F-042).

89. **A component under stress is an unreliable reporter of its own stress.**
    Fifteen minutes at 8 req/s (past the measured 2-core ceiling) made
    `PredictorLatencySLOBurning` fire at T+349.3 s and go back to **inactive at
    T+514.3 s while the load was still running**. The predictor's own `/metrics`
    had gone from 4 ms to **`scrape_duration_seconds` 4.613 s with `up == 0`** —
    a scrape that failed outright — while the IDLE second predictor, scraped by
    the same job every 15 s, stayed at 0.004 s. A failed scrape makes the series
    stale, a stale series makes the expression evaluate over nothing, and an
    expression over nothing is not `> 0.05`. *"Measure at the edge because a dead
    predictor cannot report its own absence"* is the loud version of this; this
    is the quiet one, and **the tell is a firing alert going inactive while the
    symptom persists**. Keep at least one signal for each subject on the other
    side of the failing process (A-6 reads the kubelet's cAdvisor and fired
    regardless), and note that an idle second instance of the same exporter is
    the cheapest control there is (F-043).

90. **A prose-vs-record check with no precision FLOOR passes against a number
    the record does not hold — and it is gotcha #76 arriving through rounding
    instead of through tokenisation.** `verify-m6` §7 compares every headline
    number `docs/gameday_m6.md` quotes against the record it cites, rendering
    the record's value at each precision it can legitimately be written to
    (a document sensibly writes `13.75 s` for 13.75 and `844.3` for 844.3 —
    #42). Its first draft started that range at **zero** decimals, so 13.75 also
    rendered as **`14`** — and `14` appears in almost any document of any
    length. The check therefore passed while the red team's planted 13.501 sat
    in the record, because *that* rendered as `14` too. **A comparison whose
    loosest accepted form is one a document is almost certain to contain is not
    a comparison.** The floor is one decimal; an integer-valued record still
    matches as `55`, because the trailing zero is stripped. Two properties, both
    load-bearing and neither obvious: #76's anchors stop `13` matching inside
    `13.75`, and this floor stops `13.75` becoming `14`. Both were found by a
    red team planting a value close enough to be plausible — a drill that had
    planted `999` would have gone green on both legs and taught nobody anything.

91. **The label an artifact PRINTS is a different artifact from the label it
    carries in its header, and only the printed one is read during an
    incident.** M6-S5 leg 1 moved the platform restore's honest label one notch
    — "NOT REHEARSED" -> "scratch-rehearsed 2026-08-19; a full restore over a
    dead platform still not" — in `scripts/platform_backup.sh`'s header, in the
    `MANIFEST.txt` it writes, in the gameday write-up and in CLAUDE.md, whose
    backup row then asserted that *every* artifact said so. Two did not: the
    script's own `echo` on line 85 still told every future operator `restore NOT
    rehearsed (M6 gameday candidate)`, and `ledgers/deployments.md` still
    carried the M4-S2 row's unqualified claim. Nothing was wrong with the
    system; a *claim about the system* was stale in exactly the two places a
    reviewer does not look and an operator does. **When a status label moves,
    enumerate the artifacts that carry it — including the RUNTIME output — and
    make a check assert the compound claim** (`verify-m6` §7 now requires both
    halves in every artifact and refuses an `echo` that mentions rehearsal
    without saying "scratch"). Historical ledger rows are corrected with a dated
    note BESIDE the original, never rewritten: decisions were made from what
    they said (the `error_memo_m2.md` §9 precedent).

92. **A pushed metric arrives with the WRONG `job` label unless one flag says
    otherwise, and every rule that selects on it then matches nothing —
    silently.** Prometheus overwrites a scraped sample's `job` and `instance`
    with the target's own, which is correct for a service reporting on itself
    and exactly wrong for a pushgateway reporting on somebody else. Without
    `honor_labels: true` the drift series arrive as `job="pushgateway"`, the
    pusher's `job="taxi-drift"` is demoted to `exported_job`, and every rule in
    the `crosstown-drift` group **evaluates over nothing**. Nothing errors: the
    rules stay `health=ok` and sit `inactive` forever, which is indistinguishable
    from a healthy system (#78's family). The related trap is worse and was
    avoided by luck as much as design: had the gateway ALSO carried a
    `prometheus.io/scrape` annotation it would have been picked up by the chart's
    generic endpoints job, which does not set the flag — so a *correct* dedicated
    job and a *label-mangling* accidental one would both have scraped it, giving
    two contradictory copies of every number. One gateway, one scrape job, one
    flag (M7-S3).

93. **A checker whose unit of judgement is coarser than the fact it is judging
    reports a failure over a system behaving exactly as predicted.** The drift
    drill predicts that A-9 FIRES for 2020-03 *and* stays quiet for 2020-01 and
    2020-02 — three statements about one rule name — while its `fired_at` map was
    keyed on the alert name alone. So it printed `ok A-9 FIRED — as predicted`
    and `FAIL A-9 fired and was predicted INACTIVE` in the same run, both correct
    readings of a prediction it could not express, and went RED over a perfect
    result. #67 with the grain wrong instead of the population wrong. The repair
    is never a looser bar: read Prometheus's per-series `alerts` array, which is
    **strictly the stronger claim** — a bar so low that an ordinary January trips
    it passes a name-level check and fails a per-series one. And note what
    survived the repair unchanged: the PREDICTION object, because the defect was
    in the judge (M7-S3).

94. **A second witness that cannot be READ reports maximum disagreement, which
    is the most alarming thing it could say and the least true.** The Evidently
    corroboration printed `the two instruments DISAGREE` for every column with an
    empty ranking on one side; nothing had disagreed, the parser was looking for
    a `metric_id` and a `status` field that the payload does not have (it carries
    `metric_name`, a structured `config` and `value`). Two lessons, and the
    second is the general one. First: read a third-party payload's SHAPE off a
    real object before parsing it — one throwaway script printing `snapshot.dict()`
    answered it in seconds. Second: **check the failure DIRECTION of any
    cross-instrument check you write.** A comparison that degrades toward "they
    agree" hides its own breakage; one that degrades toward "they disagree"
    screams — and both are wrong, so what the code must do is distinguish "no
    verdict" from "a verdict of disagreement". A quiet `nan` in the output column
    was the only honest signal in that run, and it was easy to read past (M7-S3).

95. **A `hasattr` guard on the CONTAINER makes an unchecked access to the ELEMENT
    look checked — and the code that runs *after* the expensive part is the code
    no test has ever executed.** The first full-data retrain fitted for 28
    minutes, cleared the floor at +3.30%, was correctly refused by the incumbent
    condition, and then died writing the verdict down on `c.text`; `gate.Check`
    carries `name`/`passed`/`detail` and never had a `text`. The line was
    *guarded*: `[... for c in decision.checks] if hasattr(decision, "checks")
    else None`. `Decision.checks` is a dataclass field and is therefore always
    present, so the guard protected nothing — what it did was put the word
    `hasattr` one token to the left of the unchecked access and make the whole
    expression read as defensive. **Why it survived review is the general
    lesson**: every test of that module asserted on its SOURCE (`'"ended_by"' in
    RUN_SOURCE`, an `ast` walk for a forbidden verb), which is the right
    instrument for a law with no runtime symptom and the wrong one here — **a
    string test sees a field being written and cannot see that the field does not
    exist.** Nothing had executed the line because executing it cost the fit. The
    repair is not a `try`: make the post-expensive step a FUNCTION that can be
    called in microseconds, and test it on a real object built by the real
    producer. Ask of any long job: *if the last 5% of this raises, what did I
    spend and what do I keep?* (M7-S4).

96. **An unhandled crash exits with a status your program may already have given
    a meaning, and the status file is what the next session reads.** The same run
    exited through a traceback, which landed on **2** — and this repo's retrain
    CLI defines 0/1/2/3 as *passed · refused · the challenger could not be built ·
    no verdict was issued*. So `automation/runs/m7-retrain-fulldata.status` read
    `FAILED 2`, the handoff's decoding key rendered that as *the challenger could
    not be built*, and the next session was told the exact opposite of what had
    happened: the challenger had been built, fitted and judged. The log was the
    only witness, and logs are gitignored here. **If you design an exit-code
    vocabulary, handle the case you did not enumerate** — catch it, print the
    frame, and exit OUTSIDE the vocabulary (4 here) with a message saying what is
    and is not true. Note the near-miss that makes this worse than it looks: an
    uncaught Python exception exits **1**, which in this vocabulary means
    *REFUSED* — a crash would have been read as a verdict (M7-S4).

97. **`make` collapses every failing recipe to exit 2, so an exit-code
    vocabulary does not survive being detached as a make TARGET.** The retrain
    was given 0/1/2/3/4 — *passed · refused · could not be built · no verdict ·
    crashed* — and #96 had just added the 4 so a crash could not wear a verdict's
    clothes. The repaired re-run then refused correctly (CLI exit **1**) and
    `automation/runs/m7-s4-retrain-rerun.status` read **`FAILED 2`**: the third
    session in a row misinformed by an exit code, and the first where nothing in
    the repository was at fault. **GNU make exits 2 for ANY failed recipe** —
    measured against a throwaway makefile, a recipe exiting 1 comes back 2 and a
    recipe exiting 3 comes back 2 — and `make detach` runs `make TARGET`, so the
    vocabulary collapses to {0, 2} at the launcher and 2 is a word already in
    use. **The fix is not a bigger vocabulary; it is to stop reading verdicts out
    of exit codes.** A refusal writes a RECORD and a crash writes nothing, so the
    record's presence and its `verdict` field are the discriminator, and it is a
    positive artifact rather than a decoded number (#59). Two cheap mitigations
    beside it: have the recipe echo the CLI's own `$?` into the log *and re-exit
    with it* (swallowing the code to make the line printable turns every refusal
    into a green make), and refuse the tempting `CMD=` escape hatch on the
    launcher — retyping the recipe at the launch site preserves the exit code by
    creating a twin. Argparse also exits 2 on a usage error, which happens to
    collide with the same word: **a vocabulary built on small integers shares
    them with every tool it passes through** (M7-S4 completion leg).

98. **A pushgateway keeps nothing across a restart, and the staleness rule
    written to catch a stopped producer cannot fire on an ABSENT series.**
    `make verify-m7`'s one live query returned **zero** `taxi_drift_*` series
    against three tracked records saying there should be three. Nothing had
    drifted: the gateway pod had restarted after a host reboot, and a bulletin
    board with no persistence loses its board. The trap is what happens next.
    `docs/slo_serving.md` §8.5 argues — correctly — that a pushed metric
    **persists** after its producer dies, which is why A-10 compares
    `time()` against the newest `*_last_run_timestamp_seconds`. Over no series
    that expression **is no series**, so A-10 sits `inactive`, the drift board
    renders empty, and both are indistinguishable from a healthy month.
    **Gotcha #78's empty-panel disease one layer up**: the guard written against
    *a number nobody refreshed* is blind to *a number nobody has*, and the only
    rule shape that can see it is `absent()`. Generalises past pushgateways —
    any rule of the form "this value is too old" is silent about the value not
    existing, and the two states need different rules (F-050, M7-S5 leg 2).

99. **Three needles in one test file matched WORDS instead of INVOCATIONS —
    and all three were the gate quoting itself.** `test_verify_m7.py`'s first run
    failed on `--push` (inside the advice line the gate PRINTS for an operator),
    on `ingest_month` (a prefix of `ingest_months`, the analyst-layer VIEW the
    gate legitimately reads), and on `retrain(` (inside the sentence reporting
    what `ast` had just found about `retrain`'s signature). #35 and #68 said
    prose must not sit where a parser reads it as code; this is the same lesson
    arriving from the opposite direction — **the more a checker EXPLAINS itself,
    the more surface it offers a checker of the checker**, and the more of its
    own vocabulary appears in its output. The fixes are anchors at both ends,
    command position, and — for the third — picking a property the sentence
    cannot satisfy: the gate must never IMPORT the callable it inspects
    (M7-S5 leg 2).


100. **A ratio whose DENOMINATOR is derived from the data it measures is not
    monotonic in the thing it watches.** A-9 reads trips-per-day this month over
    trips-per-day in the reference, and the drift job computed the days as
    `COUNT(DISTINCT observed date)`. A day on which the city took no trips
    contributes no row, so it left the numerator **and the denominator
    together** — and the ratio therefore measured *how busy were the days that
    happened*, which RISES as a shutdown deepens. Measured on the real COVID
    month by deleting its quietest days outright, a strictly worse world:
    0.3913 (fires) → 0.4768 (fires) → **0.5143 (SILENT)** → 0.6641. The same
    arithmetic reads a truncated 20-of-31-day extract as healthy volume. The
    doc and the alert's own annotation both said "trips per day", and no reader
    of either would have guessed "per day on which trips occurred". Two rules
    follow: **derive a denominator from something the numerator cannot move**
    (here the calendar), and **assert the MONOTONICITY as a property test** — a
    signal whose whole claim is that it sees a marginal must be monotonic in
    that marginal, and no test asserted it because every shipped month happened
    to hold all its days (F-051, raised by REV at the M7 review, fixed M8-S1).

101. **`make backup` was running `make restore-drill`, because the manifest's
    own prose named it in backticks inside an unquoted heredoc.** This is #60
    for the SECOND time — and the tell was the same shape both times: somebody
    else's output spliced into the middle of a generated artifact (there, a pod
    manifest that failed to parse on an unrelated line; here, five words of
    `make`'s `Entering directory` chatter sitting mid-sentence in `MANIFEST.txt`,
    a lifeboat artifact nobody reads until an incident). The blast radius was
    bounded by luck rather than by design: the substituted drill creates and
    drops scratch databases in the ONE Postgres and was being launched against a
    backup directory still being written; it happened to exit early. **The real
    lesson is not "escape backticks" — it is that #60 came back because the
    lesson had no test.** One now exists, repo-wide, over every heredoc in
    `scripts/*.sh` and the Makefile, skipping quoted delimiters and failing on an
    unescaped backtick in the body: a gotcha that can only be remembered will be
    forgotten by the session that was not there (F-053, M8-S1).

102. **A lookup that answers a set of questions with a SMALLER set of answers
    must say which questions it declined, or every consumer reads "declined" as
    "the answer is nothing".** Feast's `get_historical_features` returned 77 rows
    for 88 entity rows, for two entirely different reasons: one pair of rows
    shared an entity key AND an event timestamp, so the store answered them once
    (the second is not missing — it was answered, elsewhere in the frame); and
    ten rows were earlier than every source row in the view, so they were DROPPED
    rather than returned null. Both are legitimate library behaviour. The problem
    is what happens next: after the obvious `merge(answers, on="row_id",
    how="left")` those two, plus a row the store genuinely lost, are the same
    NaN. Asserting a row count is the wrong repair — it goes red on both
    legitimate causes, which is a guard firing on a correct system (#50). The
    repair is to CLASSIFY the shortfall — recover the duplicates by joining on
    the keys the store actually keyed on, accept the too-early rows as
    legitimately null and check two-sidedly that your own path is null there too,
    and make anything unaccounted-for a FAIL naming the row ids. Read the
    boundary that decides the second class (here, the earliest source timestamp)
    OFF the artifact rather than typing it. #78's family, one layer along: there
    an empty panel looked like a quiet system, here an absent row looks like an
    absent value (F-056, M8-S3).

103. **A join's duplicate-collapse is an edge case only while your timestamps
    vary; hold them constant and it becomes the majority of every answer.**
    M8-S3 met F-056 as one row in eighty-eight. M8-S4 retrieves the offline half
    of its parity table at a SINGLE instant — it has to, because a materialized
    online store keeps the latest row per key and has no history to be
    point-in-time about — and the same call then answered **34 rows for 100
    declared pairs** on one view, 37 on another, 67 and 73 on the rest, while
    `get_online_features` answered 100 of 100 on every one. Nothing was wrong:
    the two APIs disagree about the SHAPE of an answer, a lookup returning one
    row per request and a join returning one row per distinct key. But a
    comparison aligned by POSITION would have compared a store against a shuffled
    copy of itself and failed loudly, randomly and unattributably; and one
    aligned by `row_id` alone would have read two thirds of the table as nulls.
    Align on the keys the store actually keyed the answer on. The general form:
    **before comparing two APIs, ask what each one's row count MEANS** — and note
    that the property that makes the collapse rare in one story can be the exact
    thing the next story is required to remove (M8-S4).

104. **A pin file that cannot be regenerated byte-identically hides its own real
    diffs.** `feast_probe_record.py --rewrite-pins` builds the quarantine's pin
    file from `importlib.metadata`, which reports distribution names as PUBLISHED
    (`Jinja2`, `PyYAML`, `ast-serialize`), while the committed file carries the
    NORMALIZED forms `uv pip freeze` emits. Regenerating it to add two lines
    rewrote twelve for no reason. Nothing breaks — installers accept both — but
    the file's whole job is to be the thing a human reviews, and a two-line change
    arriving as a fourteen-line diff is where a third line hides. Whenever a
    generated artifact is ALSO a review surface, prove it round-trips: generate
    it twice and diff (F-057, M8-S4).

105. **A negative assertion passes for free when the system is entirely absent —
    and the two cases are the same bytes.** The transformer's accept check asserts
    that the CHAMPION'S model name 404s on the transformer's host, which is what
    makes "which boundary produced this number?" answerable at all. Its first run
    PASSED that check while failing every other one, because nginx had not yet
    loaded KServe's generated Ingress and the host was 404ing EVERYTHING. #59 says
    assert on a positive artifact; this is its negative form — **where the artifact
    IS an absence, prove first that presence was possible**. The repair is to make
    the negative check conditional on the positive one (`404 and route_live`), so
    it asserts a DIFFERENCE between two names on a live route rather than a silence
    (F-060, M8-S4 leg 3).

106. **`kubectl wait` and `rollout status` can both be satisfied while the ROUTE
    does not exist yet, on a FIRST deploy — #71/#84's family with nothing to be
    satisfied by.** F-037 was found at M6-S3 when a shadow's route 404'd; leg 3 hit
    it again on a brand-new InferenceService, where there is no predecessor at all:
    both Deployments rolled out, the ISVC's `Ready` condition went True, and the
    generated Ingress was ~12 s from being loaded. A readiness wait is only about
    the objects it names. Ask the thing the NEXT step uses — here, `GET /health` on
    the route, under the Host header the next step will send (M8-S4 leg 3).

107. **The feature build was priced COLD and paid WARM, so the boundary cost less
    than its own prediction.** M5-S4 recorded `build_features` at ~30 ms for one
    row and warned the M7 transformer would move it inside the p95. Measured, the
    p50 moved **+18 ms** — and that buys the feature build PLUS two HTTP round
    trips to another pod PLUS a second in-cluster hop. The 30 ms was a first call
    paying module import and an `lru_cache` fill; a warm pod pays neither, and the
    store path never reads those CSVs. #80's family (an analogy from a
    differently-conditioned measurement), erring this time in the safe direction —
    and the same run showed the p95 DELTA swinging +23.0 -> +5.0 ms between two
    runs eight minutes apart while p50 held to a millisecond, so quote the p50 and
    say the p95 is inside a band wider than the effect (M8-S4 leg 3).


108. **Two assumptions can be the same assumption for three milestones, and the
    day they separate nothing announces it.** The `kserve-predictors` scrape job
    keeps every pod carrying `serving.kserve.io/inferenceservice` and then
    rewrites its address to mlserver's `:8082` (pinned there by F-034). "Belongs
    to an InferenceService" and "is an mlserver" were ONE fact through the
    champion, M6-S3's shadow and M6-S4's canary — all predictors. M8-S4 added a
    **transformer** pod, which is the first isvc pod in this program that is not
    an mlserver, and it silently became a target that can never be up. The cost
    is not a wrong number: it is a **permanently-false instance of the one signal
    whose entire value is that `up == 0` means a predictor stopped reporting**
    (F-043), and a standing false alarm is how a real one becomes invisible.
    Two transferable halves. (a) When a discovery rule and a transport
    assumption are written next to each other, the rule is only as narrow as the
    NARROWER of them — say so in the selector, not in the comment; KServe already
    labels `component: predictor` vs `component: transformer`, so the
    discriminator cost nothing and was simply never asked for. (b) When a gate
    finds this, fix the CAUSE. The tempting repair was to scope the gate's
    question to the champion's own exporter, which would have been a guard edited
    to fit a defect — gotcha #50 inverted, and the habit this program exists to
    refuse (F-061, M8-S5 leg 2).

109. **A red team is only as good as the field nobody was checking, and the
    milestone's thesis tells you which field that is.** M8's four seams all
    measure `max |delta| = 0.000e+00`, and `docs/feast_online_m8.md` §2 argues at
    length that **a comparison which silently dropped nulls would print exactly
    that same zero** while being blind to the ~1% of rows carrying no geometry.
    So the plant is not a wrong measurement — it is a `both_missing` count
    rewritten from 13 to **0**, leaving `compared`, `mismatches`, the delta and
    the verdict untouched. The record still reads as a clean pass; it now
    describes a comparison that never looked, and it looks BETTER than the truth.
    The generalisation: **find the sentence in your own design document that says
    "a broken version of this would produce the same headline", and plant
    there** — and then give that field three witnesses, because one artifact
    agreeing with itself is not a measurement (M8-S5 leg 2).

110. **A generator whose template documents its own placeholders will substitute
    the documentation.** `scripts/build_demo_page.py`'s first run replaced
    `{{ZONE_OPTIONS}}` inside the template's own explanatory comment — the
    paragraph naming the tokens — and shipped a page with **795 `<option>`
    elements across two `<select>`s instead of 530**. It rendered. It scrolled
    oddly. And it was wrong in a way that *no* assertion of the form "the zone
    list matches the CSV" would have caught, because each of the three copies
    matched. This is gotcha #53/#60 in a new place — prose sitting where a parser
    reads it as code — and the cheap guard is not a smarter parser: it is an
    OCCURRENCE COUNT. `TOKEN_COUNTS` declares how many times each token may
    appear, the generator refuses a mismatch naming the token, and a unit test
    asserts the template agrees. Name a placeholder in prose without its
    delimiters, always (M9-S1).

111. **The V2 model name is in the URL path, so a new caller's endpoint is a
    function of the ISVC's name — not of the model's, and not of the champion's.**
    The demo's first route claimed `/v2/models/nyc-taxi-eta/infer`, the
    champion's name, and every quote came back **404**. The transformer answers
    to its own isvc name (`nyc-taxi-eta-transformer`) and 404s on the other —
    which is not a defect but M8-S4 leg 3's deliberate negative, the thing that
    makes "which boundary produced this number?" answerable at all. Two lessons.
    (a) The diagnosis was free ONLY because the transformer's 404 body names the
    path it does answer to; an endpoint that answered to both names, or that
    404'd silently, would have cost the session. Write the alternative into the
    error. (b) The repair turned the failure into a stronger check rather than a
    correction: the champion's name is now **deliberately unrouted** on the
    demo's origin and its 404 is asserted, so the demo cannot quietly end up
    talking to the 24-column wire. ADR-011 condition 2, third occurrence
    (M9-S1).

112. **A guard whose alarm channel is also its sensor cannot tell its own
    handwriting from the world's — and the cure it forces is worse than the
    disease.** `watchdog.sh` detected "a session parked on a fork" by watching
    AWAITING_PO.md's sha change, and `red()` ALARMS BY APPENDING TO
    AWAITING_PO.md. So every alarm manufactured a false park on the next pass.
    That feedback loop was not a cosmetic wart: because false parks existed,
    REAL parks had to be allowed to expire after a couple of passes, or one
    FAILED run would have wedged the chain shut forever. The expiry is what let
    the program-close park — correctly detected and alarmed at 06:40 — be
    HEALED at 07:00, starting an executor session into a closed, tagged
    program. Two rules. (a) **A condition a human must clear is a STATE, so
    latch it**; "no change since the last pass" is not "nobody is waiting on
    me", and any test of a latch must exercise the SECOND pass, because the
    first is where an edge detector and a latch agree. (b) When a guard has
    been made lenient to work around its own noise, **fix the noise at the
    source and the leniency becomes unnecessary** — here killing the false park
    let the FAILED-run recovery drop from four passes to two while the real
    park became permanent, i.e. both properties got STRICTER at once. The tell
    that this had been normalised: the existing test's docstring described the
    false park as the expected trace (F-066, M9 post-close).

113. **`kubectl exec deploy/X` can land on the pod you just replaced, and
    `rollout restart` + `rollout status` will tell you it is safe to try.**
    Two independent races, one consequence. `exec deploy/X` does not address
    the Deployment — it resolves the Deployment's SELECTOR and picks a matching
    pod, and a RollingUpdate with `maxSurge=100%` puts two pods behind that
    selector. Meanwhile `rollout status` asks about the Deployment's CURRENT
    status, which until the controller observes the new generation still
    describes the PREVIOUS, complete, rollout — so it affirms a restart that has
    not begun (F-036/gotcha #79 from the other side: there a trailing
    `observedGeneration` made kubectl REFUSE conditions that were true). Both
    fire hardest on the check you added because the operation is dangerous: here
    the read-back proving a MinIO root rotation had not destroyed the named
    users answered `authentication failed` — **byte-for-byte the catastrophe's
    own signature** — on a rotation that had worked. A false alarm
    indistinguishable from a real disaster is worse than no alarm, because the
    reflex it triggers is to undo the thing that was fine. Wait for
    `observedGeneration >= generation` before `rollout status`, and resolve ONE
    ready, non-terminating pod by name rather than execing a Deployment. Then
    MEASURE what is left: here the first successful read moved to **0.3 s past
    Ready**, which is how you learn the generation race was the cause and the
    retry you also added is not what fixed it (F-076, M9-S12).

114. **A negative proof is only as good as the path it runs on, and a positive
    control cannot save it if that path authenticates nothing.** The rotation's
    "the old password is refused" probe ran `psql` to `127.0.0.1` from inside
    the postgres pod. `pg_hba.conf` there is `host all all 127.0.0.1/32 trust`
    before `host all all all scram-sha-256`, so the password was never
    consulted — and the probe reported a correctly-rotated role as unrotated.
    The control ("the NEW password works over the same path") had been added
    precisely to stop a false refusal, and it could not: **under `trust` both
    arms pass, so the control agreed with the false alarm.** A control only
    discriminates if the mechanism under test is engaged; this one was built to
    catch *the database is gone*, which is a different failure from *nothing is
    being authenticated*. The fix was the address, not the assertion —
    connecting to the pod's own IP falls through to the `scram-sha-256` rule.
    Before trusting any auth check, read the auth CONFIG and confirm your
    connection matches the rule you think it does (F-077, M9-S12).

115. **A variable the launcher exported can convert a test into a test of
    something else, and the suite's verdict becomes a function of who ran it.**
    `tests/unit/test_watchdog.py` built its sandbox from `os.environ`;
    `watchdog.sh`'s heal path exports `WATCHDOG_HEAL=1`, and a session STARTED
    by that path carries the flag for its whole life. Two tests asserting the
    ordinary human-run behaviour of `next_session.sh` silently became tests of
    the heal path and went red on a repo where nothing was wrong. The tell is a
    failure that reproduces for one operator and not another, on the same
    commit. Pin the flags your subject reads to an explicit default in the
    fixture — the tests that WANT the other path already set it themselves, so
    pinning makes both intentions visible instead of leaving one to chance
    (F-079, M9-S12).

116. **A git hook that is not executable is not a hook, and git says nothing
    about it.** No error, no warning, no scan — `ls` shows the file sitting
    right where you put it and every commit sails through. Git records the mode
    of a TRACKED file (`scripts/hooks/pre-commit` is `100755` in the index, and
    a test asserts that), but the copy into `.git/hooks` is where the bit gets
    lost: a `cp` from a tarball, a `curl`, a filesystem that drops it, or
    M8-S4 leg 2's `COPY`, whose 0644 surfaced as containerd's
    `exec: permission denied` and read like a missing binary. So the installer
    sets the bit and then READS IT BACK off the installed file, and its
    `--check` distinguishes the three ways a hook stops being one — absent,
    stale, and present-but-not-executable — because they are three different
    repairs and only one of them is visible to `ls` (M9-S13).

117. **Before shipping a repo-wide refusal, ask who already does the forbidden
    thing on purpose — the answer is usually the drills.** The M9-S13
    pre-commit hook refuses a staged credential; `make security-scan-redteam`
    STAGES one deliberately, so it can watch the audit catch a secret on a ref
    HEAD does not reach. It had passed 16/16 for a day and died at `git commit`
    under `set -e` the hour the hook was installed — a working guard presenting
    as a broken red team. Neither party was wrong; the interaction was new. The
    fix is one flag with a comment saying the flag is there BECAUSE the guard is
    right, and the blast radius is a two-second measurement (`grep -rn "git
    commit"` over `scripts/`, `automation/` and the Makefile found exactly one
    caller). This is F-053/F-063's question asked from the other side: those ask
    *what does my command do to state that already exists*, this asks *what does
    my new refusal do to commands that already exist* (F-080, M9-S13).

118. **A CLI's subcommands are a version fact, not a remembered one.** The M9
    charter specified `gitleaks protect --staged`; `protect` was removed in the
    8.19 line and the pinned 8.30.1 binary offers `dir`, `git` and `stdin` —
    with `git --staged` as the pre-commit form. One `--help` on the PINNED
    binary answered it before a line was written. Same family as #70 (ask the
    server what endpoint it serves) and the Flyte-2 trigger check: when a
    charter, a blog post or a memory names a command, run it against the version
    you actually pin before designing around it (M9-S13).
