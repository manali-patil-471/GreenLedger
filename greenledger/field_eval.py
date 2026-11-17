"""Evaluation helpers for a deterministic rule-only carbon-field baseline."""

import hashlib
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from greenledger.field_extraction import extract_carbon_fields, _parse_number
from greenledger.ocr_eval import ROOT, iter_jsonl_split_records


DATASET_DIR = ROOT / "data" / "synthetic" / "greenledger_v0_1_1_partial"
ANNOTATIONS_PATH = DATASET_DIR / "annotations.jsonl"


def _normalized_text(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(value.split())


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _fields(record):
    return {field["field_name"]: field for field in record.get("ground_truth", {}).get("fields", [])}


def _score_values(pairs, comparator):
    true_positive = false_positive = false_negative = 0
    correct = []
    for expected, predicted in pairs:
        expected_present = expected is not None and expected != ""
        predicted_present = predicted is not None and predicted != ""
        match = expected_present and predicted_present and comparator(expected, predicted)
        if match:
            true_positive += 1
            correct.append((expected, predicted))
        else:
            if predicted_present:
                false_positive += 1
            if expected_present:
                false_negative += 1
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else 0.0 if precision is not None and recall is not None else None
    return {
        "support": len(pairs),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match_rate": true_positive / len(pairs) if pairs else None,
    }


def _exact_text(expected, predicted):
    return _normalized_text(expected) == _normalized_text(predicted)


def _number_exact(expected, predicted):
    left, right = _decimal(expected), _decimal(predicted)
    return left is not None and right is not None and left == right


def _score_numeric(pairs):
    result = _score_values(pairs, _number_exact)
    errors = []
    relative_errors = []
    for expected, predicted in pairs:
        left, right = _decimal(expected), _decimal(predicted)
        if left is not None and right is not None:
            errors.append(abs(left - right))
            if left != 0:
                relative_errors.append(abs(left - right) / abs(left))
    result["mae"] = float(sum(errors) / len(errors)) if errors else None
    result["numeric_pairs_compared"] = len(errors)
    result["mean_relative_error"] = float(sum(relative_errors) / len(relative_errors)) if relative_errors else None
    return result


def _load_annotations(split):
    if split == "test":
        raise ValueError("The v0.1.1 test split is quarantined after annotation exposure and cannot be evaluated.")
    if split not in {"train", "validation"}:
        raise ValueError("Only the training and validation splits may be loaded for current development.")
    root = DATASET_DIR.resolve()
    records = {}
    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as source:
        # Route by split before parsing so quarantined/out-of-split labels are not loaded.
        for line_number, row in iter_jsonl_split_records(source, split):
            if row.get("source_type") != "synthetic":
                continue
            relative = Path(row["source_document"]["path_or_id"])
            image_path = (DATASET_DIR / relative).resolve()
            try:
                image_path.relative_to(root)
            except ValueError as error:
                raise ValueError("Annotation line {} points outside the synthetic release.".format(line_number)) from error
            expected_hash = row.get("source_document", {}).get("sha256")
            if expected_hash:
                actual_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
                if actual_hash.casefold() != expected_hash.casefold():
                    raise ValueError("Synthetic document checksum mismatch for {}.".format(row.get("document_id")))
            records[row["document_id"]] = row
    return records


def evaluate_rule_fields(ocr_report):
    dataset = ocr_report.get("dataset", {})
    if not dataset.get("synthetic_only"):
        raise ValueError("This rule baseline is configured only for explicitly synthetic GreenLedger records.")
    split = dataset.get("split")
    annotations = _load_annotations(split)
    engine_results = ocr_report.get("engine_results", [])
    if len(engine_results) != 1:
        raise ValueError("Provide one OCR engine result per rule-extraction evaluation.")
    engine_result = engine_results[0]
    predictions = engine_result.get("predictions")
    if predictions is None:
        raise ValueError("OCR report does not store transcriptions. Re-run with --store-predictions.")
    predicted_text = {row["document_id"]: row.get("transcription", "") for row in predictions}
    if set(predicted_text) != set(annotations):
        raise ValueError("OCR prediction IDs do not match the selected annotated split.")

    doc_type_pairs = []
    activity_pairs = []
    supplier_pairs = []
    date_pairs = []
    activity_text_pairs = []
    quantity_pairs = []
    unit_raw_pairs = []
    canonical_unit_pairs = []
    normalized_quantity_pairs = []
    review_labels = []
    per_document = []
    unresolved_units = 0
    eligible_unit_documents = 0

    for document_id, annotation in sorted(annotations.items()):
        extraction = extract_carbon_fields(predicted_text[document_id])
        fields = _fields(annotation)
        activity_truth = annotation.get("ground_truth", {}).get("activity_normalization", {}).get("normalized_activity")
        quantity_truth = fields.get("quantity", {})
        unit_truth = fields.get("unit", {})
        supplier_truth = fields.get("supplier_name", {})
        date_truth = fields.get("invoice_date", {})
        activity_text_truth = fields.get("activity_description", {})

        doc_type_pairs.append((annotation.get("document_type"), extraction.get("document_type")))
        activity_pairs.append((activity_truth, extraction.get("activity", {}).get("value")))
        supplier_pairs.append((supplier_truth.get("normalized_value"), extraction.get("supplier_name", {}).get("value")))
        date_pairs.append((date_truth.get("normalized_value"), extraction.get("invoice_date", {}).get("value")))
        activity_text_pairs.append((activity_text_truth.get("normalized_value"), extraction.get("activity", {}).get("raw_text")))

        expected_raw_quantity = _parse_number(quantity_truth.get("raw_text")) if quantity_truth.get("presence_status") == "present" else None
        predicted_quantity = extraction.get("quantity", {}).get("value")
        quantity_pairs.append((str(expected_raw_quantity) if expected_raw_quantity is not None else None, predicted_quantity))

        expected_raw_unit = unit_truth.get("raw_text") if unit_truth.get("presence_status") == "present" else None
        predicted_raw_unit = extraction.get("unit", {}).get("raw_text")
        unit_raw_pairs.append((expected_raw_unit, predicted_raw_unit))

        expected_unit = unit_truth.get("normalized_value")
        if expected_unit is not None:
            eligible_unit_documents += 1
            canonical_unit_pairs.append((expected_unit, extraction.get("unit", {}).get("value")))
            expected_normalized_quantity = quantity_truth.get("normalized_value")
            normalized_quantity_pairs.append((expected_normalized_quantity, extraction.get("quantity", {}).get("normalized_value")))
        elif unit_truth.get("presence_status") == "present":
            unresolved_units += 1

        expected_review = any(bool(field.get("expected_review_required")) for field in fields.values())
        review_labels.append((expected_review, bool(extraction.get("review_required"))))
        per_document.append({
            "document_id": document_id,
            "expected_review": expected_review,
            "predicted_review": bool(extraction.get("review_required")),
            "review_reasons": extraction.get("review_reasons", []),
            "field_states": {
                field_name: extraction.get(field_name, {}).get("status")
                for field_name in ("activity", "supplier_name", "invoice_date", "quantity", "unit")
            },
            "confidence": extraction.get("confidence"),
            "confidence_note": extraction.get("confidence_note"),
            "quantity": extraction.get("quantity"),
            "unit": extraction.get("unit"),
        })

    doc_types = sorted({expected for expected, _predicted in doc_type_pairs if expected is not None})
    confusion = {expected: {predicted: 0 for predicted in doc_types} for expected in doc_types}
    for expected, predicted in doc_type_pairs:
        if expected in confusion and predicted in confusion[expected]:
            confusion[expected][predicted] += 1
        elif expected in confusion and predicted is not None:
            confusion[expected]["OTHER"] = confusion[expected].get("OTHER", 0) + 1
    doc_accuracy = sum(expected == predicted for expected, predicted in doc_type_pairs) / len(doc_type_pairs) if doc_type_pairs else None
    review_tp = sum(expected and predicted for expected, predicted in review_labels)
    review_fp = sum((not expected) and predicted for expected, predicted in review_labels)
    review_fn = sum(expected and (not predicted) for expected, predicted in review_labels)
    review_recall = review_tp / (review_tp + review_fn) if review_tp + review_fn else None
    review_precision = review_tp / (review_tp + review_fp) if review_tp + review_fp else None

    return {
        "status": "MEASURED",
        "dataset": {"dataset_id": dataset.get("dataset_id"), "split": split, "synthetic_only": True, "documents": len(annotations)},
        "ocr_engine": engine_result.get("engine"),
        "extractor": "greenledger_conservative_rules_v1",
        "limitations": [
            "Rules were authored from the training annotation vocabulary and are scored only on OCR output for the held-out synthetic validation family.",
            "The measured fields are document type, activity, supplier, invoice date, quantity, and unit; no factor, scope, CO2e, or model-confidence output is produced by this extractor.",
            "Unit normalization and normalized-quantity scores exclude records whose verified annotations have no normalized unit; their abstention/review behavior is scored separately.",
            "Review labels are synthetic annotation labels, not human-review outcomes on real SME documents.",
        ],
        "metrics": {
            "document_type": {"accuracy": doc_accuracy, "documents": len(doc_type_pairs), "confusion_matrix": confusion},
            "activity_normalization": _score_values(activity_pairs, _exact_text),
            "supplier_name": _score_values(supplier_pairs, _exact_text),
            "invoice_date": _score_values(date_pairs, _exact_text),
            "activity_description": _score_values(activity_text_pairs, _exact_text),
            "quantity_raw_numeric": _score_numeric(quantity_pairs),
            "unit_raw_extraction": _score_values(unit_raw_pairs, _exact_text),
            "unit_normalization": {
                **_score_values(canonical_unit_pairs, _exact_text),
                "eligible_documents": eligible_unit_documents,
                "present_but_unresolved_documents": unresolved_units,
            },
            "normalized_quantity": _score_numeric(normalized_quantity_pairs),
            "human_review_decision": {
                "documents": len(review_labels),
                "expected_review_documents": sum(expected for expected, _predicted in review_labels),
                "true_positive": review_tp,
                "false_positive": review_fp,
                "false_negative": review_fn,
                "precision": review_precision,
                "recall": review_recall,
                "false_negative_rate": review_fn / (review_tp + review_fn) if review_tp + review_fn else None,
            },
        },
        "per_document": per_document,
    }
