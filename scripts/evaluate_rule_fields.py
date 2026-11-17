"""Evaluate conservative rule-extracted carbon fields on a checksum-verified OCR report."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from greenledger.field_eval import evaluate_rule_fields


DEFAULT_INPUT = Path("data/benchmark/evaluations/ocr/rapidocr_3_9_2_validation_2026-09-24_with_predictions.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="OCR evaluator report created with --store-predictions.")
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--output", type=Path, help="Optional JSON evaluation report path; default is stdout.")
    args = parser.parse_args(argv)

    ocr_report = json.loads(args.input.read_text(encoding="utf-8"))
    if ocr_report.get("dataset", {}).get("split") != args.split:
        parser.error("--split does not match the split recorded in the OCR report")
    report = evaluate_rule_fields(ocr_report)
    report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    report["input_report"] = str(args.input)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print("Wrote rule-field evaluation report to {}".format(args.output))
        print("status={} split={} documents={}".format(report["status"], report["dataset"]["split"], report["dataset"]["documents"]))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
