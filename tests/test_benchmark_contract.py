import unittest

from greenledger.benchmark.contract import (
    Ambiguity,
    BoundingBox,
    DocumentPrediction,
    EvidenceReference,
    FieldCandidate,
    FieldPrediction,
    ModelMetadata,
    validate_prediction,
)
from greenledger.benchmark.current_pipeline_adapter import adapt_current_pipeline_output


class BenchmarkContractTests(unittest.TestCase):
    def test_contract_represents_missing_insufficient_and_undetermined_separately(self):
        prediction = DocumentPrediction(
            document_id="DOC-1",
            extracted_fields=(
                FieldPrediction("net_lpg_mass", "MISSING", "NO_CANDIDATE"),
                FieldPrediction(
                    "quantity", "INSUFFICIENT", "SINGLE_CANDIDATE",
                    (FieldCandidate(raw_value="2", raw_unit="cylinders"),),
                ),
                FieldPrediction("geography", "UNDETERMINED", "NO_CANDIDATE"),
            ),
            model_metadata=ModelMetadata("test"),
        )
        data = validate_prediction(prediction)
        statuses = {row["field_name"]: row["evidence_status"] for row in data["extracted_fields"]}
        self.assertEqual(statuses, {
            "net_lpg_mass": "MISSING",
            "quantity": "INSUFFICIENT",
            "geography": "UNDETERMINED",
        })
        self.assertEqual(data["accounting_readiness"], "UNDETERMINED")

    def test_ambiguity_preserves_each_candidate_and_anchor(self):
        candidates = (
            FieldCandidate(
                raw_value="285", normalized_value="285", raw_unit="kWh", normalized_unit="kWh",
                evidence=(EvidenceReference("Reading A: 285 kWh", 1, BoundingBox(0.1, 0.2, 0.3, 0.1)),),
            ),
            FieldCandidate(
                raw_value="285", normalized_value="285000", raw_unit="MWh", normalized_unit="kWh",
                evidence=(EvidenceReference("Reading B: 285 MWh", 2),),
            ),
        )
        prediction = DocumentPrediction(
            document_id="DOC-2",
            extracted_fields=(FieldPrediction("quantity", "AMBIGUOUS", "MULTIPLE_CANDIDATES", candidates),),
            ambiguities=(Ambiguity("quantity", candidates, reason="Conflicting units."),),
            model_metadata=ModelMetadata("test"),
        )
        data = validate_prediction(prediction)
        field = data["extracted_fields"][0]
        self.assertEqual(field["evidence_status"], "AMBIGUOUS")
        self.assertEqual(len(field["candidates"]), 2)
        self.assertEqual(field["candidates"][0]["evidence"][0]["page"], 1)
        self.assertIsNone(field["candidates"][1]["confidence"])

    def test_contract_rejects_factor_or_accounting_result_fields(self):
        data = DocumentPrediction("DOC-3", (), model_metadata=ModelMetadata("test")).to_dict()
        data["factor_id"] = "must-not-be-here"
        with self.assertRaisesRegex(ValueError, "unsupported top-level"):
            validate_prediction(data)
        data = DocumentPrediction("DOC-4", (), model_metadata=ModelMetadata("test")).to_dict()
        data["extracted_fields"] = [{
            "field_name": "scope",
            "evidence_status": "PRESENT",
            "candidate_state": "NO_CANDIDATE",
            "candidates": [],
            "source_status": None,
            "reason": None,
        }]
        with self.assertRaisesRegex(ValueError, "Unsupported evidence field"):
            validate_prediction(data)

    def test_confidence_and_coordinates_are_validated(self):
        prediction = DocumentPrediction(
            "DOC-5",
            (FieldPrediction(
                "quantity", "PRESENT", "SINGLE_CANDIDATE",
                (FieldCandidate(
                    normalized_value="285", confidence=1.2,
                    evidence=(EvidenceReference("285 kWh", 1, BoundingBox(0.9, 0.1, 0.2, 0.1)),),
                ),),
            ),),
            model_metadata=ModelMetadata("test"),
        )
        with self.assertRaises(ValueError):
            validate_prediction(prediction)

    def test_current_adapter_does_not_infer_lpg_mass_from_cylinder_count(self):
        prediction = adapt_current_pipeline_output("candidate-lpg", {
            "extractor": "rules",
            "activity": {"value": "lpg", "raw_text": None, "evidence_text": None, "status": "extracted"},
            "quantity": {"value": "2", "normalized_value": None, "unit": None, "raw_text": "2 cylinders", "evidence_text": "2 cylinders", "status": "extracted"},
            "unit": {"value": None, "raw_text": "cylinders", "evidence_text": "2 cylinders", "status": "unresolved"},
            "review_reasons": [],
        }).to_dict()
        fields = {item["field_name"]: item for item in prediction["extracted_fields"]}
        self.assertIn("net_lpg_mass", fields)
        self.assertEqual(fields["net_lpg_mass"]["evidence_status"], "UNDETERMINED")
        self.assertEqual(fields["net_lpg_mass"]["candidate_state"], "NO_CANDIDATE")
        self.assertEqual(fields["quantity"]["evidence_status"], "INSUFFICIENT")
        self.assertEqual(fields["quantity"]["candidates"][0]["normalized_value"], None)
        self.assertEqual(prediction["accounting_readiness"], "UNDETERMINED")

    def test_current_adapter_keeps_absence_of_localization_and_calibration(self):
        prediction = adapt_current_pipeline_output("candidate-elec", {
            "extractor": "rules",
            "activity": {"value": "purchased_electricity", "raw_text": None, "evidence_text": None, "status": "extracted"},
            "quantity": {"value": "285", "normalized_value": "285", "unit": "kWh", "raw_text": "285", "evidence_text": None, "status": "extracted"},
            "unit": {"value": "kWh", "raw_text": "kWh", "evidence_text": None, "status": "extracted"},
            "review_reasons": [],
        }).to_dict()
        quantity = next(item for item in prediction["extracted_fields"] if item["field_name"] == "quantity")
        domain = next(item for item in prediction["extracted_fields"] if item["field_name"] == "document_domain")
        self.assertEqual(quantity["evidence_status"], "PRESENT")
        self.assertEqual(quantity["candidates"][0]["evidence"], [])
        self.assertEqual(domain["candidates"][0]["normalized_value"], "electricity")
        self.assertIsNone(quantity["candidates"][0]["confidence"])
        self.assertFalse(prediction["model_metadata"]["confidence_calibrated"])
        self.assertEqual(prediction["accounting_readiness"], "UNDETERMINED")

    def test_unimplemented_critical_fields_are_undetermined_without_domain_input(self):
        prediction = adapt_current_pipeline_output("candidate-unknown", {
            "extractor": "rules",
            "activity": {"value": None, "status": "missing"},
            "quantity": {"value": None, "normalized_value": None, "status": "missing"},
            "unit": {"value": None, "status": "missing"},
        }).to_dict()
        statuses = {item["field_name"]: item["evidence_status"] for item in prediction["extracted_fields"]}
        self.assertEqual(statuses["activity_description"], "MISSING")
        self.assertEqual(statuses["quantity"], "MISSING")
        self.assertEqual(statuses["unit"], "MISSING")
        self.assertEqual(statuses["material_identity"], "UNDETERMINED")
        self.assertEqual(statuses["transport_vehicle_class"], "UNDETERMINED")
        self.assertEqual({item["field_name"] for item in prediction["missing_evidence"]}, {"activity_description", "quantity", "unit"})


if __name__ == "__main__":
    unittest.main()
