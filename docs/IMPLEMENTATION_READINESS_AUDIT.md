# GreenLedger implementation-readiness audit

**Updated:** 2026-11-14  
**Audit sequence:** repository and documentation review was completed read-only before any project files were changed. This report summarizes that baseline and the subsequent foundation work completed in this task. The frozen v1 activity scope remains electricity, diesel, LPG, selected purchased materials, and selected transport/freight.

## A. Existing data

- FATURA is available locally with 10,000 invoice images and associated generic annotations.
- A local CORD v2 sample and research metadata are present; the full multi-gigabyte collection is not needed for current work.
- SROIE research metadata is present, but its documents were not downloaded or used because access/terms remain unapproved.
- CEA V21.0 materials are retained historically; official CEA V22.0 workbook and guide are now the current source copies.
- GHG Protocol Corporate Standard, Scope 3 guidance, and published Scope 2 guidance/corrections are available.
- GreenLedger synthetic release v0.1.1 contains 520 documents and exact per-document annotations: 200 electricity, 160 diesel, 160 LPG. No real SME documents are present.

## B. Existing knowledge base

- Five frozen canonical activity IDs and context-aware Scope/category mappings are defined.
- The factor catalogue has 37 rows and structured gas-basis, system-boundary, geography, period, methodology, vehicle-class, product-class, and source-hash applicability metadata.
- The global IPCC Tier 1 LPG factor independently recomputes to **2.99230679 kgCO2e/kg** and is `VERIFIED_TIER1_CONDITIONAL` for IPCC 1.A.4.a commercial/institutional stationary combustion with confirmed owned/controlled boundary and verified net mass.
- The SFC India road diesel factor is conditionally available at **2.675 kgCO2e/L TTW** for India road-vehicle Scope 1 combustion. CEA V22 electricity remains CO2-only with a separate result path. Materials, transport, and other diesel/LPG contexts remain unresolved.

## C. Existing schemas

- Benchmark annotation schema v0.3 separates ground truth from predictions and covers task applicability, OCR evidence, normalized quantities/units, scope/category, factor status, CO2e status, uncertainty, and human review.
- Activity ground-truth schema and canonical activity definitions are present.
- The factor CSV schema and catalogue use matching columns. A repeatable validator checks the catalogue structure, unique IDs, conditional LPG derivation, and source-file hashes.

## D. Existing benchmark definitions

- The approved design target remains approximately 800 records: electricity 200, diesel 160, LPG 160, selected materials 160, selected transport 120.
- Release v0.1.1 contains 520 records with family-held-out splits: 325 train, 65 validation, 130 test. Materials and transport are intentionally withheld until their exact subsets, category boundaries, and factors are selected.
- Per-task matching and metrics are defined. The current release has no CO2e targets; its LPG records do not contain the source/boundary context needed to exercise the now-conditionally eligible LPG factor.
- OCR transcription scores are measured on synthetic validation data. No carbon-task performance score or real-SME generalization result is claimed.

## E. Existing scripts

- `scripts/generate_synthetic_benchmark.py` creates the partial synthetic benchmark.
- `scripts/validate_factor_catalogue.py` validates the factor catalogue and source checksums.
- `scripts/evaluate_ocr.py` evaluates installed OCR candidates on the held-out validation split using the existing transcription labels; `scripts/setup_ocr_eval.py` fetches and checksum-verifies the pinned English Tesseract model.
- `scripts/evaluate_rule_fields.py` scores conservative rule candidates against existing synthetic field annotations; raw OCR text is stored only when explicitly requested.
- `scripts/train_ai_field_extractor.py` trains a supervised character n-gram line-role candidate from training annotations only; `scripts/evaluate_ai_field_extractor.py` compares it with rules on the identical 65 validation OCR transcripts. See `docs/AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`.
- `scripts/download_datasets.py` and `scripts/download_cord.py` are legacy acquisition utilities. They can install dependencies or retrieve large data and should not be run without a specific need and reviewed download plan.
- The standard-library local manual-entry app is available. Running it from `.venv-ocr-eval` adds transient OCR transcription and deterministic rule suggestions. The AI candidate remains a separate offline experiment and is not wired into the application.

## F. Existing documentation

