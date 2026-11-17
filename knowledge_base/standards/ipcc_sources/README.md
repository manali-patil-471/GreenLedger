# IPCC factor source copies

These files are local copies of official IPCC sources used to independently recompute and conditionally verify the LPG Tier 1 factor in `knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv`. The factor is eligible only for the matching commercial/institutional stationary combustion context (IPCC 1.A.4.a), with confirmed owned/controlled Scope 1 combustion and verified net LPG mass. Its value is computed from source inputs and is not copied from an online calculator.

| Local file | Source/version and use | Official URL | SHA-256 |
| --- | --- | --- | --- |
| `IPCC_2006_Vol2_Ch1_Introduction.pdf` | 2006 IPCC Guidelines, Vol.2 Ch.1 Table 1.2; LPG NCV 47.3 TJ/Gg, lower/upper 44.8/52.2 | https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf | `E391CD4676D0891CD77F67D3BD76E0E6775386B468CE5CE7EBE2311A6EA1AC45` |
| `IPCC_2006_Vol2_Ch2_Stationary_Combustion_corrected.pdf` | 2006 IPCC Guidelines, Vol.2 Ch.2 corrected stationary-combustion tables; Table 2.4 LPG row for commercial/institutional combustion | https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf | `A25D9F96D7672DF391B328DE79D4CFD812C07FE79D5CF4A30D23D82D8F02985B` |
| `IPCC_AR6_WGIII_Annex_II.pdf` | IPCC AR6 WGIII Annex II, Table 9; 100-year GWP values of 27.0 for fossil methane from combustion and 273 for N2O | https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_Annex-II.pdf | `5CC3EE5E6E27D176E8EDB8A0038C35698388606F6F6D494A039AA479B9211DC9` |
| `../GHG_Protocol_Required_Gases_and_GWP_Values_Amendment.pdf` | GHG Protocol amendment supporting the use of 100-year IPCC GWPs and recommending values from the most recent assessment report | https://ghgprotocol.org/sites/default/files/2022-12/Required%20gases%20and%20GWP%20values_0.pdf | `2BC8B42D4CB94D1F74AE477F3BFAF3EB7AB55F216F575050EBDD67C9447A3A7F` |

The 2006 IPCC Guidelines call Table 2.4 default emission factors for stationary combustion in the commercial/institutional category, on a net calorific basis. The 2006 Vol.2 page identifies Chapter 2 as corrected in April 2007. Source uncertainty ranges are retained in the factor catalogue notes; they have not been propagated to a combined interval.

Independent derivation (Decimal arithmetic): NCV = 47.3 TJ/Gg = 47.3 MJ/kg; CO2 = 63,100 kg/TJ; CH4 = 5 kg/TJ; N2O = 0.1 kg/TJ; AR6 GWP100 = 27.0 for fossil methane from combustion and 273 for N2O. Thus `(63,100 + 5×27.0 + 0.1×273) kgCO2e/TJ × 47.3 MJ/kg ÷ 1,000,000 MJ/TJ = 2.99230679 kgCO2e/kg LPG`. The recomputed value exactly equals the catalogue value. This does not validate applicability outside the stated IPCC stationary category or turn a cylinder count into verified mass.
