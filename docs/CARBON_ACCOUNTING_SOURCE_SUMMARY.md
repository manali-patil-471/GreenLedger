# Carbon accounting source summary

Updated: 2026-11-14

This summary distinguishes verified source values from GreenLedger factors that are eligible only under documented activity, geography, unit, year, and category conditions.

| Topic | Authoritative source | Current use and limits |
| --- | --- | --- |
| India electricity CO2 intensity | [CEA CO2 Baseline Database V22.0](https://cea.nic.in/wp-content/uploads/baseline/2026/09/Baseline_Carbon_Dioxide_Emission_Database_Version_22.0.xlsx), with [CEA archive](https://cea.nic.in/cdm-co2-baseline-database/?lang=en) | The selected RES-inclusive weighted-average FY2025-26 row supports a separate CO2-only result path (`kgCO2`); it remains ineligible for CO2e, for which a GHG-complete Scope 2 factor/method is still required. |
| Scope 2 accounting method | [GHG Protocol Scope 2 Guidance (2015)](https://ghgprotocol.org/sites/default/files/2023-03/Scope%202%20Guidance.pdf) and [corrections through April 2025](https://ghgprotocol.org/sites/default/files/2023-03/List%20of%20Corrections%20to%20the%20Scope%202%20Guidance.pdf) | Distinguishes location-based and market-based methods. Market-based evidence is not implemented. |
| LPG direct combustion | IPCC 2006 Guidelines, [Vol.2 Ch.2 Table 2.4](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf), [Vol.2 Ch.1 Table 1.2](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf), and [AR6 GWP100 values](https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_Annex-II.pdf) | Independently recomputed to 2.99230679 kgCO2e/kg LPG and marked `VERIFIED_TIER1_CONDITIONAL` only for IPCC 1.A.4.a commercial/institutional stationary combustion, owned/controlled Scope 1, and verified net mass. Other LPG contexts remain unresolved. Source copies and hashes are under `knowledge_base/standards/ipcc_sources/`. |
| India road diesel TTW | [SFC India V1.0 / TCI-IIMB](https://smartfreightcentre.org/news/13311661), linked methodology PDF | Source-reported 2.675 kgCO2e/L, TTW, conditionally eligible only for India road diesel actually combusted by an owned/controlled vehicle (Scope 1 mobile). Not applicable to stationary/power-sector fuel or freight tonne-km. The publication says the values are subject to review and has a nitrogen-species/GWP notation inconsistency; see the local source note. |
| GWP policy | [GHG Protocol GWP amendment](https://ghgprotocol.org/sites/default/files/2022-12/Required%20gases%20and%20GWP%20values_0.pdf) and IPCC AR6 | The retained LPG candidate derivation records AR6 GWP100 values; the final selected combustion context/GWP100 basis still requires independent revalidation and approval. |
| Diesel power-sector combustion | CEA V22.0 Assumptions sheet | Catalogue includes NCV and GCV CO2-only factors (72.6 and 69.14285714285714 gCO2/MJ). They remain power-sector source references, not SME litre-based factors; no litre-to-energy basis is selected. |
| Purchased materials and transport | [GHG Protocol Scope 3 Guidance](https://ghgprotocol.org/scope-3-calculation-guidance-2) | Informs category logic only. The material subset, transport mode, factor sources, and matching activity bases remain unresolved. |
| Generic document understanding | Local FATURA and CORD samples | May support generic document/OCR work only. Neither provides GreenLedger carbon ground truth. SROIE remains unused pending access and terms approval. |

## Factor status

- **Conditional CO2e factors:** LPG is eligible only for the exact IPCC 1.A.4.a stationary context and verified mass. India road diesel is eligible only for confirmed India road/mobile TTW context. Neither is a generic fuel factor.
- **CO2-only references:** CEA electricity supports a separate location-based CO2 calculation for FY2025-26; it remains blocked from CO2e. CEA diesel energy-basis assumptions are not used for calculation.
- **Unresolved:** electricity CO2e; stationary/power-sector diesel CO2e and L-to-energy conversion; LPG outside IPCC 1.A.4.a and cylinder-count-to-mass conversion; exact selected purchased materials; exact transport mode/category/activity/factor.

## Classification constraints

Electricity requires purchased/acquired electricity consumed in the organization's operation. Diesel and LPG require confirmation that fuel was combusted by an owned/controlled source before Scope 1 classification. A purchase receipt alone does not establish combustion or scope. Purchased materials require an approved Category 1 subset and matching upstream cradle-to-gate factor. Transport requires the service boundary, mode, and business flow needed to distinguish the relevant category; charges are not activity quantities.

No benchmark performance, model accuracy, or real-SME result is claimed by this source summary.
