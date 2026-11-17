# Synthetic GreenLedger Benchmark Specification

**Status: specification plus partial synthetic release.** `data/synthetic/greenledger_v0_1_1_partial/` contains 520 documents and linked records for electricity, diesel, and LPG. This is not the complete proposed 800-record allocation. Earlier development renders are marked superseded and excluded. Read the benchmark with `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json`, the frozen v1 scope, and the factor catalogue. If a newer, explicitly approved specification is recorded, use it instead of the proposed counts below.

## 1. Objective and intended coverage

Create controlled documents with exact ground truth for document understanding, carbon-relevant extraction, normalization, context-aware GHG classification, factor-status handling, calculation where scientifically supported, and human-review decisions. The benchmark is synthetic and cannot establish real-SME generalization.

The current recommended allocation is 800 documents:

| Activity group | Proposed count |
| --- | ---: |
| Electricity | 200 |
| Diesel | 160 |
| LPG | 160 |
| Selected purchased materials | 160 |
| Selected transport/freight | 120 |
| **Total** | **800** |

These are design targets, not generated or validated sample counts. Material and transport generation is blocked until their exact v1 subsets and category/boundary rules are selected. Fuel and electricity records may test extraction, normalization, scope context, factor-status and abstention behavior, but must not contain invented CO2e targets. The global LPG Tier 1 factor is now independently recomputed and conditionally eligible; current release v0.1.1 LPG records lack the necessary boundary/source context and contain no expected CO2e targets.

## 2. Required diversity

Every activity group should vary the following dimensions across examples, not just randomize values within one layout:

- fictional supplier names and visually distinct vendor/layout families;
- bills, receipts, invoices, delivery notes, and statements where the activity permits;
- heading and line-item wording, abbreviations, spelling/spacing variants;
- dates, date formats, periods, quantity magnitudes, decimal/grouping styles, and applicable currencies;
- unit spelling and placement (for example `litres`, `L`, `Qty: 250 L`);
- typography, page size, table shape, field order and position, logos/marks, and whitespace;
- clean digital output and bounded scan degradations such as low contrast, skew, blur, compression, partial crop, or stamps;
- realistic irrelevant data and optional fields, plus missing, illegible, conflicting, or genuinely ambiguous fields.

Use fictional identifiers and supplier identities. Do not reproduce a real SME document or imply that a fictional document is real. Define generation families first, then allocate families across train/validation/test so whole vendor/layout families are held out. Store a deterministic seed and rendering parameters for reproducibility.

## 3. Activity-specific fields and guardrails

### Electricity bills

Annotate supplier, bill/period dates, account/meter identifiers where visible, billed consumption, raw unit, bill amount/currency, and relevant energy fields. Distinguish consumption from billed amount, demand, meter readings, and exported energy. Normalize MWh to kWh only under the documented scaling rule. If an emission factor is recorded, retain its exact CO2-only status and source provenance; do not label it CO2e or compute an expected CO2e value.

### Diesel invoices and receipts

Annotate fuel wording, quantity, raw unit, supplier, date, amount/currency, and printed vehicle/equipment or delivery context. Include both explicit-unit examples and ambiguous examples such as a bare quantity. Represent whether the synthetic scenario says the fuel was purchased, consumed, or remains unknown; provide boundary/source context only where the document or scenario supplies it. Do not infer Scope 1 from a diesel purchase label. L-to-MJ/kg conversion is prohibited until the factor basis and authoritative fuel-property basis are matched and documented.

### LPG receipts and invoices

Annotate printed net gas mass, cylinder count, product/size wording, supplier, date, amount/currency, and use/boundary context when supplied. A cylinder count is not a mass: normalize it only if printed net fill mass or an authoritative linked product specification supports the conversion. Mark unit or fill-mass ambiguity for human review. The global IPCC Tier 1 factor is calculable only for matching IPCC 1.A.4.a stationary combustion with confirmed owned/controlled boundary and verified net mass; current synthetic LPG records do not annotate that context and have no CO2e target.

### Selected purchased materials

