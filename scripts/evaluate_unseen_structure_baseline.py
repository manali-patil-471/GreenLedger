"""Run the existing GreenLedger OCR/rule-extraction baseline on the frozen 120 pilot.

This is an evaluation adapter only. It calls the current production OCR, field
extractor and accounting engine; it does not change or improve their behavior.
Run with .venv-ocr-eval/Scripts/python.exe to use the already-installed local
RapidOCR runtime and pinned model assets.
"""

from __future__ import annotations

import ctypes
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15"
OUTPUT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_2026-11-15.json"
sys.path.insert(0, str(ROOT))


CRITICAL_FIELDS = {
    "electricity": ["activity_description", "quantity", "unit", "electricity_use", "geography", "billing_period"],
    "diesel": ["activity_description", "quantity", "unit", "geography", "vehicle_reference", "source_type", "combustion_status", "operational_control"],
    "lpg": ["activity_description", "net_lpg_mass", "unit", "geography", "combustion_status", "operational_control", "source_type", "commercial_institutional"],
    "materials": ["activity_description", "material_identity", "quantity", "unit", "geography", "purchase_evidence"],
    "freight": ["activity_description", "geography", "transport_mode", "transport_scenario", "shipment_mass", "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class"],
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_frozen_dataset() -> tuple[dict[str, Any], dict[str, Any]]:
    marker_path = PILOT / "FROZEN.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("freeze_status") != "FROZEN" or marker.get("validation", {}).get("old_quarantined_test_split_accessed") is not False:
        raise RuntimeError("Pilot freeze marker is invalid or records quarantined-test access.")
    manifest_path = PILOT / "manifest.json"
    annotations_path = PILOT / "annotations.jsonl"
    if _sha256(manifest_path) != marker.get("manifest_sha256"):
        raise RuntimeError("Frozen manifest SHA-256 does not match FROZEN.json.")
    if _sha256(annotations_path) != marker.get("annotations_sha256"):
        raise RuntimeError("Frozen annotations SHA-256 does not match FROZEN.json.")
    actual = sorted(p.relative_to(PILOT).as_posix() for p in PILOT.rglob("*") if p.is_file() and p.name != "FROZEN.json")
    expected = sorted(row["path"] for row in marker["hash_scope"]["files"])
    if actual != expected:
        raise RuntimeError("Frozen dataset file set differs from the freeze marker.")
    mismatches = []
    for row in marker["hash_scope"]["files"]:
        path = PILOT / row["path"]
        if path.stat().st_size != row["bytes"] or _sha256(path) != row["sha256"]:
            mismatches.append(row["path"])
    if mismatches:
        raise RuntimeError("Frozen file hash mismatch: " + ", ".join(mismatches))
    return marker, json.loads(manifest_path.read_text(encoding="utf-8"))


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value).replace(",", ""))
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


def _field_index(annotation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["field_name"]: field for field in annotation.get("fields", [])}


def _canonical_expected_value(annotation: dict[str, Any], field_name: str, field: dict[str, Any]) -> Any:
    """Compare the extractor's calculation-unit outputs to canonical annotation units."""
    if field_name != "unit":
        return field.get("normalized_value")
    raw_unit = field.get("raw_unit") or field.get("raw_value")
    if not raw_unit:
        return field.get("normalized_value")
    try:
        from greenledger.core import normalize_activity, normalize_quantity, normalize_unit
        activity = normalize_activity(annotation["activity_id"])
        unit = normalize_unit(activity, raw_unit)
        _quantity, canonical_unit, _trace = normalize_quantity(activity, Decimal("1"), unit)
        return canonical_unit or field.get("normalized_value")
    except Exception:
        return field.get("normalized_value")


def _predicted_values(extraction: dict[str, Any] | None, domain: str) -> dict[str, dict[str, Any]]:
    if not extraction:
        return {}
    result: dict[str, dict[str, Any]] = {}
    activity = extraction.get("activity") or {}
    quantity = extraction.get("quantity") or {}
    unit = extraction.get("unit") or {}
    if activity.get("value") is not None:
        result["activity_description"] = {"value": activity["value"], "evidence_text": activity.get("evidence_text"), "source_field": "activity"}
    quantity_field = {"lpg": "net_lpg_mass"}.get(domain, "quantity")
    if domain != "freight" and quantity.get("normalized_value") is not None:
        result[quantity_field] = {"value": quantity["normalized_value"], "evidence_text": quantity.get("evidence_text"), "source_field": "quantity"}
    if domain in {"electricity", "diesel", "lpg", "materials"} and unit.get("value") is not None:
        result["unit"] = {"value": unit["value"], "evidence_text": unit.get("evidence_text"), "source_field": "unit"}
    return result


def _candidate_statuses(extraction: dict[str, Any] | None) -> list[str]:
    if not extraction:
        return []
    return [str((extraction.get(key) or {}).get("status") or "") for key in ("activity", "quantity", "unit")]


def _evidence_texts(field: dict[str, Any]) -> list[str]:
    values = []
    for evidence in field.get("evidence", []):
        text = evidence.get("text")
        if text:
            values.append(text)
    return values


def _candidate_is_supported(pred: Any, reference_field: dict[str, Any] | None, annotation: dict[str, Any], field_name: str) -> bool:
    if not reference_field or pred is None:
        return False
    candidate_values = []
    if reference_field.get("normalized_value") is not None:
        candidate_values.append(reference_field["normalized_value"])
    if reference_field.get("raw_value") is not None:
        candidate_values.append(reference_field["raw_value"])
    for candidate in reference_field.get("candidates", []):
        if candidate.get("raw_value") is not None:
            candidate_values.append(candidate["raw_value"])
            if candidate.get("raw_unit"):
                try:
                    from greenledger.core import normalize_activity, normalize_quantity, normalize_unit
                    activity = normalize_activity(annotation["activity_id"])
                    unit = normalize_unit(activity, candidate["raw_unit"])
                    quantity, _canonical_unit, _trace = normalize_quantity(activity, Decimal(str(candidate["raw_value"])), unit)
                    if quantity is not None:
                        candidate_values.append(str(quantity))
                except Exception:
                    pass
    if field_name == "unit":
        canonical = _canonical_expected_value(annotation, field_name, reference_field)
        if canonical is not None:
            candidate_values.append(canonical)
    if any(_norm(pred) == _norm(value) for value in candidate_values):
        return True
    text = " ".join(_evidence_texts(reference_field)).casefold()
    value = str(pred).casefold().strip()
    return bool(value and value in text)


def _anchor_exact(predicted: str | None, field: dict[str, Any] | None) -> bool | None:
    if predicted is None or field is None:
        return None
    from greenledger.ocr_eval import normalize_ocr_text
    target = normalize_ocr_text(predicted)
    return any(target == normalize_ocr_text(reference) for reference in _evidence_texts(field))


def _counter_metrics(counter: dict[str, int]) -> dict[str, Any]:
    tp, fp, fn = counter.get("tp", 0), counter.get("fp", 0), counter.get("fn", 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn, "precision": precision, "recall": recall, "f1": f1}


