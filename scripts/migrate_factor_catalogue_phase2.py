"""Add Phase 2 applicability metadata and the source-reported India road diesel row."""

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv"
SCHEMA = ROOT / "knowledge_base/emission_factors/schema.csv"
LPG_ID = "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6"
ROAD_DIESEL_ID = "sfc_india_v1_road_diesel_ttw"
ROAD_DIESEL_URL = (
    "https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/"
    "communication_news/13311661/08ad10f82dca3ef5ff61a81a137d7274.pdf"
)
ROAD_DIESEL_SHA256 = "8D814B6B3D35D40452EF85ABF560D3EE52DE260875E65DDC76AB8801C4DE7FD6"
STRUCTURED_COLUMNS = [
    "gas_basis", "system_boundary", "geography_code", "applicable_period",
    "methodology_id", "vehicle_class", "product_class",
]


def row_metadata(row):
    factor_id = row["factor_id"]
    activity = row["normalized_activity"]
    factor_unit = row["factor_unit"].casefold()
    row["gas_basis"] = "CO2e" if "co2e" in factor_unit else "CO2"
    row["applicable_period"] = (
        row["applicable_year"] if row["applicable_year"].startswith("FY")
        else "NOT_YEAR_SPECIFIC" if "Not year-specific" in row["applicable_year"]
        else "UNRESOLVED"
    )
    row["vehicle_class"] = "NOT_APPLICABLE"
    row["product_class"] = "UNRESOLVED"
    row["system_boundary"] = "UNRESOLVED"
    row["geography_code"] = "UNRESOLVED"
    row["methodology_id"] = "UNSELECTED"

    if activity == "purchased_electricity":
        row["product_class"] = "GRID_ELECTRICITY"
        row["geography_code"] = "INDIA_GRID"
        if "weighted_average_grid_emission_rate_incl_res_captive_" in factor_id:
            row["system_boundary"] = "SCOPE2_LOCATION_BASED_GRID_AVERAGE"
            row["methodology_id"] = "CEA_V22_WEIGHTED_AVERAGE_GRID_INCL_RES_CAPTIVE"
        elif "simple_operating_margin_" in factor_id:
            row["system_boundary"] = "CEA_GRID_BASELINE_REFERENCE"
            row["methodology_id"] = "CEA_V22_SIMPLE_OPERATING_MARGIN"
        elif "build_margin_" in factor_id:
            row["system_boundary"] = "CEA_GRID_BASELINE_REFERENCE"
            row["methodology_id"] = "CEA_V22_BUILD_MARGIN"
        elif "combined_margin_" in factor_id:
            row["system_boundary"] = "CEA_GRID_BASELINE_REFERENCE"
            row["methodology_id"] = "CEA_V22_COMBINED_MARGIN"
        else:
            row["system_boundary"] = "CEA_GRID_BASELINE_REFERENCE"
            row["methodology_id"] = "CEA_V22_WEIGHTED_AVERAGE_NON_RES_CAPTIVE"
    elif activity == "diesel_fuel" and factor_id.startswith("cea_v22_"):
        row["system_boundary"] = "CEA_POWER_SECTOR_FUEL_ASSUMPTION"
        row["geography_code"] = "INDIA_POWER_SECTOR"
        row["product_class"] = "DIESEL_FUEL"
        row["applicable_period"] = "NOT_YEAR_SPECIFIC"
        row["methodology_id"] = (
            "CEA_V22_DIESEL_CO2_NCV" if factor_id.endswith("_ncv")
            else "CEA_V22_DIESEL_CO2_GCV"
        )
    elif activity == "lpg" and factor_id == LPG_ID:
        row["system_boundary"] = "SCOPE1_STATIONARY_COMBUSTION_1A4A"
        row["geography_code"] = "GLOBAL"
        row["applicable_period"] = "NOT_YEAR_SPECIFIC"
        row["methodology_id"] = "IPCC_2006_TIER1_AR6_GWP100"
        row["product_class"] = "LPG_FUEL"
        row["verification_status"] = "VERIFIED_TIER1_CONDITIONAL"
        row["notes"] = (
            "Eligible only for verified net LPG mass actually combusted in an owned/controlled "
            "commercial or institutional stationary source (IPCC 1.A.4.a), Scope 1. Global Tier 1, "
            "not India-specific or year-specific. Source uncertainty ranges are retained but not propagated."
        )
        row["methodology"] = (
            "Independently recomputed from the corrected IPCC 2006 Vol.2 Ch.2 Table 2.4 "
            "commercial/institutional LPG row (IPCC 1.A.4.a) and Vol.2 Ch.1 Table 1.2: 47.3 MJ/kg NCV x "
            "[63,100 kg CO2/TJ + 5 kg CH4/TJ x 27.0 GWP100 + 0.1 kg N2O/TJ x 273 GWP100] "
            "/ 1,000,000 MJ/TJ = 2.99230679 kgCO2e/kg. 1 TJ/Gg equals 1 MJ/kg. GWP100 inputs "
            "are from IPCC AR6 Annex II Table 9."
        )
    elif activity == "lpg":
        row["system_boundary"] = "UNRESOLVED"
        row["geography_code"] = "UNRESOLVED"
        row["applicable_period"] = "UNRESOLVED"
        row["methodology_id"] = "UNSELECTED_IPCC_EFDB_OR_COUNTRY_SOURCE"
        row["product_class"] = "LPG_FUEL"
    elif activity == "selected_material":
        row["system_boundary"] = "UNRESOLVED"
        row["geography_code"] = "UNRESOLVED"
        row["applicable_period"] = "UNRESOLVED"
        row["methodology_id"] = "UNSELECTED_MATERIAL_FACTOR"
        row["product_class"] = "UNRESOLVED"
    elif activity == "selected_transport":
        row["system_boundary"] = "UNRESOLVED"
        row["geography_code"] = "UNRESOLVED"
        row["applicable_period"] = "UNRESOLVED"
        row["methodology_id"] = "UNSELECTED_TRANSPORT_FACTOR"
        row["vehicle_class"] = "UNRESOLVED"
        row["product_class"] = "UNRESOLVED"
    return row


