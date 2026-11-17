# GreenLedger v1 calculation methods and gating rules

Updated: 2026-11-14

## Calculation eligibility rule

GreenLedger keeps CO2 and CO2e as distinct outputs. A CO2-only factor such as `kgCO2/kWh` or `gCO2/MJ` is not a CO2e factor and must never enter the CO2e path. Retrieval must require an explicitly eligible, authoritative catalogue record with matching activity, quantity/factor basis, geography, applicable year, scope/category, and methodology. Otherwise return `FACTOR_NOT_VERIFIED` or the catalogue's unresolved status.

Never allow an AI component to select a factor value, perform the factor lookup, or generate a CO2e result.

## Purchased electricity

- CO2 reference: CEA V22.0 Results sheet, `Weighted Average Grid Emission Rate (Incl. RES,Captive)`, import-adjusted series.
- Source units: tCO2/MWh. Conversion: `1 tCO2/MWh = 1 kgCO2/kWh` numerically.
- For a CO2-only result: `CO2_kg = activity_kWh * factor_kgCO2_per_kWh`.
- The application has a separate deterministic CO2-only path for the selected CEA V22.0 FY2025-26 location-based weighted-average row (0.6750986831448641 kgCO2/kWh). Its output is labeled `kgCO2`; the separate CO2e lookup continues to abstain.
- This source does **not** provide a CO2e factor. The GHG Protocol Scope 2 Guidance distinguishes grid-average from marginal factors and market-based contractual-instrument methods. Do not label this CO2-only intermediate/result as CO2e or use it for an end-to-end GreenLedger CO2e record. A GHG-complete Scope 2 factor/method is still required.
- Match a factor to the billing fiscal year and India grid geography. Market-based accounting requires separate contractual data and is not supported by this catalogue entry.

## Diesel fuel

- CEA V22.0 lists diesel factors of 72.6 gCO2/MJ (NCV) and 69.14285714285714 gCO2/MJ (GCV) in Assumptions.
- Those source values are CO2-only power-sector assumptions. They are not a complete SME mobile or stationary combustion CO2e factor.
- If activity data is in litres, do not calculate energy without authoritative, basis-matched MJ/L data. Do not substitute density, NCV, GCV, or a vehicle-class assumption without source documentation.
- A CO2e calculation also needs the combustion source category and applicable factors for all relevant gases, plus a documented GWP version. Fuel purchase must not be assumed to equal fuel combusted without an explicit activity-boundary rule.
- A separate SFC India road/mobile diesel TTW factor (2.675 kgCO2e/L) is conditionally eligible only for diesel actually combusted by an owned/controlled India road vehicle. It is not the freight tonne-kilometre factor and cannot be used for stationary or power-sector activity. Its source caveat is documented in `knowledge_base/standards/sfc_india/README.md`.

## LPG

The retained factor was independently recomputed from the documented IPCC combustion inputs and AR6 GWP100 basis. Its catalogue status is `VERIFIED_TIER1_CONDITIONAL`; it is eligible only for verified net kg actually combusted by an owned/controlled commercial or institutional stationary source (IPCC 1.A.4.a). It remains global, not India-specific, and is not a general factor for all LPG purchases or appliances.

The source factor inputs are on a net-calorific energy basis:

| Component | Source value | Basis and source |
| --- | ---: | --- |
| LPG NCV | 47.3 MJ/kg (lower/upper: 44.8/52.2) | IPCC 2006 Vol.2 Ch.1 Table 1.2; TJ/Gg is numerically equal to MJ/kg |
| CO2 | 63,100 kg/TJ (61,600/65,600) | IPCC 2006 Vol.2 Ch.2 Table 2.4, LPG row, commercial/institutional category |
| CH4 | 5 kg/TJ (1.5/15) | Same IPCC Table 2.4 row |
| N2O | 0.1 kg/TJ (0.03/0.3) | Same IPCC Table 2.4 row |
| CH4 GWP100 | 27.0 | IPCC AR6, fossil methane from combustion |
| N2O GWP100 | 273 | IPCC AR6 |

