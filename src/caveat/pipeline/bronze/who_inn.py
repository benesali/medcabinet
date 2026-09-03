"""Bronze-layer ingestor for WHO INN (International Nonproprietary Names) data.

The WHO INN programme publishes cumulative lists of recommended INNs — the canonical
names for pharmaceutical active substances. Every ActiveIngredient.inn in CAVEAT must
trace to a WHO rINN.

Source: https://www.who.int/teams/health-product-and-policy-standards/inn
[SOURCED: online, primary | WHO INN programme | who.int | accessed 2026-09-03]

WHO does not publish a machine-readable download catalog, so the URL must be obtained
from the website and passed via --url. Accepts CSV, ZIP containing CSVs, or PDF
(stored as-is; Silver extracts INN names from it in Phase 2).

Usage:
    uv run caveat-ingest-who-inn --url <url>
    uv run caveat-ingest-who-inn --url <url> --version 133 --force
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from caveat.pipeline.bronze.base import SourceName, extract_csvs, stream_download
from caveat.pipeline.bronze.manifest import BronzeManifest, sha256_file, write_manifest

logger = logging.getLogger(__name__)

_CSV_SUFFIXES = {".csv"}
_ZIP_SUFFIXES = {".zip"}


def snapshot_dir(bronze_root: Path, version: str) -> Path:
    """Return the bronze snapshot directory for a given WHO INN list version."""
    return bronze_root / "who_inn" / version


def download(
    bronze_root: Path,
    url: str,
    version: str = "latest",
    force: bool = False,
) -> Path:
    """Download WHO INN data to the bronze layer.

    Accepts a CSV, ZIP, or PDF URL. Idempotent: skips when manifest already
    exists unless *force* is True. PDFs are stored as-is; Silver extracts names
    from them later.
    """
    dest = snapshot_dir(bronze_root, version)
    manifest_path = dest / "manifest.json"

    if manifest_path.exists() and not force:
        logger.info("WHO INN snapshot already exists: %s — skipping", dest)
        return dest

    dest.mkdir(parents=True, exist_ok=True)

    suffix = Path(url.split("?")[0]).suffix.lower()
    filename = Path(url.split("?")[0]).name or f"who_inn_{version}{suffix or '.bin'}"
    dest_file = dest / filename

    logger.info("Downloading WHO INN v%s → %s", version, dest_file)
    stream_download(url, dest_file)
    checksum = sha256_file(dest_file)

    row_count: int | None = None
    files: list[str]

    if suffix in _ZIP_SUFFIXES:
        extracted = extract_csvs(dest_file, dest)
        dest_file.unlink()
        files = sorted(f.name for f in extracted)
        size = sum(f.stat().st_size for f in extracted)
    elif suffix in _CSV_SUFFIXES:
        size = dest_file.stat().st_size
        files = [filename]
        with dest_file.open(encoding="utf-8") as fh:
            row_count = sum(1 for _ in fh) - 1
    else:
        # PDF or other binary — store as-is; Silver will parse.
        size = dest_file.stat().st_size
        files = [filename]

    manifest = BronzeManifest(
        source=SourceName.WHO_INN,
        source_version=version,
        downloaded_at=datetime.now(tz=UTC).isoformat(),
        url=url,
        filename=filename,
        size_bytes=size,
        checksum=checksum,
        encoding="utf-8" if suffix in _CSV_SUFFIXES else "binary",
        files=files,
        row_count=row_count,
    )
    write_manifest(dest, manifest)
    logger.info("WHO INN manifest written — version %s, %s", version, dest)
    return dest


def main() -> None:
    """CLI entrypoint: download WHO INN list to the bronze layer."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="Download WHO INN list to the bronze layer.")
    parser.add_argument(
        "--url",
        required=True,
        help="Direct download URL for the WHO INN CSV, ZIP, or PDF (from who.int)",
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="INN list version tag used as the snapshot directory name (default: latest)",
    )
    parser.add_argument("--force", action="store_true", help="Re-download if snapshot exists")
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_BRONZE_ROOT", "data/bronze")),
        metavar="PATH",
    )
    args = parser.parse_args()

    try:
        dest = download(
            bronze_root=args.bronze_root,
            url=args.url,
            version=args.version,
            force=args.force,
        )
        print(f"Bronze snapshot ready: {dest}")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
