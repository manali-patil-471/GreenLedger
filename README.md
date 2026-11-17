# GreenLedger

GreenLedger is a carbon-accounting research platform for SMEs. Its frozen v1 activity scope is electricity, diesel, LPG, selected purchased materials, and selected transport/freight.

## Run the local baseline

Use Python 3.8 or newer. No extra packages are required:

```powershell
py -3.12 app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. Press **Ctrl+C** in the terminal to stop the server.

This application stage provides manual field entry, normalization using documented rules, context-aware scope mapping, deterministic calculation, and a traceable result. It can also show a local RapidOCR transcript and unconfirmed rule-based field suggestions when run from the isolated OCR environment below; no AI extraction is active. It has a separate CO₂-only result path for the selected CEA V22 India location-based electricity factor for FY2025-26; that factor cannot produce CO₂e. Conditional CO₂e paths are available for IPCC 1.A.4.a commercial/institutional stationary LPG, India road/mobile TTW diesel, three CPWD 2024 material reference classes, and seven India road-freight WTW vehicle classes when their required context and activity units are confirmed. See [the local baseline guide](docs/LOCAL_BASELINE_APP.md) and [factor decisions](docs/GREENLEDGER_FACTOR_DECISIONS.md) for applicability limits and source caveats.

## Validate the factor catalogue

```powershell
py -3.12 scripts/validate_factor_catalogue.py
```

## Run the application checks

```powershell
py -3.12 -m unittest discover -s tests -v
```

## Evaluate OCR candidates

```powershell
py -3.12 -m venv .venv-ocr-eval
.\.venv-ocr-eval\Scripts\python.exe -m pip install -r requirements-ocr-eval.txt
py -3.12 scripts/setup_ocr_eval.py
.\.venv-ocr-eval\Scripts\python.exe scripts/evaluate_ocr.py --engine all --split validation
```

The isolated environment keeps OCR dependencies separate from the standard-library app. Run the app with `.venv-ocr-eval\Scripts\python.exe app.py` to show a transient OCR transcript for supported uploads. Three OCR candidates were compared on the 65-record synthetic validation split; RapidOCR remains the provisional transcription baseline. See [the measured comparison](docs/OCR_CANDIDATE_COMPARISON_2026-09-24.md). This evaluates OCR text, not AI field extraction or carbon-accounting quality. The original 130-record test split is quarantined after annotation exposure; see [the quarantine record](docs/TEST_SPLIT_QUARANTINE_2026-11-10.md).

To reproduce the Florence-2 OCR candidate measurement in a separate CPU-only environment:

```powershell
py -3.12 -m venv .venv-field-eval
.\.venv-field-eval\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-field-model-eval.lock.txt
.\.venv-field-eval\Scripts\python.exe scripts/evaluate_florence_ocr.py --split validation --store-predictions --output data/benchmark/evaluations/ocr/florence2_ocr_validation_2026-09-24_with_predictions.json
```

This downloads the pinned model checkpoint the first time. Florence-2 is an evaluated research candidate only; the app continues to use RapidOCR.

The rule-only field baseline is evaluated separately on the same synthetic validation split. See [its measured results and limitations](docs/RULE_FIELD_EXTRACTION_BASELINE_2026-09-24.md). The suggestions do not calculate emissions and require human confirmation.

## Train and compare the experimental field-extraction candidate

The application does **not** use this candidate. Its supervised line-role model is a separate research experiment trained on the 325 training records and compared with rules on the 65-record synthetic validation set. It requires the CPU PyTorch environment already used for Florence-2 evaluation:

```powershell
.\.venv-field-eval\Scripts\python.exe scripts/train_ai_field_extractor.py
.\.venv-field-eval\Scripts\python.exe scripts/evaluate_ai_field_extractor.py
```

The scripts do not load test annotations. The original 130-record test split is quarantined. See [the experiment report](docs/AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md) for measured comparison, field-label coverage, and limitations. AI suggestions always require human confirmation; no confidence is calibrated and the candidate cannot choose factors or calculate CO₂e.
