"""Validate structured factor applicability, source hashes, and audited derivations."""

import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greenledger.factor_methods import (
    derive_lpg_tier1_co2e_factor,
    derive_sfc_india_road_diesel_factor,
)


CATALOGUE = ROOT / "knowledge_base/emission_factors/GREENLEDGER_V1_FACTOR_CATALOGUE.csv"
SCHEMA_COLUMNS = ROOT / "knowledge_base/emission_factors/schema.csv"

SOURCE_HASHES = {
    "knowledge_base/standards/ipcc_sources/IPCC_2006_Vol2_Ch1_Introduction.pdf":
        "E391CD4676D0891CD77F67D3BD76E0E6775386B468CE5CE7EBE2311A6EA1AC45",
    "knowledge_base/standards/ipcc_sources/IPCC_2006_Vol2_Ch2_Stationary_Combustion_corrected.pdf":
        "A25D9F96D7672DF391B328DE79D4CFD812C07FE79D5CF4A30D23D82D8F02985B",
    "knowledge_base/standards/ipcc_sources/IPCC_AR6_WGIII_Annex_II.pdf":
        "5CC3EE5E6E27D176E8EDB8A0038C35698388606F6F6D494A039AA479B9211DC9",
    "knowledge_base/standards/GHG_Protocol_Required_Gases_and_GWP_Values_Amendment.pdf":
        "2BC8B42D4CB94D1F74AE477F3BFAF3EB7AB55F216F575050EBDD67C9447A3A7F",
    "knowledge_base/emission_factors/CO2_Database_V_22.0.xlsx":
        "F2341EFE03D2FCE4177A4A7090B8A946A5AC5AE32B41D784882D0226F2EB4860",
    "knowledge_base/standards/sfc_india/India_Default_GHG_Emission_Values_V1.0.pdf":
        "8D814B6B3D35D40452EF85ABF560D3EE52DE260875E65DDC76AB8801C4DE7FD6",
    "knowledge_base/standards/cpwd/Reducing_Carbon_Footprint_in_Buildings_2024.pdf":
        "469AAB40589B694187D0E65B12908CB82443D0E452EA951523327DA812D94108",
    "knowledge_base/standards/sfc_india/SFC_India_TERI_Institutionalizing_Freight_Emissions_Accounting.pdf":
        "366C10E4DDC735EA69B16E4562CC3CBF601EBB51C9E930DBEB47655AB368E7FC",
}

