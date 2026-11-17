# GreenLedger Data Gap Analysis

Updated: 2026-11-14

## 1. Available

- FATURA public invoices and annotation files are available locally for generic document-understanding work.
- A local CORD v2 sample parquet and research metadata are available; the full multi-gigabyte collection is not required.
- SROIE has metadata only and remains unused pending access/terms approval.
- GHG Protocol Corporate Standard, Scope 3 Guidance, and published Scope 2 Guidance with corrections are stored.
- CEA V22.0 workbook and guide are stored with source hashes. CEA remains CO2-only. The catalogue also includes a conditional LPG CO2e factor and an India road/mobile diesel TTW CO2e factor, each gated by applicable context.
- The frozen v1 scope, activity taxonomy, scope mapping, factor catalogue, schemas, benchmark specification, and plans are present.
- Synthetic release v0.1.1 contains 520 electricity, diesel, and LPG documents with one exact ground-truth record per image and held-out layout-family splits.

## 2. Still needed

- Final approved material and transport subsets, context/boundary rules, and corresponding synthetic documents (160 and 120 are proposed targets, not generated counts).
- Electricity CO2e remains unresolved. A stationary/power-sector diesel CO2e factor and L-to-energy conversion remain unresolved; India road/mobile TTW diesel is supported only by the conditional SFC factor and required road/geography context. LPG's commercial/institutional stationary factor has been independently recomputed and conditionally enabled; other LPG contexts and cylinder-count-to-mass conversion remain unresolved. Materials and transport factors remain unresolved.
- A supervised character n-gram field-role candidate has been trained on the 325 training records and compared with rules on 65 synthetic validation OCR transcripts. It improves coverage for billing period, cylinder net mass, and vehicle reference fields where rules had no outputs, while matching rules on the other measured fields. It is not integrated into the app or selected as final. No confidence calibration exists. See `AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`.
- Real SME documents collected with consent, anonymization, provenance, and independently checked labels.

## 3. Supported benchmark tasks now

The 520 synthetic records support controlled testing of document type, OCR text, carbon-field extraction, activity/unit normalization, context-aware scope decisions, CO2-only/unresolved factor statuses, abstention, and human-review logic. They do not provide CO2e numerical targets and are not real-world validation. Public FATURA/CORD labels remain generic document truth only.

## 4. Current blockers

- The synthetic release contains no CO2e ground-truth cases, even though narrow conditional LPG and India road/mobile diesel factors are now available in the accounting catalogue.
- Electricity calculation requires explicit India-grid geography and FY2025-26 applicable-period context. Diesel outside the India road/mobile TTW case still requires matched stationary/power-sector evidence and, where needed, an authoritative MJ-to-litre basis.
- LPG cylinder-count-to-mass conversion still requires printed net fill mass or a linked authoritative supplier specification; other source categories/geographies require matching factors.
- Material and transport activities remain deliberately narrow but not yet selected.
- Real SME collection and end-to-end evaluation have not started. The original test split is quarantined after annotation exposure; an independent replacement holdout is needed for final evaluation.

## 5. Not required now

- Broad unrelated carbon datasets or large public corpora without a demonstrated need.
- Full CORD download or SROIE download before access/terms and task need are established.
- Fine-tuning before enough licensed, annotated GreenLedger data exist.

## Status

- **DONE:** Public document baselines, standards, factor-source foundation, schemas, benchmark plan, and partial synthetic document slice.
- **BLOCKED:** Full end-to-end CO2e evaluation and material/transport synthetic completion.
- **IN PROGRESS:** Local app with optional OCR transcript and manually confirmed carbon fields.
- **DONE:** Initial AI-assisted carbon-field extraction candidate training and rule-baseline comparison using train/validation only.
- **IN PROGRESS:** Decide whether to compare other extraction families and integrate a candidate after further validation; confidence calibration is outstanding.
- **QUARANTINED:** Original test split; do not evaluate it. A replacement independent holdout is required.
- **NOT YET STARTED:** Real-SME validation and end-to-end carbon evaluation.
