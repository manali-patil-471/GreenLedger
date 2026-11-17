"""Candidate-only adapter for the existing RapidOCR + rule-extraction path."""

from __future__ import annotations

from typing import Any, Callable

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


ADAPTER_VERSION = "current-pipeline-candidate-only-v2"
_ACTIVITY_DOMAIN = {
    "purchased_electricity": "electricity",
    "diesel_fuel": "diesel",
    "lpg": "lpg",
    "purchased_materials": "materials",
    "selected_transport": "freight",
}
_ALWAYS_REPRESENTED_FIELDS = (
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
_MEDIA_SUFFIX = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}


def _as_evidence(text: Any) -> tuple[EvidenceReference, ...]:
    if not isinstance(text, str) or not text.strip():
        return ()
    # The existing extractor supplies quoted OCR text only, no page/region.
    return (EvidenceReference(text=text.strip()),)


def _candidate(
    raw_value: Any = None,
    normalized_value: Any = None,
    raw_unit: Any = None,
    normalized_unit: Any = None,
    evidence_text: Any = None,
) -> FieldCandidate:
    return FieldCandidate(
        raw_value=raw_value if isinstance(raw_value, (str, int, float)) and not isinstance(raw_value, bool) else None,
        normalized_value=normalized_value if isinstance(normalized_value, (str, int, float)) and not isinstance(normalized_value, bool) else None,
        raw_unit=raw_unit if isinstance(raw_unit, str) else None,
        normalized_unit=normalized_unit if isinstance(normalized_unit, str) else None,
        confidence=None,
        evidence=_as_evidence(evidence_text),
    )


def _status(source_status: Any, has_candidate: bool, normalized_value: Any) -> str:
    value = str(source_status or "").casefold()
    if value == "ambiguous":
        return "AMBIGUOUS"
    if value in {"missing", "not_present"}:
        return "MISSING"
    if value == "unresolved" or (has_candidate and normalized_value is None):
        return "INSUFFICIENT"
    if has_candidate:
        return "PRESENT"
    return "UNDETERMINED"


def _field(
    name: str,
    source: dict[str, Any] | None = None,
    *,
    raw_value: Any = None,
    normalized_value: Any = None,
    raw_unit: Any = None,
    normalized_unit: Any = None,
    evidence_text: Any = None,
    reason: str | None = None,
    force_undetermined: bool = False,
) -> FieldPrediction:
    source = source or {}
    source_status = source.get("status")
    has_candidate = raw_value is not None or normalized_value is not None
    status = "UNDETERMINED" if force_undetermined else _status(source_status, has_candidate, normalized_value)
    candidates = (_candidate(raw_value, normalized_value, raw_unit, normalized_unit, evidence_text),) if has_candidate else ()
    if status in {"MISSING", "UNDETERMINED"}:
        candidates = ()
    if status == "UNDETERMINED":
        reason = reason or "The current pipeline supplied no determination for this field."
    elif status == "MISSING":
        reason = reason or "The current extractor emitted no candidate for this field."
    elif status == "INSUFFICIENT":
        reason = reason or "A candidate was emitted but the current pipeline did not normalize it."
    return FieldPrediction(
        field_name=name,
        evidence_status=status,
        candidate_state="NO_CANDIDATE" if not candidates else "SINGLE_CANDIDATE",
        candidates=candidates,
        source_status=str(source_status) if source_status is not None else None,
        reason=reason,
    )


