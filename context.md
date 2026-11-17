# GreenLedger project context and work summary

This file is a compact but detailed handoff for another AI or collaborator. It captures what has already been done, what files exist, what was verified, and what remains intentionally out of scope.

## 1) Project objective and constraints

The project is GreenLedger, a carbon-accounting research platform for SMEs. The work done so far was strictly limited to data foundation and research design.

Important constraints followed throughout:
- No application backend/frontend build
- No model training
- No synthetic document generation
- No real SME data collection
- No guessed or fabricated emission factors
- No arbitrary public datasets outside verified sources
- No claims that generic invoice datasets are carbon datasets
- No expansion into broad Scope 1/2/3 coverage beyond the frozen v1 scope

The work was intentionally focused on:
- repository/data foundation setup
- data-source verification
- authoritative source research
- project scope definition
- benchmark design
- factor catalogue preparation without numeric factor invention

## 2) What we created at the project structure level

Under `GreenLedger/` the following structure was created:

- `data/`
  - `public/`
    - `cord/`
    - `fatura/`
    - `sroie/`
  - `synthetic/`
    - `electricity/`
    - `fuel/`
    - `materials/`
    - `transport/`
  - `real_sme/`
  - `benchmark/`
- `knowledge_base/`
  - `emission_factors/`
  - `activities/`
  - `scope_mapping/`
  - `standards/`
- `metadata/`
- `docs/`
- `scripts/`

This means the project now has the skeleton for a proper research data foundation: public datasets, benchmark datasets (planned but not generated), real-SME data future path, accounting knowledge, and documentation.

## 3) Public dataset verification and downloads

### 3.1 FATURA
We verified and downloaded the actual FATURA public dataset from the official Zenodo record.

Files created:
- `data/public/fatura/FATURA.zip`
- `data/public/fatura/zenodo_record_8261508.json`
- `data/public/fatura/METADATA.md`

Observed facts:
- Source: Zenodo record `8261508`
- Paper: FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis and Understanding
- Archive MD5: `a25c4f9292630f94774e0ca29d121e82`
- Download size: 363,504,027 bytes (~346.7 MiB)
- Extracted dataset under:
  - `data/public/fatura/extracted/invoices_dataset_final/`
- Dataset content:
  - 10,000 invoice images
  - 30,000 JSON annotation files across multiple annotation structures
  - split CSVs (`strat1_train.csv`, `strat1_dev.csv`, `strat1_test.csv`)
- File formats:
  - JPEG invoice images
  - JSON annotation files in multiple research formats
  - CSV split metadata
- Important conclusion:
  - FATURA is useful for generic business-document and invoice-understanding research
  - It is not a carbon-accounting dataset
  - It does not contain operational carbon scopes, GHG categories, emission factors, or expected CO2e values

The project used FATURA as a document-understanding corpus only, not as a carbon benchmark.

### 3.2 CORD v2
We verified the official source and the distinction between the code/metadata repository and the actual dataset host.

Files created/updated:
- `data/public/cord/METADATA.md`
- `data/public/cord/cord_v2_hf/README.md`
- `data/public/cord/cord_v2_hf/dataset_infos.json`

Observed facts:
- Official dataset source: Hugging Face dataset page
  - `https://huggingface.co/datasets/naver-clova-ix/cord-v2`
- GitHub repo at `https://github.com/clovaai/cord` is the repository and metadata source, not the full public dataset itself
- The dataset sample present locally includes a parquet file under:
  - `data/public/cord/cord_v2_hf/data/test-00000-of-00001-9c204eb3f4e11791.parquet`
- From the local schema inspection:
  - columns: `image`, `ground_truth`
  - image is embedded in the row as binary PNG data
  - `ground_truth` contains OCR/receipt layout parse JSON
  - includes fields like `gt_parse`, `meta`, `valid_line`, `words`, `quad`, `category`, etc.
- The dataset is useful for receipt/document extraction benchmarking, but not for GreenLedger carbon ground truth

