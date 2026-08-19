# The predictor image (M5-S2) — MLServer's MLflow runtime, plus the one package
# it does not ship, built once and delivered by `kind load` (D-001's mechanism).
#
# WHY A DERIVED IMAGE AT ALL, measured rather than assumed. The kickoff names the
# mlserver/MLflow runtime and KServe's own kustomization pins it to
# `docker.io/seldonio/mlserver:1.7.1-mlflow`. That image cannot load OUR champion:
#
#     $ docker run --rm -v /tmp/champion:/mnt/models:ro --entrypoint python \
#         seldonio/mlserver:1.7.1-mlflow -c "import mlflow; mlflow.pyfunc.load_model('/mnt/models')"
#     FAILED: ModuleNotFoundError: No module named 'lightgbm'
#
# The stock image carries the sklearn/xgboost/mlflow runtimes and no LightGBM, so
# `mlflow.lightgbm`'s loader_module has nothing to import. Adding the ONE package
# — at the version the champion's own MLmodel names — makes the same command
# print `LOADED ... _LGBModelWrapper`. That probe was run before this file
# existed, which is why this file is four lines instead of an afternoon.
#
# WHAT THIS IMAGE DOES NOT FIX, stated because it is real and because M5-S3 is
# about to measure it. The base runs **Python 3.10.12, pandas 2.2.3, numpy
# 2.2.6**; the champion was fitted under **3.12.14 / 3.0.5 / 2.5.2**, and MLflow
# prints that mismatch as a warning at every load. It is not fixable by pinning:
# mlserver 1.7.1 is built on a Python 3.10 conda base and `mlflow` (the full
# package, which its runtime needs) pins `pandas<3` against our 3.0.5 — the exact
# conflict that made this program install `mlflow-skinny` in the first place.
#
# The reason it does not threaten parity — and the reason it is a limit to
# measure rather than a defect to fight — is that none of those three libraries
# is on the numeric path:
#   * the FEATURE MATRIX is built by `taxi_mlops.features` on the CLIENT side
#     (M5-S2's `serving/client.py`), so pandas/numpy build it exactly once;
#   * the wire carries FP64, so nothing is re-derived from a dtype;
#   * `lightgbm` is 4.7.0 on BOTH sides — the pin table's version, and the one
#     `MLmodel` names — and `Booster.predict` on a float64 matrix is the same
#     deterministic C++ either way.
# M5-S3's 1e-6 parity test is what turns that argument into a number. If it comes
# back wide, this paragraph is the first suspect and the honest answer is a
# predictor built on the project's own image, not a looser bar.
#
# The base is pinned by TAG AND DIGEST — the Metabase precedent (M1-S5), for the
# same reason: a tag is a name, a digest is a fact.
FROM docker.io/seldonio/mlserver:1.7.1-mlflow@sha256:492c8bbac687b148ad81a57278368f0aaaa2b3f72b09302419258d36058fe000

# `--no-cache-dir` because a pip cache in a layer is bytes that ship and are
# never read. The version is EXACT and is the one in CLAUDE.md's pin table and in
# the champion's MLmodel (`lgb_version: 4.7.0`): a range here would let a rebuild
# serve a different booster implementation than the one the gate measured.
RUN pip install --no-cache-dir "lightgbm==4.7.0"

# Prove it at BUILD time, so a broken image cannot reach a node. `import lightgbm`
# alone would pass without an OpenMP runtime present on some bases (gotcha #37 is
# this program's scar); constructing a Booster is what actually touches libgomp.
RUN python -c "import lightgbm; lightgbm.Booster; print('lightgbm', lightgbm.__version__)"
