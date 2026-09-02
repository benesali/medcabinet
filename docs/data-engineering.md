# Data Engineering

Two separate data layers — keep them distinct:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Knowledge graph build | dbt (PostgreSQL staging) → Neo4j Cypher load | Builds and maintains the drug + interaction graph from open sources |
| User data | PostgreSQL (OLTP) | Inventory, expiry alerts, audit log — transactional, no medallion |

---

## Knowledge Graph — Medallion Pipeline

Raw open-source data → cleansed → INN-linked → Neo4j-ready.

**Tooling:**

| Concern | Tool | Why |
|---------|------|-----|
| Staging warehouse | PostgreSQL (same instance, separate `staging` schema) or DuckDB | Silver/Gold live as SQL tables — queryable, testable, auditable |
| Transformations | dbt (dbt-core + dbt-postgres or dbt-duckdb) | Incremental models, built-in schema/data tests, documentation, lineage DAG, snapshot strategy |
| Neo4j load | Python script consuming Gold tables | dbt is SQL-only — the Cypher MERGE step is a separate Python job |
| Orchestration | Prefect 3.x | Chosen over Makefile (too plain) and Airflow (too heavy). Provides scheduling, run history, retries, local UI. |
| Bronze storage | Filesystem with date-stamped directories (or S3/MinIO if deployed) | Immutable raw snapshots, cheap, trivially versionable |

### Bronze — Raw Ingestion (Immutable, Historized)

Store everything exactly as received. **Never overwrite — append with version stamp.**

```
bronze/
  sukl/
    2026-09-02/  ← date of download
      dlp_lecivepripravky.csv   ← 69 759 drug registrations
      dlp_lecivelatky.csv       ← 3 378 active ingredients (NAZEV_INN in Latin form)
      dlp_slozeni.csv           ← 807 466 composition rows (drug↔ingredient with dose)
      dlp_atc.csv               ← ATC classification
      dlp_synonyma.csv          ← 273 065 ingredient aliases
      dlp_zruseneregistrace.csv ← cancelled registrations
      ... (30 CSV files total)
      manifest.json  ← {source, source_version, checksum, encoding: "cp1250", files: [...]}
  ddinter/
    2026-09-01/
      interactions.csv
      manifest.json  ← {source: "DDInter", version: "2.0", checksum, row_count: 237000}
```

> **Encoding:** All SÚKL DLP CSVs use Windows-1250 (`cp1250`) with semicolon delimiter. Verified 2026-09-02. The `encoding` field in `BronzeManifest` records this for every snapshot. Silver models must open with `encoding='cp1250'`.

**Why historize Bronze:**
- **Rollback:** if a new source version introduces bad data (e.g., DDInter reclassifies severity en masse), rebuild the graph from the previous Bronze snapshot
- **Audit:** regulators (or your mentor) can ask "what data did the system use on date X?" and you can answer
- **Diff:** compare two Bronze versions to detect what changed before promoting to Silver
- **Reproducibility:** any Gold state can be reproduced from its Bronze inputs + the dbt transformation code

**dbt snapshot** (for slowly changing dimensions): use `dbt snapshot` with `check` strategy on key source tables to automatically track when a drug registration changes, an interaction severity shifts, or a source entry disappears.

| Source | Format | Key fields |
|--------|--------|-----------|
| SÚKL DLP ZIP | 30 CSV files, cp1250, `;` delimiter | `dlp_lecivepripravky`: KOD_SUKL, NAZEV, ATC_WHO, REG, LL (ingredient codes). `dlp_lecivelatky`: KOD_LATKY, NAZEV_INN (Latin), NAZEV_EN, NAZEV. `dlp_slozeni`: KOD_SUKL, KOD_LATKY, AMNT, UN, S (L=active / X=excipient). `dlp_synonyma`: KOD_LATKY, NAZEV, ZDROJ |
| DDInter CSV | CSV rows | `drug1`, `drug2`, severity text, interaction type, mechanism, management advice |
| ChEMBL | REST API → JSON | INN, SMILES, molecular targets, bioactivities |
| RxNorm | REST API → JSON | CUI, drug names (multi-language), synonyms, ingredient relationships |

### Silver — Cleanse and Normalize (dbt models)

One normalized record per entity. Deduplication happens here. Each transformation is a dbt model with schema tests.

**SÚKL → Drug + ActiveIngredient candidates** (`stg_sukl__drugs`, `stg_sukl__ingredients`)

Source tables: `dlp_lecivepripravky` (drugs), `dlp_lecivelatky` (ingredients), `dlp_slozeni` (composition with dose), `dlp_synonyma` (aliases).

