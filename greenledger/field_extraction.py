"""Conservative rule-only carbon-field baseline; it never assigns factors or emissions."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from greenledger.core import ValidationError, load_activities, normalize_activity, normalize_quantity, normalize_unit


DOCUMENT_PATTERNS = {
    "purchased_electricity": re.compile(r"\b(?:electricity|grid power|active energy|kwh|mwh)\b", re.I),
    "diesel_fuel": re.compile(r"\b(?:diesel|high[ -]?speed diesel|hsd)\b", re.I),
    "lpg": re.compile(r"\b(?:lpg|liquefied petroleum gas|propane|cooking gas refill)\b", re.I),
}
SUPPLIER_LINE = re.compile(r"^\s*(?:supplier|vendor)\s*:\s*(.*?)\s*$", re.I)
DATE_LINE = re.compile(r"^\s*(?:issue date|invoice date|supply date|date)\s*:\s*(.*?)\s*$", re.I)
ACTIVITY_LINE = re.compile(r"^\s*(?:energy charge|product|activity)\s*:\s*(.*?)\s*$", re.I)
QUANTITY_LINE = re.compile(
    r"^\s*(?:total active energy|energy used|units billed|consumption|usage|fuel quantity|"
    r"volume supplied|volume|qty supplied|net lpg|product mass|quantity supplied|"
    r"units delivered|refill count|quantity)\s*:\s*(.*?)\s*$",
    re.I,
)
QUANTITY_DETAIL_PREFIX = re.compile(
    r"^\s*(?:fuel quantity|quantity supplied|qty supplied|qty|volume supplied|volume|"
    r"net lpg|product mass|units delivered|cylinder qty|refill count|quantity)\s*:\s*",
    re.I,
)
UNIT_LINE = re.compile(r"^\s*(?:quantity unit|activity unit|unit|uom)\s*:\s*(.*?)\s*$", re.I)
NUMBER_PATTERN = re.compile(r"(?<![\w])(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?(?!\w)")
LINE_NUMBER_PREFIX = re.compile(r"^\s*\d{1,3}[.)]?\s+(?=\D)")
UNIT_QUALIFIED_QUANTITY_PATTERNS = {
    "purchased_electricity": re.compile(r"(?<![\w/])(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?)\s+(?P<unit>kwh|mwh)\b", re.I),
    "diesel_fuel": re.compile(r"(?<![\w/])(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?)\s+(?P<unit>litres?|liters?|ml|kl|l)\b", re.I),
    "lpg": re.compile(r"(?<![\w/])(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?)\s+(?P<unit>kilograms?|kg)\b", re.I),
}
NON_QUANTITY_CONTEXT = re.compile(r"\b(?:rate|tariff|price|amount|total|tax|balance|invoice|account|meter|payment|due)\b|(?:inr|rs\.?|₹)", re.I)
NUMBERED_LABEL = re.compile(r"^[A-Za-z][A-Za-z /_.()\-]{0,48}\s*:")


def _searchable_line(line):
    """Strip a layout ordinal only when it precedes a colon-terminated field label."""
    match = LINE_NUMBER_PREFIX.match(line)
    if not match:
        return line
    remainder = line[match.end():].lstrip()
    return remainder if NUMBERED_LABEL.match(remainder) else line


def _one_value(lines, pattern):
    matches = []
    for line in lines:
        searchable = _searchable_line(line)
        match = pattern.match(searchable)
        if match and match.group(1).strip():
            # Keep the unmodified OCR line as evidence while matching a layout-normalized view.
            matches.append((line, match.group(1).strip()))
    distinct = {value.casefold() for _line, value in matches}
    if len(distinct) == 1:
        return matches[0][0], matches[0][1], False
    return (None, None, len(distinct) > 1)


def _unit_qualified_quantity(lines, activity_id):
    """Recover one explicit, activity-compatible quantity when its label is unknown or absent."""
    pattern = UNIT_QUALIFIED_QUANTITY_PATTERNS.get(activity_id)
    if pattern is None:
        return None, None, False
    matches = []
    for line in lines:
        searchable = _searchable_line(line)
        if NON_QUANTITY_CONTEXT.search(searchable):
            continue
        found = list(pattern.finditer(searchable))
        if len(found) == 1:
            match = found[0]
            matches.append((line, match.group(0).strip()))
        elif len(found) > 1:
            return None, None, True
    if len(matches) == 1:
        return matches[0][0], matches[0][1], False
    return None, None, len(matches) > 1


def _document_activity(text):
    found = [activity_id for activity_id, pattern in DOCUMENT_PATTERNS.items() if pattern.search(text or "")]
    return (found[0], False) if len(found) == 1 else (None, len(found) > 1)


def _parse_number(raw):
    candidates = NUMBER_PATTERN.findall(raw or "")
    if len(candidates) != 1:
        return None
    value_text = candidates[0]
    if "," in value_text and "." in value_text:
        if value_text.rfind(",") > value_text.rfind("."):
            return None  # Ambiguous locale format: refuse to infer thousands/decimal order.
        value_text = value_text.replace(",", "")
    elif "," in value_text:
        integer, decimal = value_text.split(",", 1)
        if len(decimal) == 3 and len(integer) <= 3:
            value_text = integer + decimal
        else:
            value_text = integer + "." + decimal
    try:
        value = Decimal(value_text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value


def _quantity_payload(raw):
    value = (raw or "").strip()
    while True:
        stripped = QUANTITY_DETAIL_PREFIX.sub("", value, count=1)
        if stripped == value:
            return value
        value = stripped.strip()


def _date_iso(raw):
    value = (raw or "").strip()
    formats = (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y",
        "%d-%B-%Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    )
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _status(value, ambiguous=False, unresolved=False):
    if ambiguous:
        return "ambiguous"
    if unresolved:
        return "unresolved"
    return "extracted" if value not in (None, "") else "missing"


def extract_carbon_fields(transcription):
    """Return cautious candidates and explicit review reasons from OCR text only."""
    lines = [line.strip() for line in (transcription or "").splitlines() if line.strip()]
    text = "\n".join(lines)
    supplier_evidence, supplier, supplier_ambiguous = _one_value(lines, SUPPLIER_LINE)
    date_evidence, date_raw, date_ambiguous = _one_value(lines, DATE_LINE)
    activity_evidence, activity_raw, activity_ambiguous = _one_value(lines, ACTIVITY_LINE)
    quantity_evidence, quantity_raw, quantity_ambiguous = _one_value(lines, QUANTITY_LINE)
    unit_evidence, unit_raw, unit_ambiguous = _one_value(lines, UNIT_LINE)
    document_activity, document_ambiguous = _document_activity(text)

    activity_id = None
    if activity_raw:
        try:
            activity_id = normalize_activity(activity_raw)["id"]
        except ValidationError:
            activity_id = document_activity
    else:
        activity_id = document_activity

    if quantity_raw is None and not quantity_ambiguous and activity_id:
        fallback_evidence, fallback_raw, fallback_ambiguous = _unit_qualified_quantity(lines, activity_id)
        if fallback_raw is not None:
            quantity_evidence, quantity_raw = fallback_evidence, fallback_raw
        quantity_ambiguous = quantity_ambiguous or fallback_ambiguous

    quantity_payload = _quantity_payload(quantity_raw)
    quantity = _parse_number(quantity_payload)
    quantity_ambiguous = quantity_ambiguous or bool(quantity_raw and quantity is None)
    if unit_raw is None and quantity_raw:
        inline_unit = NUMBER_PATTERN.sub(" ", quantity_payload, count=1).strip(" \t:;,.|")
        if inline_unit and re.search(r"[A-Za-z]", inline_unit):
            unit_raw = inline_unit
            unit_evidence = quantity_evidence

    normalized_quantity = None
    normalized_unit = None
    conversion_trace = None
    unit_error = None
    if quantity is not None and unit_raw and activity_id:
        try:
            activity = normalize_activity(activity_id)
            normalized_input_unit = normalize_unit(activity, unit_raw)
            normalized_quantity, normalized_unit, conversion_trace = normalize_quantity(activity, quantity, normalized_input_unit)
            if normalized_quantity is None:
                unit_error = "No documented conversion is available for this unit."
        except ValidationError as error:
            unit_error = str(error)
    elif quantity is not None and not unit_raw:
        unit_error = "The document does not state a unit; no unit was inferred."

    date_value = _date_iso(date_raw)
    reasons = []
    if not activity_id or document_ambiguous or activity_ambiguous:
        reasons.append("Activity/document type is missing or ambiguous.")
    if quantity_ambiguous or quantity is None:
        reasons.append("Quantity is missing or ambiguous.")
    if unit_ambiguous or not unit_raw or unit_error:
        reasons.append(unit_error or "Unit is missing or ambiguous.")
    if date_ambiguous or (date_raw and not date_value):
        reasons.append("Document date is missing or could not be normalized unambiguously.")

    activity_definition = next((item for item in load_activities() if item["id"] == activity_id), None)
    return {
        "extractor": "greenledger_conservative_rules_v1",
        "document_type": (activity_definition.get("document_types") or [None])[0] if activity_definition else None,
        "activity": {
            "value": activity_id,
            "raw_text": activity_raw,
            "evidence_text": activity_evidence,
            "status": _status(activity_id, document_ambiguous or activity_ambiguous),
        },
        "supplier_name": {
            "value": supplier,
            "evidence_text": supplier_evidence,
            "status": _status(supplier, supplier_ambiguous),
        },
        "invoice_date": {
            "value": date_value,
            "raw_text": date_raw,
            "evidence_text": date_evidence,
            "status": _status(date_value, date_ambiguous, bool(date_raw and not date_value)),
        },
        "quantity": {
            "value": str(quantity) if quantity is not None else None,
            "normalized_value": str(normalized_quantity) if normalized_quantity is not None else None,
            "unit": normalized_unit,
            "raw_text": quantity_raw,
            "evidence_text": quantity_evidence,
            "conversion_trace": conversion_trace,
            "status": _status(quantity, quantity_ambiguous),
            "normalization_status": "resolved" if normalized_quantity is not None else "unresolved" if quantity is not None else "not_attempted",
        },
        "unit": {
            "value": normalized_unit,
            "raw_text": unit_raw,
            "evidence_text": unit_evidence,
            "normalization_error": unit_error,
            "status": _status(normalized_unit, unit_ambiguous, bool(unit_raw and unit_error)),
        },
        "confidence": None,
        "confidence_note": "No numeric confidence is calibrated. Field states describe rule evidence and normalization only; human verification is required.",
        "human_confirmation_required": True,
        "review_required": bool(reasons),
        "review_reasons": list(dict.fromkeys(reasons)),
    }