The repository includes the frozen v1 scope, field specification, data-acquisition and data-gap plans, benchmark and experiment plans, synthetic benchmark specification, real-SME validation plan, CEA source reviews, source metadata, and factor methodology/decision logs. Stale statements implying no LPG CO2e factor at all were corrected to describe its conditional scope. Candidate material examples and generic transport labels are explicitly marked unapproved.

## G. Missing implementation components

- The model-assisted field-extraction candidate is implemented and measured offline, but final model selection, app integration, confidence calibration, and full pipeline evaluation remain absent. OCR and rule baselines are also measured on synthetic validation data.
- Durable records, database/history, and evaluation harnesses for factor retrieval, CO₂e, calibrated uncertainty, and end-to-end carbon tasks.
- Multi-field transport quantity normalization (verified mass plus distance to tonne-km).
- Full Scope 2, stationary/power-sector diesel, material, and transport CO₂e coverage; conditional fuel factors do not cover all v1 contexts.

A dependency-free local application baseline now supports manual entry, optional in-memory upload, documented normalization, context-aware classification, eligible factor lookup, deterministic trace output, and a confirmation/review gate. See `docs/LOCAL_BASELINE_APP.md`.

## H. Missing data

- Real SME documents with consent, anonymization, provenance, and independently verified annotations.
- Approved exact material subset and transport mode/activity/boundary definitions, with corresponding synthetic documents.
- GreenLedger-specific CO2e benchmark labels. The current synthetic release is controlled document-understanding data, not real validation.

## I. Missing verified emission factors

- Electricity: CEA provides CO2-only grid intensity, now used only by a distinct FY2025-26 CO2 result path; a GHG-complete Scope 2 CO2e method/source is still needed.
- Diesel: CEA provides CO2-only power-sector energy-basis assumptions; SFC provides a separate conditional India road/mobile TTW factor at 2.675 kgCO2e/L. Stationary/power-sector GHG factors and any required litre-to-energy basis remain unresolved.
- LPG: the global Tier 1 factor is independently recomputed and conditionally calculable only for IPCC 1.A.4.a commercial/institutional stationary combustion per verified net kg. Other source categories/geographies remain unresolved; cylinder count needs verified net fill mass.
- Materials: exact supported product subset and matched cradle-to-gate factors are not selected.
- Transport: exact mode, service boundary/Category 4 vs 9, activity basis, and matching factor are not selected.

## J. Dependencies required

- Synthetic rendering pins Pillow 12.3.0 in `requirements-synthetic.txt`.
- Training the experimental line-role model uses the pinned CPU PyTorch environment in `requirements-field-model-eval.lock.txt`; inference in the candidate module uses the standard library and the generated JSON weights.
- The first local app uses Python's standard library and requires Python 3.8 or newer; no app packages are needed.
- No database or AI model-serving dependencies have been selected. OCR evaluation and local OCR UI dependencies are pinned in a separate environment; the standard-library application mode remains available.
- The current `py -3.12` interpreter used for app checks is Python 3.12.3; bare `python` resolves to Python 3.6.8. The current Python 3.12 environment has Pillow 11.3.0, while synthetic generation pins Pillow 12.3.0 and the existing manifest records generation under Python 3.12.14/Pillow 12.3.0. Use `py -3.12` for the app; do not regenerate the release under a different runtime without recording the environment.
- This host reports 15.7 GB RAM and no visible GPU. Tesseract and RapidOCR/ONNX Runtime are installed only in `.venv-ocr-eval`; the dependency-free application environment is unchanged. Peak process memory was not measured.

## K. Potential technical risks

- Synthetic template leakage or overly regular layouts could inflate results; split by held-out layout/vendor families and keep real data separate.
- Missing boundary/source context can cause false Scope 1 or Scope 3 assignments; abstention and human review must remain normal outcomes.
- CO2-only references can be mislabeled as CO2e unless factor eligibility is enforced in code.
- LPG factor is narrow and global; presenting it as India-specific or applying it to an unmatched source category would be invalid.
- Materials and freight charges do not determine physical quantities or emissions; price-to-mass and route-to-distance guessing must be blocked.
- Existing download scripts may install packages or download large corpora. The workspace root is not a Git repository, reducing change-history and rollback support.

## Current status and recommended order