def road_diesel_row():
    return {
        "factor_id": ROAD_DIESEL_ID,
        "activity": "diesel",
        "normalized_activity": "diesel_fuel",
        "scope": "Scope 1 (owned/controlled road vehicle combustion)",
        "scope_category": "mobile combustion",
        "activity_unit": "L",
        "factor_value": "2.675",
        "factor_unit": "kgCO2e/L",
        "geography": "India road transportation",
        "applicable_year": "Not year-specific; SFC India Default GHG Emission Values V1.0",
        "source": "Smart Freight Centre India and TCI-IIMB Supply Chain Sustainability Lab at IIM Bangalore",
        "source_version": "India Default GHG Emission Values V1.0 (PDF dated May 2025; SFC publication page dated June 30, 2026)",
        "source_url": ROAD_DIESEL_URL,
        "source_sha256": ROAD_DIESEL_SHA256,
        "methodology": (
            "SFC V1.0 Fuel Emission Factors table, Road Transportation / Diesel row: source-reported "
            "2.675 kgCO2e/litre of fuel, TTW, rounded to three decimals. Independent recomputation "
            "using table values (CO2 74100, CH4 3.9, N2O 3.9 kg/TJ; NCV 43 TJ/Gg; 1.21 L/kg) "
            "and AR6 GWP100 values for fossil methane from combustion (27.0) and N2O (273) gives "
            "2.674884297520661... kgCO2e/L, which rounds to 2.675. The report's printed 27.9 methane "
            "coefficient also rounds to 2.675. This fuel factor is not vehicle-class-stratified; no WTT "
            "component is included."
        ),
        "conversion_required": "no",
        "verification_status": "VERIFIED_TIER1_CONDITIONAL",
        "notes": (
            "Eligible only for India road diesel actually combusted by an owned/controlled road vehicle "
            "(Scope 1 mobile combustion). Not applicable to stationary combustion, power-sector fuel activity, "
            "non-road equipment, freight tonne-km, WTT, or WTW. The source describes these as developing "
            "values subject to review. Its methodology text cites AR6 GWP100, while the table labels a "
            "nitrogen column NO2 and shows 27.9*B + 273*C; GreenLedger retains the published rounded factor "
            "value without silently correcting that source-method inconsistency. Source-owner clarification "
            "remains advisable."
        ),
        "gas_basis": "CO2e",
        "system_boundary": "SCOPE1_ROAD_MOBILE_TTW",
        "geography_code": "INDIA",
        "applicable_period": "NOT_YEAR_SPECIFIC",
        "methodology_id": "SFC_INDIA_V1_ROAD_DIESEL_TTW",
        "vehicle_class": "ROAD_VEHICLE_CLASS_INDEPENDENT",
        "product_class": "ROAD_DIESEL",
    }


