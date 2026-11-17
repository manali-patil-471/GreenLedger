> Historical source note: this page describes CEA V21.0 only. CEA V22.0 (August 2026) is now archived locally and supersedes it for current results; see [CEA_V22_RELEVANT_CONTENT.md](CEA_V22_RELEVANT_CONTENT.md).

# CEA CO2 Baseline Database V21.0 - Relevant Content for GreenLedger

File inspected:
- knowledge_base/emission_factors/CO2_Database_V_21.0.xlsx

## 1. Workbook structure and worksheets

The workbook contains the following worksheets:

- Data
- Results
- Transfer (1G)
- Units + Abbrev
- Assumptions

## 2. Which worksheets are relevant to GreenLedger electricity Scope 2 work?

The most relevant worksheets for GreenLedger are:

1. Results
   - This is the main electricity-sector summary sheet.
   - It provides national/grid emission-rate metrics that are directly relevant to purchased-electricity accounting.
   - It includes weighted average emission rate, weighted average grid emission rate, simple operating margin, build margin, combined margin, and imported-power adjustments.

2. Data
   - This is the detailed plant-level and state-level generation/emissions dataset.
   - It is relevant because it contains power-plant operational data which underpins the aggregate grid factors.
   - It is not itself a GreenLedger final emission-factor table, but it is the raw source material used to build the electricity factors.

3. Assumptions
   - This provides fuel emission-factor assumptions, plant assumptions, auxiliary consumption, net heat rate, and other conversion assumptions used in the calculation methodology.
   - Important for understanding how the workbook interprets fuel-use and electricity generation data.

Secondary but useful reference sheets:

- Units + Abbrev
  - units and abbreviations used throughout the workbook

- Transfer (1G)
  - electricity transfer / net transfer information not central to GreenLedger’s initial scope mapping but helpful for understanding system totals

## 3. What the relevant worksheets actually contain

### Results worksheet

This sheet is the clearest candidate for GreenLedger’s initial purchased-electricity factor review.

It includes national annual summary values for:

- Weighted Average Emission Rate
- Weighted Average Grid Emission Rate (with and without imports)
- Simple Operating Margin
- Build Margin
- Combined Margin

Observed annual values in the workbook (for 2020-21 through 2024-25):

- Weighted Average Emission Rate (excl. imports): roughly 0.79 to 0.84 tCO2/MWh
- Weighted Average Grid Emission Rate (incl. imports/res/captive): roughly 0.70 to 0.73 tCO2/MWh
- Simple Operating Margin: roughly 0.94 to 0.97 tCO2/MWh
- Build Margin: roughly 0.51 to 0.87 tCO2/MWh
- Combined Margin: roughly 0.74 to 0.92 tCO2/MWh

The workbook clearly states the baseline methodology used is:

- ACM0002 / Ver 22.0
- Tool to Calculate the Emission Factor for an Electricity System, Version 7.0

It also explains that:

- operating margin is based on the same-year ex post option
- build margin uses a different generation mix
- import adjustments are applied for power exchanged with other grids
- imported power from other countries is treated as zero-emission for the purpose described in the sheet

This is not yet a final GreenLedger factor record, but it is a direct source for electricity-sector grid emission factors that could support Scope 2 analysis for India.

### Data worksheet

The Data sheet is a large plant-level dataset. It includes columns such as:

- S_NO
- NAME
- UNIT_NO
- DT_COMM
- CAPACITY as on 31.03.2025 (MW)
- STATE
- SECTOR
- SYSTEM
- TYPE
- FUEL 1
- FUEL 2
- 2024-25 Net Generation GWh
- 2024-25 FUEL 1 Consumption
- 2024-25 FUEL 2 Consumption
- 2024-25 Absolute Emissions t CO2
- 2024-25 Specific Emissions t CO2/MWh

This sheet is a plant-level database of fossil generation, emissions, and operational characteristics. It is useful for understanding the underlying generation mix and how regional/grid emission factors are derived.

### Assumptions worksheet

This sheet explains the calculations used to build the emission intensity values. It includes:

- fuel emission factors by fuel type
- oxidation factors
- net heat rate assumptions
- gross heat rate assumptions
- auxiliary power consumption assumptions
- specific CO2 emission assumptions by fuel and unit class

Representative fuel assumptions shown in the spreadsheet include:

- Coal: ~90.6 gCO2/MJ (after oxidation factor)
- Imported coal: ~85.2 gCO2/MJ
- Lignite: ~100.5 gCO2/MJ
- Gas: ~49.4 gCO2/MJ
- Oil: ~71.9 gCO2/MJ
- Diesel: ~69.1 gCO2/MJ
- Naptha: ~66 gCO2/MJ

The workbook also provides station- and unit-level assumptions such as:

- auxiliary power consumption percentages
- gross/net heat rates by technology type
- specific oil consumption
- specific CO2 emissions by fuel and unit size

These assumptions are necessary to interpret the electricity-factor tables but are not GreenLedger’s final factor database values.

## 4. Geography and time coverage

The workbook is India-specific. The Data sheet contains:

- state-level and regional attributes
- plant/system ownership information
- plant-level generation and emissions

The Results sheet provides annual values by fiscal year, including:

- 2020-21
- 2021-22
- 2022-23
- 2023-24
- 2024-25

This means the workbook is suitable for India national/grid-level electricity emissions as a function of year, but it does not directly provide a general cross-country emission-factor lookup for all SMEs.

## 5. What the workbook contains by category

The workbook contains, in principle:

- grid-average factors: yes
- weighted-average factors: yes
- regional factors: yes, indirectly through state/system/plant and regional grid structure
- plant-level factors: yes
- operating-margin/build-margin data: yes
- other categories: yes, including captive power, net imports, renewable generation, and fuel assumptions

## 6. What this means for GreenLedger

This workbook is highly relevant to GreenLedger’s initial purchased-electricity calculation path, because it provides an authoritative India electricity baseline and the methodology behind grid emission factors.

However, GreenLedger should not yet use the workbook as a final factor table without verifying:

- the exact factor needed (e.g., grid average vs operating margin vs build margin vs combined margin)
- the geography of the supplier or grid
- the year matching the activity data
- whether the factor is meant to represent a marginal or average grid emission rate
- whether the activity is a purchased-electricity bill, a supplier-specific tariff, or a consumption-based electricity factor

## 7. Important caution

This workbook is not a GreenLedger factor database by itself. It is an authoritative CEA electricity baseline source that may support GreenLedger’s Scope 2 calculations, but it does not yet provide the normalized GreenLedger factor schema required for final records.

We therefore stop here at the source-analysis stage and do not create final numeric emission-factor records yet.
