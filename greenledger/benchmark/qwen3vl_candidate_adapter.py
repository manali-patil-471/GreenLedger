"""Benchmark-only Qwen3-VL GGUF adapter for candidate-side document evidence.

This adapter receives only ``CandidateDocumentInput`` (opaque ID, bytes, MIME
type). PDFs are rendered page-by-page to generic image names and supplied to a
local llama.cpp unified CLI. It has no annotation, manifest, source-path,
factor, scope, or accounting-result interface.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable

from .candidate_interface import CandidateDocumentInput
from .contract import (
    ALLOWED_FIELD_NAMES,
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


ADAPTER_VERSION = "qwen3-vl-4b-gguf-q4_k_m-candidate-only-v1"
MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct-GGUF:Q4_K_M"
MODEL_REVISION_NOTE = "official Q4_K_M GGUF; adapter does not download or resolve model files"
SUPPORTED_DOMAINS = {"electricity", "diesel", "lpg", "materials", "freight"}

FIELD_ORDER = (
    "document_type", "document_domain", "activity_description", "supplier_name", "document_date",
    "billing_period", "quantity", "unit", "net_lpg_mass", "material_identity", "geography",
    "electricity_use", "vehicle_reference", "source_type", "combustion_status",
    "operational_control", "commercial_institutional", "purchase_evidence", "transport_mode",
    "transport_scenario", "shipment_mass", "shipment_mass_unit", "distance", "distance_unit",
    "transport_vehicle_class",
)

MEDIA_SUFFIX = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

_FIELD_ALIASES = {
    "lpg_net_mass": "net_lpg_mass",
    "cylinder_net_mass": "net_lpg_mass",
    "vehicle_gvw_class": "transport_vehicle_class",
    "gvw_class": "transport_vehicle_class",
    "date": "document_date",
}
_EVIDENCE_STATUSES = {"PRESENT", "MISSING", "INSUFFICIENT", "AMBIGUOUS", "UNDETERMINED"}
_READINESS_STATES = {"READY", "INCOMPLETE", "AMBIGUOUS", "UNDETERMINED"}


class QwenInferenceError(RuntimeError):
    """A local llama.cpp invocation did not produce a usable response."""


@dataclass(frozen=True)
class PreparedPage:
    """Opaque image path paired with its one-based source page number."""

    path: Path
    page_number: int


def render_pdf_pages(pdf_bytes: bytes, output_directory: Path, *, scale: float = 2.5) -> list[PreparedPage]:
    """Render every PDF page to PNG without OCR or annotation-derived crops."""
    try:
        import pypdfium2
    except ImportError as error:  # pragma: no cover - depends on smoke runtime
        raise RuntimeError("PDF input requires pypdfium2 in the isolated smoke environment.") from error

    output_directory.mkdir(parents=True, exist_ok=True)
    pdf = pypdfium2.PdfDocument(pdf_bytes)
    pages: list[PreparedPage] = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        image_path = output_directory / f"candidate-input-page-{index + 1:04d}.png"
                        image.save(image_path, format="PNG")
                    finally:
                        close_image = getattr(image, "close", None)
                        if callable(close_image):
                            close_image()
                finally:
                    close_bitmap = getattr(bitmap, "close", None)
                    if callable(close_bitmap):
                        close_bitmap()
                pages.append(PreparedPage(image_path, index + 1))
            finally:
                close_page = getattr(page, "close", None)
                if callable(close_page):
                    close_page()
        if not pages:
            raise ValueError("PDF contains no renderable pages.")
        return pages
    finally:
        close_pdf = getattr(pdf, "close", None)
        if callable(close_pdf):
            close_pdf()


def prepare_candidate_pages(
    document: CandidateDocumentInput,
    output_directory: Path,
    *,
    pdf_renderer: Callable[[bytes, Path], list[PreparedPage]] = render_pdf_pages,
) -> list[PreparedPage]:
    """Materialize candidate bytes under opaque names and return pages in order."""
    if not isinstance(document, CandidateDocumentInput):
        raise TypeError("Qwen3VLCandidateAdapter accepts CandidateDocumentInput only.")
    suffix = MEDIA_SUFFIX.get(document.media_type)
    if suffix is None:
        raise ValueError(f"Unsupported Qwen candidate MIME type: {document.media_type}")
    output_directory.mkdir(parents=True, exist_ok=True)
    if document.media_type == "application/pdf":
        pages = pdf_renderer(document.document_bytes, output_directory)
        if not pages or [item.page_number for item in pages] != list(range(1, len(pages) + 1)):
            raise ValueError("PDF renderer must return every page in contiguous one-based order.")
        return pages

    image_path = output_directory / f"candidate-input{suffix}"
    image_path.write_bytes(document.document_bytes)
    return [PreparedPage(image_path, 1)]


def build_evidence_prompt(page_count: int) -> str:
    """Return the fixed evidence-only instruction sent to every document."""
    return f"""You are a document-evidence extractor. Inspect only the supplied page image(s), in order; there are {page_count} page(s). Return exactly one JSON object and no markdown or commentary.