1. **INN source:** `dlp_lecivelatky.NAZEV_INN` — this is a **Latin pharmacopoeial form** (e.g. `PARACETAMOLUM`, `BISACODYLUM`), not the normalized WHO rINN. `[FACT — verified 2026-09-02 from actual DLP data]`
2. **Normalize INN:** lowercase + strip Latin suffix → WHO rINN form (`paracetamolum` → `paracetamol`, `ibuprofeni lysini` → `ibuprofen lysine`). Apply the USAN seed file for known EN divergences (`acetaminophen` → `paracetamol`). Fallback: ATC level 5 → INN for any ingredient where NAZEV_INN normalization is ambiguous.
3. **Composition:** join `dlp_slozeni` on `KOD_SUKL` + `KOD_LATKY`. **Filter `S = 'L'` (active ingredients only** — `S = 'X'` are excipients and must be excluded from CONTAINS edges).
4. **Dose:** `AMNT` + `UN` from `dlp_slozeni` → `CONTAINS.dose` + `CONTAINS.dose_unit`. Rows where `AMNT = 'PL'` (*dle povahy* — quantity sufficient) are excipients that slipped through; excluded by the `S = 'L'` filter.
5. **Normalize ATC code:** validate format `[A-Z]\d{2}[A-Z]{2}\d{2}`, strip whitespace. Source: `dlp_lecivepripravky.ATC_WHO`.
6. **Deduplicate:** multiple brand names with the same normalized INN → one `ActiveIngredient` record, many `Drug` records linked via CONTAINS.
7. **Aliases:** `dlp_synonyma.NAZEV` grouped by `KOD_LATKY`; `ZDROJ` field is the language/source tag.
8. **Withdrawn drugs:** `dlp_lecivepripravky.REG != 'R'` and `dlp_zruseneregistrace` → mark `Drug.status = 'withdrawn'`. Never delete.
9. **Assign `substance_type`:** `drug` for all SÚKL registrations; `supplement` / `food_component` from curated seed file.

**DDInter → Interaction candidates** (`stg_ddinter__interactions`)

1. Map `drug1`, `drug2` names to INN — DDInter uses mixed English brand + INN naming:
   - Direct INN match against Silver ActiveIngredient list
   - Fallback: RxNorm CUI lookup by drug name → INN (RxNorm is strong for English drug names, weak for CZ/SK)
   - Unresolved pairs → flagged for manual review, excluded from graph
2. Normalize severity vocabulary: DDInter free-text severity → `critical | major | moderate | minor`
3. Detect direction: if DDInter marks the pair as bidirectional → `bidirectional: true`; otherwise infer from interaction type (`CONTRAINDICATED`, `ADDITIVE` are always symmetric)
4. Deduplicate: same INN pair appearing as (A,B) and (B,A) in DDInter → one Interaction record
5. Flag `never_miss`: apply the critical pairs defined in [testing.md](testing.md)

**dbt tests on Silver models:**

| Test | dbt implementation |
|------|-------------------|
| INN not null | `not_null` test on `inn` column |
| ATC format valid | Custom data test: regex check |
| No self-interactions | Custom data test: `drug1_inn != drug2_inn` |
| Severity in vocabulary | `accepted_values` test: `{critical, major, moderate, minor}` |
| INN uniqueness | `unique` test on `ActiveIngredient.inn` |
| Referential integrity | `relationships` test: every interaction INN exists in ingredients |

**interaction_coverage classification** (feeds deterministic abstention):

| Value | Criterion |
|-------|-----------|
| `well_studied` | ≥ 3 independent source confirmations, severity = critical or major |
| `partial` | 1–2 source confirmations, or mechanism known but severity uncertain |
| `sparse` | INN in graph but no interactions from any source — data gap, not confirmed safe |

### Gold — Graph-Ready (dbt models)

Validated records, ready for Cypher `MERGE` into Neo4j. Gold models are the final dbt layer — consumed by the Python Neo4j loader.

- `gold_drugs` — name, registration_number, dosage_form, atc_code, aliases list
- `gold_ingredients` — inn (normalized), substance_type, interaction_coverage, aliases
- `gold_drug_ingredients` — drug→ingredient mapping with **dose_per_unit** and **dose_unit** (how much of each active ingredient per tablet/ml)
- `gold_interactions` — type, severity, mechanism, evidence_strength, recommended_action, bidirectional, never_miss, subject_inn, object_inn
- `gold_atc_codes` — code, level (1–5), description
- `gold_sources` — name, version, date (one per source per build)

