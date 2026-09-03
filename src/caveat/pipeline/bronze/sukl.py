"""Bronze-layer ingestor for the SÚKL DLP (Databáze léčivých přípravků) dataset.

The DLP ZIP is published monthly at opendata.sukl.cz and contains a set of CSV files
covering drug registrations, active ingredients, compositions, ATC codes, and synonyms.

Datasets handled:
  dlp          — current full extract (30 CSVs, monthly)
  dlp_history  — historical monthly archives back to 2021 (one ZIP per month)

Usage:
    uv run caveat-ingest-sukl                        # latest DLP, download today
    uv run caveat-ingest-sukl --url <url>            # explicit URL
    uv run caveat-ingest-sukl --force                # re-download even if snapshot exists
    uv run caveat-ingest-sukl-history --year 2026    # download all months for a year
    uv run caveat-ingest-sukl-history --year 2026 --month 8  # single month
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from caveat.pipeline.bronze.manifest import BronzeManifest, sha256_file, write_manifest

logger = logging.getLogger(__name__)

# Catalog page listing the latest DLP ZIP download link.
# Verify at: https://opendata.sukl.cz/?q=katalog%2Fdatabaze-lecivych-pripravku-dlp
CATALOG_PAGE_URL = "https://opendata.sukl.cz/?q=katalog%2Fdatabaze-lecivych-pripravku-dlp"

# History catalog page (monthly archives back to 2021).
# Verify at: https://opendata.sukl.cz/?q=katalog/historie-databaze-lecivych-pripravku-dlp
HISTORY_CATALOG_PAGE_URL = (
    "https://opendata.sukl.cz/?q=katalog/historie-databaze-lecivych-pripravku-dlp"
)

# Pattern that matches the current DLP ZIP URL embedded in the catalog page HTML.
_DLP_URL_RE = re.compile(
    r"https://opendata\.sukl\.cz/soubory/SOD\d{8}/DLP\d{8}\.zip"
)

# History ZIPs follow a different SOD folder pattern (year-only, not year+month+day).
# URL template: .../soubory/SOD{YYYY}/DLP{YYYYMM}.zip
# Example verified from history catalog: SOD2026/DLP202608.zip
_HISTORY_URL_TEMPLATE = (
    "https://opendata.sukl.cz/soubory/SOD{year}/DLP{year}{month:02d}.zip"
)

# Pattern to discover all available history ZIPs from the catalog page.
_HISTORY_URL_RE = re.compile(
    r"https://opendata\.sukl\.cz/soubory/SOD\d{4}/DLP\d{6}\.zip"
)

SOURCE_NAME = "SÚKL"
SOURCE_NAME_HISTORY = "SÚKL-history"
# All DLP CSV files use Windows-1250 encoding (verified 2026-09-02).
CSV_ENCODING = "cp1250"


def discover_latest_url(catalog_url: str = CATALOG_PAGE_URL) -> str:
    """Fetch the SÚKL catalog page and extract the latest DLP ZIP download URL."""
    logger.info("Discovering latest DLP URL from %s", catalog_url)
    response = httpx.get(catalog_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    match = _DLP_URL_RE.search(response.text)
    if not match:
        raise RuntimeError(
            f"Could not find a DLP ZIP URL on the catalog page {catalog_url}. "
            "The page structure may have changed — check it manually."
        )
    url = match.group(0)
    logger.info("Latest DLP URL: %s", url)
    return url


def _version_from_url(url: str) -> str:
    """Extract the date-version string from a DLP ZIP URL (e.g. '20260827')."""
    m = re.search(r"DLP(\d{8})\.zip", url)
    return m.group(1) if m else "unknown"


def snapshot_dir(bronze_root: Path, snapshot_date: date) -> Path:
    """Return the path of the date-stamped SÚKL DLP snapshot directory."""
    return bronze_root / "sukl" / "dlp" / snapshot_date.isoformat()


def download(
    bronze_root: Path,
    snapshot_date: date | None = None,
    force: bool = False,
    url: str | None = None,
) -> Path:
    """Download the SÚKL DLP CSV bundle to the bronze layer and return the snapshot directory.

    Discovers the latest ZIP URL automatically unless *url* is provided.
    Idempotent: skips the download when a manifest already exists for *snapshot_date*,
    unless *force* is ``True``.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    dest = snapshot_dir(bronze_root, snapshot_date)
    manifest_path = dest / "manifest.json"

    if manifest_path.exists() and not force:
        logger.info("Snapshot already exists: %s — skipping (use --force to re-download)", dest)
        return dest

    if url is None:
        url = discover_latest_url()

    dest.mkdir(parents=True, exist_ok=True)

    zip_path = dest / "_dlp_download.zip"
    logger.info("Downloading %s → %s", url, zip_path)
    _stream_download(url, zip_path)

    checksum = sha256_file(zip_path)
    extracted = _extract_csvs(zip_path, dest)
    zip_path.unlink()

    manifest = BronzeManifest(
        source=SOURCE_NAME,
        source_version=_version_from_url(url),
        downloaded_at=datetime.now(tz=timezone.utc).isoformat(),
        url=url,
        filename=Path(url).name,  # e.g. "DLP20260827.zip"
        size_bytes=sum(f.stat().st_size for f in extracted),
        checksum=checksum,  # checksum of the ZIP before extraction
        encoding=CSV_ENCODING,
        files=sorted(f.name for f in extracted),
    )
    write_manifest(dest, manifest)
    logger.info("Manifest written — %d CSV files, checksum %s", len(extracted), checksum)
    return dest


