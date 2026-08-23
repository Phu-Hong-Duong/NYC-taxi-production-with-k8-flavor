# M8-S4 leg 2 — THE QUARANTINE, CONTAINERISED. The pandas-2 half of the wall.
#
# WHY THIS IMAGE EXISTS, AND WHY IT IS NOT A WEAKENING OF ADR-012.
# ---------------------------------------------------------------
# ADR-012 recorded that "there is no Feast image and building one would move the
# wall into the cluster" — and that sentence was about the MATERIALIZER, which
# writes the store from the host inside `.venv-feast`. It stays true: nothing
# here materializes.
#
# What this image is for is the opposite direction. M8-S4 leg 2 puts a
# transformer in front of the champion, and the transformer runs OUR image —
# pandas 3.0.5, the project graph, `src/taxi_mlops` — and therefore **may not
# import the Feast SDK** (M8 law 4; feast 0.66.0 pins `pandas<3`). The kickoff
# names three shapes in order and this is (i): Feast's own feature server as its
# OWN quarantined pod, reached over HTTP.
#
# That is the shape that keeps the wall a WALL rather than a compromise. The two
# worlds never share an interpreter, a process or a dependency graph — they share
# a JSON document over a Service. `src/taxi_mlops` gains no dependency at all,
# which is why `uv.lock` is byte-identical at this story's exit exactly as it was
# at every other M8 story's (law 4's checkable invariant).
#
# It was PROBED before it was built (`make feast-serve-probe`, ~30 s against a
# ~5 minute build + load): `feast serve` answered `/get-online-features` for zone
# 132 with JFK's real centroid and for zone 264 with `null`. The M4-S4
# `DRILL_STAGE=ingest` idiom — the defects a cheap probe finds are almost never
# about the expensive thing it stands in front of.
#
# WHAT IT CONTAINS, AND WHAT IT DELIBERATELY DOES NOT.
# ---------------------------------------------------
#  * The 64 EXACT pins from `infra/feast/requirements-feast.txt`, installed with
#    `--no-deps` — the same file, the same flag and the same argument as
#    `scripts/feast_quarantine.sh`: a resolver consulted at build time can
#    legally answer differently from the one that was reviewed, and an image is
#    the worst place to discover that. One pin file, two consumers, no twin.
#  * The feature repo AS GIT DEFINES IT (`definitions.py` + `feature_store.yaml`)
#    and the published offline parquet (1.3 MB — the sources `feast apply` stats
#    when it re-stamps DataSource meta, F-055's mechanism).
#  * **NO registry.** `data/registry.db` is generated and gitignored, and baking a
#    generated artifact into an image would make the image a second home for a
#    thing `definitions.py` is the source of truth for (F-013's family, and
#    F-048's (b) refused for the same reason). The entrypoint runs `feast apply`
#    against the definitions it carries, so the pod's registry is DERIVED from
#    git every start.
#  * **NO credentials and NO store address.** `${FEAST_REDIS_CONNECTION}` is
#    expanded from the environment at run time and has no default, so an unset
#    variable fails loudly naming itself rather than connecting to something
#    wrong (ADR-012's rule, F-048's rule).
#
# The base is the SAME digest-pinned interpreter the task image uses
# (`docker/Dockerfile.pipeline`) — one libc family across node and workload, and
# a version bump cannot arrive silently on either side.
FROM python:3.12.14-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

# The non-root user is created BEFORE anything is installed. Doing it afterwards
# and fixing ownership with `chown -R` duplicates every file it touches — gotcha
# #57 measured that at 1.7 GB and 139 s on the task image.
RUN useradd --create-home --uid 10001 feast
USER feast
ENV PATH=/home/feast/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DO_NOT_TRACK=1 \
    FEAST_USAGE=False

COPY --chown=feast:feast infra/feast/requirements-feast.txt /tmp/requirements-feast.txt
RUN pip install --user --no-deps -r /tmp/requirements-feast.txt

# THE LAYOUT MIRRORS THE HOST'S DEPTH, AND THAT IS NOT COSMETIC.
# `definitions.py` resolves its own sources with
# `Path(__file__).resolve().parents[3] / "data" / "feast"` — four levels up from
# `<root>/infra/feast/feature_repo/definitions.py`. Flattening it into /repo
# would make `parents[3]` walk off the top of the filesystem and raise, and
# "fixing" that by editing the file would give the program a SECOND definition of
# where the offline sources live, differing between the host and the pod. So the
# container reproduces the shape instead: /app is the repo root, and one
# definitions.py serves both filesystems unchanged.
COPY --chown=feast:feast infra/feast/feature_repo/definitions.py /app/infra/feast/feature_repo/definitions.py
COPY --chown=feast:feast infra/feast/feature_repo/feature_store.yaml /app/infra/feast/feature_repo/feature_store.yaml
COPY --chown=feast:feast data/feast /app/data/feast
COPY --chown=feast:feast docker/feast-server-entrypoint.sh /home/feast/.local/bin/feast-server

WORKDIR /app/infra/feast/feature_repo

EXPOSE 6566
ENTRYPOINT ["/home/feast/.local/bin/feast-server"]
