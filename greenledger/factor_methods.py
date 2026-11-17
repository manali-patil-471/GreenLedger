"""Deterministic derivations used to verify catalogue factors against source inputs."""

from decimal import Decimal, ROUND_HALF_UP


LPG_SOURCE_INPUTS = {
    "ncv_mj_per_kg": Decimal("47.3"),
    "co2_kg_per_tj": Decimal("63100"),
    "ch4_kg_per_tj": Decimal("5"),
    "n2o_kg_per_tj": Decimal("0.1"),
    "ch4_gwp100": Decimal("27.0"),
    "n2o_gwp100": Decimal("273"),
    "mj_per_tj": Decimal("1000000"),
}


def derive_lpg_tier1_co2e_factor(inputs=None):
    """Return kgCO2e/kg LPG from IPCC 1.A.4.a inputs and selected AR6 GWP100s."""
    values = inputs or LPG_SOURCE_INPUTS
    co2e_kg_per_tj = (
        values["co2_kg_per_tj"]
        + values["ch4_kg_per_tj"] * values["ch4_gwp100"]
        + values["n2o_kg_per_tj"] * values["n2o_gwp100"]
    )
    return values["ncv_mj_per_kg"] * co2e_kg_per_tj / values["mj_per_tj"]


SFC_INDIA_ROAD_DIESEL_INPUTS = {
    "co2_kg_per_tj": Decimal("74100"),
    "ch4_kg_per_tj": Decimal("3.9"),
    "n2o_kg_per_tj": Decimal("3.9"),
    "ch4_gwp100_ar6_combustion": Decimal("27.0"),
    "n2o_gwp100_ar6": Decimal("273"),
    "ncv_tj_per_gg": Decimal("43"),
    "litre_per_kg_fuel": Decimal("1.21"),
    "kg_per_gg": Decimal("1000000"),
}


def derive_sfc_india_road_diesel_factor(ch4_gwp100=None, inputs=None):
    """Return exact and source-rounded kgCO2e/L from the SFC road-diesel table inputs."""
    values = inputs or SFC_INDIA_ROAD_DIESEL_INPUTS
    methane_gwp = ch4_gwp100 or values["ch4_gwp100_ar6_combustion"]
    co2e_kg_per_tj = (
        values["co2_kg_per_tj"]
        + values["ch4_kg_per_tj"] * methane_gwp
        + values["n2o_kg_per_tj"] * values["n2o_gwp100_ar6"]
    )
    co2e_kg_per_kg = co2e_kg_per_tj * values["ncv_tj_per_gg"] / values["kg_per_gg"]
    exact_kgco2e_per_litre = co2e_kg_per_kg / values["litre_per_kg_fuel"]
    rounded_kgco2e_per_litre = exact_kgco2e_per_litre.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return exact_kgco2e_per_litre, rounded_kgco2e_per_litre
