"""Bronze-layer ingestor for DDInter drug-drug interaction data.

DDInter v2.0 provides ~237,000 drug-drug interaction pairs with severity,
mechanism, and management advice. License: CC BY-NC-SA 4.0 — acceptable for
personal/portfolio use, not for commercial products.

Source: https://ddinter.scbdd.com  [SOURCED: online, primary | DDInter v2.0 | ddinter.scbdd.com]

DDInter does not publish a machine-readable catalog page, so the download URL must
be obtained from the website and passed via --url. Accepts both direct CSV and ZIP.

Usage:
    uv run caveat-ingest-ddinter --url <url>
    uv run caveat-ingest-ddinter --url <url> --version 2.0 --force
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from caveat.pipeline.raw.base import SourceName, extract_csvs, stream_download
from caveat.pipeline.raw.manifest import RawManifest, sha256_file, write_manifest

logger = logging.getLogger(__name__)


def snapshot_dir(bronze_root: Path, version: str) -> Path:
    """Return the bronze snapshot directory for a given DDInter version."""
    return bronze_root / "ddinter" / version


def download(
    raw_root: Path,
    url: str,
    version: str = "2.0",
    force: bool = False,
) -> Path:
    """Download DDInter interaction data to the raw layer.

    Accepts a direct CSV URL or a ZIP containing CSVs. Idempotent: skips when
    manifest already exists unless *force* is True.
    """
    dest = snapshot_dir(raw_root, version)
    manifest_path = dest / "manifest.json"

    if manifest_path.exists() and not force:
        logger.info("DDInter snapshot already exists: %s — skipping", dest)
        return dest

    dest.mkdir(parents=True, exist_ok=True)

    filename = Path(url).name or f"ddinter_v{version}.csv"
    dest_file = dest / filename

    logger.info("Downloading DDInter v%s → %s", version, dest_file)
    stream_download(url, dest_file)
    checksum = sha256_file(dest_file)

    if url.lower().endswith(".zip"):
        extracted = extract_csvs(dest_file, dest)
        dest_file.unlink()
        files = sorted(f.name for f in extracted)
        size = sum(f.stat().st_size for f in extracted)
        row_count = None
    else:
        size = dest_file.stat().st_size
        files = [filename]
        # Row count: total lines minus header.
        with dest_file.open(encoding="utf-8") as fh:
            row_count = sum(1 for _ in fh) - 1

    manifest = RawManifest(
        source=SourceName.DDINTER,
        source_version=version,
        downloaded_at=datetime.now(tz=UTC).isoformat(),
        url=url,
        filename=filename,
        size_bytes=size,
        checksum=checksum,
        encoding="utf-8",
        files=files,
        row_count=row_count,
    )
    write_manifest(dest, manifest)
    logger.info("DDInter manifest written — %s rows, %s", row_count, dest)
    return dest


def main() -> None:
    """CLI entrypoint: download DDInter interaction data to the raw layer."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="Download DDInter drug-drug interaction CSV to the raw layer.")
    parser.add_argument(
        "--url",
        required=True,
        help="Direct download URL for the DDInter CSV or ZIP (from ddinter.scbdd.com)",
    )
    parser.add_argument(
        "--version",
        default="2.0",
        help="DDInter version tag used as the snapshot directory name (default: 2.0)",
    )
    parser.add_argument("--force", action="store_true", help="Re-download if snapshot exists")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_RAW_ROOT", "data/raw")),
        metavar="PATH",
    )
    args = parser.parse_args()

    try:
        dest = download(
            raw_root=args.raw_root,
            url=args.url,
            version=args.version,
            force=args.force,
        )
        print(f"Raw snapshot ready: {dest}")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
