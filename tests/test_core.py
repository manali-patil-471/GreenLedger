import unittest
from decimal import Decimal
from unittest.mock import patch

from greenledger.core import (
    ValidationError,
    evaluate_submission,
    load_factors,
    make_json_trace,
    normalize_activity,
    normalize_quantity,
    normalize_unit,
    parse_quantity,
)
from greenledger.factor_methods import (
    derive_lpg_tier1_co2e_factor,
    derive_sfc_india_road_diesel_factor,
)


class NormalizationTests(unittest.TestCase):
    def test_activity_alias_is_canonicalized(self):
        self.assertEqual(normalize_activity("High Speed Diesel")["id"], "diesel_fuel")

    def test_exact_documented_electricity_conversion(self):
        activity = normalize_activity("purchased_electricity")
        unit = normalize_unit(activity, "MWh")
        quantity, canonical_unit, trace = normalize_quantity(activity, Decimal("0.25"), unit)
        self.assertEqual(quantity, Decimal("250.00"))
        self.assertEqual(canonical_unit, "kWh")
        self.assertIn("1000", trace)

    def test_material_grams_convert_to_canonical_kilograms(self):
        activity = normalize_activity("purchased_materials")
        unit = normalize_unit(activity, "g")
        quantity, canonical_unit, trace = normalize_quantity(activity, Decimal("750"), unit)
        self.assertEqual(quantity, Decimal("0.75000"))
        self.assertEqual(canonical_unit, "kg")
        self.assertIn("1000 g = 1 kg", trace)

    def test_material_tonnes_alias_convert_to_kilograms(self):
        activity = normalize_activity("purchased_materials")
        unit = normalize_unit(activity, "t")
        quantity, canonical_unit, trace = normalize_quantity(activity, Decimal("1.5"), unit)
        self.assertEqual(quantity, Decimal("1500.0"))
        self.assertEqual(canonical_unit, "kg")
        self.assertIn("1 tonne = 1000 kg", trace)

    def test_missing_unit_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_unit(normalize_activity("diesel"), "")

    def test_ambiguous_number_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_quantity("1,250.00")