Use only text and facts visibly present in the supplied document. Do not infer, repair, guess, or invent values. Preserve exact evidence wording. Page numbers are one-based. Do not convert units, infer missing quantities, infer LPG net mass from cylinder count, infer a material grade from vague wording, or infer a freight vehicle class from a vehicle registration/reference.

Identify document type and document domain from visible evidence. document_domain must be one of electricity, diesel, lpg, materials, freight, or UNDETERMINED. For every field you report use evidence_status PRESENT, MISSING, INSUFFICIENT, AMBIGUOUS, or UNDETERMINED. PRESENT has one candidate; AMBIGUOUS preserves all plausible conflicting candidates and their evidence; MISSING means the document was inspected and the evidence is absent; use UNDETERMINED if you cannot tell.

Extract only visible business evidence, including when present: supplier_name, document_date, billing_period, activity_description, quantity, unit, net_lpg_mass, material_identity, geography, electricity_use, vehicle_reference, source_type, combustion_status, operational_control, commercial_institutional, purchase_evidence, transport_mode, transport_scenario, shipment_mass, shipment_mass_unit, distance, distance_unit, and transport_vehicle_class. Do not turn cylinder count into net_lpg_mass. Do not silently choose between conflicting quantities or units.

Return this shape (omit no required top-level keys; use empty arrays when appropriate):
{{
  "document_type": {{"evidence_status":"...","raw_value":"...","normalized_value":"...","evidence":[{{"text":"exact visible text","page":1}}]}},
  "document_domain": {{"evidence_status":"...","raw_value":"electricity|diesel|lpg|materials|freight|UNDETERMINED","normalized_value":"...","evidence":[{{"text":"exact visible text","page":1}}]}},
  "fields": [{{"field_name":"quantity","evidence_status":"...","candidates":[{{"raw_value":"...","normalized_value":"...","raw_unit":"...","normalized_unit":"...","evidence":[{{"text":"exact visible text","page":1}}]}}],"reason":"..."}}],
  "missing_evidence": [{{"field_name":"...","reason":"...","evidence":[]}}],
  "ambiguities": [{{"field_name":"...","reason":"...","candidates":[{{"raw_value":"...","normalized_value":"...","raw_unit":"...","normalized_unit":"...","evidence":[{{"text":"exact visible text","page":1}}]}}],"evidence":[]}}],
  "accounting_readiness":"READY|INCOMPLETE|AMBIGUOUS|UNDETERMINED"
}}

