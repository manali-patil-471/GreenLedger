"""Benchmark-only PaddleOCR-VL 1.6 adapter.

The model receives document bytes (written temporarily under an opaque generic
filename) through the existing candidate-only interface. This adapter maps the
official page/layout parse into GreenLedger's evidence-only contract; it never
receives annotations and never emits accounting factors or results.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Iterable

from .candidate_interface import CandidateDocumentInput
from .contract import (
    Ambiguity,
    BoundingBox,
    DocumentPrediction,
    EvidenceReference,
    FieldCandidate,
    FieldPrediction,
    MissingEvidence,
    ModelMetadata,
    ReviewSignal,
    validate_prediction,
)


ADAPTER_VERSION = "paddleocr-vl-1.6-contract-v1"
MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"
PIPELINE_MODEL_NAME = "PaddleOCR-VL-1.6-0.9B"

_MEDIA_SUFFIX = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}

_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?"
_MEASURE = re.compile(
    rf"(?P<number>{_NUMBER})\s*(?P<unit>kwh|mwh|kilograms?|kg|tonnes?|metric tons?|tons?|t|"
    rf"litres?|liters?|kl|ml|km|kilomet(?:er|re)s?|miles?)\b",
    re.IGNORECASE,
)
_DOMAIN_PATTERNS = {
    "electricity": re.compile(r"\b(?:purchased electricity|electricity|grid power|active energy|kwh|mwh)\b", re.I),
    "diesel": re.compile(r"\b(?:diesel|high[ -]?speed diesel|hsd)\b", re.I),
    "lpg": re.compile(r"\b(?:lpg|liquefied petroleum gas|propane|cooking gas refill)\b", re.I),
    "materials": re.compile(r"\b(?:ppc cement|portland pozzolana cement|steel rebar|rebar|tmt bars?|generic steel|cement|steel)\b", re.I),
    "freight": re.compile(r"\b(?:road freight|freight|consignment|lorry receipt|shipment|cargo manifest|transport of goods)\b", re.I),
}

_FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "document_type": ("document type", "document category", "record type"),
    "supplier_name": ("supplier", "vendor", "seller", "service provider", "issued by", "carrier"),
    "document_date": ("invoice date", "issue date", "supply date", "document date", "date"),
    "billing_period": ("billing period", "bill period", "period covered", "service period", "metering period"),
    "activity_description": ("activity", "product", "item description", "goods description", "fuel grade", "commodity", "description"),
    "quantity": ("energy consumption", "total active energy", "units billed", "consumption", "fuel quantity", "volume supplied", "quantity supplied", "net quantity", "quantity", "qty", "volume"),
    "net_lpg_mass": ("net lpg mass", "net lpg", "net contents", "net content", "net mass", "filled mass", "product mass"),
    "material_identity": ("material", "material description", "product", "item description", "goods description", "commodity"),
    "geography": ("service location", "supply location", "site location", "delivery location", "origin", "destination", "location", "state", "region"),
    "electricity_use": ("electricity use", "energy source", "supply type", "grid supply", "connection type"),
    "vehicle_reference": ("vehicle reference", "vehicle no", "vehicle number", "registration", "registration no", "truck no", "vehicle"),
    "source_type": ("source type", "fuel source", "source", "supply source"),
    "combustion_status": ("combustion", "combusted in", "end use", "usage type", "use type"),
    "operational_control": ("operational control", "owned or controlled", "control status", "ownership"),
    "commercial_institutional": ("commercial", "institutional", "consumer type", "customer type", "establishment type"),
    "purchase_evidence": ("purchase order", "purchase invoice", "purchase evidence", "procurement", "goods received", "purchase"),
    "transport_mode": ("transport mode", "mode", "mode of transport", "road mode"),
    "transport_scenario": ("transport scenario", "business flow", "shipment type", "movement type", "dispatch type"),
    "shipment_mass": ("shipment mass", "shipment weight", "cargo mass", "cargo weight", "load weight", "goods weight", "gross weight", "net weight"),
    "distance": ("distance", "route length", "route distance", "trip distance", "travelled distance"),
    "transport_vehicle_class": ("vehicle class", "gvw class", "gross vehicle weight class", "vehicle category"),
}

_REQUIRED_FIELDS = {
    "electricity": ("activity_description", "quantity", "unit", "electricity_use", "geography", "billing_period"),
    "diesel": ("activity_description", "quantity", "unit", "geography", "vehicle_reference", "source_type", "combustion_status", "operational_control"),
    "lpg": ("activity_description", "net_lpg_mass", "unit", "geography", "combustion_status", "operational_control", "source_type", "commercial_institutional"),
    "materials": ("activity_description", "material_identity", "quantity", "unit", "geography", "purchase_evidence"),
    "freight": ("activity_description", "geography", "transport_mode", "transport_scenario", "shipment_mass", "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class"),
}

_UNIT_NORMALIZATION = {
    "kwh": "kWh", "mwh": "MWh", "l": "L", "litre": "L", "litres": "L",
    "liter": "L", "liters": "L", "kl": "kL", "ml": "mL", "kg": "kg",
    "kilogram": "kg", "kilograms": "kg", "t": "t", "tonne": "t", "tonnes": "t",
    "ton": "t", "tons": "t", "metric ton": "t", "metric tons": "t", "km": "km",
    "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km",
    "mile": "mile", "miles": "mile",
}

_MATERIALS = (
    ("ppc_cement", re.compile(r"\b(?:ppc cement|portland pozzolana cement)\b", re.I)),
    ("steel_rebar", re.compile(r"\b(?:steel rebar|rebar|tmt bars?)\b", re.I)),
    ("generic_steel", re.compile(r"\bgeneric steel\b", re.I)),
)


@dataclass(frozen=True)
class _Block:
    text: str
    page: int
    label: str | None
    bbox: BoundingBox | None

    def evidence(self) -> EvidenceReference:
        return EvidenceReference(text=self.text, page=self.page, bounding_box=self.bbox)


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj.get(key, default)
    except Exception:
        return getattr(obj, key, default)


def _to_plain(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _result_data(result: Any) -> dict[str, Any]:
    data = getattr(result, "json", None)
    if callable(data):
        data = data()
    if data is None:
        data = getattr(result, "res", None)
    if data is None and isinstance(result, dict):
        data = result
    if not isinstance(data, dict):
        raise ValueError("PaddleOCR-VL returned a page result without structured JSON data.")
    inner = data.get("res", data)
    if not isinstance(inner, dict):
        raise ValueError("PaddleOCR-VL page result has an invalid 'res' object.")
    return inner


def _normalized_bbox(raw_bbox: Any, width: Any, height: Any) -> BoundingBox | None:
    try:
        values = [float(value) for value in _to_plain(raw_bbox)]
        page_width, page_height = float(width), float(height)
    except (TypeError, ValueError):
        return None
    if len(values) < 4 or page_width <= 0 or page_height <= 0:
        return None
    x0, y0, x1, y1 = values[:4]
    x = max(0.0, min(1.0, x0 / page_width))
    y = max(0.0, min(1.0, y0 / page_height))
    right = max(x, min(1.0, x1 / page_width))
    bottom = max(y, min(1.0, y1 / page_height))
    return BoundingBox(x=x, y=y, width=right - x, height=bottom - y)


def parse_page_results(results: Iterable[Any]) -> tuple[list[_Block], list[dict[str, Any]]]:
    """Convert official PaddleOCR-VL page results without inventing anchors."""
    blocks: list[_Block] = []
    pages: list[dict[str, Any]] = []
    for fallback_index, result in enumerate(results):
        data = _result_data(result)
        raw_page = data.get("page_index")
        page = int(raw_page) + 1 if isinstance(raw_page, (int, float)) else fallback_index + 1
        width, height = data.get("width"), data.get("height")
        page_blocks: list[dict[str, Any]] = []
        for item in data.get("parsing_res_list") or []:
            content = _value(item, "block_content", _value(item, "content", ""))
            if not isinstance(content, str) or not content.strip():
                continue
            raw_bbox = _value(item, "block_bbox", _value(item, "bbox"))
            bbox = _normalized_bbox(raw_bbox, width, height)
            label = _value(item, "block_label", _value(item, "label"))
            block = _Block(content.strip(), page, str(label) if label is not None else None, bbox)
            blocks.append(block)
            page_blocks.append({
                "text": block.text,
                "label": block.label,
                "page": page,
                "bounding_box": block.bbox.to_dict() if block.bbox else None,
            })
        pages.append({
            "page": page,
            "page_index_raw": raw_page,
            "width": width,
            "height": height,
            "blocks": page_blocks,
        })
    return blocks, pages


def _lines(blocks: list[_Block]) -> list[tuple[str, _Block]]:
    result: list[tuple[str, _Block]] = []
    for block in blocks:
        table_headers: list[str] | None = None
        for raw_line in block.text.splitlines():
            line = raw_line.strip().strip("| ").strip()
            if not line or re.fullmatch(r"[-:| ]+", line):
                continue
            cells = [cell.strip() for cell in raw_line.split("|") if cell.strip()]
            if len(cells) >= 2 and all(re.fullmatch(r"[-: ]+", cell or "-") for cell in cells):
                continue
            if len(cells) >= 2 and any(re.search(r"\b(?:material|product|description|qty|quantity|mass|weight|distance|route|unit|consumption|amount)\b", cell, re.I) for cell in cells):
                table_headers = cells
                continue
            if table_headers and len(cells) == len(table_headers):
                aliases = []
                for header in table_headers:
                    folded = header.casefold()
                    if re.search(r"material|product|description|commodity|item", folded):
                        aliases.append("Material")
                    elif re.search(r"distance|route", folded):
                        aliases.append("Distance")
                    elif re.search(r"shipment|cargo|gross|net|mass|weight", folded):
                        aliases.append("Shipment mass")
                    elif re.search(r"unit|uom", folded):
                        aliases.append("Unit")
                    elif re.search(r"qty|quantity|consumption|volume", folded):
                        aliases.append("Quantity")
                    else:
                        aliases.append(header)
                for header, cell in zip(aliases, cells):
                    if header.casefold() in {"material", "distance", "shipment mass", "unit", "quantity"} and cell:
                        result.append((f"{header}: {cell}", block))
                continue
            if len(cells) == 2 and not re.search(r"\d", cells[0]):
                line = f"{cells[0]}: {cells[1]}"
            result.append((line, block))
    return result


def _decimal_string(raw: str) -> str | None:
    value = raw.strip().replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            return None
        value = value.replace(",", "")
    elif "," in value:
        left, right = value.split(",", 1)
        value = left + right if len(right) == 3 and len(left) <= 3 else left + "." + right
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    return format(number.normalize(), "f")


def _label_pattern(labels: tuple[str, ...]) -> re.Pattern[str]:
    labels_expr = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    return re.compile(rf"^\s*(?:{labels_expr})\s*(?:[:=#]|\s+-\s*)\s*(?P<value>.+?)\s*$", re.I)


def _field_candidates(
    name: str,
    matches: list[tuple[str, str | None, str | None, _Block]],
    *,
    source_status: str = "paddleocr_vl_text_parse",
    reason: str | None = None,
) -> FieldPrediction:
    # Collapse repeated identical values while retaining each independently
    # observed evidence anchor. Distinct values remain explicitly ambiguous.
    grouped: dict[tuple[str, str | None], list[tuple[str, str | None, str | None, _Block]]] = {}
    for raw, normalized, unit, block in matches:
        key_value = normalized if normalized is not None else raw.casefold().strip()
        grouped.setdefault((key_value, unit), []).append((raw, normalized, unit, block))
    candidates: list[FieldCandidate] = []
    for group in grouped.values():
        first = group[0]
        evidence = tuple(dict.fromkeys(item[3].evidence() for item in group))
        candidates.append(FieldCandidate(
            raw_value=first[0],
            normalized_value=first[1],
            raw_unit=first[2],
            normalized_unit=first[2],
            confidence=None,
            evidence=evidence,
        ))
    if not candidates:
        return FieldPrediction(name, "MISSING", "NO_CANDIDATE", (), source_status, reason or "No matching candidate evidence was found in parsed page blocks.")
    if len(candidates) > 1:
        return FieldPrediction(name, "AMBIGUOUS", "MULTIPLE_CANDIDATES", tuple(candidates), source_status, reason or "Multiple distinct evidence-backed values were parsed.")
    candidate = candidates[0]
    if candidate.normalized_value is None:
        status = "INSUFFICIENT"
        reason = reason or "Evidence was found but the value could not be normalized without guessing."
    else:
        status = "PRESENT"
    return FieldPrediction(name, status, "SINGLE_CANDIDATE", tuple(candidates), source_status, reason)


def _find_label_values(lines: list[tuple[str, _Block]], field: str) -> list[tuple[str, str | None, str | None, _Block]]:
    pattern = _label_pattern(_FIELD_LABELS[field])
    output: list[tuple[str, str | None, str | None, _Block]] = []
    for line, block in lines:
        match = pattern.match(line)
        if not match:
            continue
        raw = match.group("value").strip().strip("|;,")
        unit_match = _MEASURE.search(raw)
        unit = _UNIT_NORMALIZATION.get(unit_match.group("unit").casefold()) if unit_match else None
        numeric = _decimal_string(unit_match.group("number")) if unit_match else None
        normalized: str | None = numeric if numeric is not None else raw
        if field in {"quantity", "net_lpg_mass", "shipment_mass", "distance"}:
            if unit_match is None:
                number_match = re.search(_NUMBER, raw)
                numeric = _decimal_string(number_match.group(0)) if number_match else None
                normalized = numeric
            output.append((raw, normalized, unit, block))
        else:
            output.append((raw, raw, None, block))
    return output


def _extract_domain(blocks: list[_Block], lines: list[tuple[str, _Block]]) -> FieldPrediction:
    text = "\n".join(block.text for block in blocks)
    matches: list[tuple[str, str | None, str | None, _Block]] = []
    for domain, pattern in _DOMAIN_PATTERNS.items():
        match = pattern.search(text)
        if match:
            block = next((item for item in blocks if pattern.search(item.text)), blocks[0] if blocks else None)
            if block:
                matches.append((match.group(0), domain, None, block))
    return _field_candidates("document_domain", matches, reason="Domain is inferred only from candidate-side parsed document text.")


def _activity_field(domain: FieldPrediction, blocks: list[_Block], lines: list[tuple[str, _Block]]) -> FieldPrediction:
    if domain.evidence_status == "PRESENT" and domain.candidates:
        domain_value = str(domain.candidates[0].normalized_value)
        activity_id = {
            "electricity": "purchased_electricity", "diesel": "diesel_fuel", "lpg": "lpg",
            "materials": "purchased_materials", "freight": "selected_transport",
        }.get(domain_value)
        if activity_id:
            candidate = domain.candidates[0]
            return _field_candidates("activity_description", [
                (candidate.raw_value, activity_id, None, next((b for b in blocks if candidate.evidence and b.text == candidate.evidence[0].text), blocks[0]))
            ])
    return FieldPrediction("activity_description", domain.evidence_status, domain.candidate_state, domain.candidates, "paddleocr_vl_text_parse", domain.reason)


def _material_identity(lines: list[tuple[str, _Block]]) -> FieldPrediction:
    matches: list[tuple[str, str | None, str | None, _Block]] = []
    for line, block in lines:
        for canonical, pattern in _MATERIALS:
            match = pattern.search(line)
            if match:
                matches.append((match.group(0), canonical, None, block))
    return _field_candidates("material_identity", matches)


def _explicit_simple_field(
    name: str,
    lines: list[tuple[str, _Block]],
    patterns: tuple[tuple[re.Pattern[str], str], ...],
) -> FieldPrediction:
    matches: list[tuple[str, str | None, str | None, _Block]] = []
    for line, block in lines:
        for pattern, normalized in patterns:
            match = pattern.search(line)
            if match:
                matches.append((match.group(0), normalized, None, block))
    return _field_candidates(name, matches)


def _vehicle_class(lines: list[tuple[str, _Block]]) -> FieldPrediction:
    classes = (
        (re.compile(r"\b30\s*[-–]\s*60\s*t(?:onne)?\s*(?:tractor[ -]?trailer|tractor trailer)\b", re.I), "30-60 t tractor-trailer"),
        (re.compile(r"(?<!\d)<\s*3\.5\s*t\b|\bunder\s+3\.5\s*t\b", re.I), "<3.5 t"),
        (re.compile(r"\b3\s*[-–]\s*5\s*t\b", re.I), "3-5 t"),
        (re.compile(r"\b5\s*[-–]\s*12\s*t\b", re.I), "5-12 t"),
        (re.compile(r"\b12\s*[-–]\s*20\s*t\b", re.I), "12-20 t"),
        (re.compile(r"\b20\s*[-–]\s*30\s*t\b", re.I), "20-30 t"),
        (re.compile(r"\b30\s*[-–]\s*50\s*t\b", re.I), "30-50 t"),
    )
    return _explicit_simple_field("transport_vehicle_class", lines, classes)


def _field_map(blocks: list[_Block]) -> dict[str, FieldPrediction]:
    lines = _lines(blocks)
    domain = _extract_domain(blocks, lines)
    fields: dict[str, FieldPrediction] = {"document_domain": domain}
    fields["document_type"] = _document_type(blocks, lines)
    fields["activity_description"] = _activity_field(domain, blocks, lines)
    for name in ("supplier_name", "document_date", "billing_period", "geography", "electricity_use", "vehicle_reference", "source_type", "combustion_status", "operational_control", "commercial_institutional", "purchase_evidence", "transport_mode", "transport_scenario"):
        fields[name] = _field_candidates(name, _find_label_values(lines, name))
    fields["quantity"] = _field_candidates("quantity", _find_label_values(lines, "quantity"))
    fields["net_lpg_mass"] = _field_candidates("net_lpg_mass", [item for item in _find_label_values(lines, "net_lpg_mass") if item[2] == "kg"])
    fields["material_identity"] = _material_identity(lines)
    fields["shipment_mass"] = _field_candidates("shipment_mass", _find_label_values(lines, "shipment_mass"))
    fields["distance"] = _field_candidates("distance", _find_label_values(lines, "distance"))
    fields["transport_vehicle_class"] = _vehicle_class(lines)
    fields["shipment_mass_unit"] = _explicit_simple_field(
        "shipment_mass_unit", lines, ((re.compile(r"\b(?:kg|kilograms?)\b", re.I), "kg"), (re.compile(r"\b(?:t|tonnes?|metric tons?)\b", re.I), "t"))
    )
    fields["distance_unit"] = _explicit_simple_field(
        "distance_unit", lines, ((re.compile(r"\bkm\b|kilomet(?:er|re)s?\b", re.I), "km"), (re.compile(r"\bmiles?\b", re.I), "mile"))
    )
    fields["unit"] = _explicit_simple_field(
        "unit", lines, tuple((re.compile(rf"\b{re.escape(raw)}\b", re.I), normalized) for raw, normalized in _UNIT_NORMALIZATION.items())
    )
    return fields


def _document_type(blocks: list[_Block], lines: list[tuple[str, _Block]]) -> FieldPrediction:
    labelled = _field_candidates("document_type", _find_label_values(lines, "document_type"))
    if labelled.evidence_status == "PRESENT":
        return labelled
    patterns = (
        (re.compile(r"\b(?:utility|electricity) bill\b", re.I), "utility_bill"),
        (re.compile(r"\b(?:account|billing) statement\b", re.I), "statement"),
        (re.compile(r"\b(?:meter reading|reading register)\b", re.I), "meter_reading_record"),
        (re.compile(r"\b(?:purchase order|p\.o\.)\b", re.I), "purchase_order"),
        (re.compile(r"\b(?:delivery note|goods received note)\b", re.I), "delivery_note"),
        (re.compile(r"\b(?:consignment note|lorry receipt|waybill)\b", re.I), "transport_document"),
        (re.compile(r"\b(?:invoice|tax invoice)\b", re.I), "invoice"),
        (re.compile(r"\b(?:receipt|cash memo)\b", re.I), "receipt"),
    )
    matches: list[tuple[str, str | None, str | None, _Block]] = []
    text = "\n".join(block.text for block in blocks)
    for pattern, normalized in patterns:
        match = pattern.search(text)
        if match:
            block = next((item for item in blocks if pattern.search(item.text)), blocks[0] if blocks else None)
            if block:
                matches.append((match.group(0), normalized, None, block))
    return _field_candidates("document_type", matches)


def _set_readiness(fields: dict[str, FieldPrediction]) -> tuple[str, tuple[MissingEvidence, ...], tuple[Ambiguity, ...]]:
    domain_field = fields["document_domain"]
    if domain_field.evidence_status == "AMBIGUOUS":
        return "AMBIGUOUS", (), (Ambiguity("document_domain", domain_field.candidates, tuple(ref for candidate in domain_field.candidates for ref in candidate.evidence), "Parsed evidence contains cues for multiple supported activity domains."),)
    if domain_field.evidence_status != "PRESENT" or not domain_field.candidates:
        return "UNDETERMINED", (), ()
    domain = str(domain_field.candidates[0].normalized_value)
    required = _REQUIRED_FIELDS[domain]
    missing = tuple(MissingEvidence(name, fields[name].reason or "Required evidence was not found in the parsed document blocks.") for name in required if fields[name].evidence_status in {"MISSING", "INSUFFICIENT", "UNDETERMINED"})
    ambiguities = tuple(
        Ambiguity(item.field_name, item.candidates, tuple(ref for candidate in item.candidates for ref in candidate.evidence), item.reason)
        for name, item in fields.items() if name in required and item.evidence_status == "AMBIGUOUS"
    )
    if ambiguities:
        return "AMBIGUOUS", missing, ambiguities
    return ("INCOMPLETE", missing, ()) if missing else ("READY", (), ())


class PaddleOCRVLCandidateAdapter:
    """Candidate-only PaddleOCR-VL parser plus fixed evidence-to-contract mapping."""

    def __init__(
        self,
        *,
        pipeline: Any | None = None,
        pipeline_factory: Callable[..., Any] | None = None,
        model_cache_dir: str | Path | None = None,
        engine: str = "transformers",
    ) -> None:
        self.model_load_seconds = 0.0
        self.last_inference_seconds = 0.0
        self.last_pages: list[dict[str, Any]] = []
        self.engine = engine
        if model_cache_dir is not None:
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(Path(model_cache_dir).resolve())
        if pipeline is None:
            started = time.perf_counter()
            if pipeline_factory is None:
                # On Windows, importing Paddle before PyTorch can load DLLs
                # with colliding names and make the Transformers engine fail
                # to load torch\lib\shm.dll. Preload the isolated CPU runtime.
                if engine == "transformers":
                    import torch  # noqa: F401
                from paddleocr import PaddleOCRVL
                pipeline_factory = PaddleOCRVL
            pipeline = pipeline_factory(pipeline_version="v1.6", device="cpu", engine=engine)
            self.model_load_seconds = time.perf_counter() - started
        self._pipeline = pipeline

    def predict(self, document: CandidateDocumentInput) -> DocumentPrediction:
        if not isinstance(document, CandidateDocumentInput):
            raise TypeError("PaddleOCRVLCandidateAdapter accepts CandidateDocumentInput only.")
        suffix = _MEDIA_SUFFIX.get(document.media_type)
        if suffix is None:
            raise ValueError(f"Unsupported candidate media type: {document.media_type}")
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="greenledger-pvl-") as temp_dir:
            # A generic basename prevents original filenames or domain labels
            # from reaching the PaddleOCR-VL runtime.
            input_path = Path(temp_dir) / ("candidate-input" + suffix)
            input_path.write_bytes(document.document_bytes)
            raw_results = self._pipeline.predict(str(input_path))
            if not isinstance(raw_results, Iterable):
                raise ValueError("PaddleOCR-VL predict() returned a non-iterable result.")
            page_results = list(raw_results)
        blocks, pages = parse_page_results(page_results)
        self.last_pages = pages
        self.last_inference_seconds = time.perf_counter() - started
        fields = _field_map(blocks)
        readiness, missing, ambiguities = _set_readiness(fields)
        ordered = tuple(fields[name] for name in (
            "document_type", "document_domain", "activity_description", "supplier_name", "document_date", "billing_period",
            "quantity", "unit", "net_lpg_mass", "material_identity", "geography", "electricity_use",
            "vehicle_reference", "source_type", "combustion_status", "operational_control",
            "commercial_institutional", "purchase_evidence", "transport_mode", "transport_scenario",
            "shipment_mass", "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class",
        ))
        prediction = DocumentPrediction(
            document_id=document.candidate_id,
            extracted_fields=ordered,
            accounting_readiness=readiness,
            missing_evidence=missing,
            ambiguities=ambiguities,
            review_signal=ReviewSignal(
                review_required=readiness != "READY",
                human_confirmation_required=True,
                explicit_missing_evidence_signal=bool(missing),
                explicit_ambiguity_signal=bool(ambiguities),
                reasons=tuple(item.reason for item in ambiguities if item.reason) + tuple(item.reason for item in missing),
            ),
            model_metadata=ModelMetadata(
                candidate_name=f"PaddleOCR-VL-1.6 full PaddleOCR pipeline ({self.engine} engine) + fixed evidence mapper",
                candidate_version=f"PaddleOCR full pipeline v1.6; {self.engine} engine; runtime versions recorded in result artifact",
                adapter_version=ADAPTER_VERSION,
                confidence_calibrated=False,
                confidence_note="No calibrated field confidence is exposed. Layout detector scores are not treated as field confidence.",
                evidence_localization_method="PaddleOCR-VL page parsing block text and block_bbox normalized by reported page width/height; no box is synthesized when unavailable.",
            ),
        )
        validate_prediction(prediction)
        return prediction

