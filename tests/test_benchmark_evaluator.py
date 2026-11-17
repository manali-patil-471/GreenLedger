import unittest

from greenledger.benchmark.contract import (
    BoundingBox,
    DocumentPrediction,
    EvidenceReference,
    FieldCandidate,
    FieldPrediction,
    ModelMetadata,
    ReviewSignal,
)
from greenledger.benchmark.evaluator import bbox_iou, evaluate_predictions


def field(name, status, value=None, *, unit=None, evidence=(), candidate_state=None):
    candidates = ()
    if value is not None or unit is not None or evidence:
        candidates = (FieldCandidate(
            raw_value=value,
            normalized_value=value,
            raw_unit=unit,
            normalized_unit=unit,
            evidence=evidence,
        ),)
    return FieldPrediction(
        field_name=name,
        evidence_status=status,
        candidate_state=candidate_state or ("SINGLE_CANDIDATE" if candidates else "NO_CANDIDATE"),
        candidates=candidates,
    )


class BenchmarkEvaluatorTests(unittest.TestCase):
    def test_bbox_iou(self):
        self.assertAlmostEqual(
            bbox_iou(
                {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
                {"x": 0.2, "y": 0.1, "width": 0.2, "height": 0.2},
            ),
            1 / 3,
        )

    def test_evaluator_reports_field_grounding_missing_ambiguity_readiness_and_safety(self):
        annotations = [
            {
                "document_id": "R",
                "domain": "electricity",
                "activity_id": "purchased_electricity",
                "evidence_state": "ready",
                "fields": [{
                    "field_name": "quantity", "presence_status": "present",
                    "raw_value": "100", "raw_unit": "kWh", "normalized_value": "100",
                    "evidence": [{
                        "text": "Energy use: 100 kWh", "page_number": 1,
                        "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.1},
                    }],
                }],
            },
            {
                "document_id": "I",
                "domain": "electricity",
                "activity_id": "purchased_electricity",
                "evidence_state": "incomplete",
                "fields": [{
                    "field_name": "quantity", "presence_status": "not_present",
                    "raw_value": None, "raw_unit": None, "normalized_value": None,
                    "evidence": [],
                }],
            },
            {
                "document_id": "A",
                "domain": "electricity",
                "activity_id": "purchased_electricity",
                "evidence_state": "ambiguous",
                "fields": [{
                    "field_name": "quantity", "presence_status": "ambiguous",
                    "raw_value": None, "raw_unit": None, "normalized_value": None,
                    "candidates": [
                        {"raw_value": "100", "raw_unit": "kWh"},
                        {"raw_value": "120", "raw_unit": "kWh"},
                    ],
                    "evidence": [{"text": "Two readings: 100 kWh and 120 kWh", "page_number": 1}],
                }],
            },
        ]
        predictions = [
            DocumentPrediction(
                "R",
                (field("quantity", "PRESENT", "100", unit="kWh", evidence=(
                    EvidenceReference("Energy use: 100 kWh", 1, BoundingBox(0.1, 0.1, 0.2, 0.1)),
                )),),
                accounting_readiness="READY",
                model_metadata=ModelMetadata("unit-test"),
            ),
            DocumentPrediction(
                "I",
                (field("quantity", "MISSING"),),
                accounting_readiness="READY",
                review_signal=ReviewSignal(explicit_missing_evidence_signal=True),
                model_metadata=ModelMetadata("unit-test"),
            ),
            DocumentPrediction(
                "A",
                (field("quantity", "PRESENT", "100", unit="kWh"),),
                accounting_readiness="READY",
                review_signal=ReviewSignal(explicit_ambiguity_signal=False),
                model_metadata=ModelMetadata("unit-test"),
            ),
        ]
        result = evaluate_predictions(predictions, annotations)
        metrics = result["metrics"]
        self.assertEqual(metrics["carbon_critical_extraction"]["aggregate"]["true_positive"], 1)
        self.assertEqual(metrics["carbon_critical_extraction"]["aggregate"]["false_positive"], 1)
        self.assertEqual(metrics["evidence_grounding"]["unsupported_values"], 0)
        self.assertEqual(metrics["evidence_grounding"]["evidence_text_correctness"], 1.0)
        self.assertEqual(metrics["evidence_grounding"]["page_correctness"], 1.0)
        self.assertAlmostEqual(metrics["evidence_grounding"]["mean_bbox_iou"], 1.0)
        self.assertEqual(metrics["missing_evidence_detection"]["metrics"]["true_positive"], 1)
        self.assertEqual(metrics["missing_evidence_detection"]["false_completion_count"], 1)
        self.assertEqual(metrics["ambiguity_detection"]["metrics"]["false_negative"], 1)
        self.assertEqual(metrics["ambiguity_detection"]["false_resolution_count"], 1)
        self.assertEqual(metrics["ambiguity_detection"]["unflagged_single_scalar_documents"], 1)
        self.assertEqual(metrics["accounting_readiness"]["confusion_matrix_rows_true_columns_predicted"]["ambiguous"]["ready"], 1)
        self.assertEqual(len(result["per_document"]), 3)

    def test_ambiguous_candidates_are_not_collapsed_to_one_normalized_prediction(self):
        annotations = [{
            "document_id": "A",
            "domain": "electricity",
            "activity_id": "purchased_electricity",
            "evidence_state": "ambiguous",
            "fields": [{
                "field_name": "quantity", "presence_status": "ambiguous",
                "normalized_value": None, "evidence": [],
            }],
        }]
        predictions = [DocumentPrediction(
            "A",
            (FieldPrediction(
                "quantity", "AMBIGUOUS", "MULTIPLE_CANDIDATES",
                (
                    FieldCandidate("100", "100", "kWh", "kWh"),
                    FieldCandidate("120", "120", "kWh", "kWh"),
                ),
            ),),
            accounting_readiness="AMBIGUOUS",
            model_metadata=ModelMetadata("unit-test"),
        )]
        result = evaluate_predictions(predictions, annotations)
        self.assertEqual(result["metrics"]["carbon_critical_extraction"]["aggregate"]["false_positive"], 0)
        self.assertEqual(result["metrics"]["evidence_grounding"]["scalar_candidates_in_critical_fields"], 2)
        self.assertEqual(result["metrics"]["ambiguity_detection"]["metrics"]["true_positive"], 1)
        self.assertEqual(result["metrics"]["ambiguity_detection"]["false_resolution_count"], 0)

    def test_unknown_and_duplicate_document_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "IDs differ"):
            evaluate_predictions(
                [DocumentPrediction("P", (), model_metadata=ModelMetadata("unit-test"))],
                [{"document_id": "G", "domain": "electricity", "evidence_state": "ready", "fields": []}],
            )

    def test_candidate_predicted_domain_has_separate_classification_metrics(self):
        prediction = DocumentPrediction(
            "D",
            (field("document_domain", "PRESENT", "freight"),),
            model_metadata=ModelMetadata("unit-test"),
        )
        annotation = {
            "document_id": "D",
            "domain": "freight",
            "activity_id": "selected_transport",
            "evidence_state": "ready",
            "fields": [],
        }
        result = evaluate_predictions([prediction], [annotation])
        metrics = result["metrics"]["document_domain_classification"]
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["per_class"]["freight"]["true_positive"], 1)
        self.assertEqual(metrics["macro_f1"], 0.2)
        self.assertEqual(result["per_document"][0]["predicted_domain"], "freight")


if __name__ == "__main__":
    unittest.main()
