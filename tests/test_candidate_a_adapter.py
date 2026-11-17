import hashlib
import inspect
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from greenledger.benchmark.candidate_a_adapter import (
    CandidateAAdapter,
    EXPECTED_ARTIFACT_SHA256,
    adapt_candidate_a_output,
)
from greenledger.benchmark.candidate_interface import CandidateDocumentInput
from greenledger.benchmark.contract import validate_prediction
import scripts.evaluate_current_pipeline_contract as candidate_runner


ARTIFACT = Path("models/ai_field_extraction/char_ngram_line_role_v1.json")


def _lpg_extraction():
    return {
        "extractor": "greenledger_char_ngram_line_role_v1",
        "document_type": "fuel invoice",
        "activity": {"value": "lpg", "status": "extracted"},
        "activity_description": {
            "value": "LPG supply",
            "raw_text": "LPG supply",
            "evidence_text": "Product supplied: LPG",
            "status": "extracted",
        },
        "supplier_name": {"value": "North Quay Fuels", "evidence_text": "Supplier: North Quay Fuels", "status": "extracted"},
        "invoice_date": {"value": "2026-07-04", "raw_text": "04/07/2026", "evidence_text": "Date: 04/07/2026", "status": "extracted"},
        "billing_period": {"value": None, "evidence_text": None, "status": "missing"},
        "quantity": {
            "value": "19",
            "normalized_value": "19",
            "unit": "kg",
            "raw_text": "19",
            "evidence_text": "Net LPG mass: 19 kg",
            "status": "extracted",
        },
        "unit": {"value": "kg", "raw_text": "kg", "evidence_text": "Net LPG mass: 19 kg", "status": "extracted"},
        "cylinder_net_mass": {"value": "19 kg", "evidence_text": "Net LPG mass: 19 kg", "status": "extracted"},
        "vehicle_reference": {"value": None, "evidence_text": None, "status": "missing"},
        "confidence": None,
        "confidence_note": "Not calibrated.",
        "human_confirmation_required": True,
        "review_required": True,
        "review_reasons": ["Suggestions require human confirmation."],
    }