Every Gold interaction record carries `source_name`, `source_version`, `source_date`. Every build produces a `gold_graph_snapshot` record.

---

## INN Matching — The Core Challenge

SÚKL (Czech brand names) and DDInter (English mixed names) speak different languages. Two separate resolution strategies, because the available pivots differ.

### SÚKL → INN (Czech/Slovak drugs)

```
1. activeSubstance field → INN (direct, preferred — works for ~85% of registrations)
2. ATC level 5 → INN (ATC 5th level IS the chemical substance)
3. Last resort: manual mapping from curated seed file
```

**RxNorm is NOT the primary pivot for CZ/SK drugs.** RxNorm is US-centric. Czech brand names like "Paralen", "Ibalgin", "Nurofen" may not appear in RxNorm. ATC level 5 is the reliable bridge for European drug registries.

### DDInter → INN (English drug names)

```
1. Direct INN match (many DDInter entries already use INN)
2. RxNorm name search → CUI → ingredient CUI → INN (works well for English names)
3. Unresolved → manual review queue
```

RxNorm is effective here because DDInter uses English names that RxNorm knows.

### Cross-Source Linking (Gold)

Both sides resolve to the same normalized INN → same `ActiveIngredient` node. The INN string is the join key between SÚKL entities and DDInter interactions.

**Unresolved names:** If neither path resolves a DDInter drug name to a known INN, the interaction pair is excluded and logged. A manual review queue surfaces the most-common unresolved names. Track resolution rate as a data quality metric — target >95% of DDInter pairs resolved.

**Alias generation:** Every INN accumulates aliases through this process — Slovak variants, brand names, dose-strength suffixes (`Ibalgin 400` → alias of `ibuprofen`). The alias list on `ActiveIngredient` is what the entity resolution pipeline searches at query time.

### Multilingual Alias Sources

Aliases arrive from multiple sources, each covering a different language scope. Track source and language at the dbt Silver level — not stored in the graph itself, but auditable.

