# SFC India road diesel factor source

Local source: `India_Default_GHG_Emission_Values_V1.0.pdf` (7 pages), SHA-256 `8D814B6B3D35D40452EF85ABF560D3EE52DE260875E65DDC76AB8801C4DE7FD6`.

The report is titled *India Default GHG Emission Values V1.0 – Complementing GLEC Framework v3.01*, co-developed by Smart Freight Centre India and the TCI-IIMB Supply Chain Sustainability Lab at IIM Bangalore. The PDF is dated May 2025; the SFC source page states publication on June 30, 2026. The publication page describes the values as India-specific road/rail values and says the guideline is to be read with GLEC Framework v3.1.

The catalogue retains the report's Road Transportation / Diesel fuel row as `2.675 kgCO2e/litre`, **tank-to-wheel (TTW)**, rounded to three decimals. Independent recomputation from the table values uses CO2 = 74,100, CH4 = 3.9, N2O = 3.9 kg/TJ, NCV = 43 TJ/Gg, and 1.21 L/kg; with AR6 GWP100 values of 27.0 for fossil methane from combustion and 273 for N2O, the result is `2.674884297520661... kgCO2e/L`, which rounds to `2.675`. Using the report's printed 27.9 methane coefficient instead gives `2.675009033057851... kgCO2e/L`, which also rounds to `2.675`. This is a fuel-volume factor, not the report's freight intensity factor. It does not include WTT and must not be applied to stationary combustion, power-sector fuel activity, non-road equipment, or tonne-kilometre transport calculations. GreenLedger calculation additionally requires confirmed owned/controlled combustion, a road vehicle, and India geography.

## Source caveat

The publication says its values are under development and subject to review/update. On the diesel table page, the nitrogen-species column is printed as `NO2`; the method section calls it `NO2`, while the displayed `27.9*B + 273*C` formula, value 3.9 in that column, and usual combustion-factor meaning suggest a species-label inconsistency. The method prose says CH4 and NO2 are converted using IPCC AR6 GWP100, while the printed methane coefficient is 27.9. GreenLedger preserves the source-reported 2.675 value and does not silently repair those source details. Clarification from the source owner remains advisable; the exact table inputs are not independently substituted into a revised factor.

Official source page: https://smartfreightcentre.org/news/13311661

Direct PDF: https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311661/08ad10f82dca3ef5ff61a81a137d7274.pdf

## India road-freight intensity factors (separate from the diesel fuel factor)

Local source artifact: `SFC_India_TERI_Institutionalizing_Freight_Emissions_Accounting.pdf`.

- Source: Smart Freight Centre (SFC) India and The Energy and Resources Institute (TERI), *Institutionalizing Freight Emissions Accounting in India: Pathways for Clean Freight Programs and Policy Integration* (2026), Table 4, p. 26.
- Official source URL: https://www.teriin.org/sites/default/files/files/SFC-India-TERI.pdf
- Source SHA-256: `366C10E4DDC735EA69B16E4562CC3CBF601EBB51C9E930DBEB47655AB368E7FC`.
- Table 4 gives the India diesel road-freight values as WTW kgCO2e/tonne-km for average load and average empty running. The values used by GreenLedger are 0.3795 (<3.5 t GVW), 0.2222 (3–5 t GVW), 0.1400 (5–12 t GVW), 0.0902 (12–20 t GVW), 0.0823 (20–30 t GVW), 0.0663 (30–50 t GVW), and 0.0551 (30–60 t tractor-trailer GVW).
- The report describes these factors as co-developed by the TCI-IIMB Supply Chain Sustainability Lab with SFC methodology support; road intensity methods follow IPCC, GHG Protocol, and GLEC. Its activity-based equation is distance × shipment weight × intensity factor and it recommends shortest feasible distance for road freight. The reported method also describes a 5% distance-adjustment uplift for out-of-route deviations; GreenLedger does not silently add this uplift to a user-entered distance. Users must provide a reviewed distance consistent with the selected method and evidence.
- These freight WTW factors are separate from the existing 2.675 kgCO2e/L road-diesel TTW fuel factor. They are not fuel factors, are not TTW, and do not apply to stationary combustion or other transport modes. They are eligible only for India road freight with explicit vehicle GVW class, shipment mass, distance, and Scope 3 Category 4/9 business-flow classification.
