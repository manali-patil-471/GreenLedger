# GreenLedger implementation roadmap and repository audit

> **Status refresh (2026-11-10):** This roadmap contains an earlier repository snapshot and its `[BLOCKED]` / `[NOT IMPLEMENTED]` labels are historical. The current implementation-readiness audit and data-gap page supersede those labels. Since the 2026-09 snapshot, the project added a manual-entry accounting app with optional provisional RapidOCR transcription, a three-candidate OCR validation comparison, and an experimental supervised carbon-field extractor measured against rules on train/validation data. The candidate is not integrated or selected. Full CO₂e coverage, a replacement blinded holdout, and real-SME validation remain outstanding.

> **Accounting update (2026-11-14):** Phase 3 added conditional CPWD 2024 reference factors for PPC cement, steel rebar, and generic steel, plus seven India road-freight WTW factors from SFC India/TERI 2026. The accounting path and minimal form fields are implemented and source-hash validated for those exact cases. Other materials/modes, benchmark documents for these classes, and real-SME validation remain outstanding. See `docs/GREENLEDGER_FACTOR_DECISIONS.md`.

## 1) Project objective

[VERIFIED COMPLETE]

The research objective in the repository is:

"Can a document-understanding pipeline extract and normalize carbon-relevant fields from heterogeneous SME business documents, classify them into the correct GHG Protocol scope/category, retrieve the relevant authoritative emission factor, and produce a human-verifiable CO2e estimate with uncertainty awareness?"

Evidence:
- `GreenLedger/context.md`
- `GreenLedger/docs/IMPLEMENTATION_READINESS_AUDIT.md`
- `GreenLedger/docs/GREENLEDGER_BENCHMARK_PLAN.md`
- `GreenLedger/docs/GREENLEDGER_V1_SCOPE.md`

This is a research/data-foundation project, not a production application build.

## 2) V1 scope

[VERIFIED COMPLETE]

Current V1 scope is intentionally narrow and realistic:
- Purchased electricity
- Diesel/fuel
- LPG
- Selected purchased materials
- Selected transport/freight

The repo explicitly avoids forcing unsupported activities into v1.

Evidence:
- `GreenLedger/knowledge_base/activities/activities.json`
- `GreenLedger/knowledge_base/scope_mapping/mapping.json`
- `GreenLedger/docs/GREENLEDGER_V1_SCOPE.md`
- `GreenLedger/docs/GREENLEDGER_FACTOR_DECISIONS.md`

## 3) Complete current status

[VERIFIED COMPLETE]

### 3.1 Data foundation and project structure

[VERIFIED COMPLETE]

The repository contains the required GreenLedger project skeleton and data organization under `GreenLedger/`:
- `data/public/{cord,fatura,sroie}`
- `data/synthetic/{electricity,fuel,materials,transport}`
- `data/real_sme/`
- `knowledge_base/{emission_factors,activities,scope_mapping,standards}`
- `metadata/`
- `docs/`
- `scripts/`

Evidence:
- `GreenLedger/context.md`
- `GreenLedger/metadata/REPO_INVENTORY.json`

### 3.2 Public datasets

[VERIFIED COMPLETE]

1. FATURA
- Verified official public dataset and downloaded archive present.
- Local files:
  - `GreenLedger/data/public/fatura/FATURA.zip`
  - `GreenLedger/data/public/fatura/zenodo_record_8261508.json`
  - `GreenLedger/data/public/fatura/METADATA.md`
  - `GreenLedger/data/public/fatura/extracted/invoices_dataset_final/`
- Observed content: 10,000 invoice images and multi-format annotation files from the official FATURA dataset.
- Status: useful for generic invoice/document understanding research only; not carbon ground truth.

2. CORD v2
- Local metadata and sample dataset present.
- Local files:
  - `GreenLedger/data/public/cord/METADATA.md`
  - `GreenLedger/data/public/cord/README.md`
  - `GreenLedger/data/public/cord/cord_v2_hf/dataset_infos.json`
  - `GreenLedger/data/public/cord/cord_v2_hf/data/test-00000-of-00001-9c204eb3f4e11791.parquet`
- Status: verified as a generic receipt/document dataset; not carbon-accounting ground truth.
- The full multi-GB CORD LFS dataset was intentionally not fully downloaded; project scope was frozen before that expansion.

