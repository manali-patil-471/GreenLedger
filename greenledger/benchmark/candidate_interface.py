"""Candidate-only inputs and adapter protocol for benchmark predictions.

Ground-truth annotations are intentionally absent from this module's types and
functions. Candidate IDs are opaque bookkeeping keys; the evaluator runner
maps them to frozen document IDs only after prediction generation completes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contract import DocumentPrediction, validate_prediction


@dataclass(frozen=True)
class CandidateDocumentInput:
    """Prediction-time document data, with no path, filename, or label fields."""

    candidate_id: str
    document_bytes: bytes
    media_type: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty.")
        if not isinstance(self.document_bytes, bytes) or not self.document_bytes:
            raise ValueError("document_bytes must be non-empty bytes.")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ValueError("media_type must be a MIME type.")


class CandidateAdapter(Protocol):
    """A candidate maps one prediction-time document to the shared contract."""

    def predict(self, document: CandidateDocumentInput) -> DocumentPrediction:
        ...


def generate_candidate_predictions(
    adapter: CandidateAdapter,
    documents: list[CandidateDocumentInput],
) -> list[DocumentPrediction]:
    """Run a candidate without any annotation argument or annotation access."""

    predictions: list[DocumentPrediction] = []
    for document in documents:
        if not isinstance(document, CandidateDocumentInput):
            raise TypeError("Candidate adapters accept CandidateDocumentInput only.")
        prediction = adapter.predict(document)
        if not isinstance(prediction, DocumentPrediction):
            raise TypeError("Candidate adapter must return DocumentPrediction.")
        if prediction.document_id != document.candidate_id:
            raise ValueError("Candidate prediction ID must match its opaque candidate_id.")
        validate_prediction(prediction)
        predictions.append(prediction)
    ids = [prediction.document_id for prediction in predictions]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate inputs produced duplicate candidate IDs.")
    return predictions


def remap_prediction_ids(
    predictions: list[DocumentPrediction],
    candidate_to_document_id: dict[str, str],
) -> list[dict[str, object]]:
    """Restore evaluator IDs after candidate generation has finished."""

    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for prediction in predictions:
        data = validate_prediction(prediction)
        candidate_id = data["document_id"]
        if candidate_id not in candidate_to_document_id:
            raise ValueError(f"Unknown candidate ID: {candidate_id}")
        document_id = candidate_to_document_id[candidate_id]
        if document_id in seen:
            raise ValueError(f"Duplicate mapped document ID: {document_id}")
        seen.add(document_id)
        data["document_id"] = document_id
        result.append(validate_prediction(data))
    if seen != set(candidate_to_document_id.values()):
        raise ValueError("Candidate predictions do not cover the candidate ID mapping.")
    return result


def evaluate_after_candidate_generation(
    predictions: list[dict[str, object]],
    annotation_loader,
    evaluator,
):
    """Load references only after candidates are fixed, then score separately."""

    annotations = annotation_loader()
    return evaluator(predictions, annotations)
