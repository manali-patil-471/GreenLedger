"""Candidate-only adapter for the existing Candidate A line-role extractor."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from greenledger.ai_field_extraction import (
    DEFAULT_MODEL_PATH,
    extract_ai_carbon_fields,
    load_line_model,
)

from .candidate_interface import CandidateDocumentInput
from .contract import (
    Ambiguity,
    DocumentPrediction,
    EvidenceReference,
    FieldCandidate,
    FieldPrediction,
    MissingEvidence,
    ModelMetadata,
    ReviewSignal,
    validate_prediction,
)


ADAPTER_VERSION = "candidate-a-char-ngram-candidate-only-v1"
EXPECTED_ARTIFACT_SHA256 = "6b7cecb47346fa8582eb4dc3963a746bf932c06874caa784f98bcd6a53d205ab"
FIELD_NAMES = (
    "document_type",
    "document_domain",
    "activity_description",
    "supplier_name",
    "document_date",
    "billing_period",
    "quantity",
    "unit",
    "net_lpg_mass",
    "material_identity",
    "geography",
    "electricity_use",
    "vehicle_reference",
    "source_type",
    "combustion_status",
    "operational_control",
    "commercial_institutional",
    "purchase_evidence",
    "transport_mode",
    "transport_scenario",
    "shipment_mass",
    "shipment_mass_unit",
    "distance",
    "distance_unit",
    "transport_vehicle_class",
)
ACTIVITY_TO_DOMAIN = {
    "purchased_electricity": "electricity",
    "diesel_fuel": "diesel",
    "lpg": "lpg",
    "purchased_materials": "materials",
    "selected_transport": "freight",
}
MEDIA_SUFFIX = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}
_UNSET = object()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _evidence(text: Any) -> tuple[EvidenceReference, ...]:
    if isinstance(text, str) and text.strip():
        return (EvidenceReference(text=text.strip()),)
    return ()


def _field(
    name: str,
    *,
    source_status: Any = None,
    raw_value: Any = None,
    normalized_value: Any = None,
    raw_unit: Any = None,
    normalized_unit: Any = None,
    evidence_text: Any = None,
    reason: str | None = None,
    force_undetermined: bool = False,
) -> FieldPrediction:
    has_value = raw_value is not None or normalized_value is not None
    status_text = str(source_status or "").casefold()
    if force_undetermined:
        status = "UNDETERMINED"
    elif status_text == "ambiguous":
        status = "AMBIGUOUS"
    elif status_text in {"missing", "not_present"} and not has_value:
        status = "MISSING"
    elif not has_value:
        # Candidate A's "unresolved" can mean it saw an unparseable line but
        # did not retain a scalar. Do not relabel that as confirmed absence.
        status = "UNDETERMINED" if status_text == "unresolved" else "MISSING" if status_text else "UNDETERMINED"
    elif normalized_value is None or status_text == "unresolved":
        status = "INSUFFICIENT"
    else:
        status = "PRESENT"

    candidates: tuple[FieldCandidate, ...] = ()
    if has_value and status not in {"MISSING", "UNDETERMINED", "AMBIGUOUS"}:
        candidates = (FieldCandidate(
            raw_value=raw_value if isinstance(raw_value, (str, int, float)) and not isinstance(raw_value, bool) else None,
            normalized_value=normalized_value if isinstance(normalized_value, (str, int, float)) and not isinstance(normalized_value, bool) else None,
            raw_unit=raw_unit if isinstance(raw_unit, str) else None,
            normalized_unit=normalized_unit if isinstance(normalized_unit, str) else None,
            confidence=None,
            evidence=_evidence(evidence_text),
        ),)

    if status == "MISSING":
        reason = reason or "Candidate A did not identify this field in the OCR transcript."
    elif status == "INSUFFICIENT":
        reason = reason or "Candidate A emitted evidence but did not produce a normalized value."
    elif status == "UNDETERMINED":
        reason = reason or "Candidate A does not provide a determination for this field."
    elif status == "AMBIGUOUS":
        reason = reason or "Candidate A identified multiple possible lines but did not preserve their individual values."

    return FieldPrediction(
        field_name=name,
        evidence_status=status,
        candidate_state=("NO_CANDIDATE" if not candidates else "SINGLE_CANDIDATE"),
        candidates=candidates,
        source_status=str(source_status) if source_status is not None else None,
        reason=reason,
    )


def _source_field(
    name: str,
    source: Any,
    *,
    normalized_value: Any = _UNSET,
    raw_unit: Any = None,
    normalized_unit: Any = None,
    reason: str | None = None,
) -> FieldPrediction:
    source = source if isinstance(source, dict) else {}
    return _field(
        name,
        source_status=source.get("status"),
        raw_value=source.get("value"),
        normalized_value=source.get("value") if normalized_value is _UNSET else normalized_value,
        raw_unit=raw_unit,
        normalized_unit=normalized_unit,
        evidence_text=source.get("evidence_text"),
        reason=reason,
    )


def adapt_candidate_a_output(
    candidate_id: str,
    extraction: dict[str, Any] | None,
    *,
    artifact_sha256: str,
) -> DocumentPrediction:
    """Map only Candidate A's transcript-derived fields into the contract."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty.")
    extraction = extraction if isinstance(extraction, dict) else {}
    activity = extraction.get("activity") if isinstance(extraction.get("activity"), dict) else {}
    activity_description = extraction.get("activity_description") if isinstance(extraction.get("activity_description"), dict) else {}
    quantity = extraction.get("quantity") if isinstance(extraction.get("quantity"), dict) else {}
    unit = extraction.get("unit") if isinstance(extraction.get("unit"), dict) else {}
    date = extraction.get("invoice_date") if isinstance(extraction.get("invoice_date"), dict) else {}
    supplier = extraction.get("supplier_name") if isinstance(extraction.get("supplier_name"), dict) else {}
    billing_period = extraction.get("billing_period") if isinstance(extraction.get("billing_period"), dict) else {}
    vehicle_reference = extraction.get("vehicle_reference") if isinstance(extraction.get("vehicle_reference"), dict) else {}
    cylinder_net_mass = extraction.get("cylinder_net_mass") if isinstance(extraction.get("cylinder_net_mass"), dict) else {}

    activity_id = activity.get("value")
    domain = ACTIVITY_TO_DOMAIN.get(str(activity_id)) if activity_id is not None else None
    activity_ambiguous = (
        str(activity.get("status") or "").casefold() == "ambiguous"
        or str(activity_description.get("status") or "").casefold() == "ambiguous"
    )

    fields: dict[str, FieldPrediction] = {}
    fields["document_type"] = _field(
        "document_type",
        source_status="extracted" if extraction.get("document_type") else "missing",
        raw_value=extraction.get("document_type"),
        normalized_value=extraction.get("document_type"),
        reason="Document type is emitted by Candidate A's existing activity-to-document-type post-processing.",
    )
    if domain is not None and not activity_ambiguous:
        fields["document_domain"] = _field(
            "document_domain",
            source_status=activity.get("status"),
            raw_value=activity_id,
            normalized_value=domain,
            evidence_text=activity_description.get("evidence_text"),
            reason="Domain is mapped from Candidate A's transcript-derived normalized activity.",
        )
    elif activity_ambiguous:
        fields["document_domain"] = _field(
            "document_domain", source_status="ambiguous", reason="Candidate A's activity evidence is ambiguous."
        )
    else:
        fields["document_domain"] = _field(
            "document_domain", source_status=activity.get("status"), force_undetermined=True,
            reason="Candidate A did not produce a supported normalized activity; domain remains undetermined.",
        )

    activity_normalized = activity_id if activity_description.get("value") is not None else None
    fields["activity_description"] = _source_field(
        "activity_description", activity_description, normalized_value=activity_normalized,
        reason="Candidate A's line-role prediction; normalized only when its existing activity post-processing returned an activity ID.",
    )
    fields["supplier_name"] = _source_field("supplier_name", supplier)
    fields["document_date"] = _field(
        "document_date",
        source_status=date.get("status"),
        raw_value=date.get("raw_text") or date.get("value"),
        normalized_value=date.get("value"),
        evidence_text=date.get("evidence_text"),
    )
    fields["billing_period"] = _source_field("billing_period", billing_period)

    quantity_raw = quantity.get("value") if quantity.get("value") is not None else quantity.get("raw_text")
    quantity_normalized = quantity.get("normalized_value")
    raw_unit = unit.get("raw_text")
    normalized_unit = quantity.get("unit") or unit.get("value")
    fields["quantity"] = _field(
        "quantity",
        source_status=quantity.get("status"),
        raw_value=quantity_raw,
        normalized_value=quantity_normalized,
        raw_unit=raw_unit,
        normalized_unit=normalized_unit,
        evidence_text=quantity.get("evidence_text"),
    )
    fields["unit"] = _field(
        "unit",
        source_status=unit.get("status"),
        raw_value=unit.get("raw_text"),
        normalized_value=unit.get("value"),
        evidence_text=unit.get("evidence_text") or quantity.get("evidence_text"),
    )

    # A quantity is treated as LPG mass only when Candidate A itself identified
    # LPG and normalized that quantity to kilograms. Cylinder counts or a raw
    # cylinder-mass string are never converted into a numeric mass here.
    if domain == "lpg" and quantity_normalized is not None and normalized_unit == "kg":
        fields["net_lpg_mass"] = _field(
            "net_lpg_mass",
            source_status=quantity.get("status"),
            raw_value=quantity_raw,
            normalized_value=quantity_normalized,
            raw_unit=raw_unit,
            normalized_unit=normalized_unit,
            evidence_text=quantity.get("evidence_text"),
            reason="Mapped from Candidate A's own LPG quantity only when its existing unit normalization produced kg.",
        )
    elif domain == "lpg" and cylinder_net_mass.get("value") is not None:
        fields["net_lpg_mass"] = _field(
            "net_lpg_mass",
            source_status="unresolved",
            raw_value=cylinder_net_mass.get("value"),
            evidence_text=cylinder_net_mass.get("evidence_text"),
            reason="Candidate A found a cylinder-net-mass line but did not parse a normalized mass; human review is required.",
        )
    elif domain == "lpg" and str(cylinder_net_mass.get("status") or "").casefold() == "missing":
        fields["net_lpg_mass"] = _field(
            "net_lpg_mass", source_status="missing",
            reason="Candidate A did not identify net LPG mass; cylinder count is not converted to mass.",
        )
    else:
        fields["net_lpg_mass"] = _field(
            "net_lpg_mass", force_undetermined=True,
            reason="Candidate A did not produce a usable LPG net-mass field for this candidate domain.",
        )

    fields["vehicle_reference"] = _source_field("vehicle_reference", vehicle_reference)

    # Candidate A has no extracted evidence fields for the following. In
    # particular, activity-description text is not silently relabeled as a
    # material identity, shipment mass, distance, or vehicle class.
    for name in FIELD_NAMES:
        fields.setdefault(name, _field(name, force_undetermined=True))
    ordered_fields = tuple(fields[name] for name in FIELD_NAMES)

    missing: list[MissingEvidence] = []
    ambiguities: list[Ambiguity] = []
    for item in ordered_fields:
        if item.evidence_status == "MISSING":
            source = {
                "quantity": quantity,
                "unit": unit,
                "activity_description": activity_description,
                "supplier_name": supplier,
                "document_date": date,
                "billing_period": billing_period,
                "vehicle_reference": vehicle_reference,
                "net_lpg_mass": cylinder_net_mass,
            }.get(item.field_name, {})
            refs = _evidence(source.get("evidence_text")) if isinstance(source, dict) else ()
            missing.append(MissingEvidence(
                field_name=item.field_name,
                reason=item.reason or "Candidate A identified no field candidate.",
                evidence=refs,
            ))
        elif item.evidence_status == "AMBIGUOUS":
            ambiguities.append(Ambiguity(
                field_name=item.field_name,
                candidates=item.candidates,
                evidence=tuple(ref for candidate in item.candidates for ref in candidate.evidence),
                reason=item.reason,
            ))

    monitored_statuses = (
        activity.get("status"), quantity.get("status"), unit.get("status"),
    )
    missing_signal = any(str(status or "").casefold() in {"missing", "unresolved"} for status in monitored_statuses)
    ambiguity_signal = any(
        str(source.get("status") or "").casefold() == "ambiguous"
        for source in (activity, activity_description, quantity, unit, cylinder_net_mass, vehicle_reference)
    )
    prediction = DocumentPrediction(
        document_id=candidate_id,
        extracted_fields=ordered_fields,
        missing_evidence=tuple(missing),
        ambiguities=tuple(ambiguities),
        accounting_readiness="UNDETERMINED",
        review_signal=ReviewSignal(
            review_required=extraction.get("review_required", True),
            human_confirmation_required=extraction.get("human_confirmation_required", True),
            explicit_missing_evidence_signal=missing_signal,
            explicit_ambiguity_signal=ambiguity_signal,
            reasons=tuple(str(value) for value in extraction.get("review_reasons", []) if value is not None)
            or ("Candidate A suggestions require human confirmation; readiness is not predicted.",),
        ),
        model_metadata=ModelMetadata(
            candidate_name="GreenLedger Candidate A: supervised character n-gram line-role extractor",
            candidate_version=f"greenledger_char_ngram_line_role_v1; artifact_sha256={artifact_sha256}",
            adapter_version=ADAPTER_VERSION,
            confidence_calibrated=False,
            confidence_note=str(extraction.get("confidence_note") or "Candidate A confidence is unavailable and uncalibrated."),
            evidence_localization_method="RapidOCR transcript line text only; page and bounding-box locations are not retained by Candidate A.",
        ),
    )
    validate_prediction(prediction)
    return prediction


