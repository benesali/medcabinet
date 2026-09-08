"""dlt pipeline for SÚKL DLP bronze load.

Parallel to the asyncpg COPY loader (caveat-bronze-load-sukl). Produces the same
bronze.sukl_* tables so dbt Silver models need no changes.

Column names are preserved as-is (KOD_SUKL, NAZEV_INN, ...) via the "direct"
naming convention in .dlt/config.toml.

dlt adds two system columns to every table:
  _dlt_id      — row-level hash (dedup / idempotency)
  _dlt_load_id — load identifier (maps to _dlt_loads table)

These are extra columns; dbt Silver models ignore them.

Usage:
    uv run caveat-bronze-dlt-sukl --batch-id 2026-09-02
    uv run caveat-bronze-dlt-sukl --batch-id 2026-09-02 --raw-root data/raw
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import dlt

logger = logging.getLogger(__name__)

SUKL_ENCODING = "cp1250"
SUKL_DELIMITER = ";"

# Maps source CSV filename → dlt resource / table name in bronze schema
_FILE_TO_TABLE: dict[str, str] = {
    "dlp_lecivepripravky.csv": "sukl_drugs",
    "dlp_lecivelatky.csv": "sukl_ingredients",
    "dlp_slozeni.csv": "sukl_contains",
    "dlp_atc.csv": "sukl_atc",
    "dlp_synonyma.csv": "sukl_synonyms",
    "dlp_zruseneregistrace.csv": "sukl_cancelled",
}


def _rows(path: Path, batch_id: str) -> Iterator[dict[str, Any]]:
    """Yield rows from a SÚKL CSV with provenance metadata appended."""
    load_ts = datetime.now(tz=UTC).isoformat()
    with path.open(encoding=SUKL_ENCODING, newline="") as fh:
        for row in csv.DictReader(fh, delimiter=SUKL_DELIMITER):
            row["_source_file"] = path.name
            row["_load_ts"] = load_ts
            row["_batch_id"] = batch_id
            yield row


@dlt.source(name="sukl")
def sukl_source(snapshot_dir: Path, batch_id: str) -> list[dlt.sources.DltResource]:
    """dlt source for all six SÚKL DLP CSV files in one raw snapshot directory."""
    resources: list[dlt.sources.DltResource] = []
    for csv_file, table_name in _FILE_TO_TABLE.items():
        csv_path = snapshot_dir / csv_file
        if not csv_path.exists():
            logger.warning("File not found, skipping: %s", csv_path)
            continue
        resources.append(
            dlt.resource(
                _rows(csv_path, batch_id),
                name=table_name,
                write_disposition="append",
            )
        )
    return resources


def _normalize_dsn(dsn: str) -> str:
    """Convert SQLAlchemy-style DSN to plain psycopg2 DSN for dlt.

    CAVEAT_DB_DSN uses postgresql+asyncpg:// (SQLAlchemy driver notation).
    dlt postgres destination expects postgresql://.
    """
    return dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")


def run(dsn: str, raw_root: Path, batch_id: str) -> None:
    """Load one SÚKL DLP raw snapshot into bronze.sukl_* via dlt."""
    snapshot_dir = raw_root / "sukl" / "dlp" / batch_id
    if not snapshot_dir.exists():
        raise FileNotFoundError(f"Raw snapshot not found: {snapshot_dir}")

    pipeline = dlt.pipeline(
        pipeline_name="caveat_bronze_sukl",
        destination=dlt.destinations.postgres(credentials=_normalize_dsn(dsn)),
        dataset_name="bronze",
    )

    load_info = pipeline.run(sukl_source(snapshot_dir=snapshot_dir, batch_id=batch_id))

    if load_info.has_failed_jobs:
        raise RuntimeError(f"dlt load had failed jobs: {load_info}")

    for package in load_info.load_packages:
        for job in package.jobs.get("completed_jobs", []):
            logger.info("  %s loaded", job.job_file_info.table_name)

    logger.info("dlt load complete (batch: %s)", batch_id)


def main() -> None:
    """CLI entrypoint: load SÚKL DLP raw snapshot into bronze.sukl_* via dlt."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description="Load SÚKL raw snapshot into bronze.sukl_* via dlt.")
    parser.add_argument("--batch-id", required=True, help="Snapshot date, e.g. 2026-09-02")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_RAW_ROOT", "data/raw")),
        metavar="PATH",
    )
    args = parser.parse_args()

    dsn = os.environ.get("CAVEAT_DB_DSN") or os.environ.get("DATABASE_URL", "")
    if not dsn:
        logger.error("Set CAVEAT_DB_DSN or DATABASE_URL")
        sys.exit(1)

    try:
        run(dsn=dsn, raw_root=args.raw_root, batch_id=args.batch_id)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
