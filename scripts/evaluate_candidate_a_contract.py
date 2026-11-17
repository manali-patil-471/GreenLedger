"""Evaluate the existing Candidate A extractor on the frozen 120 pilot.

Candidate predictions are generated from opaque IDs, document bytes and MIME
types before the frozen annotations are deserialized for scoring.
"""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15"
CURRENT_RESULT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16.json"
DEFAULT_OUTPUT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_candidate_a_contract_v1_2026-11-16.json"
EXPECTED_ARTIFACT_SHA256 = "6b7cecb47346fa8582eb4dc3963a746bf932c06874caa784f98bcd6a53d205ab"
sys.path.insert(0, str(ROOT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _peak_working_set_bytes() -> int | None:
    """Return Windows process peak working set using only the standard library."""
    if sys.platform != "win32":
        return None

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    try:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCountersEx),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return None
        return int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError):
        return None


def _metric_comparison(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    current_metrics = current["evaluation"]["metrics"]
    candidate_metrics = candidate["metrics"]
    current_extract = current_metrics["carbon_critical_extraction"]["aggregate"]
    candidate_extract = candidate_metrics["carbon_critical_extraction"]["aggregate"]
    current_missing = current_metrics["missing_evidence_detection"]["metrics"]
    candidate_missing = candidate_metrics["missing_evidence_detection"]["metrics"]
    current_ambiguity = current_metrics["ambiguity_detection"]["metrics"]
    candidate_ambiguity = candidate_metrics["ambiguity_detection"]["metrics"]
    current_readiness = current_metrics["accounting_readiness"]["macro_f1"]
    candidate_readiness = candidate_metrics["accounting_readiness"]["macro_f1"]
    current_domain = current_metrics["document_domain_classification"]
    candidate_domain = candidate_metrics["document_domain_classification"]
    current_runtime = current["candidate_only_protocol"]["candidate_generation_seconds"]
    candidate_runtime = candidate["runtime"]["candidate_generation_seconds"]
    rows = {
        "precision": (current_extract["precision"], candidate_extract["precision"]),
        "recall": (current_extract["recall"], candidate_extract["recall"]),
        "f1": (current_extract["f1"], candidate_extract["f1"]),
        "unsupported_value_rate": (
            current_metrics["evidence_grounding"]["unsupported_value_rate"],
            candidate_metrics["evidence_grounding"]["unsupported_value_rate"],
        ),
        "missing_evidence_f1": (current_missing["f1"], candidate_missing["f1"]),
        "ambiguity_f1": (current_ambiguity["f1"], candidate_ambiguity["f1"]),
        "readiness_macro_f1": (current_readiness, candidate_readiness),
        "domain_accuracy": (current_domain["accuracy"], candidate_domain["accuracy"]),
        "domain_macro_f1": (current_domain["macro_f1"], candidate_domain["macro_f1"]),
        "mean_candidate_seconds_per_document": (current_runtime / 120, candidate_runtime / 120),
    }
    return {
        key: {
            "current_pipeline": left,
            "candidate_a": right,
            "difference_candidate_a_minus_current": (
                right - left if left is not None and right is not None else None
            ),
        }
        for key, (left, right) in rows.items()
    }


class _TimedAdapter:
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.rows: list[dict[str, Any]] = []

    def predict(self, document):
        started = time.perf_counter()
        prediction = self.adapter.predict(document)
        elapsed = time.perf_counter() - started
        self.rows.append({
            "candidate_id": document.candidate_id,
            "total_seconds": elapsed,
            "ocr_seconds": getattr(self.adapter, "last_ocr_latency_seconds", None),
            "ocr_status": getattr(self.adapter, "last_ocr_status", None),
        })
        return prediction


def run(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    adapter: Any | None = None,
    annotation_loader: Callable[[], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    from greenledger.benchmark.candidate_a_adapter import CandidateAAdapter
    from greenledger.benchmark.candidate_interface import (
        evaluate_after_candidate_generation,
        generate_candidate_predictions,
        remap_prediction_ids,
    )
    from greenledger.benchmark.contract import CONTRACT_VERSION
    from greenledger.benchmark.evaluator import evaluate_predictions
    from scripts.evaluate_current_pipeline_contract import (
        _load_annotations_after_candidate_predictions,
        _verify_local_ocr_assets,
        build_candidate_inputs,
        verify_freeze,
    )

    output_path = Path(output_path).resolve()
    try:
        output_path.relative_to(PILOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Evaluation output must not be written inside the frozen pilot.")
    if output_path in {CURRENT_RESULT.resolve(), DEFAULT_OUTPUT.resolve()} and output_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing benchmark result: {output_path}")
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing benchmark result: {output_path}")

    overall_started = time.perf_counter()
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        owns_tracemalloc = True
    else:
        owns_tracemalloc = False

    marker, manifest = verify_freeze()
    freeze_sha = _sha256(PILOT / "FROZEN.json")
    artifact_path = ROOT / "models/ai_field_extraction/char_ngram_line_role_v1.json"
    artifact_sha = _sha256(artifact_path)
    if artifact_sha != EXPECTED_ARTIFACT_SHA256:
        raise RuntimeError(
            f"Candidate A artifact SHA256 mismatch: expected {EXPECTED_ARTIFACT_SHA256}, got {artifact_sha}."
        )
    local_ocr_hashes = _verify_local_ocr_assets()

    # No annotation data is loaded here. The manifest projection supplies only
    # bytes/MIME and an opaque candidate ID to the adapter.
    candidate_inputs, candidate_to_document_id = build_candidate_inputs(manifest)
    selected_adapter = adapter or CandidateAAdapter(model_path=artifact_path)
    timed_adapter = _TimedAdapter(selected_adapter)
    candidate_started = time.perf_counter()
    opaque_predictions = generate_candidate_predictions(timed_adapter, candidate_inputs)
    candidate_generation_seconds = time.perf_counter() - candidate_started
    predictions = remap_prediction_ids(opaque_predictions, candidate_to_document_id)
    prediction_payload = json.dumps(
        predictions, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    prediction_sha = hashlib.sha256(prediction_payload).hexdigest()

    # This is the first point at which the frozen annotation file is read.
    evaluation = evaluate_after_candidate_generation(
        predictions,
        annotation_loader or _load_annotations_after_candidate_predictions,
        evaluate_predictions,
    )

    marker_after, _manifest_after = verify_freeze()
    if marker_after != marker or _sha256(PILOT / "FROZEN.json") != freeze_sha:
        raise RuntimeError("Frozen marker changed during Candidate A evaluation.")
    if _sha256(artifact_path) != artifact_sha:
        raise RuntimeError("Candidate A artifact changed during evaluation.")

    current = json.loads(CURRENT_RESULT.read_text(encoding="utf-8"))
    current_freeze = current.get("freeze_verification", {})
    if (
        current_freeze.get("freeze_marker_sha256") != freeze_sha
        or current_freeze.get("manifest_sha256") != marker.get("manifest_sha256")
        or current_freeze.get("annotations_sha256") != marker.get("annotations_sha256")
    ):
        raise RuntimeError("Current-pipeline baseline does not refer to the same frozen pilot.")

    document_id_by_candidate = candidate_to_document_id
    per_document_runtime = [
        {
            "document_id": document_id_by_candidate[row["candidate_id"]],
            "total_seconds": row["total_seconds"],
            "ocr_seconds": row["ocr_seconds"],
            "downstream_seconds": (
                max(0.0, row["total_seconds"] - row["ocr_seconds"])
                if row["ocr_seconds"] is not None else None
            ),
            "ocr_status": row["ocr_status"],
        }
        for row in timed_adapter.rows
    ]
    elapsed_values = [row["total_seconds"] for row in per_document_runtime]
    ocr_values = [row["ocr_seconds"] for row in per_document_runtime if row["ocr_seconds"] is not None]
    downstream_values = [row["downstream_seconds"] for row in per_document_runtime if row["downstream_seconds"] is not None]
    current_metrics = current["evaluation"]["metrics"]
    metrics = evaluation["metrics"]

    try:
        import numpy
        numpy_version = numpy.__version__
    except Exception:
        numpy_version = None
    try:
        rapidocr_version = importlib.metadata.version("rapidocr")
    except importlib.metadata.PackageNotFoundError:
        rapidocr_version = None
    try:
        onnx_version = importlib.metadata.version("onnxruntime")
    except importlib.metadata.PackageNotFoundError:
        onnx_version = None
    try:
        pillow_version = importlib.metadata.version("Pillow")
    except importlib.metadata.PackageNotFoundError:
        pillow_version = None

    source_files = {
        "greenledger/ai_field_extraction.py": ROOT / "greenledger/ai_field_extraction.py",
        "greenledger/field_extraction.py": ROOT / "greenledger/field_extraction.py",
        "greenledger/core.py": ROOT / "greenledger/core.py",
        "greenledger/ocr.py": ROOT / "greenledger/ocr.py",
        "greenledger/benchmark/candidate_interface.py": ROOT / "greenledger/benchmark/candidate_interface.py",
        "greenledger/benchmark/candidate_a_adapter.py": ROOT / "greenledger/benchmark/candidate_a_adapter.py",
        "greenledger/benchmark/contract.py": ROOT / "greenledger/benchmark/contract.py",
        "greenledger/benchmark/evaluator.py": ROOT / "greenledger/benchmark/evaluator.py",
        "scripts/evaluate_current_pipeline_contract.py": ROOT / "scripts/evaluate_current_pipeline_contract.py",
        "scripts/evaluate_candidate_a_contract.py": Path(__file__).resolve(),
        "data/benchmark/contracts/GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1.json": ROOT / "data/benchmark/contracts/GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1.json",
    }
    source_hashes = {name: _sha256(path) for name, path in source_files.items()}

    tracemalloc_current, tracemalloc_peak = tracemalloc.get_traced_memory()
    if owns_tracemalloc:
        tracemalloc.stop()
    elapsed_total = time.perf_counter() - overall_started
    peak_working_set = _peak_working_set_bytes()

    model_info = json.loads(artifact_path.read_text(encoding="utf-8"))
    result = {
        "benchmark_id": "greenledger_unseen_structure_pilot_120_candidate_a_contract_v1_2026-11-16",
        "status": "COMPLETED",
        "evaluation_only": True,
        "not_training_or_tuning_data": True,
        "candidate": {
            "name": "Candidate A: supervised character n-gram line-role extractor",
            "model_id": model_info.get("model_id"),
            "method": model_info.get("method"),
            "artifact_path": artifact_path.relative_to(ROOT).as_posix(),
            "artifact_sha256": artifact_sha,
            "training_split": model_info.get("training_split"),
            "training_documents": model_info.get("training_documents"),
            "retrained_or_tuned_on_pilot": False,
            "confidence_calibrated": model_info.get("confidence_calibrated"),
        },
        "candidate_only_protocol": {
            "candidate_inputs": ["opaque candidate_id", "document bytes", "MIME media_type"],
            "forbidden_candidate_inputs": [
                "original document ID", "file path/name", "annotation objects or domain",
                "annotation field values/status", "expected missing/ambiguous labels",
                "expected accounting result", "manifest ground-truth fields",
            ],
            "annotations_deserialized_after_predictions": True,
            "candidate_predictions_generated_before_annotation_loader": True,
            "ocr_path": "Existing RapidOCR recognize_upload on candidate bytes; generic candidate-input filename only.",
            "candidate_a_input": "RapidOCR transcription string; no page-level layout or annotation data.",
            "candidate_input_count": len(candidate_inputs),
            "candidate_generation_seconds": candidate_generation_seconds,
            "prediction_sha256": prediction_sha,
            "old_quarantined_test_split_accessed": False,
        },
        "freeze_verification": {
            "freeze_status": marker.get("freeze_status"),
            "freeze_marker_sha256": freeze_sha,
            "manifest_sha256": marker.get("manifest_sha256"),
            "annotations_sha256": marker.get("annotations_sha256"),
            "covered_files_verified": len(marker["hash_scope"]["files"]),
            "documents": len(manifest["documents"]),
            "frozen_dataset_modified": False,
            "old_quarantined_test_split_accessed": False,
        },
        "runtime": {
            "evaluation_total_seconds": elapsed_total,
            "candidate_generation_seconds": candidate_generation_seconds,
            "mean_seconds_per_document": statistics.mean(elapsed_values) if elapsed_values else None,
            "median_seconds_per_document": statistics.median(elapsed_values) if elapsed_values else None,
            "ocr_mean_seconds_per_document": statistics.mean(ocr_values) if ocr_values else None,
            "ocr_median_seconds_per_document": statistics.median(ocr_values) if ocr_values else None,
            "downstream_mean_seconds_per_document": statistics.mean(downstream_values) if downstream_values else None,
            "downstream_median_seconds_per_document": statistics.median(downstream_values) if downstream_values else None,
            "peak_working_set_bytes": peak_working_set,
            "peak_traced_python_bytes": tracemalloc_peak,
            "traced_python_current_bytes_at_end": tracemalloc_current,
            "python": sys.version,
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "gpu_used": False,
            "packages": {
                "rapidocr": rapidocr_version,
                "onnxruntime": onnx_version,
                "numpy": numpy_version,
                "Pillow": pillow_version,
                "pytorch_used_for_inference": False,
            },
            "ocr_assets_sha256": local_ocr_hashes,
        },
        "evaluation_configuration": {
            "prediction_contract_version": CONTRACT_VERSION,
            "evaluator": "greenledger.benchmark.evaluator.evaluate_predictions",
            "same_evaluator_as_current_pipeline": True,
            "same_ground_truth": True,
            "ocr_metrics_included": False,
            "source_code_sha256": source_hashes,
            "source_hashes_recorded_post_run": False,
        },
        "metrics": metrics,
        "comparison_with_current_pipeline": {
            "current_pipeline_prediction_sha256": current["candidate_only_protocol"]["prediction_sha256"],
            "candidate_a_prediction_sha256": prediction_sha,
            "metrics": _metric_comparison(current, {"metrics": metrics, "runtime": {"candidate_generation_seconds": candidate_generation_seconds}}),
            "per_domain_extraction": {
                domain: {
                    "current_pipeline": current_metrics["carbon_critical_extraction"]["per_domain"].get(domain),
                    "candidate_a": metrics["carbon_critical_extraction"]["per_domain"].get(domain),
                }
                for domain in ("electricity", "diesel", "lpg", "materials", "freight")
            },
            "per_field_extraction": {
                field: {
                    "current_pipeline": current_metrics["carbon_critical_extraction"]["per_field"].get(field),
                    "candidate_a": metrics["carbon_critical_extraction"]["per_field"].get(field),
                }
                for field in sorted(set(current_metrics["carbon_critical_extraction"]["per_field"]) | set(metrics["carbon_critical_extraction"]["per_field"]))
            },
            "interpretation_note": "Descriptive paired-set comparison only; no significance test or confidence interval is claimed.",
        },
        "per_document_runtime": per_document_runtime,
        "predictions": predictions,
        "evaluation": evaluation,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.output)
    extraction = result["metrics"]["carbon_critical_extraction"]["aggregate"]
    print(json.dumps({
        "status": result["status"],
        "output": str(args.output.resolve()),
        "documents": len(result["predictions"]),
        "artifact_sha256": result["candidate"]["artifact_sha256"],
        "prediction_sha256": result["candidate_only_protocol"]["prediction_sha256"],
        "carbon_critical_extraction": extraction,
        "runtime": result["runtime"],
    }, indent=2))


if __name__ == "__main__":
    main()
