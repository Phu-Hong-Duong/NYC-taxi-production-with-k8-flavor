"""Raw acquisition: skip-if-present, retried, sha256-manifested.

The manifest is the pin. It carries no timestamps on purpose: re-running ingest
must produce a byte-identical `data/raw_manifest.json`, so a diff on that file
always means the DATA moved, never that the clock did.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import DataConfig
from .errors import ChecksumDriftError

MANIFEST_NOTE = (
    "sha256 pin of the raw TLC files. No timestamps by design: a diff here means "
    "the bytes changed (gotcha #6 -- TLC backfills months in place), not that the "
    "file was fetched again. Regenerate with `make ingest`."
)


def sha256_file(path: Path, chunk_bytes: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("files", {})


def save_manifest(path: Path, files: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_note": MANIFEST_NOTE, "files": dict(sorted(files.items()))}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _fetch(url: str, dest: Path, attempts: int, backoff: int, timeout: int) -> None:
    """Download to a temp sibling then rename — a half-written file never looks done."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response, tmp.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            tmp.replace(dest)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            tmp.unlink(missing_ok=True)
            print(f"  attempt {attempt}/{attempts} failed for {url}: {exc}")
            if attempt < attempts:
                time.sleep(backoff * attempt)
    raise OSError(f"download failed after {attempts} attempts: {url}") from last


def ensure_month(cfg: DataConfig, month: str, manifest: dict[str, dict[str, Any]]) -> str:
    """Make the raw file for `month` present and pinned. Returns 'present' or 'downloaded'.

    Raises ChecksumDriftError if the bytes disagree with an existing manifest pin.
    """
    path = cfg.raw_path(month)
    url = cfg.url(month)
    dl = cfg.source["download"]

    if path.exists():
        action = "present"
    else:
        _fetch(url, path, dl["attempts"], dl["backoff_seconds"], dl["timeout_seconds"])
        action = "downloaded"

    checksum = sha256_file(path)
    size = path.stat().st_size
    pinned = manifest.get(month)
    if pinned and pinned["sha256"] != checksum:
        raise ChecksumDriftError(
            f"{path.name}: sha256 on disk {checksum} != manifest pin {pinned['sha256']}. "
            "TLC backfilled this month or the local file was edited. This is an EVENT: "
            "review the change and update data/raw_manifest.json deliberately -- ingest "
            "will not silently adopt new bytes."
        )
    manifest[month] = {"file": path.name, "url": url, "bytes": size, "sha256": checksum}
    return action
