# Rule-Based Field Extraction Baseline — 2026-09-24

## Status

**Measured on synthetic validation data.** This is a deterministic rules baseline operating on RapidOCR transcriptions. It is not an AI model, a trained GreenLedger model, a real-SME result, or an end-to-end carbon-accounting score.

## Evaluation setup

- 65 checksum-verified synthetic validation documents: 25 electricity, 20 diesel, 20 LPG; the OCR transcript was produced by RapidOCR 3.9.2 with the recorded model hashes in the linked input report.
- Extraction rules use field-label and activity vocabulary found in the 325-record training split. The held-out validation split was not used to create the vocabulary.
- All 65 document OCR outputs are joined by document ID to the existing annotations. The evaluator re-verifies annotation image hashes before scoring.
- Scalar text fields use case/Unicode/whitespace-normalized exact matches. Quantity values are compared numerically as decimals. Canonical units and canonical quantities are scored only where annotations contain a supported normalized unit.
- The benchmark contains 65 records in the held-out `layout_F` family. This measures transfer to that synthetic family; it does not demonstrate broad vendor or real-document generalization.

## Measured results

| Task | Eligible records | Result |
|---|---:|---:|
| Document-type classification | 65 | 65/65 correct; accuracy 1.000; all 3 classes represented |
| Activity normalization | 65 | precision 1.000, recall 1.000, F1 1.000 |
| Supplier name | 65 | precision 1.000, recall 1.000, F1 1.000 |
| Invoice date | 65 | precision 1.000, recall 1.000, F1 1.000 |
| Activity description | 65 | precision 1.000, recall 1.000, F1 1.000 |
| Raw numeric quantity | 65 | 65/65 exact numeric matches; MAE 0 |
| Raw unit text | 65 | precision 1.000, recall 1.000, F1 1.000 |
| Unit normalization | 61 | 61/61 correct; four records with unresolvable cylinder-count units are excluded from this denominator |
| Normalized quantity | 61 | 61/61 exact decimal matches; MAE 0 |
| Human-review decision | 65 | 4/4 expected cases flagged, 0 false positives; precision 1.000, recall 1.000, false-negative rate 0 |

## Safety behavior

- Missing or ambiguous units are never inferred from a fuel name.
- LPG cylinder counts are extracted as counts but are not converted to kilograms. The four validation records requiring review were all flagged.
- Only conversions already defined in the activity catalogue are applied. No factor retrieval, scope assignment, CO₂e calculation, or confidence score is produced by this extractor.
- The upload UI shows these values as unconfirmed suggestions. Applying suggestions copies them into editable form fields but leaves human confirmation unchecked.

## Limits

These perfect task scores are measured only on the controlled synthetic validation family and reflect the current synthetic vocabulary/layout patterns. The OCR transcription result is also synthetic. The app now exposes extracted/missing/ambiguous/unresolved field states, but these are evidence states rather than calibrated confidence probabilities. There are no material/transport examples in this release, no model-confidence calibration, no test-split evaluation, and no real-SME validation. Do not present these results as expected field accuracy on real invoices. **Status note (2026-11-10):** a separate supervised line-role model has since been trained and compared against this rules baseline; it remains experimental and is not integrated into the app. See `AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`.

Full per-task metrics and per-document review decisions are stored in `data/benchmark/evaluations/fields/rapidocr_rules_v1_validation_2026-09-24.json`. The OCR input report, including the explicitly requested synthetic transcriptions, is `data/benchmark/evaluations/ocr/rapidocr_3_9_2_validation_2026-09-24_with_predictions.json`.

## OCR transfer check: Florence-2 transcript

The same rule extractor was also run on a third OCR candidate's stored transcripts. Florence-2 OCR produced 47/65 document-type and activity-normalization matches (72.3%); the current line-based rules extracted no exact quantities or normalized units. Review recall was 4/4 (100%), but review precision fell to 4/65 (6.15%) because the flattened transcript led the rules to abstain on nearly every record. This is a downstream integration check, not an AI field-extraction result. It shows that the current parser depends on line boundaries preserved by the selected RapidOCR path. Full task metrics are in `data/benchmark/evaluations/fields/florence2_rules_v1_validation_2026-09-24.json`.

## Parser update — 2026-11-10

The repository audit found that layout-E OCR lines prefix numbered field labels (for example `04  Units billed: 285 kWh`), while the original anchored rules expected the field label at the start of the line. The rule extractor now removes an ordinal only when it precedes a colon-terminated label, retains the full OCR line as evidence, and can recover one unique activity-compatible unit-qualified quantity when no known label is present. It still abstains if multiple candidate quantities occur or a line looks like a rate/amount.

The original user-uploaded `285 kWh` document/transcript was not retained, so it could not be replayed. The equivalent numbered case is covered by a regression test, and the updated rule report was rerun on the same 65 RapidOCR validation records: document type, activity, supplier, date, activity description, raw numeric quantity and raw unit text remain 65/65; unit normalization and normalized quantity remain 61/61; expected review cases remain 4/4 flagged. See `data/benchmark/evaluations/fields/rapidocr_rules_v2_validation_2026-11-10.json`.

As a parser sanity check only, running the updated rule extractor on the 325 training reference OCR transcripts yielded 325/325 for the present activity, supplier, date, activity-description, and numeric quantity labels, and 293/293 among the training records with supported normalized units/quantities. This is an in-sample reference-text check, not a held-out performance result. The broader limitation remains: extraction depends on meaningful OCR line segmentation; the Florence flattened-text experiment lost line boundaries and produced no exact quantity/unit outputs.

The earlier report of 19 electricity quantity misses and two LPG “cooking gas refill” parsing gaps cannot be mapped back to their exact input rows because those original parser diagnostics were not preserved. On the current files/code, there are zero missing quantities among 125 training-reference and 25 validation-OCR electricity records, and zero among 100 training-reference and 20 validation-OCR LPG records. Every current transcript line containing “cooking gas refill” maps to LPG (19 training references and 6 validation OCR transcripts). These are equivalent-case rechecks, not proof that the exact earlier two rows were replayed.