def unresolved_rows_from_existing_definitions():
    """Restore the final three legacy rows, whose old CSV notes were unquoted commas."""
    rows = [
        {
            "factor_id": "lpg_stationary_co2e_unresolved",
            "activity": "lpg",
            "normalized_activity": "lpg",
            "scope": "Scope 1 (conditional on owned/controlled stationary combustion)",
            "scope_category": "stationary combustion; contexts outside the verified commercial/institutional Tier 1 row",
            "activity_unit": "kg",
            "factor_value": "",
            "factor_unit": "kgCO2e/kg",
            "geography": "Geography and exact source category must match a verified factor",
            "applicable_year": "TBD",
            "source": "IPCC EFDB or authoritative country/source-specific factor (not selected)",
            "source_version": "Not selected",
            "source_url": "https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf",
            "source_sha256": "",
            "methodology": (
                "No generic LPG factor is selected. A conditional global Tier 1 factor exists only for IPCC "
                "1.A.4.a commercial/institutional stationary combustion. Other contexts still require a matching "
                "source-category and geography-appropriate factor. Cylinder count alone is not a mass measure."
            ),
            "conversion_required": "yes unless invoice provides verified LPG mass and selected factor is mass-based",
            "verification_status": "METHOD_SELECTION_REQUIRED",
            "notes": (
                "FACTOR_NOT_VERIFIED outside the documented conditional eligibility of "
                "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6. Confirm combustion, organizational "
                "boundary, source category, geography, and verified net mass."
            ),
        },
        {
            "factor_id": "selected_materials_future_scope",
            "activity": "selected_materials",
            "normalized_activity": "selected_material",
            "scope": "Scope 3",
            "scope_category": "Category 1 purchased goods and services; exact subset pending",
            "activity_unit": "kg",
            "factor_value": "",
            "factor_unit": "kgCO2e/kg",
            "geography": "India supplier/product-specific preferred; exact geography pending",
            "applicable_year": "TBD",
            "source": "Supplier product EPD or authoritative regional cradle-to-gate LCI database (not selected)",
            "source_version": "TBD",
            "source_url": "",
            "source_sha256": "",
            "methodology": (
                "No numeric factor. Requires a fixed material/product class and product- or region-matched "
                "cradle-to-gate GHG factor, plus verified mass conversion where needed."
            ),
            "conversion_required": "yes for non-mass invoice units",
            "verification_status": "FUTURE_SCOPE",
            "notes": (
                "Frozen v1 category remains selected purchased materials; exact supported material subset and "
                "authoritative factor source are not finalized. Do not calculate from invoice price, piece, box, "
                "or length without a verified conversion and matching factor."
            ),
        },
        {
            "factor_id": "selected_transport_future_scope",
            "activity": "selected_transport",
            "normalized_activity": "selected_transport",
            "scope": "Scope 3",
            "scope_category": "Category 4 or 9 pending documented business flow",
            "activity_unit": "tonne_km",
            "factor_value": "",
            "factor_unit": "kgCO2e/tonne_km",
            "geography": "India route/provider-specific where available; exact geography pending",
            "applicable_year": "TBD",
            "source": "Authoritative India transport-factor source or carrier-specific verified factor (not selected)",
            "source_version": "TBD",
            "source_url": "",
            "source_sha256": "",
            "methodology": (
                "No numeric factor. Requires chosen transport mode, direction/business flow, service boundary, "
                "mass and distance (or source-supported tonne-km), and mode-specific factor basis."
            ),
            "conversion_required": "yes unless invoice provides verified tonne-km and matching factor",
            "verification_status": "FUTURE_SCOPE",
            "notes": (
                "Frozen v1 category remains selected transport/freight; exact mode and Category 4 versus 9 "
                "selection are unresolved. Freight price alone cannot be converted to emissions."
            ),
        },
    ]
    return rows


def main():
    with CATALOGUE.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        old_columns = list(reader.fieldnames)
        rows = list(reader)
    fieldnames = old_columns + [name for name in STRUCTURED_COLUMNS if name not in old_columns]

    rows = [row_metadata(row) for row in rows]
    existing_ids = {row["factor_id"] for row in rows}
    for row in unresolved_rows_from_existing_definitions():
        if row["factor_id"] not in existing_ids:
            rows.append(row_metadata(row))
            existing_ids.add(row["factor_id"])
    road_row = road_diesel_row()
    replaced = False
    for index, row in enumerate(rows):
        if row["factor_id"] == ROAD_DIESEL_ID:
            rows[index] = road_row
            replaced = True
    if not replaced:
        rows.append(road_row)

    with CATALOGUE.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with SCHEMA.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerow(fieldnames)

    print("catalogue rows:", len(rows))
    print("catalogue columns:", len(fieldnames))
    print("LPG status:", next(row["verification_status"] for row in rows if row["factor_id"] == LPG_ID))
    print("road diesel factor:", ROAD_DIESEL_ID, "2.675 kgCO2e/L (TTW)")


if __name__ == "__main__":
    main()
