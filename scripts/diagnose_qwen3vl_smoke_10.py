"""Diagnostic runner: test all 10 smoke documents one-by-one with detailed logging.

This script executes the exact same 10 candidate inputs as run_qwen3vl_smoke_10.py,
but processes them individually with try/except so that a failure on any one
document does not abort the run. It records and prints the complete diagnostic table
specified in the GreenLedger debugging protocol.
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

from greenledger.benchmark.qwen3vl_candidate_adapter import (
    ADAPTER_VERSION,
    MODEL_ID,
    Qwen3VLCandidateAdapter,
    _parse_json_object,
)
from greenledger.benchmark.contract import validate_prediction
from scripts.run_qwen3vl_smoke_10 import (
    DEFAULT_PILOT,
    EXPECTED_MMPROJ_NAME,
    EXPECTED_MMPROJ_SHA256,
    EXPECTED_MODEL_NAME,
    EXPECTED_MODEL_SHA256,
    _sha256_file,
    build_smoke_inputs,
)


def run_diagnostics(
    *,
    pilot_dir: Path,
    llama_binary: str,
    model_path: Path,
    mmproj_path: Path,
    output_path: Path | None = None,
    gpu_layers: int = 99,
    timeout_seconds: int = 300,
) -> list[dict[str, Any]]:
    """Run all 10 smoke documents one at a time and capture per-document telemetry."""
    if not model_path.is_file() or not mmproj_path.is_file():
        raise FileNotFoundError("Model or mmproj file not found.")

    model_sha = _sha256_file(model_path)
    mmproj_sha = _sha256_file(mmproj_path)
    if model_sha != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Model SHA256 mismatch: {model_sha}")
    if mmproj_sha != EXPECTED_MMPROJ_SHA256:
        raise ValueError(f"MMPROJ SHA256 mismatch: {mmproj_sha}")

    cli_probe = subprocess.run([llama_binary, "--version"], capture_output=True, text=True, check=False)
    if cli_probe.returncode != 0:
        detail = (cli_probe.stderr or cli_probe.stdout or "no output").strip()
        raise RuntimeError(f"llama CLI preflight failed ({cli_probe.returncode}): {detail[-1000:]}")
    cli_version = (cli_probe.stdout or cli_probe.stderr).strip()
    print(f"llama.cpp runtime: {cli_version}")

    inputs, selection_map = build_smoke_inputs(pilot_dir, count=10)
    print(f"Loaded {len(inputs)} smoke inputs from manifest.")

    adapter = Qwen3VLCandidateAdapter(
        llama_binary=llama_binary,
        model_path=model_path,
        mmproj_path=mmproj_path,
        gpu_layers=gpu_layers,
        timeout_seconds=timeout_seconds,
    )

    records: list[dict[str, Any]] = []

    for index, (candidate_doc, meta) in enumerate(zip(inputs, selection_map), start=1):
        cid = candidate_doc.candidate_id
        doc_id = meta.get("document_id", "UNKNOWN")
        domain = meta.get("domain", "UNKNOWN")
        evidence_state = meta.get("evidence_state", "UNKNOWN")
        fmt = meta.get("format", "UNKNOWN")
        pages = meta.get("page_count", 1)

        print(f"\n" + "=" * 70)
        print(f"[{index}/10] Testing {cid} | doc_id={doc_id} | domain={domain} | state={evidence_state} | format={fmt} | pages={pages}")
        print("=" * 70)

        started = time.perf_counter()
        record: dict[str, Any] = {
            "index": index,
            "candidate_id": cid,
            "document_id": doc_id,
            "domain": domain,
            "evidence_state": evidence_state,
            "format": fmt,
            "media_type": candidate_doc.media_type,
            "page_count": pages,
            "status": "UNKNOWN",
            "returncode": None,
            "stdout_length": 0,
            "stderr_length": 0,
            "json_parsed": False,
            "contract_validated": False,
            "elapsed_seconds": 0.0,
            "error_type": None,
            "error_message": None,
            "stdout_tail": "",
            "stderr_tail": "",
        }

        try:
            prediction = adapter.predict(candidate_doc)
            elapsed = time.perf_counter() - started
            record["status"] = "SUCCESS"
            record["returncode"] = adapter.last_process_returncode
            record["stdout_length"] = len(adapter.last_stdout)
            record["stderr_length"] = len(adapter.last_stderr)
            record["json_parsed"] = True
            record["contract_validated"] = True
            record["elapsed_seconds"] = round(elapsed, 2)
            record["readiness"] = prediction.accounting_readiness
            record["extracted_fields_count"] = len(prediction.extracted_fields)

            print(f"  -> RESULT: SUCCESS in {record['elapsed_seconds']}s")
            print(f"  -> Returncode: {record['returncode']}, Stdout: {record['stdout_length']} chars, Stderr: {record['stderr_length']} chars")
            print(f"  -> Readiness: {prediction.accounting_readiness}, Fields: {len(prediction.extracted_fields)}")

        except Exception as error:
            elapsed = time.perf_counter() - started
            record["status"] = "FAILED"
            record["returncode"] = adapter.last_process_returncode
            record["stdout_length"] = len(adapter.last_stdout) if adapter.last_stdout else 0
            record["stderr_length"] = len(adapter.last_stderr) if adapter.last_stderr else 0
            record["elapsed_seconds"] = round(elapsed, 2)
            record["error_type"] = type(error).__name__
            record["error_message"] = str(error)
            record["stdout_tail"] = (adapter.last_stdout or "")[-1500:]
            record["stderr_tail"] = (adapter.last_stderr or "")[-1500:]

            # Check if raw JSON parsing could find anything
            try:
                raw_json = _parse_json_object(adapter.last_stdout or "")
                record["json_parsed"] = bool(raw_json)
            except Exception:
                record["json_parsed"] = False

            print(f"  -> RESULT: FAILED ({type(error).__name__}) after {record['elapsed_seconds']}s")
            print(f"  -> Error: {error}")
            print(f"  -> Returncode: {record['returncode']}")
            print(f"  -> Stdout length: {record['stdout_length']}, Stderr length: {record['stderr_length']}")
            if record["stdout_tail"]:
                print(f"  -> STDOUT TAIL:\n{record['stdout_tail'][-500:]}")
            if record["stderr_tail"]:
                print(f"  -> STDERR TAIL:\n{record['stderr_tail'][-500:]}")

        records.append(record)

    # Print summary markdown table
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY TABLE (ALL 10 SMOKE DOCUMENTS)")
    print("=" * 80)
    header = f"| # | Candidate ID | Doc ID | Domain | Format | Pages | Status | RC | Stdout | Stderr | Elapsed |"
    sep = f"|---|---|---|---|---|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for r in records:
        print(f"| {r['index']} | {r['candidate_id']} | {r['document_id']} | {r['domain']} | {r['format']} | {r['page_count']} | **{r['status']}** | {r['returncode']} | {r['stdout_length']} | {r['stderr_length']} | {r['elapsed_seconds']}s |")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nFull diagnostic records saved to: {output_path.resolve()}")

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-dir", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--llama-binary", required=True, help="Existing local llama.cpp unified CLI binary")
    parser.add_argument("--model", required=True, type=Path, help="Existing official Q4_K_M GGUF file")
    parser.add_argument("--mmproj", required=True, type=Path, help="Existing compatible official mmproj GGUF file")
    parser.add_argument("--output", type=Path, default=Path("qwen3vl_smoke_10_diagnostic_report.json"))
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    try:
        records = run_diagnostics(
            pilot_dir=args.pilot_dir,
            llama_binary=args.llama_binary,
            model_path=args.model,
            mmproj_path=args.mmproj,
            output_path=args.output,
            gpu_layers=args.gpu_layers,
            timeout_seconds=args.timeout_seconds,
        )
        failures = sum(1 for r in records if r["status"] != "SUCCESS")
        return 1 if failures > 0 else 0
    except Exception as exc:
        print(f"Diagnostic execution aborted: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
