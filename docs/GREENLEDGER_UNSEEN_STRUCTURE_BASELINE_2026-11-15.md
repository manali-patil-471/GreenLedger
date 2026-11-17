# GreenLedger unseen-structure pilot — current pipeline baseline

**Run date:** 2026-11-15  
**Result:** completed on all 120 frozen documents  
**Evaluation status:** current pipeline baseline only; no alternative model was run.

## 1. Executive summary

The current upload pipeline completed OCR on **120/120 documents**, with no document-level OCR failures. On 526 carbon-critical evidence snippets, targeted OCR scored **8.16% anchor-CER**, **8.39% anchor-WER**, and **85.36% exact anchor text**. These are evidence-snippet metrics, not full-page OCR CER/WER; the annotations do not contain full-page transcripts.

The existing conservative extractor has high precision when it proposes a supported field, but low coverage across the carbon-critical schema: exact normalized field micro-F1 was **30.19%** (125 TP, 9 FP, 569 FN over 890 annotated field records). It extracted no fields for the 30 material and 30 freight documents. It does not extract the accounting context required by any domain. Its explicit ambiguity signal caught **6/40** ambiguous documents; it produced a single scalar for an ambiguous quantity/mass in **9/40** without marking the field ambiguous.

The app did not automatically classify readiness or calculate any upload-only case: all 120 readiness outputs are **UNDETERMINED**, and no OCR suggestion was sent to accounting. In a separate diagnostic only, frozen ground-truth fields were supplied as manually entered and confirmed values to the existing deterministic accounting engine. That reproduced the annotated result, factor and scope/category for **40/40 ready cases**. Because the expected results were produced by the same engine, this confirms repeatability and applicability, not independent factor validity or end-to-end document processing.

## 2. Evaluation protocol

### Frozen input and leakage controls

Before reading annotations, the runner verified every SHA-256 and byte count in `FROZEN.json`, the complete 126-file covered set, and the frozen manifest and annotation hashes. The marker SHA-256 was `e3fcac4917e621a860b29e8924b28f2bd9f764cee3e13b6aaadaa91d251d7c0a`. The same frozen hashes were rechecked after the run. No document, annotation, manifest, or marker was modified. The quarantined old test split was not accessed.

### Pipeline run

The benchmark called the existing functions used by the app upload path:

1. `greenledger.ocr.recognize_upload` on each original PDF/image.
2. `greenledger.field_extraction.extract_carbon_fields` on the returned transcript, when nonempty.
3. Current extractor review flags/reasons were recorded as emitted.

OCR candidates remained advisory. They were **not** copied into `evaluate_submission`; no manual corrections or ground-truth values were used for extraction or readiness. The app currently requires manual field entry and human confirmation, so upload-only automatic accounting results are absent by design.

For the separate ready-case accounting diagnostic, the frozen ready annotations were mapped to the engine’s existing input fields and `fields_confirmed=yes` was used to simulate the user-confirmation gate. Ambiguous and incomplete cases were not supplied to the engine. These diagnostic rows are distinct from pipeline predictions.

### Scoring definitions

- Field metrics score only domain-relevant carbon-critical fields listed in the machine result. A predicted normalized scalar must exactly match the normalized reference. A wrong scalar counts as FP and FN; no value for a present reference is FN; any scalar for a missing or ambiguous reference is FP. An ambiguous reference has no single valid scalar.
- Unit comparisons use the existing documented normalization to the activity’s calculation unit where required (for example, MWh to kWh); this changes only evaluation comparison, not pipeline output.
- Unsupported-value rate is `unsupported scalar values / all non-null carbon-critical scalar values proposed`. A value counts as supported if it matches the frozen normalized/raw value, an explicitly annotated ambiguity candidate, or same-field evidence. An ambiguous candidate can therefore be evidence-supported while still being an unsafe single-choice proposal; ambiguity metrics report that separately.
- The missing-evidence proxy is the current extractor’s activity/quantity/unit status `missing` or `unresolved`. It is not a domain-complete missing-evidence classifier.
- Ambiguity detection counts only an explicit `ambiguous` status from the extractor’s activity/quantity/unit fields.
- OCR anchor-CER/WER compares each available critical evidence snippet with the closest OCR line on its annotated page. Full-document CER/WER cannot be computed without full-page transcript references.

## 3. Environment