def _binary_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, Any]:
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum((not a) and p for a, p in zip(actual, predicted))
    fn = sum(a and (not p) for a, p in zip(actual, predicted))
    tn = sum((not a) and (not p) for a, p in zip(actual, predicted))
    return {**_counter_metrics({"tp": tp, "fp": fp, "fn": fn}), "true_negative": tn}


def _percentile_summary(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean_seconds": statistics.mean(values) if values else None,
        "median_seconds": statistics.median(values) if values else None,
        "min_seconds": min(values) if values else None,
        "max_seconds": max(values) if values else None,
        "total_seconds": sum(values),
    }


def _peak_working_set_mb() -> float | None:
    if os.name != "nt":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
    return counters.PeakWorkingSetSize / (1024 * 1024) if ok else None


def _host_physical_memory_gb() -> float | None:
    if os.name != "nt":
        return None
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    return status.ullTotalPhys / (1024 ** 3) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None


def _anchor_ocr_metrics(predictions: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    from greenledger.ocr_eval import edit_distance, normalize_ocr_text
    by_id = {row["document_id"]: row for row in predictions}
    totals = Counter()
    exact_anchors = 0
    anchors = 0
    page_covered = 0
    for annotation in annotations:
        pred = by_id[annotation["document_id"]]
        page_lines = {int(row["page"]): [x for x in (row.get("text") or "").splitlines() if x.strip()] for row in pred.get("ocr", {}).get("pages", [])}
        field_map = _field_index(annotation)
        seen = set()
        for field_name in CRITICAL_FIELDS[annotation["domain"]]:
            field = field_map.get(field_name)
            if not field or field.get("presence_status") not in {"present", "ambiguous"}:
                continue
            for evidence in field.get("evidence", []):
                text = evidence.get("text")
                page = int(evidence.get("page_number", 1))
                if not text or (page, text) in seen:
                    continue
                seen.add((page, text))
                anchors += 1
                reference = normalize_ocr_text(text)
                candidates = [normalize_ocr_text(line) for line in page_lines.get(page, [])]
                if candidates:
                    page_covered += 1
                    best = min(candidates, key=lambda value: edit_distance(reference, value) / max(1, len(reference)))
                    char_edits = edit_distance(reference, best)
                    reference_words, output_words = reference.split(), best.split()
                    word_edits = edit_distance(reference_words, output_words)
                else:
                    char_edits, word_edits = len(reference), len(reference.split())
                totals["char_edits"] += char_edits
                totals["reference_characters"] += len(reference)
                totals["word_edits"] += word_edits
                totals["reference_words"] += len(reference.split())
                if char_edits == 0:
                    exact_anchors += 1
    return {
        "scope": "Carbon-critical annotation evidence snippets only; each snippet compared with the closest OCR line on its annotated page.",
        "not_full_document_cer_wer": True,
        "anchors": anchors,
        "anchors_with_ocr_lines_on_annotated_page": page_covered,
        "exact_anchor_text_rate": exact_anchors / anchors if anchors else None,
        "anchor_cer": totals["char_edits"] / totals["reference_characters"] if totals["reference_characters"] else None,
        "anchor_wer": totals["word_edits"] / totals["reference_words"] if totals["reference_words"] else None,
        **dict(totals),
    }


def _find_present(field_map: dict[str, dict[str, Any]], *names: str) -> dict[str, Any] | None:
    for name in names:
        field = field_map.get(name)
        if field and field.get("presence_status") == "present":
            return field
    return None


def _field_value(field_map: dict[str, dict[str, Any]], name: str, key: str = "normalized_value", default: Any = None) -> Any:
    field = _find_present(field_map, name)
    if not field:
        return default
    value = field.get(key)
    return value if value is not None else field.get("raw_value", default)


def _gold_submission(annotation: dict[str, Any]) -> dict[str, Any]:
    fields = _field_index(annotation)
    domain = annotation["domain"]
    submission: dict[str, Any] = {"activity": annotation["activity_id"], "fields_confirmed": "yes"}
    if domain == "electricity":
        quantity = _find_present(fields, "quantity")
        submission.update({
            "quantity": quantity.get("raw_value") if quantity else None,
            "unit": quantity.get("raw_unit") if quantity else _field_value(fields, "unit", "raw_value"),
            "geography_code": _field_value(fields, "geography"),
            "applicable_period": _field_value(fields, "billing_period"),
            "electricity_use": _field_value(fields, "electricity_use"),
        })
    elif domain == "diesel":
        quantity = _find_present(fields, "quantity")
        submission.update({
            "quantity": quantity.get("raw_value") if quantity else None,
            "unit": quantity.get("raw_unit") if quantity else _field_value(fields, "unit", "raw_value"),
            "geography_code": _field_value(fields, "geography"),
            "vehicle_class": _field_value(fields, "vehicle_reference"),
            "source_type": _field_value(fields, "source_type"),
            "combusted": _field_value(fields, "combustion_status"),
            "controlled": _field_value(fields, "operational_control"),
        })
    elif domain == "lpg":
        quantity = _find_present(fields, "net_lpg_mass", "quantity")
        submission.update({
            "quantity": quantity.get("raw_value") if quantity else None,
            "unit": quantity.get("raw_unit") if quantity else _field_value(fields, "unit", "raw_value"),
            "geography_code": _field_value(fields, "geography"),
            "combusted": _field_value(fields, "combustion_status"),
            "controlled": _field_value(fields, "operational_control"),
            "source_type": _field_value(fields, "source_type"),
            "commercial_institutional": _field_value(fields, "commercial_institutional"),
        })
    elif domain == "materials":
        quantity = _find_present(fields, "quantity")
        submission.update({
            "quantity": quantity.get("raw_value") if quantity else None,
            "unit": quantity.get("raw_unit") if quantity else _field_value(fields, "unit", "raw_value"),
            "geography_code": _field_value(fields, "geography"),
            "material_identity": _field_value(fields, "material_identity"),
        })
    elif domain == "freight":
        mass = _find_present(fields, "shipment_mass")
        distance = _find_present(fields, "distance")
        submission.update({
            "geography_code": _field_value(fields, "geography"),
            "transport_mode": _field_value(fields, "transport_mode"),
            "transport_scenario": _field_value(fields, "transport_scenario"),
            "transport_vehicle_class": _field_value(fields, "transport_vehicle_class"),
            "shipment_mass": mass.get("raw_value") if mass else None,
            "mass_unit": mass.get("raw_unit") if mass else _field_value(fields, "shipment_mass_unit", "raw_value"),
            "distance": distance.get("raw_value") if distance else None,
            "distance_unit": distance.get("raw_unit") if distance else _field_value(fields, "distance_unit", "raw_value"),
        })
    return submission


def _accounting_gold_input_check(annotation: dict[str, Any]) -> dict[str, Any]:
    from greenledger.core import evaluate_submission
    try:
        result = evaluate_submission(_gold_submission(annotation))
    except Exception as error:  # Record a diagnostic failure, never repair a case.
        return {"status": "ENGINE_ERROR", "error": type(error).__name__ + ": " + str(error)}
    expected_trace = (annotation.get("expected_deterministic_result") or {}).get("accounting_trace") or {}
    expected_calculation = expected_trace.get("co2_calculation") if annotation["domain"] == "electricity" else expected_trace.get("calculation")
    expected_value = (expected_calculation or {}).get("co2_kg" if annotation["domain"] == "electricity" else "co2e_kg")
    expected_unit = "kgCO2" if annotation["domain"] == "electricity" else "kgCO2e"
    actual_value = result.get("co2_kg") if annotation["domain"] == "electricity" else result.get("co2e")
    actual_unit = result.get("co2_result_unit") if annotation["domain"] == "electricity" else "kgCO2e"
    expected_factor = (expected_calculation or {}).get("factor") or expected_trace.get("factor") or {}
    actual_factor = result.get("co2_factor") if annotation["domain"] == "electricity" else result.get("factor")
    expected_classification = expected_trace.get("classification") or {}
    expected_decimal, actual_decimal = _decimal(expected_value), _decimal(actual_value)
    absolute_error = abs(actual_decimal - expected_decimal) if actual_decimal is not None and expected_decimal is not None else None
    relative_error = absolute_error / abs(expected_decimal) if absolute_error is not None and expected_decimal not in (None, Decimal(0)) else None
    factor_correct = bool(actual_factor and actual_factor.get("factor_id") == expected_factor.get("factor_id"))
    expected_gas_basis = (expected_calculation or {}).get("gas_basis") or expected_factor.get("gas_basis")
    actual_gas_basis = actual_factor.get("gas_basis") if actual_factor else result.get("co2_gas_basis")
    gas_basis_correct = actual_gas_basis == expected_gas_basis
    boundary_correct = (
        result.get("scope") == expected_classification.get("scope")
        and result.get("scope_category") == expected_classification.get("scope_category")
        and result.get("classification_status", "").startswith("APPROVED")
    )
    numeric_exact = absolute_error == 0 if absolute_error is not None else False
    unit_correct = actual_unit == expected_unit
    accounting_correct = numeric_exact and factor_correct and boundary_correct and unit_correct and gas_basis_correct
    return {
        "status": "CALCULATED" if actual_value is not None else "NO_RESULT",
        "input_source": "frozen normalized/raw ground-truth annotations; isolated accounting diagnostic only; not used by OCR/extraction/readiness",
        "expected_value": str(expected_decimal) if expected_decimal is not None else None,
        "actual_value": str(actual_decimal) if actual_decimal is not None else None,
        "expected_unit": expected_unit,
        "actual_unit": actual_unit,
        "unit_correct": unit_correct,
        "expected_gas_basis": expected_gas_basis,
        "actual_gas_basis": actual_gas_basis,
        "gas_basis_correct": gas_basis_correct,
        "absolute_error": str(absolute_error) if absolute_error is not None else None,
        "relative_error": str(relative_error) if relative_error is not None else None,
        "exact_numeric_match": numeric_exact,
        "factor_correct": factor_correct,
        "expected_factor_id": expected_factor.get("factor_id"),
        "actual_factor_id": actual_factor.get("factor_id") if actual_factor else None,
        "accounting_boundary_correct": boundary_correct,
        "expected_scope": expected_classification.get("scope"),
        "actual_scope": result.get("scope"),
        "expected_category": expected_classification.get("scope_category"),
        "actual_category": result.get("scope_category"),
        "accounting_result_correct": accounting_correct,
        "calculation_trace": result.get("co2_calculation_trace") if annotation["domain"] == "electricity" else result.get("calculation_trace"),
    }


def _system_grounding_and_metrics(predictions: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    metric_rows = []
    unsupported = 0
    proposals = 0
    anchored_proposals = 0
    exact_anchors = 0
    anchor_evaluable = 0
    numeric_rows = []
    for annotation, prediction in zip(annotations, predictions):
        domain = annotation["domain"]
        fields = _field_index(annotation)
        predicted = prediction["proposed_critical_values"]
        for field_name in CRITICAL_FIELDS[domain]:
            gold = fields.get(field_name)
            if gold is None:
                continue
            proposal = predicted.get(field_name)
            value = proposal.get("value") if proposal else None
            status = gold.get("presence_status")
            valid_gold = _canonical_expected_value(annotation, field_name, gold) if status == "present" else None
            record = {"document_id": annotation["document_id"], "domain": domain, "field_name": field_name, "presence_status": status, "gold": valid_gold, "prediction": value}
            if status == "present" and valid_gold is not None:
                record["correct"] = _norm(value) == _norm(valid_gold) if value is not None else False
                numeric_expected = _decimal(valid_gold) if field_name in {"quantity", "net_lpg_mass", "shipment_mass", "distance"} else None
                numeric_pred = _decimal(value) if field_name in {"quantity", "net_lpg_mass", "shipment_mass", "distance"} else None
                if numeric_expected is not None:
                    numeric_rows.append({"field_name": field_name, "expected": numeric_expected, "predicted": numeric_pred})
            else:
                record["correct"] = None
            metric_rows.append(record)
            if value is not None:
                proposals += 1
                supported = _candidate_is_supported(value, gold, annotation, field_name)
                if not supported:
                    unsupported += 1
                if proposal.get("evidence_text"):
                    anchored_proposals += 1
                    anchor_match = _anchor_exact(proposal["evidence_text"], gold)
                    if anchor_match is not None:
                        anchor_evaluable += 1
                        exact_anchors += int(anchor_match)
                record["evidence_text"] = proposal.get("evidence_text")
                record["source_field"] = proposal.get("source_field")
                record["evidence_supported_by_annotation"] = supported
                record["anchor_exact_match"] = _anchor_exact(proposal.get("evidence_text"), gold)

    grouped: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0}))
    all_counter = {"tp": 0, "fp": 0, "fn": 0}
    field_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gold_present": 0, "predicted": 0, "eligible": 0, "exact": 0})
    domain_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gold_present": 0, "predicted": 0, "eligible": 0, "exact": 0})
    for row in metric_rows:
        field = row["field_name"]
        domain = row["domain"]
        value = row["prediction"]
        status = row["presence_status"]
        counter = field_counts[field]
        dcounter = domain_counts[domain]
        if status == "present" and row["gold"] is not None:
            counter["gold_present"] += 1; dcounter["gold_present"] += 1
            counter["eligible"] += 1; dcounter["eligible"] += 1
            if row["correct"]:
                counter["tp"] += 1; dcounter["tp"] += 1
                counter["exact"] += 1; dcounter["exact"] += 1
            else:
                counter["fn"] += 1; dcounter["fn"] += 1
                if value is not None:
                    counter["fp"] += 1; dcounter["fp"] += 1
        elif value is not None:
            counter["fp"] += 1; dcounter["fp"] += 1
        if value is not None:
            counter["predicted"] += 1; dcounter["predicted"] += 1
    for counts in field_counts.values():
        for key in ("tp", "fp", "fn"):
            all_counter[key] += counts[key]
    for domain in CRITICAL_FIELDS:
        for key in ("tp", "fp", "fn"):
            all_counter[key] += 0
    # Domain grouping above is the exact micro score; fields remain separate for the report.
    per_domain = {}
    for domain, counts in domain_counts.items():
        per_domain[domain] = {
            **_counter_metrics(counts),
            "critical_field_records": sum(1 for row in metric_rows if row["domain"] == domain),
            "gold_present_values": counts["gold_present"],
            "predicted_values": counts["predicted"],
            "normalized_exact_match_accuracy": counts["exact"] / counts["eligible"] if counts["eligible"] else None,
        }
    per_field = {}
    for field, counts in field_counts.items():
        per_field[field] = {
            **_counter_metrics(counts),
            "gold_present_values": counts["gold_present"],
            "predicted_values": counts["predicted"],
            "normalized_exact_match_accuracy": counts["exact"] / counts["eligible"] if counts["eligible"] else None,
        }
    numeric_errors = []
    numeric_relative = []
    numeric_exact = 0
    numeric_gold = 0
    numeric_predicted = 0
    for row in numeric_rows:
        numeric_gold += 1
        if row["predicted"] is None:
            continue
        numeric_predicted += 1
        error = abs(row["predicted"] - row["expected"])
        numeric_errors.append(float(error))
        if row["expected"] != 0:
            numeric_relative.append(float(error / abs(row["expected"])))
        numeric_exact += int(error == 0)
    numeric = {
        "gold_present_numeric_values": numeric_gold,
        "numeric_predictions": numeric_predicted,
        "numeric_prediction_coverage": numeric_predicted / numeric_gold if numeric_gold else None,
        "exact_normalized_numeric_accuracy_over_gold": numeric_exact / numeric_gold if numeric_gold else None,
        "exact_accuracy_when_predicted": numeric_exact / numeric_predicted if numeric_predicted else None,
        "mae": statistics.mean(numeric_errors) if numeric_errors else None,
        "mean_relative_error": statistics.mean(numeric_relative) if numeric_relative else None,
        "numeric_prediction_error_rate_when_predicted": (numeric_predicted - numeric_exact) / numeric_predicted if numeric_predicted else None,
    }
    return {
        "field_extraction": {
            "definition": "Exact normalized field-value match. A wrong scalar counts as one FP and one FN; no scalar for a present reference is an FN; a scalar for missing/ambiguous evidence is an FP. Ambiguous references have no single acceptable scalar.",
            "aggregate": _counter_metrics(all_counter),
            "per_domain": per_domain,
            "per_field": per_field,
            "numeric": numeric,
            "scored_field_records": len(metric_rows),
            "carbon_critical_fields_by_domain": CRITICAL_FIELDS,
        },
        "evidence_grounding": {
            "proposed_carbon_critical_values": proposals,
            "unsupported_values": unsupported,
            "unsupported_value_rate": unsupported / proposals if proposals else None,
            "definition": "Unsupported means a proposed scalar does not match the frozen normalized/raw value, an annotated ambiguity candidate, or evidence text for that same field. Denominator is every non-null carbon-critical value proposed by the existing extractor.",
            "proposals_with_evidence_text": anchored_proposals,
            "evidence_text_coverage": anchored_proposals / proposals if proposals else None,
            "proposals_with_evaluable_exact_anchor": anchor_evaluable,
            "exact_anchor_matches": exact_anchors,
            "exact_anchor_correctness": exact_anchors / anchor_evaluable if anchor_evaluable else None,
            "page_correctness": None,
            "bbox_iou": None,
            "location_limitation": "Current extractor emits text evidence only; it does not emit page numbers or bounding boxes.",
        },
        "metric_rows": metric_rows,
    }


