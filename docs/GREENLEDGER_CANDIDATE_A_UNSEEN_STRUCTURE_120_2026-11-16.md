# Candidate A evaluation on the frozen unseen-structure pilot

## 1. Result summary

Candidate A was evaluated without retraining or tuning on the frozen 120-document pilot. It used the existing character n-gram line-role artifact and the same candidate-only interface, frozen documents, contract, and evaluator as the corrected current-pipeline baseline. Its carbon-critical extraction F1 was **0.1001**, below the current pipeline's **0.3019**. Candidate A had higher ambiguity-detection F1 (**0.3462** vs **0.2609**) but lower domain accuracy and a higher unsupported-value rate. It did not produce an automatic readiness classification.

These are descriptive results on one synthetic pilot. They do not establish statistical significance, real-SME performance, or production readiness.

## 2. Candidate A and adapter

Candidate A is the existing supervised character n-gram hashed linear line-role classifier (`greenledger_char_ngram_line_role_v1`). It reads OCR transcript lines and identifies these existing field roles: activity description, quantity, unit, invoice date, supplier, billing period, LPG cylinder net-mass text, and vehicle reference. Its existing deterministic post-processing performs activity normalization, date normalization, and quantity/unit normalization. Confidence is not calibrated. It does not select a factor, scope, accounting boundary, or emissions result.

The benchmark-only adapter is `greenledger/benchmark/candidate_a_adapter.py`. It feeds Candidate A the transcript from the existing RapidOCR `recognize_upload` path. The adapter passes only document bytes, MIME type, and an opaque candidate ID; OCR gets a generic `candidate-input` filename. Candidate predictions finish before the runner loads annotations. The adapter does not receive an annotation, domain label, original filename/path, manifest row, expected result, or evidence-state label.

Domain is candidate-predicted from Candidate A's own normalized activity. It returns `UNDETERMINED` when Candidate A has no supported activity. Candidate A emits no material identity, transport mode, freight mass, distance, or vehicle class; the adapter leaves those fields undetermined. It does not infer LPG mass from cylinder count. A cylinder-net-mass text result without a normalized numeric mass remains insufficient evidence.

## 3. Dataset and protocol

- Dataset: `data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/`, 120 documents.
- Evidence states: frozen pilot annotations, 40 ready, 40 incomplete, and 40 ambiguous; annotations were loaded only after prediction generation.
- Candidate input: opaque candidate ID, document bytes, MIME type.
- OCR: RapidOCR 3.9.2 with the existing verified local ONNX assets; no model assets were downloaded.
- Evaluation command: `.venv-ocr-eval\Scripts\python.exe scripts\evaluate_candidate_a_contract.py`.
- Evaluator: `greenledger.benchmark.evaluator.evaluate_predictions`, unchanged.
- Contract: version 1.0; OCR text metrics are excluded from this field-evaluation layer.
- Candidate A artifact: `models/ai_field_extraction/char_ngram_line_role_v1.json`.
- Artifact SHA256: `6b7cecb47346fa8582eb4dc3963a746bf932c06874caa784f98bcd6a53d205ab`.
- Training metadata in that artifact: train split, 325 documents. No training or tuning was performed on the pilot.
- Old quarantined test split: not accessed.

## 4. Aggregate results

### Carbon-critical extraction

| TP | FP | FN | Precision | Recall | F1 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 37 | 8 | 657 | 0.8222 | 0.0533 | 0.1001 |

### Evidence grounding

| Metric | Result |
| --- | ---: |
| Scalar candidates in carbon-critical fields | 84 |
| Unsupported candidates | 23 / 84 (0.2738) |
| Evidence-text coverage | 84 / 84 (1.0000) |
| Evidence-anchor correctness | 70 / 81 evaluable anchors (0.8642) |
| Page correctness | Not evaluable; no page anchors |
| Bounding-box IoU | Not evaluable; no boxes |

Unsupported-value rate uses the shared evaluator definition: a scalar proposal is unsupported if it matches neither the reference value/candidates nor text in its annotated evidence. The evaluator also reports a legacy normalized-only unsupported rate of 3/45 (0.0667); the primary contract metric above includes raw-only scalar candidates.

