"""Evaluate the pinned Florence-2 OCR task on GreenLedger synthetic documents."""

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".venv-field-eval" / "hf_home"))

from greenledger.ocr_eval import load_ocr_records, summarize_rows, text_error_counts


MODEL_ID = "microsoft/Florence-2-base-ft"
MODEL_REVISION = "f6c1a25888ffc1d945ee8a1a77ac833c7303d46e"
MODEL_WEIGHT_SHA256 = "58757d657ff44051314c8030b68e04cb1bb618ca9a4885418f111f6fb708185a"
TASK_PROMPT = "<OCR>"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_model():
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoProcessor

    torch.set_num_threads(4)
    model_path = Path(snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        ignore_patterns=["pytorch_model.bin"],
    ))
    weight_path = model_path / "model.safetensors"
    actual_hash = _sha256(weight_path)
    if actual_hash != MODEL_WEIGHT_SHA256:
        raise RuntimeError("Pinned Florence-2 weight checksum does not match the reviewed model file.")
    processor = AutoProcessor.from_pretrained(str(model_path), trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.float32,
        local_files_only=True,
    ).to("cpu")
    model.eval()
    files = (
        "model.safetensors", "configuration_florence2.py", "modeling_florence2.py",
        "processing_florence2.py", "config.json", "preprocessor_config.json",
    )
    file_hashes = {name: _sha256(model_path / name) for name in files if (model_path / name).is_file()}
    return model, processor, torch, file_hashes


def _transcribe(model, processor, torch, image_path):
    from PIL import Image

    with Image.open(image_path) as source:
        image = source.convert("RGB")
    width, height = image.size
    batch = processor(text=TASK_PROMPT, images=image, return_tensors="pt")
    with torch.inference_mode():
        generated = model.generate(
            input_ids=batch["input_ids"],
            pixel_values=batch["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
            do_sample=False,
        )
    decoded = processor.batch_decode(generated, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(decoded, task=TASK_PROMPT, image_size=(width, height))
    if isinstance(parsed, dict):
        value = parsed.get(TASK_PROMPT, "")
    else:
        value = parsed
    return str(value or "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--limit", type=int, help="Optional smoke limit; limited runs are not benchmark results.")
    parser.add_argument("--store-predictions", action="store_true", help="Store raw synthetic OCR transcripts for separate field evaluation.")
    parser.add_argument("--output", type=Path, help="Write JSON report here; defaults to stdout.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")

    records = load_ocr_records(args.split, verify_hashes=True)
    if args.limit is not None:
        records = records[:args.limit]
    initialization_started = time.perf_counter()
    model, processor, torch, file_hashes = _load_model()
    initialization_seconds = time.perf_counter() - initialization_started
    predictions, rows, latencies, errors = [], [], [], []
    for index, record in enumerate(records, 1):
        started = time.perf_counter()
        try:
            transcript = _transcribe(model, processor, torch, record["image_path"])
            error = None
        except Exception as failure:
            transcript = ""
            error = type(failure).__name__
            errors.append({"document_id": record["document_id"], "error": error})
        latency = time.perf_counter() - started
        latencies.append(latency)
        rows.append(text_error_counts(record["reference"], transcript))
        if args.store_predictions:
            predictions.append({
                "document_id": record["document_id"],
                "transcription": transcript,
                "source_sha256": _sha256(record["image_path"]),
                "inference_error": error,
            })
        print("Florence OCR progress: {}/{}".format(index, len(records)), file=sys.stderr, flush=True)

    complete = args.limit is None and len(records) > 0
    report = {
        "status": "MEASURED" if complete else "SMOKE_TEST_ONLY",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "dataset_id": "greenledger_synthetic_v0_1_1_partial",
            "synthetic_only": True,
            "split": args.split,
            "records_selected": len(records),
            "records_with_ocr_truth": len(records),
            "smoke_test_subset": not complete,
            "co2e_results_measured": False,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "visible_gpu": torch.cuda.is_available(),
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "device": "CPU",
        },
        "metric_definitions": {
            "normalization": "Unicode NFKC, casefold, collapse whitespace; punctuation is retained.",
            "cer": "Pooled character-level Levenshtein edits divided by normalized reference characters.",
            "wer": "Pooled word-level Levenshtein edits divided by normalized reference words.",
            "exact_match_rate": "Fraction of documents whose normalized OCR transcription exactly matches normalized reference.",
            "bootstrap_95_ci": "Percentile interval from 1000 deterministic document-level bootstrap resamples; descriptive for this synthetic split.",
            "latency": "Per-document OCR inference time; excludes one-time model initialization.",
        },
        "limitations": [
            "Florence-2 is a pretrained general-purpose vision model run with its documented OCR task prompt; no GreenLedger fine-tuning was performed.",
            "Synthetic OCR results do not estimate performance on real SME documents.",
            "This report measures OCR transcription only, not field extraction or accounting correctness.",
            "The candidate is CPU-only on this host; peak memory is not measured.",
        ],
        "engine_availability": {
            "florence2": {"available": True, "model": MODEL_ID, "revision": MODEL_REVISION, "sha256": file_hashes.get("model.safetensors")},
        },
        "engine_results": [{
            "engine": {"name": "Florence-2 OCR", "model": MODEL_ID, "revision": MODEL_REVISION},
            "engine_configuration": {
                "task_prompt": TASK_PROMPT,
                "preprocessing": "official Florence-2 processor; no additional preprocessing",
                "device": "CPU",
                "torch_threads": 4,
                "torch_dtype": "float32",
                "generation": {"num_beams": 3, "max_new_tokens": 1024, "do_sample": False},
                "model_file_sha256": file_hashes,
            },
            "startup_seconds": initialization_seconds,
            "wall_seconds": sum(latencies),
            "latency_seconds": {
                "mean": statistics.mean(latencies) if latencies else None,
                "p50": statistics.median(latencies) if latencies else None,
                "p95": sorted(latencies)[max(0, int(0.95 * len(latencies) + 0.999999) - 1)] if latencies else None,
            },
            "metrics": summarize_rows(rows, include_confidence_intervals=True),
            "errors": errors,
            **({"predictions": predictions} if args.store_predictions else {}),
        }],
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print("Wrote Florence OCR evaluation to {}".format(args.output))
        print("status={} split={} documents={} errors={}".format(report["status"], args.split, len(records), len(errors)))
    else:
        print(rendered)


if __name__ == "__main__":
    main()