class CandidateAAdapter:
    """Run the existing Candidate A model on OCR text from candidate bytes only."""

    def __init__(
        self,
        *,
        ocr: Callable[[bytes, str], dict[str, Any] | None] | None = None,
        field_extractor: Callable[..., dict[str, Any]] | None = None,
        model: dict[str, Any] | None = None,
        model_path: Path = DEFAULT_MODEL_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.artifact_sha256 = _sha256(self.model_path)
        if self.artifact_sha256 != EXPECTED_ARTIFACT_SHA256:
            raise RuntimeError(
                "Candidate A artifact SHA256 mismatch: expected the existing frozen artifact "
                f"{EXPECTED_ARTIFACT_SHA256}, got {self.artifact_sha256}."
            )
        self.model = model if model is not None else load_line_model(self.model_path)
        if ocr is None:
            from greenledger.ocr import recognize_upload
            ocr = recognize_upload
        self._ocr = ocr
        self._field_extractor = field_extractor or extract_ai_carbon_fields
        self.last_ocr_latency_seconds: float | None = None
        self.last_ocr_status: str | None = None

    def predict(self, document: CandidateDocumentInput) -> DocumentPrediction:
        if not isinstance(document, CandidateDocumentInput):
            raise TypeError("CandidateAAdapter accepts CandidateDocumentInput only.")
        suffix = MEDIA_SUFFIX.get(document.media_type)
        if suffix is None:
            raise ValueError(f"Unsupported candidate media type: {document.media_type}")
        # Never pass an original filename or directory path into OCR.
        ocr_result = self._ocr(document.document_bytes, "candidate-input" + suffix) or {}
        latency = ocr_result.get("latency_seconds")
        self.last_ocr_latency_seconds = float(latency) if isinstance(latency, (int, float)) else None
        self.last_ocr_status = str(ocr_result.get("status") or "OCR_RESULT_UNSPECIFIED")
        transcription = ocr_result.get("transcription")
        extraction = None
        if isinstance(transcription, str) and transcription.strip():
            extraction = self._field_extractor(transcription, model=self.model)
        return adapt_candidate_a_output(
            document.candidate_id,
            extraction,
            artifact_sha256=self.artifact_sha256,
        )