### Missing evidence, ambiguity, readiness

| Capability | TP | FP | FN | TN | Precision | Recall | F1 | Safety rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Missing-evidence detection | 38 | 80 | 2 | 0 | 0.3220 | 0.9500 | 0.4810 | False completion: 0/40 |
| Ambiguity detection | 9 | 3 | 31 | 77 | 0.7500 | 0.2250 | 0.3462 | False resolution: 0/40 |

Candidate A predicted `UNDETERMINED` readiness for all 120 documents. Three-way readiness macro-F1 was **0.0000**. The zero false-completion and false-resolution rates arise because it never predicts `READY`; they do not demonstrate a functioning readiness gate. Candidate A's line-role extractor can mark a field ambiguous, but its existing output does not retain the individual ambiguous lines, so those ambiguity records may lack candidate values and evidence anchors.

## 5. Candidate-predicted domain classification

Accuracy was **0.4583 (55/120)** and macro-F1 was **0.5733**. It classified all 20 diesel documents correctly, 18/20 LPG correctly, and 17/20 electricity correctly. All 30 materials and all 30 freight documents were undetermined.

| Domain | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Electricity | 17 | 0 | 3 | 1.0000 | 0.8500 | 0.9189 |
| Diesel | 20 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| LPG | 18 | 0 | 2 | 1.0000 | 0.9000 | 0.9474 |
| Materials | 0 | 0 | 30 | 0.0000 | 0.0000 | 0.0000 |
| Freight | 0 | 0 | 30 | 0.0000 | 0.0000 | 0.0000 |

## 6. Per-domain carbon-critical extraction

| Domain | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Electricity | 12 | 5 | 92 | 0.7059 | 0.1154 | 0.1983 |
| Diesel | 16 | 3 | 86 | 0.8421 | 0.1569 | 0.2645 |
| LPG | 9 | 0 | 86 | 1.0000 | 0.0947 | 0.1731 |
| Materials | 0 | 0 | 150 | 0.0000 | 0.0000 | 0.0000 |
| Freight | 0 | 0 | 243 | 0.0000 | 0.0000 | 0.0000 |

## 7. Selected per-field extraction results

| Field | TP | FP | FN | Gold present | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Activity description | 33 | 0 | 87 | 120 | 0.4314 |
| Quantity | 2 | 0 | 44 | 46 | 0.0833 |
| Unit | 2 | 0 | 72 | 74 | 0.0526 |
| Billing period | 0 | 5 | 18 | 18 | 0.0000 |
| Vehicle reference | 0 | 3 | 7 | 7 | 0.0000 |
| Net LPG mass | 0 | 0 | 7 | 7 | 0.0000 |
| Material identity | 0 | 0 | 20 | 20 | 0.0000 |
| Shipment mass | 0 | 0 | 30 | 30 | 0.0000 |
| Distance | 0 | 0 | 27 | 27 | 0.0000 |
| Transport vehicle class | 0 | 0 | 9 | 9 | 0.0000 |

The complete evaluator output contains all scored fields and per-document predictions.

## 8. Comparison with the corrected current pipeline

| Metric | Current pipeline | Candidate A | Candidate A minus current |
| --- | ---: | ---: | ---: |
| Carbon-critical precision | 0.9328 | 0.8222 | -0.1106 |
| Carbon-critical recall | 0.1801 | 0.0533 | -0.1268 |
| Carbon-critical F1 | 0.3019 | 0.1001 | -0.2018 |
| Unsupported-value rate | 0.0000 | 0.2738 | +0.2738 |
| Missing-evidence F1 | 0.5041 | 0.4810 | -0.0231 |
| Ambiguity F1 | 0.2609 | 0.3462 | +0.0853 |
| Readiness macro-F1 | 0.0000 | 0.0000 | 0.0000 |
| Domain accuracy | 0.5000 | 0.4583 | -0.0417 |
| Domain macro-F1 | 0.6000 | 0.5733 | -0.0267 |
| Mean candidate-generation seconds/document | 7.0535 | 9.3526 | +2.2992 |

