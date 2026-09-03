"""Bronze schema for WHO INN recommended list — CSV variant.

Column names from the WHO INN Excel/CSV export.
[SOURCED: online, primary | WHO INN programme | who.int | accessed 2026-09-03]

Note: when the raw layer holds a PDF (not CSV), this table is not populated.
The PDF is stored as-is in the raw layer and processed separately in Silver.
"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text

from caveat.pipeline.bronze import metadata

# WHO INN recommended international nonproprietary names
who_inn = Table(
    "who_inn",
    metadata,
    Column("INN", Text),  # recommended INN (normalized, lowercase in Silver)
    Column("Status", Text),  # recommended / proposed / modified
    Column("List_number", Text),  # INN list number (e.g. '133')
    Column("CAS", Text),  # CAS registry number
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),  # version string, e.g. 'latest' or '133'
)
