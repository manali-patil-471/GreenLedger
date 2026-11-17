"""Experimental supervised line-role extractor; it never classifies scope or calculates emissions."""

import hashlib
import json
import math
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from greenledger.core import ValidationError, normalize_activity, normalize_quantity, normalize_unit
from greenledger.field_extraction import (
    ACTIVITY_LINE,
    DATE_LINE,
    LINE_NUMBER_PREFIX,
    NUMBER_PATTERN,
    QUANTITY_LINE,
    QUANTITY_DETAIL_PREFIX,
    SUPPLIER_LINE,
    UNIT_LINE,
    _date_iso,
    _document_activity,
    _parse_number,
    extract_carbon_fields,
)
from greenledger.ocr_eval import iter_jsonl_split_records


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "ai_field_extraction" / "char_ngram_line_role_v1.json"
FIELD_LABELS = (
    "activity_description",
    "quantity",
    "unit",
    "invoice_date",
    "supplier_name",
    "billing_period",
    "cylinder_net_mass",
    "vehicle_reference",
)
CLASS_LABELS = ("__other__",) + FIELD_LABELS
FEATURE_BUCKETS = 4096
NGRAM_RANGE = (2, 5)
MAX_MODEL_CLASSES = len(CLASS_LABELS)

FIELD_NAME_TO_LABEL = {name: name for name in FIELD_LABELS}


def searchable_line(line):
    """Normalize only an ordinal that precedes a label, never a numeric quantity line."""
    value = (line or "").strip()
    prefix = LINE_NUMBER_PREFIX.match(value)
    if prefix:
        remainder = value[prefix.end():].lstrip()
        if re.match(r"^[A-Za-z][A-Za-z /_.()\-]{0,48}\s*:", remainder):
            value = remainder
    return value


def normalized_line_key(line):
    value = unicodedata.normalize("NFKC", searchable_line(line)).casefold()
    return " ".join(value.split())


def char_ngram_features(text, feature_buckets=FEATURE_BUCKETS, ngram_range=NGRAM_RANGE):
    """Return stable hashed character n-gram features for a line."""
    normalized = unicodedata.normalize("NFKC", searchable_line(text)).casefold()
    normalized = " ^" + " ".join(normalized.split()) + "$ "
    counts = {}
    for size in range(ngram_range[0], ngram_range[1] + 1):
        for start in range(max(0, len(normalized) - size + 1)):
            gram = normalized[start:start + size]
            hashed = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(hashed, "big") % feature_buckets
            counts[index] = counts.get(index, 0) + 1
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return tuple((index, value / norm) for index, value in sorted(counts.items()))


def load_training_lines(root=ROOT):
    """Build line-role examples from training annotations only; evidence is matched to OCR lines."""
    root = Path(root).resolve()
    dataset_dir = root / "data" / "synthetic" / "greenledger_v0_1_1_partial"
    annotation_path = dataset_dir / "annotations.jsonl"
    samples = []
    document_ids = set()
    counts = {"documents": 0, "lines": 0, "positive_lines": 0, "unmatched_evidence": 0, "conflicting_evidence": 0}

    with annotation_path.open("r", encoding="utf-8") as source:
        for line_number, record in iter_jsonl_split_records(source, "train"):
            if record.get("source_type") != "synthetic":
                continue
            ground_truth = record.get("ground_truth", {})
            transcription = ground_truth.get("ocr", {}).get("transcription")
            if not isinstance(transcription, str):
                continue

            lines = [line.strip() for line in transcription.splitlines() if line.strip()]
            field_by_line = {}
            for field in ground_truth.get("fields", []):
                field_name = field.get("field_name")
                if field_name not in FIELD_NAME_TO_LABEL or field.get("presence_status") != "present":
                    continue
                evidence = field.get("evidence_text")
                if not evidence:
                    counts["unmatched_evidence"] += 1
                    continue
                evidence_key = normalized_line_key(evidence)
                matching_indices = [index for index, text in enumerate(lines) if normalized_line_key(text) == evidence_key]
                if not matching_indices:
                    counts["unmatched_evidence"] += 1
                    continue
                for index in matching_indices:
                    current = field_by_line.get(index)
                    if current and current != field_name:
                        counts["conflicting_evidence"] += 1
                        field_by_line[index] = "__other__"
                    elif current is None:
                        field_by_line[index] = field_name

            for index, text in enumerate(lines):
                label = field_by_line.get(index, "__other__")
                samples.append((searchable_line(text), label, record["document_id"]))
                counts["lines"] += 1
                counts["positive_lines"] += label != "__other__"
            counts["documents"] += 1
            document_ids.add(record["document_id"])

    if not samples or counts["documents"] != 325:
        raise ValueError("Expected the manifest's 325 training documents; got {}.".format(counts["documents"]))
    if counts["unmatched_evidence"] or counts["conflicting_evidence"]:
        raise ValueError("Training evidence alignment failed: {}".format(counts))
    return samples, counts


