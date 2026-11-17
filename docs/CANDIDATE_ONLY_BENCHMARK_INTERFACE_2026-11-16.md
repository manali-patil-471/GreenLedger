# Candidate-only benchmark interface and corrected baseline

## Purpose

This report documents the repair to the GreenLedger unseen-structure pilot evaluation path. It does not modify the frozen documents, annotations, accounting logic, OCR implementation, or extraction rules. No alternative model was installed or benchmarked.

## Original fairness problem

The earlier `scripts/evaluate_unseen_structure_baseline.py` loop read each annotation and used `annotation["domain"]` to create `proposed_critical_values` and to write a `domain` field into the saved per-document record. It also generated annotation-derived accounting diagnostics and stored the reference evidence state in that result. The earlier contract runner filtered most of those fields out, but it still passed the saved `domain` into the adapter.

The adapter used that domain to choose which domain-critical fields to emit and to relabel an extracted kilogram quantity as `net_lpg_mass`. Its `domain_supported` logic also changed missing source statuses to `UNDETERMINED` for materials and freight. The contract adapter did not itself open the annotation file, but its prediction depended on annotation-derived data supplied by its caller. The prior contract result is preserved as a historical result and is not a candidate-only baseline.

Other annotation-derived baseline fields (`reference_evidence_state`, `proposed_critical_values`, per-document scores, and gold-input accounting diagnostics) were present in the saved baseline record but were not needed by the corrected adapter. The original document IDs also encode domain-like prefixes; the new adapter therefore receives opaque candidate IDs instead of original IDs or file paths.

## Domain decision

`document_domain` is **candidate-predicted**, not a known input. Phase 4 is intended to measure document and activity understanding, and the application requires activity confirmation instead of receiving a trusted domain as an external input. Supplying the annotation domain would hide a classification task and give the candidate privileged field-selection information.

The contract now permits a `document_domain` field. The evaluator separately reports accuracy, per-class precision/recall/F1, macro-F1, micro metrics, and a confusion matrix. Missing or ambiguous predictions count as `UNDETERMINED`. Domain ground truth is consulted only inside the evaluator.

## Candidate input/output boundary

The reusable interface is `greenledger/benchmark/candidate_interface.py`:

- `CandidateAdapter.predict(document)` receives one `CandidateDocumentInput`.
- Its only fields are an opaque `candidate_id`, document bytes, and MIME `media_type`.
- It receives no original document ID, path/name, manifest row, annotation, domain, field status/value, expected result, or layout-family label.
- Candidate outputs use the common `DocumentPrediction` contract. The runner restores original document IDs only after all candidate predictions are generated.
- The current-pipeline adapter runs the existing RapidOCR and rule extractor on the supplied bytes. Those production OCR/extraction functions were not changed.
- Candidate generation finishes before the annotation loader is called. The evaluator then receives predictions and annotations as separate arguments.

The input builder projects only file locator/hash data from the frozen manifest to load the bytes. Manifest domain, activity, document-type, layout, evidence-state, and expected-readiness fields are not forwarded. Original paths and IDs remain in a runner-side mapping and are not exposed to candidate adapters.

## Corrected baseline protocol

Runner: `scripts/evaluate_current_pipeline_contract.py`  
Result: `data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16.json`

The runner verifies the freeze marker and all covered file hashes, constructs opaque candidate inputs from the frozen documents, runs the existing CPU RapidOCR plus extraction pipeline, validates contract predictions, remaps IDs, and only then loads annotations for scoring. It checks the local RapidOCR asset hashes before inference and will fail rather than fetch missing OCR weights. The output is written outside the frozen pilot and does not overwrite either prior baseline artifact.

Prediction SHA256: `ce56339ac39efe92f67381ff35147248704cc50b9e1c03f80e1e0763fdcbbe53`  
Frozen marker SHA256: `e3fcac4917e621a860b29e8924b28f2bd9f764cee3e13b6aaadaa91d251d7c0a`  
Manifest SHA256: `00d097c8893875c0f1db376698c71b03819750b8184ceedae87a0598ea15377d`  
Annotation SHA256: `4d9fd0cbeeb0a2627589eb60efd10c2d39af6f501cda50218a487a7f32ec5e8a`

## Corrected results

The same evaluation metrics as the prior contract baseline were reproduced exactly. Domain classification is additive because the prior result did not score a candidate-predicted domain.

