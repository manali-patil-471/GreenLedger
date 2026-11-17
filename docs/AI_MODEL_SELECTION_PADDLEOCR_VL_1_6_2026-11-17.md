# PaddleOCR-VL 1.6 Evaluation Attempt — 2026-11-17

## 1. Outcome

**Status: BLOCKED before document inference.** The isolated runtime and candidate-only adapter were prepared, but PaddleOCR-VL did not initialize successfully on this Windows CPU machine. The candidate produced **0 of 120 predictions**. The smoke documents were never passed to the model. The PaddleOCR-VL runner did not deserialize the frozen annotations, and there are no PaddleOCR-VL benchmark metrics. Missing metrics below mean **not measured**, not zero.

This does not establish that PaddleOCR-VL performs well or poorly at OCR or carbon-field extraction. It establishes that this installation could not reach inference on the available machine.

## 2. Candidate and runtime

The requested official model was `PaddlePaddle/PaddleOCR-VL-1.6`, through the PaddleOCR `pipeline_version="v1.6"` full document pipeline. The full pipeline combines layout analysis and VLM recognition. The configured inference engine was `transformers`; both layout analysis and VLM inference were requested through that engine. The downloaded model files identify the pipeline's VLM component as `PaddleOCR-VL-1.6-0.9B`.

