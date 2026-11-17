# GreenLedger v1 Research Scope

## Objective

GreenLedger v1 is a realistic first-version research system for a 4-person final-year CSE project. The goal is to demonstrate a complete carbon-accounting workflow on a narrow, defensible set of SME business documents without trying to solve every possible scope or data source in one project.

The design is intentionally conservative:

- small, document-driven workflow
- narrow activity coverage
- traceable accounting logic
- explicit use of authoritative sources
- human verification for uncertain fields
- the factor catalogue records verified CO2-only CEA source values plus conditional global LPG Tier 1 and India road/mobile diesel TTW CO2e factors; the selected electricity row supports a distinct CO2-only result, and every calculation remains gated by matching factor applicability and verified activity/context

## 1. Initial document types

### 1. Electricity bills
Why it is useful:
- Purchased electricity is a core, high-volume SME activity and a clean Scope 2 workflow.
- It is relatively structured and easier to normalize than more complex business documents.

What can realistically be extracted:
- supplier name
- billing period
- meter/contract number
- total kWh consumed
- tariff or billing category
- total amount or unit charge
- document date

Business activity represented:
- grid electricity consumption for operations

Public dataset usefulness:
- Not a carbon dataset; generic utility bills are not the same as carbon ground truth.
- FATURA/CORD are helpful only for generic invoice/receipt understanding, not for electricity-accounting semantics.

Synthetic documents:
- Yes, eventually useful for controlled evaluation of extraction and normalization on bill layouts.

Real SME documents:
- Very valuable for validation because actual utility bills vary by supplier, tariff, and billing format.

### 2. Diesel/fuel purchase receipts and fuel invoices
Why it is useful:
- Diesel fuel purchases are common in SMEs and represent a clear, high-value activity with combustion-based emissions.
- It is simpler than complex procurement categories and can be extracted from a purchase receipt form.

What can realistically be extracted:
- fuel type
- quantity
- unit (litres or gallons)
- date
- supplier
- vehicle/equipment reference if present
- total amount

Business activity represented:
- purchased diesel fuel for transport or equipment use

Public dataset usefulness:
- Generic receipt/invoice datasets help with OCR and layout, but do not provide fuel-type or emissions ground truth.

Synthetic documents:
- Yes, useful for controlled field-extraction evaluation.

Real SME documents:
- Very valuable because real fuel invoices vary by vendor, tax format, and fuel grade.

### 3. LPG cylinder/refill invoices and receipts
Why it is useful:
- LPG is a common fuel in SMEs and households and is comparatively structured.
- It gives GreenLedger another combustion-based activity without requiring a broad fuel taxonomy.

What can realistically be extracted:
- fuel type
- quantity or cylinder size
- weight or volume if present
- refill date
- supplier and invoice number
- total amount

Business activity represented:
- LPG purchased for cooking or process use

Public dataset usefulness:
- Some generic invoice datasets can help with receipt layout, but they do not provide LPG carbon semantics.

Synthetic documents:
- Yes, useful for controlled benchmarking.

Real SME documents:
- Valuable for validation and to cover vendor-specific formatting differences.

### 4. Selected purchased materials invoices
Why it is useful:
- Purchased materials are a realistic Scope 3 category for SMEs and give the project a meaningful upstream inventory challenge.
- A narrow, traceable material subset is feasible.

What can realistically be extracted:
- supplier
- date
- item description
- quantity
- unit (kg, kg/m, piece, box, tonne, etc.)
- material description if present
- price and tax data

Business activity represented:
- purchase of selected physical materials or raw materials

Public dataset usefulness:
- FATURA is useful only for generic invoice extraction; it does not provide material-specific emission characteristics.

Synthetic documents:
- Yes, useful for benchmarking invoice extraction but not for real material-intensity ground truth.

Real SME documents:
- Very valuable; material invoices are highly variable and require human review.

Important restriction:
- This will not support every possible material type in v1.
- v1 will only support a small set of high-frequency, weight-tractable materials with verifiable factors.
- Any unverified material or monetary-only material invoice is FUTURE SCOPE.

### 5. Selected transport/freight invoices
Why it is useful:
- Transport is a common SME Scope 3 activity and raises real document-understanding challenges.
- It is relevant to the core GreenLedger problem of establishing activity data from business documents.

What can realistically be extracted:
- mode of transport
- distance or trip distance
- weight or load information
- freight charge or fuel unit
- shipment origin/destination if present
- invoice date

