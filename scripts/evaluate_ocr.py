"""Measure OCR candidates on GreenLedger synthetic ground-truth transcriptions."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from greenledger.ocr_eval import build_report, discover_engines, evaluate_engine, load_ocr_records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("all", "tesseract", "tesserocr", "rapidocr"), default="all")
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--tesseract-cmd", help="Optional path to a Tesseract executable.")
    parser.add_argument("--tessdata-dir", type=Path, help="Optional directory containing eng.traineddata for tesserocr.")
    parser.add_argument("--limit", type=int, help="Optional small smoke-test limit; do not use limited runs for model selection.")
    parser.add_argument("--store-predictions", action="store_true", help="Include raw OCR transcriptions in the report; use only with synthetic or explicitly approved data.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path; default is stdout.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")

    records = load_ocr_records(args.split)
    if args.limit:
        records = records[:args.limit]
    candidates, availability = discover_engines(args.tesseract_cmd, args.tessdata_dir)
    if args.engine != "all":
        candidates = [engine for engine in candidates if engine["name"] == args.engine]
    results = [evaluate_engine(engine, records, store_predictions=args.store_predictions) for engine in candidates]
    report = build_report(args.split, records, results, availability, smoke_test=bool(args.limit))
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print("Wrote OCR evaluation report to {}".format(args.output))
        print("status={} records={} engines={}".format(report["status"], len(records), len(results)))
    else:
        print(rendered)
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
