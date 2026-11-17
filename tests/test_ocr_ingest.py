import hashlib
import sys
import types
import unittest
from unittest.mock import patch

from greenledger import ocr
from greenledger.core import evaluate_submission
from greenledger.web import OCR_PREVIEW_SCRIPT, render_form, render_result


class FakeImage:
    def convert(self, mode):
        self.mode = mode
        return self


class FakeArray:
    def __getitem__(self, key):
        return self

    def copy(self):
        return self


class FakeEngine:
    def __call__(self, image):
        return types.SimpleNamespace(txts=["Diesel supplied: 250 litres"])


class OcrIngestTests(unittest.TestCase):
    def test_page_text_extracts_rapidocr_text_and_skips_nulls(self):
        result = types.SimpleNamespace(txts=["Diesel", None, "250 L"])
        self.assertEqual(ocr._page_text(result), "Diesel\n250 L")

    def test_runtime_unavailable_returns_manual_review_without_transcript(self):
        with patch.object(ocr, "get_ocr_runtime_status", return_value={"available": False}):
            result = ocr.recognize_upload(b"document-bytes", "bill.png")
        self.assertEqual(result["status"], "OCR_RUNTIME_UNAVAILABLE")
        self.assertEqual(result["sha256"], hashlib.sha256(b"document-bytes").hexdigest())
        self.assertEqual(result["transcription"], "")
        self.assertIn("manually", result["warning"])

    def test_successful_ocr_keeps_transcript_separate_from_carbon_fields(self):
        status = {"available": True, "engine": "RapidOCR", "version": "3.9.2", "inference_runtime": "ONNX Runtime CPU"}
        fake_numpy = types.SimpleNamespace(asarray=lambda image: FakeArray())
        with patch.object(ocr, "get_ocr_runtime_status", return_value=status), \
             patch.object(ocr, "_images_from_upload", return_value=([(1, FakeImage(), 1.0)], False)), \
             patch.object(ocr, "_get_rapidocr_engine", return_value=FakeEngine()), \
             patch.dict(sys.modules, {"numpy": fake_numpy}):
            result = ocr.recognize_upload(b"document-bytes", "bill.png")
        self.assertEqual(result["status"], "OCR_COMPLETE")
        self.assertEqual(result["transcription"], "Diesel supplied: 250 litres")
        self.assertIsNone(result["confidence"])
        self.assertTrue(result["truncated"] is False)
        self.assertEqual(result["page_count_processed"], 1)

    def test_form_offers_ocr_preview_before_manual_field_entry(self):
        page = render_form()
        self.assertIn("Read OCR transcript", page)
        self.assertIn('id="ocr-preview"', page)
        self.assertIn("/app.js", page)
        self.assertIn("/app.js", page)
        self.assertIn("Copy suggestions into fields", OCR_PREVIEW_SCRIPT)
        self.assertIn("confirmation.checked = false", OCR_PREVIEW_SCRIPT)

    def test_form_exposes_required_accounting_context_without_stale_factor_claims(self):
        page = render_form()
        for field in (
            'name="geography_code"', 'name="applicable_period"', 'name="vehicle_class"',
            'name="material_identity"', 'name="transport_mode"', 'name="transport_vehicle_class"',
            'name="shipment_mass"', 'name="mass_unit"', 'name="distance"', 'name="distance_unit"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, page)
        self.assertIn("PPC cement · CPWD 30% fly-ash reference", page)
        self.assertIn("Conditional LPG; India road diesel", page)
        self.assertNotIn("LPG is pending", page)
        self.assertNotIn("Current CO₂e case</div><div class=\"v\">None", page)
        self.assertIn('name="fields_confirmed"', page)

    def test_freight_result_ui_shows_mass_distance_and_derived_tonne_km(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "shipment_mass": "1000", "mass_unit": "kg", "distance": "100", "distance_unit": "km",
            "fields_confirmed": "yes",
        })
        page = render_result(result, "freight.pdf")
        self.assertIn("Shipment mass input", page)
        self.assertIn("1000 kg", page)
        self.assertIn("100 km", page)
        self.assertIn("100.000 tonne-km", page)
        self.assertNotIn("Entered quantity</div><div class=\"v\">100", page)

    def test_transcript_is_escaped_and_does_not_authorize_calculation(self):
        submission = evaluate_submission({
            "activity": "lpg", "quantity": "1", "unit": "kg", "fields_confirmed": "no",
            "combusted": "yes", "controlled": "yes", "source_type": "stationary",
            "commercial_institutional": "yes",
        })
        result = {
            "status": "OCR_COMPLETE", "engine": "RapidOCR", "engine_version": "3.9.2",
            "sha256": "abc123", "page_count_processed": 1, "pages": [{"page": 1, "text": "<img src=x>"}],
            "transcription": "<img src=x>", "confidence": None,
            "field_candidates": {"activity": {"value": "lpg"}, "human_confirmation_required": True},
        }
        page = render_result(submission, "bill.png", result)
        self.assertIn("&lt;img src=x&gt;", page)
        self.assertNotIn("<img src=x>", page)
        self.assertIn("Needs human review", page)
        self.assertIn("Not calculated", page)
        self.assertIn("Unconfirmed rule-based field suggestions", page)


if __name__ == "__main__":
    unittest.main()
