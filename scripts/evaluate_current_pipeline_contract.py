"""Run a candidate-only current-pipeline evaluation on the frozen 120 pilot.

Candidate predictions are generated from document bytes before annotations are
loaded. The candidate adapter receives an opaque ID, bytes, and MIME type only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15"
PREVIOUS_CONTRACT_RESULT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_contract_baseline_v1_2026-11-16.json"
DEFAULT_OUTPUT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16.json"
sys.path.insert(0, str(ROOT))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze() -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify frozen files by hash; do not deserialize annotation contents."""

    marker = json.loads((PILOT / "FROZEN.json").read_text(encoding="utf-8"))
    if marker.get("freeze_status") != "FROZEN":
        raise RuntimeError("The pilot has no valid FROZEN marker.")
    if marker.get("validation", {}).get("old_quarantined_test_split_accessed") is not False:
        raise RuntimeError("Freeze marker does not confirm old test split isolation.")
    if _sha256(PILOT / "manifest.json") != marker.get("manifest_sha256"):
        raise RuntimeError("Frozen manifest hash mismatch.")
    if _sha256(PILOT / "annotations.jsonl") != marker.get("annotations_sha256"):
        raise RuntimeError("Frozen annotation hash mismatch.")
    expected = {row["path"]: row for row in marker["hash_scope"]["files"]}
    actual = {
        path.relative_to(PILOT).as_posix()
        for path in PILOT.rglob("*")
        if path.is_file() and path.name != "FROZEN.json"
    }
    if actual != set(expected):
        raise RuntimeError("Frozen pilot file set differs from its marker.")
    for relative, row in expected.items():
        path = PILOT / relative
        if path.stat().st_size != row["bytes"] or _sha256(path) != row["sha256"]:
            raise RuntimeError(f"Frozen pilot hash mismatch: {relative}")
    manifest = json.loads((PILOT / "manifest.json").read_text(encoding="utf-8"))
    return marker, manifest


def build_candidate_inputs(
    manifest: dict[str, Any],
) -> tuple[list[Any], dict[str, str]]:
    """Project manifest rows into label-free candidate inputs.

    Domain, activity, document type, layout family, evidence state, expected
    readiness, and every other manifest field are deliberately not forwarded.
    Original IDs and file paths remain in the evaluator-side mapping only.
    """

    from greenledger.benchmark.candidate_interface import CandidateDocumentInput

    candidates: list[tuple[str, CandidateDocumentInput]] = []
    candidate_to_document_id: dict[str, str] = {}
    rows = manifest.get("documents")
    if not isinstance(rows, list):
        raise ValueError("Frozen manifest does not contain document rows.")
    for row in rows:
        # Read only the locator/hash fields needed by the runner. The candidate
        # sees neither these source fields nor the document's original name.
        document_id = row.get("document_id")
        relative = row.get("file")
        expected_hash = row.get("sha256")
        if not all(isinstance(value, str) and value for value in (document_id, relative, expected_hash)):
            raise ValueError("Manifest row lacks a document ID, file path, or SHA256.")
        path = (PILOT / relative).resolve()
        try:
            path.relative_to(PILOT.resolve())
        except ValueError as error:
            raise ValueError("Manifest document path escapes the frozen pilot.") from error
        content = path.read_bytes()
        if _sha256_bytes(content) != expected_hash:
            raise RuntimeError(f"Document hash differs from manifest: {relative}")
        suffix = path.suffix.casefold()
        media_type = mimetypes.types_map.get(suffix)
        if media_type is None:
            raise ValueError(f"Unsupported frozen document extension: {suffix}")
        candidate_id = "candidate-" + hashlib.sha256(
            ("greenledger-candidate-input-v1:" + expected_hash).encode("ascii")
        ).hexdigest()[:24]
        if candidate_id in candidate_to_document_id:
            raise ValueError("Duplicate opaque candidate ID.")
        candidate_to_document_id[candidate_id] = document_id
        candidates.append((candidate_id, CandidateDocumentInput(candidate_id, content, media_type)))
    candidates.sort(key=lambda item: item[0])
    return [item for _, item in candidates], candidate_to_document_id


