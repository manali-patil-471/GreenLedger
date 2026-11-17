import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CORRECTED = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_current_pipeline_candidate_only_contract_v1_2026-11-16.json"
PREVIOUS = ROOT / "data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_contract_baseline_v1_2026-11-16.json"


class CandidateOnlyContractBaselineTests(unittest.TestCase):
    def test_corrected_saved_predictions_reproduce_evaluator_result(self):
        from scripts.evaluate_current_pipeline_contract import (
            _load_annotations_after_candidate_predictions,
            verify_freeze,
        )
        from greenledger.benchmark.evaluator import evaluate_predictions

        marker, _manifest = verify_freeze()
        corrected = json.loads(CORRECTED.read_text(encoding="utf-8"))
        self.assertIs(corrected["candidate_only_protocol"]["candidate_predictions_generated_before_annotation_loader"], True)
        self.assertIs(corrected["candidate_only_protocol"]["old_quarantined_test_split_accessed"], False)
        self.assertEqual(corrected["freeze_verification"]["annotations_sha256"], marker["annotations_sha256"])

        predictions = corrected["predictions"]
        annotations = _load_annotations_after_candidate_predictions()
        recomputed = evaluate_predictions(predictions, annotations)
        self.assertEqual(recomputed, corrected["evaluation"])

        payload = json.dumps(predictions, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertEqual(hashlib.sha256(payload).hexdigest(), corrected["candidate_only_protocol"]["prediction_sha256"])

    def test_old_metrics_are_preserved_and_domain_metric_is_additive(self):
        previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))["evaluation"]["metrics"]
        corrected = json.loads(CORRECTED.read_text(encoding="utf-8"))["evaluation"]["metrics"]
        for section in (
            "carbon_critical_extraction",
            "evidence_grounding",
            "missing_evidence_detection",
            "ambiguity_detection",
            "accounting_readiness",
        ):
            self.assertEqual(corrected[section], previous[section], section)
        self.assertIn("document_domain_classification", corrected)
        self.assertEqual(corrected["document_domain_classification"]["accuracy"], 0.5)

    def test_saved_candidate_predictions_do_not_include_reference_domain_key(self):
        corrected = json.loads(CORRECTED.read_text(encoding="utf-8"))
        for prediction in corrected["predictions"]:
            self.assertNotIn("domain", prediction)
            self.assertIn(
                "document_domain",
                {field["field_name"] for field in prediction["extracted_fields"]},
            )


if __name__ == "__main__":
    unittest.main()
