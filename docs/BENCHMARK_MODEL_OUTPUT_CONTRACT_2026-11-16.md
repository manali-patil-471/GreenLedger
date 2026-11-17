# GreenLedger benchmark model-output contract

## Purpose and boundary

The benchmark contract is a benchmark-only intermediate representation in `greenledger/benchmark/`. It standardizes document evidence emitted by future candidates. It does not change production OCR, extraction, readiness, or accounting behavior.

The JSON Schema is `data/benchmark/contracts/GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1.json`. The Python contract and validation code are in `greenledger/benchmark/contract.py`.

Each DocumentPrediction contains:

- document_id
- extracted_fields[]
- missing_evidence[]
- ambiguities[]
- accounting_readiness
- a separate review_signal
- restricted model_metadata

Each field prediction records evidence_status, candidate_state, candidate values/units/confidence/evidence, the source system's raw status, and an optional reason. Evidence references can identify text, page, and normalized page coordinates. `document_domain` is a candidate-predicted classification field (`electricity`, `diesel`, `lpg`, `materials`, or `freight`). No factor, Scope/category, gas basis, CO2/CO2e total, or accounting result property is allowed. Field names are an allowlist of observable document evidence.

## Status semantics

| Status | Meaning in a prediction |
| --- | --- |
| PRESENT | One candidate value was emitted. This does not establish that it is supported or accounting-ready. |
| MISSING | The candidate explicitly reports that no field value was found. It is a prediction, not ground truth. |
| INSUFFICIENT | Some evidence/candidate was found, but it cannot be normalized into a usable value. |
| AMBIGUOUS | The candidate explicitly reports competing interpretations. Preserve all candidates and anchors it has; an empty candidate list is allowed when the source only emits an ambiguity flag. |
| UNDETERMINED | No field decision was emitted, including when the current candidate has no implementation for the field/domain. |

candidate_state is separately NO_CANDIDATE, SINGLE_CANDIDATE, or MULTIPLE_CANDIDATES. This allows a consumer to distinguish an explicit missing claim from no output, and an explicit ambiguity flag from a scalar proposal. Confidence may be null; it must not be fabricated or treated as calibrated.

One scalar candidate is not a safety certification. Evidence grounding and deterministic GreenLedger validation must establish whether evidence is sufficient. A model's READY output is only a benchmarked evidence-readiness prediction; the contract contains no accounting action.

## Current-pipeline adapter

`greenledger/benchmark/current_pipeline_adapter.py` now accepts only the benchmark `CandidateDocumentInput` and invokes the existing OCR and extraction functions through injectable dependencies. It does not receive a path/name, original document ID, annotation, or domain label. Domain is derived only from candidate-produced activity output.

- Existing activity, quantity, unit, supplier, date, and document-type outputs are represented when present.
- Quantity and unit are preserved separately. Raw and normalized values/units remain distinct.
- An LPG quantity is mapped to net_lpg_mass only if the current extractor already normalized it in kilograms. Cylinder count is never converted into LPG mass.
- The current extractor's explicit ambiguous status remains AMBIGUOUS. Since it does not expose the alternatives, the adapter does not invent candidates.
- All domain-critical field names have a fixed contract representation. Fields the current candidate does not implement remain UNDETERMINED; explicit missing outputs from the generic extractor remain MISSING.
- The current pipeline's generic review flags are retained in review_signal. Their generic “missing” flag is not upgraded to a field-specific truth label.
- Readiness remains UNDETERMINED; no three-way readiness classifier exists in the current pipeline.
- Confidence is null and marked uncalibrated. Evidence is text-only: page and bounding-box locations are unavailable.

The adapter's prediction method has no annotation parameter. The runner gives it opaque IDs, document bytes and MIME types only; original IDs are restored after prediction generation. The evaluator loads annotations afterward and scores predictions separately. Domain classification is reported as its own evaluator metric.

## Evaluator

`greenledger/benchmark/evaluator.py` consumes contract predictions and a separately supplied annotation list. It does not produce predictions. OCR CER/WER are not included and remain a distinct evaluation layer.

It reports carbon-critical exact normalized-value precision/recall/F1, normalized-value accuracy, per-domain/per-field metrics, numeric error summaries, evidence-text correctness, page correctness, bounding-box IoU where both sides provide coordinates, unsupported-value rate, missing-evidence detection, ambiguity detection, three-way readiness with an UNDETERMINED abstention column, and per-document decisions.

False-completion rate is READY predictions on INCOMPLETE references divided by all INCOMPLETE references. False-resolution rate is READY predictions on AMBIGUOUS references divided by all AMBIGUOUS references. The evaluator separately reports unflagged single-scalar predictions on ambiguous fields, so a candidate can be audited even when it did not claim the document was ready.

Unsupported-value rate counts scalar candidates in carbon-critical fields, including raw-only candidates. For direct comparison with the prior baseline, the result also reports the prior normalized-scalar proposal count and its unsupported rate under the prior denominator.

## Saved current-pipeline baseline verification

The original v1 contract baseline artifact is preserved but is not a candidate-only benchmark result: its earlier runner passed an annotation-derived domain to the adapter. The corrected candidate-only runner verifies the frozen marker and covered file hashes, generates predictions from document bytes first, and only then deserializes annotations for evaluation. Its result is stored separately under `data/benchmark/evaluations/`; it does not modify the frozen pilot or prior result. The old quarantined test split is not read. See [the candidate-only interface and corrected baseline report](CANDIDATE_ONLY_BENCHMARK_INTERFACE_2026-11-16.md).

The result is evaluation-only and must not be used for training, fine-tuning, prompt/model tuning, or threshold selection.

## Limits

- Candidate A provides no page/bounding-box grounding and no calibrated confidence. Those metrics are unavailable rather than estimated.
- The current candidate does not extract the materials/freight critical fields.
- Its existing missing flag is a generic extractor-status proxy, so its missing detection score is not a dedicated evidence-completeness classifier result.
- It has no automatic READY/INCOMPLETE/AMBIGUOUS classifier.
- The adapter/evaluator do not run the deterministic accounting engine.
- No alternative model is integrated or benchmarked in this phase.