3. SROIE
- Source metadata exists but no actual downloaded dataset.
- Local file:
  - `GreenLedger/data/public/sroie/METADATA.md`
- Status: official challenge dataset, registration required, not downloaded and not used as GreenLedger carbon data.

### 3.3 Carbon-accounting knowledge sources

[VERIFIED COMPLETE]

The repository contains official carbon-accounting sources:
- `GreenLedger/knowledge_base/emission_factors/CO2_Database_V_21.0.xlsx`
- `GreenLedger/knowledge_base/emission_factors/User_Guide_V_21.0.pdf`
- `GreenLedger/knowledge_base/emission_factors/CO2_Database_V_22.0.xlsx` (if present in the repo; if not, the source log documents the latest official CEA v22.0 workbook and guide)
- `GreenLedger/knowledge_base/standards/GHG Protocol Corporate Standard Revised (English).pdf`
- `GreenLedger/knowledge_base/standards/Scope3_Calculation_Guidance_0[1].pdf`
- `GreenLedger/metadata/SOURCES.md`

The repo also documents the IPCC EFDB as the authoritative source to consult, with the project intentionally avoiding guessed numeric factors.

## 4) Completed and verified components

[VERIFIED COMPLETE]

- Project structure and handoff context created:
  - `GreenLedger/context.md`
  - `GreenLedger/metadata/REPO_INVENTORY.json`

- Source provenance and dataset verification recorded:
  - `GreenLedger/metadata/SOURCES.md`
  - `GreenLedger/data/public/fatura/METADATA.md`
  - `GreenLedger/data/public/cord/METADATA.md`
  - `GreenLedger/data/public/sroie/METADATA.md`

- authoritative carbon-source summary and CEA review documents:
  - `GreenLedger/docs/CARBON_ACCOUNTING_SOURCE_SUMMARY.md`
  - `GreenLedger/docs/CEA_V21_RELEVANT_CONTENT.md`
  - `GreenLedger/docs/CEA_V22_RELEVANT_CONTENT.md`

- Scope freeze and benchmark design recorded:
  - `GreenLedger/docs/GREENLEDGER_V1_SCOPE.md`
  - `GreenLedger/docs/GREENLEDGER_BENCHMARK_PLAN.md`
  - `GreenLedger/docs/GREENLEDGER_FIELD_SPECIFICATION.md`
  - `GreenLedger/docs/SYNTHETIC_GREENLEDGER_BENCHMARK_SPEC.md`
  - `GreenLedger/docs/GREENLEDGER_DATA_GAP.md`
  - `GreenLedger/docs/GREENLEDGER_EXPERIMENT_PLAN.md`

- Activity and mapping definitions:
  - `GreenLedger/knowledge_base/activities/activities.json`
  - `GreenLedger/knowledge_base/scope_mapping/mapping.json`

- Benchmark annotation schema created:
  - `GreenLedger/data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json`

- Factor catalogue and methodology frozen in a documented non-guessed form:
  - `GreenLedger/knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv`
  - `GreenLedger/knowledge_base/emission_factors/GREENLEDGER_V1_CALCULATION_METHODS.md`
  - `GreenLedger/docs/GREENLEDGER_FACTOR_DECISIONS.md`

- There is a validator for catalogue structure and source checksums:
  - `GreenLedger/scripts/validate_factor_catalogue.py`

- Partial synthetic benchmark was generated and is present:
  - `GreenLedger/data/synthetic/greenledger_v0_1_1_partial/manifest.json`
  - `GreenLedger/data/synthetic/greenledger_v0_1_1_partial/annotations.jsonl`
  - `GreenLedger/data/synthetic/greenledger_v0_1_1_partial/documents/`

Evidence of generated counts from the manifest:
- `generated_total`: 520
- `electricity`: 200
- `diesel`: 160
- `lpg`: 160
- `materials`, `transport`: withheld/not generated

## 5) Partially completed components

[PARTIALLY COMPLETE]

### 5.1 Synthetic benchmark

[PARTIALLY COMPLETE]

A partial synthetic benchmark exists, but it is explicitly not the full target benchmark.

Evidence:
- `GreenLedger/data/synthetic/greenledger_v0_1_1_partial/manifest.json`
- `GreenLedger/scripts/generate_synthetic_benchmark.py`
- `GreenLedger/data/synthetic/greenledger_v0_1_1_partial/README.md`