- **DONE:** initial repository audit; source/schema/benchmark foundation review; factor catalogue refresh; task-specific benchmark definition; 520-document synthetic release and integrity checks. Phase 2 adds structured applicability checks, independently recomputed conditional LPG, and a distinct conditional SFC India road-diesel TTW factor while preserving the CEA CO2-only rows.
- **BLOCKED:** full CO2e coverage pending matched electricity, diesel, materials, and transport sources; material/transport synthetic generation pending exact subset/boundary decisions; real-SME validation pending documents and consent.
- **DONE:** runnable local application baseline for manual entry and deterministic trace output. The accounting engine gates conditional LPG and road-diesel CO2e on required context; the separate CEA V22 FY2025-26 electricity CO2-only path requires matching India-grid and applicable-period context. The existing form has not yet been extended to collect all new road/electricity context fields.
- **DONE:** OCR evaluation harness and checksum-verified loader for the 65-record validation split; the full test suite covers OCR metrics/data loading and test-split protection. It reports no results when engines are unavailable.
- **DONE:** RapidOCR, Tesseract, and Florence-2 OCR transcription comparison on all 65 held-out synthetic validation documents. RapidOCR remains the provisional OCR baseline; Florence-2 had higher measured error and latency. This is not a final carbon-field AI/model selection.
- **INVALID / EXCLUDED:** an earlier Florence `<DocVQA>` one-document smoke used an unsupported task prompt. Its harness and two archived outputs are explicitly labeled invalid and are not benchmark evidence.
- **DONE:** provisional OCR transcript and unconfirmed deterministic rule suggestions are integrated into the local upload UI with preview endpoint, source hash, page/pixel limits, and manual carbon-field confirmation; OCR text cannot set categories, retrieve factors, or calculate CO₂e.
- **DONE:** 51 unit tests pass after the Phase 2 accounting governance changes. Rule/AI suggestions expose evidence states, but no calibrated confidence probability is available.
- **DONE:** Rule-only extraction scored on 65 synthetic validation records; perfect results were measured for selected tasks on one held-out layout family. See `docs/RULE_FIELD_EXTRACTION_BASELINE_2026-09-24.md`; this is not real-SME performance.
- **DONE:** Numbered-layout parser gap fixed, including labels with punctuation, plus conservative unique unit-qualified quantity fallback. Rechecked against all 325 training reference transcripts and the 65 RapidOCR validation transcripts. The source document from the earlier `285 kWh` user test was not retained, so this is a verified equivalent parser case, not a replay of that upload.
- **DONE:** Benchmark field-label audit on train/validation only. The extractor uses schema-backed evidence for supplier, date, billing period, activity description, quantity, unit, vehicle reference, and cylinder net mass. Scenario context without document evidence is excluded.
- **QUARANTINED:** The original 130-record test partition after an earlier broad search exposed at least `GL-SYN-L-0160`; the full exposure list cannot be recovered from truncated output. The new split iterator checks the split marker and skips excluded records before JSON deserialization. No test labels or metrics were used in this milestone. See `docs/TEST_SPLIT_QUARANTINE_2026-11-10.md`.
- **DONE (experimental candidate stage):** A supervised character n-gram line-role model was fitted on 325 training documents and compared on 65 validation documents against rules using the same RapidOCR transcripts. Supplier, date, activity description, raw quantity, raw unit, unit normalization, and normalized quantity matched rule scores; billing period, cylinder net mass, and vehicle reference were extracted where the rule baseline had no outputs. See the AI candidate report. The result is synthetic-only and does not select a final model.
- **IN PROGRESS:** final AI approach selection and app integration; calibrated confidence, durable records, factor/category evaluation, and CO₂e benchmark evaluation remain absent.
- **NOT YET STARTED:** broader comparison with pretrained layout/VLM approaches, replacement blinded holdout, real-SME evaluation, factor-retrieval evaluation, and end-to-end carbon benchmark results.

Recommended order: (1) retain this AI candidate as an experimental baseline, not a selected production model; (2) compare a justified layout-aware candidate on train/validation and freeze choices before measuring a new independent holdout; (3) add confidence labels/calibration only if the annotation protocol supports them; (4) handle factor/category methodology as a separate research milestone; (5) integrate only a reviewed extraction candidate behind human confirmation; (6) collect consented, anonymized SME documents for external validation. Do not use the quarantined original test partition.
