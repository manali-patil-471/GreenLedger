# GreenLedger Experiment Plan

This plan defines experiments for the frozen GreenLedger v1 activities: purchased electricity, diesel, LPG, a still-to-be-selected narrow purchased-material subset, and a still-to-be-selected narrow transport/freight subset. It separates measured results from planned experiments. No final model is selected. One supervised field-extraction candidate has now been trained and measured; see the dated report.

## 1. Capability tasks

Evaluate the following capabilities separately. Each record must declare applicability in `task_coverage`; records without the relevant ground truth are excluded from that task.

1. **Document-type classification:** v1 classes for GreenLedger documents; generic invoice/receipt labels may be evaluated separately on public data.
2. **OCR/text extraction:** transcribed text, words, and regions where the reference annotations support them.
3. **Carbon-relevant field extraction:** supplier, date/period, activity description, quantity, unit, and relevant context fields with evidence text or bounding boxes where available.
4. **Activity normalization:** map supported wording such as HSD / high-speed diesel to an approved canonical activity; retain ambiguous and out-of-scope states.
5. **Unit normalization:** parse locale-aware numbers and units, apply only documented conversions, and compare both canonical unit and normalized value.
6. **GHG scope classification:** require relevant organization-boundary and activity context. A receipt by itself does not prove fuel combustion or scope.
7. **Scope 3 category classification:** evaluate only approved and applicable categories with sufficient business-flow context.
8. **Emission-factor retrieval:** match activity, factor basis/unit, geography, applicable year, and category/method against the verified catalogue. Return an explicit unresolved status when no eligible factor exists.
9. **CO2e calculation:** deterministic normalized activity multiplied by an eligible verified CO2e factor, with a complete trace. LPG and India road/mobile TTW diesel now have narrow conditional factors, but current synthetic records have no expected CO2e labels, so no GreenLedger CO2e cases are scoreable yet.
10. **Confidence/uncertainty:** evaluate the stated event (such as field correctness) and whether confidence separates reliable from unreliable predictions.
11. **Human-review decision:** flag missing units, ambiguous quantities, uncertain OCR, missing context, and unavailable verified factors when the task requires human action.

Exact-text equality is not the only matching rule. Apply the task-specific rules and metric definitions in `docs/GREENLEDGER_BENCHMARK_PLAN.md`; normalize representations before comparing quantities and units.

## 2. Model-selection experiment

Do not name a final model before a controlled comparison. The partial synthetic benchmark provides 325 train records, 65 validation records, and a nominal 130-record test partition (50 electricity, 40 diesel, 40 LPG). The original test partition is quarantined following annotation exposure; it is unavailable for development or final evaluation. Use training families for development and validation for candidate/threshold selection. These records are synthetic, not real SME annotations. Release v0.1.1 has no numeric CO2e targets and its LPG examples omit required combustion/boundary context. Compare document understanding, normalization, factor-status and review behavior only until applicable CO2e labels are annotated. See `TEST_SPLIT_QUARANTINE_2026-11-10.md`.

Candidate families to compare when their local availability, license, and hardware requirements are established:

- **OCR:** a conventional OCR engine; an OCR/layout-capable document model; and OCR supplied by a vision-language model where available.
- **Layout/document understanding:** OCR tokens with geometric features and rules; a pretrained document-layout model; and an image-to-structured-output VLM/LLM.
- **Field extraction:** rules/regular expressions over OCR; a pretrained document information extraction model; and prompted structured extraction using a VLM/LLM.
- **Activity classification and normalization:** deterministic aliases/rules; a compact text classifier if training labels justify it; and model-assisted normalization constrained to the approved taxonomy.

### Initial OCR shortlist (not a model selection)

