import unittest

from greenledger.ai_field_extraction import extract_ai_carbon_fields, load_line_model, load_training_lines


class AIFieldExtractionTests(unittest.TestCase):
    def test_training_examples_come_from_the_approved_training_partition(self):
        samples, counts = load_training_lines()
        self.assertEqual(counts["documents"], 325)
        self.assertEqual(counts["lines"], 5706)
        self.assertEqual(len({document_id for _line, _label, document_id in samples}), 325)

    def test_model_extracts_schema_backed_fields_and_always_requires_review(self):
        model = load_line_model()
        result = extract_ai_carbon_fields("""ELECTRICITY SERVICE STATEMENT
Supplier: Fictional Utility 01
Issue date: 2025-03-03
Energy charge: Active energy used
Units billed: 285 kWh
Quantity unit: kWh""", model=model)
        self.assertEqual(result["supplier_name"]["value"], "Fictional Utility 01")
        self.assertEqual(result["invoice_date"]["value"], "2025-03-03")
        self.assertEqual(result["quantity"]["value"], "285")
        self.assertEqual(result["quantity"]["normalized_value"], "285")
        self.assertEqual(result["unit"]["value"], "kWh")
        self.assertTrue(result["human_confirmation_required"])
        self.assertTrue(result["review_required"])
        self.assertIsNone(result["confidence"])
        self.assertNotIn("factor_id", result)
        self.assertNotIn("co2e", result)


if __name__ == "__main__":
    unittest.main()
