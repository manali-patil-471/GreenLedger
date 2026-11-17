"""Generate ten Qwen3-VL smoke predictions without scoring or loading labels.

The manifest is used only by this outer runner to choose a diverse smoke set
and to build an external ID map. Each adapter call receives only an opaque
candidate ID, the bytes, and MIME type. This script never opens annotations.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_PILOT = ROOT / "data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15"
DEFAULT_OUTPUT = ROOT / "data/benchmark/evaluations/qwen3vl_smoke_10_predictions_v1.json"
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
EXPECTED_MODEL_NAME = "Qwen3VL-4B-Instruct-Q4_K_M.gguf"
EXPECTED_MODEL_SHA256 = "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a"
EXPECTED_MMPROJ_NAME = "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"
EXPECTED_MMPROJ_SHA256 = "30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d"


def _row_covers(row: dict[str, Any], target: tuple[str, str]) -> bool:
    kind, expected = target
    if kind == "domain":
        return str(row.get("domain", "")).casefold() == expected
    if kind == "evidence_state":
        return str(row.get("evidence_state", "")).casefold() == expected
    suffix = Path(str(row.get("file", ""))).suffix.casefold()
    if kind == "multipage_pdf":
        return suffix == ".pdf" and int(row.get("page_count") or 0) > 1
    if kind == "image":
        return suffix in IMAGE_TYPES
    return False


def select_smoke_rows(rows: list[dict[str, Any]], *, count: int = 10) -> list[dict[str, Any]]:
    """Select a deterministic ten-row set with coverage targets from metadata.

    The selected row metadata remains outside candidate inference. The old
    quarantined test split is not referenced by this module.
    """
    if count != 10:
        raise ValueError("This controlled smoke runner is fixed at exactly 10 documents.")
    ordered = sorted(
        (row for row in rows if isinstance(row, dict) and isinstance(row.get("file"), str)),
        key=lambda row: str(row.get("document_id", "")),
    )
    targets = [
        *(("domain", domain) for domain in ("electricity", "diesel", "lpg", "materials", "freight")),
        *(("evidence_state", state) for state in ("ready", "incomplete", "ambiguous")),
        ("multipage_pdf", "true"),
        ("image", "true"),
    ]
    selected: list[dict[str, Any]] = []
    for target in targets:
        if any(_row_covers(row, target) for row in selected):
            continue
        candidate = next((row for row in ordered if row not in selected and _row_covers(row, target)), None)
        if candidate is None:
            raise ValueError(f"Frozen pilot manifest does not contain a document for smoke target {target!r}.")
        selected.append(candidate)
    for row in ordered:
        if row not in selected:
            selected.append(row)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError(f"Expected 10 smoke documents, found only {len(selected)} eligible manifest rows.")
    return selected


def build_smoke_inputs(pilot_dir: Path, *, count: int = 10):
    """Read selected document bytes and return candidate inputs plus an external map."""
    from greenledger.benchmark.candidate_interface import CandidateDocumentInput

    manifest_path = pilot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("documents")
    if not isinstance(rows, list):
        raise ValueError("Frozen pilot manifest has no document list.")
    selected = select_smoke_rows(rows, count=count)
    inputs = []
    mapping: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        relative = Path(row["file"])
        source = (pilot_dir / relative).resolve()
        if not source.is_relative_to(pilot_dir.resolve()):
            raise ValueError("Manifest document path escapes the frozen pilot directory.")
        media_type = (
            "application/pdf" if source.suffix.casefold() == ".pdf"
            else IMAGE_TYPES.get(source.suffix.casefold())
        )
        if media_type is None:
            raise ValueError(f"Unsupported frozen-pilot document type: {source.suffix}")
        candidate_id = f"qwen-smoke-{index:04d}"
        inputs.append(CandidateDocumentInput(candidate_id, source.read_bytes(), media_type))
        # This is external selection metadata. No part of this row is passed to
        # the candidate adapter; the candidate only receives the three fields
        # in CandidateDocumentInput.
        mapping.append({
            "candidate_id": candidate_id,
            "document_id": row.get("document_id"),
            "domain": row.get("domain"),
            "evidence_state": row.get("evidence_state"),
            "format": row.get("format"),
            "page_count": row.get("page_count"),
        })
    return inputs, mapping


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_smoke(
    *,
    pilot_dir: Path,
    llama_binary: str,
    model_path: Path,
    mmproj_path: Path,
    output_path: Path,
    gpu_layers: int = 99,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    from greenledger.benchmark.candidate_interface import generate_candidate_predictions
    from greenledger.benchmark.qwen3vl_candidate_adapter import (
        ADAPTER_VERSION,
        MODEL_ID,
        Qwen3VLCandidateAdapter,
    )

    if not model_path.is_file() or not mmproj_path.is_file():
        raise FileNotFoundError("Provide existing local GGUF and mmproj files; this runner never downloads weights.")
    if model_path.name != EXPECTED_MODEL_NAME or mmproj_path.name != EXPECTED_MMPROJ_NAME:
        raise ValueError("Only the official Qwen3-VL Q4_K_M model and Q8_0 mmproj filenames are allowed.")
    model_sha256 = _sha256_file(model_path)
    mmproj_sha256 = _sha256_file(mmproj_path)
    if model_sha256 != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Official Q4_K_M model SHA256 mismatch: {model_sha256}")
    if mmproj_sha256 != EXPECTED_MMPROJ_SHA256:
        raise ValueError(f"Official mmproj SHA256 mismatch: {mmproj_sha256}")
    cli_probe = subprocess.run([llama_binary, "--version"], capture_output=True, text=True, check=False)
    if cli_probe.returncode != 0:
        detail = (cli_probe.stderr or cli_probe.stdout or "no output").strip()
        raise RuntimeError(f"llama.cpp unified CLI preflight failed ({cli_probe.returncode}): {detail[-2000:]}")
    cli_version = (cli_probe.stdout or cli_probe.stderr).strip()
    inputs, selection_map = build_smoke_inputs(pilot_dir, count=10)
    adapter = Qwen3VLCandidateAdapter(
        llama_binary=llama_binary,
        model_path=model_path,
        mmproj_path=mmproj_path,
        gpu_layers=gpu_layers,
        timeout_seconds=timeout_seconds,
    )
    started = time.perf_counter()
    predictions = generate_candidate_predictions(adapter, inputs)
    elapsed = time.perf_counter() - started
    prediction_payloads = [prediction.to_dict() for prediction in predictions]
    result = {
        "benchmark_id": "greenledger_unseen_structure_pilot_qwen3vl_smoke_10_v1",
        "status": "PREDICTIONS_GENERATED_NOT_SCORED",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "candidate_name": "Qwen3-VL-4B-Instruct-GGUF Q4_K_M via llama.cpp",
            "model_identifier": MODEL_ID,
            "adapter_version": ADAPTER_VERSION,
            "llama_binary": llama_binary,
            "llama_version": cli_version,
            "gpu_layers": gpu_layers,
            "model_sha256": model_sha256,
            "mmproj_sha256": mmproj_sha256,
        },
        "candidate_input_count": len(inputs),
        "candidate_generation_seconds": elapsed,
        "annotation_file_opened": False,
        "scoring_performed": False,
        "prediction_sha256": _sha256_json(prediction_payloads),
        "predictions": prediction_payloads,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selection_path = output_path.with_suffix(output_path.suffix + ".selection.json")
    selection_path.write_text(json.dumps({
        "note": "External smoke-set selection mapping. This metadata was not passed to Qwen.",
        "selected": selection_map,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["selection_map_path"] = str(selection_path)
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-dir", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--llama-binary", required=True, help="Existing local llama.cpp unified CLI binary")
    parser.add_argument("--model", required=True, type=Path, help="Existing official Q4_K_M GGUF file; no downloads")
    parser.add_argument("--mmproj", required=True, type=Path, help="Existing compatible official mmproj GGUF file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()

    if args.output.resolve().is_relative_to(args.pilot_dir.resolve()):
        parser.error("Output must be outside the frozen pilot directory.")
    try:
        result = run_smoke(
            pilot_dir=args.pilot_dir,
            llama_binary=args.llama_binary,
            model_path=args.model,
            mmproj_path=args.mmproj,
            output_path=args.output,
            gpu_layers=args.gpu_layers,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as error:
        print(f"Smoke run failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Generated {result['candidate_input_count']} schema-valid predictions; no annotations loaded or scoring performed.")
    print(f"Predictions: {args.output.resolve()}")
    print(f"External selection map: {result['selection_map_path']}")
    print(f"Prediction SHA256: {result['prediction_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
