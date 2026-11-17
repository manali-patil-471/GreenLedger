# AI-Assisted Carbon-Field Extraction Candidate — 2026-11-10

## Status

**Experimental candidate trained and measured; not selected as the final model and not integrated into the application.** This is a supervised character n-gram line-role classifier, not RapidOCR, a VLM, or a fine-tuned general document model. Activity normalization, unit rules, and date parsing remain deterministic post-processing. The model cannot assign a GHG scope/category, retrieve a factor, calculate CO₂e, or return calibrated confidence.

## Labels and split use

The annotation schema includes the following field names in the current synthetic train/validation records: `supplier_name`, `customer_name`, `invoice_number`, `invoice_date`, `billing_period`, `account_number`, `meter_id`, `activity_description`, `quantity`, `unit`, `total_amount`, `currency`, `vehicle_reference`, and `cylinder_net_mass`. The extractor candidate uses only schema-backed, evidence-located carbon-relevant labels: supplier, invoice date, billing period, activity description, quantity, unit, vehicle reference, and cylinder net mass. It does not train on customer, account/invoice identifiers, totals, currency, or ungrounded scenario context.

Present field-label support in the existing annotations is:

| Field label | Train present | Validation present | Used by candidate |
|---|---:|---:|---|
| `supplier_name` | 325 | 65 | Yes |
| `customer_name` | 325 | 65 | No |
| `invoice_number` | 312 | 62 | No |
| `invoice_date` | 325 | 65 | Yes |
| `billing_period` | 125 | 25 | Yes |
| `account_number` | 125 | 25 | No |
| `meter_id` | 115 | 23 | No |
| `activity_description` | 325 | 65 | Yes |
| `quantity` | 325 | 65 | Yes |
| `unit` | 313 | 65 | Yes |
| `total_amount` | 325 | 65 | No |
| `currency` | 325 | 65 | No |
| `vehicle_reference` | 86 | 17 | Yes |
| `cylinder_net_mass` | 80 | 16 | Yes |

These counts are present labels, not necessarily all normalized or calculable values. The benchmark also contains explicit not-present field annotations. There are no observed labels for material or transport documents in the current release.

| Split | Documents | Activity counts | Role in this experiment |
|---|---:|---|---|
| Train | 325 | Electricity 125; diesel 100; LPG 100 | Model fitting only |
| Validation | 65 | Electricity 25; diesel 20; LPG 20 | One held-out comparison against rules |
| Original test | 130 | Electricity 50; diesel 40; LPG 40 | Quarantined after prior annotation exposure; not loaded or evaluated |

The model training loader routes JSONL by its split marker before deserializing a record. Only `train` rows are read for training; validation records are used only by the comparison script. Test labels are not parsed by either loader. The whole original test partition remains quarantined; see [the quarantine record](TEST_SPLIT_QUARANTINE_2026-11-10.md).

The available `ghg_classification.context_fields` are scenario labels rather than evidence-located field annotations: electricity records mark account ownership and site consumption as true, while fuel records leave `fuel_consumed` and `operational_control` null and mark only `purchase_visible` true. These are not trained or inferred as document fields.

## Method and run record

- Training input is each record's annotated reference OCR transcription, paired with existing `fields[].evidence_text` labels. The comparison input is RapidOCR 3.9.2 output for validation. This trains on clean reference text and evaluates transfer to OCR output; it does not train the model on OCR-engine errors. The annotation is matched to the exact reference OCR line after safe line-ordinal normalization. An alignment failure stops training.
- Classifier: supervised hashed character n-gram (2–5) linear classifier, fitted with PyTorch CPU; fixed seed `20261110`, 40 epochs, no validation-based tuning.
- Training used 325 documents, 5,706 lines, and 1,904 positive field lines. No test records were loaded. Training loss is recorded for reproducibility only; it is not a benchmark metric.
- Evaluation reuses the same stored RapidOCR 3.9.2 transcripts and the same 65 validation IDs for both the AI candidate and the rule baseline.
- Raw text parsing, date normalization, activity mapping, and unit/quantity conversions use existing deterministic GreenLedger code. All model suggestions require human confirmation. Confidence is `null`.

