from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from greenledger.benchmark.candidate_interface import CandidateDocumentInput, generate_candidate_predictions
from greenledger.benchmark.contract import validate_prediction
from greenledger.benchmark.qwen3vl_candidate_adapter import (
    FIELD_ORDER,
    PreparedPage,
    Qwen3VLCandidateAdapter,
    build_evidence_prompt,
    parse_qwen_output,
    prepare_candidate_pages,
    render_pdf_pages,
)
from scripts.run_qwen3vl_smoke_10 import build_smoke_inputs, select_smoke_rows


def _payload(**overrides):
    payload = {
        "document_type": {
            "evidence_status": "PRESENT",
            "raw_value": "Utility statement",
            "normalized_value": "Utility statement",
            "evidence": [{"text": "UTILITY STATEMENT", "page": 1}],
        },
        "document_domain": {
            "evidence_status": "PRESENT",
            "raw_value": "electricity",
            "normalized_value": "electricity",
            "evidence": [{"text": "Energy used", "page": 1}],
        },
        "fields": [
            {
                "field_name": "quantity",
                "evidence_status": "PRESENT",
                "candidates": [{
                    "raw_value": "244.0",
                    "normalized_value": "244.0",
                    "raw_unit": "kWh",
                    "normalized_unit": "kWh",
                    "evidence": [{"text": "Energy used: 244.0 kWh", "page": 1}],
                }],
            },
            {
                "field_name": "unit",
                "evidence_status": "PRESENT",
                "candidates": [{
                    "raw_value": "kWh",
                    "normalized_value": "kWh",
                    "evidence": [{"text": "Energy used: 244.0 kWh", "page": 1}],
                }],
            },
        ],
        "missing_evidence": [],
        "ambiguities": [],
        "accounting_readiness": "UNDETERMINED",
    }
    payload.update(overrides)
    return payload