The official PaddleOCR documentation lists the Transformers engine for x64 CPU and says the full pipeline uses Transformers for both layout and VLM stages. The current inference-engine guide specifies Transformers `>=5.10.0`. This environment used Transformers 5.10.4. [PaddleOCR-VL v3.6 usage guide](https://www.paddleocr.ai/v3.6.0/en/version3.x/pipeline_usage/PaddleOCR-VL.html), [PaddleOCR inference-engine requirements](https://www.paddleocr.ai/latest/en/version3.x/inference_deployment/local_inference/inference_engine.html)

Dedicated environment: `.venv-paddleocr-vl`, Python 3.12.3, CPU-only. Relevant final package versions:

| Package | Version |
|---|---:|
| PaddleOCR | 3.6.0 |
| PaddleX | 3.6.1 |
| PaddlePaddle | 3.2.1 CPU |
| Transformers | 5.10.4 |
| PyTorch | 2.10.0+cpu |
| torchvision | 0.25.0+cpu |
| tokenizers | 0.22.2 |
| huggingface-hub | 1.33.0 |
| protobuf | 7.36.1 |
| NumPy | 2.3.5 |
| Pillow | 12.1.0 |
| pypdfium2 | 5.15.2 |
| safetensors | 0.7.0 |
| psutil | 7.2.2 |

`pip check` passed. CPU PyTorch, Paddle, `AutoImageProcessor`, and `PaddleOCRVL` imports passed after the final package update. Hardware: Intel Core i5-1235U, 10 physical cores / 12 logical processors, 15.7 GiB RAM, Intel Iris Xe integrated graphics (not used), and no CUDA. About 4.1 GiB RAM was available before the final model-load attempt; memory exhaustion was not established as the cause of the crash.

### Model files downloaded

| Cached file | Bytes | SHA256 |
|---|---:|---|
| `PaddleOCR-VL-1.6/model.safetensors` | 1,917,255,968 | `85a479d506a11e724e7285d395c551be69f41dbc16b6342d3cacfb189aed71db` |
| `PP-DocLayoutV3_safetensors/model.safetensors` | 133,270,468 | `5ea422c6cc5fe759a47e1357c35639b58173508e025a3131cbe4b6ac59e2b85e` |
| `PP-DocLayoutV3/inference.pdiparams` | 130,806,572 | `70bd316b0582769ec968829fd1feb1a6a58b7c941b938327e551b6b12b45c137` |

The model files were downloaded, but the PaddleOCR-VL model was **not successfully initialized**. The local Hugging Face tree metadata identifies model-repository revision `132c45f52c0a26ed5a6b2f6bd8e3985794cc27dd`; the model-file SHA256 is also recorded above.

## 3. Runtime attempts and stopping point

1. **Paddle engine:** after correcting a Protobuf version mismatch, Windows recorded an Application Error 1000 access violation (`0xc0000005`) in Paddle's `phi.dll` at 00:42:35 local time. No prediction was produced.
2. **Transformers engine with PyTorch 2.6.0+cpu:** the import failed because Transformers 5.10.4 referenced `torch.float8_e8m0fnu`, absent from that PyTorch version. This was an environment compatibility issue, corrected only inside `.venv-paddleocr-vl` by installing the official PyTorch 2.10 CPU and torchvision 0.25 CPU wheels. The official PyTorch version table lists these CPU wheels. [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/)
3. **Transformers engine with PyTorch 2.10.0+cpu:** PP-DocLayoutV3 loaded. During PaddleOCR-VL-1.6 model initialization, Windows recorded an Application Error 1000 access violation (`0xc0000005`) in `torch_cpu.dll` at 01:03:06 local time. The process exited before the first input document was passed to the model.

Both native backend paths therefore failed in native inference libraries on this machine. I stopped after the recorded initialization crash; I did not change model settings or retry for a preferred result.

## 4. Candidate-only interface and data protection

The benchmark-only adapter accepts only `CandidateDocumentInput(candidate_id, document_bytes, media_type)`. It passes document bytes through a temporary generic name, `candidate-input.<extension>`. It does not receive a source filename/path, annotation object, manifest domain, expected value, missing/ambiguous label, or expected result. Domain is candidate-predicted from parsed document content when inference is available. The adapter maps output to the existing common contract and emits no factor, Scope/category, accounting boundary, or emissions result.

The runner verified the frozen marker and manifest before inference and was structured to deserialize annotations only after all 120 candidate predictions. In these attempts it generated zero predictions and deserialized no annotations. Afterward, the full repository regression suite ran its existing Current Pipeline baseline-reproduction test, which deserializes the frozen pilot annotations to verify that previously saved predictions reproduce their saved metrics. Those annotations were not passed to PaddleOCR-VL or used in its candidate inference. No old quarantined test split was accessed.

Because inference never began, there was no document preprocessing, OCR output, page output, evidence mapping, or smoke result to evaluate. OCR CER/WER and downstream metrics are unavailable. The pilot contains field/evidence annotations rather than complete page transcription ground truth, so CER/WER would in any case require a separately justified transcript reference.

## 5. Three-way comparison

Current-pipeline and Candidate A figures below come from the saved candidate-only pilot results. PaddleOCR-VL values are unavailable because the model did not initialize.

| Metric | Current pipeline | Candidate A | PaddleOCR-VL 1.6 |
|---|---:|---:|---:|
| Carbon-critical precision | 0.9328 | 0.8222 | Not measured |
| Carbon-critical recall | 0.1801 | 0.0533 | Not measured |
| Carbon-critical F1 | 0.3019 | 0.1001 | Not measured |
| Unsupported-value rate | 0.0000 | 0.2738 | Not measured |
| Evidence-text coverage | 0.5620 | 1.0000 | Not measured |
| Missing-evidence F1 | 0.5041 | 0.4810 | Not measured |
| False-completion rate | 0.0000 | 0.0000 | Not measured |
| Ambiguity F1 | 0.2609 | 0.3462 | Not measured |
| False-resolution rate | 0.0000 | 0.0000 | Not measured |
| Readiness macro-F1 | 0.0000 | 0.0000 | Not measured |
| Domain accuracy | 0.5000 | 0.4583 | Not measured |
| Domain macro-F1 | 0.6000 | 0.5733 | Not measured |
| Mean latency/document | Not recorded in saved result | 9.351 s | Not measured |

The current pipeline's and Candidate A's page/bounding-box correctness were not evaluable in their saved artifacts (`page_evaluable=0`, `bbox_iou_evaluable=0`). No corresponding PaddleOCR-VL grounding result exists.

### Per-domain carbon-critical F1

| Domain | Current pipeline | Candidate A | PaddleOCR-VL 1.6 |
|---|---:|---:|---:|
| Electricity | 0.5467 | 0.1983 | Not measured |
| Diesel | 0.6216 | 0.2645 | Not measured |
| LPG | 0.5547 | 0.1731 | Not measured |
| Materials | 0.0000 | 0.0000 | Not measured |
| Freight | 0.0000 | 0.0000 | Not measured |

### Selected per-field F1

| Field | Current pipeline | Candidate A | PaddleOCR-VL 1.6 |
|---|---:|---:|---:|
| Activity description | 0.6667 | 0.4314 | Not measured |
| Quantity | 0.5833 | 0.0833 | Not measured |
| Unit | 0.6667 | 0.0526 | Not measured |
| Billing period | 0.0000 | 0.0000 | Not measured |
| Vehicle reference | 0.0000 | 0.0000 | Not measured |
| LPG net mass | 0.7778 | 0.0000 | Not measured |
| Material identity | 0.0000 | 0.0000 | Not measured |
| Shipment mass | 0.0000 | 0.0000 | Not measured |
| Distance | 0.0000 | 0.0000 | Not measured |
| Transport vehicle class | 0.0000 | 0.0000 | Not measured |

## 6. Tests and integrity

- PaddleOCR-VL adapter tests: **9 passed**.
- Full test suite: **108 passed** (`py -3.12 -m unittest discover -s tests -v`).
- Compile check: **passed** (`py -3.12 -m compileall -q greenledger scripts tests app.py`).
- Isolated environment dependency check: **passed** (`.venv-paddleocr-vl/Scripts/python.exe -m pip check`).
- Candidate A model artifact remains at its recorded SHA256: `6b7cecb47346fa8582eb4dc3963a746bf932c06874caa784f98bcd6a53d205ab`.
- Frozen pilot remains `FROZEN`, 120 documents / 126 hash-covered files. `FROZEN.json` SHA256: `e3fcac4917e621a860b29e8924b28f2bd9f764cee3e13b6aaadaa91d251d7c0a`; manifest SHA256: `00d097c8893875c0f1db376698c71b03819750b8184ceedae87a0598ea15377d`; annotation SHA256: `4d9fd0cbeeb0a2627589eb60efd10c2d39af6f501cda50218a487a7f32ec5e8a`.
- Frozen documents, annotations, manifest, and marker were not modified. Existing Candidate A/current-pipeline results, RapidOCR environment, OCR implementation, and production accounting were not modified.

## 7. Interpretation and decision

1. Did PaddleOCR-VL improve extraction over the current pipeline? **Unknown; no predictions.**
2. Did it improve over Candidate A? **Unknown; no predictions.**
3. Did it improve missing/ambiguity detection or reduce unsupported values? **Unknown; no predictions.**
4. Can it handle materials/freight or produce grounded evidence/readiness? **Not evaluated.**
5. Is CPU cost acceptable? **Not measured.** Initialization was unstable before latency could be measured.
6. Is it the strongest candidate? **No evidence supports that claim.**

This remains a synthetic 120-document evaluation only; it provides no evidence about real-SME performance.

**One next experiment:** run the unchanged PaddleOCR-VL 1.6 adapter and frozen protocol on a separate supported x64 Linux or CUDA-capable machine, first with the same small runtime feasibility gate. Do not proceed to Qwen until this candidate can complete inference and produce a scored result.

## 8. Artifacts

- Machine-readable blocked attempt: `data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_paddleocr_vl_16_blocked_runtime_v1_2026-11-17.json`
- Preserved Protobuf-blocked attempt: `data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_paddleocr_vl_16_native_protobuf_blocked_2026-11-17.json`
- Preserved Transformers/PyTorch-2.6 import-blocked attempt: `data/benchmark/evaluations/greenledger_unseen_structure_pilot_120_paddleocr_vl_16_transformers_torch260_import_blocked_2026-11-17.json`
- Downloaded weights/cache: `models/paddleocr_vl_16_cache/`
- Dedicated runtime: `.venv-paddleocr-vl/`
