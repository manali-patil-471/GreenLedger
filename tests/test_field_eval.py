import unittest
from unittest.mock import patch

from greenledger.field_eval import _score_numeric, _score_values, _exact_text, evaluate_rule_fields


class FieldEvaluationTests(unittest.TestCase):
    def test_field_precision_recall_f1_count_wrong_values_as_fp_and_fn(self):
        metrics = _score_values([("250", "250"), ("1", "2"), (None, None)], _exact_text)
        self.assertEqual(metrics["true_positive"], 1)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertEqual(metrics["f1"], 0.5)

    def test_numeric_metric_uses_numeric_equality_and_error(self):
        metrics = _score_numeric([("250.0", "250"), ("100", "90")])
        self.assertEqual(metrics["exact_match_rate"], 0.5)
        self.assertEqual(metrics["mae"], 5.0)
        self.assertEqual(metrics["mean_relative_error"], 0.05)

    def test_rule_evaluation_joins_ocr_predictions_to_existing_truth(self):
        annotation = {
            "document_id": "GL-SYN-D-X", "document_type": "diesel_fuel_invoice",
            "ground_truth": {
                "activity_normalization": {"normalized_activity": "diesel_fuel"},
                "fields": [
                    {"field_name": "supplier_name", "presence_status": "present", "normalized_value": "Sample Fuel Depot"},
                    {"field_name": "invoice_date", "presence_status": "present", "normalized_value": "2025-06-13"},
                    {"field_name": "activity_description", "presence_status": "present", "normalized_value": "High-speed diesel (HSD)"},
                    {"field_name": "quantity", "presence_status": "present", "raw_text": "1,200 L", "normalized_value": 1200.0},
                    {"field_name": "unit", "presence_status": "present", "raw_text": "L", "normalized_value": "L"},
                ],
            },
        }
        report = {
            "dataset": {"synthetic_only": True, "split": "validation", "dataset_id": "test"},
            "engine_results": [{"engine": {"name": "test"}, "predictions": [{
                "document_id": "GL-SYN-D-X",
                "transcription": "FUEL SUPPLY INVOICE\nSupplier: Sample Fuel Depot\nDate: 13-Jun-2025\nProduct: High-speed diesel (HSD)\nQuantity: 1,200 L\nUnit: L",
            }]}],
        }
        with patch("greenledger.field_eval._load_annotations", return_value={"GL-SYN-D-X": annotation}):
            result = evaluate_rule_fields(report)
        self.assertEqual(result["metrics"]["document_type"]["accuracy"], 1.0)
        self.assertEqual(result["metrics"]["quantity_raw_numeric"]["exact_match_rate"], 1.0)
        self.assertEqual(result["metrics"]["unit_normalization"]["exact_match_rate"], 1.0)
        self.assertFalse(result["per_document"][0]["predicted_review"])
        self.assertEqual(result["per_document"][0]["field_states"]["quantity"], "extracted")
        self.assertIsNone(result["per_document"][0]["confidence"])


if __name__ == "__main__":
    unittest.main()