| Item | Measured environment |
|---|---|
| Python | 3.12.3, 64-bit |
| OS | Windows 11, build 10.0.26300 |
| CPU | Intel64 Family 6 Model 154 Stepping 4; 12 logical CPUs |
| Installed physical RAM | 15.68 GiB on the same host; measured after the OCR run |
| GPU | Not used; RapidOCR ran with ONNX Runtime CPU |
| OCR | RapidOCR 3.9.2; ONNX Runtime 1.30.0 CPU |
| PDF rendering | pypdfium2 5.13.0 |
| Image/runtime libraries | Pillow 12.3.0; NumPy 2.5.3 |
| OCR configuration | Up to 3 pages; PDF render scale 2.0; max page size 20 MP; 4 intra-op and 1 inter-op threads |
| Model assets | SHA-256 pinned and recorded in the machine result |

The run used `.venv-ocr-eval`. The default `py -3.12` interpreter does not have RapidOCR/ONNX Runtime installed, so running the app in that interpreter would show OCR unavailable. Peak process working-set memory was **not captured**; the runner’s in-process Windows peak-memory query did not return a value. Total host RAM is reported separately and is not a peak-memory estimate.

## 4. Aggregate carbon-critical field extraction

| Scope | Field records | Precision | Recall | F1 | Exact match over present references |
|---|---:|---:|---:|---:|---:|
| **Micro aggregate** | **890** | **93.28%** | **18.01%** | **30.19%** | **18.01%** |

Counts: **125 TP, 9 FP, 569 FN**. There were 694 present normalized reference values. Most false negatives are required context and material/freight fields the current extractor does not produce. All nine false-positive field values are single candidates proposed for ambiguous references.

### Per domain

| Domain | Field records | Precision | Recall | F1 | Exact match over present references |
|---|---:|---:|---:|---:|---:|
| Electricity | 120 | 89.13% | 39.42% | 54.67% | 39.42% |
| Diesel | 160 | 100.00% | 45.10% | 62.16% | 45.10% |
| LPG | 160 | 90.48% | 40.00% | 55.47% | 40.00% |
| Materials | 180 | 0.00% | 0.00% | 0.00% | 0.00% |
| Freight | 270 | 0.00% | 0.00% | 0.00% | 0.00% |

### Per field

| Field | Present references | Proposed values | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Activity description / normalized activity | 120 | 60 | 100.00% | 50.00% | 66.67% |
| Quantity | 46 | 26 | 80.77% | 45.65% | 58.33% |
| Unit, canonicalized | 74 | 37 | 100.00% | 50.00% | 66.67% |
| LPG net mass | 7 | 11 | 63.64% | 100.00% | 77.78% |
| Electricity use, electricity geography and billing period | 58 combined | 0 | 0.00% | 0.00% | 0.00% |
| Diesel geography, vehicle/source, combustion and control context | 69 combined | 0 | 0.00% | 0.00% | 0.00% |
| LPG geography, combustion/control/source and commercial context | 69 combined | 0 | 0.00% | 0.00% | 0.00% |
| Material identity, geography and purchase evidence | 70 combined | 0 | 0.00% | 0.00% | 0.00% |
| Freight geography/mode, business flow, mass/distance/units and vehicle class | 243 combined | 0 | 0.00% | 0.00% | 0.00% |

The individual context-field counts and scores are in the machine result. The current extractor recognizes activity patterns only for electricity, diesel and LPG; it has no materials/freight activity pattern and no carbon-context extraction fields. It proposed an activity for all 20 electricity, 20 diesel and 20 LPG documents, but for none of the 30 materials or 30 freight documents.

For numeric extraction, 110 unambiguous present numeric references were available. The system proposed 28 values: all **28/28** matched normalized values exactly (conditional exact accuracy 100%; MAE 0; relative error 0). Coverage over all 110 present numeric references was **25.45%**. Scalar proposals on ambiguous numeric references are scored as ambiguity behavior, not included in this numeric error denominator.

## 5. OCR

| Metric | Result |
|---|---:|
| OCR complete | 120/120 |
| Document-level OCR failures | 0 |
| Critical evidence anchors | 526 |
| Anchors with OCR text on the annotated page | 526/526 |
| Exact anchor text after case/whitespace normalization | 449/526 (85.36%) |
| Anchor-CER | 2,224 / 27,264 = **8.16%** |
| Anchor-WER | 325 / 3,872 = **8.39%** |
| Full-document CER/WER | Not measurable: no full-document transcripts in the ground truth |

These anchor metrics use the closest OCR output line on the annotated page. They are not equivalent to a complete-page OCR benchmark. OCR recognized text on every page, but 77 evidence snippets were not exact after normalization; downstream extraction misses cannot all be attributed to OCR alone.

