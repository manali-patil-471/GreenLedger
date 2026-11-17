# Qwen3-VL Candidate Adapter — 2026-11-18

## Status

The benchmark-only adapter and fixed 10-document smoke runner are implemented. Focused unit tests validate the input boundary, PDF page rendering, output parsing, and contract conformance. **The 10-document smoke run has not been executed.** No full-pilot benchmark, scoring, model comparison, or annotation read was performed for this implementation.

## Candidate and runtime

- Candidate: `Qwen/Qwen3-VL-4B-Instruct-GGUF:Q4_K_M`
- Runtime: the existing llama.cpp unified CLI, invoked as `llama cli`
- Language GGUF: `Qwen3VL-4B-Instruct-Q4_K_M.gguf`
- Vision projector: `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf`
- Required SHA256 values are checked by the smoke runner before inference:
  - model: `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a`
  - mmproj: `30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d`
- Model files are local inputs. The runner has no Hugging Face reference or download path and will not download weights.
- llama.cpp is invoked with `--offline` and explicit local `-m`/`--mmproj` paths.
- The configured command uses `-ngl 99` and `--mmproj-offload` for GPU offload on the Colab T4, with temperature 0 and seed 1 for repeatable decoding. The CLI's documented `--image` argument accepts comma-separated page images; its `--version`, `--simple-io`, `--mmproj`, `--mmproj-offload`, GPU-layer, temperature, seed, and offline options are documented by the [llama.cpp CLI README](https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md). Qwen's official [GGUF model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF) documents the Q4_K_M llama.cpp route and separate vision-projector component.

## Candidate-only interface

`Qwen3VLCandidateAdapter.predict()` accepts exactly `CandidateDocumentInput`, whose fields are only:

- opaque `candidate_id` for returning the prediction ID;
- `document_bytes`;
- `media_type`.

The adapter has no parameter for an annotation, manifest row, path, filename, domain label, evidence state, expected value, layout family, split, or expected accounting result. The opaque ID is not placed in the model prompt or command line. Inputs are written to temporary generic names such as `candidate-input.jpg` and `candidate-input-page-0001.png`.

The smoke runner uses the frozen manifest only outside the candidate to select a balanced 10-document set and create a separate candidate-ID mapping. It gives each prediction call only an opaque ID, document bytes, and MIME type. It does not open `annotations.jsonl`, import the evaluator, or score predictions. Candidate predictions are generated and written without loading annotations.

The candidate predicts `document_domain` from the page images. The manifest domain and evidence-state labels are used only by the outer selector and appear only in the external `.selection.json` sidecar written after prediction generation. They never enter the adapter input or prompt.

## PDF and image handling

- PNG and JPEG inputs are written byte-for-byte to a generic image path and passed as images.
- PDFs are rendered page-by-page through `pypdfium2` at a fixed scale of 2.5. Every page is sent in source order in one comma-separated `--image` argument. Page numbering in the output contract is one-based.
- No OCR runs before Qwen. No annotation-derived crops or page-selection decisions are used.
- The prompt asks for exact visible evidence text and page. No bounding boxes or confidence values are requested or fabricated. Contract confidence remains `null` and marked uncalibrated.

## Prompt and output mapping

The fixed prompt requests document type/domain and visible fields in the existing `GREENLEDGER_DOCUMENT_PREDICTION_SCHEMA_v1` contract. It asks the model to preserve `PRESENT`, `MISSING`, `INSUFFICIENT`, `AMBIGUOUS`, or `UNDETERMINED` states, to keep conflicting candidates separate, and to abstain where evidence is unclear. It explicitly forbids Scope/category, factors, accounting boundaries, unit conversion without visible support, and CO2/CO2e calculations.

The adapter filters Qwen output to existing contract field names; it does not extend the contract. Evidence text is copied as returned. Page references outside the rendered page range become `null`, not a guessed page. Bboxes are accepted only if Qwen returns valid normalized coordinates; the prompt does not ask for them. Cylinder/refill counts reported as `net_lpg_mass` are retained only as `INSUFFICIENT` evidence and never converted to a mass.

`accounting_readiness` is the model's evidence-completeness classification for benchmark comparison only. Human confirmation remains required. This is not a production accounting decision and does not trigger the deterministic accounting engine.

## Smoke set

`scripts/run_qwen3vl_smoke_10.py` selects exactly 10 records deterministically from accessible manifest metadata, covering all five domains, all three evidence states, at least one multipage PDF, and at least one PNG/JPEG. The mapping from `qwen-smoke-0001` etc. to source document ID/domain/state is written separately to `<output>.selection.json`; the candidate never receives it.

The runner writes schema-validated prediction JSON and a separate selection-map JSON. It does not calculate metrics or open annotations. It verifies local GGUF filenames and SHA256 values and calls `llama --version` before candidate inference. Output paths must remain outside the frozen pilot directory.

## Colab command (not run here)

From the GreenLedger repository root in the Colab runtime where the already-validated llama.cpp binary and model files are available:

```bash
LLAMA="$HOME/.llama-app/llama"
MODEL_PATH="$(find -L "$HOME/.cache" "$HOME/.llama-app" -type f -name 'Qwen3VL-4B-Instruct-Q4_K_M.gguf' -print -quit 2>/dev/null)"
MMPROJ_PATH="$(find -L "$HOME/.cache" "$HOME/.llama-app" -type f -name 'mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf' -print -quit 2>/dev/null)"
test -x "$LLAMA" && test -n "$MODEL_PATH" && test -n "$MMPROJ_PATH" || { echo 'Existing llama/model files not found'; exit 1; }
python scripts/run_qwen3vl_smoke_10.py \
  --llama-binary "$LLAMA" \
  --model "$MODEL_PATH" \
  --mmproj "$MMPROJ_PATH" \
  --pilot-dir data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15 \
  --output /content/qwen3vl_smoke_10_predictions_v1.json \
  --gpu-layers 99
```

The runner checks the CLI version and exact cached file hashes before inference. If the weights cannot be found or the hash differs, it stops without downloading or substituting anything. The Colab runtime must already have `pypdfium2` available for PDF inputs; this task does not install packages.

## Files

- `greenledger/benchmark/qwen3vl_candidate_adapter.py` — candidate-only adapter, fixed prompt, PDF rendering, output parser, schema mapping.
- `scripts/run_qwen3vl_smoke_10.py` — deterministic smoke-set selector and unscored 10-document prediction runner.
- `tests/test_qwen3vl_candidate_adapter.py` — focused input-isolation, rendering, parsing, and schema tests.

## Limitations

- Qwen output evidence is text/page only unless the model voluntarily emits a valid normalized bbox; bbox quality is not established by these unit tests.
- Confidence is intentionally uncalibrated and remains null.
- The adapter maps the model's predicted readiness label; it does not implement a separate deterministic readiness gate.
- The 10-document smoke run remains to be executed in Colab. This change establishes an adapter and protocol, not model accuracy, extraction quality, superiority over Candidate A, or production suitability.
