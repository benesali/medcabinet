-- Bronze schema: 1:1 with raw CSV files, all original columns preserved.
-- Adds technical metadata (_source_file, _load_ts, _batch_id) but NO business
-- transformations — that belongs in Silver.
--
-- Naming: bronze.<source>_<table>
-- Encoding: all SÚKL text columns are stored as TEXT (cp1250 decoded at load time).

CREATE SCHEMA IF NOT EXISTS bronze;

-- ---------------------------------------------------------------------------
-- SÚKL DLP
-- ---------------------------------------------------------------------------

-- dlp_lecivepripravky.csv — drug registrations
CREATE TABLE IF NOT EXISTS bronze.sukl_drugs (
    -- Original columns (verbatim names from SÚKL CSV header)
    "KOD_SUKL"      TEXT,
    "NAZEV"         TEXT,
    "FORMA"         TEXT,
    "SILA"          TEXT,
    "BALENI"        TEXT,
    "CESTA"         TEXT,
    "ATC_WHO"       TEXT,
    "REG"           TEXT,
    "RC"            TEXT,
    "VYDEJ"         TEXT,
    "DRZITEL"       TEXT,
    "VYROBCE"       TEXT,
    "LL"            TEXT,   -- semicolon-separated list of KOD_LATKY codes
    -- Technical metadata
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL   -- snapshot date, e.g. '2026-09-02'
);

-- dlp_lecivelatky.csv — active ingredients
CREATE TABLE IF NOT EXISTS bronze.sukl_ingredients (
    "KOD_LATKY"     TEXT,
    "NAZEV"         TEXT,
    "NAZEV_EN"      TEXT,
    "NAZEV_INN"     TEXT,
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL
);

-- dlp_slozeni.csv — composition (drug ↔ ingredient with dose); all S values kept
CREATE TABLE IF NOT EXISTS bronze.sukl_contains (
    "KOD_SUKL"      TEXT,
    "KOD_LATKY"     TEXT,
    "SQ"            TEXT,
    "S"             TEXT,   -- L=active, X=excipient, O=other active
    "AMNT"          TEXT,   -- dose amount (numeric string or 'PL')
    "UN"            TEXT,   -- dose unit
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL
);

-- dlp_atc.csv — ATC classification codes
CREATE TABLE IF NOT EXISTS bronze.sukl_atc (
    "ATC"           TEXT,
    "NAZEV"         TEXT,
    "NAZEV_EN"      TEXT,
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL
);

-- dlp_synonyma.csv — ingredient aliases / synonyms
CREATE TABLE IF NOT EXISTS bronze.sukl_synonyms (
    "KOD_LATKY"     TEXT,
    "SQ"            TEXT,
    "ZDROJ"         TEXT,   -- source/language tag (CZ, INN, INNE, USA, ...)
    "NAZEV"         TEXT,
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL
);

-- dlp_zruseneregistrace.csv — cancelled registrations
CREATE TABLE IF NOT EXISTS bronze.sukl_cancelled (
    "KOD_SUKL"      TEXT,
    "NAZEV"         TEXT,
    "DATUM_ZRUSENI" TEXT,
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL
);

-- ---------------------------------------------------------------------------
-- DDInter
-- ---------------------------------------------------------------------------

-- DDInter v2.0 interaction pairs — column names from actual CSV header
CREATE TABLE IF NOT EXISTS bronze.ddinter_interactions (
    "Drug1"         TEXT,
    "Drug2"         TEXT,
    "Level"         TEXT,   -- severity label (Major / Moderate / Minor / Unknown)
    "Interaction"   TEXT,   -- free-text description
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL   -- DDInter version, e.g. '2.0'
);

-- ---------------------------------------------------------------------------
-- WHO INN
-- ---------------------------------------------------------------------------

-- WHO INN recommended list — column names vary by file format/edition;
-- this matches the typical CSV export (INN list spreadsheet).
CREATE TABLE IF NOT EXISTS bronze.who_inn (
    "INN"           TEXT,
    "Status"        TEXT,   -- 'recommended' / 'proposed' / 'modified'
    "List_number"   TEXT,   -- INN list number (e.g. '133')
    "CAS"           TEXT,   -- CAS registry number
    _source_file    TEXT        NOT NULL,
    _load_ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    _batch_id       TEXT        NOT NULL   -- INN list version, e.g. '133'
);

-- ---------------------------------------------------------------------------
-- Indexes for common join/filter patterns
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_sukl_drugs_batch     ON bronze.sukl_drugs    (_batch_id);
CREATE INDEX IF NOT EXISTS idx_sukl_contains_batch  ON bronze.sukl_contains (_batch_id);
CREATE INDEX IF NOT EXISTS idx_ddinter_batch        ON bronze.ddinter_interactions (_batch_id);
CREATE INDEX IF NOT EXISTS idx_who_inn_batch        ON bronze.who_inn        (_batch_id);
