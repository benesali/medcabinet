from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RawManifest:
    """Metadata written alongside every raw snapshot."""

    source: str  # "SÚKL" / "DDInter"
    source_version: str  # date or release tag from the source
    downloaded_at: str  # ISO 8601, UTC
    url: str  # URL the data was fetched from
    filename: str  # source archive name (e.g. "DLP20260827.zip")
    size_bytes: int  # total size of extracted files in bytes
    checksum: str  # "sha256:<hex>" of the downloaded archive
    encoding: str | None = None  # character encoding of extracted files (e.g. "cp1250")
    files: list[str] | None = None  # names of all extracted files, alphabetically sorted
    row_count: int | None = None  # total rows across key tables; filled in by Bronze


MANIFEST_FILENAME = "manifest.json"


def write_manifest(directory: Path, manifest: RawManifest) -> None:
    """Serialise *manifest* to ``manifest.json`` inside *directory*."""
    (directory / MANIFEST_FILENAME).write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_manifest(directory: Path) -> RawManifest:
    """Read and deserialise ``manifest.json`` from *directory*."""
    data = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    return RawManifest(**data)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path* in ``'sha256:<hex>'`` format."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
