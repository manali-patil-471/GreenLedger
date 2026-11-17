"""Reproducible OCR evaluation helpers for the synthetic GreenLedger split."""

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "synthetic" / "greenledger_v0_1_1_partial"


def _record_split_from_jsonl_line(line):
    """Read only the top-level split value without deserializing the remaining record."""
    decoder = json.JSONDecoder()
    index = len(line) - len(line.lstrip())
    if index >= len(line) or line[index] != "{":
        return None
    index += 1
    while index < len(line):
        while index < len(line) and (line[index].isspace() or line[index] == ","):
            index += 1
        if index >= len(line) or line[index] == "}":
            return None
        try:
            key, key_end = decoder.raw_decode(line, index)
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(key, str):
            return None
        index = key_end
        while index < len(line) and line[index].isspace():
            index += 1
        if index >= len(line) or line[index] != ":":
            return None
        index += 1
        while index < len(line) and line[index].isspace():
            index += 1
        if key == "split":
            try:
                value, _end = decoder.raw_decode(line, index)
            except (ValueError, json.JSONDecodeError):
                return None
            return value if value in {"train", "validation", "test"} else None

        # Skip the value lexically. In particular, do not deserialize nested annotations.
        if index >= len(line):
            return None
        if line[index] == '"':
            escaped = False
            index += 1
            while index < len(line):
                char = line[index]
                index += 1
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    break
        else:
            depth = 0
            in_string = False
            escaped = False
            while index < len(line):
                char = line[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                elif char == '"':
                    in_string = True
                elif char in "[{":
                    depth += 1
                elif char in "]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif char == "," and depth == 0:
                    break
                index += 1
        while index < len(line) and line[index].isspace():
            index += 1
        if index < len(line) and line[index] == ",":
            index += 1
    return None


def iter_jsonl_split_records(source, split):
    """Deserialize only JSONL records whose split marker matches the requested partition."""
    if split == "test":
        raise ValueError("The v0.1.1 test split is quarantined after annotation exposure and cannot be loaded.")
    if split not in {"train", "validation"}:
        raise ValueError("Only the training and validation splits may be loaded for current development.")
    for line_number, line in enumerate(source, 1):
        if not line.strip() or _record_split_from_jsonl_line(line) != split:
            continue
        yield line_number, json.loads(line)


def normalize_ocr_text(text):
    """Apply formatting-insensitive comparison: NFKC, casefold, collapsed whitespace."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return " ".join(text.split())


def edit_distance(reference, hypothesis):
    """Levenshtein distance using O(min(n,m)) memory."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for row_index, left in enumerate(reference, 1):
        current = [row_index]
        for column_index, right in enumerate(hypothesis, 1):
            current.append(min(
                current[-1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (left != right),
            ))
        previous = current
    return previous[-1]


def text_error_counts(reference, hypothesis):
    ref_text = normalize_ocr_text(reference)
    hyp_text = normalize_ocr_text(hypothesis)
    ref_words = ref_text.split()
    hyp_words = hyp_text.split()
    return {
        "char_edits": edit_distance(ref_text, hyp_text),
        "reference_characters": len(ref_text),
        "word_edits": edit_distance(ref_words, hyp_words),
        "reference_words": len(ref_words),
        "exact_match": ref_text == hyp_text,
    }


def _bootstrap_ratio_interval(rows, numerator_key, denominator_key, repetitions=1000, seed=20260924):
    if len(rows) < 2:
        return None
    randomizer = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        sample = [rows[randomizer.randrange(len(rows))] for _ in rows]
        numerator = sum(item[numerator_key] for item in sample)
        denominator = sum(item[denominator_key] for item in sample)
        if denominator:
            estimates.append(numerator / denominator)
    if not estimates:
        return None
    estimates.sort()
    low_index = max(0, int(math.ceil(0.025 * len(estimates))) - 1)
    high_index = max(0, int(math.ceil(0.975 * len(estimates))) - 1)
    return [estimates[low_index], estimates[high_index]]


def summarize_rows(rows, include_confidence_intervals=False):
    """Return micro CER/WER plus document-level exact and macro error rates."""
    if not rows:
        return {"documents": 0, "cer": None, "wer": None, "exact_match_rate": None, "macro_cer": None, "macro_wer": None}
    char_edits = sum(row["char_edits"] for row in rows)
    ref_chars = sum(row["reference_characters"] for row in rows)
    word_edits = sum(row["word_edits"] for row in rows)
    ref_words = sum(row["reference_words"] for row in rows)
    per_doc_cer = [row["char_edits"] / row["reference_characters"] for row in rows if row["reference_characters"]]
    per_doc_wer = [row["word_edits"] / row["reference_words"] for row in rows if row["reference_words"]]
    summary = {
        "documents": len(rows),
        "cer": char_edits / ref_chars if ref_chars else None,
        "wer": word_edits / ref_words if ref_words else None,
        "exact_match_rate": sum(bool(row["exact_match"]) for row in rows) / len(rows),
        "macro_cer": sum(per_doc_cer) / len(per_doc_cer) if per_doc_cer else None,
        "macro_wer": sum(per_doc_wer) / len(per_doc_wer) if per_doc_wer else None,
    }
    if include_confidence_intervals:
        summary["bootstrap_95_ci"] = {
            "cer": _bootstrap_ratio_interval(rows, "char_edits", "reference_characters"),
            "wer": _bootstrap_ratio_interval(rows, "word_edits", "reference_words"),
            "replicates": 1000,
            "seed": 20260924,
            "unit": "document, sampled with replacement",
        }
    return summary


def _within_root(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def load_ocr_records(split="validation", root=ROOT, verify_hashes=True):
    """Load only GreenLedger synthetic records with OCR ground truth for one split."""
    if split == "test":
        raise ValueError("The v0.1.1 test split is quarantined after annotation exposure and cannot be evaluated.")
    if split not in {"train", "validation"}:
        raise ValueError("Only the training and validation splits may be loaded for current development.")
    root = Path(root).resolve()
    annotation_path = root / "data" / "synthetic" / "greenledger_v0_1_1_partial" / "annotations.jsonl"
    records = []
    with annotation_path.open("r", encoding="utf-8") as source:
        # Route by split before deserializing. This avoids loading labels from excluded partitions.
        for line_number, item in iter_jsonl_split_records(source, split):
            if item.get("source_type") != "synthetic":
                continue
            coverage = item.get("task_coverage", [])
            transcription = item.get("ground_truth", {}).get("ocr", {}).get("transcription")
            if "ocr_text_extraction" not in coverage or not isinstance(transcription, str):
                continue
            relative_path = Path(item["source_document"]["path_or_id"])
            image_path = (root / "data" / "synthetic" / "greenledger_v0_1_1_partial" / relative_path).resolve()
            dataset_root = (root / "data" / "synthetic" / "greenledger_v0_1_1_partial").resolve()
            if not _within_root(image_path, dataset_root):
                raise ValueError("Annotation line {} contains a path outside the synthetic release.".format(line_number))
            if not image_path.is_file():
                raise ValueError("Missing benchmark image for {}: {}".format(item.get("document_id"), image_path))
            expected_hash = item.get("source_document", {}).get("sha256")
            if verify_hashes and expected_hash:
                digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
                if digest.casefold() != expected_hash.casefold():
                    raise ValueError("Image checksum mismatch for {}.".format(item.get("document_id")))
            records.append({
                "document_id": item["document_id"],
                "document_type": item.get("document_type"),
                "layout_family": item.get("layout_family", "unknown"),
                "quality_tags": item.get("quality_tags", []),
                "image_path": image_path,
                "reference": transcription,
            })
    return records


def _package_version(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def discover_engines(tesseract_cmd=None, tessdata_dir=None):
    tesseract_cmd = tesseract_cmd or shutil.which("tesseract")
    tessdata_dir = Path(tessdata_dir or os.environ.get(
        "GREENLEDGER_TESSDATA_DIR", ROOT / ".venv-ocr-eval" / "tessdata"
    )).resolve()
    found = []
    availability = {
        "tesseract": {"available": bool(tesseract_cmd), "executable": tesseract_cmd},
        "tesserocr": {"available": False, "package": None, "tessdata_dir": str(tessdata_dir)},
        "rapidocr": {"available": False, "package": None},
    }
    if tesseract_cmd:
        try:
            version_run = subprocess.run([tesseract_cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15)
            version_output = (version_run.stdout or version_run.stderr).decode("utf-8", errors="replace").splitlines()
            if version_run.returncode == 0 and version_output:
                version = version_output[0].strip()
                availability["tesseract"]["version"] = version
                found.append({"name": "tesseract", "executable": tesseract_cmd, "version": version})
            else:
                availability["tesseract"]["available"] = False
                availability["tesseract"]["probe_error"] = "Tesseract --version failed."
        except Exception as error:
            availability["tesseract"]["available"] = False
            availability["tesseract"]["probe_error"] = "{}: {}".format(type(error).__name__, str(error)[:200])
    try:
        import tesserocr
        tesserocr_version = str(tesserocr.tesseract_version()).strip()
        availability["tesserocr"].update({
            "available": (tessdata_dir / "eng.traineddata").is_file(),
            "package": "tesserocr",
            "version": _package_version("tesserocr"),
            "tesseract_version": tesserocr_version,
            "english_model_available": (tessdata_dir / "eng.traineddata").is_file(),
        })
        if availability["tesserocr"]["available"]:
            found.append({
                "name": "tesserocr",
                "package": "tesserocr",
                "version": _package_version("tesserocr"),
                "tesseract_version": tesserocr_version,
                "tessdata_dir": str(tessdata_dir),
            })
    except Exception as tesserocr_error:
        availability["tesserocr"]["probe_error"] = "{}: {}".format(
            type(tesserocr_error).__name__, str(tesserocr_error)[:200]
        )
    try:
        import rapidocr  # noqa: F401
        version = _package_version("rapidocr")
        availability["rapidocr"] = {"available": True, "package": "rapidocr", "version": version}
        found.append({"name": "rapidocr", "package": "rapidocr", "version": version})
    except Exception as rapidocr_error:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            version = _package_version("rapidocr-onnxruntime")
            availability["rapidocr"] = {"available": True, "package": "rapidocr-onnxruntime", "version": version}
            found.append({"name": "rapidocr", "package": "rapidocr-onnxruntime", "version": version})
        except Exception as legacy_error:
            availability["rapidocr"] = {
                "available": False,
                "package": None,
                "probe_error": "{}: {}; {}: {}".format(
                    type(rapidocr_error).__name__, str(rapidocr_error)[:100],
                    type(legacy_error).__name__, str(legacy_error)[:100],
                ),
            }
    return found, availability


def _run_tesseract(engine, image_path):
    command = [engine["executable"], str(image_path), "stdout", "--psm", "3", "-l", "eng"]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError("Tesseract exited with code {}: {}".format(result.returncode, message[:300]))
    return result.stdout.decode("utf-8", errors="replace")


def _make_tesserocr_engine(engine):
    from tesserocr import OEM, PSM, PyTessBaseAPI
    return PyTessBaseAPI(
        path=engine["tessdata_dir"],
        lang="eng",
        oem=OEM.LSTM_ONLY,
        psm=PSM.AUTO,
    )


def _run_tesserocr(instance, image_path):
    from PIL import Image
    with Image.open(image_path) as image:
        instance.SetImage(image)
        return instance.GetUTF8Text() or ""


def _make_rapidocr_engine(engine):
    if engine.get("package") == "rapidocr":
        from rapidocr import RapidOCR
        model_root = ROOT / ".venv-ocr-eval" / "rapidocr_models"
        model_root.mkdir(parents=True, exist_ok=True)
        # RapidOCR 3.9.2 assigns a pathlib.Path to OmegaConf when its model root
        # is omitted; pass a string to avoid that Windows initialization error.
        # The synthetic release uses English text, so pin recognition to English.
        return RapidOCR(params={
            "Global.model_root_dir": str(model_root),
            "Rec.lang_type": "en",
            "EngineConfig.onnxruntime.intra_op_num_threads": 4,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        })
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _run_rapidocr(instance, image_path):
    result = instance(str(image_path))
    if result is None:
        return ""
    # RapidOCR 3.x returns RapidOCROutput with .txts; the earlier
    # rapidocr_onnxruntime API returns rows shaped like [box, text, score].
    lines = getattr(result, "txts", None)
    if lines is not None:
        return "\n".join(str(line) for line in lines if line is not None)
    if isinstance(result, (list, tuple)):
        return "\n".join(str(row[1]) for row in result if isinstance(row, (list, tuple)) and len(row) > 1)
    return str(result)


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(math.ceil(percentile * len(ordered))) - 1))
    return ordered[index]


def _engine_configuration(engine):
    if engine["name"] == "tesseract":
        return {
            "preprocessing": "none",
            "language": "eng",
            "page_segmentation_mode": 3,
        }
    if engine["name"] == "tesserocr":
        model_path = Path(engine["tessdata_dir"]) / "eng.traineddata"
        return {
            "preprocessing": "none",
            "language": "eng",
            "recognition_engine": "LSTM_ONLY",
            "page_segmentation_mode": "AUTO (3)",
            "english_model": "tessdata_fast eng.traineddata",
            "english_model_source": "https://github.com/tesseract-ocr/tessdata_fast/blob/87416418657359cb625c412a48b6e1d6d41c29bd/eng.traineddata",
            "english_model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "implementation_source": "https://github.com/simonflueckiger/tesserocr-windows_build/releases/tag/tesserocr-v2.10.0-tesseract-5.5.2",
            "wheel_sha256": "e05d41a2b0e6f38f3a5195d05a73674d72152a775d1b8ebe481ca9306f94d27a",
            "tessdata_dir": str(engine["tessdata_dir"]),
        }
    if engine.get("package") == "rapidocr":
        model_root = ROOT / ".venv-ocr-eval" / "rapidocr_models"
        assets = []
        if model_root.is_dir():
            for path in sorted(model_root.glob("*.onnx")):
                assets.append({
                    "file": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
        return {
            "preprocessing": "none",
            "detector": "PP-OCRv6 small",
            "orientation_classifier": "PP-OCRv4 mobile",
            "recognizer": "PP-OCRv6 small",
            "recognition_language": "en",
            "inference_engine": "ONNX Runtime CPU (RapidOCR default config has use_cuda=false)",
            "onnxruntime_threads": {"intra_op": 4, "inter_op": 1},
            "model_assets": assets,
        }
    return {
        "preprocessing": "none",
        "package_configuration": "package defaults; capture package/version above",
    }


def evaluate_engine(engine, records, store_predictions=False):
    startup_started = time.perf_counter()
    try:
        instance = (
            _make_rapidocr_engine(engine) if engine["name"] == "rapidocr"
            else _make_tesserocr_engine(engine) if engine["name"] == "tesserocr"
            else None
        )
    except Exception as error:
        return {
            "engine": engine,
            "initialization_error": "{}: {}".format(type(error).__name__, str(error)[:300]),
            "metrics": summarize_rows([]),
            "failed_documents": [{"document_id": item["document_id"], "error": "Engine initialization failed."} for item in records],
        }
    startup_seconds = time.perf_counter() - startup_started
    scored = []
    latencies = []
    failures = []
    predictions = []
    group_rows = {"document_type": {}, "layout_family": {}, "quality_tag": {}}
    for record_index, record in enumerate(records, 1):
        started = time.perf_counter()
        try:
            if engine["name"] == "tesseract":
                prediction = _run_tesseract(engine, record["image_path"])
            elif engine["name"] == "tesserocr":
                prediction = _run_tesserocr(instance, record["image_path"])
            else:
                prediction = _run_rapidocr(instance, record["image_path"])
            latency = time.perf_counter() - started
            row = text_error_counts(record["reference"], prediction)
            scored.append(row)
            latencies.append(latency)
            if store_predictions:
                predictions.append({"document_id": record["document_id"], "transcription": prediction})
            for dimension, labels in (
                ("document_type", [record["document_type"]]),
                ("layout_family", [record["layout_family"]]),
                ("quality_tag", record["quality_tags"] or ["untagged"]),
            ):
                for label in labels:
                    group_rows[dimension].setdefault(label, []).append(row)
        except Exception as error:
            failures.append({"document_id": record["document_id"], "error": "{}: {}".format(type(error).__name__, str(error)[:300])})
        if record_index % 10 == 0 or record_index == len(records):
            print("{} progress: {}/{} documents".format(engine["name"], record_index, len(records)), file=sys.stderr)
    result = {
        "engine": engine,
        "engine_configuration": _engine_configuration(engine),
        "startup_seconds": startup_seconds,
        "wall_seconds": sum(latencies) + startup_seconds,
        "latency_seconds": {
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "metrics": summarize_rows(scored, include_confidence_intervals=True),
        "group_metrics": {
            dimension: {key: summarize_rows(rows) for key, rows in sorted(groups.items())}
            for dimension, groups in group_rows.items()
        },
        "failed_documents": failures,
    }
    if store_predictions:
        result["predictions"] = predictions
    return result


def build_report(split, records, engine_results, unavailable, smoke_test=False):
    manifest_path = DATASET / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "status": (
            "MEASURED" if any(item.get("metrics", {}).get("documents", 0) for item in engine_results)
            else "BLOCKED_CANDIDATE_FAILED" if engine_results
            else "BLOCKED_NO_ENGINE_AVAILABLE"
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "synthetic_only": manifest["synthetic_only"],
            "split": split,
            "records_selected": len(records),
            "records_with_ocr_truth": len(records),
            "smoke_test_subset": bool(smoke_test),
            "co2e_results_measured": False,
        },
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform(), "visible_gpu": False},
        "metric_definitions": {
            "normalization": "Unicode NFKC, casefold, collapse whitespace; punctuation is retained.",
            "cer": "Pooled character-level Levenshtein edits divided by normalized reference characters.",
            "wer": "Pooled word-level Levenshtein edits divided by normalized reference words.",
            "macro_cer_wer": "Unweighted mean of per-document CER/WER; supplementary to pooled rates.",
            "exact_match_rate": "Fraction of documents whose normalized OCR transcription exactly matches normalized reference.",
            "bootstrap_95_ci": "Percentile interval from 1000 deterministic document-level bootstrap resamples; descriptive for this synthetic split, not a real-SME population interval.",
            "latency": "Per-document OCR call time; excludes one-time engine initialization and includes Tesseract CLI process startup.",
        },
        "limitations": [
            "Synthetic OCR results are controlled benchmark evidence, not real-SME performance.",
            "Candidate selection uses training/validation only; the v0.1.1 test split is quarantined after annotation exposure.",
            "This evaluator measures transcription only; it does not measure field extraction, accounting correctness, or CO2e accuracy.",
            "Peak memory is not measured by this harness.",
        ],
        "engine_availability": unavailable,
        "engine_results": engine_results,
    }