def _domain_field(activity: dict[str, Any]) -> tuple[FieldPrediction, str | None]:
    """Derive domain solely from the current candidate's extracted activity."""

    activity_id = activity.get("value")
    source_status = activity.get("status")
    domain = _ACTIVITY_DOMAIN.get(str(activity_id)) if activity_id is not None else None
    if domain is not None and str(source_status or "").casefold() != "ambiguous":
        return _field(
            "document_domain",
            activity,
            raw_value=activity_id,
            normalized_value=domain,
            evidence_text=activity.get("evidence_text"),
        ), domain
    if str(source_status or "").casefold() == "ambiguous":
        return FieldPrediction(
            field_name="document_domain",
            evidence_status="AMBIGUOUS",
            candidate_state="NO_CANDIDATE",
            reason="The current extractor marked activity classification ambiguous but supplied no alternatives.",
            source_status="ambiguous",
        ), None
    return _field(
        "document_domain",
        {"status": source_status or "missing"},
        reason="No supported document domain was produced by the candidate activity output.",
    ), None


class CurrentPipelineAdapter:
    """Runs unchanged OCR/extraction components and adapts their output.

    Dependencies are injectable for tests. The production extractor/OCR code
    remains unmodified and this adapter accepts no annotations or domain labels.
    """

    def __init__(
        self,
        *,
        ocr: Callable[[bytes, str], dict[str, Any] | None] | None = None,
        extractor: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        if ocr is None:
            from greenledger.ocr import recognize_upload
            ocr = recognize_upload
        if extractor is None:
            from greenledger.field_extraction import extract_carbon_fields
            extractor = extract_carbon_fields
        self._ocr = ocr
        self._extractor = extractor

    def predict(self, document: CandidateDocumentInput) -> DocumentPrediction:
        if not isinstance(document, CandidateDocumentInput):
            raise TypeError("CurrentPipelineAdapter accepts CandidateDocumentInput only.")
        suffix = _MEDIA_SUFFIX.get(document.media_type)
        if suffix is None:
            raise ValueError(f"Unsupported candidate media type: {document.media_type}")
        ocr_result = self._ocr(document.document_bytes, "candidate-input" + suffix)
        transcription = (ocr_result or {}).get("transcription")
        extraction = self._extractor(transcription) if isinstance(transcription, str) and transcription.strip() else None
        return adapt_current_pipeline_output(document.candidate_id, extraction)


def adapt_current_pipeline_output(
    candidate_id: str,
    extraction: dict[str, Any] | None,
) -> DocumentPrediction:
    """Map candidate-produced extraction output without labels or metadata."""

    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be a non-empty string.")
    extraction = extraction if isinstance(extraction, dict) else {}
    activity = extraction.get("activity") if isinstance(extraction.get("activity"), dict) else {}
    quantity = extraction.get("quantity") if isinstance(extraction.get("quantity"), dict) else {}
    unit = extraction.get("unit") if isinstance(extraction.get("unit"), dict) else {}
    date = extraction.get("invoice_date") if isinstance(extraction.get("invoice_date"), dict) else {}
    supplier = extraction.get("supplier_name") if isinstance(extraction.get("supplier_name"), dict) else {}
    document_type = extraction.get("document_type")

    domain_prediction, predicted_domain = _domain_field(activity)
    quantity_value = quantity.get("value")
    quantity_normalized = quantity.get("normalized_value")
    quantity_raw_unit = unit.get("raw_text")
    quantity_normalized_unit = quantity.get("unit") or unit.get("value")

    fields_by_name: dict[str, FieldPrediction] = {
        "document_type": _field(
            "document_type",
            {"status": "extracted" if document_type else "missing"},
            raw_value=document_type,
            normalized_value=document_type,
        ),
        "document_domain": domain_prediction,
        "activity_description": _field(
            "activity_description", activity,
            raw_value=activity.get("raw_text"),
            normalized_value=activity.get("value"),
            evidence_text=activity.get("evidence_text"),
        ),
        "supplier_name": _field(
            "supplier_name", supplier,
            raw_value=supplier.get("value"),
            normalized_value=supplier.get("value"),
            evidence_text=supplier.get("evidence_text"),
        ),
        "document_date": _field(
            "document_date", date,
            raw_value=date.get("raw_text"),
            normalized_value=date.get("value"),
            evidence_text=date.get("evidence_text"),
        ),
        "quantity": _field(
            "quantity", quantity,
            raw_value=quantity_value if quantity_value is not None else quantity.get("raw_text"),
            normalized_value=quantity_normalized,
            raw_unit=quantity_raw_unit,
            normalized_unit=quantity_normalized_unit,
            evidence_text=quantity.get("evidence_text"),
        ),
        "unit": _field(
            "unit", unit,
            raw_value=unit.get("raw_text"),
            normalized_value=unit.get("value"),
            evidence_text=unit.get("evidence_text"),
        ),
    }

    # LPG mass is a semantic view of candidate quantity only when the
    # candidate itself classified the activity as LPG and normalized kg.
    if predicted_domain == "lpg" and quantity_normalized is not None and quantity_normalized_unit == "kg":
        fields_by_name["net_lpg_mass"] = _field(
            "net_lpg_mass", quantity,
            raw_value=quantity_value if quantity_value is not None else quantity.get("raw_text"),
            normalized_value=quantity_normalized,
            raw_unit=quantity_raw_unit,
            normalized_unit=quantity_normalized_unit,
            evidence_text=quantity.get("evidence_text"),
            reason="Mapped from candidate-recognized LPG quantity only when normalized in kilograms.",
        )
    else:
        fields_by_name["net_lpg_mass"] = _field(
            "net_lpg_mass", force_undetermined=True,
            reason="LPG mass was not emitted as a usable candidate field.",
        )

    for name in _ALWAYS_REPRESENTED_FIELDS:
        if name not in fields_by_name:
            fields_by_name[name] = _field(name, force_undetermined=True)
    fields = tuple(fields_by_name[name] for name in _ALWAYS_REPRESENTED_FIELDS)

    ambiguities: list[Ambiguity] = []
    missing: list[MissingEvidence] = []
    for item in fields:
        if item.evidence_status == "AMBIGUOUS":
            evidence = tuple(ref for candidate in item.candidates for ref in candidate.evidence)
            ambiguities.append(Ambiguity(
                field_name=item.field_name,
                candidates=item.candidates,
                evidence=evidence,
                reason=item.reason or "The current extractor explicitly marked this field ambiguous.",
            ))
        elif item.evidence_status == "MISSING" and item.field_name in {"activity_description", "quantity", "unit"}:
            missing.append(MissingEvidence(
                field_name=item.field_name,
                reason=item.reason or "No candidate emitted by the current extractor.",
            ))

    statuses = [activity.get("status"), quantity.get("status"), unit.get("status")]
    original_missing = any(str(status or "").casefold() in {"missing", "unresolved"} for status in statuses)
    original_ambiguity = any(str(status or "").casefold() == "ambiguous" for status in statuses)
    if extraction:
        review_signal = ReviewSignal(
            review_required=extraction.get("review_required"),
            human_confirmation_required=extraction.get("human_confirmation_required"),
            explicit_missing_evidence_signal=original_missing,
            explicit_ambiguity_signal=original_ambiguity,
            reasons=tuple(str(value) for value in extraction.get("review_reasons", []) if value is not None),
        )
    else:
        review_signal = ReviewSignal(human_confirmation_required=True)

    prediction = DocumentPrediction(
        document_id=candidate_id,
        extracted_fields=fields,
        missing_evidence=tuple(missing),
        ambiguities=tuple(ambiguities),
        accounting_readiness="UNDETERMINED",
        review_signal=review_signal,
        model_metadata=ModelMetadata(
            candidate_name=str(extraction.get("extractor") or "current_pipeline_no_extractor_output"),
            candidate_version=None,
            adapter_version=ADAPTER_VERSION,
            confidence_calibrated=False,
            confidence_note=str(extraction.get("confidence_note") or "Current pipeline provides no calibrated field confidence."),
            evidence_localization_method="OCR evidence string only; page/bounding-box location unavailable.",
        ),
    )
    validate_prediction(prediction)
    return prediction