| Language scope | Source | dbt model | `_alias_lang` |
|----------------|--------|-----------|--------------|
| INN (canonical) | WHO INN list ([who.int](https://www.who.int/teams/health-product-and-policy-standards/inn)) | `stg_who__inn` | `inn` |
| CZ brand names | SÚKL drug registry ([opendata.sukl.cz](https://opendata.sukl.cz/)) | `stg_sukl__drugs` | `cs` |
| SK brand names | ŠÚKL drug registry | `stg_sukl_sk__drugs` | `sk` |
| EN/US synonyms | RxNorm ([nlm.nih.gov](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html)) — USAN basis, monthly full + weekly updates | `stg_rxnorm__synonyms` | `en-US` |
| EN/scientific | ChEMBL | `stg_chembl__synonyms` | `en` |
| USAN→INN bridge | Curated seed file (version-controlled, manual) | `seed_usan_inn_divergences` | — |

**Critical USAN/INN divergences to seed manually** (known cases affecting the EN data pipeline):

| INN (pivot) | USAN (EN variant) | Source |
|-------------|------------------|--------|
| `paracetamol` | `acetaminophen` | WHO INN vs USP — the most common divergence in EN drug literature |
| `epinephrine` | `adrenaline` (older BAN/common) | INN changed to epinephrine ~2000 |
| `norepinephrine` | `noradrenaline` | Same pattern |
| `furosemide` | `frusemide` (older BAN) | Historical BAN, still in some literature |

The `seed_usan_inn_divergences` file ensures the pipeline normalizes `acetaminophen` → `paracetamol` when encountering DDInter or RxNorm entries. Without it, the paracetamol interaction network would be split across two INNs.

**Alias deduplication at Gold:** Multiple sources may provide the same alias with different `_alias_lang` tags. Gold deduplicates by `(inn, alias_normalized)` — one canonical alias per substance, regardless of how many sources contributed it. The normalized alias strips diacritics, lowercases, and collapses whitespace.

---

## Change Detection Between Source Versions

When a new Bronze snapshot arrives, dbt can detect what changed before promoting to Gold.

| Change type | Detection | Action |
|-------------|-----------|--------|
| New drug registration in SÚKL | New row in `stg_sukl__drugs` not in previous Gold | Add Drug + ActiveIngredient nodes |
| Drug deregistered from SÚKL | Row in previous Gold missing from new Silver | **Do NOT delete** — mark Drug as `status: withdrawn`. User inventory items may point to it |
| New interaction in DDInter | New INN pair in `stg_ddinter__interactions` | Add Interaction node with new Source version |
| Interaction removed in DDInter | INN pair in previous Gold missing from new Silver | **Do NOT auto-remove.** Flag for manual review. Log as `interaction_status: removed_by_source` with date. Conservative: keep the warning |
| Severity changed in DDInter | Same INN pair, different severity | Take the **higher severity** (conservative). Log both in Source provenance. Create a `severity_change_log` dbt model |
| New DDInter version overall | Version field changes | Full re-run of DDInter Silver models, diff against previous Gold |

**The conservative principle:** in a drug safety system, removing a warning is more dangerous than keeping a stale one. Interactions are never auto-deleted; severity is never auto-downgraded.

---

## Data Quality Rules

Run as dbt tests on Gold models. Failures block the Neo4j load.

| Rule | dbt test type | What it catches |
|------|--------------|----------------|
| INN required on both sides | `not_null` | Interaction without resolved INN → excluded |
| ATC format | Custom data test | Codes not matching `[A-Z]\d{2}[A-Z]{2}\d{2}` |
| Self-interaction | Custom data test | `subject_inn == object_inn` after INN resolution |
| Severity vocabulary | `accepted_values` | Severity not in `{critical, major, moderate, minor}` |
| Source provenance | `not_null` | Interaction missing source reference |
| Symmetric completeness | Custom data test | CONTRAINDICATED and ADDITIVE pairs must have both direction records |
| Severity distribution sanity | Custom data test | If >50% of interactions are "critical," flag as anomalous (source problem) |
| Resolution rate | Custom data test | <95% of DDInter pairs resolved → pipeline warning `[ANALYSIS — engineering quality target; not validated against actual DDInter data yet]` |
| Never-miss completeness | Custom data test | All never-miss pairs exist in Gold with correct severity |
| Known drug spot-check | Custom data test | Verify 10 known drug pairs (warfarin+ibuprofen, etc.) resolve correctly |

---

## Data Lineage (dbt-native)

dbt provides lineage automatically through its DAG:

```
bronze/sukl/*.xml → stg_sukl__drugs → gold_drugs → [Neo4j loader] → (:Drug)
bronze/sukl/*.xml → stg_sukl__ingredients → gold_ingredients → [Neo4j loader] → (:ActiveIngredient)
bronze/ddinter/*.csv → stg_ddinter__interactions → gold_interactions → [Neo4j loader] → (:Interaction)
```

Each Gold record carries `_loaded_at`, `_source_version`, `_bronze_path` — full provenance chain from Neo4j node back to the raw file.

`dbt docs generate` produces a browsable lineage graph — useful for the portfolio showcase and for Martina's review.

---

## User Data — PostgreSQL (OLTP)

No medallion. This is transactional data owned by the user, not knowledge base data.

**Schema areas:**

- `users` — auth identity, preferences
- `inventory_items` — drug name as entered, resolved `Drug.id` pointer, quantity, unit, expiry_date, opening_date, active flag
- `alerts` — expiry windows (90/30/7 day), interaction warnings, low stock
- `audit_log` — every system answer with query_class, graph_snapshot_id, source citations, timestamp

**Add-to-inventory flow:**

1. User types "Paralen 500 mg"
2. Entity resolution pipeline (same one used at query time) resolves → `Drug{name: "Paralen"}` → `ActiveIngredient{inn: "paracetamol"}`
3. If resolved: create `inventory_item` with `drug_id` pointer
4. If not resolved: store as free-text, flag for manual Drug node creation

The `inventory_item` points to `Drug`, not `ActiveIngredient`, because the user owns a specific brand product with a specific expiry date. Interaction checking traverses `Drug → [CONTAINS] → ActiveIngredient → [Interaction]` at query time.

---

## Rebuild and Versioning

| Trigger | Action |
|---------|--------|
| New SÚKL XML release | Download to new Bronze directory → re-run dbt from staging |
| DDInter version update | Download to new Bronze directory → re-run DDInter Silver + Gold models → diff report |
| Manual alias addition | Update seed file → re-run entity resolution models only |
| Graph invariant failure | Neo4j load blocked — fix Gold data or transformation logic |
| Rollback needed | Point dbt at previous Bronze directory → re-run full pipeline → reload Neo4j |

Each successful Gold load creates a new `GraphSnapshot` record. The `audit_log` table records which snapshot answered each user query — required for UC9 ("why did the answer change?").

`dbt snapshot` tracks slowly changing dimensions: if DDInter changes the severity of warfarin+ibuprofen from "critical" to "major," the snapshot table preserves the history of that change with timestamps.
