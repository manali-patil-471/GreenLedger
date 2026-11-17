import unittest
from io import StringIO

from unittest.mock import patch

from greenledger.ocr_eval import edit_distance, evaluate_engine, iter_jsonl_split_records, load_ocr_records, normalize_ocr_text, summarize_rows, text_error_counts


class OcrMetricTests(unittest.TestCase):
    def test_split_filter_skips_out_of_partition_labels_before_json_deserialization(self):
        source = StringIO('{"annotation_metadata":{"split":"test"},"split":"validation","document_id":"val-1"}\n{"annotation_metadata":{},"split":"test","ground_truth": this is intentionally not parsed}\n')
        rows = list(iter_jsonl_split_records(source, "validation"))
        self.assertEqual(rows, [(1, {"annotation_metadata": {"split": "test"}, "split": "validation", "document_id": "val-1"})])

    def test_split_iterator_refuses_quarantined_test_partition(self):
        with self.assertRaisesRegex(ValueError, "quarantined"):
            list(iter_jsonl_split_records(StringIO('{"split":"test"}'), "test"))

    def test_normalization_ignores_case_unicode_width_and_whitespace(self):
        self.assertEqual(normalize_ocr_text("  QTY： 250   L\n"), "qty: 250 l")

    def test_levenshtein_distance_handles_strings_and_word_lists(self):
        self.assertEqual(edit_distance("kitten", "sitting"), 3)
        self.assertEqual(edit_distance(["250", "litres"], ["250", "L"]), 1)

    def test_text_metrics_treat_formatting_variants_as_equal(self):
        row = text_error_counts("250 litres\nDiesel", "250  LITRES Diesel")
        self.assertEqual(row["char_edits"], 0)
        self.assertEqual(row["word_edits"], 0)
        self.assertTrue(row["exact_match"])

    def test_summary_uses_pooled_cer_wer_and_reports_exact_rate(self):
        rows = [
            text_error_counts("250 L", "250 L"),
            text_error_counts("Diesel fuel", "Diesel fuell"),
        ]
        summary = summarize_rows(rows)
        self.assertEqual(summary["documents"], 2)
        self.assertGreater(summary["cer"], 0)
        self.assertEqual(summary["exact_match_rate"], 0.5)

    def test_bootstrap_intervals_are_deterministic(self):
        rows = [
            text_error_counts("Invoice amount", "Invoice amount"),
            text_error_counts("Quantity 250 L", "Quantity 250 I"),
            text_error_counts("Diesel receipt", "Diesel receipt"),
        ]
        first = summarize_rows(rows, include_confidence_intervals=True)["bootstrap_95_ci"]
        second = summarize_rows(rows, include_confidence_intervals=True)["bootstrap_95_ci"]
        self.assertEqual(first, second)
        self.assertEqual(first["replicates"], 1000)
        self.assertIsNotNone(first["cer"])
        self.assertIsNotNone(first["wer"])

    def test_validation_loader_reads_only_checksum_verified_ocr_records(self):
        records = load_ocr_records("validation", verify_hashes=True)
        self.assertEqual(len(records), 65)
        self.assertEqual(len({row["document_id"] for row in records}), 65)
        self.assertTrue(all(row["image_path"].is_file() for row in records))

    def test_raw_predictions_are_only_stored_when_explicitly_requested(self):
        record = {"document_id": "synthetic-1", "document_type": "electricity_bill", "layout_family": "layout_A", "quality_tags": [], "image_path": "synthetic.png", "reference": "250 kWh"}
        engine = {"name": "tesseract", "executable": "tesseract", "version": "test"}
        with patch("greenledger.ocr_eval._run_tesseract", return_value="250 kWh"):
            without_text = evaluate_engine(engine, [record])
        with patch("greenledger.ocr_eval._run_tesseract", return_value="250 kWh"):
            with_text = evaluate_engine(engine, [record], store_predictions=True)
        self.assertNotIn("predictions", without_text)
        self.assertEqual(with_text["predictions"], [{"document_id": "synthetic-1", "transcription": "250 kWh"}])


if __name__ == "__main__":
    unittest.main()