The retained candidate derivation uses AR6 values as its recorded GWP100 basis. The GHG Protocol amendment requires 100-year IPCC GWPs and recommends the most recent assessment report, but this candidate's final combustion context and GWP100 basis still require independent revalidation and approval. Its point value was derived deterministically as follows:

```text
kgCO2e/kg LPG
= 47.3 MJ/kg * (63,100 kgCO2/TJ + 5 kgCH4/TJ * 27.0 + 0.1 kgN2O/TJ * 273) / 1,000,000 MJ/TJ
= 2.99230679 kgCO2e/kg LPG
```

This arithmetic is the factor derivation used for the narrow eligible context. A cylinder count can be converted to mass only from printed net fill mass or an authoritative linked supplier specification. The listed NCV and component-factor ranges are retained as source evidence; they have not been combined or propagated into a statistical factor interval.

Primary factor PDF: [IPCC 2006 Vol.2 Ch.2, corrected stationary combustion chapter](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf). Supporting sources: [IPCC 2006 Vol.2 Ch.1](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf), [IPCC AR6 Annex II, GWP100 Table 9](https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_Annex-II.pdf), and [GHG Protocol Required Gases and GWP Values Amendment](https://ghgprotocol.org/sites/default/files/2022-12/Required%20gases%20and%20GWP%20values_0.pdf). Local copies and SHA-256 hashes are listed in `knowledge_base/standards/ipcc_sources/README.md`.

The current synthetic LPG annotations do not establish combustion, organizational control, and commercial/institutional stationary context; their unresolved factor/review labels therefore remain correct. No LPG CO2e target is currently present in that benchmark release.

## Selected purchased materials

The catalogue enables only three generic/reference factors from CPWD's *Reducing Carbon Footprint in Buildings* (2024), Chapter 1 table on printed p. 11: PPC cement 0.760, steel rebars 3.450, and generic steel 2.100 kgCO2e/kg. They are recorded with Scope 3 Category 1, India, the CPWD source year, a cradle-to-gate GreenLedger boundary, source hash, and exact product class. The source remarks say PPC is 30% fly ash and cites an Ambuja EPD, the rebar row cites a Jindal Steel EPD, and generic steel is weighted across BOF/DRI/EAF; these provenance notes are retained. GreenLedger treats the selected rows as generic/reference factors per the project decision and does not perform supplier-specific EPD matching. Only exact product identity plus mass quantity is accepted; “steel” alone is ambiguous. Use documented g/kg/tonne scaling only; monetary-only, piece, box, or length values do not calculate.

## Selected transport/freight

The catalogue enables India road freight only, using seven diesel WTW kgCO2e/tonne-km factors from SFC India / TERI (2026), Table 4 p. 26: <3.5 t GVW 0.3795; 3–5 t 0.2222; 5–12 t 0.1400; 12–20 t 0.0902; 20–30 t 0.0823; 30–50 t 0.0663; 30–60 t tractor-trailer 0.0551. Calculation requires an explicit supported vehicle GVW class, shipment mass, distance, India geography, road mode, and Scope 3 Category 4/9 business flow. Exact kg→tonne and m→km SI conversions occur before multiplying tonne-km by the factor. No generic fallback, route inference, mass inference, other mode, or company-controlled transport calculation is enabled. The source methodology recommends shortest-feasible road distance and mentions a 5% out-of-route deviation adjustment; the baseline does not silently add it, so the entered reviewed distance must follow the selected method and evidence.

## Trace and review requirements

Every future calculation record must retain factor ID, factor value/unit, geography, applicable year, source/version/URL/checksum, methodology, every unit-conversion input, normalized activity, extracted evidence, source-factor uncertainty data, and review decision. Missing factor, mismatched units, ambiguous quantity, or missing boundary data blocks calculation and triggers human review.