def load_line_model(path=DEFAULT_MODEL_PATH):
    path = Path(path)
    model = json.loads(path.read_text(encoding="utf-8"))
    if model.get("model_id") != "greenledger_char_ngram_line_role_v1":
        raise ValueError("Unsupported GreenLedger line-extractor model.")
    if model.get("training_split") != "train":
        raise ValueError("AI extractor artifacts must be trained only on the training split.")
    if model.get("labels") != list(CLASS_LABELS):
        raise ValueError("AI extractor label set does not match the current schema mapping.")
    if len(model.get("weights", [])) != MAX_MODEL_CLASSES:
        raise ValueError("AI extractor weight rows are malformed.")
    return model


def _predict_line(line, model):
    features = char_ngram_features(
        line,
        feature_buckets=int(model["feature_buckets"]),
        ngram_range=tuple(model["ngram_range"]),
    )
    biases = model["bias"]
    weights = model["weights"]
    scores = [float(bias) for bias in biases]
    for feature_index, value in features:
        for class_index in range(len(scores)):
            scores[class_index] += float(weights[class_index][feature_index]) * value
    return CLASS_LABELS[max(range(len(scores)), key=scores.__getitem__)]


def _after_label(line):
    searchable = searchable_line(line)
    return searchable.split(":", 1)[1].strip() if ":" in searchable else searchable


def _one_candidate(lines_by_field, field_name):
    matches = lines_by_field.get(field_name, [])
    if not matches:
        return None, "missing"
    if len(matches) != 1:
        return None, "ambiguous"
    return matches[0], "extracted"


def _quantity_from_line(line):
    searchable = searchable_line(line)
    match = QUANTITY_LINE.match(searchable)
    payload = match.group(1).strip() if match else searchable
    while True:
        stripped = QUANTITY_DETAIL_PREFIX.sub("", payload, count=1)
        if stripped == payload:
            break
        payload = stripped.strip()
    quantity = _parse_number(payload)
    unit = NUMBER_PATTERN.sub(" ", payload, count=1).strip(" \t:;,.|") if quantity is not None else None
    return quantity, unit


def _field_value(lines_by_field, name):
    line, status = _one_candidate(lines_by_field, name)
    if line is None:
        return {"value": None, "raw_text": None, "evidence_text": None, "status": status}
    raw = _after_label(line)
    return {"value": raw or None, "raw_text": raw or None, "evidence_text": line, "status": "extracted" if raw else "unresolved"}