Actual status:
- 520 synthetic documents exist
- 200 electricity, 160 diesel, 160 LPG
- 0 CO2e ground truth records are present in this partial release
- 160 materials and 120 transport records are intentionally not generated

This is not a complete 800-document GreenLedger benchmark and cannot be treated as final research evaluation data.

### 5.2 Emission-factor foundation

[PARTIALLY COMPLETE]

The factor catalogue is structured and traceable, but not all v1 activities are complete or ready for CO2e calculation.

Verified facts from the repo:
- Electricity CEA values are present as CO2-only references, not CO2e factors.
- The global LPG factor has been independently recomputed and is conditionally calculable for the narrow commercial/institutional stationary context. A separate conditional SFC India road/mobile diesel TTW factor is also in the catalogue; other diesel/LPG contexts remain unresolved.
- Materials and transport remain unresolved and explicitly not selected for v1 use yet.

Evidence:
- `GreenLedger/knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv`
- `GreenLedger/docs/GREENLEDGER_FACTOR_DECISIONS.md`
- `GreenLedger/knowledge_base/activities/activities.json`

## 6) Missing components

[NOT IMPLEMENTED]

- Real SME documents and validation set
- Final material subset with authoritative factors
- Final transport subset with authoritative factors
- Final electricity CO2e-ready factor source for a fully compliant Scope 2 calculation
- Final diesel CO2e-ready source/method for combustion activity
- End-to-end application with OCR, extraction, review, and calculation engine
- Model selection and empirical OCR comparison
- Benchmark evaluation harness against a verified CO2e ground truth
- Real production deployment pipeline

Evidence:
- `GreenLedger/data/real_sme/` is present but empty
- `GreenLedger/docs/GREENLEDGER_DATA_GAP.md`
- `GreenLedger/docs/GREENLEDGER_EXPERIMENT_PLAN.md`
- `GreenLedger/docs/IMPLEMENTATION_READINESS_AUDIT.md`

## 7) Blocked components

[BLOCKED]

### 7.1 Electricity factor choice

[BLOCKED]

The repo documents that electricity values from the CEA workbook are CO2-only references, not CO2e-ready factors. A final GHG-complete Scope 2 factor method remains unresolved.

Evidence:
- `GreenLedger/docs/GREENLEDGER_FACTOR_DECISIONS.md`
- `GreenLedger/knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv`
- `GreenLedger/metadata/SOURCES.md`

### 7.2 Diesel factor choice

[BLOCKED]

The repo records diesel as a CO2-only reference path and states that the CO2e factor path remains unresolved without the required source-category and GWP basis conditions.

### 7.3 LPG eligibility

[BLOCKED]

The retained LPG candidate is not currently eligible for calculation. If it is independently revalidated and approved, its applicability must still be limited to verified controlled commercial/institutional stationary combustion with verified net mass.

### 7.4 Materials and transport

[BLOCKED]

Exact materials and transport/activity subsets are not finalized and no authoritative factors are approved for v1.

## 8) Research risks

[VERIFIED COMPLETE]

The repository already explicitly identifies core research risks, including:
- using generic invoice/receipt datasets as carbon ground truth
- conflating CO2-only references with CO2e factors
- missing verified CO2e ground truth
- layout or vendor leakage in synthetic data
- unsupported activity assignments without evidence
- no real SME validation yet
- claiming model superiority without comparison

Evidence:
- `GreenLedger/docs/GREENLEDGER_BENCHMARK_PLAN.md`
- `GreenLedger/docs/IMPLEMENTATION_READINESS_AUDIT.md`
- `GreenLedger/knowledge_base/scope_mapping/mapping.json`

## 9) Required experiments

[NOT IMPLEMENTED]

The repo documents required experiments, but they are not yet executed:
1. Electricity factor method comparison (grid-average vs marginal vs market-based method, only with authoritative source and proper Scope 2 interpretation)
2. Diesel and LPG boundary/context validation with explicit source-category logic
3. Material subset approval using authoritative cradle-to-gate factors
4. Transport mode and category boundary validation for selected v1 freight cases
5. OCR/model comparison only after dependencies are installed and the benchmark is valid
6. End-to-end document understanding and carbon-annotation evaluation on the valid subset

Evidence:
- `GreenLedger/docs/GREENLEDGER_EXPERIMENT_PLAN.md`
- `GreenLedger/docs/GREENLEDGER_BENCHMARK_PLAN.md`

## 10) Required implementation

