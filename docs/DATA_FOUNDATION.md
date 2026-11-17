# GreenLedger Data Foundation

Updated: 2026-11-14

This page records the current repository state. Dataset counts and factor status must be refreshed from the files and official sources before making new research claims.

## Data inventory

- **FATURA:** locally available public invoice dataset with its document/annotation files. Use for generic invoice understanding only; it does not provide GreenLedger carbon truth.
- **CORD:** a local sample and research metadata are present. Use only the available sample where its data support a generic receipt task; the full multi-gigabyte collection is not required for the current plan.
- **SROIE:** research metadata only. The dataset is not downloaded or used; access/terms remain unapproved.
- **Synthetic GreenLedger v0.1.1 partial:** 520 explicitly synthetic PNG documents (200 electricity, 160 diesel, 160 LPG) with one JSONL ground-truth annotation per image, image hashes, and held-out layout-family splits. The proposed 160 material and 120 transport records are not generated because their exact v1 subsets/boundaries remain undecided. Superseded development renders are clearly marked and excluded.
- **Real SME records:** none collected. Synthetic examples are not real-world validation.

See `data/synthetic/greenledger_v0_1_1_partial/README.md` and `manifest.json` for the exact generated counts, split counts, seed, dependency version, and limitations.

## Knowledge base

- `knowledge_base/emission_factors/` contains the catalogue schema and a 37-row GreenLedger v1 catalogue. The CEA electricity and two CEA diesel records are CO2-only references. Electricity has a separate CEA V22 FY2025-26 CO2 path and remains ineligible for CO2e. Conditional CO2e factors are available for IPCC 1.A.4.a stationary LPG and India road/mobile diesel TTW; both require strict context and activity-unit matching. Materials, other LPG contexts, stationary/power-sector diesel CO2e, and transport remain unresolved.
- The official CEA V22.0 workbook and user guide, IPCC LPG inputs/GWP sources, and SFC India diesel methodology PDF are stored and SHA-256-pinned. CEA's source values must not be labeled CO2e.
- The published GHG Protocol Scope 2 Guidance and its corrections are stored under `knowledge_base/standards/`. Structured factor applicability and provenance fields are enforced by `scripts/validate_factor_catalogue.py` and the deterministic retrieval gates.
- `knowledge_base/activities/activities.json` defines five frozen v1 canonical activity IDs plus documented unit scaling. `knowledge_base/scope_mapping/mapping.json` requires context where organizational boundary or business flow affects classification.
- Material and transport activity subsets and their matched factor paths are still pending. Do not widen v1 or infer those categories from charges alone.

## Annotation and experiments

`data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json` v0.3 declares task coverage, visible field evidence, normalized quantities/units, context-aware scope, factor/calculation status, uncertainty, and human-review truth. It keeps benchmark truth separate from system predictions and only permits expected CO2e where a verified CO2e factor and all conversions are present.

The benchmark and experiment plans define task-specific comparison rules and metrics. A three-candidate OCR comparison and deterministic rules field-extraction baselines have been measured on the 65-document synthetic validation split; see the dated experiment reports. No carbon-accounting score has been measured. The 130-document synthetic test split is quarantined after annotation exposure; no result may be reported from it. See [the quarantine record](TEST_SPLIT_QUARANTINE_2026-11-10.md).

## Verified and unresolved

- **Verified / conditional:** The LPG factor independently recomputes to 2.99230679 kgCO2e/kg from the recorded IPCC/AR6 source inputs and is eligible only for its matching commercial/institutional stationary Scope 1 context and verified net mass. The SFC/TCI-IIMB publication reports 2.675 kgCO2e/L diesel TTW for road transportation; the factor is gated to India road/mobile use and retains the publication's source caveat. CEA source values remain CO2-only.
- **Unresolved:** Electricity CO2e method; stationary/power-sector diesel CO2e and litre-to-energy basis; LPG cylinder-count-to-mass evidence and other LPG source categories/geographies; exact purchased-material subset; exact transport mode/activity and Category 4/9 boundaries.
- **In progress:** local application baseline with optional transient OCR transcription. A supervised AI line-role candidate has been trained on the training partition and measured against rules on validation; it is not integrated into the app and has no calibrated confidence. No final model is selected. The original test partition is quarantined, so a new blinded holdout is required. Real SME collection and validation remain outstanding.

## Data-use constraints

FATURA and CORD support document-understanding work only. SROIE remains unused until its access and terms are approved. Synthetic data are explicitly synthetic and cannot establish SME generalization. Real documents require permission, anonymization, provenance, and independently checked labels. Never infer a factor or CO2e result from the document model.
