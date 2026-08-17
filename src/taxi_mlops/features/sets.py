"""The feature-set registry reader — `configs/features.yaml` is the ONE home.

F-013's features half (M3-S3, Design Review AI-6). Before this module there were
two places a feature set could be defined: `configs/train.yaml: features` held
the real lists, and `configs/features.yaml` held a bootstrap-era stub whose "v1"
named `trip_distance` — a column the exclusion registry refuses by law. The stub
was stale AND leaky, which is the worse half of the port-family twins lesson: a
future session reading it would have re-admitted the exact column F-007 exists
to keep out, "per the config".

So there is now one definition and one reader. `configs/train.yaml: features`
carries a `version` and a pointer; this module resolves the pair into the dict
the rest of the training path already expects:

    {version, temporal, passthrough, derived, categorical}

Resolution is by GROUP, not by column. A set is `base` plus zero or more named
groups, and the groups are the unit the Design Review's keep-threshold judges
(DR-02) — so a set whose column list was hand-assembled from the winners of a
group experiment could not be traced back to any measurement. Spelling out
`base` exactly once is the same twins argument at a smaller scale.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ..data.config import load_yaml

DEFAULT_REGISTRY = "configs/features.yaml"

#: Keys `configs/train.yaml: features` may carry. Anything else — in particular
#: a `temporal`/`passthrough`/`derived`/`categorical` list — means a second home
#: has grown back, and a test fails on exactly this tuple.
TRAIN_CONFIG_KEYS = ("version", "registry")


class FeatureSetError(ValueError):
    """The registry cannot answer the question that was asked of it.

    A ValueError rather than a KeyError so the message survives: a typo'd set
    name that resolved to an empty list would train a model on nothing and
    report it as a feature set.
    """


@lru_cache(maxsize=8)
def load_registry(path: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Read and structurally validate `configs/features.yaml`."""
    registry = load_yaml(path)
    for section in ("base", "groups", "sets"):
        if section not in registry:
            raise FeatureSetError(f"{path} has no `{section}:` section")
    groups = registry["groups"]
    for name, spec in groups.items():
        unknown = set(spec.get("categorical", [])) - set(spec.get("derived", []))
        if unknown:
            raise FeatureSetError(
                f"{path}: group {name!r} declares {sorted(unknown)} categorical, but the "
                "group does not derive them. A categorical that is not a feature is a "
                "declaration nothing reads."
            )
    for name, spec in registry["sets"].items():
        missing = [g for g in spec.get("groups", []) if g not in groups]
        if missing:
            raise FeatureSetError(
                f"{path}: set {name!r} names group(s) {missing}, which are not defined "
                f"under `groups:`. Known groups: {sorted(groups)}."
            )
    return registry


def set_names(path: str = DEFAULT_REGISTRY) -> list[str]:
    return list(load_registry(path)["sets"])


def group_names(path: str = DEFAULT_REGISTRY) -> list[str]:
    """The groups in the order `configs/features.yaml` declares them.

    The order is load-bearing: DR-03 fixed it BEFORE M3-S3 fitted anything, and
    `docs/ablation_m3.md` reports the experiments in it.
    """
    return list(load_registry(path)["groups"])


def resolve_set(version: str, path: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """One set name -> the full column definition. The only expansion in the program."""
    registry = load_registry(path)
    sets = registry["sets"]
    if version not in sets:
        raise FeatureSetError(
            f"feature set {version!r} is not defined in {path}. Known sets: "
            f"{sorted(sets)}. A set is added there, never assembled at a call site."
        )
    spec = sets[version] or {}
    base = registry["base"]
    resolved: dict[str, Any] = {
        "version": version,
        "temporal": list(base["temporal"]),
        "passthrough": list(base["passthrough"]),
        "derived": list(base.get("derived", [])),
        "categorical": list(base["categorical"]),
        "groups": list(spec.get("groups", [])),
    }
    for group_name in resolved["groups"]:
        group = registry["groups"][group_name]
        resolved["derived"].extend(group.get("derived", []))
        resolved["categorical"].extend(group.get("categorical", []))

    names = resolved["temporal"] + resolved["passthrough"] + resolved["derived"]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise FeatureSetError(
            f"feature set {version!r} resolves to duplicated column(s) {duplicates} — two "
            "groups deriving the same name means one of them is not the change it claims."
        )
    return resolved


def resolve(features_cfg: dict[str, Any]) -> dict[str, Any]:
    """`configs/train.yaml: features` -> the resolved set. Called by the ONE loader.

    Refuses a `features:` block that carries column lists of its own: that is the
    second home growing back, and it would grow back stale (which is exactly how
    the stub this replaced came to name an excluded column).
    """
    stray = sorted(set(features_cfg) - set(TRAIN_CONFIG_KEYS))
    if stray:
        raise FeatureSetError(
            f"configs/train.yaml: features carries {stray}, but feature sets have ONE "
            f"home ({features_cfg.get('registry', DEFAULT_REGISTRY)}) since M3-S3 "
            "(F-013). This block may hold only "
            f"{list(TRAIN_CONFIG_KEYS)} — a set is defined in the registry and named here."
        )
    return resolve_set(features_cfg["version"], features_cfg.get("registry", DEFAULT_REGISTRY))