def extract_ai_carbon_fields(transcription, model=None, model_path=DEFAULT_MODEL_PATH):
    """Return model-assisted field candidates only; all are unconfirmed and never authorize accounting."""
    model = model or load_line_model(model_path)
    lines = [line.strip() for line in (transcription or "").splitlines() if line.strip()]
    lines_by_field = {name: [] for name in FIELD_LABELS}
    for line in lines:
        predicted_label = _predict_line(line, model)
        if predicted_label in lines_by_field:
            lines_by_field[predicted_label].append(line)

    activity_description = _field_value(lines_by_field, "activity_description")
    quantity_line, quantity_line_status = _one_candidate(lines_by_field, "quantity")
    quantity_value, inline_unit = _quantity_from_line(quantity_line) if quantity_line else (None, None)
    quantity_status = quantity_line_status
    if quantity_line and quantity_value is None:
        quantity_status = "unresolved"

    activity_id, activity_ambiguous = _document_activity(transcription or "")
    if activity_description.get("value"):
        try:
            activity_id = normalize_activity(activity_description["value"])["id"]
            activity_ambiguous = False
        except ValidationError:
            pass
    if activity_ambiguous:
        activity_id = None

    quantity = None
    canonical_unit = None
    conversion_trace = None
    input_unit = None
    if inline_unit:
        input_unit = inline_unit
    unit_line, unit_line_status = _one_candidate(lines_by_field, "unit")
    if unit_line:
        parsed = UNIT_LINE.match(searchable_line(unit_line))
        input_unit = parsed.group(1).strip() if parsed else _after_label(unit_line)
    unit_status = unit_line_status if unit_line else ("extracted" if inline_unit else "missing")
    normalized_unit = None
    if input_unit and activity_id:
        try:
            activity = normalize_activity(activity_id)
            normalized_input_unit = normalize_unit(activity, input_unit)
            if quantity_value is not None:
                quantity, canonical_unit, conversion_trace = normalize_quantity(activity, quantity_value, normalized_input_unit)
                if quantity is None:
                    unit_status = "unresolved"
            else:
                _placeholder, canonical_unit, conversion_trace = normalize_quantity(activity, Decimal("1"), normalized_input_unit)
            normalized_unit = canonical_unit
        except ValidationError:
            unit_status = "unresolved"

    date_candidate = _field_value(lines_by_field, "invoice_date")
    date_value = _date_iso(date_candidate["value"]) if date_candidate["value"] else None
    if date_candidate["value"] and not date_value:
        date_candidate["status"] = "unresolved"

    supplier = _field_value(lines_by_field, "supplier_name")
    billing_period = _field_value(lines_by_field, "billing_period")
    cylinder_mass = _field_value(lines_by_field, "cylinder_net_mass")
    vehicle_reference = _field_value(lines_by_field, "vehicle_reference")
    document = normalize_activity(activity_id) if activity_id else None

    # Even unambiguous model output is a suggestion. There is no calibrated confidence model.
    return {
        "extractor": "greenledger_char_ngram_line_role_v1",
        "document_type": (document.get("document_types") or [None])[0] if document else None,
        "activity": {"value": activity_id, "status": "extracted" if activity_id else "missing"},
        "activity_description": activity_description,
        "supplier_name": supplier,
        "invoice_date": {
            "value": date_value,
            "raw_text": date_candidate.get("value"),
            "evidence_text": date_candidate.get("evidence_text"),
            "status": date_candidate.get("status"),
        },
        "billing_period": billing_period,
        "quantity": {
            "value": str(quantity_value) if quantity_value is not None else None,
            "normalized_value": str(quantity) if quantity is not None else None,
            "unit": canonical_unit,
            "raw_text": str(quantity_value) if quantity_value is not None else None,
            "evidence_text": quantity_line,
            "conversion_trace": conversion_trace,
            "status": quantity_status,
            "normalization_status": "resolved" if quantity is not None else "unresolved" if quantity_value is not None else "not_attempted",
        },
        "unit": {
            "value": normalized_unit,
            "raw_text": input_unit,
            "evidence_text": unit_line or quantity_line,
            "normalization_error": None if unit_status == "extracted" else "The model did not identify a uniquely normalizable unit.",
            "status": unit_status,
        },
        "cylinder_net_mass": cylinder_mass,
        "vehicle_reference": vehicle_reference,
        "confidence": None,
        "confidence_note": "Model scores are not calibrated and are not returned as probabilities.",
        "human_confirmation_required": True,
        "review_required": True,
        "review_reasons": ["AI field suggestions require human verification; no calibrated confidence is available."],
    }
