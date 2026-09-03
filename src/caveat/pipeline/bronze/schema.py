"""SQLAlchemy Core table definitions for the Bronze PostgreSQL schema.

Bronze tables are 1:1 with raw CSV files — all source columns preserved as TEXT,
no casting, no business rules. Three technical metadata columns are appended to
every table:

    _source_file  TEXT  — filename of the CSV this row came from
    _load_ts      TIMESTAMPTZ — when this batch was loaded (set by loader)
    _batch_id     TEXT  — identifies the raw snapshot, e.g. '2026-09-02' for SÚKL
                           or '2.0' for DDInter

Column names match the CSV headers verbatim (SÚKL uses UPPER_SNAKE_CASE).
All values are TEXT — type casting happens in Silver.
"""

from __future__ import annotations

from sqlalchemy import Column, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP

metadata = MetaData(schema="bronze")

# Convenience shorthand — every table gets these three columns at the end.
_META_COLS = [
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", TIMESTAMP(timezone=True), nullable=False),
    Column("_batch_id", Text, nullable=False),
]


def _meta() -> list[Column]:  # type: ignore[type-arg]
    """Return fresh copies of the metadata columns (SQLAlchemy columns are stateful)."""
    return [
        Column("_source_file", Text, nullable=False),
        Column("_load_ts", TIMESTAMP(timezone=True), nullable=False),
        Column("_batch_id", Text, nullable=False),
    ]


# ---------------------------------------------------------------------------
# SÚKL DLP tables
# ---------------------------------------------------------------------------

# dlp_lecivepripravky.csv — drug registrations (69 759 rows in 2026-08)
sukl_drugs = Table(
    "sukl_drugs",
    metadata,
    Column("KOD_SUKL", Text),  # SÚKL registration code (primary key in source)
    Column("NAZEV", Text),  # product name
    Column("FORMA", Text),  # pharmaceutical form
    Column("SILA", Text),  # strength
    Column("BALENI", Text),  # packaging description
    Column("CESTA", Text),  # route of administration
    Column("ATC_WHO", Text),  # ATC classification code
    Column("REG", Text),  # registration status (R=registered)
    Column("RC", Text),  # registration number
    Column("VYDEJ", Text),  # dispensing class (R/L/C/F/O/P/V)
    Column("DRZITEL", Text),  # marketing authorisation holder
    Column("VYROBCE", Text),  # manufacturer
    Column("LL", Text),  # semicolon-separated KOD_LATKY codes
    *_meta(),
)

# dlp_lecivelatky.csv — active ingredients (3 378 rows in 2026-08)
sukl_ingredients = Table(
    "sukl_ingredients",
    metadata,
    Column("KOD_LATKY", Text),  # ingredient code (primary key in source)
    Column("NAZEV", Text),  # Czech name
    Column("NAZEV_EN", Text),  # English name (typically WHO rINN form)
    Column("NAZEV_INN", Text),  # Latin pharmacopoeial form (e.g. PARACETAMOLUM)
    *_meta(),
)

# dlp_slozeni.csv — composition: drug ↔ ingredient with dose (807 466 rows in 2026-08)
# All S values kept — excipient filtering (S='X') is Silver's job.
sukl_contains = Table(
    "sukl_contains",
    metadata,
    Column("KOD_SUKL", Text),  # drug code
    Column("KOD_LATKY", Text),  # ingredient code
    Column("SQ", Text),  # sequence number within drug
    Column("S", Text),  # ingredient type: L=active, X=excipient, O=other active
    Column("AMNT", Text),  # dose amount (numeric string or 'PL' = qty sufficient)
    Column("UN", Text),  # dose unit (mg, ml, ...)
    *_meta(),
)

# dlp_atc.csv — ATC classification codes
sukl_atc = Table(
    "sukl_atc",
    metadata,
    Column("ATC", Text),  # ATC code (e.g. M01AE01)
    Column("NAZEV", Text),  # Czech description
    Column("NAZEV_EN", Text),  # English description
    *_meta(),
)

# dlp_synonyma.csv — ingredient aliases (273 065 rows in 2026-08)
sukl_synonyms = Table(
    "sukl_synonyms",
    metadata,
    Column("KOD_LATKY", Text),  # ingredient code
    Column("SQ", Text),  # sequence number
    Column("ZDROJ", Text),  # source/language tag (CZ, INN, INNE, USA, ...)
    Column("NAZEV", Text),  # alias name
    *_meta(),
)

# dlp_zruseneregistrace.csv — cancelled registrations
sukl_cancelled = Table(
    "sukl_cancelled",
    metadata,
    Column("KOD_SUKL", Text),
    Column("NAZEV", Text),
    Column("DATUM_ZRUSENI", Text),  # cancellation date (DD.MM.YYYY in source)
    *_meta(),
)

# ---------------------------------------------------------------------------
# DDInter
# ---------------------------------------------------------------------------

# DDInter v2.0 interaction pairs
# Column names from actual DDInter CSV header (verified against downloaded file).
# [SOURCED: online, primary | DDInter v2.0 | ddinter.scbdd.com | accessed 2026-09-03]
ddinter_interactions = Table(
    "ddinter_interactions",
    metadata,
    Column("Drug1", Text),  # first drug name (mixed INN / brand / USAN)
    Column("Drug2", Text),  # second drug name
    Column("Level", Text),  # severity: Major / Moderate / Minor / Unknown
    Column("Interaction", Text),  # free-text mechanism / description
    *_meta(),
)

# ---------------------------------------------------------------------------
# WHO INN
# ---------------------------------------------------------------------------

# WHO INN recommended list (CSV variant — PDF variant stored as-is in raw layer)
# Column names from the WHO INN Excel/CSV export format.
# [SOURCED: online, primary | WHO INN programme | who.int | accessed 2026-09-03]
who_inn = Table(
    "who_inn",
    metadata,
    Column("INN", Text),  # recommended INN
    Column("Status", Text),  # recommended / proposed / modified
    Column("List_number", Text),  # INN list number (e.g. '133')
    Column("CAS", Text),  # CAS registry number
    *_meta(),
)

# ---------------------------------------------------------------------------
# Registry: source name → (table, batch_id_field, csv_filename)
# ---------------------------------------------------------------------------

SUKL_TABLES: dict[str, tuple[Table, str]] = {
    "dlp_lecivepripravky.csv": (sukl_drugs, "KOD_SUKL"),
    "dlp_lecivelatky.csv": (sukl_ingredients, "KOD_LATKY"),
    "dlp_slozeni.csv": (sukl_contains, "KOD_SUKL"),
    "dlp_atc.csv": (sukl_atc, "ATC"),
    "dlp_synonyma.csv": (sukl_synonyms, "KOD_LATKY"),
    "dlp_zruseneregistrace.csv": (sukl_cancelled, "KOD_SUKL"),
}
