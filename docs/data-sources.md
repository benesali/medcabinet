# Data Sources

License-verified 2026-08-31.

## Open Data Pipeline

```
SÚKL DLP (CSV bundle, cp1250)
  → Drug / ActiveIngredient / ATCCode nodes
  → WHO INN list (INN = canonical pivot for all substance identity)
  → ATC/DDD index (level 5 = chemical substance = INN, secondary pivot)
  → DDInter (interaction pairs, mapped via INN)
  → Interaction nodes with ASSERTED_BY → Source{name, version, date}
  → ChEMBL (molecular enrichment + EN synonym aliases via INN)
  → RxNorm (US/EN name mapping + USAN→INN divergence resolution)
```

Every Interaction node gets `ASSERTED_BY → Source{name, version, date}`.
Every alias accumulated in the pipeline carries `_alias_source` and `_alias_lang` at the dbt Gold layer — not stored in the graph, but tracked for provenance and quality checks.

---

## Source Table

| Source | Content | License | CAVEAT role |
|--------|---------|---------|-------------|
| **SÚKL (CZ)** | Drug registry: names, INN, ATC codes, dosage forms, SPC text | Open gov data | Primary entity backbone — Drug + ActiveIngredient + ATCCode nodes |
| **ŠÚKL (SK)** | Same for Slovakia | Open gov data | SK drug mapping (Phase 1 stretch) |
| **DDInter** | ~237K drug-drug interaction pairs with severity, mechanism, management `[SOURCED: online, primary | DDInter v2.0 | ddinter.org | accessed 2026-08-31]` | CC BY-NC-SA 4.0 | Primary interaction source — OK for personal/portfolio use |
| DrugCentral | Drug targets, indications, FDA/EMA approvals | CC BY-SA 4.0 | Indication enrichment. Does NOT have structured DDI pairs despite common assumption. `[GAP — this claim needs a source citation; verify before using as justification]` |
| ChEMBL | Molecular properties, targets, bioactivities | CC BY-SA 3.0 | Molecular enrichment via INN cross-reference |
| RxNorm/RxNav | US drug names, CUI mapping, interaction API | Public domain (NLM) | English name mapping + language-neutral CUI pivot |
| OpenFDA | Drug labels (with interaction sections), adverse event reports | Public domain | Future: NLP extraction from labeling text (Phase 3+) |
| **WHO INN** | Recommended International Nonproprietary Names — the canonical name list for all pharmaceutical active substances | Public (WHO) | **Primary INN authority.** Every `ActiveIngredient.inn` must trace to a WHO rINN. Source: [WHO INN programme](https://www.who.int/teams/health-product-and-policy-standards/inn) |
| **ATC/DDD index** | Anatomical Therapeutic Chemical classification; level 5 = chemical substance = INN equivalent | Public (Norwegian Institute of Public Health / WHO) | Secondary INN pivot when `activeSubstance` field is missing in SÚKL. ATC level 5 IS the chemical substance. Source: [atcddd.fhi.no](https://atcddd.fhi.no/atc/structure_and_principles/) |
| ❌ **DrugBank** | Comprehensive interactions | Non-commercial only | **DO NOT USE.** All MedCheck interaction data traces to DrugBank — confirmed 2026-08-31. |

| **SNOMED CT** | Comprehensive clinical terminology — symptoms/diseases (`Clinical finding` hierarchy), pharmaceutical product concepts with `has active ingredient` relationships, ICD-10 cross-maps; CZ-localized release (CZ has been a SNOMED International member since 2016) | SNOMED International member license — free for national member country use | Phase 2+ candidate: canonical `snomed_id` on Symptom nodes; multilingual symptom labels; ICD-10 cross-mapping for clinical context. **Does NOT contain drug-drug interaction data.** |

---

---

## SÚKL DLP — Technical Details

`[SOURCED: online, primary | opendata.sukl.cz | accessed 2026-09-02]`

### Download

| Property | Value |
|----------|-------|
| Portal | [opendata.sukl.cz](https://opendata.sukl.cz/?q=katalog%2Fdatabaze-lecivych-pripravku-dlp) |
| URL pattern | `https://opendata.sukl.cz/soubory/SOD{YYYYMMDD}/DLP{YYYYMMDD}.zip` |
| Latest (2026-09-02) | `https://opendata.sukl.cz/soubory/SOD20260827/DLP20260827.zip` |
| Size | ~9.5 MB (ZIP), ~50 MB extracted |
| Encoding | **Windows-1250 (cp1250)** — all CSV files |
| Delimiter | semicolon (`;`) |
| Update frequency | Monthly |
| Schema reference | `https://opendata.sukl.cz/soubory/DLP_datove_rozhrani{YYYYMMDD}.csv` |

The raw ingestor (`caveat-raw-sukl`) auto-discovers the current ZIP URL from the catalog page.

### Key CSV Files

| File | Rows (2026-08) | CAVEAT use |
|------|---------------|------------|
| `dlp_lecivepripravky.csv` | 69,759 | Drug nodes — name, registration, ATC, status, dispensing class |
| `dlp_lecivelatky.csv` | 3,378 | ActiveIngredient nodes — `NAZEV_INN` (Latin form), EN name, CZ name |
| `dlp_slozeni.csv` | 807,466 | CONTAINS edges — drug↔ingredient with dose (`AMNT`, `UN`). Filter `S='L'` for active ingredients only (`X` = excipients) |
| `dlp_atc.csv` | — | ATCCode nodes — code, CZ + EN description |
| `dlp_synonyma.csv` | 273,065 | Ingredient aliases — `NAZEV` with `ZDROJ` (source language tag) |
| `dlp_zruseneregistrace.csv` | — | Withdrawn/cancelled registrations — used to mark `Drug.status = withdrawn` |
| `dlp_nazvydokumentu.csv` | — | Links `KOD_SUKL` → SPC/PIL document filenames |
| `dlp_platnost.csv` | — | Dataset validity window (`PLATNOST_OD`, `PLATNOST_DO`) |

### INN Normalization Note

`dlp_lecivelatky.NAZEV_INN` is the **Latin pharmacopoeial form** (e.g. `BISACODYLUM`, `PARACETAMOLUM`), not the normalized WHO rINN. Silver must lowercase and strip the Latin suffix to arrive at the rINN form (`bisacodyl`, `paracetamol`). This replaces the original assumption of an `activeSubstance` XML field. See [data-engineering.md](data-engineering.md) for the updated Silver pipeline.

### Additional SÚKL Datasets (Phase 3+)

| Dataset | URL | Size | Phase |
|---------|-----|------|-------|
| SPC (product characteristics PDFs) | `SOD{YYYYMMDD}/SPC{YYYYMMDD}.zip` | ~2.6 GB | 3+ (NLP extraction) |
| PIL (patient leaflet PDFs) | `SOD{YYYYMMDD}/PIL{YYYYMMDD}.zip` | ~3 GB | 3+ (NLP extraction) |
| DLP History (monthly CSVs, 2024–present) | `SOD{YYYY}/DLP{YYYYMM}.zip` (~9 MB/month) — `[FACT — verified 2026-09-03: 2024-01 through 2026-08 available (32 months); 2023 and older return 404]` | — | 1+ (dbt snapshots, UC9 history) |

SPC and PIL require NLP extraction — not viable as structured sources in Phase 1. DLP History enables dbt snapshot-based change detection and supports UC9 ("what did the system answer before and why did it change?").

---

## Notes

- **DDInter CC BY-NC-SA 4.0** is acceptable for a personal/portfolio project. Not for commercial use.
- Pharmacy availability in CZ/SK: no public real-time API exists — out of MVP scope.
- OpenFDA labeling text requires NLP extraction; not viable as a structured source in Phase 1.
- **SNOMED CT** is a terminology, not an interaction or study database. Use it for structured symptom taxonomy and multilingual labels, not for interaction evidence.

---

## Reference Literature (Never-Miss Set & Testing)

Clinical papers and regulatory sources cited in [testing.md](testing.md). These support the never-miss set and Tier 2 candidates but are not ingested as data sources — they inform which pairs must appear in DDInter.

**Source credibility tiers for clinical claims:**

| Tier | Type | Examples | Citable as evidence? |
|------|------|----------|---------------------|
| A | Peer-reviewed primary literature | PubMed-indexed journals (BMJ JCP, JAMA, Lancet) | Yes — cite DOI/PMID |
| B | Regulatory safety communications | FDA black box warnings, EMA safety updates | Yes — cite with date and URL |
| C | Clinical reference compendiums | Hansten & Horn; Lexicomp; Micromedex | Yes — cite edition |
| D | Consumer health summaries | MedicineNet, WebMD | No — candidate identification only |
| E | Addiction treatment center sites | drugabuse.com, greenhousetreatment.com, talbottcampus.com | No — candidate identification only |

> **Rule:** Consumer sites (Tier D/E) may surface candidate pairs for investigation but cannot justify a Tier 1 never-miss promotion. Every Tier 1 pair must trace to Tier A, B, or C. `[ANALYSIS — editorial policy]`

**Papers cited in testing.md (verify content before Tier 1 use):**

| Citation | PMID / DOI | Likely relevant to |
|----------|-----------|-------------------|
| Journal of Clinical Pharmacology (BMJ) — `jcp.bmj.com/content/s3-9/1/94` | Verify DOI | Warfarin + paracetamol — verify article establishes this DDI |
| PubMed PMID 7810341 | PMID: 7810341 | Theophylline + ciprofloxacin — verify content and year (~1994) |

---

## Naming Systems — INN vs National Variants

**INN is the pivot.** It is not "Latin" — INN names are WHO-standardized international names (systematically constructed, mostly with English/Greek/Latin roots), used in EU pharmacopoeias, prescriptions, and SPC documents. National naming systems have largely converged:

| System | Body | Language | Status vs INN | Relevance |
|--------|------|----------|--------------|-----------|
| **INN (rINN)** | WHO | International | IS the standard | Primary pivot for CAVEAT. Source: [WHO](https://www.who.int/teams/health-product-and-policy-standards/inn) |
| **USAN** | USAN Council / USP | English (US) | "With rare exceptions, identical to INN" (WHO) | Needed for DDInter/RxNorm EN names. Source: [NLM/RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html) |
| **BAN** | UK MHRA | English (UK) | Since ~2000, same as INN for most substances | Minor divergence risk |
| **DCF** | ANSM (France) | French | Same as INN | Not relevant for CZ/SK/EN scope |
| **JAN** | MHLW (Japan) | Japanese | Same as INN | Not relevant |

**Key divergence that matters for CAVEAT:** `paracetamol` (INN/EU/CZ/SK/UK) = `acetaminophen` (USAN/US). DDInter uses mixed EN naming — some entries use `acetaminophen`, some use `paracetamol`. RxNorm uses USAN (`acetaminophen`) as its base. The pipeline must normalize both to the INN `paracetamol`.

**Other known divergences:**
- `adrenaline` / `epinephrine` — INN changed to `epinephrine` in 2000; both in active use
- `isoprenaline` / `isoproterenol` — same substance, different regional names

**How CAVEAT handles this:**
- INN string (WHO rINN) is the canonical key on `ActiveIngredient.inn`
- USAN variants are stored as aliases: `ibuprofen` (INN = USAN, no divergence), `paracetamol` INN with `acetaminophen` as alias
- Alias source is tracked at dbt Silver/Gold level with `_alias_source` and `_alias_lang` columns

## Alias Sources by Language

| Language scope | Source | What it provides |
|----------------|--------|-----------------|
| CZ brand names | SÚKL drug registry ([opendata.sukl.cz](https://opendata.sukl.cz/)) — machine-readable, open gov data | `Drug.name` + `ActiveIngredient.aliases` for CZ brands |
| SK brand names | ŠÚKL drug registry | Same for Slovakia — Phase 1 stretch goal |
| INN (universal) | WHO INN list | `ActiveIngredient.inn` — primary canonical key |
| EN/US synonyms | RxNorm (monthly updates, USAN basis) | EN aliases + USAN→INN bridge (e.g., acetaminophen → paracetamol) |
| Molecular synonyms | ChEMBL (CC BY-SA 3.0) | Additional EN/scientific aliases via InChI/SMILES cross-reference |
| Critical divergences | Curated seed file (manual, version-controlled) | Explicit USAN/BAN→INN mappings for known divergences; the paracetamol/acetaminophen mapping must be here |