We intentionally did not download the remaining large CORD LFS content because the project froze the scope and did not need the full multi-GB dataset before deciding what subset was genuinely useful.

### 3.3 SROIE
We verified SROIE as a registration-based public challenge dataset, but we did not download it.

Files created:
- `data/public/sroie/METADATA.md`

Observed facts:
- Official challenge source: ICDAR/RRC challenge page
- Requires registration/manual access
- It is a receipt OCR/receipt text extraction dataset
- It is not a carbon-accounting dataset
- The dataset is documented but not downloaded, because the user explicitly said not to proceed without manual review/approval for terms.

## 4) Carbon accounting source verification

We inspected the authoritative carbon sources that are already in the project and recorded them in the knowledge base.

### 4.1 CEA CO2 Baseline Database V21.0
Files:
- `knowledge_base/emission_factors/CO2_Database_V_21.0.xlsx`
- `knowledge_base/emission_factors/User_Guide_V_21.0.pdf`

What we verified:
- This is the official CEA India electricity baseline workbook
- Its relevant worksheets include:
  - `Data`
  - `Results`
  - `Transfer (1G)`
  - `Units + Abbrev`
  - `Assumptions`
- The `Results` sheet contains the electricity factors we care about for GreenLedger v1:
  - Weighted Average Emission Rate
  - Weighted Average Grid Emission Rate (Incl. RES, Captive)
  - Simple Operating Margin
  - Build Margin
  - Combined Margin
- The `Assumptions` sheet contains fuel emission assumptions and explicitly lists the diesel EF values (gCO2/MJ) based on NCV and GCV
- This is a verified Indian electricity factor source for purchased-electricity calculations

Important conclusion:
- This source supports GreenLedger electricity calculations but does not automatically resolve the final methodological choice between average vs marginal factors
- For v1, the project specifically selected the CEA Weighted Average Emission Rate as the default electricity factor for location-based Scope 2 calculations, with OM/BM/CM retained as method alternatives

### 4.2 GHG Protocol Corporate Standard
File:
- `knowledge_base/standards/GHG Protocol Corporate Standard Revised (English).pdf`

What we verified:
- It defines the accounting basis for Scope 1, Scope 2, and Scope 3 boundaries
- It is the principal authoritative source for GreenLedger’s carbon-accounting structure
- It provides the conceptual framework that GreenLedger uses for activity mapping and scope/category classification

### 4.3 GHG Protocol Scope 3 guidance
File:
- `knowledge_base/standards/Scope3_Calculation_Guidance_0[1].pdf`

What we verified:
- It is relevant for purchased materials and selected transport activities
- It provides the framework for activity-data and emission-factor logic for Scope 3 categories
- It helped define what GreenLedger v1 should and should not support

### 4.4 IPCC EFDB
Source noted in metadata but not downloaded as part of the project’s constrained research phase.

Recorded in:
- `metadata/SOURCES.md`

What we verified:
- It is an authoritative repository for emission-factor references and technical documentation
- It is relevant for future fuel- and material-factor lookups, but the project did not populate numeric factors from it in this stage

## 5) Metadata and source log

Project source tracking is centralized in:
- `metadata/SOURCES.md`

This file records:
- source name
- exact URL
- access date
- version/year
- what information was obtained
- how it was used in the GreenLedger data foundation

It includes records for:
- CORD repo and CORD v2 dataset
- SROIE challenge dataset
- FATURA paper + Zenodo record
- GHG Protocol Corporate Standard
- GHG Protocol Scope 3 guidance
- IPCC EFDB
- CEA workbook and guide

This gives the project a traceable research provenance trail.

## 6) Project scoping and v1 freeze

We explicitly froze the initial scope to a realistic set of activities for a 4-person final-year project.

Files:
- `docs/GREENLEDGER_V1_SCOPE.md`
- `docs/GREENLEDGER_BENCHMARK_PLAN.md`