- **Tesseract 5.5.2:** conventional local OCR baseline using its LSTM engine; Apache-2.0. This Windows validation run used the `tesserocr` wrapper and a pinned English model; provenance is recorded with the result ([project](https://github.com/tesseract-ocr/tesseract), [installation documentation](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md)).
- **RapidOCR 3.9.2 + ONNX Runtime CPU:** local text detection and recognition with bundled small models; Apache-2.0 for the implementation and model artifacts ([release](https://pypi.org/project/rapidocr/3.9.2/), [official installation guide](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/), [model/license notes](https://github.com/RapidAI/RapidOCR)).
- **Florence-2-base-ft:** pretrained prompted OCR candidate, MIT-licensed, evaluated locally with its documented OCR task; it was not selected because its measured OCR error and latency were worse than both existing engines on the current validation family ([pinned model card](https://huggingface.co/microsoft/Florence-2-base-ft/tree/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e)). This OCR test does not evaluate carbon-field extraction.
- **PaddleOCR:** another CPU-capable document OCR/layout candidate; defer installation until the two smaller baselines run, since its optional capability/dependency footprint is broader ([official quick start](https://www.paddleocr.ai/main/en/quick_start.html)).

Runtime check on 2026-09-24: the `py -3.12` interpreter is Python 3.12.3 (bare `python` is 3.6.8), the host reports 15.7 GB RAM, and no GPU was visible. OCR dependencies are installed only in `.venv-ocr-eval`. The measured comparison is documented in `docs/OCR_CANDIDATE_COMPARISON_2026-09-24.md`; RapidOCR currently has lower transcription error on this synthetic validation slice, with substantially higher latency. The result is provisional because the validation split has one layout family and no real SME documents.

Run the evaluator after installing approved candidate engines:

```powershell
.\.venv-ocr-eval\Scripts\python.exe scripts/evaluate_ocr.py --engine all --split validation
```

The harness checksum-verifies annotated images and can use training or validation records. It reports normalized CER/WER, exact transcription rate, layout/document/quality breakdowns, latency, engine version/configuration, and deterministic document-bootstrap intervals. It refuses the quarantined test split. RapidOCR, Tesseract, and Florence-2 were each measured on all 65 validation documents; see the comparison report.

Record model/version/checkpoint, prompt and decoding settings, preprocessing, software dependencies, hardware, inference settings, license/source, random seeds where relevant, and any external service configuration. Measure:

- OCR CER/WER and field-level precision/recall/F1;
- exact and numeric quantity match, absolute/relative error, and unit-normalization accuracy;
- robustness by held-out vendor/layout, wording, image quality, and ambiguity group;
- scope/category metrics only on records with applicable, verified context labels;
- inference latency, peak memory, throughput, and hardware/GPU requirements;
- local deployment effort, reproducibility, and license suitability;
- uncertainty calibration and review precision/recall, including the unsafe false-negative rate.

Report measured values with sample counts and uncertainty intervals where appropriate. Do not infer that one approach is best from model popularity, a single aggregate metric, or results on FATURA/CORD alone.

## 3. System versions and baselines

- **Baseline:** pretrained OCR or document model plus a frozen prompt/rules/post-processing setup. This is an experiment, not a trained GreenLedger model.
- **Proposed system:** AI-assisted extraction and normalization with constrained taxonomy, deterministic scope rules, verified factor retrieval, deterministic calculations, and a review path. Factor lookup and calculation never delegate values to a language model.
- **Future fine-tuned model:** only after a sufficiently sized, licensed, annotated GreenLedger dataset exists and a reproducible training/evaluation split is approved. Do not claim fine-tuning before a recorded training run.

Run baselines on the same held-out examples and report their differences task by task. Keep public generic document results separate from GreenLedger carbon-specific results.

## 4. Data roles and leakage controls

- **FATURA:** generic invoice/document understanding only; use locally available data and annotations.
- **CORD:** use the existing local sample only where its content and annotations support the task. Do not fetch the full multi-gigabyte dataset without a demonstrated need.
- **SROIE:** excluded until dataset access and terms are explicitly approved.
- **Synthetic GreenLedger data:** controlled task development and evaluation, not real-world validation. Split by vendor/layout family and generation family before tuning.
- **Real SME documents:** external validation only after consent, anonymization, provenance capture, and independent annotation. Never fabricate them or mix them into synthetic counts.

## 5. Metrics and reporting

Use the task-specific metrics and comparison methods in `docs/GREENLEDGER_BENCHMARK_PLAN.md`. Every result must show its task, split, sample count, excluded/unscorable count, and whether the reference data are public, synthetic, or real. Report classification accuracy, macro-F1, and confusion matrices; field precision/recall/F1; numeric errors only where defined; factor retrieval only over eligible verified candidates; and CO2e error only over verified calculable references. Review performance must include recall on cases that should not be silently auto-accepted.

Do not report random or hypothetical accuracies, benchmark numbers from an unrun experiment, or a universal quality claim based on one document family.

## Status

- **DONE:** Experiment dimensions, baseline/proposed/future distinctions, candidate families, comparison criteria, and leakage controls are specified.
- **DONE:** OCR transcription evaluator, validation-only default, test-split guard, checksum verification, CER/WER, grouped metrics, latency fields, and bootstrap interval calculation are implemented.
- **DONE:** Three-candidate OCR transcription comparison on all 65 held-out synthetic validation records; RapidOCR remains the provisional OCR baseline based on measured CER/WER, with Tesseract and Florence-2 retained as measured alternatives.
- **QUARANTINED:** Existing 130-record test partition following annotation exposure; no test metric was computed, and future evaluation scripts reject it.
- **DONE:** Optional local image/PDF OCR preview and trace integration; the transcript is advisory and carbon fields remain manually entered and confirmed.
- **DONE:** Conservative rule-only field-extraction baseline measured on the same 65 synthetic validation records. See `docs/RULE_FIELD_EXTRACTION_BASELINE_2026-09-24.md`; no AI model was trained.
- **DONE:** Experimental supervised character n-gram line-role extractor trained on 325 training records and compared with rules on the same 65 RapidOCR validation transcripts. Results are limited to synthetic layout-family data; see `docs/AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`.
- **QUARANTINED:** Original 130-record test split due prior annotation exposure. Do not evaluate it; a replacement independent holdout is required after candidate decisions are frozen.
- **NOT YET STARTED:** Final model selection, production/app integration, confidence calibration, comparative study against document-layout/VLM approaches, and real-SME evaluation.
- **DONE (limited):** A GreenLedger-specific supervised line-role candidate was trained; no general document model was fine-tuned.
- **BLOCKED:** CO2e experiments until the factor catalogue contains verified CO2e factors and required conversions.
- **BLOCKED:** Material and transport experiments until the exact v1 subsets and accounting boundary rules are finalized.