def _readiness_metrics(predictions: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    labels = ["ready", "incomplete", "ambiguous"]
    matrix = {label: {target: 0 for target in labels + ["UNDETERMINED"]} for label in labels}
    for annotation in annotations:
        matrix[annotation["evidence_state"]]["UNDETERMINED"] += 1
    per_class = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[actual][label] for actual in labels if actual != label)
        fn = sum(matrix[label][target] for target in labels + ["UNDETERMINED"] if target != label)
        per_class[label] = _counter_metrics({"tp": tp, "fp": fp, "fn": fn})
    macro_f1 = statistics.mean(per_class[label]["f1"] for label in labels)
    return {
        "definition": "The current app has no automatic READY/INCOMPLETE/AMBIGUOUS classifier and requires user-entered, human-confirmed fields. No class is imputed from the annotation; UNDETERMINED is scored as an abstention/miss.",
        "confusion_matrix_rows_true_columns_predicted": matrix,
        "per_class": per_class,
        "macro_f1": macro_f1,
        "classified_documents": 0,
        "coverage": 0.0,
        "undetermined_documents": len(annotations),
    }


def _difficulty_breakdown(predictions: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    annotation_by_id = {row["document_id"]: row for row in annotations}
    groups: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in predictions:
        doc_id = row["document_id"]
        page_class = "single_page" if int(row["page_count"]) == 1 else "multi_page"
        file_class = "pdf" if row["format"].endswith("pdf") else "standalone_image"
        for name, value in (
            ("page_count", page_class),
            ("file_kind", file_class),
            ("rendering_origin", row["format"]),
            ("layout_structure", row.get("layout_structure") or "unknown"),
            ("layout_family", row.get("template_family") or "unknown"),
            ("evidence_state", row["reference_evidence_state"]),
        ):
            groups[name][value].add(doc_id)
    output: dict[str, Any] = {}
    for axis, categories in groups.items():
        output[axis] = {}
        for category, ids in sorted(categories.items()):
            group_predictions = [row for row in predictions if row["document_id"] in ids]
            group_annotations = [annotation_by_id[row["document_id"]] for row in group_predictions]
            scored = _system_grounding_and_metrics(group_predictions, group_annotations)
            review = [row["current_system_review_signal"] for row in group_predictions]
            output[axis][category] = {
                "documents": len(ids),
                "carbon_critical_extraction": scored["field_extraction"]["aggregate"],
                "normalized_exact_match_accuracy": scored["field_extraction"]["per_domain"],
                "ocr_anchor_metrics": _anchor_ocr_metrics(group_predictions, group_annotations),
                "review_required_rate": sum(bool(row["review_required"]) for row in review) / len(review) if review else None,
                "missing_signal_rate": sum(bool(row["explicit_missing_evidence_signal"]) for row in review) / len(review) if review else None,
                "ambiguity_signal_rate": sum(bool(row["explicit_ambiguity_signal"]) for row in review) / len(review) if review else None,
                "small_group_note": "Descriptive subgroup only; interpret cautiously when n < 10.",
            }
    return output


def _recompute_metrics(result: dict[str, Any], annotations: list[dict[str, Any]]) -> None:
    records = result["per_document"]
    if len(records) != 120:
        raise RuntimeError("Cannot rescore: expected 120 recorded predictions.")
    if [row["document_id"] for row in records] != [row["document_id"] for row in annotations]:
        raise RuntimeError("Cannot rescore: prediction order/IDs differ from frozen annotations.")
    annotation_by_id = {row["document_id"]: row for row in annotations}
    for record in records:
        if record["reference_evidence_state"] == "ready":
            record["gold_input_accounting_diagnostic"] = _accounting_gold_input_check(annotation_by_id[record["document_id"]])
    field_grounding = _system_grounding_and_metrics(records, annotations)
    metric_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metric in field_grounding.pop("metric_rows"):
        metric_by_id[metric["document_id"]].append(metric)
    for row in records:
        row["scored_carbon_critical_fields"] = metric_by_id[row["document_id"]]
    result_by_id = {row["document_id"]: row for row in records}
    actual_incomplete = [row["evidence_state"] == "incomplete" for row in annotations]
    predicted_missing = [bool(result_by_id[row["document_id"]]["current_system_review_signal"]["explicit_missing_evidence_signal"]) for row in annotations]
    actual_ambiguous = [row["evidence_state"] == "ambiguous" for row in annotations]
    predicted_ambiguous = [bool(result_by_id[row["document_id"]]["current_system_review_signal"]["explicit_ambiguity_signal"]) for row in annotations]
    states = {state: Counter() for state in ("ready", "incomplete", "ambiguous")}
    for annotation in annotations:
        item = result_by_id[annotation["document_id"]]
        signal = item["current_system_review_signal"]
        state_counts = states[annotation["evidence_state"]]
        state_counts["review_flagged"] += int(bool(signal["review_required"]))
        state_counts["missing_signal"] += int(bool(signal["explicit_missing_evidence_signal"]))
        state_counts["ambiguity_signal"] += int(bool(signal["explicit_ambiguity_signal"]))
    incomplete_count = sum(actual_incomplete)
    ambiguous_count = sum(actual_ambiguous)
    false_completions = sum(row["automatic_accounting_result"] is not None for row in records if row["reference_evidence_state"] == "incomplete")
    false_resolutions = sum(row["automatic_accounting_result"] is not None for row in records if row["reference_evidence_state"] == "ambiguous")
    result["metrics"]["carbon_critical_extraction"] = field_grounding["field_extraction"]
    result["metrics"]["evidence_grounding"] = field_grounding["evidence_grounding"]
    result["metrics"]["missing_evidence_detection"] = {
        "positive_class": "incomplete",
        "metrics": _binary_metrics(actual_incomplete, predicted_missing),
        "false_completion_rate": false_completions / incomplete_count if incomplete_count else None,
        "false_completion_count": false_completions,
        "denominator_incomplete_documents": incomplete_count,
        "prediction_is_generic_extractor_missing_status_proxy": True,
        "per_reference_state_signal_counts": {state: dict(counts) for state, counts in states.items()},
    }
    result["metrics"]["ambiguity_detection"] = {
        "positive_class": "ambiguous",
        "metrics": _binary_metrics(actual_ambiguous, predicted_ambiguous),
        "false_resolution_rate": false_resolutions / ambiguous_count if ambiguous_count else None,
        "false_resolution_count": false_resolutions,
        "denominator_ambiguous_documents": ambiguous_count,
        "strict_false_resolution_definition": "A system accounting result emitted without human clarification. The upload-only app emitted no result; unflagged scalar candidates are separately visible per document and do not count as an automatic proceeding result.",
        "review_required_rate": sum(bool(row["current_system_review_signal"]["review_required"]) for row in records) / len(records),
        "per_reference_state_signal_counts": {state: dict(counts) for state, counts in states.items()},
    }
    result["metrics"]["accounting_readiness"] = _readiness_metrics(records, annotations)
    result["metrics"]["difficulty_breakdown"] = _difficulty_breakdown(records, annotations)
    ready_records = [row for row in records if row["reference_evidence_state"] == "ready"]
    checks = [row["gold_input_accounting_diagnostic"] for row in ready_records]
    errors = [_decimal(row["absolute_error"]) for row in checks if row and row.get("absolute_error") is not None]
    relative = [_decimal(row["relative_error"]) for row in checks if row and row.get("relative_error") is not None]
    domains = {}
    for domain in CRITICAL_FIELDS:
        subset = [(record, record["gold_input_accounting_diagnostic"]) for record in ready_records if record["domain"] == domain]
        domains[domain] = {
            "ready_documents": len(subset),
            "correct_results": sum(bool(check and check.get("accounting_result_correct")) for _record, check in subset),
            "correct_factor_count": sum(bool(check and check.get("factor_correct")) for _record, check in subset),
            "correct_boundary_count": sum(bool(check and check.get("accounting_boundary_correct")) for _record, check in subset),
            "correct_gas_basis_count": sum(bool(check and check.get("gas_basis_correct")) for _record, check in subset),
            "correct_unit_count": sum(bool(check and check.get("unit_correct")) for _record, check in subset),
        }
    result["metrics"]["deterministic_accounting_gold_input_diagnostic"] = {
        "ready_documents": len(checks),
        "correct_accounting_result_rate": sum(bool(row and row.get("accounting_result_correct")) for row in checks) / len(checks) if checks else None,
        "correct_results": sum(bool(row and row.get("accounting_result_correct")) for row in checks),
        "exact_numeric_matches": sum(bool(row and row.get("exact_numeric_match")) for row in checks),
        "correct_factor_rate": sum(bool(row and row.get("factor_correct")) for row in checks) / len(checks) if checks else None,
        "correct_factor_count": sum(bool(row and row.get("factor_correct")) for row in checks),
        "correct_boundary_rate": sum(bool(row and row.get("accounting_boundary_correct")) for row in checks) / len(checks) if checks else None,
        "correct_boundary_count": sum(bool(row and row.get("accounting_boundary_correct")) for row in checks),
        "correct_gas_basis_rate": sum(bool(row and row.get("gas_basis_correct")) for row in checks) / len(checks) if checks else None,
        "correct_gas_basis_count": sum(bool(row and row.get("gas_basis_correct")) for row in checks),
        "correct_unit_rate": sum(bool(row and row.get("unit_correct")) for row in checks) / len(checks) if checks else None,
        "correct_unit_count": sum(bool(row and row.get("unit_correct")) for row in checks),
        "mean_absolute_error_kg": float(statistics.mean(errors)) if errors else None,
        "max_absolute_error_kg": float(max(errors)) if errors else None,
        "mean_relative_error": float(statistics.mean(relative)) if relative else None,
        "per_domain": domains,
        "independence_caveat": "Expected ready results were originally generated with the same deterministic accounting engine; this is a repeatability/applicability check, not independent factor validation.",
    }


def _prediction_digest(records: list[dict[str, Any]]) -> str:
    prediction_keys = (
        "document_id", "domain", "file", "file_sha256", "format", "page_count",
        "template_family", "layout_structure", "reference_evidence_state", "ocr",
        "extracted_fields", "proposed_critical_values", "field_statuses_used_for_review_metrics",
        "current_system_review_signal", "readiness_prediction", "readiness_limitation",
        "automatic_accounting_result", "automatic_accounting_reason",
        "latency_seconds", "failure_reason",
    )
    payload = [{key: row.get(key) for key in prediction_keys} for row in records]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _rescore_existing() -> None:
    marker, _manifest = verify_frozen_dataset()
    annotations = [json.loads(line) for line in (PILOT / "annotations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    result = json.loads(OUTPUT.read_text(encoding="utf-8"))
    policy = result.get("evaluation_policy", {})
    if policy.get("freeze_marker_sha256") != _sha256(PILOT / "FROZEN.json") or policy.get("annotations_sha256") != marker.get("annotations_sha256"):
        raise RuntimeError("Existing predictions do not cite the current frozen dataset hashes.")
    original_prediction_runner = result.get("runner_sha256")
    prediction_digest_before = _prediction_digest(result["per_document"])
    score_started = time.perf_counter()
    _recompute_metrics(result, annotations)
    prediction_digest_after = _prediction_digest(result["per_document"])
    result["prediction_runner_sha256"] = original_prediction_runner
    result["metric_scoring_script_sha256"] = _sha256(Path(__file__))
    result["metric_rescored_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["metric_rescore_seconds"] = time.perf_counter() - score_started
    result["environment"]["host_physical_memory_gb"] = _host_physical_memory_gb()
    result["environment"]["host_memory_measurement_note"] = "Installed physical RAM measured on the same host during metrics-only rescoring after the OCR run; not process peak memory."
    result["prediction_records_sha256"] = prediction_digest_before
    result["evaluation_policy"]["rescoring_reused_existing_ocr_and_extraction_predictions"] = True
    result["evaluation_policy"]["prediction_records_changed_during_rescore"] = prediction_digest_before != prediction_digest_after
    if prediction_digest_before != prediction_digest_after:
        raise RuntimeError("Prediction records unexpectedly changed during metrics-only rescore.")
    _json_write(OUTPUT, result)
    print("Metrics recomputed from recorded predictions; OCR/extraction was not rerun.", flush=True)
    print("Results updated: {}".format(OUTPUT.relative_to(ROOT)), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rescore-existing", action="store_true", help="Recompute evaluation metrics from the existing prediction file without rerunning OCR or extraction.")
    args = parser.parse_args()
    if args.rescore_existing:
        _rescore_existing()
        return
    overall_started = time.perf_counter()
    marker, manifest = verify_frozen_dataset()
    annotation_path = PILOT / "annotations.jsonl"
    annotations = [json.loads(line) for line in annotation_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(annotations) != 120:
        raise RuntimeError("Expected 120 frozen pilot annotations; found {}.".format(len(annotations)))
    docs = {row["document_id"]: row for row in manifest["documents"]}
    if set(docs) != {row["document_id"] for row in annotations}:
        raise RuntimeError("Manifest and frozen annotations do not have identical document IDs.")

    from greenledger.core import evaluate_submission
    from greenledger.field_extraction import extract_carbon_fields
    from greenledger.ocr import MAX_OCR_PAGES, MAX_PAGE_PIXELS, PDF_RENDER_SCALE, RAPIDOCR_MODEL_HASHES, get_ocr_runtime_status, recognize_upload
    from greenledger.ocr_eval import _package_version

    status = get_ocr_runtime_status()
    if not status.get("available"):
        raise RuntimeError("The existing OCR runtime is unavailable in this interpreter: {}".format(status.get("reason")))
    import onnxruntime

    records = []
    all_ocr_wall, all_ocr_reported, all_extract = [], [], []
    for index, annotation in enumerate(annotations, 1):
        manifest_row = docs[annotation["document_id"]]
        path = PILOT / manifest_row["file"]
        content = path.read_bytes()
        document_started = time.perf_counter()
        ocr_started = time.perf_counter()
        ocr_result = recognize_upload(content, path.name)
        ocr_wall = time.perf_counter() - ocr_started
        extract_started = time.perf_counter()
        extraction = extract_carbon_fields(ocr_result.get("transcription", "")) if ocr_result and ocr_result.get("transcription") else None
        extraction_wall = time.perf_counter() - extract_started
        document_wall = time.perf_counter() - document_started
        all_ocr_wall.append(ocr_wall)
        all_ocr_reported.append(float(ocr_result.get("latency_seconds") or 0.0) if ocr_result else 0.0)
        all_extract.append(extraction_wall)
        values = _predicted_values(extraction, annotation["domain"])
        statuses = _candidate_statuses(extraction)
        ambiguous_signal = "ambiguous" in statuses
        missing_signal = any(value in {"missing", "unresolved"} for value in statuses)
        records.append({
            "document_id": annotation["document_id"],
            "domain": annotation["domain"],
            "file": manifest_row["file"],
            "file_sha256": manifest_row["sha256"],
            "format": manifest_row["format"],
            "page_count": manifest_row["page_count"],
            "template_family": manifest_row.get("template_family"),
            "layout_structure": manifest_row.get("layout_structure"),
            "reference_evidence_state": annotation["evidence_state"],
            "ocr": ocr_result,
            "extracted_fields": extraction,
            "proposed_critical_values": values,
            "field_statuses_used_for_review_metrics": {"activity": statuses[0] if len(statuses) > 0 else None, "quantity": statuses[1] if len(statuses) > 1 else None, "unit": statuses[2] if len(statuses) > 2 else None},
            "current_system_review_signal": {
                "review_required": extraction.get("review_required") if extraction else None,
                "review_reasons": extraction.get("review_reasons") if extraction else [],
                "human_confirmation_required": extraction.get("human_confirmation_required") if extraction else True,
                "explicit_missing_evidence_signal": missing_signal if extraction else None,
                "explicit_ambiguity_signal": ambiguous_signal if extraction else None,
            },
            "readiness_prediction": "UNDETERMINED",
            "readiness_limitation": "Current upload path displays advisory fields and requires manual entry/confirmation; it does not emit a three-way readiness class.",
            "automatic_accounting_result": None,
            "automatic_accounting_reason": "No accounting fields were manually entered or confirmed; the current app does not submit OCR suggestions to evaluate_submission.",
            "gold_input_accounting_diagnostic": _accounting_gold_input_check(annotation) if annotation["evidence_state"] == "ready" else None,
            "latency_seconds": {"ocr_function_wall": ocr_wall, "ocr_reported_inference": float(ocr_result.get("latency_seconds") or 0.0) if ocr_result else None, "downstream_field_extraction": extraction_wall, "document_pipeline_wall": document_wall},
            "failure_reason": (ocr_result or {}).get("warning") if (ocr_result or {}).get("status") not in {"OCR_COMPLETE"} else None,
        })
        if index % 10 == 0 or index == len(annotations):
            print("Processed {}/{} pilot documents".format(index, len(annotations)), flush=True)

    result_by_id = {row["document_id"]: row for row in records}
    field_grounding = _system_grounding_and_metrics(records, annotations)
    # Retain scoring detail separately in the per-document records to make the JSON auditable.
    metric_by_id = defaultdict(list)
    for metric in field_grounding.pop("metric_rows"):
        metric_by_id[metric["document_id"]].append(metric)
    for row in records:
        row["scored_carbon_critical_fields"] = metric_by_id[row["document_id"]]

    actual_incomplete = [annotation["evidence_state"] == "incomplete" for annotation in annotations]
    predicted_missing = [bool(result_by_id[a["document_id"]]["current_system_review_signal"]["explicit_missing_evidence_signal"]) for a in annotations]
    actual_ambiguous = [annotation["evidence_state"] == "ambiguous" for annotation in annotations]
    predicted_ambiguous = [bool(result_by_id[a["document_id"]]["current_system_review_signal"]["explicit_ambiguity_signal"]) for a in annotations]
    review_required = [bool(result_by_id[a["document_id"]]["current_system_review_signal"]["review_required"]) for a in annotations]

    missed_or_extra = {"ready": Counter(), "incomplete": Counter(), "ambiguous": Counter()}
    for annotation in annotations:
        item = result_by_id[annotation["document_id"]]
        signal = item["current_system_review_signal"]
        missed_or_extra[annotation["evidence_state"]]["review_flagged"] += int(bool(signal["review_required"]))
        missed_or_extra[annotation["evidence_state"]]["missing_signal"] += int(bool(signal["explicit_missing_evidence_signal"]))
        missed_or_extra[annotation["evidence_state"]]["ambiguity_signal"] += int(bool(signal["explicit_ambiguity_signal"]))
    ready_docs = [row for row in records if row["reference_evidence_state"] == "ready"]
    account_checks = [row["gold_input_accounting_diagnostic"] for row in ready_docs]
    account_numeric_errors = [_decimal(row["absolute_error"]) for row in account_checks if row and row.get("absolute_error") is not None]
    account_relative_errors = [_decimal(row["relative_error"]) for row in account_checks if row and row.get("relative_error") is not None]
    account_count = len(account_checks)
    account_correct = sum(bool(row and row.get("accounting_result_correct")) for row in account_checks)
    factors_correct = sum(bool(row and row.get("factor_correct")) for row in account_checks)
    boundaries_correct = sum(bool(row and row.get("accounting_boundary_correct")) for row in account_checks)
    gas_basis_correct = sum(bool(row and row.get("gas_basis_correct")) for row in account_checks)
    unit_correct = sum(bool(row and row.get("unit_correct")) for row in account_checks)
    automatic_false_completions = sum(row["automatic_accounting_result"] is not None for row in records if row["reference_evidence_state"] == "incomplete")
    automatic_false_resolutions = sum(row["automatic_accounting_result"] is not None for row in records if row["reference_evidence_state"] == "ambiguous")

    ocr_failures = [row for row in records if row["ocr"].get("status") != "OCR_COMPLETE" or not row["ocr"].get("transcription", "").strip()]
    ocr_metrics = _anchor_ocr_metrics(records, annotations)
    total_wall = time.perf_counter() - overall_started
    try:
        providers = onnxruntime.get_available_providers()
    except Exception:
        providers = []
    try:
        import psutil
        total_memory_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        total_memory_gb = None

    by_domain_latency = {}
    by_state_latency = {}
    for key, getter in (("domain", lambda row: row["domain"]), ("evidence_state", lambda row: row["reference_evidence_state"])):
        groups = defaultdict(list)
        for row in records:
            groups[getter(row)].append(row)
        target = by_domain_latency if key == "domain" else by_state_latency
        for group, rows in groups.items():
            target[group] = {
                "ocr_function_wall": _percentile_summary([x["latency_seconds"]["ocr_function_wall"] for x in rows]),
                "downstream_field_extraction": _percentile_summary([x["latency_seconds"]["downstream_field_extraction"] for x in rows]),
                "document_pipeline_wall": _percentile_summary([x["latency_seconds"]["document_pipeline_wall"] for x in rows]),
            }

    result = {
        "benchmark_id": "greenledger_unseen_structure_pilot_120_current_pipeline_2026-11-15",
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED",
        "evaluation_policy": {
            "pilot_path": str(PILOT.relative_to(ROOT)).replace("\\", "/"),
            "freeze_marker_sha256": _sha256(PILOT / "FROZEN.json"),
            "manifest_sha256": marker["manifest_sha256"],
            "annotations_sha256": marker["annotations_sha256"],
            "all_freeze_hashes_verified_before_loading_annotations": True,
            "old_quarantined_test_split_accessed": False,
            "frozen_annotations_used_only_as_evaluation_ground_truth": True,
            "no_manual_prediction_corrections": True,
            "no_production_or_frozen_dataset_changes": True,
            "ground_truth_used_for_extraction_or_readiness": False,
            "gold_input_accounting_diagnostic_separate_from_pipeline_prediction": True,
            "evaluation_output_contains_ground_truth_derived_labels_and_is_not_training_data": True,
        },
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "host_physical_memory_gb": _host_physical_memory_gb() if total_memory_gb is None else total_memory_gb,
            "gpu_used": False,
            "gpu_note": "RapidOCR configuration uses ONNX Runtime CPU; no CUDA provider was selected.",
            "onnxruntime_available_providers": providers,
            "ocr_runtime": status,
            "packages": {name: _version(name) for name in ["rapidocr", "onnxruntime", "pypdfium2", "Pillow", "numpy", "psutil"]},
            "rapidocr_model_sha256": RAPIDOCR_MODEL_HASHES,
            "ocr_configuration": {"max_pages": MAX_OCR_PAGES, "pdf_render_scale": PDF_RENDER_SCALE, "max_page_pixels": MAX_PAGE_PIXELS, "intra_op_threads": 4, "inter_op_threads": 1},
            "peak_process_working_set_mb": _peak_working_set_mb(),
        },
        "dataset": {"documents": len(records), "pages": sum(row["page_count"] for row in records), "by_domain": dict(Counter(row["domain"] for row in records)), "by_evidence_state": dict(Counter(row["reference_evidence_state"] for row in records)), "by_format": dict(Counter(row["format"] for row in records)), "by_page_count": dict(Counter(str(row["page_count"]) for row in records)), "by_layout_family": dict(Counter(row["template_family"] for row in records)), "by_layout_structure": dict(Counter(row["layout_structure"] for row in records))},
        "protocol": {
            "pipeline": "greenledger.ocr.recognize_upload → greenledger.field_extraction.extract_carbon_fields, matching greenledger.web.py /ocr and /evaluate behavior; extracted suggestions remain advisory and are not submitted to accounting.",
            "candidate": "Current RapidOCR runtime plus conservative rule-only carbon-field extractor. No AI/VLM candidate was introduced.",
            "supported_extraction_outputs_scored": ["activity", "quantity", "unit"],
            "ignored_noncritical_outputs": ["supplier_name", "invoice_date"],
            "required_context_not_extracted_by_current_candidate": ["electricity_use", "geography", "billing_period", "vehicle/source/ownership/combustion context", "material_identity", "purchase_evidence", "transport_scenario", "transport_mode", "shipment_mass", "distance", "transport_vehicle_class"],
            "ocr_reference_limitation": "The pilot has field-level evidence text, not full-document OCR transcripts. Full-page CER/WER cannot be computed; anchor-CER/WER compares each carbon-critical evidence snippet with its closest OCR line on the annotated page.",
            "readiness_limitation": "The application has no automatic three-way readiness classifier; human fields and confirmation are required. Every upload-only case is therefore UNDETERMINED rather than assigned a guessed class.",
            "missing_signal_definition": "The existing extractor's activity/quantity/unit status is missing or unresolved. This generic signal is evaluated as a proxy, not a domain-complete missing-evidence detector.",
            "ambiguity_signal_definition": "The existing extractor marks activity, quantity, or unit status ambiguous. Other context conflicts are not inferred by the evaluator.",
            "accounting_diagnostic": "For ready cases only, frozen annotated values are mapped to the existing evaluate_submission fields with fields_confirmed=yes. These values never enter OCR/extraction/readiness predictions.",
        },
        "metrics": {
            "ocr": {
                "full_document_cer": None,
                "full_document_wer": None,
                "full_document_error_note": "No complete page transcription ground truth exists in pilot annotations.",
                "carbon_critical_evidence_anchor": ocr_metrics,
                "document_level_ocr_failures": len(ocr_failures),
                "failure_document_ids": [row["document_id"] for row in ocr_failures],
                "ocr_status_counts": dict(Counter(row["ocr"].get("status") for row in records)),
            },
            "carbon_critical_extraction": {k: v for k, v in field_grounding["field_extraction"].items()},
            "evidence_grounding": field_grounding["evidence_grounding"],
            "missing_evidence_detection": {
                "positive_class": "incomplete",
                "metrics": _binary_metrics(actual_incomplete, predicted_missing),
                "false_completion_rate": automatic_false_completions / sum(actual_incomplete) if any(actual_incomplete) else None,
                "false_completion_count": automatic_false_completions,
                "denominator_incomplete_documents": sum(actual_incomplete),
                "prediction_is_generic_extractor_missing_status_proxy": True,
                "per_reference_state_signal_counts": {state: dict(counts) for state, counts in missed_or_extra.items()},
            },
            "ambiguity_detection": {
                "positive_class": "ambiguous",
                "metrics": _binary_metrics(actual_ambiguous, predicted_ambiguous),
                "false_resolution_rate": automatic_false_resolutions / sum(actual_ambiguous) if any(actual_ambiguous) else None,
                "false_resolution_count": automatic_false_resolutions,
                "denominator_ambiguous_documents": sum(actual_ambiguous),
                "strict_false_resolution_definition": "A system accounting result emitted without human clarification. The upload-only app emitted no result; unflagged scalar candidates are separately visible per document and do not count as an automatic proceeding result.",
                "review_required_rate": sum(review_required) / len(review_required) if review_required else None,
                "per_reference_state_signal_counts": {state: dict(counts) for state, counts in missed_or_extra.items()},
            },
            "accounting_readiness": _readiness_metrics(records, annotations),
            "automatic_end_to_end_accounting": {"documents_with_result": 0, "reason": "The existing app requires manual entry and human confirmation; OCR candidates are advisory only."},
            "deterministic_accounting_gold_input_diagnostic": {
                "ready_documents": account_count,
                "correct_accounting_result_rate": account_correct / account_count if account_count else None,
                "correct_results": account_correct,
                "exact_numeric_matches": sum(bool(row and row.get("exact_numeric_match")) for row in account_checks),
                "correct_factor_rate": factors_correct / account_count if account_count else None,
                "correct_factor_count": factors_correct,
                "correct_boundary_rate": boundaries_correct / account_count if account_count else None,
                "correct_boundary_count": boundaries_correct,
                "correct_gas_basis_rate": gas_basis_correct / account_count if account_count else None,
                "correct_gas_basis_count": gas_basis_correct,
                "correct_unit_rate": unit_correct / account_count if account_count else None,
                "correct_unit_count": unit_correct,
                "mean_absolute_error_kg": float(statistics.mean(account_numeric_errors)) if account_numeric_errors else None,
                "max_absolute_error_kg": float(max(account_numeric_errors)) if account_numeric_errors else None,
                "mean_relative_error": float(statistics.mean(account_relative_errors)) if account_relative_errors else None,
                "per_domain": {
                    domain: {
                        "ready_documents": sum(row["domain"] == domain for row in ready_docs),
                        "correct_results": sum(row["domain"] == domain and bool(row["gold_input_accounting_diagnostic"].get("accounting_result_correct")) for row in ready_docs),
                        "correct_factor_count": sum(row["domain"] == domain and bool(row["gold_input_accounting_diagnostic"].get("factor_correct")) for row in ready_docs),
                        "correct_boundary_count": sum(row["domain"] == domain and bool(row["gold_input_accounting_diagnostic"].get("accounting_boundary_correct")) for row in ready_docs),
                        "correct_gas_basis_count": sum(row["domain"] == domain and bool(row["gold_input_accounting_diagnostic"].get("gas_basis_correct")) for row in ready_docs),
                        "correct_unit_count": sum(row["domain"] == domain and bool(row["gold_input_accounting_diagnostic"].get("unit_correct")) for row in ready_docs),
                    } for domain in CRITICAL_FIELDS
                },
                "independence_caveat": "Expected ready results were originally generated with the same deterministic accounting engine; this is a repeatability/applicability check, not independent factor validation.",
            },
            "latency_seconds": {
                "total_evaluation_wall": total_wall,
                "ocr_function_wall": _percentile_summary(all_ocr_wall),
                "ocr_reported_inference_only": _percentile_summary(all_ocr_reported),
                "downstream_field_extraction": _percentile_summary(all_extract),
                "document_pipeline_wall": _percentile_summary([row["latency_seconds"]["document_pipeline_wall"] for row in records]),
                "by_domain": by_domain_latency,
                "by_evidence_state": by_state_latency,
                "cold_start_note": "The first per-document OCR function wall time includes one-time OCR/model initialization; OCR-reported inference time excludes initialization and image decoding/rendering.",
            },
            "difficulty_breakdown": _difficulty_breakdown(records, annotations),
        },
        "per_document": records,
    }
    result["runner_sha256"] = _sha256(Path(__file__))
    _json_write(OUTPUT, result)
    print("Results written: {}".format(OUTPUT.relative_to(ROOT)), flush=True)
    print("Total evaluation wall: {:.2f} s; OCR failures: {}; gold-input accounting correct: {}/{}".format(total_wall, len(ocr_failures), account_correct, account_count), flush=True)


if __name__ == "__main__":
    main()