accounting_readiness is only a document-evidence completeness classification for this benchmark. It is not an accounting decision. Never return Scope/category, emission factors, CO2/CO2e values, calculations, or accounting boundaries. Do not add fields outside this JSON shape. Bounding boxes are not requested; do not invent coordinates. Confidence scores are not requested."""


def _plain_scalar(value: Any) -> str | int | float | None:
    if value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    return None


def _field_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    normalized = _FIELD_ALIASES.get(normalized, normalized)
    return normalized if normalized in ALLOWED_FIELD_NAMES else None


def _status(value: Any) -> str:
    candidate = str(value or "UNDETERMINED").strip().upper()
    return candidate if candidate in _EVIDENCE_STATUSES else "UNDETERMINED"


def _bbox(raw: Any) -> BoundingBox | None:
    if not isinstance(raw, dict) or set(raw) != {"x", "y", "width", "height"}:
        return None
    values = [raw.get(name) for name in ("x", "y", "width", "height")]
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in values):
        return None
    x, y, width, height = (float(value) for value in values)
    if min(x, y, width, height) < 0 or x + width > 1 or y + height > 1:
        return None
    return BoundingBox(x=x, y=y, width=width, height=height)


def _evidence_items(raw: Any, page_count: int) -> tuple[EvidenceReference, ...]:
    if isinstance(raw, str):
        raw = [{"text": raw}]
    if not isinstance(raw, list):
        return ()
    result: list[EvidenceReference] = []
    for item in raw:
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text:
            continue
        page = item.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= page_count:
            page = None
        result.append(EvidenceReference(text=text, page=page, bounding_box=_bbox(item.get("bounding_box"))))
    return tuple(result)


def _candidate(raw: Any, page_count: int, *, fallback_evidence: Any = None) -> FieldCandidate:
    if not isinstance(raw, dict):
        raw = {"raw_value": _plain_scalar(raw), "normalized_value": _plain_scalar(raw)}
    evidence_raw = raw.get("evidence", fallback_evidence)
    raw_value = _plain_scalar(raw.get("raw_value", raw.get("value")))
    normalized_value = _plain_scalar(raw.get("normalized_value", raw_value))
    raw_unit = raw.get("raw_unit")
    normalized_unit = raw.get("normalized_unit", raw_unit)
    return FieldCandidate(
        raw_value=raw_value,
        normalized_value=normalized_value,
        raw_unit=raw_unit if isinstance(raw_unit, str) else None,
        normalized_unit=normalized_unit if isinstance(normalized_unit, str) else None,
        confidence=None,
        evidence=_evidence_items(evidence_raw, page_count),
    )


def _parse_json_object(output: str) -> dict[str, Any]:
    """Find the last balanced JSON object in llama.cpp's mixed console output."""
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(output):
        if start is None:
            if char == "{":
                start, depth, in_string, escaped = index, 1, False, False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidates.append(output[start:index + 1])
                start = None
    for candidate_text in reversed(candidates):
        try:
            candidate = json.loads(candidate_text)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    raise ValueError("llama.cpp output did not contain a complete JSON object.")