class Qwen3VLCandidateAdapterTests(unittest.TestCase):
    def test_pdf_rendering_uses_all_pages_and_opaque_names(self):
        seen = {}

        def renderer(pdf_bytes, output_directory):
            seen["bytes"] = pdf_bytes
            paths = []
            for page in (1, 2, 3):
                path = output_directory / f"candidate-input-page-{page:04d}.png"
                path.write_bytes(f"page-{page}".encode())
                paths.append(PreparedPage(path, page))
            return paths

        document = CandidateDocumentInput("freight-secret-id", b"%PDF-original", "application/pdf")
        with tempfile.TemporaryDirectory() as temp:
            pages = prepare_candidate_pages(document, Path(temp), pdf_renderer=renderer)
            self.assertEqual(seen["bytes"], b"%PDF-original")
            self.assertEqual([page.page_number for page in pages], [1, 2, 3])
            self.assertEqual([page.path.name for page in pages], [
                "candidate-input-page-0001.png", "candidate-input-page-0002.png", "candidate-input-page-0003.png",
            ])

    def test_pdfium_renderer_renders_every_page_and_closes_resources(self):
        state = {"closed_pages": [], "closed_images": [], "closed_pdf": False, "scales": []}

        class FakeImage:
            def __init__(self, index):
                self.index = index

            def save(self, path, format):
                self.assert_format = format
                Path(path).write_bytes(f"rendered-{self.index}".encode())

            def close(self):
                state["closed_images"].append(self.index)

        class FakeBitmap:
            def __init__(self, index):
                self.index = index

            def to_pil(self):
                return FakeImage(self.index)

            def close(self):
                pass

        class FakePage:
            def __init__(self, index):
                self.index = index

            def render(self, *, scale):
                state["scales"].append(scale)
                return FakeBitmap(self.index)

            def close(self):
                state["closed_pages"].append(self.index)

        class FakePdf:
            def __init__(self, data):
                self.data = data
                self.pages = [FakePage(1), FakePage(2)]

            def __len__(self):
                return len(self.pages)

            def __getitem__(self, index):
                return self.pages[index]

            def close(self):
                state["closed_pdf"] = True

        fake_pdfium = SimpleNamespace(PdfDocument=FakePdf)
        with patch.dict(sys.modules, {"pypdfium2": fake_pdfium}), tempfile.TemporaryDirectory() as temp:
            pages = render_pdf_pages(b"pdf-bytes", Path(temp))
            self.assertEqual([page.page_number for page in pages], [1, 2])
            self.assertEqual([page.path.name for page in pages], ["candidate-input-page-0001.png", "candidate-input-page-0002.png"])
            self.assertEqual([page.path.read_bytes() for page in pages], [b"rendered-1", b"rendered-2"])
        self.assertEqual(state["scales"], [2.5, 2.5])
        self.assertEqual(state["closed_pages"], [1, 2])
        self.assertEqual(state["closed_images"], [1, 2])
        self.assertTrue(state["closed_pdf"])

    def test_image_is_passed_as_original_bytes_under_generic_name(self):
        document = CandidateDocumentInput("id-with-domain-diesel", b"PNG-DATA", "image/png")
        with tempfile.TemporaryDirectory() as temp:
            pages = prepare_candidate_pages(document, Path(temp))
            self.assertEqual(pages[0].path.name, "candidate-input.png")
            self.assertEqual(pages[0].path.read_bytes(), b"PNG-DATA")
            self.assertEqual(pages[0].page_number, 1)

    def test_adapter_only_receives_candidate_input_and_does_not_pass_opaque_id_to_model(self):
        observed = {}
        response = json.dumps(_payload())

        def fake_runner(command, **kwargs):
            image_arg = command[command.index("--image") + 1]
            observed["command"] = command
            observed["image_name"] = Path(image_arg).name
            observed["image_bytes"] = Path(image_arg).read_bytes()
            observed["prompt"] = command[command.index("-p") + 1]
            return SimpleNamespace(returncode=0, stdout=response, stderr="")

        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.gguf"
            mmproj = Path(temp) / "mmproj.gguf"
            model.write_bytes(b"model")
            mmproj.write_bytes(b"mmproj")
            adapter = Qwen3VLCandidateAdapter(
                llama_binary="/opt/llama",
                model_path=model,
                mmproj_path=mmproj,
                runner=fake_runner,
            )
            candidate = CandidateDocumentInput("secret-domain-diesel-layout-17", b"JPEG-DATA", "image/jpeg")
            prediction = generate_candidate_predictions(adapter, [candidate])[0]

        self.assertEqual(prediction.document_id, "secret-domain-diesel-layout-17")
        self.assertEqual(observed["image_name"], "candidate-input.jpg")
        self.assertEqual(observed["image_bytes"], b"JPEG-DATA")
        command_text = " ".join(observed["command"])
        self.assertNotIn(candidate.candidate_id, command_text)
        self.assertNotIn("annotations", command_text.casefold())
        self.assertIn("document_domain must be one of electricity, diesel", observed["prompt"].casefold())
        self.assertNotIn(candidate.candidate_id, observed["prompt"])
        self.assertIn("-ngl", observed["command"])
        self.assertIn("--single-turn", observed["command"])
        self.assertIn("--mmproj-offload", observed["command"])
        self.assertIn("--offline", observed["command"])
        self.assertIn("--temp", observed["command"])
        self.assertIn("--seed", observed["command"])

    def test_command_includes_single_turn_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.gguf"
            mmproj = Path(temp) / "mmproj.gguf"
            model.write_bytes(b"model")
            mmproj.write_bytes(b"mmproj")
            adapter = Qwen3VLCandidateAdapter(
                llama_binary="llama",
                model_path=model,
                mmproj_path=mmproj,
                runner=lambda *_args, **_kwargs: None,
            )
            dummy_page = PreparedPage(Path(temp) / "candidate-input-page-0001.png", 1)
            cmd = adapter._command([dummy_page])
            self.assertIn("--single-turn", cmd)
            self.assertEqual(cmd[1:3], ["cli", "--single-turn"])

    def test_candidate_input_has_no_ground_truth_fields(self):
        self.assertEqual(
            tuple(field.name for field in CandidateDocumentInput.__dataclass_fields__.values()),
            ("candidate_id", "document_bytes", "media_type"),
        )
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.gguf"
            mmproj = Path(temp) / "mmproj.gguf"
            model.write_bytes(b"model")
            mmproj.write_bytes(b"mmproj")
            adapter = Qwen3VLCandidateAdapter(llama_binary="llama", model_path=model, mmproj_path=mmproj, runner=lambda *_args, **_kwargs: None)
            with self.assertRaises(TypeError):
                adapter.predict({
                    "candidate_id": "opaque",
                    "document_bytes": b"data",
                    "media_type": "image/png",
                    "domain": "electricity",
                    "annotations": {"quantity": "285"},
                })

    def test_output_parser_preserves_evidence_pages_and_validates_contract(self):
        payload = _payload()
        payload.update({"scope": "Scope 2", "emission_factor": 0.67, "co2e": 100, "accounting_result": 100})
        payload["fields"][0]["candidates"][0]["evidence"][0]["bounding_box"] = {
            "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1,
        }
        prediction = parse_qwen_output(
            "llama.cpp log: done\n" + json.dumps(payload), candidate_id="opaque-1", page_count=1,
        )
        contract = validate_prediction(prediction)
        quantity = next(field for field in contract["extracted_fields"] if field["field_name"] == "quantity")
        self.assertEqual(quantity["evidence_status"], "PRESENT")
        self.assertEqual(quantity["candidates"][0]["evidence"][0]["page"], 1)
        self.assertEqual(quantity["candidates"][0]["evidence"][0]["bounding_box"]["x"], 0.1)
        self.assertEqual(len(contract["extracted_fields"]), len(FIELD_ORDER))
        self.assertNotIn("accounting_result", contract)
        self.assertNotIn("emission_factor", json.dumps(contract).casefold())
        self.assertNotIn("co2e", json.dumps(contract).casefold())

    def test_unverifiable_page_reference_is_not_rewritten_to_another_page(self):
        payload = _payload()
        payload["fields"][0]["candidates"][0]["evidence"][0]["page"] = 9
        prediction = parse_qwen_output(json.dumps(payload), candidate_id="opaque", page_count=2)
        quantity = next(field for field in prediction.extracted_fields if field.field_name == "quantity")
        self.assertIsNone(quantity.candidates[0].evidence[0].page)

    def test_missing_and_conflicting_field_states_are_preserved(self):
        payload = _payload()
        payload["fields"] = [
            {"field_name": "billing_period", "evidence_status": "MISSING", "reason": "No period shown", "evidence": []},
            {"field_name": "quantity", "evidence_status": "PRESENT", "candidates": [{
                "raw_value": "285", "normalized_value": "285", "raw_unit": "kWh", "normalized_unit": "kWh",
                "evidence": [{"text": "285 kWh", "page": 1}],
            }]},
        ]
        payload["missing_evidence"] = [{"field_name": "quantity", "reason": "Second quantity is unclear", "evidence": [{"text": "Qty: 285 MWh", "page": 1}]}]
        prediction = parse_qwen_output(json.dumps(payload), candidate_id="opaque", page_count=1)
        billing_period = next(field for field in prediction.extracted_fields if field.field_name == "billing_period")
        quantity = next(field for field in prediction.extracted_fields if field.field_name == "quantity")
        self.assertEqual(billing_period.evidence_status, "MISSING")
        self.assertTrue(any(item.field_name == "billing_period" for item in prediction.missing_evidence))
        self.assertEqual(quantity.evidence_status, "AMBIGUOUS")
        self.assertTrue(any(item.field_name == "quantity" for item in prediction.missing_evidence))
        validate_prediction(prediction)

    def test_ambiguous_values_remain_ambiguous_with_both_evidence_anchors(self):
        payload = _payload()
        payload["fields"] = [{
            "field_name": "quantity",
            "evidence_status": "AMBIGUOUS",
            "candidates": [
                {"raw_value": "285", "normalized_value": "285", "raw_unit": "kWh", "normalized_unit": "kWh", "evidence": [{"text": "285 kWh", "page": 1}]},
                {"raw_value": "285", "normalized_value": "285", "raw_unit": "MWh", "normalized_unit": "MWh", "evidence": [{"text": "285 MWh", "page": 2}]},
            ],
        }]
        payload["ambiguities"] = [{"field_name": "quantity", "reason": "Conflicting units", "candidates": []}]
        prediction = parse_qwen_output(json.dumps(payload), candidate_id="opaque", page_count=2)
        quantity = next(field for field in prediction.extracted_fields if field.field_name == "quantity")
        self.assertEqual(quantity.evidence_status, "AMBIGUOUS")
        self.assertEqual(len(quantity.candidates), 2)
        self.assertEqual({item.evidence[0].page for item in quantity.candidates}, {1, 2})
        validate_prediction(prediction)

    def test_lpg_cylinder_count_is_never_mapped_to_net_mass(self):
        payload = _payload()
        payload["fields"] = [{
            "field_name": "net_lpg_mass",
            "evidence_status": "PRESENT",
            "candidates": [{
                "raw_value": "2 cylinders", "normalized_value": "2 cylinders",
                "raw_unit": "cylinders", "normalized_unit": "cylinders",
                "evidence": [{"text": "LPG: 2 cylinders", "page": 1}],
            }],
        }]
        payload["document_domain"] = {
            "evidence_status": "PRESENT", "raw_value": "lpg", "normalized_value": "lpg",
            "evidence": [{"text": "LPG", "page": 1}],
        }
        prediction = parse_qwen_output(json.dumps(payload), candidate_id="opaque", page_count=1)
        net_mass = next(field for field in prediction.extracted_fields if field.field_name == "net_lpg_mass")
        self.assertEqual(net_mass.evidence_status, "INSUFFICIENT")
        self.assertIsNone(net_mass.candidates[0].normalized_value)
        validate_prediction(prediction)

    def test_prompt_excludes_accounting_decisions_and_requires_visible_evidence(self):
        prompt = build_evidence_prompt(2).casefold()
        self.assertIn("visibly present", prompt)
        self.assertIn("one-based", prompt)
        self.assertIn("never return scope/category", prompt)
        self.assertIn("never return scope/category, emission factors", prompt)
        self.assertIn("never return", prompt)
        self.assertIn("do not convert units", prompt)
        self.assertIn("do not turn cylinder count into net_lpg_mass", prompt)

    def test_smoke_selection_covers_domains_states_pdf_and_image_without_passing_labels(self):
        domains = ("electricity", "diesel", "lpg", "materials", "freight")
        states = ("ready", "incomplete", "ambiguous")
        rows = []
        for index, (domain, state) in enumerate(((d, s) for d in domains for s in states)):
            suffix = ".pdf" if index < 10 else ".png"
            pages = 2 if index == 9 else 1
            rows.append({
                "document_id": f"GLP-{index:03d}", "domain": domain, "evidence_state": state,
                "file": f"documents/{domain}/GLP-{index:03d}{suffix}", "format": "pdf" if suffix == ".pdf" else "image",
                "page_count": pages,
            })
        selected = select_smoke_rows(rows)
        self.assertEqual(len(selected), 10)
        self.assertEqual({row["domain"] for row in selected}, set(domains))
        self.assertEqual({row["evidence_state"] for row in selected}, set(states))
        self.assertTrue(any(Path(row["file"]).suffix == ".pdf" and row["page_count"] > 1 for row in selected))
        self.assertTrue(any(Path(row["file"]).suffix == ".png" for row in selected))

    def test_smoke_runner_keeps_selection_metadata_outside_candidate_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = []
            domains = ("electricity", "diesel", "lpg", "materials", "freight")
            states = ("ready", "incomplete", "ambiguous")
            for index, (domain, state) in enumerate(((d, s) for d in domains for s in states)):
                suffix = ".pdf" if index < 10 else ".jpg"
                relative = f"documents/{domain}/doc-{index:03d}{suffix}"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"document-{index}".encode())
                rows.append({
                    "document_id": f"source-{index:03d}", "domain": domain, "evidence_state": state,
                    "file": relative, "format": "pdf" if suffix == ".pdf" else "image", "page_count": 2 if index == 9 else 1,
                })
            (root / "manifest.json").write_text(json.dumps({"documents": rows}), encoding="utf-8")
            # Deliberately invalid JSON proves the runner never parses annotations.
            (root / "annotations.jsonl").write_text("NOT JSON; must remain unread", encoding="utf-8")
            candidates, mapping = build_smoke_inputs(root)
            self.assertEqual(len(candidates), 10)
            self.assertEqual(set(candidates[0].__dataclass_fields__), {"candidate_id", "document_bytes", "media_type"})
            self.assertFalse(hasattr(candidates[0], "domain"))
            self.assertFalse(hasattr(candidates[0], "document_id"))
            self.assertIn("domain", mapping[0])
            self.assertNotIn("domain", candidates[0].__dict__)


if __name__ == "__main__":
    unittest.main()