class CandidateAAdapterTests(unittest.TestCase):
    def setUp(self):
        self.model = {"model_id": "greenledger_char_ngram_line_role_v1"}

    def _adapter(self, *, transcription="Product supplied: LPG\nNet LPG mass: 19 kg"):
        observed_filenames = []

        def ocr(_content, filename):
            observed_filenames.append(filename)
            return {"status": "OCR_COMPLETE", "transcription": transcription, "latency_seconds": 0.01}

        adapter = CandidateAAdapter(
            ocr=ocr,
            field_extractor=lambda _text, model: _lpg_extraction(),
            model=self.model,
        )
        return adapter, observed_filenames

    def test_adapter_uses_candidate_only_interface_and_schema(self):
        adapter, _filenames = self._adapter()
        document = CandidateDocumentInput("opaque-a1", b"document bytes", "image/png")
        prediction = adapter.predict(document)
        self.assertEqual(prediction.document_id, "opaque-a1")
        self.assertEqual(validate_prediction(prediction.to_dict()), prediction.to_dict())
        with self.assertRaises(TypeError):
            adapter.predict(document, annotation={"domain": "electricity"})

    def test_ground_truth_domain_is_not_an_inference_parameter(self):
        parameters = list(inspect.signature(CandidateAAdapter.predict).parameters)
        self.assertEqual(parameters, ["self", "document"])
        adapter, _ = self._adapter()
        document = CandidateDocumentInput("opaque-domain-independent", b"same bytes", "image/png")
        annotations = (
            {"domain": "electricity", "activity_id": "purchased_electricity"},
            {"domain": "freight", "activity_id": "selected_transport"},
            {},
        )
        predictions = [adapter.predict(document).to_dict() for _annotation in annotations]
        self.assertEqual(predictions[0], predictions[1])
        self.assertEqual(predictions[1], predictions[2])

    def test_candidate_a_artifact_sha256_is_the_preserved_known_artifact(self):
        digest = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
        self.assertEqual(digest, EXPECTED_ARTIFACT_SHA256)
        adapter, _ = self._adapter()
        self.assertEqual(adapter.artifact_sha256, EXPECTED_ARTIFACT_SHA256)

    def test_domain_comes_from_candidate_evidence_and_no_filename_label(self):
        adapter, filenames = self._adapter()
        document = CandidateDocumentInput("opaque-a2", b"same document", "application/pdf")
        prediction = adapter.predict(document).to_dict()
        domain = next(row for row in prediction["extracted_fields"] if row["field_name"] == "document_domain")
        mass = next(row for row in prediction["extracted_fields"] if row["field_name"] == "net_lpg_mass")
        self.assertEqual(domain["candidates"][0]["normalized_value"], "lpg")
        self.assertEqual(mass["candidates"][0]["normalized_value"], "19")
        self.assertEqual(filenames, ["candidate-input.pdf"])
        self.assertNotIn("lpg", filenames[0].casefold())

    def test_manifest_domain_annotation_changes_do_not_change_candidate_prediction(self):
        content = b"same-byte-document"
        content_hash = hashlib.sha256(content).hexdigest()
        row = {
            "document_id": "GL-SYN-E-999",
            "file": "documents/not-a-domain-label.png",
            "sha256": content_hash,
            "domain": "electricity",
            "activity_id": "purchased_electricity",
            "evidence_state": "ready",
            "expected_accounting_readiness": "READY",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "documents").mkdir()
            (root / row["file"]).write_bytes(content)
            with patch.object(candidate_runner, "PILOT", root):
                first_inputs, _first_map = candidate_runner.build_candidate_inputs({"documents": [dict(row)]})
                altered = dict(row, domain="freight", activity_id="selected_transport", evidence_state="ambiguous")
                second_inputs, _second_map = candidate_runner.build_candidate_inputs({"documents": [altered]})
        adapter, _ = self._adapter()
        first = adapter.predict(first_inputs[0]).to_dict()
        second = adapter.predict(second_inputs[0]).to_dict()
        self.assertEqual(first_inputs, second_inputs)
        self.assertEqual(first, second)

    def test_lpg_cylinder_count_is_not_converted_to_net_mass(self):
        extraction = _lpg_extraction()
        extraction["quantity"] = {
            "value": "2", "normalized_value": None, "unit": None,
            "raw_text": "2", "evidence_text": "2 cylinders", "status": "extracted",
        }
        extraction["unit"] = {
            "value": None, "raw_text": "cylinders", "evidence_text": "2 cylinders", "status": "unresolved",
        }
        extraction["cylinder_net_mass"] = {"value": None, "evidence_text": None, "status": "missing"}
        prediction = adapt_candidate_a_output("opaque-cylinder-count", extraction, artifact_sha256=EXPECTED_ARTIFACT_SHA256).to_dict()
        mass = next(row for row in prediction["extracted_fields"] if row["field_name"] == "net_lpg_mass")
        self.assertEqual(mass["evidence_status"], "MISSING")
        self.assertEqual(mass["candidates"], [])

    def test_unparsed_explicit_cylinder_mass_stays_insufficient(self):
        extraction = _lpg_extraction()
        extraction["quantity"] = {"value": None, "normalized_value": None, "unit": None, "raw_text": None, "evidence_text": None, "status": "missing"}
        extraction["unit"] = {"value": None, "raw_text": None, "evidence_text": None, "status": "missing"}
        extraction["cylinder_net_mass"] = {
            "value": "19 kg", "evidence_text": "Net LPG mass: 19 kg", "status": "extracted",
        }
        prediction = adapt_candidate_a_output("opaque-raw-mass", extraction, artifact_sha256=EXPECTED_ARTIFACT_SHA256).to_dict()
        mass = next(row for row in prediction["extracted_fields"] if row["field_name"] == "net_lpg_mass")
        self.assertEqual(mass["evidence_status"], "INSUFFICIENT")
        self.assertIsNone(mass["candidates"][0]["normalized_value"])
        self.assertEqual(mass["candidates"][0]["raw_value"], "19 kg")

    def test_material_and_freight_specific_fields_remain_undetermined(self):
        extraction = _lpg_extraction()
        extraction["activity"] = {"value": None, "status": "missing"}
        extraction["activity_description"] = {
            "value": "PPC cement, road haulage", "raw_text": "PPC cement, road haulage",
            "evidence_text": "Description: PPC cement, road haulage", "status": "extracted",
        }
        extraction["quantity"] = {
            "value": "1200", "normalized_value": "1200", "unit": "kg", "raw_text": "1200",
            "evidence_text": "Quantity: 1200 kg", "status": "extracted",
        }
        prediction = adapt_candidate_a_output("opaque-unsupported", extraction, artifact_sha256=EXPECTED_ARTIFACT_SHA256).to_dict()
        by_name = {row["field_name"]: row for row in prediction["extracted_fields"]}
        self.assertEqual(by_name["document_domain"]["evidence_status"], "UNDETERMINED")
        for field in ("material_identity", "shipment_mass", "distance", "transport_vehicle_class"):
            self.assertEqual(by_name[field]["evidence_status"], "UNDETERMINED")
            self.assertEqual(by_name[field]["candidates"], [])

    def test_freeze_hashes_still_match_without_deserializing_annotations(self):
        marker, manifest = candidate_runner.verify_freeze()
        self.assertEqual(marker["freeze_status"], "FROZEN")
        self.assertEqual(len(manifest["documents"]), 120)
        self.assertEqual(marker["validation"]["old_quarantined_test_split_accessed"], False)


if __name__ == "__main__":
    unittest.main()