[NOT IMPLEMENTED]

The following are still required and are not currently represented as working implementation code in the repository:
- OCR pipeline
- document preprocessing
- document classification
- field extraction
- normalization and unit conversion engine
- Scope/category classification
- deterministic emission-factor retrieval
- CO2e calculation engine
- human-review and traceability layer
- app/UI backend frontend

Evidence:
- The repo contains only docs, metadata, benchmark schemas, scripts, and data; no training code, OCR stack, backend, or UI implementation is present.
- `GreenLedger/scripts/` contains only benchmark generation and validation scripts.

## 11) Required validation

[NOT IMPLEMENTED]

Validation must be done only after the underlying factor and benchmark foundation is complete.

Required validation tasks:
- verify all factor rows against authoritative sources
- verify unit conversions and scope assignments against the documented rules
- validate synthetic benchmark annotation integrity and split separation
- run OCR/model comparison on benchmark data only after dependencies are approved and installed
- ensure real CO2e ground truth exists before reporting CO2e error metrics
- evaluate human-review and abstention behavior separately from numerical accuracy

## 12) Final end-to-end workflow

[PARTIALLY COMPLETE]

The intended workflow in the repository is:

Business document
→ preprocessing
→ OCR/text/layout extraction
→ AI-assisted document understanding
→ carbon-relevant field extraction
→ confidence assessment
→ human verification when required
→ activity/unit normalization
→ GHG scope/category classification
→ verified emission-factor retrieval
→ deterministic CO2e calculation
→ validation/uncertainty assessment
→ final traceable result

This architecture is documented, but the actual implementation is not present.

Evidence:
- `GreenLedger/docs/GREENLEDGER_BENCHMARK_PLAN.md`
- `GreenLedger/context.md`

## 13) Dependency-ordered implementation plan

[VERIFIED COMPLETE] for the research foundation; [NOT IMPLEMENTED] for the implementation path.

1. Finalize verified electricity method and evidence path for Scope 2
   - Status: [BLOCKED]
   - Reason: source records exist, but full GHG-complete CO2e factor remains unresolved.

2. Finalize diesel and LPG applicability rules and boundary conditions
   - Status: [BLOCKED]
   - Reason: the LPG factor is verified only for its narrow stationary source category; the new India road-diesel TTW factor cannot cover stationary/power-sector use and the SFC source caveat remains documented.

3. Select approved material subset and factor records
   - Status: [BLOCKED]
   - Reason: exact subset and authoritative material factors are not yet approved.

4. Select approved transport subset and category boundary
   - Status: [BLOCKED]
   - Reason: exact mode, mass-distance logic, and category selection remain unresolved.

5. Extend synthetic benchmark only for approved activities
   - Status: [PARTIALLY COMPLETE]
   - Reason: 520 documents exist; full 800-target benchmark is not complete.

6. Collect and anonymize a small real SME validation set
   - Status: [NOT IMPLEMENTED]
   - Reason: no real data is present.

7. Install and evaluate OCR candidates on a valid benchmark subset
   - Status: [PARTIALLY COMPLETE]
   - Reason: RapidOCR, Tesseract, and Florence-2 were compared on synthetic validation; RapidOCR remains provisional and has a local transcript UI. An initial AI field-extraction candidate was measured separately, but broader model selection, application integration, and replacement-holdout evaluation remain pending.

8. Implement deterministic normalization and factor retrieval code
   - Status: [NOT IMPLEMENTED]

9. Implement the review/tracing and calculation engine
   - Status: [NOT IMPLEMENTED]

10. Build end-to-end application and validation pipeline
   - Status: [NOT IMPLEMENTED]

11. Run final benchmark evaluation
   - Status: [NOT IMPLEMENTED]

## Final decision

[BLOCKED]

Exact product-ready GreenLedger v1 CO2e benchmark generation is not ready yet.

The repository currently contains:
- verified data-source and project-scoping work,
- structured metadata and schemas,
- a partial synthetic benchmark,
- a non-guessed factor catalogue with blocked/unresolved entries,
- but no complete verified CO2e ground-truth benchmark and no implemented end-to-end application.

If the project is to proceed, the next gate is not model development or UI implementation; it is the resolution of authoritative, approved v1 factor/methodology decisions for electricity, diesel, LPG, and the narrow material/transport subsets.

This roadmap is intentionally conservative and matches the project’s research-first posture.
