import hashlib
from dataclasses import FrozenInstanceError, fields
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from greenledger.benchmark.candidate_interface import (
    CandidateDocumentInput,
    evaluate_after_candidate_generation,
    generate_candidate_predictions,
)
from greenledger.benchmark.contract import DocumentPrediction, ModelMetadata, validate_prediction
from greenledger.benchmark.current_pipeline_adapter import CurrentPipelineAdapter, adapt_current_pipeline_output
from greenledger.benchmark.evaluator import evaluate_predictions
import scripts.evaluate_current_pipeline_contract as current_runner


class CandidateOnlyBenchmarkTests(unittest.TestCase):
    def test_candidate_interface_has_no_annotation_or_domain_fields(self):
        names = {item.name for item in fields(CandidateDocumentInput)}
        self.assertEqual(names, {"candidate_id", "document_bytes", "media_type"})
        with self.assertRaises(TypeError):
            CandidateDocumentInput("opaque", b"doc", "image/png", domain="lpg")

    def test_current_adapter_rejects_annotation_shaped_input(self):
        adapter = CurrentPipelineAdapter(
            ocr=lambda _content, _filename: {"transcription": "Diesel supplied: 10 L"},
            extractor=lambda _text: {
                "extractor": "injected-test",
                "activity": {"value": "diesel_fuel", "status": "extracted"},
                "quantity": {"value": "10", "normalized_value": "10", "unit": "L", "status": "extracted"},
                "unit": {"value": "L", "raw_text": "L", "status": "extracted"},
            },
        )
        with self.assertRaises(TypeError):
            adapter.predict({"document_id": "GLP-D-001", "domain": "diesel", "fields": []})

    def test_prediction_generation_receives_only_candidate_input(self):
        seen = []

        class SpyAdapter:
            def predict(self, document):
                seen.append(document)
                return adapt_current_pipeline_output(document.candidate_id, None)

        item = CandidateDocumentInput("opaque-case-key", b"image bytes", "image/png")
        predictions = generate_candidate_predictions(SpyAdapter(), [item])
        self.assertEqual(seen, [item])
        self.assertEqual(predictions[0].document_id, item.candidate_id)
        self.assertNotIn("GLP", item.candidate_id)
        validate_prediction(predictions[0])

    def test_manifest_domain_changes_do_not_change_candidate_input_or_field_set(self):
        content = b"synthetic-image-bytes"
        file_hash = hashlib.sha256(content).hexdigest()
        row = {
            "document_id": "case-opaque-to-candidate",
            "file": "documents/input.png",
            "sha256": file_hash,
            "domain": "electricity",
            "activity_id": "purchased_electricity",
            "evidence_state": "ready",
            "expected_accounting_readiness": "READY",
            "template_family": "hidden-family-label",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "documents").mkdir()
            (root / "documents/input.png").write_bytes(content)
            with patch.object(current_runner, "PILOT", root):
                first, first_map = current_runner.build_candidate_inputs({"documents": [dict(row)]})
                altered = dict(row, domain="freight", activity_id="selected_transport", evidence_state="ambiguous")
                second, second_map = current_runner.build_candidate_inputs({"documents": [altered]})
        self.assertEqual(first, second)
        self.assertEqual(first_map, second_map)
        self.assertEqual(first[0].document_bytes, content)
        self.assertEqual(first[0].media_type, "image/png")
        self.assertEqual(set(vars(first[0])), {"candidate_id", "document_bytes", "media_type"})

    def test_annotations_are_loaded_only_after_candidate_generation(self):
        events = []

        class SpyAdapter:
            def predict(self, document):
                events.append("candidate")
                return adapt_current_pipeline_output(document.candidate_id, None)

        input_doc = CandidateDocumentInput("case-1", b"doc", "image/png")
        predictions = generate_candidate_predictions(SpyAdapter(), [input_doc])
        remapped = [predictions[0].to_dict()]
        remapped[0]["document_id"] = "DOC-1"

        annotations = [{"document_id": "DOC-1", "domain": "electricity", "activity_id": "purchased_electricity", "evidence_state": "incomplete", "fields": []}]

        def annotation_loader():
            events.append("annotations")
            return annotations

        def evaluator(prediction_rows, annotation_rows):
            events.append("evaluator")
            self.assertEqual(prediction_rows[0]["document_id"], "DOC-1")
            self.assertIs(annotation_rows, annotations)
            return evaluate_predictions(prediction_rows, annotation_rows)

        result = evaluate_after_candidate_generation(remapped, annotation_loader, evaluator)
        self.assertEqual(events, ["candidate", "annotations", "evaluator"])
        self.assertIn("metrics", result)

    def test_current_pipeline_candidate_predictions_are_reproducible(self):
        document = CandidateDocumentInput("opaque-lpg", b"same bytes", "image/jpeg")
        extraction = {
            "extractor": "injected-test",
            "activity": {"value": "lpg", "raw_text": "LPG", "evidence_text": "Fuel: LPG", "status": "extracted"},
            "quantity": {"value": "18", "normalized_value": "18", "unit": "kg", "raw_text": "18 kg", "evidence_text": "Net mass: 18 kg", "status": "extracted"},
            "unit": {"value": "kg", "raw_text": "kg", "evidence_text": "Net mass: 18 kg", "status": "extracted"},
            "review_reasons": [],
        }
        make_adapter = lambda: CurrentPipelineAdapter(
            ocr=lambda content, filename: {"transcription": "stable transcript", "filename": filename},
            extractor=lambda _text: extraction,
        )
        first = make_adapter().predict(document).to_dict()
        second = make_adapter().predict(document).to_dict()
        self.assertEqual(first, second)
        validate_prediction(first)
        domain = next(row for row in first["extracted_fields"] if row["field_name"] == "document_domain")
        mass = next(row for row in first["extracted_fields"] if row["field_name"] == "net_lpg_mass")
        self.assertEqual(domain["candidates"][0]["normalized_value"], "lpg")
        self.assertEqual(mass["candidates"][0]["normalized_value"], "18")

    def test_candidate_input_is_immutable_and_runner_blocks_pilot_output(self):
        input_doc = CandidateDocumentInput("opaque", b"bytes", "image/png")
        with self.assertRaises(FrozenInstanceError):
            input_doc.candidate_id = "changed"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pilot = root / "pilot"
            pilot.mkdir()
            with patch.object(current_runner, "PILOT", pilot):
                with self.assertRaisesRegex(ValueError, "must not be written inside"):
                    current_runner.run(pilot / "bad-result.json")
            self.assertEqual(list(pilot.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
