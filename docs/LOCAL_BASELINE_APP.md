# GreenLedger local application baseline

**Status:** Runnable manual-accounting baseline with optional provisional OCR transcription and deterministic rule suggestions. An experimental supervised field extractor exists separately but is not integrated into this application.

## Start it

Requirements: Python 3.8 or later. The application uses only the Python standard library.

From the repository folder in PowerShell:

```powershell
py -3.12 app.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop it with Ctrl+C in the server terminal.

The page is available only while the local server process is running. Start it again with the command above after the process or computer stops.

To use the provisional local OCR transcript, run the app inside the isolated OCR environment instead:

```powershell
.\.venv-ocr-eval\Scripts\python.exe app.py
```

If the OCR environment has not been set up, follow the README steps. The first OCR initialization may download RapidOCR model assets; the application checks their recorded hashes before use.

## What works now

- Local form for the five frozen v1 activity IDs.
- Optional PDF/image upload, limited to 8 MB and held in request memory; files are not saved.
- In the OCR environment, the **Read OCR transcript** button previews local RapidOCR text and conservative rule-based field suggestions before manual entry. Suggestions include extracted/missing/ambiguous/unresolved states; these are evidence states, not calibrated confidence probabilities. The **Copy suggestions into fields** action leaves the confirmation box unchecked. Supported images and PDFs are processed in memory; only the first three PDF/TIFF pages are read, and each image page is limited to 20 megapixels. Submitting the accounting trace reruns OCR so the returned trace records the server-produced transcript.
- The displayed transcript and source-file SHA256 are included in the transient JSON trace. Neither the upload nor the result is written to a database or disk.
- Manual entry for activity, quantity/unit, date, supplier, and accounting context, including electricity grid/period, diesel road context, material identity, and freight vehicle class/mass/distance.
- Activity alias and unit normalization, with quantity conversion only when a rule is present in the activity definitions. This includes exact SI scaling for electricity MWh/kWh, diesel mL/L/kL, and material g/kg/tonne.
- Context-aware scope/category mapping for electricity, diesel, LPG, the three selected purchased-material identities, and the existing freight Category 4/9 business-flow choices.
- CO₂e factor retrieval only from catalogue rows marked as eligible verified CO₂e factors, with activity, unit, scope/category, structured applicability, exact material/vehicle class, and required context matching; CO₂-only rows remain excluded. The engine supports conditional IPCC 1.A.4.a LPG, India road/mobile diesel TTW, three CPWD material references, and seven India road-freight WTW vehicle classes.
- A separate deterministic CO₂-only path for the selected CEA V22 India location-based electricity row for FY2025-26, with a JSON calculation/provenance trace.
- Review gate: CO₂e is withheld until the entered fields are confirmed. Missing context, undocumented conversion, and missing factors return a review/unresolved result.

## Current limitations

- Without the isolated OCR environment, uploaded files are not OCRed and no document-based field suggestions are produced; values must be entered manually. With the OCR environment, the deterministic rule baseline can suggest document type and carbon fields, but these remain unconfirmed and require human review. The separately trained AI field-extraction candidate is not active in the UI or accounting pipeline; see `AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`.
- No calibrated carbon-field confidence score, database, record history, or production authentication is implemented.
- LPG, road/mobile diesel, selected materials, and road freight are eligible only through their narrow, context-gated catalogue rows. The LPG derivation is 2.99230679 kgCO₂e/kg; the India road-diesel source reports 2.675 kgCO₂e/L TTW with a documented source-method caveat. CPWD source rows include specific provenance remarks (PPC 30% fly ash and supplier EPD citations); the selected GreenLedger entries are generic/reference uses and not supplier-specific matching. Freight factors are WTW and distinct from road-diesel TTW. Other diesel/LPG contexts, materials, and modes remain unresolved.
- The UI collects the applicable context fields and retains mandatory human confirmation. OCR suggestions remain advisory; they do not fill or confirm the new accounting context.
- The electricity CO₂ path returns `kgCO2`, not `kgCO₂e`. CO₂-only catalogue values remain ineligible for CO₂e.
- Manual user confirmation supports a controlled baseline flow; it is not real-SME validation or an OCR benchmark.

## Checks

Run:

```powershell
py -3.12 -m unittest discover -s tests -v
```

The tests cover canonical aliases and unit conversions, LPG factor derivation and conditional eligibility, the separate CEA electricity CO₂ result, road/mobile versus stationary diesel gating, exact material/product matching, each selected road-freight vehicle class, mass/distance normalization, required-context abstention, provenance traces, the human confirmation gate, and OCR transcript/manual-review behavior.