def _verify_local_ocr_assets() -> dict[str, str]:
    """Fail before inference if RapidOCR would need to fetch model assets."""

    from greenledger.ocr import RAPIDOCR_MODEL_HASHES

    model_root = ROOT / ".venv-ocr-eval" / "rapidocr_models"
    hashes: dict[str, str] = {}
    for filename, expected in RAPIDOCR_MODEL_HASHES.items():
        path = model_root / filename
        if not path.is_file():
            raise RuntimeError(f"Required local RapidOCR asset is absent: {filename}; no download attempted.")
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(f"Local RapidOCR asset hash mismatch: {filename}; no inference attempted.")
        hashes[filename] = actual
    return hashes


def _load_annotations_after_candidate_predictions() -> list[dict[str, Any]]:
    """This is the only function that deserializes pilot annotations."""

    return [
        json.loads(line)
        for line in (PILOT / "annotations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _metric_snapshot(metrics: dict[str, Any]) -> dict[str, Any]:
    extraction = metrics["carbon_critical_extraction"]
    evidence = metrics["evidence_grounding"]
    missing = metrics["missing_evidence_detection"]
    ambiguity = metrics["ambiguity_detection"]
    readiness = metrics["accounting_readiness"]
    return {
        "carbon_critical_extraction": extraction["aggregate"],
        "normalized_value_accuracy": extraction["normalized_value_accuracy"],
        "per_domain_extraction": extraction["per_domain"],
        "per_field_extraction": extraction["per_field"],
        "evidence_grounding": {
            key: evidence[key] for key in (
                "scalar_candidates_in_critical_fields", "unsupported_values",
                "unsupported_value_rate", "evidence_text_coverage",
                "evidence_text_correctness", "page_correctness", "mean_bbox_iou",
            )
        },
        "missing_evidence_detection": {
            "metrics": missing["metrics"],
            "false_completion_rate": missing["false_completion_rate"],
            "false_completion_count": missing["false_completion_count"],
        },
        "ambiguity_detection": {
            "metrics": ambiguity["metrics"],
            "false_resolution_rate": ambiguity["false_resolution_rate"],
            "false_resolution_count": ambiguity["false_resolution_count"],
        },
        "accounting_readiness": {
            "confusion_matrix_rows_true_columns_predicted": readiness["confusion_matrix_rows_true_columns_predicted"],
            "macro_f1": readiness["macro_f1"],
            "classified_documents": readiness["classified_documents"],
            "undetermined_documents": readiness["undetermined_documents"],
        },
        "document_domain_classification": metrics.get("document_domain_classification"),
    }


def run(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    adapter: Any | None = None,
    annotation_loader: Callable[[], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    output_path = output_path.resolve()
    try:
        output_path.relative_to(PILOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Evaluation output must not be written inside the frozen pilot.")
    if output_path == PREVIOUS_CONTRACT_RESULT.resolve():
        raise ValueError("The previous contract baseline is immutable; use the corrected output path.")

    marker, manifest = verify_freeze()
    freeze_sha = _sha256(PILOT / "FROZEN.json")
    local_ocr_hashes = _verify_local_ocr_assets()

    # Candidate generation is completed before annotations are deserialized.
    from greenledger.benchmark.candidate_interface import (
        evaluate_after_candidate_generation,
        generate_candidate_predictions,
        remap_prediction_ids,
    )
    from greenledger.benchmark.current_pipeline_adapter import CurrentPipelineAdapter
    from greenledger.benchmark.evaluator import evaluate_predictions

    candidate_inputs, candidate_to_document_id = build_candidate_inputs(manifest)
    selected_adapter = adapter or CurrentPipelineAdapter()
    started = time.perf_counter()
    opaque_predictions = generate_candidate_predictions(selected_adapter, candidate_inputs)
    candidate_generation_seconds = time.perf_counter() - started
    predictions = remap_prediction_ids(opaque_predictions, candidate_to_document_id)
    prediction_payload = json.dumps(predictions, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    prediction_digest = hashlib.sha256(prediction_payload).hexdigest()

    evaluation = evaluate_after_candidate_generation(
        predictions,
        annotation_loader or _load_annotations_after_candidate_predictions,
        evaluate_predictions,
    )

    # The prior artifact is read only after candidate predictions have been
    # generated and the evaluator has received those predictions separately.
    previous = json.loads(PREVIOUS_CONTRACT_RESULT.read_text(encoding="utf-8"))
    previous_freeze = previous.get("freeze_verification") or {}
    if previous_freeze.get("freeze_marker_sha256") != freeze_sha:
        raise RuntimeError("Previous contract baseline refers to a different freeze marker.")
    if previous_freeze.get("manifest_sha256") != marker.get("manifest_sha256"):
        raise RuntimeError("Previous contract baseline refers to a different manifest.")
    if previous_freeze.get("annotations_sha256") != marker.get("annotations_sha256"):
        raise RuntimeError("Previous contract baseline refers to different annotations.")
    previous_metrics = previous["evaluation"]["metrics"]
    corrected_metrics = evaluation["metrics"]
    before = _metric_snapshot(previous_metrics)
    after = _metric_snapshot(corrected_metrics)

    from greenledger.ocr import get_ocr_runtime_status
    import importlib.metadata
    import onnxruntime

    marker_after, _manifest_after = verify_freeze()
    if _sha256(PILOT / "FROZEN.json") != freeze_sha or marker_after != marker:
        raise RuntimeError("Frozen marker changed during candidate-only evaluation.")

    output = {
        "benchmark_id": "greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16",
        "status": "COMPLETED",
        "evaluation_only": True,
        "not_training_or_tuning_data": True,
        "candidate_only_protocol": {
            "candidate_inputs": ["opaque candidate_id", "document bytes", "MIME media_type"],
            "forbidden_candidate_inputs": [
                "original document ID", "file path/name", "annotation domain/activity/evidence state",
                "ground-truth field values/status", "expected accounting result", "layout-family labels",
            ],
            "annotations_deserialized_after_predictions": True,
            "candidate_predictions_generated_before_annotation_loader": True,
            "domain_treatment": "candidate-predicted document_domain; no annotation-derived domain passed to adapter",
            "candidate_input_count": len(candidate_inputs),
            "candidate_generation_seconds": candidate_generation_seconds,
            "prediction_sha256": prediction_digest,
            "ocr_rerun": True,
            "deterministic_accounting_run": False,
            "old_quarantined_test_split_accessed": False,
        },
        "freeze_verification": {
            "freeze_status": marker["freeze_status"],
            "freeze_marker_sha256": freeze_sha,
            "manifest_sha256": marker["manifest_sha256"],
            "annotations_sha256": marker["annotations_sha256"],
            "covered_files_verified": marker["hash_scope"]["covered_file_count"],
            "documents": marker["counts"]["documents"],
            "frozen_dataset_modified": False,
            "old_quarantined_test_split_accessed": False,
        },
        "runtime": {
            "python": sys.version,
            "platform": sys.platform,
            "rapidocr": get_ocr_runtime_status(),
            "onnxruntime": importlib.metadata.version("onnxruntime"),
            "onnxruntime_providers": onnxruntime.get_available_providers(),
            "local_rapidocr_model_sha256": local_ocr_hashes,
        },
        "source_code_sha256": {
            "candidate_interface": _sha256(ROOT / "greenledger/benchmark/candidate_interface.py"),
            "current_pipeline_adapter": _sha256(ROOT / "greenledger/benchmark/current_pipeline_adapter.py"),
            "evaluator": _sha256(ROOT / "greenledger/benchmark/evaluator.py"),
            "runner": _sha256(Path(__file__).resolve()),
            "contract_schema": _sha256(ROOT / "data/benchmark/contracts/GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1.json"),
        },
        "dataset": {
            "documents": marker["counts"]["documents"],
            "by_domain": marker["counts"]["by_domain"],
            "by_evidence_state": marker["counts"]["by_evidence_state"],
        },
        "previous_contract_baseline": str(PREVIOUS_CONTRACT_RESULT.relative_to(ROOT)).replace("\\", "/"),
        "before_vs_after": {
            "previous_prediction_sha256": previous.get("source_baseline_prediction_digest"),
            "previous_metrics": before,
            "corrected_metrics": after,
        },
        "predictions": predictions,
        "evaluation": evaluation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = run(args.output)
    metrics = output["evaluation"]["metrics"]
    print("Candidate-only contract evaluation complete: {} documents".format(len(output["predictions"])))
    print("Extraction: {}".format(metrics["carbon_critical_extraction"]["aggregate"]))
    print("Domain classification: {}".format(metrics["document_domain_classification"]))
    print("Metrics: {}".format(args.output))


if __name__ == "__main__":
    main()
