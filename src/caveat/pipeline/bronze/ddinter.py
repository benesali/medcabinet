"""Bronze schema for DDInter — 1:1 with raw CSV.

Column names verified against DDInter v2.0 download.
[SOURCED: online, primary | DDInter v2.0 | ddinter.scbdd.com | accessed 2026-09-03]
"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text

from caveat.pipeline.bronze import metadata

# DDInter v2.0 interaction pairs — all severity levels
ddinter_interactions = Table(
    "ddinter_interactions",
    metadata,
    Column("Drug1", Text),  # first drug name (mixed INN / brand / USAN)
    Column("Drug2", Text),  # second drug name
    Column("Level", Text),  # severity: Major / Moderate / Minor / Unknown
    Column("Interaction", Text),  # free-text mechanism / description
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),  # DDInter version, e.g. '2.0'
)
