# Dev Diary

Running log of decisions, blockers, and discoveries during development. Newest entries at the top.

---

## 2026-09-02 (SÚKL DLP bronze ingest — data discovery)

- `[FACT]` **SÚKL data format confirmed by downloading actual data.** The DLP dataset is a ZIP of ~30 CSV files (not XML as originally assumed), encoding Windows-1250, semicolon-delimited, published monthly. Latest: `DLP20260827.zip` (~9.5 MB). `[SOURCED: online, primary | opendata.sukl.cz | accessed 2026-09-02]`
- `[FACT]` **INN field is Latin pharmacopoeial form, not normalized WHO rINN.** `dlp_lecivelatky.NAZEV_INN` contains e.g. `PARACETAMOLUM`, `BISACODYLUM`. Silver must lowercase + strip Latin suffix. Previous docs assumed an `activeSubstance` XML field — corrected.
- `[FACT]` **`dlp_slozeni.S` flag must be filtered.** `S='L'` = active ingredient (*léčivá látka*); `S='X'` = excipient. CONTAINS edges must use `S='L'` only. Confirmed: rows with `AMNT='PL'` (*dle povahy*) are excipients that also have `S='X'`.
- `[FACT]` **Scale confirmed:** 69 759 drug registrations, 3 378 active ingredients, 807 466 composition rows, 273 065 synonym entries.
- `[FACT]` **Three additional SÚKL datasets identified:** DLP History (monthly CSVs back to 2021, cp1250, ~9 MB/month — useful for dbt change detection / UC9); SPC PDFs (~2.6 GB); PIL PDFs (~3 GB). SPC/PIL deferred to Phase 3+ (NLP). History is Phase 1 candidate.
- Bronze ingestor built and successfully run: `src/caveat/pipeline/bronze/sukl.py`. Auto-discovers current ZIP URL from catalog page via regex. Manifest records encoding, file list, and checksum of the source archive.
- Docs updated: `data-sources.md` (SÚKL technical details section), `data-engineering.md` (Bronze layout, Silver pipeline corrected for actual CSV structure).
- Orchestration decision locked: **Prefect 3.x** (not Makefile). Flows will live in `src/caveat/pipeline/flows/`.

---

## 2026-09-01 (naming systems research)

- Researched the drug naming landscape to establish proper alias sourcing strategy across languages.
- `[SOURCED: online, primary]` **INN confirmed as the right universal pivot** — not "Latin," but WHO-standardized international names. National variants (USAN/US, BAN/UK, DCF/France, JAN/Japan) are "with rare exceptions, identical to the INN" per WHO ([WHO INN programme](https://www.who.int/teams/health-product-and-policy-standards/inn)). Accessed 2026-09-01.
- `[ANALYSIS]` **Key divergence documented:** `paracetamol` (INN/EU) = `acetaminophen` (USAN/US). DDInter and RxNorm use EN names, so this mapping must be explicit in the pipeline. Added `seed_usan_inn_divergences` to data-engineering.md. Other divergences: epinephrine/adrenaline, norepinephrine/noradrenaline, furosemide/frusemide.
- `[SOURCED: online, primary]` **ATC level 5 confirmed as secondary INN pivot** for CZ/SK drugs when `activeSubstance` field is missing. Source: [atcddd.fhi.no](https://atcddd.fhi.no/atc/structure_and_principles/). Accessed 2026-09-01.
- `[SOURCED: online, secondary]` **RxNorm coverage note:** ~60% of source drug names normalized; uses USAN (not INN) as base; monthly full releases + weekly FDA updates. Source: [NLM RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html). Accessed 2026-09-01. Good for EN/US brand names; weak for CZ/SK brands — ATC level 5 remains the primary CZ/SK pivot.
- `[FACT]` **SÚKL open data confirmed** at [opendata.sukl.cz](https://opendata.sukl.cz/) — drug registry (LP) available as structured machine-readable data including SPC text. Contact: opendata@sukl.gov.cz for technical spec.
- Added WHO INN and ATC/DDD to `docs/data-sources.md` source table with citable URLs.
- Added "Multilingual Alias Sources" and "Naming Systems" sections to `docs/data-sources.md` and `docs/data-engineering.md`.
- Added alias schema and USAN seed file maintenance to `docs/open-questions.md`.

---

## 2026-09-01

- `[SOURCED: online, tertiary — trace to primary clinical literature before Tier 1 promotion]` Researched dangerous drug combinations to extend the never-miss set. Source: [MedicineNet — 7 Dangerous Drug Combinations](https://www.medicinenet.com/what_are_the_7_more_dangerous_medicines_to_mix/article.htm). Accessed 2026-09-01.
- `[ANALYSIS]` **Gap found:** warfarin + paracetamol (acetaminophen) is a clinically documented critical DDI not in any tier of the never-miss set. Added to Tier 2 for DDInter validation in Phase 1. This is easy to miss because paracetamol is considered "safe" — makes it higher-risk from a user perspective.
- Statins + amiodarone confirmed as a specific instance of the existing CYP3A4-inhibitor + statin Tier 2 entry. Added explicitly to Tier 2 for DDInter coverage check.
- Alcohol + opioids noted as lethal but requires a food-drug interaction source (alcohol = `substance_type: food_component`, DDInter is drug-drug only). Added to Tier 3.
- All 7 combinations from the source cross-referenced against current Tier 1 / Tier 2 — no other gaps found beyond the three above.

---

## 2026-08-31

- Architecture review completed. Phase 0 decisions locked (see [open-questions.md](open-questions.md) and [roadmap.md](roadmap.md)).
- Confirmed DrugBank license blocker — all MedCheck interaction data traces to DrugBank. CAVEAT will build from SÚKL + DDInter + ChEMBL.
- MedCheck graph schema confirmed incompatible — building CAVEAT graph from scratch.
- DDInter CC BY-NC-SA 4.0 accepted for personal/portfolio scope.