Do not generate these records until the narrow material subset, activity basis, scope-category treatment, and authoritative factor path have been approved. Then annotate exact product/material class, physical quantity and unit, supplier, date, and line-item evidence. Monetary amounts alone are not physical activity data; price-to-mass guesses and broad unselected goods are excluded.

### Selected transport/freight

Do not generate these records until the v1 transport mode(s), business flow, category 4/9 boundary treatment, activity basis, and authoritative factor path have been approved. Then annotate mode, route or distance, shipment mass, source-provided tonne-km, service purchaser, provider control, and invoice evidence. A freight charge is not distance or tonne-km. Do not infer distance from route descriptions or calculate emissions from charges.

## 4. Ground-truth record and matching

Use one record conforming to `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json` for each rendered document. The record must include:

- unique `document_id`, `source_type: synthetic`, image/PDF path and SHA-256, document type, layout/vendor-family identifiers, and quality tags;
- explicit `task_coverage`, with only tasks for which the record has ground truth;
- OCR transcription/tokens and field annotations where those tasks are covered; field evidence and presence status, including omitted, illegible, ambiguous, and not-applicable values;
- canonical activity, unit and quantity normalization status, and a documented conversion trace where applicable;
- scope/category labels only when the required scenario context supports them; otherwise an explicit ambiguous state and reason;
- factor retrieval status with exact catalogue/source/version fields when a verified factor or a CO2-only reference is applicable; otherwise an unresolved status and reason;
- CO2e calculation status. Include `expected_co2e` only when a verified CO2e factor and every conversion are available; preserve the factor ID, inputs, rules, units, and result in the calculation trace;
- truth labels for whether review is required, which fields require review, why, and the expected human action.

The raw rendered text may use different representations for the same truth. Evaluate after documented parsing: for example, `250 litres`, `250 L`, and `Qty: 250 L` can map to the same numeric quantity and canonical unit. Keep the original text and evidence so OCR and extraction can still be evaluated independently of normalization.

## 5. Reproducibility and leakage controls

Generate each record from a structured source object before rendering. Store generator version, seed, template/layout family, field placement, typography choices, degradation settings, and the rendered file hash. Do not derive ground truth from OCR output. Allocate train/validation/test by generation family and vendor/layout so the same template cannot leak across splits. Keep real SME records in a distinct external-validation partition.

## 6. What the dataset can and cannot show

Synthetic data can test exact parsing, normalization, deterministic rules, factor-status behavior, and controlled review cases. They cannot prove real-world document distribution, actual supplier behavior, or SME generalization. FATURA and CORD remain generic document-understanding resources; they do not supply GreenLedger carbon ground truth. SROIE stays unused without explicit approval of access and terms.

## Status

- **DONE:** Proposed allocation, variation requirements, per-activity guardrails, and exact-truth structure are defined.
- **DONE:** Generator and partial release exist for 200 electricity, 160 diesel, and 160 LPG documents, with deterministic seed, image hashes, annotations, and family-held-out train/validation/test splits.
- **BLOCKED:** Material and transport documents await final subset/category decisions.
- **BLOCKED:** Any CO2e ground truth awaits applicable per-record factors, complete source/boundary context, required conversions, and new annotations; the current release has no CO2e targets.
- **NOT YET STARTED:** Material/transport rendering and full 800-record completion.
- **DONE:** Three OCR transcription candidates were compared on the synthetic validation split; deterministic rules extraction was scored on RapidOCR and Florence-2 transcripts. See the dated reports; neither result measures AI carbon-field understanding or end-to-end emissions accuracy.
- **DONE (initial):** A supervised character n-gram line-role candidate was compared against rules on the 65 synthetic validation records; see `docs/AI_FIELD_EXTRACTION_CANDIDATE_2026-11-10.md`. This does not complete a broader layout/VLM comparison or establish real-world performance.
- **QUARANTINED:** The original test partition following annotation exposure; a replacement independent holdout is required for final evaluation. See `docs/TEST_SPLIT_QUARANTINE_2026-11-10.md`.
