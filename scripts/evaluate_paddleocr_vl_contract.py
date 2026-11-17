"""Run the PaddleOCR-VL 1.6 candidate-only evaluation on the frozen pilot.

All document predictions are generated and freeze-checked before annotations
are deserialized. The pilot is never used for training, prompting, or tuning.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15"
OUTPUT_DEFAULT = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_paddleocr_vl_16_contract_v1_2026-11-17.json"
PADDLE_CACHE = ROOT / "models/paddleocr_vl_16_cache"
ENGINE = "transformers"
CURRENT_BASELINE = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16.json"
CANDIDATE_A = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_candidate_a_contract_v1_2026-11-16.json"
sys.path.insert(0, str(ROOT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files_hash(paths: list[Path]) -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): _sha256(path) for path in paths}


def _failure_prediction(candidate_id: str, error: str):
    from greenledger.benchmark.contract import (
        DocumentPrediction, FieldPrediction, ModelMetadata, ReviewSignal,
    )

    names = (
        "document_type", "document_domain", "activity_description", "supplier_name", "document_date",
        "billing_period", "quantity", "unit", "net_lpg_mass", "material_identity", "geography",
        "electricity_use", "vehicle_reference", "source_type", "combustion_status", "operational_control",
        "commercial_institutional", "purchase_evidence", "transport_mode", "transport_scenario",
        "shipment_mass", "shipment_mass_unit", "distance", "distance_unit", "transport_vehicle_class",
    )
    return DocumentPrediction(
        document_id=candidate_id,
        extracted_fields=tuple(FieldPrediction(name, "UNDETERMINED", "NO_CANDIDATE", (), "inference_failure", error) for name in names),
        accounting_readiness="UNDETERMINED",
        review_signal=ReviewSignal(review_required=True, human_confirmation_required=True, reasons=(error,)),
        model_metadata=ModelMetadata(
            candidate_name="PaddleOCR-VL-1.6 inference failure",
            candidate_version=f"PaddleOCR full pipeline v1.6; {ENGINE} engine; runtime versions recorded in result artifact",
            adapter_version="paddleocr-vl-1.6-contract-v1",
            confidence_calibrated=False,
            confidence_note="No model prediction was available for this document.",
            evidence_localization_method=None,
        ),
    )


class _FailureCapturingAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.failures: list[dict[str, str]] = []
        self.pages: dict[str, list[dict[str, Any]]] = {}
        self.latencies: dict[str, float] = {}

    def predict(self, document):
        from greenledger.benchmark.contract import validate_prediction

        try:
            prediction = self.adapter.predict(document)
            self.pages[document.candidate_id] = self.adapter.last_pages
            self.latencies[document.candidate_id] = self.adapter.last_inference_seconds
            if not self.pages[document.candidate_id]:
                raise RuntimeError("PaddleOCR-VL returned no page results.")
            if not any(page.get("blocks") for page in self.pages[document.candidate_id]):
                raise RuntimeError("PaddleOCR-VL returned page results but no parsed text/layout blocks.")
            validate_prediction(prediction)
            return prediction
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            self.failures.append({"candidate_id": document.candidate_id, "reason": message})
            self.pages[document.candidate_id] = []
            self.latencies[document.candidate_id] = getattr(self.adapter, "last_inference_seconds", 0.0)
            return _failure_prediction(document.candidate_id, message)


class _ResourceSampler:
    def __init__(self, interval_seconds: float = 0.5):
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = None
        self.peak_rss = 0
        self.peak_system_used = 0
        self.cpu_samples: list[float] = []
        self.error: str | None = None

    def start(self) -> None:
        try:
            import psutil
            self.process = psutil.Process()
        except Exception as error:
            self.error = f"psutil unavailable: {type(error).__name__}: {error}"
            return
        self.process.cpu_percent(None)
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()

    def _sample(self) -> None:
        import psutil

        while not self.stop_event.wait(self.interval_seconds):
            try:
                self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
                self.peak_system_used = max(self.peak_system_used, psutil.virtual_memory().used)
                self.cpu_samples.append(float(self.process.cpu_percent(None)))
            except Exception as error:
                self.error = f"resource sample failed: {type(error).__name__}: {error}"
                return

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        if getattr(self, "process", None):
            try:
                self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
            except Exception:
                pass
        return {
            "peak_process_rss_bytes": self.peak_rss or None,
            "peak_system_used_bytes": self.peak_system_used or None,
            "mean_process_cpu_percent_sampled": statistics.mean(self.cpu_samples) if self.cpu_samples else None,
            "max_process_cpu_percent_sampled": max(self.cpu_samples) if self.cpu_samples else None,
            "sampling_interval_seconds": self.interval_seconds,
            "sampling_note": "Process RSS and process CPU sampled during model load and candidate inference; short peaks between samples may be missed.",
            "sampling_error": self.error,
        }


def _count_pdf_pages_and_text(document_bytes: bytes) -> tuple[int | None, bool | None]:
    try:
        import pypdfium2
        pdf = pypdfium2.PdfDocument(document_bytes)
        page_count = len(pdf)
        text_chars = 0
        for index in range(page_count):
            page = pdf[index]
            text_page = page.get_textpage()
            text_chars += len(text_page.get_text_range().strip())
            text_page.close()
            page.close()
        pdf.close()
        return page_count, text_chars > 0
    except Exception:
        # The PDF is still given to the model unchanged; this is only smoke
        # sample selection metadata, not candidate input or model evidence.
        try:
            import pypdfium2
            pdf = pypdfium2.PdfDocument(document_bytes)
            count = len(pdf)
            pdf.close()
            return count, None
        except Exception:
            return None, None


def _select_smoke_ids(candidate_inputs: list[Any]) -> list[str]:
    """Select 7 candidate inputs by format/page properties only, never labels."""
    pdfs: list[tuple[Any, int | None, bool | None]] = []
    images: list[Any] = []
    for item in candidate_inputs:
        if item.media_type == "application/pdf":
            count, has_text_layer = _count_pdf_pages_and_text(item.document_bytes)
            pdfs.append((item, count, has_text_layer))
        elif item.media_type.startswith("image/"):
            images.append(item)
    selected: list[Any] = []

    def take(candidate: Any | None) -> None:
        if candidate is not None and candidate not in selected:
            selected.append(candidate)

    take(next((item for item, count, text in pdfs if count == 1 and text is True), None))
    take(next((item for item, count, text in pdfs if count == 1 and text is False), None))
    take(images[0] if images else None)
    take(next((item for item, count, _text in pdfs if count and count > 1), None))
    # Fill remaining slots by opaque-ID order. No original filename, path,
    # domain, annotation, or manifest label is consulted for sample selection.
    for item in sorted(candidate_inputs, key=lambda value: value.candidate_id):
        take(item)
        if len(selected) >= min(7, len(candidate_inputs)):
            break
    return [item.candidate_id for item in selected[:7]]


def _package_versions() -> dict[str, str | None]:
    names = (
        "paddlepaddle", "paddleocr", "paddlex", "torch", "torchvision", "transformers",
        "accelerate", "numpy", "Pillow", "opencv-contrib-python", "pypdfium2", "safetensors",
        "huggingface-hub", "tokenizers", "protobuf", "psutil",
    )
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _hardware_snapshot() -> dict[str, Any]:
    try:
        import psutil
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_count(logical=False), psutil.cpu_count(logical=True)
        return {
            "cpu_physical_logical": {"physical": cpu[0], "logical": cpu[1]},
            "total_ram_bytes": memory.total,
            "available_ram_bytes_at_snapshot": memory.available,
            "gpu": "Intel Iris Xe integrated graphics; PaddlePaddle reports CPU build (CUDA unavailable).",
        }
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


def _cache_weight_manifest() -> list[dict[str, Any]]:
    if not PADDLE_CACHE.exists():
        return []
    suffixes = {".safetensors", ".pdparams", ".pdiparams", ".pdmodel", ".onnx", ".bin"}
    rows = []
    for path in sorted(PADDLE_CACHE.rglob("*")):
        if path.is_file() and path.suffix.casefold() in suffixes:
            rows.append({
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    return rows


def _stable_json_digest(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _baseline_payload() -> dict[str, Any]:
    result = {}
    for name, path in (("current_pipeline", CURRENT_BASELINE), ("candidate_a", CANDIDATE_A)):
        if path.exists():
            result[name] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(output_path: Path = OUTPUT_DEFAULT, *, max_documents: int | None = None) -> dict[str, Any]:
    output_path = output_path.resolve()
    if output_path.is_relative_to(PILOT.resolve()):
        raise ValueError("Evaluation output must be outside the frozen pilot directory.")

    # This checks annotations by digest only; it does not deserialize their
    # content. Candidate inputs are produced from bytes and opaque IDs only.
    from scripts.evaluate_current_pipeline_contract import (
        _load_annotations_after_candidate_predictions,
        build_candidate_inputs,
        verify_freeze,
    )
    from greenledger.benchmark.candidate_interface import remap_prediction_ids
    from greenledger.benchmark.evaluator import evaluate_predictions
    from greenledger.benchmark.paddleocr_vl_adapter import (
        MODEL_ID, PIPELINE_MODEL_NAME, PaddleOCRVLCandidateAdapter,
    )

    marker, manifest = verify_freeze()
    freeze_sha = _sha256(PILOT / "FROZEN.json")
    frozen_files_before = {
        item["path"]: item["sha256"] for item in marker["hash_scope"]["files"]
    }
    candidate_inputs, candidate_to_document_id = build_candidate_inputs(manifest)
    if max_documents is not None:
        if not 1 <= max_documents <= len(candidate_inputs):
            raise ValueError("max_documents must be within the frozen document count.")
        candidate_inputs = candidate_inputs[:max_documents]
        candidate_to_document_id = {
            item.candidate_id: candidate_to_document_id[item.candidate_id] for item in candidate_inputs
        }

    smoke_ids = set(_select_smoke_ids(candidate_inputs))
    cache_existed_before = any(PADDLE_CACHE.rglob("*")) if PADDLE_CACHE.exists() else False
    PADDLE_CACHE.mkdir(parents=True, exist_ok=True)
    sampler = _ResourceSampler()
    sampler.start()
    load_started = time.perf_counter()
    try:
        selected_adapter = PaddleOCRVLCandidateAdapter(model_cache_dir=PADDLE_CACHE, engine=ENGINE)
    except Exception as error:
        load_error = f"{type(error).__name__}: {error}"
        resource = sampler.stop()
        marker_after, _ = verify_freeze()
        result = {
            "benchmark_id": "greenledger_unseen_structure_pilot_120_paddleocr_vl_16_contract_v1_2026-11-17",
            "status": "BLOCKED_MODEL_LOAD_FAILURE",
            "candidate_name": f"PaddleOCR-VL 1.6 full document parsing pipeline ({ENGINE} engine)",
            "engine": ENGINE,
            "model_identifier": MODEL_ID,
            "pipeline_model_name": PIPELINE_MODEL_NAME,
            "model_load_seconds": time.perf_counter() - load_started,
            "model_load_failure": load_error,
            "candidate_predictions_generated": 0,
            "annotations_deserialized": False,
            "resource_measurements": resource,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "package_versions": _package_versions(),
                "hardware": _hardware_snapshot(),
            },
            "freeze_verification": {
                "freeze_marker_sha256": freeze_sha,
                "manifest_sha256": marker["manifest_sha256"],
                "annotations_sha256": marker["annotations_sha256"],
                "unchanged": marker_after == marker,
                "old_quarantined_test_split_accessed": False,
            },
        }
        _write_result(output_path, result)
        return result
    model_load_seconds = time.perf_counter() - load_started
    wrapped = _FailureCapturingAdapter(selected_adapter)

    predictions = []
    prediction_input_order: list[str] = []
    smoke_outcomes: list[dict[str, Any]] = []
    candidate_generation_started = time.perf_counter()
    smoke_passed = True
    remaining = list(candidate_inputs)

    # Run the initial smoke batch first. All selected inputs are based only on
    # file bytes/MIME and PDF page/text-layer properties, never labels.
    smoke_batch = [item for item in remaining if item.candidate_id in smoke_ids]
    remainder = [item for item in remaining if item.candidate_id not in smoke_ids]
    ordered_inputs = smoke_batch + remainder
    for index, item in enumerate(ordered_inputs):
        prediction = wrapped.predict(item)
        predictions.append(prediction)
        prediction_input_order.append(item.candidate_id)
        if item.candidate_id in smoke_ids:
            outcome = {
                "candidate_id": item.candidate_id,
                "page_result_count": len(wrapped.pages.get(item.candidate_id, [])),
                "parsed_block_count": sum(len(page.get("blocks", [])) for page in wrapped.pages.get(item.candidate_id, [])),
                "predicted_domain": next((field.candidates[0].normalized_value for field in prediction.extracted_fields if field.field_name == "document_domain" and field.candidates), None),
                "predicted_readiness": prediction.accounting_readiness,
                "failure": next((row["reason"] for row in wrapped.failures if row["candidate_id"] == item.candidate_id), None),
            }
            smoke_outcomes.append(outcome)
            if outcome["failure"] or not outcome["page_result_count"] or not outcome["parsed_block_count"]:
                smoke_passed = False
        if index + 1 == len(smoke_batch):
            # Preserve the requested feasibility gate. Do not deserialize any
            # annotations if the model failed to parse one of the smoke inputs.
            if not smoke_passed:
                resource = sampler.stop()
                marker_after, _ = verify_freeze()
                result = {
                    "benchmark_id": "greenledger_unseen_structure_pilot_120_paddleocr_vl_16_contract_v1_2026-11-17",
                    "status": "BLOCKED_SMOKE_FAILURE",
                    "candidate_name": f"PaddleOCR-VL 1.6 full document parsing pipeline ({ENGINE} engine)",
                    "engine": ENGINE,
                    "model_identifier": MODEL_ID,
                    "pipeline_model_name": PIPELINE_MODEL_NAME,
                    "smoke_test": {"selected_count": len(smoke_batch), "pass": False, "results": smoke_outcomes},
                    "candidate_predictions_generated": len(predictions),
                    "annotations_deserialized": False,
                    "failure_count": len(wrapped.failures),
                    "failures": wrapped.failures,
                    "resource_measurements": resource,
                    "freeze_verification": {
                        "freeze_marker_sha256": freeze_sha,
                        "manifest_sha256": marker["manifest_sha256"],
                        "annotations_sha256": marker["annotations_sha256"],
                        "unchanged": marker_after == marker,
                        "old_quarantined_test_split_accessed": False,
                    },
                    "limitations": ["Smoke failure stopped full evaluation before ground-truth annotations were loaded."],
                }
                _write_result(output_path, result)
                return result
            break

    candidate_generation_seconds = time.perf_counter() - candidate_generation_started
    mapped = remap_prediction_ids(predictions, candidate_to_document_id)
    prediction_digest = _stable_json_digest(mapped)
    candidate_predictions_generated = len(predictions)

    # Verify frozen files once more after every model output is fixed, then and
    # only then deserialize the answer key for evaluation.
    marker_after, _manifest_after = verify_freeze()
    if marker_after != marker or _sha256(PILOT / "FROZEN.json") != freeze_sha:
        raise RuntimeError("Frozen dataset changed during candidate inference.")
    before_scoring_hashes = {item["path"]: item["sha256"] for item in marker_after["hash_scope"]["files"]}
    if before_scoring_hashes != frozen_files_before:
        raise RuntimeError("Frozen pilot files changed during candidate inference.")
    annotations_deserialized = False

    def load_annotations_after_inference():
        nonlocal annotations_deserialized
        if candidate_predictions_generated != len(candidate_inputs):
            raise RuntimeError("Refusing to load annotations before candidate predictions cover the evaluation set.")
        annotations_deserialized = True
        return _load_annotations_after_candidate_predictions()

    if len(candidate_inputs) != 120:
        raise RuntimeError("A partial smoke run cannot be scored as the frozen 120-document benchmark.")
    evaluation = evaluate_predictions(mapped, load_annotations_after_inference())
    resource = sampler.stop()
    candidate_generation_seconds = time.perf_counter() - candidate_generation_started
    latencies = [wrapped.latencies.get(candidate_id, 0.0) for candidate_id in prediction_input_order]
    latencies = [value for value in latencies if value > 0]

    current_and_a = _baseline_payload()
    marker_final, _ = verify_freeze()
    if marker_final != marker or _sha256(PILOT / "FROZEN.json") != freeze_sha:
        raise RuntimeError("Frozen dataset changed during scoring.")
    final_hashes = {item["path"]: item["sha256"] for item in marker_final["hash_scope"]["files"]}
    if final_hashes != frozen_files_before:
        raise RuntimeError("Frozen pilot files changed during scoring.")

    source_files = [
        ROOT / "greenledger/benchmark/paddleocr_vl_adapter.py",
        ROOT / "greenledger/benchmark/candidate_interface.py",
        ROOT / "greenledger/benchmark/contract.py",
        ROOT / "greenledger/benchmark/evaluator.py",
        ROOT / "scripts/evaluate_paddleocr_vl_contract.py",
        ROOT / "scripts/evaluate_current_pipeline_contract.py",
        ROOT / "data/benchmark/contracts/GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1.json",
    ]
    weight_manifest = _cache_weight_manifest()
    output = {
        "benchmark_id": "greenledger_unseen_structure_pilot_120_paddleocr_vl_16_contract_v1_2026-11-17",
        "status": "COMPLETED" if not wrapped.failures else "COMPLETED_WITH_DOCUMENT_FAILURES",
        "evaluation_only": True,
        "not_training_or_tuning_data": True,
        "candidate": {
            "name": f"PaddleOCR-VL 1.6 full document parsing pipeline ({ENGINE} engine) + fixed evidence mapper",
            "engine": ENGINE,
            "model_identifier": MODEL_ID,
            "pipeline_model_name": PIPELINE_MODEL_NAME,
            "pipeline_version": "v1.6",
            "license": "Apache-2.0 per official Hugging Face model card",
            "weights_downloaded": bool(weight_manifest) and not cache_existed_before,
            "cache_existed_before_inference": cache_existed_before,
            "weight_files_present_at_inference_start": cache_existed_before,
            "model_weights": weight_manifest,
            "model_weight_bytes": sum(item["bytes"] for item in weight_manifest),
        },
        "candidate_only_protocol": {
            "allowed_inputs": ["opaque candidate_id", "document bytes", "MIME type"],
            "forbidden_inputs": ["annotations", "domain labels", "expected fields/status/results", "manifest ground truth", "original filenames or folder paths"],
            "generic_temporary_filename": "candidate-input.<original MIME extension>",
            "candidate_predictions_generated_before_annotation_deserialization": True,
            "annotations_deserialized_after_all_120_predictions": annotations_deserialized,
            "domain_treatment": "Candidate-predicted from PaddleOCR-VL parsed document text only.",
        },
        "smoke_test": {
            "selected_count": len(smoke_batch),
            "pass": smoke_passed,
            "selection_basis": "MIME type, PDF page count/text-layer presence, then opaque candidate ID order only; no annotation or domain labels.",
            "results": smoke_outcomes,
        },
        "dataset": {
            "dataset_id": marker["dataset_id"],
            "documents": marker["counts"]["documents"],
            "freeze_marker_sha256": freeze_sha,
            "manifest_sha256": marker["manifest_sha256"],
            "annotations_sha256": marker["annotations_sha256"],
            "old_quarantined_test_split_accessed": False,
        },
        "runtime": {
            "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "python": sys.version,
            "platform": platform.platform(),
            "package_versions": _package_versions(),
            "hardware": _hardware_snapshot(),
            "device": "CPU",
            "engine": ENGINE,
            "model_load_seconds_including_initial_download": model_load_seconds,
            "candidate_generation_seconds": candidate_generation_seconds,
            "mean_latency_seconds_per_document": statistics.mean(latencies) if latencies else None,
            "median_latency_seconds_per_document": statistics.median(latencies) if latencies else None,
            "per_document_latency_seconds": {
                candidate_to_document_id[candidate_id]: wrapped.latencies.get(candidate_id)
                for candidate_id in prediction_input_order
            },
            "resource_measurements": resource,
        },
        "preprocessing": {
            "pdf": "Original PDF bytes written unchanged to a temporary generic filename; PaddleOCR-VL processed pages individually in order.",
            "images": "Original PNG/JPEG bytes written unchanged to a temporary generic filename.",
            "document_orientation_and_unwarping": "Disabled per official pipeline defaults; no manual crop/deskew or annotation-derived region used.",
            "page_restructuring": "Not applied; page boundaries and result page indexes preserved.",
        },
        "adapter_notes": {
            "extraction_mapping": "PaddleOCR-VL's page layout blocks are interpreted by a fixed benchmark-only evidence mapper. It emits only candidate evidence and readiness; no factor, Scope, accounting boundary, or emissions.",
            "confidence": "Not calibrated; layout detector scores are not treated as field confidence.",
            "coordinates": "Model block_bbox xyxy coordinates normalized by the result's page width and height; null if the model provided no valid box.",
            "unit_handling": "Recognized unit spellings are standardized symbolically; quantities are not converted between physical units.",
            "ocr_cer_wer": "Unavailable: the frozen pilot does not provide full-page OCR transcription ground truth. Field evidence-anchor text is scored separately by the common evaluator.",
        },
        "source_code_sha256": _files_hash(source_files),
        "prediction_sha256": prediction_digest,
        "prediction_schema_version": "1.0",
        "evaluator": {
            "module": "greenledger.benchmark.evaluator.evaluate_predictions",
            "version": "contract-v1.0-existing-evaluator",
            "semantics_changed": False,
        },
        "failures": [
            {**failure, "document_id": candidate_to_document_id.get(failure["candidate_id"])}
            for failure in wrapped.failures
        ],
        "predictions": mapped,
        "parsed_pages_by_document": {
            candidate_to_document_id[candidate_id]: wrapped.pages.get(candidate_id, [])
            for candidate_id in prediction_input_order
        },
        "evaluation": evaluation,
        "comparison_artifacts": {
            "current_pipeline": str(CURRENT_BASELINE.relative_to(ROOT)).replace("\\", "/") if "current_pipeline" in current_and_a else None,
            "candidate_a": str(CANDIDATE_A.relative_to(ROOT)).replace("\\", "/") if "candidate_a" in current_and_a else None,
        },
        "freeze_integrity": {
            "all_covered_files_verified_before_and_after": True,
            "FROZEN_json_unchanged": True,
            "manifest_unchanged": True,
            "annotations_unchanged": True,
            "documents_unchanged": True,
            "pilot_modified": False,
            "old_quarantined_test_split_accessed": False,
        },
    }
    _write_result(output_path, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--max-documents", type=int, default=None, help="Smoke-only mode. Partial runs are not scored and do not load annotations.")
    args = parser.parse_args()
    result = run(args.output, max_documents=args.max_documents)
    print("Status:", result.get("status"))
    print("Candidate predictions:", result.get("candidate_predictions_generated", len(result.get("predictions", []))))
    if result.get("evaluation"):
        print("Extraction:", result["evaluation"]["metrics"]["carbon_critical_extraction"]["aggregate"])
    print("Output:", args.output)


if __name__ == "__main__":
    main()
