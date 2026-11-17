from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from greenledger.benchmark.candidate_interface import CandidateDocumentInput, generate_candidate_predictions
from greenledger.benchmark.contract import validate_prediction
from greenledger.benchmark.paddleocr_vl_adapter import (
    PaddleOCRVLCandidateAdapter,
    parse_page_results,
)


class FakeResult:
    def __init__(self, page_index, blocks, *, width=1000, height=2000):
        self.json = {
            "res": {
                "page_index": page_index,
                "width": width,
                "height": height,
                "parsing_res_list": [
                    {
                        "block_content": text,
                        "block_label": "text",
                        "block_bbox": bbox,
                    }
                    for text, bbox in blocks
                ],
            }
        }


class FakePipeline:
    def __init__(self, results):
        self.results = results
        self.seen_name = None
        self.seen_bytes = None

    def predict(self, path):
        candidate_path = Path(path)
        self.seen_name = candidate_path.name
        self.seen_bytes = candidate_path.read_bytes()
        return self.results


def _field(prediction, name):
    return next(item for item in prediction.extracted_fields if item.field_name == name)


class PaddleOCRVLAdapterTests(unittest.TestCase):
    def test_candidate_only_input_and_schema_valid_prediction(self):
        pipeline = FakePipeline([
            FakeResult(0, [
                ("PPC cement invoice", [100, 200, 300, 400]),
                ("Material: PPC cement", [100, 500, 500, 600]),
                ("Quantity: 1000 kg", [100, 700, 500, 800]),
                ("Location: India", [100, 900, 400, 1000]),
                ("Purchase: purchase invoice", [100, 1100, 600, 1200]),
            ])
        ])
        adapter = PaddleOCRVLCandidateAdapter(pipeline=pipeline)
        document = CandidateDocumentInput("opaque-123", b"%PDF-test-bytes", "application/pdf")
        predictions = generate_candidate_predictions(adapter, [document])
        self.assertEqual(pipeline.seen_name, "candidate-input.pdf")
        self.assertEqual(pipeline.seen_bytes, b"%PDF-test-bytes")
        self.assertEqual(predictions[0].document_id, "opaque-123")
        self.assertEqual(predictions[0].accounting_readiness, "READY")
        payload = validate_prediction(predictions[0])
        self.assertEqual(
            payload["model_metadata"]["candidate_name"],
            "PaddleOCR-VL-1.6 full PaddleOCR pipeline (transformers engine) + fixed evidence mapper",
        )
        self.assertNotIn("emission_factor", json.dumps(payload))
        self.assertNotIn("co2e", json.dumps(payload).casefold())

    def test_transformers_engine_is_explicit_for_the_full_pipeline(self):
        calls = []
        expected_pipeline = FakePipeline([FakeResult(0, [("Electricity", [0, 0, 300, 100])])])

        def factory(**kwargs):
            calls.append(kwargs)
            return expected_pipeline

        adapter = PaddleOCRVLCandidateAdapter(pipeline_factory=factory, engine="transformers")
        self.assertEqual(calls, [{"pipeline_version": "v1.6", "device": "cpu", "engine": "transformers"}])
        self.assertEqual(adapter.engine, "transformers")

    def test_adapter_rejects_annotation_shaped_inputs(self):
        adapter = PaddleOCRVLCandidateAdapter(pipeline=FakePipeline([]))
        with self.assertRaises(TypeError):
            adapter.predict({
                "candidate_id": "opaque-case",
                "document_bytes": b"document",
                "media_type": "image/png",
                "domain": "electricity",
                "annotations": {"quantity": "285"},
            })

    def test_domain_is_not_inferred_from_candidate_id(self):
        pipeline = FakePipeline([FakeResult(0, [("Record summary", [0, 0, 300, 100])])])
        prediction = PaddleOCRVLCandidateAdapter(pipeline=pipeline).predict(
            CandidateDocumentInput("electricity-diesel-lpg-materials-freight", b"image", "image/png")
        )
        domain = _field(prediction, "document_domain")
        self.assertEqual(domain.evidence_status, "MISSING")
        self.assertEqual(domain.candidates, ())

    def test_bbox_is_normalized_and_page_index_is_one_based(self):
        blocks, pages = parse_page_results([
            FakeResult(1, [("Energy consumption: 285 kWh", [100, 200, 300, 400])])
        ])
        self.assertEqual(blocks[0].page, 2)
        self.assertEqual(pages[0]["page"], 2)
        self.assertEqual(blocks[0].bbox.x, 0.1)
        self.assertEqual(blocks[0].bbox.y, 0.1)
        self.assertAlmostEqual(blocks[0].bbox.width, 0.2)
        self.assertAlmostEqual(blocks[0].bbox.height, 0.1)

    def test_multiple_quantity_interpretations_remain_ambiguous(self):
        pipeline = FakePipeline([
            FakeResult(0, [
                ("Electricity bill", [0, 0, 500, 100]),
                ("Consumption: 285 kWh", [50, 200, 500, 300]),
                ("Consumption: 285 MWh", [50, 400, 500, 500]),
                ("Supply type: purchased grid electricity", [50, 600, 500, 700]),
                ("Location: India", [50, 800, 500, 900]),
                ("Billing period: April 2025", [50, 1000, 500, 1100]),
            ])
        ])
        prediction = PaddleOCRVLCandidateAdapter(pipeline=pipeline).predict(
            CandidateDocumentInput("candidate-x", b"image", "image/png")
        )
        quantity = _field(prediction, "quantity")
        self.assertEqual(quantity.evidence_status, "AMBIGUOUS")
        self.assertEqual(len(quantity.candidates), 2)
        self.assertEqual(prediction.accounting_readiness, "AMBIGUOUS")

    def test_lpg_cylinder_count_is_not_converted_to_net_mass(self):
        pipeline = FakePipeline([
            FakeResult(0, [
                ("LPG refill receipt", [0, 0, 500, 100]),
                ("Product: LPG cylinder refill", [50, 200, 500, 300]),
                ("Quantity: 2 cylinders", [50, 400, 500, 500]),
            ])
        ])
        prediction = PaddleOCRVLCandidateAdapter(pipeline=pipeline).predict(
            CandidateDocumentInput("candidate-lpg", b"image", "image/jpeg")
        )
        mass = _field(prediction, "net_lpg_mass")
        self.assertEqual(mass.evidence_status, "MISSING")
        self.assertEqual(mass.candidates, ())
        self.assertNotIn("net_lpg_mass", [item.field_name for item in prediction.ambiguities])
        self.assertEqual(prediction.accounting_readiness, "INCOMPLETE")

    def test_vehicle_reference_does_not_infer_freight_vehicle_class(self):
        pipeline = FakePipeline([
            FakeResult(0, [
                ("Road freight consignment", [0, 0, 700, 100]),
                ("Vehicle: Truck AB12CD3456", [50, 200, 700, 300]),
                ("Shipment mass: 4 tonnes", [50, 400, 700, 500]),
                ("Distance: 300 km", [50, 600, 700, 700]),
            ])
        ])
        prediction = PaddleOCRVLCandidateAdapter(pipeline=pipeline).predict(
            CandidateDocumentInput("candidate-freight", b"image", "image/png")
        )
        self.assertEqual(_field(prediction, "transport_vehicle_class").evidence_status, "MISSING")
        self.assertEqual(prediction.accounting_readiness, "INCOMPLETE")

    def test_multpage_page_references_preserved(self):
        pipeline = FakePipeline([
            FakeResult(0, [("Diesel fuel", [0, 0, 300, 100])]),
            FakeResult(1, [("Fuel quantity: 250 L", [100, 200, 400, 300])]),
        ])
        adapter = PaddleOCRVLCandidateAdapter(pipeline=pipeline)
        prediction = adapter.predict(CandidateDocumentInput("candidate-pdf", b"%PDF-multi", "application/pdf"))
        self.assertEqual([page["page"] for page in adapter.last_pages], [1, 2])
        qty_evidence = _field(prediction, "quantity").candidates[0].evidence[0]
        self.assertEqual(qty_evidence.page, 2)


if __name__ == "__main__":
    unittest.main()