## 6. Evidence grounding and unsupported values

| Metric | Result |
|---|---:|
| Carbon-critical scalar values proposed | 134 |
| Unsupported values | 0 |
| Unsupported-value rate | **0/134 = 0.00%** |
| Proposals carrying an evidence text line | 74/134 (55.22%) |
| Exact evidence-anchor text among proposals with an anchor | 70/74 (94.59%) |
| Page correctness / bbox IoU | Not available from the existing extractor |

The zero unsupported-value result means no proposed scalar lacked an annotated same-field value/candidate/evidence match in this pilot. It does **not** mean ambiguity handling is safe: one of the 9 unflagged ambiguous candidates can be source-supported and still be an unjustified choice between conflicts. The extractor returns no page number or bounding box for a candidate, so page-level grounding and IoU cannot be scored.

The four non-exact candidate anchor strings were in `GLP-L-015` and `GLP-L-018`; the quantity and unit candidate evidence text was shortened or OCR-corrupted relative to the annotated anchor. These are anchor-string mismatches, not missing OCR documents.

## 7. Missing-evidence detection

Using the current extractor’s generic missing/unresolved field-status signal as the proxy:

| TP | FP | FN | TN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 31 | 52 | 9 | 28 | 37.35% | 77.50% | 50.41% |

The nine incomplete documents with **no missing signal** were: `GLP-D-002`, `GLP-E-009`, `GLP-D-008`, `GLP-D-011`, `GLP-D-012`, `GLP-D-016`, `GLP-E-015`, `GLP-D-018`, `GLP-D-020`.

The 52 false-positive missing signals consist of these 21 ready documents: `GLP-M-001`, `GLP-M-002`, `GLP-M-003`, `GLP-F-002`, `GLP-F-003`, `GLP-M-008`, `GLP-F-008`, `GLP-F-009`, `GLP-F-014`, `GLP-M-015`, `GLP-D-009`, `GLP-M-016`, `GLP-F-017`, `GLP-M-018`, `GLP-F-020`, `GLP-F-023`, `GLP-M-026`, `GLP-M-028`, `GLP-M-029`, `GLP-F-028`, `GLP-E-019`; and these 31 ambiguous documents: `GLP-F-001`, `GLP-D-004`, `GLP-F-005`, `GLP-D-005`, `GLP-E-003`, `GLP-F-006`, `GLP-F-007`, `GLP-D-007`, `GLP-M-010`, `GLP-M-011`, `GLP-L-005`, `GLP-M-013`, `GLP-M-014`, `GLP-F-010`, `GLP-F-013`, `GLP-D-010`, `GLP-F-016`, `GLP-D-013`, `GLP-M-019`, `GLP-M-021`, `GLP-F-021`, `GLP-M-023`, `GLP-L-013`, `GLP-F-022`, `GLP-M-025`, `GLP-M-027`, `GLP-D-017`, `GLP-F-026`, `GLP-F-027`, `GLP-M-030`, `GLP-F-030`.

False completion rate was **0/40 (0%)**: the upload-only app emitted no result on any incomplete document. This is a conservative abstention caused by manual entry/confirmation being required, not evidence that the app correctly identified all missing evidence.

## 8. Ambiguity detection

| TP | FP | FN | TN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0 | 34 | 80 | 100.00% | 15.00% | 26.09% |

The six detected ambiguous cases were all diesel documents: `GLP-D-004`, `GLP-D-005`, `GLP-D-007`, `GLP-D-010`, `GLP-D-013`, `GLP-D-017`. The 34 misses were:

- Electricity: `GLP-E-001`, `GLP-E-002`, `GLP-E-003`, `GLP-E-010`, `GLP-E-011`, `GLP-E-017`.
- LPG: `GLP-L-002`, `GLP-L-003`, `GLP-L-005`, `GLP-L-013`, `GLP-L-015`, `GLP-L-018`.
- Materials: `GLP-M-010`, `GLP-M-011`, `GLP-M-013`, `GLP-M-014`, `GLP-M-019`, `GLP-M-021`, `GLP-M-023`, `GLP-M-025`, `GLP-M-027`, `GLP-M-030`.
- Freight: `GLP-F-001`, `GLP-F-005`, `GLP-F-006`, `GLP-F-007`, `GLP-F-010`, `GLP-F-013`, `GLP-F-016`, `GLP-F-021`, `GLP-F-022`, `GLP-F-026`, `GLP-F-027`, `GLP-F-030`.