### Carbon-critical extraction

| Metric | Result |
| --- | ---: |
| TP | 125 |
| FP | 9 |
| FN | 569 |
| Precision | 0.9328 |
| Recall | 0.1801 |
| F1 | 0.3019 |

Per-domain results:

| Domain | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Electricity | 41 | 5 | 63 | 0.8913 | 0.3942 | 0.5467 |
| Diesel | 46 | 0 | 56 | 1.0000 | 0.4510 | 0.6216 |
| LPG | 38 | 4 | 57 | 0.9048 | 0.4000 | 0.5547 |
| Materials | 0 | 0 | 150 | 0.0000 | 0.0000 | 0.0000 |
| Freight | 0 | 0 | 243 | 0.0000 | 0.0000 | 0.0000 |

### Candidate-predicted domain classification

Accuracy is 0.5000 (60/120); macro-F1 is 0.6000. The current extractor classified all 20 electricity, 20 diesel, and 20 LPG documents correctly. It returned `UNDETERMINED` for all 30 materials and 30 freight documents. The micro metrics are TP 60, FP 0, FN 60; precision 1.0000, recall 0.5000, F1 0.6667.

### Evidence, missing evidence, ambiguity, readiness

- **Evidence grounding:** 137 scalar candidates in critical fields; 0 unsupported under the evaluator definition (0.0000). Evidence text coverage is 77/137 (0.5620); 73/77 evaluable anchors match (0.9481). Page and bounding-box metrics are not evaluable because the existing extractor supplies neither.
- **Missing evidence:** TP 31, FP 52, FN 9, TN 28; precision 0.3735, recall 0.7750, F1 0.5041. False-completion rate is 0/40 (0.0000). This remains a generic extractor-status proxy, not a domain-complete readiness classifier.
- **Ambiguity:** TP 6, FP 0, FN 34, TN 80; precision 1.0000, recall 0.1500, F1 0.2609. False-resolution rate is 0/40 (0.0000); 9/40 ambiguous documents contain an unflagged scalar candidate.
- **Accounting readiness:** The current pipeline predicts `UNDETERMINED` for all 120 documents. The three-way readiness macro-F1 is 0.0000; no readiness classifier is implemented in the current pipeline.

## Before/after comparison

All previously reported contract metrics and per-domain/per-field extraction metrics are exactly unchanged. A direct comparison of the old and corrected prediction artifacts found 229 scalar candidates in each and **zero changes to candidate values, units, or evidence anchors** across shared fields. The existing OCR/extraction predictions therefore did not change when the annotation-derived domain was removed.

There are 240 field-status changes across the 60 materials/freight documents: `document_type`, `activity_description`, `quantity`, and `unit` changed from the old adapter's annotation-gated `UNDETERMINED` to the current extractor's explicit `MISSING`. Their candidate values remain empty. Existing metric definitions count proposed scalar values and use the same generic review signal, so those status corrections do not change the prior metrics. The new domain-classification metric is reported separately.

## Tests and integrity checks

The full suite passed: `py -3.12 -m unittest discover -s tests -v` (90 tests). Focused tests cover the candidate-only input shape, rejection of annotation-shaped adapter inputs, domain-independent input construction, evaluator/annotation ordering, schema validity, and deterministic adapter output with fixed OCR/extractor dependencies. The saved corrected result is also re-scored by the evaluator and its prediction digest is checked in the regression suite.

The full corrected-pipeline evaluation was run twice from the same frozen inputs. Both runs produced byte-equivalent prediction objects and equal evaluator output for all 120 documents. The prediction SHA256 was identical on both runs: `ce56339ac39efe92f67381ff35147248704cc50b9e1c03f80e1e0763fdcbbe53`.

At evaluation completion, all 120 predictions passed both the Python contract validator and the JSON Schema. The freeze remained `FROZEN`; all 126 covered files matched their recorded hashes. The quarantined old test split was not accessed.

## Limitations

- The current rule extractor classifies only electricity, diesel, and LPG among these five domains; materials/freight remain undetermined.
- Current candidate confidence is not calibrated, and its evidence anchors have no page or bounding-box coordinates.
- The current system does not produce automatic three-way accounting readiness.
- Results are synthetic-pilot evaluation only and do not establish performance on real SME documents.
- No Candidate A, PaddleOCR-VL, or Qwen3-VL model comparison has been run in this task.
