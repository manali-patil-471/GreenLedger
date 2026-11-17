# GreenLedger Field Specification

This specification defines the exact fields that GreenLedger v1 intends to annotate and evaluate for the chosen document types. The purpose is to separate
-
  observed document text,
- normalized canonical values,
- derived carbon-accounting fields,
- benchmark ground truth.

Key principle: invoice amount is not the same as activity quantity. Monetary amount may be present in the document but is not necessarily the quantity used to compute emissions.

## 1. Shared annotation principles

For every document type, annotate both:
- the field as it appears in the document (raw/extracted value), and
- the normalized field used in GreenLedger calculations.

A field should be marked as:
- directly visible / OCR-extractable,
- indirectly derivable from context,
- derived from a standard or factor lookup,
- not applicable for the document type.

## 2. Electricity bill

### Required fields
- utility_supplier_name
  - type: string
  - units: n/a
  - direct: yes
  - examples: DISCOM name, utility provider, supply company
- billing_period_start
  - type: date
  - units: date
  - direct: yes
- billing_period_end
  - type: date
  - units: date
  - direct: yes
- total_consumption_kwh
  - type: number
  - units: kWh
  - direct: yes
  - aliases: units consumed, energy consumed, kWh billed
- meter_or_account_id
  - type: string
  - units: n/a
  - direct: yes
- tariff_category
  - type: string
  - units: n/a
  - direct: maybe
- document_amount_inr
  - type: number
  - units: INR
  - direct: yes
  - note: useful for billing context, but not the same as energy quantity
- activity_quantity_kwh
  - type: number
  - units: kWh
  - direct: yes or derived from bill totals
  - affects CO2e: yes

### Optional fields
- unit_charge
- contract_type
- taxes and dues
- LED or meter reading details

### Manual verification
- required when kWh is missing, unclear, or the bill is partially OCR-corrupted

### Derived fields for CO2e
- scope = Scope 2
- scope_category = purchased electricity
- factor_type = grid electricity factor
- factor_unit = kgCO2e/kWh or gCO2e/kWh

## 3. Diesel fuel receipt or invoice

### Required fields
- fuel_type
  - type: string
  - units: n/a
  - direct: yes
  - acceptable variants: diesel, HSD, high-speed diesel, diesel fuel
- fuel_quantity_liters
  - type: number
  - units: litres (L)
  - direct: yes
  - aliases: L, Litres, Lt, qty
- invoice_date
  - type: date
  - units: date
  - direct: yes
- supplier_name
  - type: string
  - units: n/a
  - direct: yes
- amount_paid
  - type: number
  - units: currency
  - direct: yes
  - not used directly as activity quantity unless no fuel volume is provided

### Optional fields
- vehicle_or_equipment_id
- fuel_grade
- tax details
- receipt number

### Derived fields for CO2e
- scope = Scope 1 or relevant fuel-related category depending on boundary
- scope_category = fuel combustion activity
- factor_type = fuel combustion factor
- factor_unit = kgCO2e/L or equivalent

## 4. LPG receipt or invoice

### Required fields
- fuel_type
  - type: string
  - units: n/a
  - direct: yes
  - acceptable variants: LPG, cooking gas, commercial LPG, refilled cylinder
- quantity_or_cylinder_size
  - type: number
  - units: kg or cylinder count
  - direct: yes; convert count to mass only with printed net fill mass or linked authoritative supplier specification
- unit_of_measure
  - type: string
  - units: kg, kg/cylinder, cylinder quantity
  - direct: yes
- invoice_date
  - type: date
- supplier_name
  - type: string

### Optional fields
- cylinder number
- refill count
- tax and service charges

### Derived fields for CO2e
- scope = Scope 1 only when LPG was combusted by an owned/controlled stationary source; otherwise resolve from actual activity and boundary
- scope_category = stationary combustion when context supports it
- factor_type = LPG combustion factor
- factor_unit = kgCO2e/kg or equivalent
- conditional catalogue factor = global IPCC Tier 1 commercial/institutional stationary default; requires verified net mass and IPCC 1.A.4.a context

## 5. Selected purchased materials invoice

### Required fields
- supplier_name
  - type: string
- invoice_date
  - type: date
- material_description
  - type: string
  - direct: yes
  - exact supported material/product subset: pending approval; this list is not a declaration that any named material is supported
- material_quantity
  - type: number
  - units: physical invoice quantity; normalize to kg only with exact unit scaling or a verified product-specific mass conversion
  - direct: yes
- material_unit
  - type: string
  - direct: yes
- material_category
  - type: string
  - direct or derived

### Optional fields
- item code
- batch or lot identifier
- origin country
- price per unit
- total invoice amount

### Critical distinction
- item price is not the activity quantity.
- material quantity must be converted to a normalized mass-based unit when the factor requires mass.

### Derived fields for CO2e
- scope = Scope 3
- scope_category = purchased goods and services (selected material subset)
- factor_type = upstream material factor
- factor_unit = kgCO2e/kg or similar functional unit

## 6. Selected transport / freight bill

### Required fields
- transport_mode
  - type: string
  - direct: yes
  - exact supported mode(s): pending selection; generic labels such as freight or logistics do not identify a mode
- distance_km
  - type: number
  - units: km
  - direct: yes, or from a linked source record with provenance; never inferred from a route description alone
- shipment_mass
  - type: number
  - units: kg or tonne
  - direct: yes, when available
- tonne_km
  - type: number
  - units: tonne-km
  - direct: yes, or calculated from verified mass and distance with documented unit scaling
- invoice_date
  - type: date
- supplier_name / logistics provider
  - type: string

### Optional fields
- origin and destination
- trip number
- fuel type used
- freight value

### Derived fields for CO2e
- scope = Scope 3
- scope_category = relevant transport category
- factor_type = transport activity factor
- factor_unit = kgCO2e/km, kgCO2e/tonne-km, or kgCO2e/L fuel

## 7. Fields that are explicitly not GreenLedger activity quantities

These fields may be present in invoices but should not be treated as emission activity quantities unless the document explicitly shows a measured energy or material quantity:
- invoice total amount
- tax amount
- discount amount
- line-item price
- payment terms
- due date
- account balance
- purchase order number alone

## 8. Annotation and review rules

For every document:
- record raw field values and their source text,
- record normalized value and unit,
- record whether the field is directly visible or derived,
- record whether a human reviewer is required,
- store the final benchmark ground truth separately from extracted predictions.

## 9. Benchmark annotation contract

Use `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json` as the record contract. Each record must include document identity, document/source type, explicit task coverage, source reference, ground truth for covered tasks, and annotation validation status. Do not require a carbon activity, scope, factor, or CO2e result on a generic public document that has no such ground truth.

For GreenLedger carbon tasks, annotate the activity, quantity/unit, scope/category context, evidence, factor status, calculation status, and review truth only where the document/scenario supports them. Mark missing or ambiguous information explicitly. Include `expected_co2e` only when a verified CO2e factor and every required conversion are available; otherwise record an unresolved factor/calculation status and reason. A CO2-only factor reference is not a CO2e result.
