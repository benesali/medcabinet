"""Bronze-layer loader: reads raw CSVs and bulk-inserts into bronze.* PostgreSQL tables.

Each load is append-only. The _batch_id column identifies the snapshot so old
batches can be queried or pruned without affecting Silver/Gold rebuilds.

Technical validation is applied here (column presence, type parsability).
Business rules (INN normalization, S='L' filtering, VYDEJ mapping) belong in Silver.

Usage:
    uv run caveat-bronze-load-sukl --batch-id 2026-09-02 --raw-root data/raw
    uv run caveat-bronze-load-ddinter --batch-id 2.0 --raw-root data/raw
"""

from __future__ import annotations

# TODO (Phase 1): implement bulk COPY loader using asyncpg COPY protocol.
# Each function should:
#   1. Resolve raw_root / <source> / <batch_id> / <filename>.csv
#   2. Open with correct encoding (cp1250 for SÚKL, utf-8 for DDInter/WHO INN)
#   3. COPY INTO bronze.<table> using asyncpg connection.copy_to_table()
#   4. Set _source_file, _load_ts, _batch_id on each row
#   5. Log row count on completion
#
# Schema is in schema.sql — apply with:
#   psql $DATABASE_URL -f src/caveat/pipeline/bronze/schema.sql
