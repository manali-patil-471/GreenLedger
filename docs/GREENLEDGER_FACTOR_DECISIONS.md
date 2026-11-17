# GreenLedger factor and methodology decision log

Updated: 2026-11-14

This record keeps verified source values separate from factors that are safe to use for GreenLedger CO2e calculations. The frozen v1 document/activity scope is unchanged.

## Electricity

- Source refreshed to CEA CO2 Baseline Database V22.0 (August 2026), which supersedes the local V21.0 workbook for the newest published fiscal year and revises some prior-year values.
- Selected reference series for a location-based grid-average **CO2** factor: Results sheet, `Weighted Average Grid Emission Rate (Incl. RES,Captive)`, import-adjusted series. It reports 0.675098683 tCO2/MWh for FY2025-26; tCO2/MWh is numerically equal to kgCO2/kWh.
- CEA labels its database and factors as CO2. These values are **not CO2e factors**. The selected series is therefore a verified CO2 reference only and is blocked from GreenLedger's CO2e calculation path until a GHG-complete source/method is verified.
- The earlier decision to use `Weighted Average Emission Rate` as the location-based default is revised: the guide's Appendix C identifies the RES-inclusive weighted-average series, adjusted for cross-border electricity transfers, as the grid-average reference. CEA operating/build/combined margins remain research alternatives and are not the default location-based factor.
- Location-based versus market-based treatment follows the published 2015 GHG Protocol Scope 2 Guidance and its correction record through April 2025 (local files under `knowledge_base/standards/`). The GHG Protocol page reported a public consultation in 2025-26; re-check for a final replacement before future factor release. Market-based calculation is not implemented; it requires qualifying contractual instruments or applicable market data.

## Diesel

- CEA V22.0 Assumptions lists diesel CO2 values of 72.6 gCO2/MJ on an NCV basis and 69.14285714285714 gCO2/MJ on a GCV basis; the guide says imported-fuel assumptions are based on IPCC 2006.
- These source values are recorded for traceability as CO2-only power-sector assumptions. They are not verified as complete SME stationary/mobile combustion CO2e factors.
- Do not convert invoice litres to MJ using an unverified density/calorific value. Do not calculate CO2e without the applicable source-category factors for all relevant gases and a documented GWP basis. Fuel purchase also needs confirmation that it was combusted by a source inside the organization's boundary.
- The CEA diesel NCV versus GCV assumption and its use for SME stationary/mobile fuel activity remain unresolved; the separate SFC road/mobile factor below does not resolve those CEA power-sector assumptions.
- A separate SFC India V1.0 / TCI-IIMB road diesel row is recorded at **2.675 kgCO2e/L, TTW**. Using the source table inputs and AR6 combustion GWP100 yields 2.674884297520661... kgCO2e/L, rounded to the source's 2.675; using the table's printed methane coefficient 27.9 also rounds to 2.675. It is conditionally eligible only for India road-vehicle diesel actually combusted by an owned/controlled source (Scope 1, mobile combustion). It is not a stationary or power-sector factor and does not include WTT. The report marks values as subject to review and contains a nitrogen-species/GWP notation inconsistency; the catalogue preserves the printed rounded factor and documents the calculation caveat. Source copy, URL, version, and hash are under `knowledge_base/standards/sfc_india/`.

## LPG

- The factor applies only to LPG actually combusted in a commercial/institutional stationary source (IPCC 1.A.4.a) under a confirmed owned/controlled Scope 1 boundary. Its IPCC 2006 Table 2.4 gas factors, Table 1.2 NCV, and selected IPCC AR6 GWP100 values were independently recomputed in Decimal arithmetic; the result is exactly 2.99230679 kgCO2e/kg LPG. Its catalogue status is `VERIFIED_TIER1_CONDITIONAL`. It is global and not year-specific. Other source categories/geographies remain unresolved. Cylinder-count conversion still requires printed net fill mass or an authoritative linked supplier specification.
- Keep LPG unresolved for invoices without use/boundary/source-category context and for residential/non-commercial, mobile, feedstock, or other nonmatching contexts. The existing synthetic LPG annotations have no scope/source context and correctly contain no CO2e targets.

## Selected purchased materials

- Phase 3 enables only the three selected CPWD 2024 generic/reference rows: PPC cement 0.760, steel rebar 3.450, and generic steel 2.100 kgCO2e/kg. The CPWD source table specifies 30% fly ash for the PPC row, cites an Ambuja EPD for PPC and a Jindal Steel EPD for rebar, and states generic steel is a weighted average of BOF, DRI, and EAF. These remarks are retained in catalogue provenance; the GreenLedger rows are used as generic/reference values per the project decision and do not perform supplier-specific EPD matching.
- Applicability is Scope 3 Category 1, India, cradle-to-gate, with exact product identity and physical mass required. “Steel” alone is ambiguous; rebar and generic steel never substitute for one another. Only g/kg/tonne SI scaling is supported. No other materials are enabled.
- The CPWD PDF, official source URL, local source hash, and table location are recorded under `knowledge_base/standards/cpwd/`; catalogue validation checks factor value, product class, applicability, provenance, and source checksum. The former empty future row now applies only to materials outside this three-product subset.

## Selected transport/freight

- Phase 3 enables only India road freight, using seven diesel WTW factors from SFC India/TERI 2026 Table 4: <3.5 t GVW 0.3795, 3–5 t 0.2222, 5–12 t 0.1400, 12–20 t 0.0902, 20–30 t 0.0823, 30–50 t 0.0663, and 30–60 t tractor-trailer 0.0551 kgCO2e/tonne-km.
- Calculation is distance (km) × shipment mass (tonnes) × class factor. Explicit India geography, road mode, exact vehicle class, mass, distance, and existing Scope 3 Category 4/9 business-flow conditions are required. Exact kg→tonne and m→km conversions are implemented; freight price, missing inputs, ambiguous classes, company-controlled transport, and other modes do not calculate.
- These are WTW freight intensity values, not the separate SFC V1.0 road-diesel TTW factor. Source PDF, URL, version, and SHA-256 are pinned under `knowledge_base/standards/sfc_india/`. The report discusses a 5% out-of-route distance adjustment; GreenLedger does not add it automatically, and the entered distance must be reviewed against source method/evidence.
- The former empty future row now applies only to other modes/services outside these seven India road classes.

## Catalogue correction record

The previous catalogue contained blank/`nan` year values and an erroneous 2024-25 Build Margin value copied from the workbook's Net Generation row. The previous default electricity series also did not match the selected RES-inclusive grid-average method. The catalogue now records CEA V22.0 source values for FY2020-21 through FY2025-26, preserves alternatives as CO2-only reference values, and marks every CO2-only or unresolved record so it cannot be mistaken for a verified CO2e factor. Source checksum and direct official download URL are recorded in the catalogue and `metadata/SOURCES.md`.