def parse_qwen_output(output: str, *, candidate_id: str, page_count: int) -> DocumentPrediction:
    """Map Qwen JSON into contract v1 without adding accounting decisions."""
    raw = _parse_json_object(output)
    if not isinstance(raw.get("fields", []), list):
        raise ValueError("Qwen response 'fields' must be an array.")

    raw_fields: dict[str, list[dict[str, Any]]] = {}
    for entry in raw.get("fields", []):
        if not isinstance(entry, dict):
            continue
        name = _field_name(entry.get("field_name", entry.get("field")))
        if name is not None:
            raw_fields.setdefault(name, []).append(entry)

    raw_missing = raw.get("missing_evidence", [])
    missing_by_field: dict[str, list[dict[str, Any]]] = {}
    if isinstance(raw_missing, list):
        for entry in raw_missing:
            if isinstance(entry, dict):
                name = _field_name(entry.get("field_name", entry.get("field")))
                if name:
                    missing_by_field.setdefault(name, []).append(entry)

    raw_ambiguities = raw.get("ambiguities", [])
    ambiguity_by_field: dict[str, list[dict[str, Any]]] = {}
    if isinstance(raw_ambiguities, list):
        for entry in raw_ambiguities:
            if isinstance(entry, dict):
                name = _field_name(entry.get("field_name", entry.get("field")))
                if name:
                    ambiguity_by_field.setdefault(name, []).append(entry)

    fields: list[FieldPrediction] = []
    all_missing: list[MissingEvidence] = []
    all_ambiguities: list[Ambiguity] = []
    for name in FIELD_ORDER:
        if name == "document_type":
            entries = [raw.get("document_type")] if raw.get("document_type") is not None else []
        elif name == "document_domain":
            entries = [raw.get("document_domain")] if raw.get("document_domain") is not None else []
        else:
            entries = raw_fields.get(name, [])

        normalized_entries: list[dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, str):
                normalized_entries.append({"evidence_status": "PRESENT", "raw_value": entry, "normalized_value": entry})
            elif isinstance(entry, dict):
                normalized_entries.append(entry)

        status_values = [_status(item.get("evidence_status", item.get("status"))) for item in normalized_entries]
        candidates: list[FieldCandidate] = []
        reasons: list[str] = []
        for entry in normalized_entries:
            entry_status = _status(entry.get("evidence_status", entry.get("status")))
            candidate_rows = entry.get("candidates")
            if isinstance(candidate_rows, list):
                candidates.extend(_candidate(item, page_count) for item in candidate_rows)
            elif any(key in entry for key in ("raw_value", "normalized_value", "value")):
                candidates.append(_candidate(entry, page_count))
            reason = entry.get("reason")
            if isinstance(reason, str) and reason:
                reasons.append(reason)
            if name == "document_domain" and candidates:
                domain_value = candidates[-1].normalized_value
                if isinstance(domain_value, str) and domain_value.casefold() in SUPPORTED_DOMAINS:
                    normalized_domain = domain_value.casefold()
                    candidates[-1] = FieldCandidate(
                        raw_value=candidates[-1].raw_value,
                        normalized_value=normalized_domain,
                        raw_unit=candidates[-1].raw_unit,
                        normalized_unit=candidates[-1].normalized_unit,
                        confidence=None,
                        evidence=candidates[-1].evidence,
                    )
                else:
                    candidates.clear()
                    status_values[-1] = "UNDETERMINED"
                    reasons.append("Domain is not one of the supported candidate labels.")

        top_ambiguity_rows = ambiguity_by_field.get(name, [])
        top_missing_rows = missing_by_field.get(name, [])
        if top_ambiguity_rows:
            for ambiguity in top_ambiguity_rows:
                ambiguity_candidates = ambiguity.get("candidates", [])
                if not isinstance(ambiguity_candidates, list):
                    ambiguity_candidates = []
                candidates.extend(_candidate(item, page_count) for item in ambiguity_candidates)
                evidence = _evidence_items(ambiguity.get("evidence"), page_count)
                reason = ambiguity.get("reason") if isinstance(ambiguity.get("reason"), str) else None
                all_ambiguities.append(Ambiguity(name, tuple(_candidate(item, page_count) for item in ambiguity_candidates), evidence, reason))

        if len(normalized_entries) > 1 and not top_ambiguity_rows:
            status = "AMBIGUOUS"
            reasons.append("Qwen returned more than one candidate entry for this field.")
            all_ambiguities.append(Ambiguity(name, tuple(candidates), tuple(ref for c in candidates for ref in c.evidence), reasons[-1]))
        elif top_ambiguity_rows or "AMBIGUOUS" in status_values:
            status = "AMBIGUOUS"
            if not top_ambiguity_rows:
                all_ambiguities.append(Ambiguity(name, tuple(candidates), tuple(ref for c in candidates for ref in c.evidence), "; ".join(reasons) or None))
        elif top_missing_rows or "MISSING" in status_values:
            if candidates:
                status = "AMBIGUOUS"
                reason = "Qwen reported both a value and missing evidence for the same field."
                all_ambiguities.append(Ambiguity(name, tuple(candidates), tuple(ref for c in candidates for ref in c.evidence), reason))
            else:
                status = "MISSING"
            if top_missing_rows:
                for item in top_missing_rows:
                    reason = item.get("reason") if isinstance(item.get("reason"), str) else "Qwen explicitly reported this evidence missing."
                    all_missing.append(MissingEvidence(name, reason, _evidence_items(item.get("evidence"), page_count)))
            elif "MISSING" in status_values:
                missing_evidence = tuple(
                    ref
                    for entry in normalized_entries
                    for ref in _evidence_items(entry.get("evidence"), page_count)
                )
                all_missing.append(MissingEvidence(
                    name,
                    "; ".join(dict.fromkeys(reasons)) or "Qwen explicitly reported this field missing.",
                    missing_evidence,
                ))
        elif "INSUFFICIENT" in status_values:
            status = "INSUFFICIENT"
            if not candidates:
                candidates.append(FieldCandidate())
        elif "PRESENT" in status_values:
            if not candidates:
                candidates.append(FieldCandidate())
                status = "INSUFFICIENT"
                reasons.append("Qwen marked evidence present but supplied no scalar candidate.")
            elif len(candidates) == 1:
                status = "PRESENT"
            else:
                status = "AMBIGUOUS"
                all_ambiguities.append(Ambiguity(name, tuple(candidates), tuple(ref for c in candidates for ref in c.evidence), "Qwen returned multiple values for a field marked present."))
        else:
            status = "UNDETERMINED"
            candidates = []

        if name == "document_domain" and candidates:
            domain = candidates[0].normalized_value
            if not isinstance(domain, str) or domain.casefold() not in SUPPORTED_DOMAINS:
                candidates = []
                status = "UNDETERMINED"

        # A cylinder count is observable evidence, but it is not net LPG mass.
        # Retain the evidence as insufficient without converting it to kg.
        if name == "net_lpg_mass" and status == "PRESENT" and candidates:
            candidate = candidates[0]
            unit_text = " ".join(value or "" for value in (candidate.raw_unit, candidate.normalized_unit)).casefold()
            value_text = " ".join(str(value or "") for value in (candidate.raw_value, candidate.normalized_value)).casefold()
            evidence_text = " ".join(ref.text for ref in candidate.evidence).casefold()
            if "cylinder" in unit_text or re.search(r"\b\d+(?:\.\d+)?\s*(?:cylinders?|refills?)\b", f"{value_text} {evidence_text}"):
                candidates[0] = FieldCandidate(
                    raw_value=candidate.raw_value,
                    normalized_value=None,
                    raw_unit=candidate.raw_unit,
                    normalized_unit=None,
                    confidence=None,
                    evidence=candidate.evidence,
                )
                status = "INSUFFICIENT"
                reasons.append("Cylinder count/refill count is not net LPG mass and was not converted.")

        # Preserve a missing statement even when a simultaneous ambiguity was
        # reported; neither claim is silently discarded.
        if top_missing_rows and status == "AMBIGUOUS" and not any(item.field_name == name for item in all_missing):
            all_missing.extend(
                MissingEvidence(name, str(row.get("reason") or "Conflicting missing-evidence statement."), _evidence_items(row.get("evidence"), page_count))
                for row in top_missing_rows
            )

        # De-duplicate candidates while preserving model order.
        unique_candidates: list[FieldCandidate] = []
        candidate_keys: set[str] = set()
        for candidate in candidates:
            key = json.dumps(candidate.to_dict(), sort_keys=True, ensure_ascii=False)
            if key not in candidate_keys:
                candidate_keys.add(key)
                unique_candidates.append(candidate)
        candidates = unique_candidates
        if status in {"MISSING", "UNDETERMINED"}:
            candidates = []
        if status == "PRESENT" and len(candidates) != 1:
            status = "AMBIGUOUS" if len(candidates) > 1 else "INSUFFICIENT"
            if status == "AMBIGUOUS":
                all_ambiguities.append(Ambiguity(name, tuple(candidates), tuple(ref for c in candidates for ref in c.evidence), "Multiple distinct candidates were returned."))
            elif not candidates:
                candidates = [FieldCandidate()]

        reason = "; ".join(dict.fromkeys(reasons)) or None
        source_status = ",".join(status_values) if status_values else ("explicit_missing" if top_missing_rows else "explicit_ambiguity" if top_ambiguity_rows else "not_returned")
        fields.append(FieldPrediction(
            field_name=name,
            evidence_status=status,
            candidate_state="NO_CANDIDATE" if not candidates else "SINGLE_CANDIDATE" if len(candidates) == 1 else "MULTIPLE_CANDIDATES",
            candidates=tuple(candidates),
            source_status=source_status,
            reason=reason or ("Qwen did not return a determination for this field." if not normalized_entries and not top_missing_rows and not top_ambiguity_rows else None),
        ))

    readiness_raw = raw.get("accounting_readiness")
    readiness = str(readiness_raw or "UNDETERMINED").strip().upper()
    if readiness not in _READINESS_STATES:
        readiness = "UNDETERMINED"

    # Keep only explicitly valid annotation-independent missing/ambiguity rows.
    missing_unique: dict[tuple[str, str], MissingEvidence] = {}
    for item in all_missing:
        missing_unique[(item.field_name, item.reason)] = item
    ambiguity_unique: dict[tuple[str, str | None], Ambiguity] = {}
    for item in all_ambiguities:
        ambiguity_unique[(item.field_name, item.reason)] = item

    prediction = DocumentPrediction(
        document_id=candidate_id,
        extracted_fields=tuple(fields),
        accounting_readiness=readiness,
        missing_evidence=tuple(missing_unique.values()),
        ambiguities=tuple(ambiguity_unique.values()),
        review_signal=ReviewSignal(
            review_required=True,
            human_confirmation_required=True,
            explicit_missing_evidence_signal=bool(missing_by_field),
            explicit_ambiguity_signal=bool(ambiguity_by_field),
            reasons=("Qwen output is an uncalibrated evidence-extraction prediction; human confirmation remains required.",),
        ),
        model_metadata=ModelMetadata(
            candidate_name="Qwen3-VL-4B-Instruct-GGUF Q4_K_M via llama.cpp",
            candidate_version=MODEL_REVISION_NOTE,
            adapter_version=ADAPTER_VERSION,
            confidence_calibrated=False,
            confidence_note="No calibrated confidence is produced; candidate confidence fields remain null.",
            evidence_localization_method="Model-provided exact evidence text and one-based page; no bounding boxes are inferred.",
        ),
    )
    validate_prediction(prediction)
    return prediction


