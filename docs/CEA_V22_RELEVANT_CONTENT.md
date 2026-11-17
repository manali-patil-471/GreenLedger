# CEA CO2 Baseline Database V22.0 ? GreenLedger source audit

Accessed and locally saved: 2026-09-24. CEA publication: August 2026. Source: Central Electricity Authority, Government of India.

## Source files

- Workbook: `knowledge_base/emission_factors/CO2_Database_V_22.0.xlsx`
- Guide: `knowledge_base/emission_factors/User_Guide_V_22.0.pdf`
- Official archive: https://cea.nic.in/cdm-co2-baseline-database/?lang=en
- Workbook download: https://cea.nic.in/wp-content/uploads/baseline/2026/09/Baseline_Carbon_Dioxide_Emission_Database_Version_22.0.xlsx
- Guide download: https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf
- Workbook SHA-256: `F2341EFE03D2FCE4177A4A7090B8A946A5AC5AE32B41D784882D0226F2EB4860`
- Guide SHA-256: `723331B2ADD30754B8794D57DC05126218B3489F9F87CE3E570D5659BDC9D3B0`

## Scope and data

V22.0 adds FY2025-26 and revises earlier results, including FY2024-25. The guide describes the average as emissions from all grid stations weighted by net generation and reports it with renewable energy and captive power injection, adjusted for cross-border transfers. The guide's Appendix C Table B gives 0.675 tCO2/MWh for FY2025-26 including transfers; the workbook's Results sheet provides the unrounded value.

The GreenLedger catalogue records the Results sheet's import-adjusted `Weighted Average Grid Emission Rate (Incl. RES,Captive)` series for FY2020-21 through FY2025-26:

| Fiscal year | tCO2/MWh (same numeric value as kgCO2/kWh) |
| --- | ---: |
| 2020-21 | 0.6975385713186759 |
| 2021-22 | 0.7113500285903359 |
| 2022-23 | 0.7160031593941543 |
| 2023-24 | 0.7271599041096539 |
| 2024-25 | 0.7101023036210137 |
| 2025-26 | 0.6750986831448641 |

The source reports CO2, not CO2e. These values are not eligible for GreenLedger CO2e calculations. The catalogue marks this restriction explicitly.

## Method choice and limits

- The selected series is the grid-average CO2 reference for location-based purchased-electricity reporting; the import-adjusted series follows CEA's Appendix C/Table S presentation.
- `Weighted Average Emission Rate`, Simple Operating Margin, Build Margin, and Combined Margin remain distinguishable source values. The latter three are CDM baseline methods and are not the default location-based reporting factor.
- CEA V22.0 supersedes the locally retained V21.0 workbook for current factor vintage. V21.0 remains for historical provenance only.
- This source does not supply a complete CO2e grid intensity, so the v1 CO2e factor requirement remains unresolved pending a GHG-complete authoritative source and explicit method.