class AccountingGateTests(unittest.TestCase):
    def test_verified_lpg_factor_calculates_only_with_complete_context(self):
        result = evaluate_submission({
            "activity": "lpg",
            "quantity": "25",
            "unit": "kg",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "stationary",
            "commercial_institutional": "yes",
            "fields_confirmed": "yes",
        })
        self.assertEqual(result["scope"], "Scope 1")
        self.assertEqual(result["scope_category"], "stationary combustion")
        self.assertEqual(result["factor"]["factor_id"], "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6")
        self.assertEqual(result["factor"]["verification_status"], "VERIFIED_TIER1_CONDITIONAL")
        self.assertEqual(result["co2e"], Decimal("74.80766975"))
        self.assertFalse(result["review_required"])

    def test_lpg_cylinder_count_does_not_get_mass_conversion_or_factor(self):
        result = evaluate_submission({
            "activity": "lpg",
            "quantity": "2",
            "unit": "cylinder_count",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "stationary",
            "commercial_institutional": "yes",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["co2e"])
        self.assertIsNone(result["factor"])
        self.assertTrue(result["review_required"])

    def test_lpg_missing_required_context_does_not_calculate(self):
        result = evaluate_submission({
            "activity": "lpg",
            "quantity": "25",
            "unit": "kg",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["scope"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertTrue(result["review_required"])

    def test_lpg_factor_is_independently_recomputed_and_retains_provenance(self):
        rows = [row for row in load_factors()
                if row["factor_id"] == "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6"]
        self.assertEqual(len(rows), 1)
        lpg = rows[0]
        self.assertEqual(lpg["factor_value"], "2.99230679")
        self.assertEqual(lpg["factor_unit"], "kgCO2e/kg")
        self.assertEqual(lpg["verification_status"], "VERIFIED_TIER1_CONDITIONAL")
        self.assertIn("47.3 MJ/kg", lpg["methodology"])
        self.assertIn("IPCC 1.A.4.a", lpg["methodology"])
        self.assertIn("63,100 kg CO2/TJ", lpg["methodology"])
        self.assertIn("5 kg CH4/TJ", lpg["methodology"])
        self.assertIn("0.1 kg N2O/TJ", lpg["methodology"])
        self.assertIn("27.0 GWP100", lpg["methodology"])
        self.assertIn("273 GWP100", lpg["methodology"])
        self.assertEqual(derive_lpg_tier1_co2e_factor(), Decimal("2.99230679"))
        self.assertIn("GWP100", lpg["methodology"])
        self.assertTrue(lpg["source"])
        self.assertTrue(lpg["source_version"])
        self.assertTrue(lpg["source_url"])
        self.assertTrue(lpg["source_sha256"])

    def test_lpg_derivation_formula_matches_source_inputs(self):
        # kg gas/TJ × MJ/kg × TJ/1,000,000 MJ, then apply AR6 GWP100.
        self.assertEqual(derive_lpg_tier1_co2e_factor(), Decimal("2.99230679"))

    def test_electricity_285_kwh_calculates_separate_co2_result_only(self):
        result = evaluate_submission({
            "activity": "purchased_electricity",
            "quantity": "285",
            "unit": "kWh",
            "electricity_use": "purchased_and_consumed",
            "geography_code": "INDIA_GRID",
            "applicable_period": "FY2025-26",
            "fields_confirmed": "yes",
        })
        self.assertEqual(result["scope"], "Scope 2")
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("FACTOR_NOT_VERIFIED", result["factor_status"])
        self.assertEqual(result["co2_kg"], Decimal("192.4031246962862685"))
        self.assertEqual(result["co2_result_unit"], "kgCO2")
        self.assertEqual(result["co2_gas_basis"], "CO2")
        self.assertEqual(result["co2_factor"]["factor_id"], "cea_v22_weighted_average_grid_emission_rate_incl_res_captive_2025-26")
        self.assertIn("kgCO2", result["co2_calculation_trace"])
        trace = make_json_trace(result, document_name="electricity.pdf")
        co2_trace = trace["co2_calculation"]
        self.assertEqual(co2_trace["gas_basis"], "CO2")
        self.assertEqual(co2_trace["result_unit"], "kgCO2")
        self.assertEqual(co2_trace["factor"]["factor_value"], "0.6750986831448641")
        self.assertEqual(co2_trace["factor"]["factor_unit"], "kgCO2/kWh")
        self.assertEqual(co2_trace["factor"]["scope"], "Scope 2")
        self.assertEqual(co2_trace["factor"]["category"], "purchased electricity (location-based)")
        self.assertEqual(co2_trace["factor"]["geography"], "India unified grid; cross-border import adjustment included")
        self.assertEqual(co2_trace["factor"]["applicable_year"], "FY2025-26")
        self.assertEqual(co2_trace["factor"]["verification_status"], "VERIFIED_CO2_ONLY_SELECTED_REFERENCE")
        self.assertIn("CEA", co2_trace["factor"]["source"])
        self.assertEqual(co2_trace["factor"]["source_version"], "Version 22.0, August 2026")
        self.assertIn("Weighted Average Grid Emission Rate", co2_trace["factor"]["methodology"])
        self.assertIn("cea.nic.in", co2_trace["factor"]["source_url"])
        self.assertEqual(co2_trace["factor"]["source_sha256"], "F2341EFE03D2FCE4177A4A7090B8A946A5AC5AE32B41D784882D0226F2EB4860")

    def test_cea_co2_path_requires_matching_grid_geography_and_period(self):
        for fields in (
            {"geography_code": "INDIA_GRID"},
            {"applicable_period": "FY2025-26"},
            {"geography_code": "OTHER_GRID", "applicable_period": "FY2025-26"},
            {"geography_code": "INDIA_GRID", "applicable_period": "FY2024-25"},
        ):
            result = evaluate_submission({
                "activity": "purchased_electricity",
                "quantity": "285",
                "unit": "kWh",
                "electricity_use": "purchased_and_consumed",
                "fields_confirmed": "yes",
                **fields,
            })
            self.assertIsNone(result["co2_factor"])
            self.assertIsNone(result["co2_kg"])
            self.assertIn("CO2_FACTOR_NOT_VERIFIED", result["co2_factor_status"])
        missing_period = evaluate_submission({
            "activity": "purchased_electricity",
            "quantity": "285",
            "unit": "kWh",
            "electricity_use": "purchased_and_consumed",
            "geography_code": "INDIA_GRID",
            "fields_confirmed": "yes",
        })
        self.assertIn("billing period", missing_period["co2_factor_status"])
        self.assertTrue(any("billing period" in reason for reason in missing_period["review_reasons"]))

    def test_cea_co2_only_factor_cannot_produce_co2e(self):
        result = evaluate_submission({
            "activity": "purchased_electricity",
            "quantity": "250",
            "unit": "kWh",
            "electricity_use": "purchased_and_consumed",
            "geography_code": "INDIA_GRID",
            "applicable_period": "FY2025-26",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("FACTOR_NOT_VERIFIED", result["factor_status"])
        self.assertEqual(result["co2_kg"], Decimal("168.77467078621602500"))

    def test_diesel_invoice_alone_does_not_assign_scope_or_calculate(self):
        result = evaluate_submission({
            "activity": "diesel",
            "quantity": "250",
            "unit": "L",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["scope"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertTrue(result["review_required"])

    def test_india_road_diesel_ttw_requires_confirmed_vehicle_and_geography_context(self):
        result = evaluate_submission({
            "activity": "diesel",
            "quantity": "250",
            "unit": "L",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "mobile",
            "vehicle_class": "ROAD_VEHICLE",
            "geography_code": "INDIA",
            "fields_confirmed": "yes",
        })
        self.assertEqual(result["scope"], "Scope 1")
        self.assertEqual(result["scope_category"], "mobile combustion")
        self.assertEqual(result["factor"]["factor_id"], "sfc_india_v1_road_diesel_ttw")
        self.assertEqual(result["factor"]["system_boundary"], "SCOPE1_ROAD_MOBILE_TTW")
        self.assertEqual(result["factor"]["factor_value"], "2.675")
        self.assertEqual(result["co2e"], Decimal("668.750"))
        self.assertEqual(result["factor"]["source_sha256"], "8D814B6B3D35D40452EF85ABF560D3EE52DE260875E65DDC76AB8801C4DE7FD6")
        exact_ar6, rounded_ar6 = derive_sfc_india_road_diesel_factor()
        exact_published_gwp, rounded_published_gwp = derive_sfc_india_road_diesel_factor(Decimal("27.9"))
        self.assertEqual(exact_ar6, Decimal("2.674884297520661157024793388"))
        self.assertEqual(exact_published_gwp, Decimal("2.675009033057851239669421488"))
        self.assertEqual(rounded_ar6, Decimal("2.675"))
        self.assertEqual(rounded_published_gwp, Decimal("2.675"))

    def test_india_road_diesel_abstains_without_road_vehicle_context(self):
        result = evaluate_submission({
            "activity": "diesel",
            "quantity": "250",
            "unit": "L",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "mobile",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("road-diesel TTW factor requires", result["factor_status"])

    def test_stationary_diesel_does_not_use_road_factor_and_cea_rows_are_preserved(self):
        result = evaluate_submission({
            "activity": "diesel",
            "quantity": "250",
            "unit": "L",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "stationary",
            "vehicle_class": "ROAD_VEHICLE",
            "geography_code": "INDIA",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        rows = {row["factor_id"]: row for row in load_factors()}
        self.assertEqual(rows["cea_v22_diesel_co2_energy_ncv"]["factor_value"], "72.6")
        self.assertEqual(rows["cea_v22_diesel_co2_energy_ncv"]["factor_unit"], "gCO2/MJ")
        self.assertEqual(rows["cea_v22_diesel_co2_energy_gcv"]["factor_value"], "69.14285714285714")
        self.assertEqual(rows["cea_v22_diesel_co2_energy_gcv"]["factor_unit"], "gCO2/MJ")
        self.assertEqual(rows["cea_v22_diesel_co2_energy_ncv"]["verification_status"], "VERIFIED_CO2_ONLY_SOURCE_VALUE")
        self.assertEqual(rows["cea_v22_diesel_co2_energy_gcv"]["verification_status"], "VERIFIED_CO2_ONLY_SOURCE_VALUE")

    def test_ppc_cement_factor_calculates_with_matching_identity_and_provenance(self):
        result = evaluate_submission({
            "activity": "purchased_materials",
            "quantity": "100",
            "unit": "kg",
            "material_identity": "ppc_cement",
            "geography_code": "INDIA",
            "fields_confirmed": "yes",
        })
        self.assertEqual(result["scope"], "Scope 3")
        self.assertEqual(result["scope_category"], "Category 1 - Purchased goods and services")
        self.assertEqual(result["factor"]["factor_id"], "cpwd_2024_ppc_cement_reference")
        self.assertEqual(result["co2e"], Decimal("76.000"))
        trace = make_json_trace(result)
        self.assertEqual(trace["factor"]["source_sha256"], "469AAB40589B694187D0E65B12908CB82443D0E452EA951523327DA812D94108")
        self.assertEqual(trace["factor"]["source_version"], "Reducing Carbon Footprint in Buildings (2024), Chapter 1, Table on printed page 11")
        self.assertEqual(trace["normalized_activity_data"]["material_identity"], "ppc_cement")

    def test_steel_rebar_factor_calculates_without_generic_steel_substitution(self):
        result = evaluate_submission({
            "activity": "purchased_materials", "quantity": "100", "unit": "kg",
            "material_identity": "steel_rebar", "geography_code": "INDIA", "fields_confirmed": "yes",
        })
        self.assertEqual(result["factor"]["factor_id"], "cpwd_2024_steel_rebar_reference")
        self.assertEqual(result["co2e"], Decimal("345.000"))

    def test_generic_steel_factor_calculates_as_distinct_product(self):
        result = evaluate_submission({
            "activity": "purchased_materials", "quantity": "100", "unit": "kg",
            "material_identity": "generic_steel", "geography_code": "INDIA", "fields_confirmed": "yes",
        })
        self.assertEqual(result["factor"]["factor_id"], "cpwd_2024_generic_steel_reference")
        self.assertEqual(result["co2e"], Decimal("210.000"))

    def test_material_factor_product_mismatch_abstains(self):
        rebar = next(row for row in load_factors() if row["factor_id"] == "cpwd_2024_steel_rebar_reference")
        with patch("greenledger.core.load_factors", return_value=[rebar]):
            result = evaluate_submission({
                "activity": "purchased_materials", "quantity": "100", "unit": "kg",
                "material_identity": "ppc_cement", "geography_code": "INDIA", "fields_confirmed": "yes",
            })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])

    def test_material_missing_quantity_is_rejected_without_calculation(self):
        with self.assertRaisesRegex(ValidationError, "Enter a quantity"):
            evaluate_submission({
                "activity": "purchased_materials", "quantity": "", "unit": "kg",
                "material_identity": "ppc_cement", "geography_code": "INDIA", "fields_confirmed": "yes",
            })

    def test_ambiguous_material_identity_abstains(self):
        result = evaluate_submission({
            "activity": "purchased_materials", "quantity": "100", "unit": "kg",
            "material_identity": "steel", "geography_code": "INDIA", "fields_confirmed": "yes",
        })
        self.assertIsNone(result["material_identity"])
        self.assertIsNone(result["scope"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertTrue(result["review_required"])

    def test_material_reference_requires_matching_india_geography(self):
        result = evaluate_submission({
            "activity": "purchased_materials", "quantity": "100", "unit": "kg",
            "material_identity": "generic_steel", "geography_code": "OTHER", "fields_confirmed": "yes",
        })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("India-specific", result["factor_status"])

    def test_transport_factors_calculate_for_each_supported_gvw_class(self):
        factors = {
            "ROAD_GVW_LT_3_5_T": ("0.3795", "sfc_teri_2026_road_freight_road_gvw_lt_3_5_t_wtw"),
            "ROAD_GVW_3_5_T": ("0.2222", "sfc_teri_2026_road_freight_road_gvw_3_5_t_wtw"),
            "ROAD_GVW_5_12_T": ("0.1400", "sfc_teri_2026_road_freight_road_gvw_5_12_t_wtw"),
            "ROAD_GVW_12_20_T": ("0.0902", "sfc_teri_2026_road_freight_road_gvw_12_20_t_wtw"),
            "ROAD_GVW_20_30_T": ("0.0823", "sfc_teri_2026_road_freight_road_gvw_20_30_t_wtw"),
            "ROAD_GVW_30_50_T": ("0.0663", "sfc_teri_2026_road_freight_road_gvw_30_50_t_wtw"),
            "ROAD_TRACTOR_TRAILER_GVW_30_60_T": ("0.0551", "sfc_teri_2026_road_freight_road_tractor_trailer_gvw_30_60_t_wtw"),
        }
        for vehicle_class, (factor_value, factor_id) in factors.items():
            with self.subTest(vehicle_class=vehicle_class):
                result = evaluate_submission({
                    "activity": "selected_transport", "transport_scenario": "upstream_purchased",
                    "transport_mode": "road", "geography_code": "INDIA",
                    "transport_vehicle_class": vehicle_class,
                    "shipment_mass": "1000", "mass_unit": "kg",
                    "distance": "100", "distance_unit": "km", "fields_confirmed": "yes",
                })
                self.assertEqual(result["scope"], "Scope 3")
                self.assertEqual(result["factor"]["factor_id"], factor_id)
                self.assertEqual(result["co2e"], Decimal(factor_value) * Decimal("100"))

    def test_transport_mass_and_distance_convert_to_tonne_km(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "shipment_mass": "2500", "mass_unit": "kg",
            "distance": "500", "distance_unit": "m", "fields_confirmed": "yes",
        })
        self.assertEqual(result["transport_data"]["shipment_mass_tonnes"], Decimal("2.500"))
        self.assertEqual(result["transport_data"]["distance_km"], Decimal("0.500"))
        self.assertEqual(result["normalized_quantity"], Decimal("1.250000"))
        self.assertEqual(result["co2e"], Decimal("0.2777500000"))
        self.assertIn("0.001", result["conversion_trace"])
        self.assertIn("tonnes", result["conversion_trace"])

    def test_transport_missing_distance_does_not_calculate(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "shipment_mass": "1000", "mass_unit": "kg", "fields_confirmed": "yes",
        })
        self.assertIsNone(result["normalized_quantity"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("distance", result["factor_status"])

    def test_transport_missing_mass_does_not_calculate(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "distance": "100", "distance_unit": "km", "fields_confirmed": "yes",
        })
        self.assertIsNone(result["normalized_quantity"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("shipment mass", result["factor_status"])

    def test_transport_missing_vehicle_class_does_not_calculate(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "shipment_mass": "1000", "mass_unit": "kg", "distance": "100", "distance_unit": "km",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("vehicle GVW class is required", result["factor_status"])

    def test_transport_invalid_vehicle_class_does_not_calculate(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "upstream_purchased",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "medium truck, probably 5 tonnes",
            "shipment_mass": "1000", "mass_unit": "kg", "distance": "100", "distance_unit": "km",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["transport_vehicle_class"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])

    def test_transport_other_modes_and_company_controlled_freight_do_not_use_road_scope3_factors(self):
        common = {
            "activity": "selected_transport", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "shipment_mass": "1000", "mass_unit": "kg", "distance": "100", "distance_unit": "km",
            "fields_confirmed": "yes",
        }
        for overrides in (
            {"transport_scenario": "upstream_purchased", "transport_mode": "rail"},
            {"transport_scenario": "company_controlled", "transport_mode": "road"},
        ):
            with self.subTest(overrides=overrides):
                result = evaluate_submission({**common, **overrides})
                self.assertIsNone(result["factor"])
                self.assertIsNone(result["co2e"])

    def test_transport_trace_preserves_factor_provenance_and_activity_inputs(self):
        result = evaluate_submission({
            "activity": "selected_transport", "transport_scenario": "downstream_sold_product",
            "transport_mode": "road", "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "shipment_mass": "2000", "mass_unit": "kg", "distance": "80", "distance_unit": "km",
            "fields_confirmed": "yes",
        })
        trace = make_json_trace(result)
        self.assertEqual(trace["classification"]["scope_category"], "Category 9 - Downstream transportation and distribution")
        self.assertEqual(trace["factor"]["factor_value"], "0.2222")
        self.assertEqual(trace["factor"]["factor_unit"], "kgCO2e/tonne_km")
        self.assertEqual(trace["factor"]["gas_basis"], "CO2e")
        self.assertEqual(trace["factor"]["system_boundary"], "SCOPE3_ROAD_FREIGHT_WTW")
        self.assertEqual(trace["factor"]["source_sha256"], "366C10E4DDC735EA69B16E4562CC3CBF601EBB51C9E930DBEB47655AB368E7FC")
        self.assertEqual(trace["normalized_activity_data"]["transport"]["shipment_mass_tonnes"], "2.000")
        self.assertEqual(trace["normalized_activity_data"]["transport"]["distance_km"], "80")

    def test_material_and_freight_calculation_still_require_human_confirmation(self):
        cases = (
            {
                "activity": "purchased_materials", "quantity": "100", "unit": "kg",
                "material_identity": "ppc_cement", "geography_code": "INDIA",
            },
            {
                "activity": "selected_transport", "transport_scenario": "upstream_purchased",
                "transport_mode": "road", "geography_code": "INDIA",
                "transport_vehicle_class": "ROAD_GVW_3_5_T",
                "shipment_mass": "1000", "mass_unit": "kg", "distance": "100", "distance_unit": "km",
            },
        )
        for fields in cases:
            with self.subTest(activity=fields["activity"]):
                result = evaluate_submission(fields)
                self.assertIsNotNone(result["factor"])
                self.assertIsNone(result["co2e"])
                self.assertEqual(result["human_verification"], "PENDING")
                self.assertTrue(result["review_required"])

    def test_electricity_does_not_calculate_co2_without_human_confirmation(self):
        result = evaluate_submission({
            "activity": "purchased_electricity",
            "quantity": "285",
            "unit": "kWh",
            "electricity_use": "purchased_and_consumed",
        })
        self.assertIsNone(result["co2_kg"])
        self.assertIsNone(result["co2e"])
        self.assertTrue(result["review_required"])

    def test_transport_distance_alone_is_not_converted_to_tonne_km(self):
        result = evaluate_submission({
            "activity": "selected_transport",
            "transport_scenario": "upstream_purchased",
            "transport_mode": "road",
            "geography_code": "INDIA",
            "transport_vehicle_class": "ROAD_GVW_3_5_T",
            "distance": "120",
            "distance_unit": "km",
            "fields_confirmed": "yes",
        })
        self.assertIsNone(result["normalized_quantity"])
        self.assertIsNone(result["factor"])
        self.assertIsNone(result["co2e"])
        self.assertIn("shipment mass", result["factor_status"])

    def test_unconfirmed_manual_fields_require_review_even_if_factor_matches(self):
        result = evaluate_submission({
            "activity": "lpg",
            "quantity": "1",
            "unit": "kg",
            "combusted": "yes",
            "controlled": "yes",
            "source_type": "stationary",
            "commercial_institutional": "yes",
        })
        self.assertIsNone(result["co2e"])
        self.assertTrue(result["review_required"])


if __name__ == "__main__":
    unittest.main()
