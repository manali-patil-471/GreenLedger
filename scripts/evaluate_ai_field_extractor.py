"""Compare the experimental AI line-role extractor with rules on synthetic validation OCR only."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greenledger.ai_field_extraction import DEFAULT_MODEL_PATH, extract_ai_carbon_fields, load_line_model  # noqa: E402
from greenledger.field_eval import (  # noqa: E402
    _exact_text,
    _fields,
    _load_annotations,
    _number_exact,
    _parse_number,
    _score_numeric,
    _score_values,
    evaluate_rule_fields,
)
from greenledger.field_extraction import extract_carbon_fields  # noqa: E402


DEFAULT_OCR_REPORT = ROOT / "data/benchmark/evaluations/ocr/rapidocr_3_9_2_validation_2026-09-24_with_predictions.json"
DEFAULT_OUTPUT = ROOT / "data/benchmark/evaluations/fields/ai_char_ngram_line_role_v1_validation_2026-11-10.json"


def _truth(field_map, name, attr="normalized_value"):
    row = field_map.get(name, {})
    if row.get("presence_status") != "present":
        return None
    value = row.get(attr)
    if value is None:
        value = row.get("raw_text")
    return value


def _nullable_truth(field_map, name, attr):
    """Return a normalized target only when the benchmark explicitly supplies one."""
    row = field_map.get(name, {})
    if row.get("presence_status") != "present":
        return None
    return row.get(attr)


def _predictions(extraction):
    quantity = extraction.get("quantity", {})
    return {
        "supplier_name": extraction.get("supplier_name", {}).get("value"),
        "invoice_date": extraction.get("invoice_date", {}).get("value"),
        "billing_period": extraction.get("billing_period", {}).get("value"),
        "activity_description": extraction.get("activity_description", {}).get("value"),
        "quantity_raw_numeric": quantity.get("value"),
        "unit_raw_extraction": extraction.get("unit", {}).get("raw_text"),
        "unit_normalization": extraction.get("unit", {}).get("value"),
        "normalized_quantity": quantity.get("normalized_value"),
        "cylinder_net_mass": extraction.get("cylinder_net_mass", {}).get("value"),
        "vehicle_reference": extraction.get("vehicle_reference", {}).get("value"),
        "activity_normalization": extraction.get("activity", {}).get("value"),
    }


def _rule_predictions(extraction):
    quantity = extraction.get("quantity", {})
    return {
        "supplier_name": extraction.get("supplier_name", {}).get("value"),
        "invoice_date": extraction.get("invoice_date", {}).get("value"),
        "billing_period": None,
        "activity_description": extraction.get("activity", {}).get("raw_text"),
        "quantity_raw_numeric": quantity.get("value"),
        "unit_raw_extraction": extraction.get("unit", {}).get("raw_text"),
        "unit_normalization": extraction.get("unit", {}).get("value"),
        "normalized_quantity": quantity.get("normalized_value"),
        "cylinder_net_mass": None,
        "vehicle_reference": None,
        "activity_normalization": extraction.get("activity", {}).get("value"),
    }


def _build_report(ocr_report, model_path=DEFAULT_MODEL_PATH):
    dataset = ocr_report.get("dataset", {})
    if dataset.get("split") != "validation" or not dataset.get("synthetic_only"):
        raise ValueError("AI field evaluation accepts only the synthetic validation split.")
    engine_results = ocr_report.get("engine_results", [])
    if len(engine_results) != 1 or not engine_results[0].get("predictions"):
        raise ValueError("Provide one OCR report with stored validation predictions.")
    annotations = _load_annotations("validation")
    predicted_text = {row["document_id"]: row.get("transcription", "") for row in engine_results[0]["predictions"]}
    if len(annotations) != 65 or len(predicted_text) != 65 or set(annotations) != set(predicted_text):
        raise ValueError("Expected an exact ID match across all 65 validation records.")
    model = load_line_model(model_path)
    baseline_report = evaluate_rule_fields(ocr_report)

    pairs = {
        name: [] for name in (
            "supplier_name", "invoice_date", "billing_period", "activity_description",
            "quantity_raw_numeric", "unit_raw_extraction", "unit_normalization",
            "normalized_quantity", "cylinder_net_mass", "activity_normalization",
            "vehicle_reference",
        )
    }
    ai_review_labels = []
    per_document = []
    for document_id, annotation in sorted(annotations.items()):
        fields = _fields(annotation)
        transcription = predicted_text[document_id]
        ai_result = extract_ai_carbon_fields(transcription, model=model)
        rule_result = extract_carbon_fields(transcription)
        ai_values = _predictions(ai_result)
        rule_values = _rule_predictions(rule_result)
        expected = {
            "supplier_name": _truth(fields, "supplier_name"),
            "invoice_date": _truth(fields, "invoice_date"),
            "billing_period": _truth(fields, "billing_period", "raw_text"),
            "activity_description": _truth(fields, "activity_description"),
            "quantity_raw_numeric": (
                str(_parse_number(fields.get("quantity", {}).get("raw_text")))
                if fields.get("quantity", {}).get("presence_status") == "present"
                and _parse_number(fields.get("quantity", {}).get("raw_text")) is not None else None
            ),
            "unit_raw_extraction": _truth(fields, "unit", "raw_text"),
            "unit_normalization": _nullable_truth(fields, "unit", "normalized_value"),
            "normalized_quantity": (
                _nullable_truth(fields, "quantity", "normalized_value")
                if _nullable_truth(fields, "unit", "normalized_value") is not None else None
            ),
            "cylinder_net_mass": _truth(fields, "cylinder_net_mass", "raw_text"),
            "vehicle_reference": _truth(fields, "vehicle_reference", "raw_text"),
            "activity_normalization": annotation.get("ground_truth", {}).get("activity_normalization", {}).get("normalized_activity"),
        }
        for name, truth in expected.items():
            comparator = _number_exact if name in {"quantity_raw_numeric", "normalized_quantity"} else _exact_text
            pairs[name].append((truth, ai_values[name], rule_values[name], comparator))
        expected_review = any(bool(field.get("expected_review_required")) for field in fields.values())
        ai_review_labels.append((expected_review, bool(ai_result.get("review_required"))))
        per_document.append({
            "document_id": document_id,
            "ai": ai_values,
            "rules": rule_values,
            "ai_review_required": bool(ai_result.get("review_required")),
            "ai_human_confirmation_required": bool(ai_result.get("human_confirmation_required")),
            "ai_confidence": ai_result.get("confidence"),
        })

    metrics = {}
    for name, records in pairs.items():
        comparator = records[0][3] if records else _exact_text
        if name in {"unit_normalization", "normalized_quantity"}:
            # Match the deterministic baseline's eligibility rule: unnormalizable labels are not scored.
            records = [record for record in records if record[0] is not None]
        ai_pairs = [(expected, ai) for expected, ai, _rule, _cmp in records]
        rule_pairs = [(expected, rule) for expected, _ai, rule, _cmp in records]
        if name in {"quantity_raw_numeric", "normalized_quantity"}:
            ai_metric, rule_metric = _score_numeric(ai_pairs), _score_numeric(rule_pairs)
        else:
            ai_metric = _score_values(ai_pairs, comparator)
            rule_metric = _score_values(rule_pairs, comparator)
        metrics[name] = {"ai_candidate": ai_metric, "rules_baseline": rule_metric}

    review_tp = sum(expected and predicted for expected, predicted in ai_review_labels)
    review_fp = sum((not expected) and predicted for expected, predicted in ai_review_labels)
    review_fn = sum(expected and (not predicted) for expected, predicted in ai_review_labels)
    review_precision = review_tp / (review_tp + review_fp) if review_tp + review_fp else None
    review_recall = review_tp / (review_tp + review_fn) if review_tp + review_fn else None
    review_f1 = (2 * review_precision * review_recall / (review_precision + review_recall)) if review_precision is not None and review_recall is not None and review_precision + review_recall else 0.0 if review_precision is not None and review_recall is not None else None

    return {
        "status": "MEASURED_EXPLORATORY_VALIDATION",
        "dataset": {"dataset_id": dataset.get("dataset_id"), "split": "validation", "synthetic_only": True, "documents": 65},
        "ocr_engine": engine_results[0].get("engine"),
        "candidate": {"model_id": model.get("model_id"), "method": model.get("method"), "training_split": "train", "training_documents": model.get("training_documents"), "confidence_calibrated": False},
        "comparison": "AI candidate and existing rules consume the identical stored RapidOCR transcription for each validation document.",
        "validation_use_note": "The validation output was inspected once to diagnose a deterministic unit-normalization output bug; the correction was then verified against the documented conversion code and the full report was rerun. Treat these metrics as exploratory, not an untouched final estimate.",
        "metrics": metrics,
        "rules_baseline_document_type_metrics": baseline_report.get("metrics", {}).get("document_type"),
        "human_review_decision": {
            "documents": len(ai_review_labels),
            "expected_review_documents": sum(expected for expected, _predicted in ai_review_labels),
            "ai_candidate": {"true_positive": review_tp, "false_positive": review_fp, "false_negative": review_fn, "precision": review_precision, "recall": review_recall, "f1": review_f1},
            "rules_baseline": baseline_report.get("metrics", {}).get("human_review_decision"),
            "interpretation": "The AI candidate conservatively requires review for every document; this preserves human confirmation but does not provide selective or calibrated review decisions.",
        },
        "limitations": [
            "Validation contains synthetic layout-family records only; this is not real-SME validation.",
            "The line-role model predicts only schema-backed field roles. Activity normalization remains deterministic; scope/category, factor selection, and CO2e calculation are outside this model.",
            "The model has no calibrated confidence. Every AI suggestion requires human confirmation and review.",
            "Billing-period and cylinder-mass extraction are measured only where the existing validation annotations contain those labels.",
            "The original test partition remains quarantined and was not loaded.",
            "The validation set was inspected during debugging of deterministic unit post-processing, so this run is not an untouched final evaluation.",
        ],
        "ai_review_required_all_documents": all(predicted for _expected, predicted in ai_review_labels),
        "test_split_loaded": False,
        "per_document": per_document,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-report", type=Path, default=DEFAULT_OCR_REPORT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = json.loads(args.ocr_report.read_text(encoding="utf-8"))
    result = _build_report(report, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = {key: value for key, value in result.items() if key != "per_document"}
    print(json.dumps(summary, indent=2))
    print("Saved {}".format(args.output))


if __name__ == "__main__":
    main()
