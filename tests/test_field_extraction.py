import unittest

from greenledger.field_extraction import extract_carbon_fields


class RuleFieldExtractionTests(unittest.TestCase):
    def test_electricity_quantity_unit_conversion_and_date(self):
        result = extract_carbon_fields("""ELECTRICITY SERVICE STATEMENT
Supplier: Fictional Utility 01
Issue date: 2024-05-02
Energy charge: Active energy used
Consumption: 1,665 MWh
Quantity unit: MWh""")
        self.assertEqual(result["activity"]["value"], "purchased_electricity")
        self.assertEqual(result["quantity"]["value"], "1665")
        self.assertEqual(result["quantity"]["normalized_value"], "1665000")
        self.assertEqual(result["unit"]["value"], "kWh")
        self.assertEqual(result["invoice_date"]["value"], "2024-05-02")
        self.assertEqual(result["activity"]["status"], "extracted")
        self.assertEqual(result["quantity"]["normalization_status"], "resolved")
        self.assertFalse(result["review_required"])

    def test_diesel_missing_unit_is_not_inferred(self):
        result = extract_carbon_fields("""FUEL SUPPLY INVOICE
Supplier: Sample Fuel Depot 01
Date: 13-Jun-2025
Product: High-speed diesel (HSD)
Quantity: Qty: 1,200
Total paid: INR 30,137""")
        self.assertEqual(result["activity"]["value"], "diesel_fuel")
        self.assertEqual(result["quantity"]["value"], "1200")
        self.assertIsNone(result["unit"]["raw_text"])
        self.assertIsNone(result["quantity"]["normalized_value"])
        self.assertEqual(result["unit"]["status"], "missing")
        self.assertEqual(result["quantity"]["normalization_status"], "unresolved")
        self.assertTrue(result["review_required"])
        self.assertTrue(any("unit" in reason.casefold() for reason in result["review_reasons"]))

    def test_lpg_cylinder_count_is_extracted_but_not_converted_to_mass(self):
        result = extract_carbon_fields("""DELIVERY NOTE - LPG
Supplier: Example Gas Supply 01
Supply date: 2025-02-01
Product: Liquefied petroleum gas
Quantity: Cylinder qty: 7 cylinders
Unit: cylinder count""")
        self.assertEqual(result["activity"]["value"], "lpg")
        self.assertEqual(result["quantity"]["value"], "7")
        self.assertEqual(result["unit"]["raw_text"], "cylinder count")
        self.assertIsNone(result["quantity"]["normalized_value"])
        self.assertEqual(result["unit"]["status"], "unresolved")
        self.assertEqual(result["quantity"]["normalization_status"], "unresolved")
        self.assertTrue(result["review_required"])

    def test_conflicting_quantity_values_abstain(self):
        result = extract_carbon_fields("""Electricity bill
Consumption: 250 or 300 kWh
Quantity unit: kWh""")
        self.assertIsNone(result["quantity"]["value"])
        self.assertEqual(result["quantity"]["status"], "ambiguous")
        self.assertTrue(result["review_required"])

    def test_numeric_confidence_is_explicitly_unavailable(self):
        result = extract_carbon_fields("Electricity bill\nConsumption: 250 kWh")
        self.assertIsNone(result["confidence"])
        self.assertIn("No numeric confidence is calibrated", result["confidence_note"])
        self.assertTrue(result["human_confirmation_required"])

    def test_training_label_variants_use_the_approved_activity_and_unit_rules(self):
        electricity = extract_carbon_fields("""ELECTRICITY SERVICE STATEMENT
Energy used: 4,627 kWh""")
        self.assertEqual(electricity["quantity"]["normalized_value"], "4627")
        self.assertEqual(electricity["unit"]["value"], "kWh")
        lpg = extract_carbon_fields("""DELIVERY NOTE
Product: Cooking gas refill
Quantity: Product mass: 10 kg""")
        self.assertEqual(lpg["activity"]["value"], "lpg")
        self.assertEqual(lpg["quantity"]["normalized_value"], "10")

    def test_numbered_layout_lines_retain_evidence_and_extract_electricity_fields(self):
        result = extract_carbon_fields("""ELECTRICITY SERVICE STATEMENT
01  Supplier: Fictional Utility 01
02  Issue date: 2025-03-03
03  Energy charge: Active energy used
04  Units billed: 285 kWh
05  Quantity unit: kWh""")
        self.assertEqual(result["supplier_name"]["value"], "Fictional Utility 01")
        self.assertEqual(result["invoice_date"]["value"], "2025-03-03")
        self.assertEqual(result["activity"]["raw_text"], "Active energy used")
        self.assertEqual(result["quantity"]["normalized_value"], "285")
        self.assertEqual(result["unit"]["value"], "kWh")
        self.assertEqual(result["quantity"]["evidence_text"], "04  Units billed: 285 kWh")

    def test_unlabeled_unique_unit_quantity_is_extracted_with_source_evidence(self):
        result = extract_carbon_fields("ELECTRICITY BILL\nSupplier: Example Utility\n285 kWh")
        self.assertEqual(result["quantity"]["normalized_value"], "285")
        self.assertEqual(result["unit"]["value"], "kWh")
        self.assertEqual(result["quantity"]["evidence_text"], "285 kWh")
        self.assertFalse(result["review_required"])

    def test_multiple_unlabeled_unit_quantities_abstain_as_ambiguous(self):
        result = extract_carbon_fields("ELECTRICITY BILL\n285 kWh\n310 kWh")
        self.assertIsNone(result["quantity"]["value"])
        self.assertEqual(result["quantity"]["status"], "ambiguous")
        self.assertTrue(result["review_required"])

    def test_rate_per_kwh_is_not_mistaken_for_consumption(self):
        result = extract_carbon_fields("ELECTRICITY BILL\nRate: INR 8/kWh")
        self.assertIsNone(result["quantity"]["value"])
        self.assertTrue(result["review_required"])


if __name__ == "__main__":
    unittest.main()
