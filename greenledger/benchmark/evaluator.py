"""Reusable evaluator for evidence-only document predictions.

OCR string error metrics are intentionally excluded. This module scores the
contract against already-authored benchmark annotations and never creates model
predictions from ground truth.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import statistics
import unicodedata
from typing import Any

from .contract import DocumentPrediction, validate_prediction


CRITICAL_FIELDS: dict[str, tuple[str, ...]] = {
    "electricity": ("activity_description", "quantity", "unit", "electricity_use", "geography", "billing_period"),
    "diesel": ("activity_description", "quantity", "unit", "geography", "vehicle_reference", "source_type", "combustion_status", "operational_control"),
    "lpg": ("activity_description", "net_lpg_mass", "unit", "geography", "combustion_status", "operational_control", "source_type", "commercial_institutional"),
    "materials": ("activity_description", "material_identity", "quantity", "unit", "geography", "purchase_evidence"),
    "freight": ("activity_description", "geography", "transport_mode", "transport_scenario", "shipment_mass", "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class"),
}
READINESS_LABELS = ("READY", "INCOMPLETE", "AMBIGUOUS")
DOCUMENT_DOMAINS = ("electricity", "diesel", "lpg", "materials", "freight")


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value).replace(",", "").strip())
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    number = _decimal(value)
    if number is not None:
        return format(number.normalize(), "f")
    return " ".join(str(value).casefold().split())


def _norm_text(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _metrics(counts: dict[str, int]) -> dict[str, Any]:
    tp, fp, fn = counts.get("tp", 0), counts.get("fp", 0), counts.get("fn", 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": precision, "recall": recall, "f1": f1,
    }


def _binary_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, Any]:
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum((not a) and p for a, p in zip(actual, predicted))
    fn = sum(a and (not p) for a, p in zip(actual, predicted))
    tn = sum((not a) and (not p) for a, p in zip(actual, predicted))
    return {**_metrics({"tp": tp, "fp": fp, "fn": fn}), "true_negative": tn}


def _canonical_expected(annotation: dict[str, Any], field_name: str, field: dict[str, Any]) -> Any:
    if field_name != "unit":
        return field.get("normalized_value")
    raw_unit = field.get("raw_unit") or field.get("raw_value")
    if not raw_unit:
        return field.get("normalized_value")
    try:
        # Reuse documented deterministic unit normalization for comparable
        # normalized-unit scoring. This does not feed predictions or accounting.
        from greenledger.core import normalize_activity, normalize_quantity, normalize_unit
        activity = normalize_activity(annotation["activity_id"])
        unit = normalize_unit(activity, raw_unit)
        _quantity, canonical_unit, _trace = normalize_quantity(activity, Decimal("1"), unit)
        return canonical_unit or field.get("normalized_value")
    except Exception:
        return field.get("normalized_value")


def _bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    result = {key: value.get(key) for key in ("x", "y", "width", "height")}
    if any(not isinstance(number, (int, float)) or isinstance(number, bool) for number in result.values()):
        return None
    return result


def bbox_iou(first: dict[str, float], second: dict[str, float]) -> float:
    """IoU for normalized x/y/width/height boxes."""
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_first = first["width"] * first["height"]
    area_second = second["width"] * second["height"]
    union = area_first + area_second - intersection
    return intersection / union if union else 0.0


def _prediction_fields(prediction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["field_name"]: row for row in prediction.get("extracted_fields", [])}


def _predicted_document_domain(prediction: dict[str, Any]) -> str | None:
    field = _prediction_fields(prediction).get("document_domain")
    if not field or field.get("evidence_status") == "AMBIGUOUS":
        return None
    candidate = _selected_candidate(field)
    value = candidate.get("normalized_value") if candidate else None
    return value if value in DOCUMENT_DOMAINS else None


def _selected_candidate(field_prediction: dict[str, Any] | None) -> dict[str, Any] | None:
    if not field_prediction:
        return None
    candidates = field_prediction.get("candidates") or []
    # Multiple candidates and explicitly ambiguous fields are not silently
    # collapsed to one scalar.
    if field_prediction.get("evidence_status") == "AMBIGUOUS" or len(candidates) != 1:
        return None
    return candidates[0]


def _gold_evidence(field: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((field or {}).get("evidence") or [])


def _candidate_is_supported(
    value: Any,
    gold: dict[str, Any] | None,
    annotation: dict[str, Any],
    field_name: str,
) -> bool:
    if not gold or value is None:
        return False
    comparable: list[Any] = []
    if gold.get("normalized_value") is not None:
        comparable.append(gold["normalized_value"])
    if gold.get("raw_value") is not None:
        comparable.append(gold["raw_value"])
    for candidate in gold.get("candidates") or []:
        if candidate.get("raw_value") is not None:
            comparable.append(candidate["raw_value"])
            if candidate.get("raw_unit"):
                try:
                    from greenledger.core import normalize_activity, normalize_quantity, normalize_unit
                    activity = normalize_activity(annotation["activity_id"])
                    unit = normalize_unit(activity, candidate["raw_unit"])
                    normalized, _canonical_unit, _trace = normalize_quantity(
                        activity, Decimal(str(candidate["raw_value"])), unit
                    )
                    if normalized is not None:
                        comparable.append(str(normalized))
                except Exception:
                    pass
    if field_name == "unit":
        canonical = _canonical_expected(annotation, field_name, gold)
        if canonical is not None:
            comparable.append(canonical)
    if any(_norm(value) == _norm(item) for item in comparable):
        return True
    text = " ".join(item.get("text", "") for item in _gold_evidence(gold)).casefold()
    return bool(str(value).casefold().strip() and str(value).casefold().strip() in text)


def _candidate_scalar(candidate: dict[str, Any]) -> Any:
    if candidate.get("normalized_value") is not None:
        return candidate["normalized_value"]
    return candidate.get("raw_value")


def _reference_anchor_match(evidence_text: str, gold: dict[str, Any] | None) -> bool | None:
    if gold is None:
        return None
    targets = [item.get("text") for item in _gold_evidence(gold) if item.get("text")]
    if not targets:
        return None
    normalized = _norm_text(evidence_text)
    return any(normalized == _norm_text(target) for target in targets)


def _field_evidence_metrics(candidate: dict[str, Any], gold: dict[str, Any] | None) -> dict[str, Any]:
    predicted_refs = candidate.get("evidence") or []
    reference_refs = _gold_evidence(gold)
    text_results = [
        _reference_anchor_match(ref.get("text", ""), gold)
        for ref in predicted_refs if ref.get("text")
    ]
    text_results = [value for value in text_results if value is not None]
    page_pairs = [
        (pred.get("page"), ref.get("page_number"))
        for pred in predicted_refs for ref in reference_refs
        if pred.get("page") is not None and ref.get("page_number") is not None
    ]
    page_correct = any(predicted == expected for predicted, expected in page_pairs) if page_pairs else None
    ious: list[float] = []
    for predicted in predicted_refs:
        predicted_box = _bbox(predicted.get("bounding_box"))
        if predicted_box is None or predicted.get("page") is None:
            continue
        for reference in reference_refs:
            reference_box = _bbox(reference.get("bbox"))
            if reference_box is None or reference.get("page_number") != predicted.get("page"):
                continue
            ious.append(bbox_iou(predicted_box, reference_box))
    return {
        "has_evidence_text": bool(predicted_refs),
        "evidence_text_correct": any(text_results) if text_results else None,
        "evidence_text_evaluable": bool(text_results),
        "page_correct": page_correct,
        "page_evaluable": bool(page_pairs),
        "bbox_iou": max(ious) if ious else None,
        "bbox_iou_evaluable": bool(ious),
    }


def _extract_prediction_dicts(predictions: list[DocumentPrediction | dict[str, Any]]) -> list[dict[str, Any]]:
    return [validate_prediction(item) for item in predictions]


def evaluate_predictions(
    predictions: list[DocumentPrediction | dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate predictions against annotation records.

    Ground-truth labels are consumed only here, after predictions have already
    been produced. OCR metrics are out of scope and must be reported separately.
    """
    pred_rows = _extract_prediction_dicts(predictions)
    pred_by_id = {row["document_id"]: row for row in pred_rows}
    if len(pred_by_id) != len(pred_rows):
        raise ValueError("Duplicate document_id in predictions.")
    ann_by_id = {row["document_id"]: row for row in annotations}
    if len(ann_by_id) != len(annotations):
        raise ValueError("Duplicate document_id in annotations.")
    if set(pred_by_id) != set(ann_by_id):
        missing = sorted(set(ann_by_id) - set(pred_by_id))
        extra = sorted(set(pred_by_id) - set(ann_by_id))
        raise ValueError(f"Prediction/annotation IDs differ (missing={missing[:3]}, extra={extra[:3]}).")

    domain_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gold_present": 0, "predicted": 0, "exact": 0})
    field_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gold_present": 0, "predicted": 0, "exact": 0})
    all_counts = {"tp": 0, "fp": 0, "fn": 0}
    numeric_rows: list[tuple[Decimal, Decimal]] = []
    evidence_proposals = 0
    unsupported = 0
    legacy_normalized_proposals = 0
    legacy_unsupported = 0
    proposals_with_text = 0
    anchor_evaluable = 0
    anchor_correct = 0
    legacy_proposals_with_text = 0
    legacy_anchor_evaluable = 0
    legacy_anchor_correct = 0
    page_evaluable = 0
    page_correct = 0
    bbox_scores: list[float] = []
    per_doc: list[dict[str, Any]] = []
    domain_matrix = {
        actual: {candidate: 0 for candidate in (*DOCUMENT_DOMAINS, "UNDETERMINED")}
        for actual in DOCUMENT_DOMAINS
    }

    for annotation in annotations:
        doc_id = annotation["document_id"]
        prediction = pred_by_id[doc_id]
        domain = annotation["domain"]
        predicted_domain = _predicted_document_domain(prediction)
        domain_matrix[domain][predicted_domain or "UNDETERMINED"] += 1
        references = {item["field_name"]: item for item in annotation.get("fields", [])}
        predicted_fields = _prediction_fields(prediction)
        field_results: list[dict[str, Any]] = []
        unflagged_ambiguous_scalar = False

        for field_name in CRITICAL_FIELDS[domain]:
            gold = references.get(field_name)
            if gold is None:
                continue
            field_prediction = predicted_fields.get(field_name)
            selected = _selected_candidate(field_prediction)
            normalized_value = selected.get("normalized_value") if selected else None
            scalar_candidates = (field_prediction or {}).get("candidates") or []
            status = gold.get("presence_status")
            expected = _canonical_expected(annotation, field_name, gold) if status == "present" else None
            is_correct = bool(
                status == "present" and expected is not None and normalized_value is not None
                and _norm(normalized_value) == _norm(expected)
            )

            field_counter = field_counts[field_name]
            domain_counter = domain_counts[domain]
            if status == "present" and expected is not None:
                field_counter["gold_present"] += 1
                domain_counter["gold_present"] += 1
                if is_correct:
                    field_counter["tp"] += 1
                    domain_counter["tp"] += 1
                    field_counter["exact"] += 1
                    domain_counter["exact"] += 1
                else:
                    field_counter["fn"] += 1
                    domain_counter["fn"] += 1
                    if normalized_value is not None:
                        field_counter["fp"] += 1
                        domain_counter["fp"] += 1
                if field_name in {"quantity", "net_lpg_mass", "shipment_mass", "distance"}:
                    expected_numeric = _decimal(expected)
                    predicted_numeric = _decimal(normalized_value)
                    if expected_numeric is not None:
                        numeric_rows.append((expected_numeric, predicted_numeric) if predicted_numeric is not None else (expected_numeric, Decimal("NaN")))
            elif normalized_value is not None:
                field_counter["fp"] += 1
                domain_counter["fp"] += 1

            if normalized_value is not None:
                field_counter["predicted"] += 1
                domain_counter["predicted"] += 1

            if status == "ambiguous" and normalized_value is not None:
                if field_prediction and field_prediction.get("evidence_status") != "AMBIGUOUS":
                    unflagged_ambiguous_scalar = True

            # Safety denominator counts each scalar candidate in critical fields,
            # including raw-only candidates that could not be normalized.
            for candidate in scalar_candidates:
                scalar = _candidate_scalar(candidate)
                if scalar is None:
                    continue
                evidence_proposals += 1
                supported = _candidate_is_supported(scalar, gold, annotation, field_name)
                unsupported += int(not supported)
                if candidate.get("normalized_value") is not None:
                    legacy_normalized_proposals += 1
                    legacy_unsupported += int(not supported)
                evidence_metrics = _field_evidence_metrics(candidate, gold)
                if evidence_metrics["has_evidence_text"]:
                    proposals_with_text += 1
                    if candidate.get("normalized_value") is not None:
                        legacy_proposals_with_text += 1
                if evidence_metrics["evidence_text_evaluable"]:
                    anchor_evaluable += 1
                    anchor_correct += int(bool(evidence_metrics["evidence_text_correct"]))
                    if candidate.get("normalized_value") is not None:
                        legacy_anchor_evaluable += 1
                        legacy_anchor_correct += int(bool(evidence_metrics["evidence_text_correct"]))
                if evidence_metrics["page_evaluable"]:
                    page_evaluable += 1
                    page_correct += int(bool(evidence_metrics["page_correct"]))
                if evidence_metrics["bbox_iou_evaluable"]:
                    bbox_scores.append(float(evidence_metrics["bbox_iou"]))

            field_results.append({
                "field_name": field_name,
                "reference_status": status,
                "expected_normalized_value": expected,
                "predicted_normalized_value": normalized_value,
                "prediction_evidence_status": field_prediction.get("evidence_status") if field_prediction else "UNDETERMINED",
                "normalized_value_correct": is_correct if status == "present" else None,
                "candidate_count": len(scalar_candidates),
                "candidate_evidence": [
                    ref for candidate in scalar_candidates for ref in candidate.get("evidence", [])
                ],
            })

        evidence_state = annotation["evidence_state"]
        readiness = prediction["accounting_readiness"]
        signal = prediction["review_signal"]
        missing_signal = signal["explicit_missing_evidence_signal"]
        if missing_signal is None:
            missing_signal = bool(prediction.get("missing_evidence"))
        ambiguity_signal = signal["explicit_ambiguity_signal"]
        if ambiguity_signal is None:
            ambiguity_signal = bool(prediction.get("ambiguities")) or any(
                item.get("evidence_status") == "AMBIGUOUS" for item in prediction["extracted_fields"]
            )
        per_doc.append({
            "document_id": doc_id,
            "domain": domain,
            "predicted_domain": predicted_domain or "UNDETERMINED",
            "document_domain_correct": predicted_domain == domain,
            "reference_evidence_state": evidence_state,
            "predicted_readiness": readiness,
            "missing_evidence_detected": bool(missing_signal),
            "ambiguity_detected": bool(ambiguity_signal),
            "false_completion": evidence_state == "incomplete" and readiness == "READY",
            "false_resolution": evidence_state == "ambiguous" and readiness == "READY",
            "unflagged_scalar_for_ambiguous_field": unflagged_ambiguous_scalar,
            "field_results": field_results,
        })

    for counts in field_counts.values():
        for key in ("tp", "fp", "fn"):
            all_counts[key] += counts[key]
    for counts in domain_counts.values():
        for key in ("tp", "fp", "fn"):
            # Domain counts are aggregated separately below; no double counting.
            pass

    per_field = {
        field: {
            **_metrics(counts),
            "gold_present_values": counts["gold_present"],
            "normalized_predictions": counts["predicted"],
            "normalized_value_accuracy": counts["exact"] / counts["gold_present"] if counts["gold_present"] else None,
        }
        for field, counts in sorted(field_counts.items())
    }
    per_domain = {
        domain: {
            **_metrics(counts),
            "carbon_critical_field_records": sum(1 for row in per_doc if row["domain"] == domain for _f in row["field_results"]),
            "gold_present_values": counts["gold_present"],
            "normalized_predictions": counts["predicted"],
            "normalized_value_accuracy": counts["exact"] / counts["gold_present"] if counts["gold_present"] else None,
        }
        for domain, counts in sorted(domain_counts.items())
    }

    domain_class_metrics = {}
    domain_micro = {"tp": 0, "fp": 0, "fn": 0}
    for label in DOCUMENT_DOMAINS:
        tp = domain_matrix[label][label]
        fp = sum(domain_matrix[actual][label] for actual in DOCUMENT_DOMAINS if actual != label)
        fn = sum(domain_matrix[label][candidate] for candidate in domain_matrix[label] if candidate != label)
        domain_class_metrics[label] = {
            **_metrics({"tp": tp, "fp": fp, "fn": fn}),
            "support": sum(domain_matrix[label].values()),
        }
        for key, value in (("tp", tp), ("fp", fp), ("fn", fn)):
            domain_micro[key] += value
    domain_total = sum(sum(row.values()) for row in domain_matrix.values())
    domain_correct = sum(domain_matrix[label][label] for label in DOCUMENT_DOMAINS)
    domain_classification = {
        "labels": list(DOCUMENT_DOMAINS),
        "confusion_matrix_rows_true_columns_predicted": domain_matrix,
        "accuracy": domain_correct / domain_total if domain_total else None,
        "aggregate_micro": _metrics(domain_micro),
        "per_class": domain_class_metrics,
        "macro_f1": statistics.mean(item["f1"] for item in domain_class_metrics.values()) if domain_class_metrics else 0.0,
        "classified_documents": sum(
            domain_matrix[actual][candidate]
            for actual in DOCUMENT_DOMAINS for candidate in DOCUMENT_DOMAINS
        ),
        "undetermined_documents": sum(domain_matrix[actual]["UNDETERMINED"] for actual in DOCUMENT_DOMAINS),
        "definition": "document_domain is scored from candidate predictions only; missing or ambiguous domain predictions count as UNDETERMINED.",
    }

    numeric_errors = []
    relative_errors = []
    numeric_exact = 0
    numeric_present = 0
    numeric_predicted = 0
    for expected, predicted in numeric_rows:
        numeric_present += 1
        if predicted.is_nan():
            continue
        numeric_predicted += 1
        error = abs(predicted - expected)
        numeric_errors.append(float(error))
        if expected != 0:
            relative_errors.append(float(error / abs(expected)))
        numeric_exact += int(error == 0)

    actual_incomplete = [row["reference_evidence_state"] == "incomplete" for row in per_doc]
    predicted_missing = [row["missing_evidence_detected"] for row in per_doc]
    actual_ambiguous = [row["reference_evidence_state"] == "ambiguous" for row in per_doc]
    predicted_ambiguity = [row["ambiguity_detected"] for row in per_doc]

    matrix = {
        label: {candidate: 0 for candidate in ("ready", "incomplete", "ambiguous", "UNDETERMINED")}
        for label in ("ready", "incomplete", "ambiguous")
    }
    for row in per_doc:
        predicted_label = "UNDETERMINED" if row["predicted_readiness"] == "UNDETERMINED" else row["predicted_readiness"].casefold()
        if predicted_label not in matrix[row["reference_evidence_state"]]:
            predicted_label = "UNDETERMINED"
        matrix[row["reference_evidence_state"]][predicted_label] += 1
    per_readiness_class = {}
    for label in READINESS_LABELS:
        key = label.casefold()
        tp = matrix[key][key]
        fp = sum(matrix[actual][key] for actual in matrix if actual != key)
        fn = sum(matrix[key][candidate] for candidate in matrix[key] if candidate != key)
        per_readiness_class[key] = _metrics({"tp": tp, "fp": fp, "fn": fn})
    classified = sum(row["predicted_readiness"] != "UNDETERMINED" for row in per_doc)
    ready_count = sum(row["reference_evidence_state"] == "ready" for row in per_doc)
    incomplete_count = sum(actual_incomplete)
    ambiguous_count = sum(actual_ambiguous)
    false_completions = sum(row["false_completion"] for row in per_doc)
    false_resolutions = sum(row["false_resolution"] for row in per_doc)
    ambiguous_scalar_docs = sum(row["unflagged_scalar_for_ambiguous_field"] for row in per_doc if row["reference_evidence_state"] == "ambiguous")

    return {
        "protocol": {
            "contract_version": "1.0",
            "ocr_metrics_included": False,
            "prediction_source": "Contract predictions supplied before annotations are evaluated.",
            "readiness_scope": "Evidence sufficiency prediction only; no accounting result is represented in this contract.",
            "false_completion_definition": "A READY prediction for a reference INCOMPLETE document.",
            "false_resolution_definition": "A READY prediction for a reference AMBIGUOUS document.",
            "missing_signal_basis": "Use explicit current-pipeline signal when present; otherwise use nonempty missing_evidence.",
            "ambiguity_signal_basis": "Use explicit current-pipeline signal when present; otherwise use ambiguity records or AMBIGUOUS field statuses.",
        },
        "metrics": {
            "document_domain_classification": domain_classification,
            "carbon_critical_extraction": {
                "definition": "Exact normalized-value match. A wrong normalized scalar counts as one false positive and one false negative; missing a present reference is a false negative; a scalar on missing/ambiguous reference evidence is a false positive.",
                "aggregate": _metrics(all_counts),
                "normalized_value_accuracy": all_counts["tp"] / sum(c["gold_present"] for c in field_counts.values()) if sum(c["gold_present"] for c in field_counts.values()) else None,
                "per_domain": per_domain,
                "per_field": per_field,
                "scored_field_records": sum(
                    len(row["field_results"]) for row in per_doc
                ),
                "numeric": {
                    "gold_present_numeric_values": numeric_present,
                    "numeric_predictions": numeric_predicted,
                    "exact_normalized_numeric_accuracy_over_gold": numeric_exact / numeric_present if numeric_present else None,
                    "exact_accuracy_when_predicted": numeric_exact / numeric_predicted if numeric_predicted else None,
                    "mae": statistics.mean(numeric_errors) if numeric_errors else None,
                    "mean_relative_error": statistics.mean(relative_errors) if relative_errors else None,
                },
            },
            "evidence_grounding": {
                "scalar_candidates_in_critical_fields": evidence_proposals,
                "unsupported_values": unsupported,
                "unsupported_value_rate": unsupported / evidence_proposals if evidence_proposals else None,
                "unsupported_value_definition": "A scalar candidate is unsupported if it matches neither the annotation's normalized/raw value, an annotated candidate, nor text in the same field's evidence. Denominator is all scalar candidates in carbon-critical fields, including raw-only candidates.",
                "legacy_normalized_scalar_proposals": legacy_normalized_proposals,
                "legacy_unsupported_normalized_values": legacy_unsupported,
                "legacy_unsupported_value_rate": legacy_unsupported / legacy_normalized_proposals if legacy_normalized_proposals else None,
                "legacy_proposals_with_evidence_text": legacy_proposals_with_text,
                "legacy_evidence_text_coverage": legacy_proposals_with_text / legacy_normalized_proposals if legacy_normalized_proposals else None,
                "legacy_evidence_text_evaluable": legacy_anchor_evaluable,
                "legacy_evidence_text_correct": legacy_anchor_correct,
                "legacy_evidence_text_correctness": legacy_anchor_correct / legacy_anchor_evaluable if legacy_anchor_evaluable else None,
                "proposals_with_evidence_text": proposals_with_text,
                "evidence_text_coverage": proposals_with_text / evidence_proposals if evidence_proposals else None,
                "evidence_text_evaluable": anchor_evaluable,
                "evidence_text_correct": anchor_correct,
                "evidence_text_correctness": anchor_correct / anchor_evaluable if anchor_evaluable else None,
                "page_evaluable": page_evaluable,
                "page_correct": page_correct,
                "page_correctness": page_correct / page_evaluable if page_evaluable else None,
                "bbox_iou_evaluable": len(bbox_scores),
                "mean_bbox_iou": statistics.mean(bbox_scores) if bbox_scores else None,
                "bbox_iou_at_least_0_5_rate": sum(value >= 0.5 for value in bbox_scores) / len(bbox_scores) if bbox_scores else None,
                "adapter_location_limitation": "Current extractor supplies evidence text only; it supplies no page or bounding-box coordinates.",
            },
            "missing_evidence_detection": {
                "positive_class": "incomplete",
                "metrics": _binary_metrics(actual_incomplete, predicted_missing),
                "false_completion_rate": false_completions / incomplete_count if incomplete_count else None,
                "false_completion_count": false_completions,
                "denominator_incomplete_documents": incomplete_count,
            },
            "ambiguity_detection": {
                "positive_class": "ambiguous",
                "metrics": _binary_metrics(actual_ambiguous, predicted_ambiguity),
                "false_resolution_rate": false_resolutions / ambiguous_count if ambiguous_count else None,
                "false_resolution_count": false_resolutions,
                "denominator_ambiguous_documents": ambiguous_count,
                "unflagged_single_scalar_documents": ambiguous_scalar_docs,
                "unflagged_single_scalar_rate": ambiguous_scalar_docs / ambiguous_count if ambiguous_count else None,
                "unflagged_single_scalar_definition": "An ambiguous reference document contains at least one ambiguous critical field for which the prediction emitted one normalized scalar without marking that field AMBIGUOUS; this is reported separately from READY-level false resolution.",
            },
            "accounting_readiness": {
                "confusion_matrix_rows_true_columns_predicted": matrix,
                "per_class": per_readiness_class,
                "macro_f1": statistics.mean(item["f1"] for item in per_readiness_class.values()) if per_readiness_class else 0.0,
                "classified_documents": classified,
                "coverage": classified / len(per_doc) if per_doc else None,
                "undetermined_documents": len(per_doc) - classified,
                "ready_reference_documents": ready_count,
            },
        },
        "per_document": per_doc,
    }
