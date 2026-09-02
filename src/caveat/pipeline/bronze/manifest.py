from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BronzeManifest:
    """Metadata written alongside every raw bronze snapshot."""

    source: str           # "SÚKL" / "DDInter"
    source_version: str   # date or release tag from the source
    downloaded_at: str    # ISO 8601, UTC
    url: str
    filename: str         # canonical filename within the snapshot directory
    size_bytes: int
    checksum: str         # "sha256:<hex>"
    row_count: int | None = None  # filled in by the Silver parse step


MANIFEST_FILENAME = "manifest.json"


def write_manifest(directory: Path, manifest: BronzeManifest) -> None:
    """Serialise *manifest* to ``manifest.json`` inside *directory*."""
    (directory / MANIFEST_FILENAME).write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_manifest(directory: Path) -> BronzeManifest:
    """Read and deserialise ``manifest.json`` from *directory*."""
    data = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    return BronzeManifest(**data)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path* in ``'sha256:<hex>'`` format."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
