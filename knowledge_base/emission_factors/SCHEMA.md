# Emission-factor catalogue schema and eligibility rules

The canonical CSV column order is recorded in `schema.csv`. `GREENLEDGER_V1_FACTOR_CATALOGUE.csv` uses this schema, and `scripts/validate_factor_catalogue.py` enforces structural and source-specific invariants.

## Structured applicability fields

| Field | Meaning and validation |
| --- | --- |
| `gas_basis` | `CO2` for CO2-only factors or `CO2e` for GHG-complete factors expressed as CO2-equivalent. It must agree with `factor_unit`; CO2-only rows cannot receive a CO2e-calculable status. |
| `system_boundary` | Controlled boundary/method identifier, such as `SCOPE2_LOCATION_BASED_GRID_AVERAGE`, `SCOPE1_STATIONARY_COMBUSTION_1A4A`, or `SCOPE1_ROAD_MOBILE_TTW`. A calculable row cannot use `UNRESOLVED`. |
| `geography_code` | Machine-readable geography against which the factor is applicable, such as `INDIA_GRID`, `GLOBAL`, or `INDIA`. Calculation-time retrieval must match required contextual geography. |
| `applicable_period` | Explicit period such as `FY2025-26`, or `NOT_YEAR_SPECIFIC`. A calculable row cannot use `UNRESOLVED`; time-specific retrieval requires a matching submission period. |
| `methodology_id` | Stable identifier for the source method and boundary. A calculable row cannot use `UNSELECTED`. Human-readable derivation remains in `methodology`. |
| `vehicle_class` | Vehicle-class applicability or `NOT_APPLICABLE`. A factor that requires a road vehicle must receive that class in the submission context. |
| `product_class` | Fuel/product class such as `LPG_FUEL`, `ROAD_DIESEL`, or `GRID_ELECTRICITY`. It is checked by the applicable retrieval path. |
| `source_sha256` | Uppercase SHA-256 of the pinned local source used for the factor. Calculable rows must point to an existing source hash listed in the validator's source manifest. |

Calculable rows also require nonempty `source`, `source_version`, `source_url`, and `methodology`. When a derivation depends on multiple publications, the factor's detailed derivation note and source documentation must identify every input source; the validator pins and checks the local source files.

## Current narrow eligibility rules

- CEA V22 electricity is `CO2` and can only produce a separate `kgCO2` result for purchased/consumed electricity with `INDIA_GRID` and matching `FY2025-26` context. It must never enter the `kgCO2e` path.
- The LPG `CO2e` row is conditional on verified net kg actually combusted by an owned/controlled commercial/institutional stationary source (IPCC 1.A.4.a). It is global and not year-specific; cylinder count alone is not mass.
- The SFC India diesel `CO2e` row is conditional on actual owned/controlled India road-vehicle combustion and is TTW only. It is not for stationary/power-sector fuel, non-road equipment, or freight tonne-km.
- CEA diesel rows remain CO2-only power-sector references; the road factor does not replace them.
- Purchased materials are limited to three CPWD 2024 generic/reference rows: PPC cement (source row specifies 30% fly ash), steel rebars, and generic steel. Exact product identity and physical mass are mandatory; there is no substitution among material factors.
- Selected transport is limited to seven explicit India road-freight GVW classes using SFC India/TERI 2026 WTW factors. Road mode, class, geography, distance, shipment mass, and the existing Scope 3 Category 4/9 business-flow decision are mandatory. These factors cannot be used for company-controlled vehicles or other modes.
