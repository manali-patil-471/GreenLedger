GreenLedger - Minimum Data Requirements
Created: 2026-08-18

Goal: Define the minimum verified data needed to begin a legitimate GreenLedger research pipeline for the initial activity classes. These are the minimal requirements for the first research scope only. This does not claim the system is complete for all Scope 1/2/3 activities.

Scope of initial support
1. Purchased electricity
2. Diesel/fuel
3. LPG
4. Selected purchased materials
5. Selected transport activity

General constraint
- Public document datasets (CORD, SROIE, FATURA) are useful for document understanding only.
- They do not provide carbon-accounting ground truth.
- GreenLedger-specific data must therefore include: document-level extraction, emissions factor provenance, and accounting category mapping.

1) Purchased electricity
- Document types needed:
  - electricity bills, utility statements, commercial energy bills, metered energy invoices
- Fields that must be extracted:
  - supply period start/end, meter identifier, kWh consumed, tariff type, billing amount, currency, supplier name, meter address (if visible), account number (redacted where sensitive)
- Expected units:
  - kWh for consumption; monetary amount in local currency; emission factor in kg CO2e/kWh or gCO2e/kWh
- Accounting category:
  - Scope 2 - Purchased electricity; location-based or market-based distinction must be explicit
- Type of emission factor needed:
  - grid electricity emission factor for the relevant geography and reporting year
- Public source exists?
  - Yes, but not as one uniform global repository: national utility reports, grid factors, and official electricity inventory publications may exist. For India, the CEA official source is required.
- Synthetic data needed?
  - Yes, for controlled benchmarking of OCR and field extraction.
- Real SME data valuable?
  - Yes, for realistic field extraction and validation.
- Major data risks:
  - missing tariff details, differing billing conventions, market vs location factor ambiguity, multi-meter bills

2) Diesel / fuel
- Document types needed:
  - fuel station receipts, diesel purchase invoices, fuel-card statements, bulk diesel delivery invoices
- Fields that must be extracted:
  - date, quantity in litres, fuel type, unit price, total amount, supplier, vehicle/tank identifier if present, account identifier (redacted), currency
- Expected units:
  - litres (L), and fuel-specific emissions factor in kg CO2e per litre or gCO2e per litre; if mass-based, convert using density and source-specific assumptions
- Accounting category:
  - Scope 1 for direct combustion in company-owned equipment/vehicles; context-dependent Scope 3 if combusted by third parties or under other ownership
- Type of emission factor needed:
  - fuel combustion emission factor specific to diesel and reporting year
- Public source exists?
  - Yes, via national inventories and IPCC EFDB sources, but not a single universal public GreenLedger benchmark dataset for exact business receipts.
- Synthetic data needed?
  - Yes, for controlled generation of layouts and quantities.
- Real SME data valuable?
  - Yes, for validation of document noise and real receipt variation.
- Major data risks:
  - ambiguous product/fuel type, missing density assumptions, ownership scope ambiguity

3) LPG
- Document types needed:
  - LPG cylinder delivery receipts, LPG purchase invoices, cylinder dispatch notes
- Fields that must be extracted:
  - fuel type, quantity in kg or cylinder count, unit price, total amount, supplier, date, delivery details
- Expected units:
  - verified net kg of LPG; cylinder count may be converted only using printed net fill mass or an authoritative linked supplier specification
- Accounting category:
  - Scope 1 only for actual combustion in an owned/controlled source; an invoice alone does not establish use or boundary
- Type of emission factor needed:
  - a global IPCC Tier 1 factor is available for commercial/institutional stationary combustion (IPCC 1.A.4.a), using AR6 GWP100; other contexts need a matching factor
- Public source exists?
  - Yes in general publications and EFDB, but public document datasets are not sufficient by themselves.
- Synthetic data needed?
  - Yes, for benchmark experimentation.
- Real SME data valuable?
  - Yes, especially for small commercial LPG purchases.
- Major data risks:
  - mixed cylinder sizes, density/weight assumptions, missing quantity units

4) Selected purchased materials
- Document types needed:
  - purchase invoices and delivery records for the exact narrow material subset once approved; candidate examples in this document are not approved v1 activities
- Fields that must be extracted:
  - supplier name, item description, quantity, unit, unit price, line total, material category, invoice total, currency, date
- Expected units:
  - verified physical quantities; monetary-only values are not activity quantities and do not support a CO2e calculation
- Accounting category:
  - Scope 3 - Purchased goods and services (Category 1) for relevant purchased materials
- Type of emission factor needed:
  - cradle-to-gate product or material emission factor; supplier-specific or third-party LCA factor; otherwise mark as FACTOR_NOT_VERIFIED
- Public source exists?
  - Unresolved: no factor source has been selected for the final material subset and matching geography/product basis.
- Synthetic data needed?
  - Yes, for controlled invoice layout generation and material line-item extraction.
- Real SME data valuable?
  - Very valuable, because material categories and supplier practices vary significantly.
- Major data risks:
  - missing physical quantity, price-only invoices, supplier-specific intensity not publicly available, insufficient data for arbitrary materials

5) Selected transport activity
- Document types needed:
  - freight invoices, delivery notes, transport bills, waybills, consignment records, fuel invoices for transport operations
- Fields that must be extracted:
  - mode of transport, distance in km, mass in kg or tonnes, tonne-km, fuel quantity, route or origin-destination, invoice total, carrier name, date
- Expected units:
  - km, tonne-km, kg, litres for fuel; emission factor depends on transport mode and, for freight, mass-distance intensity
- Accounting category:
  - Scope 3 - Upstream/downstream transportation and distribution, depending on the business context; category assignment must be contextual
- Type of emission factor needed:
  - mode-specific transport emission factor or fuel-based factor; if freight, tonne-km factors are preferred when available
- Public source exists?
  - Some generic factors exist, but none is selected for the pending v1 transport mode, category boundary, geography, and activity basis.
- Synthetic data needed?
  - Yes, for document layouts and transport details with exact ground truth.
- Real SME data valuable?
  - Yes, for validation of real freight and logistics data.
- Major data risks:
  - missing mass or route data, varied invoice conventions, uncertain category assignment, mode ambiguity

Minimum GreenLedger data bundle required for a credible first study
- Document-understanding dataset(s): CORD, SROIE, and/or FATURA for general OCR/parsing development
- GreenLedger synthetic benchmark: exact ground-truth benchmark for electricity, fuel, LPG, materials, and transport documents
- Real SME validation set: small, anonymized set collected under consent with human-reviewed annotations
- Carbon-accounting knowledge sources: GHG Protocol, IPCC EFDB, and relevant national grid/baseline sources such as CEA for India

Classification summary
- Generic document-understanding datasets: available or manual access
- GreenLedger synthetic benchmark: synthetic required
- Real SME validation: real-SME needed
- Carbon-accounting factors: authoritative source-based, not public benchmark datasets