The strict false-resolution rate at the accounting-output stage was **0/40**: none of the ambiguous uploads produced a calculation without clarification because the current upload path does not submit suggestions to accounting. However, the extractor did propose one scalar for an ambiguous critical field without setting its explicit ambiguity status in **9/40** cases: `GLP-E-001`, `GLP-E-002`, `GLP-E-010`, `GLP-E-011`, `GLP-E-017`, `GLP-L-002`, `GLP-L-003`, `GLP-L-015`, `GLP-L-018`. This is a **22.5% unflagged candidate rate** and a human-review risk; the actual later user confirmation behavior was not part of this benchmark.

## 9. Accounting-readiness classification

The current pipeline has no automatic three-way readiness classifier. It returned **UNDETERMINED** for all documents.

| True \\ Predicted | READY | INCOMPLETE | AMBIGUOUS | UNDETERMINED |
|---|---:|---:|---:|---:|
| READY | 0 | 0 | 0 | 40 |
| INCOMPLETE | 0 | 0 | 0 | 40 |
| AMBIGUOUS | 0 | 0 | 0 | 40 |

Coverage was 0/120; under abstention-as-missed-class scoring, each class precision/recall/F1 is 0 and macro-F1 is **0.00**. This reflects a missing automatic readiness component, not three wrong class assignments. The generic review flag was raised on 83/120 uploads (69.17%) and does not distinguish ready, incomplete and ambiguous states.

## 10. Deterministic accounting correctness

**Upload-only accounting:** 0/40 ready documents produced an automatic result because the app requires manual field entry and confirmation.

**Separate confirmed-ground-truth diagnostic:** on frozen annotation values for the 40 READY documents, the current engine matched the expected numeric result, factor ID, scope/category boundary, gas basis and result unit on **40/40**. Exact numeric matches were 40/40; MAE and maximum absolute error were 0 kg; mean relative error was 0.

| Domain | Gold-input ready cases | Exact result / factor / boundary |
|---|---:|---:|
| Electricity | 7 | 7/7 |
| Diesel | 7 | 7/7 |
| LPG | 7 | 7/7 |
| Materials | 10 | 10/10 |
| Freight | 9 | 9/9 |

This is not end-to-end extraction performance. The frozen expected results were originally generated by the same accounting engine, so the check demonstrates repeatable engine behavior against those annotations, not independent factor validation.

## 11. Latency and resources

| Stage | Mean / document | Median / document | Total |
|---|---:|---:|---:|
| OCR function wall time, including decode/render and first-call initialization | 5.562 s | 5.173 s | 667.441 s |
| OCR-reported inference only, excluding initialization and decode/render | 5.501 s | 5.061 s | 660.143 s |
| Downstream rule extraction | 0.00143 s | 0.00118 s | 0.172 s |
| OCR + extraction document pipeline wall time | 5.563 s | 5.174 s | 667.613 s |

Total benchmark wall time was **673.13 seconds** (about 11 min 13 sec). The slowest document pipeline call was 15.68 seconds. Full per-domain and per-evidence-state latency summaries are in the JSON result. Peak process memory was not available for this run.

## 12. Difficulty breakdown

Subgroup scores are descriptive, particularly for small groups; no ranking or generalization claim should be drawn from them.

| Group | n | Field F1 | Anchor-CER |
|---|---:|---:|---:|
| Single-page | 90 | 29.73% | 9.35% |
| Multi-page | 30 | 31.58% | 4.12% |
| PDF (born-digital + simulated scanned) | 80 | 28.99% | 6.76% |
| Standalone image | 40 | 32.61% | 10.79% |
| Born-digital PDF | 40 | 26.42% | 6.30% |
| Simulated scanned PDF | 40 | 31.36% | 7.18% |
| Standalone JPEG | 20 | 35.37% | 10.53% |
| Standalone PNG | 20 | 29.46% | 11.05% |
| READY | 40 | 33.33% | 11.11% |
| INCOMPLETE | 40 | 34.36% | 10.88% |
| AMBIGUOUS | 40 | 21.86% | 3.98% |

| Layout structure | n | Field F1 | Anchor-CER |
|---|---:|---:|---:|
| Annex | 14 | 19.57% | 5.15% |
| Floating cards | 22 | 32.21% | 13.77% |
| Ledger | 22 | 33.78% | 1.46% |
| Prose | 22 | 30.67% | 12.25% |
| Table | 22 | 33.99% | 0.52% |
| Thermal | 18 | 26.02% | 16.72% |