def _stream_download(url: str, dest: Path) -> None:
    """Stream *url* to *dest*, printing a progress indicator."""
    with httpx.Client(follow_redirects=True, timeout=180) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            received = 0
            with dest.open("wb") as fh:
                for chunk in response.iter_bytes(chunk_size=65536):
                    fh.write(chunk)
                    received += len(chunk)
                    if total:
                        print(f"\r  {received / total * 100:.1f}%  ({received:,} / {total:,} B)", end="", flush=True)
            print()


def _extract_csvs(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extract all CSV members from *zip_path* into *dest_dir* and return their paths."""
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.lower().endswith(".csv"):
                zf.extract(member, dest_dir)
                out = dest_dir / Path(member).name  # flatten any subdirectory in ZIP
                if (dest_dir / member) != out:
                    (dest_dir / member).rename(out)
                extracted.append(out)
                logger.info("Extracted: %s", out.name)
    if not extracted:
        raise RuntimeError(f"No CSV files found in ZIP: {zip_path}")
    return extracted


def main() -> None:
    """CLI entrypoint: parse arguments and run the SÚKL DLP bronze download."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(
        description="Download the SÚKL DLP drug-registry CSV bundle to the bronze layer."
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="Snapshot date label (default: today)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if today's snapshot already exists",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Explicit DLP ZIP URL (default: auto-discovered from the catalog page)",
    )
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_BRONZE_ROOT", "data/bronze")),
        metavar="PATH",
        help="Bronze root directory (default: data/bronze or $CAVEAT_BRONZE_ROOT)",
    )
    args = parser.parse_args()

    try:
        dest = download(
            bronze_root=args.bronze_root,
            snapshot_date=args.date,
            force=args.force,
            url=args.url,
        )
        print(f"Bronze snapshot ready: {dest}")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


def discover_history_urls(catalog_url: str = HISTORY_CATALOG_PAGE_URL) -> list[str]:
    """Fetch the history catalog page and return all available history ZIP URLs."""
    logger.info("Discovering history URLs from %s", catalog_url)
    response = httpx.get(catalog_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    urls = sorted(set(_HISTORY_URL_RE.findall(response.text)))
    logger.info("Found %d history ZIPs on catalog page", len(urls))
    return urls


def history_url(year: int, month: int) -> str:
    """Return the expected history ZIP URL for a given year and month."""
    return _HISTORY_URL_TEMPLATE.format(year=year, month=month)


def history_snapshot_dir(bronze_root: Path, year: int, month: int) -> Path:
    """Return the path of the date-stamped SÚKL DLP history snapshot directory."""
    return bronze_root / "sukl" / "dlp_history" / f"{year}-{month:02d}"


def download_history_month(
    bronze_root: Path,
    year: int,
    month: int,
    force: bool = False,
    url: str | None = None,
) -> Path:
    """Download one month of SÚKL DLP history to the bronze layer.

    Idempotent: skips download when a manifest already exists, unless *force* is True.
    """
    dest = history_snapshot_dir(bronze_root, year, month)
    manifest_path = dest / "manifest.json"

    if manifest_path.exists() and not force:
        logger.info("History snapshot already exists: %s — skipping", dest)
        return dest

    if url is None:
        url = history_url(year, month)

    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / f"_dlp_history_{year}{month:02d}.zip"

    logger.info("Downloading history %d-%02d from %s", year, month, url)
    _stream_download(url, zip_path)

    checksum = sha256_file(zip_path)
    extracted = _extract_csvs(zip_path, dest)
    zip_path.unlink()

    manifest = BronzeManifest(
        source=SOURCE_NAME_HISTORY,
        source_version=f"{year}{month:02d}",
        downloaded_at=datetime.now(tz=timezone.utc).isoformat(),
        url=url,
        filename=Path(url).name,
        size_bytes=sum(f.stat().st_size for f in extracted),
        checksum=checksum,
        encoding=CSV_ENCODING,
        files=sorted(f.name for f in extracted),
    )
    write_manifest(dest, manifest)
    logger.info("History manifest written — %d CSV files", len(extracted))
    return dest


def main_history() -> None:
    """CLI entrypoint: download SÚKL DLP history snapshots to the bronze layer.

    Downloads one month, a full year, or lists available URLs from the catalog page.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(
        description=(
            "Download SÚKL DLP monthly history snapshots to the bronze layer. "
            "History is available back to ~2021 at opendata.sukl.cz."
        )
    )
    parser.add_argument("--year", type=int, required=True, help="Year to download (e.g. 2025)")
    parser.add_argument(
        "--month",
        type=int,
        default=None,
        choices=range(1, 13),
        metavar="1-12",
        help="Month to download (default: all months for the year)",
    )
    parser.add_argument("--force", action="store_true", help="Re-download existing snapshots")
    parser.add_argument(
        "--list-available",
        action="store_true",
        help="List available history ZIP URLs from the catalog page and exit",
    )
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_BRONZE_ROOT", "data/bronze")),
        metavar="PATH",
        help="Bronze root directory (default: data/bronze or $CAVEAT_BRONZE_ROOT)",
    )
    args = parser.parse_args()

    if args.list_available:
        for url in discover_history_urls():
            print(url)
        return

    months = [args.month] if args.month else list(range(1, 13))
    current = date.today()

    for month in months:
        # Skip future months
        if date(args.year, month, 1) > current.replace(day=1):
            logger.info("Skipping future month %d-%02d", args.year, month)
            continue
        try:
            dest = download_history_month(
                bronze_root=args.bronze_root,
                year=args.year,
                month=month,
                force=args.force,
            )
            print(f"History snapshot ready: {dest}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Not found (404): %d-%02d — may not be published yet", args.year, month)
            else:
                logger.error("HTTP %d for %d-%02d: %s", exc.response.status_code, args.year, month, exc)
        except Exception as exc:
            logger.error("Failed %d-%02d: %s", args.year, month, exc)


if __name__ == "__main__":
    main()