Reproduce from a Python environment with the pinned CPU PyTorch dependencies in `requirements-field-model-eval.lock.txt`:

```powershell
.\.venv-field-eval\Scripts\python.exe scripts/train_ai_field_extractor.py
.\.venv-field-eval\Scripts\python.exe scripts/evaluate_ai_field_extractor.py
```

The training command writes `models/ai_field_extraction/char_ngram_line_role_v1.json`; the evaluation writes `data/benchmark/evaluations/fields/ai_char_ngram_line_role_v1_validation_2026-11-10.json`.

## Measured validation comparison

Exact field values are scored after the existing documented normalization. F1 counts wrong predicted values as both a false positive and a false negative. Normalized-unit and normalized-quantity metrics use the 61 rows with an explicitly supported normalized unit; the four cylinder-count cases are not treated as canonical mass conversions.

| Field/task | Eligible / support | AI candidate | Rules baseline |
|---|---:|---:|---:|
| Supplier name | 65 | P/R/F1 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Invoice date | 65 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Billing period | 25 present of 65 | 1.000 / 1.000 / 1.000 | Recall 0/25; no rule output |
| Activity description | 65 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Raw numeric quantity | 65 | exact 65/65; MAE 0 | exact 65/65; MAE 0 |
| Raw unit text | 65 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Unit normalization | 61 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Normalized quantity | 61 | exact 61/61; MAE 0 | exact 61/61; MAE 0 |
| Cylinder net mass | 16 present of 65 | 1.000 / 1.000 / 1.000 | No rule output |
| Vehicle reference | 17 present of 65 | 1.000 / 1.000 / 1.000 | No rule output |
| Activity normalization | 65 | 1.000 / 1.000 / 1.000 (deterministic mapping) | 1.000 / 1.000 / 1.000 |
| Human-review decision | 4 records require review | Recall 1.000; precision 0.062; F1 0.116 | Precision/recall/F1 1.000 / 1.000 / 1.000 |

The rules baseline classified document type correctly on 65/65 validation records. Both extractors' perfect field scores are confined to this controlled synthetic layout-family slice. The model adds billing-period, cylinder-mass, and vehicle-reference line extraction versus the current rules evaluator, but it does not improve the already-perfect measured supplier/date/activity/quantity/unit scores. Its review precision is low because it conservatively flags every validation record for review (4 true review cases and 61 unnecessary review flags); it has no selective review policy. This is not evidence of real-invoice performance or superiority across layouts.

**Validation-use caveat:** During the first candidate run, the validation output exposed a deterministic bug where the candidate returned a recognized input unit (such as MWh) instead of the activity's canonical output unit (kWh). The normalization output was corrected to use the existing deterministic conversion function and checked against its documented rules; the final comparison was rerun. Because validation output was inspected during this debugging step, treat these numbers as exploratory, not as an untouched final estimate. The model weights and training split were not tuned with validation labels. A fresh independent evaluation set is required before making a final model-selection claim.

## Remaining work and limits

- The model is experimental and is not connected to upload/preview or accounting endpoints. The application continues to show OCR plus rule suggestions only.
- No numeric confidence calibration or separate confidence labels exist. Review is required for every AI output; calibrated uncertainty and safe automation are unimplemented.
- No independent replacement holdout exists; the original test split is quarantined. A new blinded evaluation should be created only after model and parser choices are frozen.
- The result covers synthetic electricity/diesel/LPG only. Materials, transport, real SME documents, scope/category decisions, factor retrieval, and CO₂e are not evaluated by this model.
- The model sees OCR line strings without token boxes or page geometry. It may fail when an OCR engine flattens line breaks; the earlier Florence-2 transcript transfer check demonstrates this risk for the rule baseline.
- No emission factors or calculation code were changed for this milestone.
