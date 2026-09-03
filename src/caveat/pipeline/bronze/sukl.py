"""Bronze schema for SÚKL DLP — 1:1 with raw CSV files.

Six tables covering the key DLP datasets. All source columns are TEXT;
type casting happens in Silver. Column names match CSV headers verbatim.
"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text

from caveat.pipeline.bronze import metadata

# dlp_lecivepripravky.csv — drug registrations (69 759 rows in 2026-08)
sukl_drugs = Table(
    "sukl_drugs",
    metadata,
    Column("KOD_SUKL", Text),  # SÚKL registration code
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
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),  # ISO 8601 UTC
    Column("_batch_id", Text, nullable=False),  # snapshot date, e.g. '2026-09-02'
)

# dlp_lecivelatky.csv — active ingredients (3 378 rows in 2026-08)
sukl_ingredients = Table(
    "sukl_ingredients",
    metadata,
    Column("KOD_LATKY", Text),  # ingredient code
    Column("NAZEV", Text),  # Czech name
    Column("NAZEV_EN", Text),  # English name (typically WHO rINN form)
    Column("NAZEV_INN", Text),  # Latin pharmacopoeial form (e.g. PARACETAMOLUM)
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),
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
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),
)

# dlp_atc.csv — ATC classification codes
sukl_atc = Table(
    "sukl_atc",
    metadata,
    Column("ATC", Text),  # ATC code (e.g. M01AE01)
    Column("NAZEV", Text),  # Czech description
    Column("NAZEV_EN", Text),  # English description
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),
)

# dlp_synonyma.csv — ingredient aliases (273 065 rows in 2026-08)
sukl_synonyms = Table(
    "sukl_synonyms",
    metadata,
    Column("KOD_LATKY", Text),  # ingredient code
    Column("SQ", Text),  # sequence number
    Column("ZDROJ", Text),  # source/language tag (CZ, INN, INNE, USA, ...)
    Column("NAZEV", Text),  # alias name
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),
)

# dlp_zruseneregistrace.csv — cancelled registrations
sukl_cancelled = Table(
    "sukl_cancelled",
    metadata,
    Column("KOD_SUKL", Text),
    Column("NAZEV", Text),
    Column("DATUM_ZRUSENI", Text),  # cancellation date (DD.MM.YYYY in source)
    Column("_source_file", Text, nullable=False),
    Column("_load_ts", Text, nullable=False),
    Column("_batch_id", Text, nullable=False),
)

# Maps CSV filename → (table, primary_key_column_name)
SUKL_TABLES: dict[str, tuple[Table, str]] = {
    "dlp_lecivepripravky.csv": (sukl_drugs, "KOD_SUKL"),
    "dlp_lecivelatky.csv": (sukl_ingredients, "KOD_LATKY"),
    "dlp_slozeni.csv": (sukl_contains, "KOD_SUKL"),
    "dlp_atc.csv": (sukl_atc, "ATC"),
    "dlp_synonyma.csv": (sukl_synonyms, "KOD_LATKY"),
    "dlp_zruseneregistrace.csv": (sukl_cancelled, "KOD_SUKL"),
}