The extraction comparison is lower for Candidate A overall and in electricity, diesel, and LPG; both systems score zero on material and freight critical fields. Candidate A's ambiguity F1 is higher, though recall remains 0.225 and readiness remains undetermined. Its unsupported-value rate is worse. No statistically significant difference is claimed: this is one paired synthetic pilot, and no confidence interval or hypothesis test was run.

The latency values are from separate full runs. Candidate A's observed OCR mean was 9.174 seconds/document, while its downstream line extraction averaged 0.178 seconds/document. The current baseline did not record a per-document median, so none is inferred for it. The observed end-to-end timing difference should be treated as descriptive; it is not evidence that the Candidate A classifier itself accounts for the full gap.

## 9. Runtime and reproducibility

- Python 3.12.3; Windows 11; Intel Core i5-1235U, CPU-only.
- RapidOCR 3.9.2; ONNX Runtime 1.30.0 CPU; NumPy 2.5.3; Pillow 12.3.0.
- Candidate A inference used no PyTorch; no GPU was used.
- Candidate generation: 1122.317 seconds; total evaluation: 1123.982 seconds.
- Mean / median candidate latency: 9.351 / 8.050 seconds/document.
- Peak process working set: 800,485,376 bytes; peak traced Python allocations: 264,942,280 bytes. The latter excludes native allocations; working set is the broader process measure.
- First-run prediction SHA256: `1d94ef1e831fe7287f2bee227fac546d5223f98a4fb04680b3c53d36a303a2ad`.
- A second complete run produced byte-equivalent prediction objects, equal evaluator output and metrics, and the same prediction SHA256. Its candidate-generation time was 1268.345 seconds (total evaluation 1269.943 seconds); mean / median candidate latency was 10.568 / 8.916 seconds/document. The OCR mean varied from 9.174 to 10.386 seconds/document, while downstream extraction stayed near 0.18 seconds/document. The repeat output was written under `%TEMP%`, outside the repository and frozen pilot.
- The result artifact records model, OCR-asset, source-code, freeze, manifest, and annotation hashes. Source-code hashes were added after inference to repair a metadata-only hash-capture bug; the report artifact records that fact. The candidate adapter/model, OCR, contract, evaluator, and prediction logic were unchanged; only the runner's source-hash collection block changed after both runs.

## 10. Tests, integrity, and limitations

`py -3.12 -m unittest discover -s tests -v` passed **99 tests**. Candidate A-specific tests verify candidate-only inputs, no filename/domain leakage, unchanged predictions when manifest answer-key fields change, domain-free inference signature, schema validity, abstention on unsupported fields, no cylinder-count-to-mass conversion, known artifact SHA256, and frozen-file hash verification. All 120 saved predictions also passed the contract JSON Schema validation.

The freeze verifier confirmed 120 documents and 126 covered files. FROZEN marker SHA256: `e3fcac4917e621a860b29e8924b28f2bd9f764cee3e13b6aaadaa91d251d7c0a`; manifest SHA256: `00d097c8893875c0f1db376698c71b03819750b8184ceedae87a0598ea15377d`; annotations SHA256: `4d9fd0cbeeb0a2627589eb60efd10c2d39af6f501cda50218a487a7f32ec5e8a`. No frozen data changed.

Candidate A remains a limited transcript line-role candidate, not a general document-layout model. It does not support material or freight field extraction, has no calibrated confidence, does not provide page/bounding-box anchors, loses the individual lines behind some ambiguity flags, and does not classify accounting readiness. Results are synthetic-only; real-SME generalization is untested. No VLM was installed or benchmarked.

## 11. Recommendation

Keep Candidate A as a documented research comparison point, but do not select it as the current best-performing extraction pipeline on this pilot. The current pipeline has higher carbon-critical F1, higher domain accuracy, and lower unsupported-value rate. Candidate A's higher ambiguity F1 is a narrow advantage that does not offset its weak extraction recall, absent materials/freight support, or lack of readiness classification.

The complete second run confirmed identical prediction objects, prediction digest, evaluator output, metrics, frozen hashes, and Candidate A artifact hash. Runtime varied between runs, primarily in OCR latency; runtime is reported as an observed measurement rather than a reproducible fixed value.
