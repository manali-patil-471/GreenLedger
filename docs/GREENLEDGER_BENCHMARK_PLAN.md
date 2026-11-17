# GreenLedger Benchmark Plan

This plan defines three separate evaluation layers. Each record declares which tasks it can support; labels from a public generic document dataset must never be treated as carbon-accounting truth.

## A. Public document-understanding data

FATURA and the local CORD sample may support generic document-type, OCR, layout, and generic field-extraction experiments where their supplied annotations are suitable. They are not carbon-accounting datasets and do not provide GreenLedger activity, scope, factor, or CO2e ground truth. SROIE remains excluded unless access and terms are explicitly approved.

Use only the data already present in the repository. Do not download another public dataset unless a defined experiment needs a specific missing capability and its access terms are reviewed first. A public annotation can set `task_coverage` to only the supported generic tasks and leave carbon-specific sections out of `ground_truth`.

## B. GreenLedger synthetic benchmark

The current specification in `docs/SYNTHETIC_GREENLEDGER_BENCHMARK_SPEC.md` recommends 800 documents: 200 electricity, 160 diesel, 160 LPG, 160 selected materials, and 120 selected transport/freight. A partial release contains the first 520 electricity/diesel/LPG records. The 160 material and 120 transport records remain ungenerated pending the exact approved subsets and boundaries.

Every rendered synthetic document must have a one-to-one annotation record conforming to `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json`. Ground truth must be generated from the structured source record before rendering and include document provenance, visible field evidence, task coverage, normalization and conversion traces, context for scope decisions, and the expected review truth. Use fictional supplier identities and values; do not copy private records or present synthetic examples as real SME data.

Synthetic documents should deliberately vary vendor pseudonyms, layouts, wording, dates, quantity and unit formats, currency notation, typography, table structures, field positions, scan quality, spelling, irrelevant content, and optional or ambiguous fields. Hold out vendor/layout families between train, validation, and test to prevent template leakage. Record rendering parameters so instances can be reproduced.

An expected CO2e value is permitted only when the matching verified CO2e factor and every required conversion are available for the represented geography, year, activity basis, and scope/category. CEA CO2-only values are reference data, not CO2e factors. Conditional LPG and India road/mobile diesel factors are now available, but current synthetic records lack some required combustion/boundary context and no record in release v0.1.1 has an expected CO2e target. For unresolved cases, annotate the factor status and an explicit non-calculable outcome; do not put in a guessed factor or expected CO2e. Material and transport sample generation also waits for exact v1 subset and boundary decisions.

## C. Real anonymized SME validation

Real SME documents are a separate external validation set. Collect them only with appropriate consent, anonymize them, preserve provenance, and have trained annotators verify field evidence, activity, organizational-boundary context, and accounting ground truth. Keep real validation records separate from synthetic training or tuning data. No real SME documents are currently collected.

## Matching and scoring rules

Do not use raw text equality as the sole criterion. Each task has an explicit comparison method:

| Task | Comparison and metrics |
| --- | --- |
| Document-type classification | Accuracy, macro-F1, and confusion matrix over the declared label set. Generic public labels are evaluated separately from GreenLedger v1 classes. |
| OCR/text extraction | Character error rate and word error rate on normalized transcription; token or region scores only where alignment annotations exist. |
| Carbon field extraction | Field-level precision, recall, and F1 using canonical field names and presence status. Compare text after documented Unicode/whitespace normalization; compare dates as parsed calendar dates and numeric values numerically. Report exact match only as a supplemental metric. |
| Quantity extraction | Exact match after locale-aware numeric parsing, plus absolute and relative error. Relative error is reported only when the reference is nonzero. |
| Unit normalization | Accuracy on canonical unit labels and conversion correctness on normalized value/unit pairs. `250 litres`, `250 L`, and `Qty: 250 L` are equivalent after parsing; a conversion is accepted only if its rule is documented. |
| Activity normalization | Accuracy and macro-F1 over the frozen canonical activity IDs; ambiguous/out-of-scope cases are evaluated as explicit statuses, not forced into a class. |
| Scope and Scope 3 category | Accuracy, macro-F1, and confusion matrix on records with sufficient context and applicable task coverage. Report ambiguous cases and review recall separately. |
| Factor retrieval | Top-1 factor-ID accuracy only for queries whose expected factor is a verified, eligible catalogue record with matching activity, basis, geography, year, and category/method. Report unresolved-status classification separately; do not score a CO2-only reference as a valid CO2e factor. Top-k is optional and must be justified by a real candidate set. |
| CO2e calculation | MAE and RMSE against verified expected CO2e on calculable cases. Relative error/MAPE is used only for nonzero references and is accompanied by the evaluated sample count. No records in the current synthetic release have verified expected CO2e targets, so this metric is not currently scoreable. |
| Confidence / uncertainty | Brier score and calibration plots for probability of field correctness when confidence is a calibrated probability; otherwise report risk-versus-coverage and error rate by confidence band. State the target event and calibration method. |
| Human-review decision | Precision, recall, and F1 for review-required decisions; emphasize review recall for ambiguous or unsafe-to-calculate records. Also report unnecessary review rate and the sample counts. |
| End-to-end output | Score only records with a verified, calculable ground truth. Report the fraction correctly abstained on unresolved cases separately from numerical accuracy. |

Always report denominators and excluded/unscorable counts by task. Do not pool public, synthetic, and real SME performance into one headline score. Do not report hypothetical or unmeasured results.

## Status

- **DONE:** Annotation schema v0.3 defines task coverage, separate system predictions, evidence, normalization, factor status, calculation status, and human-review truth.
- **DONE:** The task-specific metric and comparison plan is defined above.
- **DONE:** A partial, explicitly synthetic 520-document electricity/diesel/LPG dataset and matching records are generated; held-out layout-family splits are included.
- **BLOCKED:** CO2e benchmark scoring requires annotations that satisfy factor eligibility and conversion conditions. The current release has no expected CO2e targets; its LPG records lack context despite the factor now being conditionally eligible for matching cases.
- **BLOCKED:** Material and transport synthetic ground truth requires final v1 subset and category/boundary decisions.
- **NOT YET STARTED:** Complete 800-record generation, including materials and transport.
- **DONE:** OCR transcription candidates have been compared on the 65-record synthetic validation split; conservative deterministic field-extraction rules have also been scored on those OCR outputs. These are limited synthetic baselines, not model-assisted field-extraction or carbon-accounting results.
- **DONE (initial):** A supervised character n-gram line-role extractor was compared against rules on the 65-record synthetic validation split; see `AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`. Broader layout/VLM comparisons, factor-retrieval and scope/category scoring, CO₂e/end-to-end scoring, and a replacement blinded holdout remain outstanding.
- **QUARANTINED:** The original 130-record test partition after annotation exposure; it is not available for final scoring.
- **NOT YET STARTED:** Real SME collection and validation.
