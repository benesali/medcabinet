# MedCabinet (CAVEAT)

**Contraindication-Aware Verification of Evidence, Abstention & Traces**

A personal medication intelligence platform that warns — it does not advise. The system surfaces contraindications and drug interactions from a knowledge graph, explains them via graph paths, and manages a home medication inventory.

Simultaneously a portfolio project demonstrating **how to evaluate AI systems** — all evaluation layers from data to product KPIs — targeting Data & AI Architect roles.

---

## What it does

- **Home inventory** — track drugs, quantities, expiry dates, and opening dates (syrups/creams degrade faster than label expiry)
- **Contraindication checker** — finds interactions between drugs in your cabinet, explains the graph path behind each warning
- **Active ingredient deduplication** — flags when multiple products share the same ingredient (e.g. paracetamol overlap)
- **Expiry alerts** — 90 / 30 / 7 day thresholds + expired
- **Honest abstention** — says "I don't know" when the graph doesn't have the answer; never invents a relation

The AI layer is strictly informational. No treatment recommendations, no dosing, no substitution advice.

---

## Query classes

| Class | Example | System behavior |
|-------|---------|----------------|
| **A — Factual** | "Does ibuprofen interact with warfarin?" | Answers from graph + source citation |
| **B — Treatment suggestion** | "What should I take for a headache?" | Neutral list only + referral to pharmacist |
| **C — Out of scope** | "How much ibuprofen can I give a child?" | Hard refusal + specialist referral — consistent across CZ/SK/EN |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Knowledge graph | Neo4j |
| Application data | PostgreSQL |
| Backend | Python + FastAPI |
| Frontend | React + Next.js |
| Auth | Azure Entra ID / Auth0 |
| AI orchestration | LangGraph + Claude |
| Evaluation | DeepEval, Promptfoo, RAGAS/ARES, Veritas (submodule) |
| Observability | Phoenix, OpenTelemetry, LangSmith |

---

## Data sources

Open-licensed sources only: SÚKL (CZ), ŠÚKL (SK), DDInter, ChEMBL, WHO INN (canonical INN pivot), RxNorm (EN/US synonym bridge). DrugBank excluded — non-commercial license only. DrugCentral under evaluation for indication enrichment.

---

## Evaluation philosophy

Seven-layer pyramid diagnosed bottom-up. A generation error is not worth fixing if retrieval is broken.

1. **Data & graph** — graph invariants as CI Cypher queries (symmetry, orphan nodes, source coverage)
2. **Retrieval** — recall and precision against golden set
3. **Generation** — LLM-as-judge (different model family than generator) + human annotation
4. **Abstention (NESCIO)** — honest-null rate vs. false-abstention rate; risk–coverage AUC
5. **Safety** — never-miss set of critical combinations; hard 100% recall threshold or build fails
6. **Product** — business KPIs
7. **Operations** — latency p50/p95/p99, cost per query

Includes parametric contamination testing: ablation with empty context, fictitious drugs, and counterfactual graph — because LLMs know common interactions from training and will answer correctly even when retrieval fails.

---

## Status

**Phase 1 — Data & Graph (in progress)**

- Phase 0 complete — scope, domain model, data source licenses locked
- Raw ingestors done — SÚKL (DLP, history, SPC, PIL), DDInter, WHO INN; shared base (stream download, ZIP extraction, SourceName enum); date-stamped snapshots with SHA-256 manifests
- Bronze layer defined — PostgreSQL `bronze.*` tables (1:1 with raw CSVs + `_source_file`, `_load_ts`, `_batch_id`); schema in `src/caveat/pipeline/bronze/schema.sql`; loader stub ready
- Silver SÚKL parser in progress — INN normalization (Latin form → WHO rINN), drug/ingredient/composition extraction, withdrawn registration handling

**Owner:** Alisa Benesova  
**Collaborator/Mentor:** Martina Fusková