Main decisions:
- v1 supports a small but meaningful workflow built around:
  - electricity bills
  - diesel fuel receipts/invoices
  - LPG receipts/invoices
  - selected purchased materials invoices
  - selected transport/freight bills
- Materials and transport are intentionally narrow and limited
- Major uncertain categories are marked as `FUTURE SCOPE`, not forced into v1

This is a major design decision that prevents scope creep.

## 7) Ground-truth schema and activity definitions

Files:
- `knowledge_base/activities/greenledger_ground_truth_schema.json`
- `knowledge_base/activities/activities.json`
- `knowledge_base/scope_mapping/mapping.json`

What they contain:
- canonical activity names and aliases
- likely Scope and category mapping
- expected units and conversion requirements
- ground-truth fields needed to link documents to carbon-accounting calculations

Examples of canonical activities recorded:
- purchased_electricity
- diesel_fuel
- lpg
- purchased_materials
- selected_transport

These schemas define the exact research vocabulary used by the project.

## 8) Emission-factor database foundation

Files:
- `knowledge_base/emission_factors/schema.csv`
- `knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv`
- `knowledge_base/emission_factors/GREENLEDGER_V1_CALCULATION_METHODS.md`
- `knowledge_base/emission_factors/CO2_Database_V_21.0.xlsx`

What was done:
- Built the factor schema for future GreenLedger factor records
- Defined required fields such as:
  - `factor_id`
  - `activity`
  - `normalized_activity`
  - `scope`
  - `scope_category`
  - `unit`
  - `factor_value`
  - `factor_unit`
  - `geography`
  - `applicable_year`
  - `source`
  - `source_version`
  - `source_url`
  - `notes`
- Added a first set of verified entries for the CEA-based electricity and diesel factors where traceability exists
- Kept all factors conservative and did not invent numeric values for unsupported activities like LPG or materials/transport

Important control: The project does not add guessed values. Any factor that cannot be traced remains marked as `METHOD_SELECTION_REQUIRED`, `FUTURE_SCOPE`, or left blank with explicit status.

## 9) Benchmark design

Files:
- `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json`
- `docs/GREENLEDGER_FIELD_SPECIFICATION.md`
- `docs/SYNTHETIC_GREENLEDGER_BENCHMARK_SPEC.md`
- `docs/GREENLEDGER_EXPERIMENT_PLAN.md`
- `docs/REAL_SME_VALIDATION_SPEC.md`
- `docs/GREENLEDGER_DATA_GAP.md`
- `docs/FATURA_TO_GREENLEDGER_MAPPING.md`

What was designed:
- explicit benchmark tasks
- exact annotation schema for one document
- field-level specification for each v1 document type
- synthetic benchmark strategy for future generated data
- real-SME validation plan
- research experiments and evaluation metrics
- data gap analysis

Important conceptual point:
- FATURA and CORD are not carbon benchmarks
- GreenLedger’s benchmark must separate:
  1. document-understanding performance
  2. carbon activity extraction
  3. carbon accounting and factor retrieval

This benchmark design is crucial because it prevents the common mistake of treating invoice datasets as carbon ground truth.

## 10) Decision records and factor methodology

Files:
- `docs/GREENLEDGER_FACTOR_DECISIONS.md`
- `knowledge_base/emission_factors/GREENLEDGER_V1_CALCULATION_METHODS.md`

What these contain:
- the selected approach for electricity factor choice
- reasoning about weighted average vs operating/build/combined margins
- diesel calculation approach and conversion rules
- why LPG/materials/transport remain not ready for v1
- how calculations will work once a factor is selected

This is the project’s reproducibility record for decision-making and methodology.

## 11) Documentation created for the project foundation

The docs folder is extensive and includes:

- `docs/DATA_FOUNDATION.md`
  - explains why GreenLedger needs multiple dataset types and their role