Business activity represented:
- outsourced transportation of goods

Public dataset usefulness:
- Generic document datasets help with layout parsing, but do not provide true GHG transport ground truth.

Synthetic documents:
- Yes, for controlled evaluation of extraction and mapping.

Real SME documents:
- Very valuable; actual freight documentation varies widely.

Important restriction:
- v1 will only include selected transport activities with clear, extractable fields and authoritative factor types.
- Broad transport logistics, air travel, and highly ambiguous freight data will remain FUTURE SCOPE.

## 2. Supported carbon activities

For v1, GreenLedger will support a narrow set of carbon-relevant activities mapped to document types.

The canonical structure is:

Document
→ Extracted fields
→ Canonical activity
→ Scope
→ Scope category
→ Required emission factor
→ Calculation method
→ Final CO2e output

### 2.1 Purchased electricity
Document:
- electricity bill / utility invoice

Extracted fields:
- billing period
- total kWh
- supplier or utility
- meter ID or customer ID
- tariff or billed category
- date

Canonical activity:
- purchased electricity

Scope:
- Scope 2

Scope category:
- purchased electricity

Required emission factor:
- electricity emission factor aligned to grid/year/geography

Calculation method:
- activity data (kWh) × electricity EF (kg CO2e/kWh or gCO2e/kWh)

Final CO2e output:
- kg CO2e or t CO2e for the billing period

### 2.2 Diesel fuel purchase
Document:
- diesel receipt or fuel invoice

Extracted fields:
- fuel type = diesel
- quantity in L
- date
- supplier
- vehicle/equipment reference if available

Canonical activity:
- diesel fuel combustion

Scope:
- Scope 1 for direct combustion by company-owned sources; possible Scope 3 if contractual or upstream classification applies

Scope category:
- stationary or mobile combustion; fuel- and energy-related activity as applicable

Required emission factor:
- fuel combustion factor matching fuel type and geography

Calculation method:
- fuel volume × fuel-specific EF for diesel (or fuel mass if required)

Final CO2e output:
- kg CO2e or t CO2e

### 2.3 LPG purchase
Document:
- LPG cylinder refill invoice / LPG receipt

Extracted fields:
- fuel type = LPG
- quantity or cylinder size
- weight/volume if present
- date
- supplier

Canonical activity:
- LPG combustion

Scope:
- Scope 1 for on-site combustion by the organization; possible Scope 3 depending on ownership and use

Scope category:
- stationary combustion or fuel-related activities as applicable

Required emission factor:
- LPG combustion factor by mass or volume, geography-specific, traceable

Calculation method:
- LPG mass or volume × applicable EF

Final CO2e output:
- kg CO2e or t CO2e

### 2.4 Selected purchased materials
Document:
- purchase invoice / material delivery note

Extracted fields:
- material description
- item quantity
- unit of measure
- supplier and date
- item/weight or volume data

Canonical activity:
- selected purchased material

Scope:
- Scope 3

Scope category:
- purchased goods and services (category 1) for selected material classes

Required emission factor:
- material-specific cradle-to-gate or upstream factor by mass or functional unit

Calculation method:
- material quantity × material EF

Final CO2e output:
- kg CO2e or t CO2e for the selected material purchase

### 2.5 Selected transport activity
Document:
- freight bill, logistics invoice, transport receipt

Extracted fields:
- mode of transport
- distance or trip data
- shipment mass or tonne-km if present
- fuel type or freight charge
- origin/destination if present

Canonical activity:
- selected freight transport activity

Scope:
- Scope 3

Scope category:
- upstream or downstream transportation and distribution based on ownership and invoice structure

Required emission factor:
- mode-specific and geography-specific transport factor by distance, fuel, or tonne-km

Calculation method:
- transport activity data × EF (distance-based, fuel-based, or tonne-km-based)

Final CO2e output:
- kg CO2e or t CO2e

## 3. Restricting the initial scope

GreenLedger v1 should not attempt to support every Scope 1/2/3 category. A 4-person final-year project should focus on a small but meaningful set.

### Recommended v1 scope
- purchased electricity
- diesel purchase/activity
- LPG purchase/activity
- selected purchased materials (very small, verified subset)
- selected transport activity (small, well-defined subset)

This is realistic because it gives GreenLedger:

