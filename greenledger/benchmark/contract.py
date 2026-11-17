"""A constrained evidence-only intermediate representation for benchmarking.

The contract contains document observations and candidate readiness predictions.
It deliberately has no fields for scopes, factors, emission totals, or accounting
results. A PRESENT candidate is not thereby certified as safe or accounting-ready.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


CONTRACT_VERSION = "1.0"

EVIDENCE_STATUSES = {"PRESENT", "MISSING", "INSUFFICIENT", "AMBIGUOUS", "UNDETERMINED"}
CANDIDATE_STATES = {"NO_CANDIDATE", "SINGLE_CANDIDATE", "MULTIPLE_CANDIDATES"}
READINESS_STATES = {"READY", "INCOMPLETE", "AMBIGUOUS", "UNDETERMINED"}

# Field names are limited to observable business-document evidence. Accounting
# decisions such as scope/category, factor, gas basis, and emissions are excluded.
ALLOWED_FIELD_NAMES = {
    "document_type", "document_domain", "activity_description", "supplier_name", "document_date",
    "billing_period", "quantity", "unit", "net_lpg_mass", "material_identity",
    "geography", "electricity_use", "vehicle_reference", "source_type",
    "combustion_status", "operational_control", "commercial_institutional",
    "purchase_evidence", "transport_mode", "transport_scenario", "shipment_mass",
    "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class",
}


@dataclass(frozen=True)
class BoundingBox:
    """Normalized top-left x/y/width/height coordinates in [0, 1]."""

    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceReference:
    text: str
    page: int | None = None
    bounding_box: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "page": self.page,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
        }


@dataclass(frozen=True)
class FieldCandidate:
    raw_value: str | int | float | None = None
    normalized_value: str | int | float | None = None
    raw_unit: str | None = None
    normalized_unit: str | None = None
    confidence: float | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "raw_unit": self.raw_unit,
            "normalized_unit": self.normalized_unit,
            "confidence": self.confidence,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class FieldPrediction:
    field_name: str
    evidence_status: str
    candidate_state: str
    candidates: tuple[FieldCandidate, ...] = ()
    source_status: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "evidence_status": self.evidence_status,
            "candidate_state": self.candidate_state,
            "candidates": [item.to_dict() for item in self.candidates],
            "source_status": self.source_status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MissingEvidence:
    field_name: str
    reason: str
    evidence: tuple[EvidenceReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class Ambiguity:
    field_name: str
    candidates: tuple[FieldCandidate, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "candidates": [item.to_dict() for item in self.candidates],
            "evidence": [item.to_dict() for item in self.evidence],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ReviewSignal:
    review_required: bool | None = None
    human_confirmation_required: bool | None = None
    # These preserve a source pipeline's explicit signals. They do not certify
    # the document's true state; their source/definition belongs in metadata.
    explicit_missing_evidence_signal: bool | None = None
    explicit_ambiguity_signal: bool | None = None
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_required": self.review_required,
            "human_confirmation_required": self.human_confirmation_required,
            "explicit_missing_evidence_signal": self.explicit_missing_evidence_signal,
            "explicit_ambiguity_signal": self.explicit_ambiguity_signal,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ModelMetadata:
    candidate_name: str
    candidate_version: str | None = None
    adapter_version: str = CONTRACT_VERSION
    confidence_calibrated: bool | None = None
    confidence_note: str | None = None
    evidence_localization_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentPrediction:
    document_id: str
    extracted_fields: tuple[FieldPrediction, ...]
    accounting_readiness: str = "UNDETERMINED"
    missing_evidence: tuple[MissingEvidence, ...] = ()
    ambiguities: tuple[Ambiguity, ...] = ()
    review_signal: ReviewSignal = field(default_factory=ReviewSignal)
    model_metadata: ModelMetadata = field(default_factory=lambda: ModelMetadata(candidate_name="unspecified"))
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "document_id": self.document_id,
            "extracted_fields": [item.to_dict() for item in self.extracted_fields],
            "missing_evidence": [item.to_dict() for item in self.missing_evidence],
            "ambiguities": [item.to_dict() for item in self.ambiguities],
            "accounting_readiness": self.accounting_readiness,
            "review_signal": self.review_signal.to_dict(),
            "model_metadata": self.model_metadata.to_dict(),
        }


def _is_scalar(value: Any) -> bool:
    return value is None or (isinstance(value, (str, int, float)) and not isinstance(value, bool))


def _validate_evidence(item: EvidenceReference | dict[str, Any], path: str) -> None:
    data = item.to_dict() if isinstance(item, EvidenceReference) else item
    if not isinstance(data, dict) or set(data) != {"text", "page", "bounding_box"}:
        raise ValueError(f"{path} must contain text, page, and bounding_box only.")
    if not isinstance(data["text"], str):
        raise ValueError(f"{path}.text must be a string.")
    page = data["page"]
    if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
        raise ValueError(f"{path}.page must be a positive integer or null.")
    box = data["bounding_box"]
    if box is not None:
        if not isinstance(box, dict) or set(box) != {"x", "y", "width", "height"}:
            raise ValueError(f"{path}.bounding_box must contain x, y, width, and height.")
        vals = [box[name] for name in ("x", "y", "width", "height")]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in vals):
            raise ValueError(f"{path}.bounding_box coordinates must be finite numbers.")
        x, y, width, height = vals
        if x < 0 or y < 0 or width < 0 or height < 0 or x + width > 1 or y + height > 1:
            raise ValueError(f"{path}.bounding_box must lie within normalized page coordinates.")


def _candidate_dict(candidate: FieldCandidate | dict[str, Any], path: str) -> dict[str, Any]:
    data = candidate.to_dict() if isinstance(candidate, FieldCandidate) else candidate
    allowed = {"raw_value", "normalized_value", "raw_unit", "normalized_unit", "confidence", "evidence"}
    if not isinstance(data, dict) or set(data) != allowed:
        raise ValueError(f"{path} must have exactly the candidate contract keys.")
    for key in ("raw_value", "normalized_value"):
        if not _is_scalar(data[key]):
            raise ValueError(f"{path}.{key} must be a scalar or null.")
    for key in ("raw_unit", "normalized_unit"):
        if data[key] is not None and not isinstance(data[key], str):
            raise ValueError(f"{path}.{key} must be a string or null.")
    confidence = data["confidence"]
    if confidence is not None and (
        not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
        or not math.isfinite(confidence) or not 0 <= confidence <= 1
    ):
        raise ValueError(f"{path}.confidence must be null or a number from 0 through 1.")
    if not isinstance(data["evidence"], (tuple, list)):
        raise ValueError(f"{path}.evidence must be an array.")
    for index, evidence in enumerate(data["evidence"]):
        _validate_evidence(evidence, f"{path}.evidence[{index}]")
    return data


def validate_prediction(prediction: DocumentPrediction | dict[str, Any]) -> dict[str, Any]:
    """Validate and return the JSON-compatible contract representation.

    Strict allowlists intentionally reject accounting-result/factor fields and
    unregistered field names.
    """
    data = prediction.to_dict() if isinstance(prediction, DocumentPrediction) else prediction
    top_keys = {
        "contract_version", "document_id", "extracted_fields", "missing_evidence",
        "ambiguities", "accounting_readiness", "review_signal", "model_metadata",
    }
    if not isinstance(data, dict) or set(data) != top_keys:
        raise ValueError("DocumentPrediction has missing or unsupported top-level keys.")
    if data["contract_version"] != CONTRACT_VERSION:
        raise ValueError(f"Unsupported contract version: {data['contract_version']!r}.")
    if not isinstance(data["document_id"], str) or not data["document_id"].strip():
        raise ValueError("document_id must be a non-empty string.")
    if data["accounting_readiness"] not in READINESS_STATES:
        raise ValueError("accounting_readiness must be READY, INCOMPLETE, AMBIGUOUS, or UNDETERMINED.")

    fields = data["extracted_fields"]
    if not isinstance(fields, (tuple, list)):
        raise ValueError("extracted_fields must be an array.")
    names: set[str] = set()
    for index, item in enumerate(fields):
        item = item.to_dict() if isinstance(item, FieldPrediction) else item
        keys = {"field_name", "evidence_status", "candidate_state", "candidates", "source_status", "reason"}
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError(f"extracted_fields[{index}] has missing or unsupported keys.")
        name = item["field_name"]
        if name not in ALLOWED_FIELD_NAMES:
            raise ValueError(f"Unsupported evidence field name: {name!r}.")
        if name in names:
            raise ValueError(f"Duplicate field prediction: {name!r}.")
        names.add(name)
        if item["evidence_status"] not in EVIDENCE_STATUSES:
            raise ValueError(f"Invalid evidence status for {name!r}.")
        candidates = item["candidates"]
        if not isinstance(candidates, (tuple, list)):
            raise ValueError(f"{name}.candidates must be an array.")
        for candidate_index, candidate in enumerate(candidates):
            _candidate_dict(candidate, f"extracted_fields[{index}].candidates[{candidate_index}]")
        expected_state = (
            "NO_CANDIDATE" if len(candidates) == 0 else
            "SINGLE_CANDIDATE" if len(candidates) == 1 else
            "MULTIPLE_CANDIDATES"
        )
        if item["candidate_state"] != expected_state:
            raise ValueError(f"{name}.candidate_state must agree with its candidate count.")
        if item["evidence_status"] in {"MISSING", "UNDETERMINED"} and candidates:
            raise ValueError(f"{name} cannot claim {item['evidence_status']} while carrying candidates.")
        if item["evidence_status"] == "PRESENT" and len(candidates) != 1:
            raise ValueError(f"{name} must have exactly one candidate when evidence_status is PRESENT.")
        if item["evidence_status"] == "INSUFFICIENT" and not candidates:
            raise ValueError(f"{name} must carry a candidate when evidence_status is INSUFFICIENT.")
        for key in ("source_status", "reason"):
            if item[key] is not None and not isinstance(item[key], str):
                raise ValueError(f"{name}.{key} must be a string or null.")

    if not isinstance(data["missing_evidence"], (tuple, list)):
        raise ValueError("missing_evidence must be an array.")
    for index, missing in enumerate(data["missing_evidence"]):
        missing = missing.to_dict() if isinstance(missing, MissingEvidence) else missing
        if not isinstance(missing, dict) or set(missing) != {"field_name", "reason", "evidence"}:
            raise ValueError(f"missing_evidence[{index}] has unsupported keys.")
        if missing["field_name"] not in ALLOWED_FIELD_NAMES or not isinstance(missing["reason"], str):
            raise ValueError(f"missing_evidence[{index}] has invalid field_name/reason.")
        for evidence_index, evidence in enumerate(missing["evidence"]):
            _validate_evidence(evidence, f"missing_evidence[{index}].evidence[{evidence_index}]")

    if not isinstance(data["ambiguities"], (tuple, list)):
        raise ValueError("ambiguities must be an array.")
    for index, ambiguity in enumerate(data["ambiguities"]):
        ambiguity = ambiguity.to_dict() if isinstance(ambiguity, Ambiguity) else ambiguity
        if not isinstance(ambiguity, dict) or set(ambiguity) != {"field_name", "candidates", "evidence", "reason"}:
            raise ValueError(f"ambiguities[{index}] has unsupported keys.")
        if ambiguity["field_name"] not in ALLOWED_FIELD_NAMES:
            raise ValueError(f"ambiguities[{index}] has an unsupported field_name.")
        if ambiguity["reason"] is not None and not isinstance(ambiguity["reason"], str):
            raise ValueError(f"ambiguities[{index}].reason must be a string or null.")
        for candidate_index, candidate in enumerate(ambiguity["candidates"]):
            _candidate_dict(candidate, f"ambiguities[{index}].candidates[{candidate_index}]")
        for evidence_index, evidence in enumerate(ambiguity["evidence"]):
            _validate_evidence(evidence, f"ambiguities[{index}].evidence[{evidence_index}]")

    signal = data["review_signal"]
    signal_keys = {
        "review_required", "human_confirmation_required",
        "explicit_missing_evidence_signal", "explicit_ambiguity_signal", "reasons",
    }
    if not isinstance(signal, dict) or set(signal) != signal_keys:
        raise ValueError("review_signal has missing or unsupported keys.")
    for key in ("review_required", "human_confirmation_required", "explicit_missing_evidence_signal", "explicit_ambiguity_signal"):
        if signal[key] is not None and not isinstance(signal[key], bool):
            raise ValueError(f"review_signal.{key} must be boolean or null.")
    if not isinstance(signal["reasons"], (tuple, list)) or any(not isinstance(value, str) for value in signal["reasons"]):
        raise ValueError("review_signal.reasons must be an array of strings.")

    metadata = data["model_metadata"]
    metadata_keys = {
        "candidate_name", "candidate_version", "adapter_version",
        "confidence_calibrated", "confidence_note", "evidence_localization_method",
    }
    if not isinstance(metadata, dict) or set(metadata) != metadata_keys:
        raise ValueError("model_metadata has missing or unsupported keys.")
    if not isinstance(metadata["candidate_name"], str) or not metadata["candidate_name"]:
        raise ValueError("model_metadata.candidate_name must be a non-empty string.")
    for key in ("candidate_version", "confidence_note", "evidence_localization_method"):
        if metadata[key] is not None and not isinstance(metadata[key], str):
            raise ValueError(f"model_metadata.{key} must be a string or null.")
    if not isinstance(metadata["adapter_version"], str):
        raise ValueError("model_metadata.adapter_version must be a string.")
    if metadata["confidence_calibrated"] is not None and not isinstance(metadata["confidence_calibrated"], bool):
        raise ValueError("model_metadata.confidence_calibrated must be boolean or null.")
    return data
