"""INVALID legacy attempt: Florence-2 does not document the prompted DocVQA task used below."""

raise SystemExit(
    "INVALID EXPERIMENT: this legacy harness prompts Florence-2 with unsupported <DocVQA>. "
    "Do not run or cite it. The valid measured candidate is scripts/evaluate_florence_ocr.py."
)

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".venv-field-eval" / "hf_home"))

from greenledger.core import ValidationError, load_activities, normalize_activity, normalize_quantity, normalize_unit
from greenledger.field_eval import _exact_text, _load_annotations, _parse_number, _score_numeric, _score_values
from greenledger.field_extraction import _date_iso


MODEL_ID = "microsoft/Florence-2-base-ft"
MODEL_REVISION = "f6c1a25888ffc1d945ee8a1a77ac833c7303d46e"
MODEL_WEIGHT_SHA256 = "58757d657ff44051314c8030b68e04cb1bb618ca9a4885418f111f6fb708185a"
ACTIVITY_BY_DOC_TYPE = {
    "electricity_bill": "purchased_electricity",
    "diesel_fuel_invoice": "diesel_fuel",
    "lpg_receipt": "lpg",
}
QUESTIONS = {
    "document_type": "Classify this document as electricity_bill, diesel_fuel_invoice, lpg_receipt, or other. Answer with one label only.",
    "activity_description": "What electricity activity or fuel product is billed? Copy the activity or product wording only.",
    "supplier_name": "What is the supplier or vendor name on this document? Copy the name only.",
    "invoice_date": "What is the issue, invoice, or supply date? Copy the date only.",
    "quantity": (
        "What exact fuel or electricity quantity and unit are explicitly shown for the billed activity? "
        "Copy the number and unit only. Do not use a price, tax, total, or account number. "
        "If the quantity or unit is missing, unclear, or ambiguous, answer unanswerable."
    ),
}
PROMPTS = {name: "<DocVQA>{}</DocVQA>".format(question) for name, question in QUESTIONS.items()}


