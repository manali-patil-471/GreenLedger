GreenLedger - Data Acquisition Plan
Created: 2026-08-18

Purpose
This plan defines the smallest realistic acquisition strategy that would allow GreenLedger to become a legitimate research project without over-claiming or fabricating data. It intentionally separates generic document-understanding data from GreenLedger-specific data and carbon-accounting knowledge sources.

A. Generic document-understanding datasets

1) CORD (generic receipt parsing)
- What we have:
  - local CORD v2 research metadata and one sample parquet dataset
- Where it comes from:
  - Official CORD dataset on Hugging Face: https://huggingface.co/datasets/naver-clova-ix/cord-v2
  - Project repo: https://github.com/clovaai/cord
- How we use it:
  - Use only the local sample where its annotations support a defined generic receipt task; do not download the full multi-gigabyte collection without a demonstrated research need.
- What it is used for:
  - baseline document extraction, layout parsing, OCR for receipt-like records
- Limitations:
  - Indonesian receipts; no emissions ground truth; not a carbon dataset; only a generic document-understanding reference

2) SROIE (generic receipt extraction benchmark)
- What we need:
  - text localization, OCR, and key-field extraction benchmark on scanned receipts
- Where it comes from:
  - Official ICDAR RRC challenge page: https://rrc.cvc.uab.es/?ch=13&com=downloads
- How we obtain it:
  - Register to the ICDAR RRC portal and accept the challenge terms; then download the dataset package via the official portal.
- What it is used for:
  - OCR and layout extraction for receipt-like documents
- Limitations:
  - manual access required; generic receipts only; no emissions ground truth; no carbon accounting labels

3) FATURA (generic invoice understanding)
- What we have:
  - public invoice documents and annotations available locally
- Where it comes from:
  - Original paper: https://arxiv.org/abs/2311.11856
  - Public distribution: https://zenodo.org/records/8261508
- How we use it:
  - Use locally available files for generic invoice OCR/field extraction; keep license and redistribution constraints in view.
- What it is used for:
  - benchmark invoice document understanding and layout extraction
- Limitations:
  - invoice dataset, not carbon dataset; no emissions factors or accounting ground truth

B. GreenLedger-specific synthetic benchmark

1) Purpose
Create a controlled synthetic benchmark with exact ground truth for GreenLedger's frozen v1 activities.

2) Current status and remaining needs
- A partial v0.1.1 release has been generated: 200 electricity, 160 diesel, and 160 LPG documents, each with an exact JSONL ground-truth record and a held-out layout-family split.
- The 160 material and 120 transport documents remain ungenerated until their exact subsets and category/boundary decisions are approved.
- Release v0.1.1 has no CO2e targets. The global LPG factor has since been independently recomputed and conditionally enabled for its exact commercial/institutional stationary context; future labels still require combustion/boundary context and verified net mass.
- Electricity documents: bills with exact kWh, billing period, supplier, meter data, and per-document ground truth
- Fuel documents: diesel receipts/invoices with exact litres, date, supplier, fuel type, and totals
- LPG documents: cylinder or kg-based field extraction with exact quantity and fuel type
- Material invoices: line items with physical quantities and units where available
- Transport documents: freight notes with distance, mode, mass, and/or tonne-km

3) Where it comes from
- Synthetic generation pipeline designed in-house, never fabricated from real SME sources
- Output must be clearly labeled as synthetic data

4) How we obtain it
- Continue the controlled generator in `scripts/generate_synthetic_benchmark.py` after the remaining v1 activity decisions are approved.
- Keep the dataset intentionally limited: a small research benchmark, not a large production dataset.

5) What it is used for
- exact OCR benchmarking, field extraction evaluation, and controlled ablations

6) Limitations
- Synthetic documents do not replace real SME validation.
- Synthetic data must not be confused with actual business documents.

C. Real SME validation documents

1) What we need
- Small anonymized sample from real SMEs for validation of extraction and accounting logic
- Target: 5–15 SMEs, roughly 100–300 documents total for an initial pilot

2) Where it comes from
- Direct outreach to SMEs under consent, with secure transfer and anonymization

3) How we obtain it
- Use the outreach script and consent/retention procedures in metadata/REAL_SME_PLAN.md.
- Redact personal and financial data before storing in the research dataset.

4) What it is used for
- validating extraction quality on real-world bills/invoices; checking whether extracted fields map to the right GHG accounting category

5) Limitations
- small sample only; may not generalize; requires ethics/legal review; storage and consent are crucial

D. Carbon-accounting knowledge / factor sources

1) GHG Protocol
- What we need:
  - accounting terminology, scope definitions, and boundary rules
- Where it comes from:
  - https://ghgprotocol.org
  - Corporate Standard PDF: https://ghgprotocol.org/sites/default/files/standards/ghg-protocol-revised.pdf
  - Scope 3 standard page: https://ghgprotocol.org/corporate-value-chain-scope-3-standard
- How we obtain it:
  - download the PDF / use the official site and page
- What it is used for:
  - defining scope/category mapping and activity classification
- Limitations:
  - not a numerical factor database; provides accounting logic, not direct factor values

2) IPCC Emission Factor Database
- What we need:
  - authoritative document references and emission factor lookups where available
- Where it comes from:
  - https://www.ipcc-nggip.iges.or.jp/EFDB/main.php
- How we obtain it:
  - use the official EFDB search interface and record source references and versions
- What it is used for:
  - traceability and source verification for emission factors
- Limitations:
  - may require careful interpretation of technical references; not every factor is easily available for every activity

3) CEA India
- What we need:
  - Indian electricity grid baseline emission factors for local electricity accounting
- Where it comes from:
  - official CEA site: https://cea.nic.in
- How we obtain it:
  - use the official CEA archive, select a year-matched version, and record its direct URL, version, access date, and checksum
- What it is used for:
  - location-based electricity carbon accounting for Indian SMEs
- Limitations:
  - V22.0 was downloaded on 2026-09-24; check the official archive before future calculations because annual editions and applicable years change. The CEA values are CO2-only, not CO2e.

Minimum realistic acquisition strategy
Phase 1: use locally available public document-understanding sources
- Use the local CORD sample only for supported generic receipt tasks; do not fetch the full corpus without need.
- Keep SROIE unused unless access and terms are explicitly approved and the task requires it.
- Use the local FATURA files and preserve the recorded license/metadata constraints.

Phase 2: complete the GreenLedger-specific benchmark
- Validate the current 520-record partial release and use its declared splits for document-understanding/review experiments.
- Finalize material/transport subsets before generating their proposed 280 records.
- Ensure every generated document has exact ground truth and is labeled synthetic; never add guessed factors or CO2e values.

Phase 3: collect real SME validation data
- Run a small pilot with consent and anonymization.
- Annotate fields with human review and retain only anonymized validation data.

Phase 4: add carbon-accounting knowledge only from authoritative sources
- Use GHG Protocol + IPCC EFDB + CEA as the formal source library.
- Add emission factors only when they can be traced to a documented source; otherwise record FACTOR_NOT_VERIFIED.

Final source classification
- AVAILABLE — FATURA and a local CORD v2 sample for generic document understanding; CEA V22.0 CO2-only source references.
- MANUAL / NOT APPROVED — SROIE access and terms.
- PARTIAL SYNTHETIC — GreenLedger electricity, diesel, and LPG documents; materials and transport records remain pending exact scope decisions.
- REAL-SME NEEDED — external validation for realistic enterprise documents and carbon-accounting logic.