LPG_FACTOR_ID = "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6"
ROAD_DIESEL_FACTOR_ID = "sfc_india_v1_road_diesel_ttw"
CEA_ELECTRICITY_FACTOR_ID = "cea_v22_weighted_average_grid_emission_rate_incl_res_captive_2025-26"
MATERIAL_FACTORS = {
    "cpwd_2024_ppc_cement_reference": ("ppc_cement", "0.760"),
    "cpwd_2024_steel_rebar_reference": ("steel_rebar", "3.450"),
    "cpwd_2024_generic_steel_reference": ("generic_steel", "2.100"),
}
ROAD_FREIGHT_FACTORS = {
    "ROAD_GVW_LT_3_5_T": "0.3795",
    "ROAD_GVW_3_5_T": "0.2222",
    "ROAD_GVW_5_12_T": "0.1400",
    "ROAD_GVW_12_20_T": "0.0902",
    "ROAD_GVW_20_30_T": "0.0823",
    "ROAD_GVW_30_50_T": "0.0663",
    "ROAD_TRACTOR_TRAILER_GVW_30_60_T": "0.0551",
}
TRANSPORT_SCOPE_CATEGORY = "Category 4 or 9 - road freight, selected by business flow"
CO2E_CALCULABLE_STATUSES = {"VERIFIED_CO2E", "VERIFIED_TIER1_CONDITIONAL"}
CALCULABLE_STATUSES = CO2E_CALCULABLE_STATUSES | {"VERIFIED_CO2_ONLY_SELECTED_REFERENCE"}
REQUIRED_APPLICABILITY_FIELDS = (
    "gas_basis", "system_boundary", "geography_code", "applicable_period",
    "methodology_id", "vehicle_class", "product_class", "source_sha256",
)
REQUIRED_PROVENANCE_FIELDS = ("source", "source_version", "source_url", "methodology")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    with open(str(SCHEMA_COLUMNS), "r", newline="", encoding="utf-8-sig") as stream:
        expected_columns = next(csv.reader(stream))
    with open(str(CATALOGUE), "r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == expected_columns, "catalogue header differs from schema.csv")
        rows = list(reader)

    require(rows, "catalogue has no data rows")
    ids = [row.get("factor_id", "").strip() for row in rows]
    require(all(ids), "catalogue contains an empty factor_id")
    require(len(ids) == len(set(ids)), "factor_id values are not unique")

    source_hash_values = set(SOURCE_HASHES.values())
    for row in rows:
        value = row.get("factor_value", "").strip()
        if value:
            require(Decimal(value) > 0, "factor value must be positive: " + row["factor_id"])
        if row.get("verification_status") in ("METHOD_SELECTION_REQUIRED", "FUTURE_SCOPE"):
            require(not value, "unresolved/future factor has a numeric value: " + row["factor_id"])
        factor_unit = row.get("factor_unit", "").casefold()
        gas_basis = row.get("gas_basis", "").strip()
        if "co2e" in factor_unit:
            require(gas_basis == "CO2e", "CO2e factor has a conflicting gas_basis: " + row["factor_id"])
        elif "co2" in factor_unit:
            require(gas_basis == "CO2", "CO2-only factor has a conflicting gas_basis: " + row["factor_id"])
        else:
            require(not row.get("factor_value", "").strip(), "numeric factor has no recognizable CO2 gas basis: " + row["factor_id"])

        status = row.get("verification_status", "")
        if status in CALCULABLE_STATUSES:
            for field in REQUIRED_APPLICABILITY_FIELDS:
                require(row.get(field, "").strip(), "calculable factor is missing " + field + ": " + row["factor_id"])
            for field in REQUIRED_PROVENANCE_FIELDS:
                require(row.get(field, "").strip(), "calculable factor is missing " + field + ": " + row["factor_id"])
            require(row["gas_basis"] in {"CO2", "CO2e"}, "unknown gas basis: " + row["factor_id"])
            require(row["system_boundary"] not in {"", "UNRESOLVED"}, "calculable factor has unresolved system boundary: " + row["factor_id"])
            require(row["geography_code"] not in {"", "UNRESOLVED"}, "calculable factor has unresolved geography: " + row["factor_id"])
            require(row["applicable_period"] not in {"", "UNRESOLVED"}, "calculable factor has unresolved applicable period: " + row["factor_id"])
            require(row["methodology_id"] not in {"", "UNSELECTED"}, "calculable factor has unresolved methodology: " + row["factor_id"])
            require(row["vehicle_class"] != "UNRESOLVED", "calculable factor has unresolved vehicle class: " + row["factor_id"])
            require(row["product_class"] != "UNRESOLVED", "calculable factor has unresolved product class: " + row["factor_id"])
            require(len(row["source_sha256"]) == 64 and row["source_sha256"] == row["source_sha256"].upper(),
                    "calculable factor source_sha256 is malformed: " + row["factor_id"])
            require(row["source_sha256"] in source_hash_values,
                    "calculable factor source_sha256 has no pinned local source: " + row["factor_id"])
        if status in CO2E_CALCULABLE_STATUSES:
            require(row["gas_basis"] == "CO2e" and "co2e" in factor_unit,
                    "CO2-only factor cannot carry a CO2e-calculable status: " + row["factor_id"])
        if status == "VERIFIED_CO2_ONLY_SELECTED_REFERENCE":
            require(row["gas_basis"] == "CO2" and "co2" in factor_unit and "co2e" not in factor_unit,
                    "CO2-only selected reference is mislabeled: " + row["factor_id"])
            require(row["system_boundary"] == "SCOPE2_LOCATION_BASED_GRID_AVERAGE",
                    "selected CEA electricity reference has a mismatched system boundary: " + row["factor_id"])
            require(row["geography_code"] == "INDIA_GRID" and row["product_class"] == "GRID_ELECTRICITY",
                    "selected CEA electricity reference has mismatched geography/product applicability: " + row["factor_id"])

    lpg_matches = [row for row in rows if row.get("factor_id") == LPG_FACTOR_ID]
    require(len(lpg_matches) == 1, "expected exactly one LPG Tier 1 factor")
    lpg = lpg_matches[0]
    expected_lpg = derive_lpg_tier1_co2e_factor()
    require(Decimal(lpg["factor_value"]) == expected_lpg,
            "LPG factor does not match the independently recomputed source-input derivation")
    require(lpg["factor_unit"] == "kgCO2e/kg", "LPG factor unit mismatch")
    require(lpg["verification_status"] == "VERIFIED_TIER1_CONDITIONAL",
            "verified LPG factor status mismatch")
    require(lpg["gas_basis"] == "CO2e" and lpg["system_boundary"] == "SCOPE1_STATIONARY_COMBUSTION_1A4A",
            "LPG gas basis or combustion boundary mismatch")
    require(lpg["geography_code"] == "GLOBAL" and lpg["applicable_period"] == "NOT_YEAR_SPECIFIC",
            "LPG geography or period applicability mismatch")
    require(lpg["methodology_id"] == "IPCC_2006_TIER1_AR6_GWP100" and lpg["product_class"] == "LPG_FUEL",
            "LPG methodology or product-class applicability mismatch")
    for field in ("source", "source_version", "source_url", "source_sha256", "methodology"):
        require(lpg.get(field, "").strip(), "LPG derivation/provenance is missing " + field)
    for evidence in ("47.3 MJ/kg", "63,100 kg CO2/TJ", "5 kg CH4/TJ", "0.1 kg N2O/TJ", "27.0 GWP100", "273 GWP100", "IPCC 1.A.4.a"):
        require(evidence in lpg["methodology"], "LPG recomputation provenance is missing " + evidence)
    eligibility_notes = lpg["notes"].lower()
    require("commercial/institutional" in eligibility_notes or
            "commercial or institutional" in eligibility_notes,
            "LPG factor eligibility condition is missing")

    diesel_matches = [row for row in rows if row.get("factor_id") == ROAD_DIESEL_FACTOR_ID]
    require(len(diesel_matches) == 1, "expected exactly one SFC India road diesel TTW factor")
    diesel = diesel_matches[0]
    require(diesel["factor_value"] == "2.675" and diesel["factor_unit"] == "kgCO2e/L",
            "SFC road diesel source-reported factor value or unit mismatch")
    require(diesel["gas_basis"] == "CO2e" and diesel["scope"] == "Scope 1 (owned/controlled road vehicle combustion)" and diesel["scope_category"] == "mobile combustion",
            "SFC road diesel gas/scope applicability mismatch")
    require(diesel["system_boundary"] == "SCOPE1_ROAD_MOBILE_TTW" and diesel["geography_code"] == "INDIA",
            "SFC road diesel boundary/geography applicability mismatch")
    require(diesel["applicable_period"] == "NOT_YEAR_SPECIFIC" and diesel["methodology_id"] == "SFC_INDIA_V1_ROAD_DIESEL_TTW",
            "SFC road diesel period/methodology applicability mismatch")
    require(diesel["vehicle_class"] == "ROAD_VEHICLE_CLASS_INDEPENDENT" and diesel["product_class"] == "ROAD_DIESEL",
            "SFC road diesel vehicle/product applicability mismatch")
    require(diesel["source_sha256"] == SOURCE_HASHES["knowledge_base/standards/sfc_india/India_Default_GHG_Emission_Values_V1.0.pdf"],
            "SFC road diesel SHA-256 does not match its pinned local source")
    diesel_exact_ar6, diesel_rounded_ar6 = derive_sfc_india_road_diesel_factor()
    diesel_exact_published_gwp, diesel_rounded_published_gwp = derive_sfc_india_road_diesel_factor(Decimal("27.9"))
    require(diesel_rounded_ar6 == Decimal(diesel["factor_value"]),
            "SFC diesel factor does not match the independent AR6 recomputation to source precision")
    require(diesel_rounded_published_gwp == Decimal(diesel["factor_value"]),
            "SFC diesel factor does not match the report's printed methane coefficient to source precision")
    for evidence in ("CO2 74100", "CH4 3.9", "N2O 3.9", "NCV 43 TJ/Gg", "1.21 L/kg", "27.0", "27.9"):
        require(evidence in diesel["methodology"], "SFC diesel recomputation provenance is missing " + evidence)
    require("smart freight centre" in diesel["source"].casefold() and "tci-iimb" in diesel["source"].casefold(),
            "SFC/TCI-IIMB source attribution is missing")
    require("TTW" in diesel["methodology"] and "2.675" in diesel["methodology"],
            "SFC diesel provenance does not identify the source-reported TTW row")

    cea_matches = [row for row in rows if row.get("factor_id") == CEA_ELECTRICITY_FACTOR_ID]
    require(len(cea_matches) == 1, "expected exactly one selected CEA V22 FY2025-26 electricity factor")
    cea = cea_matches[0]
    require(cea["gas_basis"] == "CO2" and cea["factor_unit"] == "kgCO2/kWh",
            "CEA CO2-only electricity applicability was mislabeled")
    require(cea["system_boundary"] == "SCOPE2_LOCATION_BASED_GRID_AVERAGE" and cea["geography_code"] == "INDIA_GRID",
            "CEA electricity system boundary/geography mismatch")
    require(cea["applicable_period"] == "FY2025-26" and cea["methodology_id"] == "CEA_V22_WEIGHTED_AVERAGE_GRID_INCL_RES_CAPTIVE",
            "CEA electricity applicable period/methodology mismatch")

    for factor_id, (product_class, expected_value) in MATERIAL_FACTORS.items():
        matches = [row for row in rows if row.get("factor_id") == factor_id]
        require(len(matches) == 1, "expected exactly one CPWD material factor: " + factor_id)
        row = matches[0]
        require(row["factor_value"] == expected_value and row["factor_unit"] == "kgCO2e/kg",
                "CPWD material value or unit mismatch: " + factor_id)
        require(row["gas_basis"] == "CO2e" and row["scope"] == "Scope 3" and
                row["scope_category"] == "Category 1 - Purchased goods and services",
                "CPWD material scope/category/gas applicability mismatch: " + factor_id)
        require(row["system_boundary"] == "SCOPE3_PURCHASED_MATERIAL_CRADLE_TO_GATE" and
                row["geography_code"] == "INDIA" and row["applicable_period"] == "NOT_YEAR_SPECIFIC" and
                row["methodology_id"] == "CPWD_2024_EMBODIED_MATERIAL_REFERENCE" and
                row["product_class"] == product_class and row["vehicle_class"] == "NOT_APPLICABLE",
                "CPWD material applicability metadata mismatch: " + factor_id)
        require(row["verification_status"] == "VERIFIED_CO2E" and
                row["source_sha256"] == SOURCE_HASHES["knowledge_base/standards/cpwd/Reducing_Carbon_Footprint_in_Buildings_2024.pdf"],
                "CPWD material status/source hash mismatch: " + factor_id)
        require("generic/reference" in row["notes"].casefold(),
                "CPWD factor must be explicitly described as a GreenLedger reference factor: " + factor_id)
        require(row["source_url"].startswith("https://cpwd.gov.in/"),
                "CPWD material must retain the official source URL: " + factor_id)

    for vehicle_class, expected_value in ROAD_FREIGHT_FACTORS.items():
        matches = [row for row in rows if row.get("normalized_activity") == "selected_transport" and
                   row.get("vehicle_class") == vehicle_class and row.get("methodology_id") == "SFC_TERII_2026_ROAD_FREIGHT_WTW"]
        require(len(matches) == 1, "expected exactly one SFC/TERI India road-freight factor for " + vehicle_class)
        row = matches[0]
        require(row["factor_value"] == expected_value and row["factor_unit"] == "kgCO2e/tonne_km" and
                row["activity_unit"] == "tonne_km",
                "SFC/TERI road-freight value or unit mismatch: " + vehicle_class)
        require(row["gas_basis"] == "CO2e" and row["scope"] == "Scope 3" and
                row["scope_category"] == TRANSPORT_SCOPE_CATEGORY,
                "SFC/TERI road-freight scope/category/gas mismatch: " + vehicle_class)
        require(row["system_boundary"] == "SCOPE3_ROAD_FREIGHT_WTW" and row["geography_code"] == "INDIA" and
                row["applicable_period"] == "NOT_YEAR_SPECIFIC" and row["product_class"] == "ROAD_FREIGHT_SERVICE",
                "SFC/TERI road-freight applicability metadata mismatch: " + vehicle_class)
        require(row["verification_status"] == "VERIFIED_TIER1_CONDITIONAL" and
                row["source_sha256"] == SOURCE_HASHES["knowledge_base/standards/sfc_india/SFC_India_TERI_Institutionalizing_Freight_Emissions_Accounting.pdf"],
                "SFC/TERI road-freight status/source hash mismatch: " + vehicle_class)
        require("wtw" in row["methodology"].casefold() and "average load" in row["methodology"].casefold(),
                "SFC/TERI road-freight basis/load methodology missing: " + vehicle_class)
    enabled_transport_rows = [row for row in rows if row.get("verification_status") in CALCULABLE_STATUSES and
                              row.get("normalized_activity") == "selected_transport"]
    require(len(enabled_transport_rows) == len(ROAD_FREIGHT_FACTORS),
            "only the seven explicit SFC/TERI India road-freight vehicle classes may be calculable")

    for relative_path, expected_hash in SOURCE_HASHES.items():
        source_path = ROOT / relative_path
        require(source_path.is_file(), "source file is missing: " + relative_path)
        require(sha256(source_path) == expected_hash, "source checksum mismatch: " + relative_path)

    summary = {
        "result": "PASS",
        "catalogue_rows": len(rows),
        "unique_factor_ids": len(set(ids)),
        "lpg_independently_recomputed_kgco2e_per_kg": str(expected_lpg),
        "lpg_factor_id": LPG_FACTOR_ID,
        "lpg_status": lpg["verification_status"],
        "road_diesel_factor_id": ROAD_DIESEL_FACTOR_ID,
        "road_diesel_factor_value": diesel["factor_value"],
        "road_diesel_status": diesel["verification_status"],
        "road_diesel_independent_ar6_kgco2e_per_l": str(diesel_exact_ar6),
        "road_diesel_published_gwp_kgco2e_per_l": str(diesel_exact_published_gwp),
        "cpwd_material_factor_count": len(MATERIAL_FACTORS),
        "sfc_teri_road_freight_factor_count": len(ROAD_FREIGHT_FACTORS),
        "source_files_hash_verified": len(SOURCE_HASHES),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