def _clean_candidate(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    result = str(value).strip()
    if not result or result.casefold() in {"null", "none", "not found", "unknown", "n/a"}:
        return None
    return result


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
    relevant_files = (
        "model.safetensors", "configuration_florence2.py", "modeling_florence2.py",
        "processing_florence2.py", "config.json", "preprocessor_config.json",
    )
    model_hashes = {name: _sha256(model_path / name) for name in relevant_files if (model_path / name).is_file()}
    return model, processor, torch, model_hashes


def _ask(model, processor, torch, image, prompt):
    width, height = image.size
    batch = processor(text=prompt, images=image, return_tensors="pt")
    with torch.inference_mode():
        generated = model.generate(
            input_ids=batch["input_ids"],
            pixel_values=batch["pixel_values"],
            max_new_tokens=64,
            num_beams=1,
            do_sample=False,
            early_stopping=False,
        )
    decoded = processor.batch_decode(generated, skip_special_tokens=False)[0]
    try:
        processed = processor.post_process_generation(decoded, task="<DocVQA>", image_size=(width, height))
    except Exception:
        processed = decoded
    if isinstance(processed, dict):
        answer = processed.get("<DocVQA>", processed.get("answer", decoded))
    else:
        answer = processed
    return _clean_candidate(answer) or "unanswerable"


def _document_type_label(answer):
    value = (answer or "").casefold().replace(" ", "_").replace("-", "_")
    if value in {"electricity_bill", "electricity_invoice", "power_bill", "utility_bill"}:
        return "electricity_bill"
    if value in {"diesel_fuel_invoice", "diesel_invoice", "fuel_invoice", "diesel_receipt"}:
        return "diesel_fuel_invoice"
    if value in {"lpg_receipt", "lpg_invoice", "gas_receipt", "gas_invoice"}:
        return "lpg_receipt"
    return None


def _quantity_unit(answer):
    if not answer or answer.casefold() == "unanswerable":
        return None
    value = re.sub(r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?(?!\w)", " ", answer, count=1)
    value = re.sub(r"\b(?:qty|quantity|volume|consumption|usage|supplied|used|billed|is|of|unit)\b", " ", value, flags=re.I)
    value = re.sub(r"[|:;,.()\[\]{}]", " ", value)
    value = " ".join(value.split()).strip()
    return value or None


def _run_one(model, processor, torch, image_path):
    from PIL import Image

    with Image.open(image_path) as source:
        image = source.convert("RGB")
    answers = {field: _ask(model, processor, torch, image, prompt) for field, prompt in PROMPTS.items()}
    quantity_answer = answers["quantity"]
    quantity_number = _parse_number(quantity_answer)
    prediction = {
        "document_type": _document_type_label(answers["document_type"]),
        "activity_description": answers["activity_description"] if answers["activity_description"].casefold() != "unanswerable" else None,
        "supplier_name": answers["supplier_name"] if answers["supplier_name"].casefold() != "unanswerable" else None,
        "invoice_date": answers["invoice_date"] if answers["invoice_date"].casefold() != "unanswerable" else None,
        "quantity": str(quantity_number) if quantity_number is not None else None,
        "unit": _quantity_unit(quantity_answer),
    }
    return answers, prediction


def _ground_truth_fields(annotation):
    return {field.get("field_name"): field for field in annotation.get("ground_truth", {}).get("fields", [])}


def _activity_id(prediction):
    doc_type = prediction.get("document_type")
    if doc_type in ACTIVITY_BY_DOC_TYPE:
        return ACTIVITY_BY_DOC_TYPE[doc_type]
    description = prediction.get("activity_description")
    if description:
        try:
            return normalize_activity(description)["id"]
        except ValidationError:
            return None
    return None


def _normalized_quantity(prediction):
    quantity = _parse_number(prediction.get("quantity"))
    unit_text = prediction.get("unit")
    activity_id = _activity_id(prediction)
    if quantity is None or not unit_text or not activity_id:
        return None, None
    try:
        activity = normalize_activity(activity_id)
        input_unit = normalize_unit(activity, unit_text)
        normalized_value, canonical_unit, _trace = normalize_quantity(activity, quantity, input_unit)
        if normalized_value is None:
            return None, None
        return str(normalized_value), canonical_unit
    except ValidationError:
        return None, None


def _field_values(pairs, field_name):
    return [(expected.get(field_name), prediction.get(field_name)) for expected, prediction in pairs]


def _evaluate_metrics(rows):
    predictions = [row["prediction"] or {} for row in rows]
    doc_types = [(row["expected"]["document_type"], pred.get("document_type")) for row, pred in zip(rows, predictions)]
    activity = [(row["expected"]["activity"], _activity_id(pred)) for row, pred in zip(rows, predictions)]
    activity_text = [(row["expected"]["activity_description"], pred.get("activity_description")) for row, pred in zip(rows, predictions)]
    suppliers = [(row["expected"]["supplier_name"], pred.get("supplier_name")) for row, pred in zip(rows, predictions)]
    dates = [(row["expected"]["invoice_date"], _date_iso(pred.get("invoice_date"))) for row, pred in zip(rows, predictions)]
    quantities = [(row["expected"]["quantity_numeric"], _parse_number(pred.get("quantity"))) for row, pred in zip(rows, predictions)]
    units_raw = [(row["expected"]["unit_raw"], pred.get("unit")) for row, pred in zip(rows, predictions)]
    normalized_units = []
    normalized_quantities = []
    expected_unresolved = 0
    for row in rows:
        expected_unit = row["expected"]["unit_normalized"]
        predicted_quantity, predicted_unit = _normalized_quantity(row["prediction"] or {})
        if expected_unit is None:
            if row["expected"]["unit_raw"] is not None:
                expected_unresolved += 1
            continue
        normalized_units.append((expected_unit, predicted_unit))
        normalized_quantities.append((row["expected"]["quantity_normalized"], predicted_quantity))

    labels = sorted({value for value, _ in doc_types if value is not None})
    confusion = {label: {predicted: 0 for predicted in labels} for label in labels}
    for expected, predicted in doc_types:
        if expected in confusion and predicted in confusion[expected]:
            confusion[expected][predicted] += 1
        elif expected in confusion and predicted is not None:
            confusion[expected]["OTHER"] = confusion[expected].get("OTHER", 0) + 1
    doc_accuracy = sum(expected == predicted for expected, predicted in doc_types) / len(doc_types) if doc_types else None
    return {
        "document_type": {"accuracy": doc_accuracy, "documents": len(doc_types), "confusion_matrix": confusion},
        "activity_normalization": _score_values(activity, _exact_text),
        "activity_description": _score_values(activity_text, _exact_text),
        "supplier_name": _score_values(suppliers, _exact_text),
        "invoice_date": _score_values(dates, _exact_text),
        "quantity_raw_numeric": _score_numeric(quantities),
        "unit_raw_extraction": _score_values(units_raw, _exact_text),
        "unit_normalization": {
            **_score_values(normalized_units, _exact_text),
            "eligible_documents": len(normalized_units),
            "present_but_unresolved_documents": expected_unresolved,
        },
        "normalized_quantity": _score_numeric(normalized_quantities),
        "complete_inference_rate": sum(row["inference_error"] is None for row in rows) / len(rows) if rows else None,
    }


def _annotation_values(annotation):
    fields = _ground_truth_fields(annotation)
    quantity = fields.get("quantity", {})
    unit = fields.get("unit", {})
    quantity_numeric = _parse_number(quantity.get("raw_text")) if quantity.get("presence_status") == "present" else None
    quantity_normalized = quantity.get("normalized_value") if unit.get("normalized_value") is not None else None
    return {
        "document_type": annotation.get("document_type"),
        "activity": annotation.get("ground_truth", {}).get("activity_normalization", {}).get("normalized_activity"),
        "activity_description": fields.get("activity_description", {}).get("normalized_value"),
        "supplier_name": fields.get("supplier_name", {}).get("normalized_value"),
        "invoice_date": fields.get("invoice_date", {}).get("normalized_value"),
        "quantity_numeric": str(quantity_numeric) if quantity_numeric is not None else None,
        "quantity_normalized": str(quantity_normalized) if quantity_normalized is not None else None,
        "unit_raw": unit.get("raw_text") if unit.get("presence_status") == "present" else None,
        "unit_normalized": unit.get("normalized_value"),
    }


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="validation")
    parser.add_argument("--final-test", action="store_true", help="Acknowledge final test evaluation after the prompt/model is frozen.")
    parser.add_argument("--limit", type=int, help="Optional smoke-run limit; limited runs are not benchmark results.")
    parser.add_argument("--output", type=Path, help="Write result JSON here; defaults to stdout.")
    args = parser.parse_args(argv)
    if args.split == "test" and not args.final_test:
        parser.error("the test split is reserved; pass --final-test only after the candidate and prompt are frozen")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")

    annotations = _load_annotations(args.split)
    ids = sorted(annotations)
    if args.limit is not None:
        ids = ids[:args.limit]
    model, processor, torch, model_hashes = _load_model()

    rows, latencies = [], []
    for index, document_id in enumerate(ids, 1):
        annotation = annotations[document_id]
        relative = Path(annotation["source_document"]["path_or_id"])
        image_path = (ROOT / "data" / "synthetic" / "greenledger_v0_1_1_partial" / relative).resolve()
        started = time.perf_counter()
        try:
            raw_output, prediction = _run_one(model, processor, torch, image_path)
            error = None
        except Exception as error_value:
            raw_output, prediction = "", None
            error = type(error_value).__name__
        latency = time.perf_counter() - started
        latencies.append(latency)
        rows.append({
            "document_id": document_id,
            "expected": _annotation_values(annotation),
            "prediction": prediction,
            "field_answers": raw_output,
            "inference_error": error,
            "latency_seconds": round(latency, 4),
            "source_sha256": annotation.get("source_document", {}).get("sha256"),
        })
        print("Florence progress: {}/{}".format(index, len(ids)), file=sys.stderr, flush=True)

    complete = args.limit is None
    report = {
        "status": "MEASURED" if complete else "SMOKE_TEST_ONLY",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "dataset_id": "greenledger_synthetic_v0_1_1_partial",
            "split": args.split,
            "synthetic_only": True,
            "documents": len(rows),
            "full_split": complete,
        },
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "license": "MIT",
            "runtime": {"torch": torch.__version__, "transformers": __import__("transformers").__version__, "device": "CPU", "visible_cuda": torch.cuda.is_available()},
            "file_sha256": model_hashes,
        },
        "extractor": "Florence-2-base-ft-DocVQA-prompt-v2",
        "prompts": PROMPTS,
        "limitations": [
            "Pretrained prompted baseline only; no GreenLedger fine-tuning was performed.",
            "Evaluation uses synthetic annotations only and does not measure real-SME generalization.",
            "Model output is advisory. No scope/category, factor, CO2e, or calibrated confidence is generated or evaluated.",
            "Every candidate requires human verification; model output cannot authorize accounting calculation.",
            "Activity-unit conversions and canonical activity mappings are applied by the GreenLedger deterministic rules after extraction.",
        ],
        "latency_seconds": {
            "documents": len(latencies),
            "mean": statistics.mean(latencies) if latencies else None,
            "p50": statistics.median(latencies) if latencies else None,
            "p95": sorted(latencies)[max(0, int(0.95 * len(latencies) + 0.999999) - 1)] if latencies else None,
        },
        "metrics": _evaluate_metrics(rows),
        "per_document": rows,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print("Wrote Florence field evaluation to {}".format(args.output))
        print("status={} split={} documents={}".format(report["status"], args.split, len(rows)))
    else:
        print(rendered)


if __name__ == "__main__":
    main()