- `docs/DATA_ACQUISITION_PLAN.md`
  - separates public datasets, synthetic benchmark, real SME data, and carbon knowledge sources
- `docs/MINIMUM_DATA_REQUIREMENTS.md`
  - states the minimum data needed for each initial activity
- `docs/CORD_USAGE_ASSESSMENT.md`
  - evaluates what CORD actually provides and whether the full dataset is worth downloading now
- `docs/CEA_V21_RELEVANT_CONTENT.md`
  - explains what the CEA workbook contains that is relevant to electricity calculations
- `docs/CARBON_ACCOUNTING_SOURCE_SUMMARY.md`
  - summarizes authoritative sources and their role in the GreenLedger project
- `docs/GREENLEDGER_BENCHMARK_PLAN.md`
  - explains the three-layer benchmark strategy
- `docs/GREENLEDGER_DATA_GAP.md`
  - identifies missing data and blocking items
- `docs/REAL_SME_VALIDATION_SPEC.md`
  - defines validation targets and anonymization rules
- `docs/FATURA_TO_GREENLEDGER_MAPPING.md`
  - explains how FATURA supports document-understanding but not carbon ground truth
- `docs/GREENLEDGER_EXPERIMENT_PLAN.md`
  - defines evaluation tasks and experiment baselines

These are all part of the reasoning and documentation layer that makes the project traceable and auditable.

## 12) Real-SME acquisition planning

Files:
- `metadata/REAL_SME_PLAN.md`
- `docs/REAL_SME_VALIDATION_SPEC.md`

What we prepared:
- realistic validation target ranges
- anonymization requirements
- sensitive-field redaction guidance
- outreach message template
- consent/data-use considerations
- annotation workflow
- privacy and retention recommendations

This ensures the project knows how it would later collect a small validation set without fabricating data or violating privacy.

## 13) Scripts created

Files:
- `scripts/download_datasets.py`
- `scripts/download_cord.py`

What they do:
- prepare dataset-downloading pipelines
- install dataset dependencies
- attempt to load the CORD dataset from Hugging Face
- write manifest outputs and verification files

These scripts are operational but not part of the application itself; they are research/support scripts for dataset handling.

## 14) What we did NOT do

This is important context for other AI.

We did not:
- build the GreenLedger app or any backend/frontend modules
- train any model
- generate synthetic invoice documents
- collect real SME data
- add random or guessed numerical emission factors
- claim that CORD/FATURA are carbon datasets
- support all GHG categories in scope
- proceed to model development before the data foundation and v1 scope were frozen

## 15) Current project status

The current status is:
- Data foundation is set up
- Public datasets and authoritative source files are verified and recorded
- GreenLedger v1 document/activity scope is frozen
- Benchmark strategy is designed
- Emission-factor decisions are documented and conservative
- The project is ready for the next phase only when the user explicitly instructs it to move forward

The project is deliberately not at the implementation stage yet.

## 16) Key final state

The project is in a research-ready, traceable, standards-aware data foundation stage. It has:
- verified public corpora for invoice/receipt understanding
- authoritative carbon-accounting sources
- a realistic narrow AI/data research scope for a final-year project
- a benchmark and validation strategy that separates public, synthetic, and real SME data
- factor and methodology decisions that are conservative, documented, and not invented

## 17) Important open gaps still intentionally unresolved

The project still does not yet have all of the following:
- final numeric factor values for LPG, selected materials, and selected transport
- a final set of real SME validation documents
- a full synthetic benchmark dataset generated from exact ground truth
- a final, fully verified set of exact material and transport categories for v1

These are explicitly kept out of scope until the user approves further work.

## 18) Best one-line summary for handoff

GreenLedger is currently in a strict data-foundation and methodology-freeze phase: we verified the public document datasets, audited authoritative carbon-accounting sources, froze the v1 scope, designed the benchmark and annotation framework, and created a conservative emission-factor catalogue and calculation methods without inventing unsupported factors or generating any synthetic or real data.