All 27 layout-family groups (n=4–5 each) are reported in the machine result; these tiny groups are especially unsuitable for ranking.

## 13. Per-document failures and error attribution

- **OCR:** no document-level failures. The 77 non-exact carbon evidence anchors are counted in the anchor OCR metric; complete page transcription references are unavailable.
- **Activity/field extraction:** all material IDs `GLP-M-001`–`GLP-M-030` and freight IDs `GLP-F-001`–`GLP-F-030` received no activity candidate. The current rule extractor has no materials/freight patterns. Context fields were not extracted in any domain.
- **Missing-evidence signal:** false negatives are the nine IDs listed in Section 7; false positives are the 21 READY and 31 AMBIGUOUS IDs listed there. This is the extractor’s generic field-status signal, not an explicit readiness decision.
- **Ambiguity:** false negatives are the 34 IDs in Section 8; nine of those cases also received a single scalar candidate without an ambiguity status.
- **Evidence string anchoring:** four exact anchor mismatches are two field outputs each in `GLP-L-015` and `GLP-L-018`.
- **Accounting:** no upload-only calculation was attempted. Gold-input diagnostic had no failures.

The machine result contains predictions, OCR pages/transcripts, extraction candidates, evidence strings, status/review decisions, per-field scoring, per-document accounting diagnostic, latency and failure reasons for every ID.

## 14. Limitations and conclusion

This is a synthetic-only challenge. It does not demonstrate operation on real SME documents. The existing field extractor is deliberately conservative and remains a rule baseline; no AI/VLM or newly written extraction logic was tested. OCR text lines lack output page/bounding-box coordinates for extractor candidates. There is no calibrated field confidence. The readiness and ambiguity results show the current application cannot autonomously distinguish the three evidence states. The zero unsupported-value rate must be interpreted with the nine unflagged ambiguous scalar candidates in view.

**What the current system does well:** RapidOCR returned text for all 120 documents; when the current rules emitted unambiguous activity/quantity/unit candidates, their normalized values matched the annotated values at high precision, and no proposed scalar lacked same-field source support under the stated definition. The deterministic engine reproduced all 40 ready expected outputs when supplied confirmed ground-truth values.

**Where it fails:** field recall is 18.01%; materials/freight extraction is absent; required accounting context is not extracted; the missing signal has only 50.41% F1; ambiguity recall is 15%; and automatic readiness coverage/accounting from an upload is zero.

**Failure attribution:** OCR errors are present in evidence snippets (8.16% anchor-CER), but no document failed OCR. The largest observed end-to-end gaps are extraction/schema coverage and missing evidence grounding/location. Review/readiness fails because the app requires manual field entry and has no three-way readiness classifier. The deterministic accounting diagnostic itself matched the frozen expected results, subject to its same-engine ground-truth caveat.

## 15. Artifacts and reproduction

- Frozen input: `data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/`
- Machine-readable predictions and metrics: [greenledger_unseen_structure_pilot_120_current_pipeline_2026-11-15.json](../data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_2026-11-15.json)
- Evaluation-only runner: [evaluate_unseen_structure_baseline.py](../scripts/evaluate_unseen_structure_baseline.py)
- Result SHA-256: `bbf7564625b4fc22e6c47e96998d8eb8a9ed698b1c7536a937bd6052612b960b`
- Prediction-run code SHA-256 recorded in JSON: `044c85ca4e7fe6edfad3d78740757853fa710b30e7c6e3f3ae1cb8952fbe725d`
- Metrics scorer SHA-256 recorded in JSON: `f1b71b0102b9da18734814fa8f9b379535ab6fa0313dc1d6e26dfd03bb5c04ad`

After the OCR/extraction pass, the evaluation script was extended to canonicalize unit comparisons and add subgroup metrics. The metrics-only rescore reused the saved predictions; the JSON confirms the prediction-record digest was unchanged. The OCR and extraction orchestration was not changed.

To rerun OCR/extraction and the complete baseline in the configured OCR environment:

```powershell
.venv-ocr-eval\Scripts\python.exe scripts\evaluate_unseen_structure_baseline.py
```

The metrics-only rescore mode reuses the saved per-document predictions and does not call OCR or extraction:

```powershell
.venv-ocr-eval\Scripts\python.exe scripts\evaluate_unseen_structure_baseline.py --rescore-existing
```

The evaluation JSON is ground-truth-derived and must remain evaluation-only; it is not training or tuning data. No alternative model benchmark was started, and no production OCR, extraction, accounting or UI file was modified.
