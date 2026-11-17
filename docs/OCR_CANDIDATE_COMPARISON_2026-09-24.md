# OCR Candidate Comparison — 2026-09-24

## Status

**Measured on the synthetic validation split.** RapidOCR remains the provisional OCR baseline after a third, pretrained Florence-2 OCR candidate was evaluated. Florence-2 is not selected for the current OCR pipeline. This is not a final document-understanding model selection and does not establish performance on real SME documents.

## Protocol

- Dataset: GreenLedger synthetic release `greenledger_synthetic_v0_1_1_partial`, held-out validation split; 65 checksum-verified documents (25 electricity, 20 diesel, 20 LPG); all documents were scored by all three candidates, with zero engine failures.
- Reference: the existing GreenLedger transcription annotations. Comparison normalizes Unicode NFKC, case, and whitespace; punctuation is retained.
- Metrics: pooled character error rate (CER), pooled word error rate (WER), normalized exact-document match, mean/p95 per-document latency, and deterministic document-bootstrap 95% intervals (1,000 resamples; descriptive for this synthetic sample).
- Input: the original image for each candidate. RapidOCR and Tesseract used their recorded English configurations; Florence-2 used its official processor and documented `<OCR>` task. No extra preprocessing was added. The test split was not used.
- Runtime: Windows 11, Python 3.12.3, CPU-only (no visible GPU). Peak memory was not measured.

## Results

| Candidate | CER (95% bootstrap interval) | WER (95% bootstrap interval) | Exact transcription | Mean latency | P95 latency | Total elapsed |
|---|---:|---:|---:|---:|---:|---:|
| RapidOCR 3.9.2 + ONNX Runtime 1.30.0 | 0.231% (0.094–0.456%) | 1.126% (0.683–1.629%) | 63.1% (41/65) | 4.986 s | 7.161 s | 324.9 s |
| Tesseract 5.5.2 through tesserocr 2.10.0 | 1.211% (0.841–1.656%) | 6.082% (5.593–6.541%) | 0.0% (0/65) | 0.357 s | 0.492 s | 23.3 s |
| Florence-2-base-ft (pinned revision; CPU) | 6.392% (6.046–6.749%) | 46.314% (45.831–46.817%) | 0.0% (0/65) | 9.750 s | 11.221 s | 633.8 s |

On this split RapidOCR had about 81% fewer character and word errors, and Tesseract was about 14 times faster per document. RapidOCR's measured CER and WER intervals do not overlap Tesseract's intervals. These are independent descriptive bootstrap intervals, not a paired significance test.

Florence-2 had about 27.7 times RapidOCR's CER and 41.1 times its WER, with roughly twice the per-document latency. Its measured model initialization was 765.8 seconds in this run; that one-time measurement includes loading the local checkpoint and runtime but is not part of per-document latency. Peak memory was not measured.

## Configurations and provenance

- **RapidOCR:** package 3.9.2; PP-OCRv6 small detector and recognizer, PP-OCRv4 mobile orientation classifier; English; ONNX Runtime CPU with intra-op threads 4 and inter-op threads 1. Exact model asset hashes and run metrics are in `data/benchmark/evaluations/ocr/rapidocr_3_9_2_validation_2026-09-24.json`. The official usage guide describes the RapidOCR entry point and its default models: <https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/>.
- **Tesseract:** tesserocr 2.10.0 Windows CPython 3.12 x64 wheel containing Tesseract 5.5.2; LSTM-only OCR, page segmentation mode 3, English `tessdata_fast` model. Wheel SHA256: `e05d41a2b0e6f38f3a5195d05a73674d72152a775d1b8ebe481ca9306f94d27a`. Model source commit: `87416418657359cb625c412a48b6e1d6d41c29bd`; model SHA256: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. Run details are in `data/benchmark/evaluations/ocr/tesserocr_2_10_0_tesseract_5_5_2_validation_2026-09-24.json`.
- **Florence-2:** Microsoft `Florence-2-base-ft`, 0.23B parameters, MIT license, pinned revision `f6c1a25888ffc1d945ee8a1a77ac833c7303d46e`; official `<OCR>` task, CPU float32, 4 Torch threads, 3-beam deterministic generation. Model weights SHA256: `58757d657ff44051314c8030b68e04cb1bb618ca9a4885418f111f6fb708185a`. The official model card lists its OCR task and model details: <https://huggingface.co/microsoft/Florence-2-base-ft/tree/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e>. Exact runtime, prompt, generation settings, and source-file hashes are in `data/benchmark/evaluations/ocr/florence2_ocr_validation_2026-09-24_with_predictions.json`.
- Both dependencies and model files are kept in `.venv-ocr-eval`; the standard-library application environment is not changed. The pinned English Tesseract model is obtained by `scripts/setup_ocr_eval.py` and hash-checked before use.
- Florence-2 dependencies are isolated in `.venv-field-eval`, pinned in `requirements-field-model-eval.lock.txt`, and separate from the app runtime. Its official model code is revision-pinned and the loaded weight and code hashes are recorded.

## Interpretation and limits

- An earlier one-document Florence field-prompt smoke used `<DocVQA>`, which is not a documented task for this model. Its harness now exits with an invalid-experiment notice; its archived smoke records are labeled `INVALID_EXPERIMENT` and are excluded from all conclusions. The valid Florence measurement here uses the documented `<OCR>` task.

- Use RapidOCR as the **provisional OCR transcription baseline** for the next workflow stage: it was substantially more accurate on this validation slice, while its roughly five-second mean runtime per synthetic document is slower and should be weighed against the intended batch size.
- Do not use Florence-2 OCR in the current pipeline: it was slower and materially less accurate than both existing engines on all 65 synthetic validation records. This result is specific to the evaluated model revision, prompt, runtime, and layout family.
- Do not call it the final GreenLedger AI/model. This experiment measures text transcription only—not document-type classification, carbon-field F1, numeric extraction, normalization, scope/category, factor retrieval, CO2e, confidence, or review decisions.
- These are synthetic documents, not real SME evidence. The validation slice contains only electricity, diesel, and LPG, and all 65 records share layout family `layout_F`; the result does not demonstrate generalization across layout families or the frozen material/transport categories.
- Feeding Florence-2's flattened OCR text to the current line-based rules produced 47/65 document-type/activity-normalization matches, zero exact quantities or normalized units, and 4/4 review recall with only 4/65 review precision. This is a downstream integration check, not a Florence field-extraction score; the transcript format loses line breaks expected by the current rule parser. See `data/benchmark/evaluations/fields/florence2_rules_v1_validation_2026-09-24.json`.
- This comparison predates the 2026-11-10 annotation-exposure audit. The 130-record test split is now quarantined; it must not be used for a final score. A real-SME validation set and peak-memory measurement are still outstanding. An initial supervised AI carbon-field candidate has since been compared with rules on the same synthetic validation OCR transcripts; broader layout/VLM model comparison remains open. See `docs/AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md` and `docs/TEST_SPLIT_QUARANTINE_2026-11-10.md`.