- a meaningful end-user workflow: energy, fuel, materials, and logistics from SME documents
- sufficient technical complexity: extraction + normalization + classification + factor lookup + CO2e calculation + human review
- sufficient document diversity: bills, receipts, purchase invoices, logistics receipts
- realistic data path: public document-understanding datasets plus a small synthetic and real SME validation set
- realistic delivery timeline: 6–9 months if kept small and properly scoped

### Items explicitly excluded from v1
These are marked FUTURE SCOPE:

- all Scope 3 categories beyond the selected materials and transport subset
- employee commuting
- waste disposal and waste treatment
- water use
- refrigerant leakage
- capital goods
- large multi-category procurement data
- complex product-level life-cycle data without clear quantity fields
- broad international taxonomies without authoritative factors

## 4. Exact factor requirements

For each supported activity, GreenLedger must verify the factor type, category, unit, geography, year, provenance, and CO2e eligibility before a numeric record can be used in a calculation.

### Electricity
- Factor type required: grid electricity emission factor
- Factor unit: kg CO2e/kWh or gCO2e/kWh
- Geography: country or grid region; for India the CEA grid factors are relevant
- Applicable year: billing year or historical year matching the activity data
- Source type: CEA for India; other authoritative grid inventories where required
- Method: electricity factor, average or adjusted grid factor depending on use
- Selected source series for the CO2 reference: CEA V22.0 import-adjusted weighted-average grid emission rate including RES/captive generation; it is CO2-only and is not enabled for CO2e calculation. Market-based accounting remains outside the current verified factor set.

### Diesel / fuel
- Factor type required: fuel combustion emission factor
- Factor unit: kg CO2e/L or gCO2e/L, or mass-based equivalent
- Geography: country or local fuel benchmark
- Applicable year: fuel purchase or reporting year
- Source type: national fuel factors, IPCC EFDB, or other authoritative fuel databases
- Method: combustion factor matched to fuel type and fuel use context
- CO2e factor applicability is unresolved: confirm actual combustion, operational control, stationary/mobile source category, GHG coverage, and any required fuel-property conversion before calculation.

### LPG
- Factor type required: LPG combustion factor
- Factor unit: kg CO2e/kg or gCO2e/kg; possibly volume-based in some national databases
- Conditional LPG factor: global IPCC Tier 1 value for commercial/institutional stationary combustion (Scope 1; IPCC 1.A.4.a), per verified net kg and using recorded AR6 GWP100 inputs. It was independently recomputed as 2.99230679 kgCO2e/kg and is calculable only for this exact context. It is not India-specific or year-specific.
- Applicability conditions: owned/controlled stationary combustion, commercial/institutional source category, and verified net mass. A cylinder count requires a printed net fill mass or an authoritative linked supplier specification.
- Other LPG contexts remain unresolved and require an appropriate country/source-category factor. A purchase document alone does not establish fuel combustion or Scope 1.

### Selected purchased materials
- Factor type required: cradle-to-gate upstream material intensity factor
- Factor unit: kg CO2e/kg, kg CO2e/tonne, or equivalent functional unit
- Geography: country or region-specific if available
- Applicable year: relevant year of production or emission factor vintage
- Source type: authoritative life-cycle or sector-specific inventory source; possibly IPCC or material-specific databases
- Method: material quantity × material EF
- Methodological decision still unresolved: which material classes are acceptable for v1 and whether a weight-based material factor is available for each selected item

### Selected transport activity
- Factor type required: mode-specific transport emission factor
- Factor unit: kg CO2e/km, kg CO2e/tonne-km, or kg CO2e/L fuel depending on data type
- Geography: route/region-specific where necessary
- Applicable year: invoice year or transport year
- Source type: national transport or GHG Protocol-aligned guidance; authoritative mode-specific factor sources
- Method: distance-based, fuel-based, or tonne-km-based conversion
- Methodological decision still unresolved: whether v1 uses distance-only, fuel-only, or tonne-km factors, and whether the invoice reflects actual loaded transport or trip-level activity data

## 5. Research feasibility

The dataset and accounting requirements are feasible for a final-year project if GreenLedger v1 stays narrow and explicit:

- small number of document types
- specific extraction targets
- fixed set of activities
- clear scope mapping
- human verification for uncertain fields
- no attempt to support all material classes or all transport modes

## 6. Final v1 recommendation

GreenLedger v1 should support a narrow but useful SME carbon workflow centered on:

- electricity bills
- diesel fuel invoices and receipts
- LPG receipts
- selected purchased material invoices with weight-based extraction
- selected transport/freight bills

Everything else is FUTURE SCOPE.
