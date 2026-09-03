"""Bronze-layer loader: reads raw CSVs and bulk-inserts into bronze.* PostgreSQL tables.

Each load is append-only with _batch_id identifying the snapshot. Old batches remain
queryable for audit and rollback. Technical validation (column presence) is applied
here; business rules belong in Silver.

Uses asyncpg COPY for performance — 807K composition rows load in seconds.

Usage:
    uv run caveat-bronze-load-sukl --batch-id 2026-09-02
    uv run caveat-bronze-load-sukl --batch-id 2026-09-02 --raw-root data/raw
    uv run caveat-bronze-load-ddinter --batch-id 2.0
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

from caveat.pipeline.bronze import metadata
from caveat.pipeline.bronze.ddinter import ddinter_interactions
from caveat.pipeline.bronze.sukl import SUKL_TABLES

logger = logging.getLogger(__name__)

CSV_ENCODING_SUKL = "cp1250"
CSV_ENCODING_DEFAULT = "utf-8"
CSV_DELIMITER_SUKL = ";"
CSV_DELIMITER_DEFAULT = ","


async def ensure_schema(conn: asyncpg.Connection) -> None:  # type: ignore[type-arg]
    """Create the bronze schema and all tables if they do not exist."""
    await conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    for table in metadata.tables.values():
        cols = []
        for col in table.columns:
            pg_type = "TIMESTAMPTZ" if "TIMESTAMP" in str(col.type) else "TEXT"
            nullable = "" if col.nullable else " NOT NULL"
            cols.append(f'    "{col.name}" {pg_type}{nullable}')
        ddl = f'CREATE TABLE IF NOT EXISTS bronze."{table.name}" (\n' + ",\n".join(cols) + "\n)"
        await conn.execute(ddl)
        logger.debug("Ensured table: bronze.%s", table.name)


async def _copy_csv(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    table_name: str,
    csv_path: Path,
    encoding: str,
    delimiter: str,
    batch_id: str,
    expected_columns: list[str],
) -> int:
    """COPY one CSV file into a bronze table. Returns row count loaded."""
    load_ts = datetime.now(tz=UTC).isoformat()

    # Read CSV, validate header, append metadata columns, stream via COPY.
    with csv_path.open(encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV: {csv_path}")

        actual = set(reader.fieldnames)
        missing = set(expected_columns) - actual
        if missing:
            raise ValueError(f"{csv_path.name}: missing expected columns {sorted(missing)}")

        all_cols = list(reader.fieldnames) + ["_source_file", "_load_ts", "_batch_id"]

        buf = io.StringIO()
        writer = csv.writer(buf)
        row_count = 0
        for row in reader:
            writer.writerow(
                [row.get(c, "") for c in reader.fieldnames]  # type: ignore[arg-type]
                + [csv_path.name, load_ts, batch_id]
            )
            row_count += 1

        buf.seek(0)
        await conn.copy_to_table(  # type: ignore[attr-defined]
            table_name,
            schema_name="bronze",
            source=buf,
            format="csv",
            columns=all_cols,
        )

    logger.info("Loaded %d rows → bronze.%s (batch: %s)", row_count, table_name, batch_id)
    return row_count


async def load_sukl(
    dsn: str,
    raw_root: Path,
    batch_id: str,
) -> dict[str, int]:
    """Load all key SÚKL DLP CSVs from a raw snapshot into bronze.sukl_* tables.

    Returns a dict of {table_name: row_count}.
    """
    snapshot_dir = raw_root / "sukl" / "dlp" / batch_id
    if not snapshot_dir.exists():
        raise FileNotFoundError(f"Raw snapshot not found: {snapshot_dir}")

    conn = await asyncpg.connect(dsn)
    try:
        await ensure_schema(conn)
        counts: dict[str, int] = {}
        for csv_filename, (table, _pk_col) in SUKL_TABLES.items():
            csv_path = snapshot_dir / csv_filename
            if not csv_path.exists():
                logger.warning("File not found, skipping: %s", csv_path)
                continue
            expected = [c.name for c in table.columns if not c.name.startswith("_")]
            counts[table.name] = await _copy_csv(
                conn=conn,
                table_name=table.name,
                csv_path=csv_path,
                encoding=CSV_ENCODING_SUKL,
                delimiter=CSV_DELIMITER_SUKL,
                batch_id=batch_id,
                expected_columns=expected,
            )
        return counts
    finally:
        await conn.close()


async def load_ddinter(
    dsn: str,
    raw_root: Path,
    batch_id: str,
    csv_filename: str = "ddinter_downloads_code_all.csv",
) -> int:
    """Load a DDInter CSV from a raw snapshot into bronze.ddinter_interactions."""
    snapshot_dir = raw_root / "ddinter" / batch_id
    csv_path = snapshot_dir / csv_filename
    if not csv_path.exists():
        # Try any CSV in the snapshot directory.
        candidates = list(snapshot_dir.glob("*.csv"))
        if not candidates:
            raise FileNotFoundError(f"No CSV found in: {snapshot_dir}")
        csv_path = candidates[0]
        logger.info("Using CSV: %s", csv_path.name)

    conn = await asyncpg.connect(dsn)
    try:
        await ensure_schema(conn)
        expected = [c.name for c in ddinter_interactions.columns if not c.name.startswith("_")]
        return await _copy_csv(
            conn=conn,
            table_name=ddinter_interactions.name,
            csv_path=csv_path,
            encoding=CSV_ENCODING_DEFAULT,
            delimiter=CSV_DELIMITER_DEFAULT,
            batch_id=batch_id,
            expected_columns=expected,
        )
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# CLI entrypoints
# ---------------------------------------------------------------------------


def _dsn_from_env() -> str:
    dsn = os.environ.get("CAVEAT_DB_DSN") or os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Set CAVEAT_DB_DSN or DATABASE_URL environment variable")
    return dsn


def main_sukl() -> None:
    """CLI: load SÚKL DLP raw snapshot into bronze.sukl_* tables."""
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description="Load SÚKL raw snapshot into bronze.sukl_* tables.")
    parser.add_argument("--batch-id", required=True, help="Snapshot date, e.g. 2026-09-02")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_RAW_ROOT", "data/raw")),
        metavar="PATH",
    )
    args = parser.parse_args()

    try:
        counts = asyncio.run(load_sukl(dsn=_dsn_from_env(), raw_root=args.raw_root, batch_id=args.batch_id))
        for table, n in counts.items():
            print(f"  bronze.{table}: {n:,} rows")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


def main_ddinter() -> None:
    """CLI: load DDInter raw snapshot into bronze.ddinter_interactions."""
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description="Load DDInter raw snapshot into bronze.ddinter_interactions.")
    parser.add_argument("--batch-id", required=True, help="DDInter version, e.g. 2.0")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(os.environ.get("CAVEAT_RAW_ROOT", "data/raw")),
        metavar="PATH",
    )
    args = parser.parse_args()

    try:
        n = asyncio.run(load_ddinter(dsn=_dsn_from_env(), raw_root=args.raw_root, batch_id=args.batch_id))
        print(f"  bronze.ddinter_interactions: {n:,} rows")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