class Qwen3VLCandidateAdapter:
    """Run the official local Q4_K_M GGUF candidate using llama.cpp."""

    def __init__(
        self,
        *,
        llama_binary: str | Path,
        model_path: str | Path,
        mmproj_path: str | Path,
        gpu_layers: int = 99,
        timeout_seconds: int = 1800,
        runner: Callable[..., Any] = subprocess.run,
        pdf_renderer: Callable[[bytes, Path], list[PreparedPage]] = render_pdf_pages,
    ) -> None:
        self.llama_binary = str(llama_binary)
        self.model_path = Path(model_path)
        self.mmproj_path = Path(mmproj_path)
        self.gpu_layers = int(gpu_layers)
        self.timeout_seconds = int(timeout_seconds)
        self._runner = runner
        self._pdf_renderer = pdf_renderer
        self.last_latency_seconds: float | None = None
        self.last_page_count: int | None = None
        self.last_process_returncode: int | None = None
        self.last_stdout = ""
        self.last_stderr = ""

    def _command(self, pages: list[PreparedPage]) -> list[str]:
        prompt = build_evidence_prompt(len(pages))
        image_argument = ",".join(str(page.path) for page in pages)
        return [
            self.llama_binary,
            "cli",
            "--single-turn",
            "--offline",
            "-m", str(self.model_path),
            "--mmproj", str(self.mmproj_path),
            "--image", image_argument,
            "-p", prompt,
            "-ngl", str(self.gpu_layers),
            "--mmproj-offload",
            "--simple-io",
            "-n", "4096",
            "--temp", "0",
            "--seed", "1",
        ]

    def predict(self, document: CandidateDocumentInput) -> DocumentPrediction:
        if not isinstance(document, CandidateDocumentInput):
            raise TypeError("Qwen3VLCandidateAdapter accepts CandidateDocumentInput only.")
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Local Q4_K_M model file not found: {self.model_path}")
        if not self.mmproj_path.is_file():
            raise FileNotFoundError(f"Local multimodal projector file not found: {self.mmproj_path}")

        with tempfile.TemporaryDirectory(prefix="greenledger-qwen-candidate-") as temp_name:
            pages = prepare_candidate_pages(
                document, Path(temp_name), pdf_renderer=self._pdf_renderer,
            )
            self.last_page_count = len(pages)
            command = self._command(pages)
            started = time.perf_counter()
            try:
                completed = self._runner(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                self.last_latency_seconds = time.perf_counter() - started
                self.last_stdout = _decode_stream(error.stdout)
                self.last_stderr = _decode_stream(error.stderr)
                raise QwenInferenceError(f"llama.cpp timed out after {self.timeout_seconds} seconds.") from error
            self.last_latency_seconds = time.perf_counter() - started
            self.last_process_returncode = int(getattr(completed, "returncode", 1))
            self.last_stdout = _decode_stream(getattr(completed, "stdout", ""))
            self.last_stderr = _decode_stream(getattr(completed, "stderr", ""))
            if self.last_process_returncode != 0:
                detail = self.last_stderr.strip() or self.last_stdout.strip() or "no console output"
                raise QwenInferenceError(f"llama.cpp exited with {self.last_process_returncode}: {detail[-2000:]}")
            prediction = None
            parse_error: Exception | None = None
            for output in (self.last_stdout, self.last_stderr):
                if not output:
                    continue
                try:
                    prediction = parse_qwen_output(
                        output,
                        candidate_id=document.candidate_id,
                        page_count=len(pages),
                    )
                    break
                except (ValueError, json.JSONDecodeError) as error:
                    parse_error = error
            if prediction is None:
                raise QwenInferenceError("llama.cpp completed but returned no contract-mappable JSON object.") from parse_error
            validate_prediction(prediction)
            return prediction


def _decode_stream(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else str(value or "")


