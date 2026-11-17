"""Conservative, deterministic accounting helpers for the first GreenLedger UI."""

import csv
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVITIES_PATH = ROOT / "knowledge_base" / "activities" / "activities.json"
MAPPINGS_PATH = ROOT / "knowledge_base" / "scope_mapping" / "mapping.json"
FACTORS_PATH = ROOT / "knowledge_base" / "emission_factors" / "GREENLEDGER_V1_FACTOR_CATALOGUE.csv"
LPG_FACTOR_ID = "lpg_ipcc_2006_tier1_commercial_stationary_gwp100_ar6"
CEA_V22_ELECTRICITY_FACTOR_ID = "cea_v22_weighted_average_grid_emission_rate_incl_res_captive_2025-26"
SFC_INDIA_ROAD_DIESEL_FACTOR_ID = "sfc_india_v1_road_diesel_ttw"
TRANSPORT_SCOPE_CATEGORY = "Category 4 or 9 - road freight, selected by business flow"

MATERIAL_IDENTITIES = {
    "ppc_cement": {"ppc cement", "portland pozzolana cement", "portland pozzolana cement ppc", "ppc cement 30% fly ash"},
    "steel_rebar": {"steel rebar", "steel rebars", "rebar", "reinforcing steel", "reinforcement steel"},
    "generic_steel": {"generic steel", "steel generic"},
}

TRANSPORT_VEHICLE_CLASSES = {
    "ROAD_GVW_LT_3_5_T": {"<3.5 t", "<3.5t", "gvw <3.5 mt", "small commercial vehicles gvw <3.5 mt"},
    "ROAD_GVW_3_5_T": {"3-5 t", "3-5t", "gvw 3 to 5 mt", "medium commercial vehicles -1 gvw 3 to 5 mt"},
    "ROAD_GVW_5_12_T": {"5-12 t", "5-12t", "gvw 5 to 12 mt", "medium commercial vehicles -2 gvw 5 to 12 mt"},
    "ROAD_GVW_12_20_T": {"12-20 t", "12-20t", "gvw 12 to 20 mt", "heavy commercial vehicles -1 gvw 12 to 20 mt"},
    "ROAD_GVW_20_30_T": {"20-30 t", "20-30t", "gvw 20 to 30 mt", "heavy commercial vehicles -2 gvw 20 to 30 mt"},
    "ROAD_GVW_30_50_T": {"30-50 t", "30-50t", "gvw 30 to 50 mt", "heavy commercial vehicles -3 gvw 30 to 50 mt"},
    "ROAD_TRACTOR_TRAILER_GVW_30_60_T": {"30-60 t tractor-trailer", "30-60t tractor trailer", "tractor trailer commercial vehicles gvw 30 to 60 mt"},
}


class ValidationError(ValueError):
    pass


def load_activities():
    with ACTIVITIES_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)["activities"]


def load_mappings():
    with MAPPINGS_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)["mappings"]


def load_factors():
    with FACTORS_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def normalize_activity(raw_activity):
    query = " ".join((raw_activity or "").strip().casefold().split())
    if not query:
        raise ValidationError("Choose an activity before submitting.")
    for activity in load_activities():
        candidates = [activity["id"], activity["canonical_name"]] + activity.get("aliases", [])
        if query in {" ".join(item.casefold().split()) for item in candidates}:
            return activity
    raise ValidationError("That activity is not in the frozen GreenLedger v1 taxonomy.")


def normalize_material_identity(raw_identity):
    query = " ".join((raw_identity or "").strip().casefold().replace("–", "-").split())
    for canonical, aliases in MATERIAL_IDENTITIES.items():
        if query in {canonical.casefold(), canonical.replace("_", " ")} or query in aliases:
            return canonical
    # In particular, the unqualified label "steel" is ambiguous and is not a fallback.
    return None


def normalize_transport_vehicle_class(raw_class):
    query = " ".join((raw_class or "").strip().casefold().replace("–", "-").split())
    if query in TRANSPORT_VEHICLE_CLASSES:
        return query
    for canonical, aliases in TRANSPORT_VEHICLE_CLASSES.items():
        if query == canonical.casefold() or query in aliases:
            return canonical
    return None


def normalize_unit(activity, raw_unit):
    query = " ".join((raw_unit or "").strip().casefold().replace("_", " ").split())
    if not query:
        raise ValidationError("Enter a unit. GreenLedger will not infer a missing unit.")

    aliases = {
        "purchased_electricity": {"kwh": "kWh", "kilowatt hour": "kWh", "kilowatt hours": "kWh", "mwh": "MWh", "megawatt hour": "MWh", "megawatt hours": "MWh"},
        "diesel_fuel": {"l": "L", "litre": "L", "litres": "L", "liter": "L", "liters": "L", "ml": "mL", "millilitre": "mL", "millilitres": "mL", "milliliter": "mL", "milliliters": "mL", "kl": "kL", "kilolitre": "kL", "kilolitres": "kL", "kiloliter": "kL", "kiloliters": "kL"},
        "lpg": {"kg": "kg", "kilogram": "kg", "kilograms": "kg"},
        "purchased_materials": {"kg": "kg", "kilogram": "kg", "kilograms": "kg", "g": "g", "gram": "g", "grams": "g", "tonne": "tonne", "tonnes": "tonne", "t": "tonne"},
        "selected_transport": {"tonne-km": "tonne_km", "tonne km": "tonne_km", "tonne_kilometre": "tonne_km", "tonne kilometres": "tonne_km", "tonne kilometer": "tonne_km", "tonne kilometers": "tonne_km", "km": "km", "kilometre": "km", "kilometres": "km", "kilometer": "km", "kilometers": "km", "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m", "kg": "kg", "kilogram": "kg", "kilograms": "kg", "tonne": "tonne", "tonnes": "tonne", "t": "tonne"},
    }
    normalized = aliases.get(activity["id"], {}).get(query)
    if normalized is None:
        # Preserve an explicitly listed canonical unit while still rejecting unknown units.
        for listed in activity.get("document_units", []):
            if query == " ".join(listed.casefold().replace("_", " ").split()):
                normalized = listed
                break
    if normalized is None or normalized not in activity.get("document_units", []):
        raise ValidationError("That unit is not listed for this activity in the GreenLedger definitions.")
    return normalized


def parse_quantity(raw_quantity):
    value_text = (raw_quantity or "").strip()
    if not value_text:
        raise ValidationError("Enter a quantity.")
    # Accept a decimal point or a single decimal comma; reject ambiguous thousands separators.
    if "," in value_text:
        if "." in value_text or value_text.count(",") != 1:
            raise ValidationError("Use an unambiguous number, such as 250 or 2.5.")
        value_text = value_text.replace(",", ".")
    try:
        value = Decimal(value_text)
    except InvalidOperation:
        raise ValidationError("Enter a valid numeric quantity.")
    if not value.is_finite() or value <= 0:
        raise ValidationError("Quantity must be a finite number greater than zero.")
    return value


def normalize_quantity(activity, quantity, unit):
    canonical = activity["canonical_unit"]
    conversions = {rule["input_unit"]: rule for rule in activity.get("conversion_rules", [])}
    if unit == canonical:
        return quantity, canonical, "No unit conversion; document unit matches canonical unit."
    rule = conversions.get(unit)
    if not rule or rule.get("output_unit") != canonical:
        return None, canonical, "No documented conversion rule in the GreenLedger activity definition."
    multiplier = Decimal(str(rule["multiplier"]))
    return quantity * multiplier, canonical, "{} × {} = {} {}. Basis: {}".format(
        quantity, multiplier, quantity * multiplier, canonical, rule["basis"]
    )


def classify_scope(activity_id, context):
    """Return only categories authorized by the existing GreenLedger mapping."""
    mappings = {item["activity_id"]: item for item in load_mappings()}
    mapping = mappings[activity_id]
    if activity_id == "purchased_electricity":
        if context.get("electricity_use") == "purchased_and_consumed":
            return "Scope 2", "purchased electricity", "APPROVED"
        return None, None, "HUMAN_REVIEW: confirm purchased electricity was consumed in company operations."
    if activity_id == "diesel_fuel":
        if context.get("combusted") == "yes" and context.get("controlled") == "yes":
            source = context.get("source_type")
            if source == "stationary":
                return "Scope 1", "stationary combustion", "APPROVED"
            if source == "mobile":
                return "Scope 1", "mobile combustion", "APPROVED"
        return None, None, "HUMAN_REVIEW: combustion, control, or stationary/mobile source context is incomplete."
    if activity_id == "lpg":
        if context.get("combusted") == "yes" and context.get("controlled") == "yes" and context.get("source_type") == "stationary":
            return "Scope 1", "stationary combustion", "APPROVED"
        return None, None, "HUMAN_REVIEW: confirm actual combustion by an owned/controlled stationary source."
    if activity_id == "purchased_materials":
        if context.get("material_identity") in MATERIAL_IDENTITIES:
            return "Scope 3", "Category 1 - Purchased goods and services", "APPROVED: approved material identity selected."
        return None, None, "HUMAN_REVIEW: select one unambiguous approved material identity (PPC cement, steel rebar, or generic steel)."
    if activity_id == "selected_transport":
        scenario = context.get("transport_scenario")
        if scenario == "upstream_purchased":
            return "Scope 3", "Category 4 - Upstream transportation and distribution", "APPROVED"
        if scenario == "downstream_sold_product":
            return "Scope 3", "Category 9 - Downstream transportation and distribution", "APPROVED"
        if scenario == "company_controlled":
            return "Scope 1", "mobile combustion; fuel data required", "APPROVED"
        return None, None, "HUMAN_REVIEW: transport direction, purchase, or ownership boundary is missing."
    return None, None, "HUMAN_REVIEW: no approved scope mapping exists."


def retrieve_factor(activity, unit, scope, scope_category, context):
    """Retrieve a matching, nonempty CO2e factor; never return CO2-only references."""
    if not scope or not scope_category:
        return None, "FACTOR_NOT_VERIFIED: scope/category context is unresolved."
    if activity["id"] == "lpg":
        if not (
            context.get("combusted") == "yes"
            and context.get("controlled") == "yes"
            and context.get("source_type") == "stationary"
            and context.get("commercial_institutional") == "yes"
            and unit == "kg"
        ):
            return None, "FACTOR_NOT_VERIFIED: the conditional LPG factor requires verified net kg actually combusted by an owned/controlled commercial or institutional stationary source."
        lpg_rows = [row for row in load_factors() if row.get("factor_id") == LPG_FACTOR_ID]
        if len(lpg_rows) == 1 and lpg_rows[0].get("verification_status") == "PENDING_REVALIDATION":
            return None, "FACTOR_NOT_VERIFIED: Eligible LPG factor is pending independent revalidation."
        if len(lpg_rows) == 1 and not (
            lpg_rows[0].get("gas_basis") == "CO2e"
            and lpg_rows[0].get("system_boundary") == "SCOPE1_STATIONARY_COMBUSTION_1A4A"
            and lpg_rows[0].get("geography_code") == "GLOBAL"
            and lpg_rows[0].get("applicable_period") == "NOT_YEAR_SPECIFIC"
            and lpg_rows[0].get("methodology_id") == "IPCC_2006_TIER1_AR6_GWP100"
            and lpg_rows[0].get("vehicle_class") == "NOT_APPLICABLE"
            and lpg_rows[0].get("product_class") == "LPG_FUEL"
        ):
            return None, "FACTOR_NOT_VERIFIED: LPG factor applicability metadata does not match this Scope 1 stationary case."
    if activity["id"] == "diesel_fuel" and scope_category == "mobile combustion":
        if not (
            context.get("combusted") == "yes"
            and context.get("controlled") == "yes"
            and context.get("source_type") == "mobile"
            and context.get("vehicle_class") == "ROAD_VEHICLE"
            and context.get("geography_code") == "INDIA"
        ):
            return None, (
                "FACTOR_NOT_VERIFIED: the India road-diesel TTW factor requires confirmed combustion "
                "by an owned/controlled road vehicle and India geography."
            )
    if activity["id"] == "purchased_materials":
        material_identity = context.get("material_identity")
        if material_identity not in MATERIAL_IDENTITIES:
            return None, "FACTOR_NOT_VERIFIED: an exact approved material identity is required; no material fallback is used."
        if context.get("geography_code") != "INDIA":
            return None, "FACTOR_NOT_VERIFIED: the selected CPWD material reference is India-specific; confirm India geography."
    if activity["id"] == "selected_transport":
        if scope != "Scope 3" or scope_category not in {
            "Category 4 - Upstream transportation and distribution",
            "Category 9 - Downstream transportation and distribution",
        }:
            return None, "FACTOR_NOT_VERIFIED: only third-party Scope 3 Category 4/9 India road freight is supported."
        if context.get("transport_mode") != "road" or context.get("geography_code") != "INDIA":
            return None, "FACTOR_NOT_VERIFIED: this factor set requires confirmed India road freight."
        if context.get("transport_vehicle_class") not in TRANSPORT_VEHICLE_CLASSES:
            return None, "FACTOR_NOT_VERIFIED: a supported, unambiguous road-freight vehicle GVW class is required."
    candidates = []
    for row in load_factors():
        if row.get("normalized_activity") != activity["id"]:
            continue
        catalog_scope = (row.get("scope") or "").split("(", 1)[0].strip()
        if row.get("activity_unit") != unit or catalog_scope != scope:
            continue
        if activity["id"] == "selected_transport":
            if row.get("scope_category") != TRANSPORT_SCOPE_CATEGORY:
                continue
            if row.get("vehicle_class") != context.get("transport_vehicle_class"):
                continue
            if not (
                row.get("system_boundary") == "SCOPE3_ROAD_FREIGHT_WTW"
                and row.get("geography_code") == "INDIA"
                and row.get("product_class") == "ROAD_FREIGHT_SERVICE"
            ):
                continue
        elif row.get("scope_category") != scope_category:
            continue
        if activity["id"] == "purchased_materials":
            if row.get("product_class") != context.get("material_identity"):
                continue
            if row.get("system_boundary") != "SCOPE3_PURCHASED_MATERIAL_CRADLE_TO_GATE":
                continue
        if row.get("verification_status") not in {"VERIFIED_CO2E", "VERIFIED_TIER1_CONDITIONAL"}:
            continue
        if row.get("gas_basis") != "CO2e":
            continue
        if row.get("factor_id") == SFC_INDIA_ROAD_DIESEL_FACTOR_ID:
            if not (
                row.get("system_boundary") == "SCOPE1_ROAD_MOBILE_TTW"
                and row.get("geography_code") == "INDIA"
                and row.get("applicable_period") == "NOT_YEAR_SPECIFIC"
                and row.get("methodology_id") == "SFC_INDIA_V1_ROAD_DIESEL_TTW"
                and row.get("vehicle_class") == "ROAD_VEHICLE_CLASS_INDEPENDENT"
                and row.get("product_class") == "ROAD_DIESEL"
                and context.get("vehicle_class") == "ROAD_VEHICLE"
                and context.get("geography_code") == row.get("geography_code")
            ):
                continue
        if not row.get("factor_value") or "co2e" not in row.get("factor_unit", "").casefold():
            continue
        candidates.append(row)
    if not candidates:
        return None, "FACTOR_NOT_VERIFIED: no eligible verified CO2e factor matches this activity, unit, scope/category, and context."
    # The v1 LPG factor is the only eligible factor. For future catalog additions, ambiguity must abstain.
    if len(candidates) != 1:
        return None, "HUMAN_REVIEW: multiple eligible factors match; a documented selection rule is required."
    return candidates[0], "Verified factor matched to activity, unit, and scope/category."


def retrieve_co2_factor(activity, unit, scope, scope_category, context):
    """Retrieve only the selected CEA V22 electricity CO2 reference for a CO2 result."""
    if not (
        activity["id"] == "purchased_electricity"
        and unit == "kWh"
        and scope == "Scope 2"
        and scope_category in {"purchased electricity", "purchased electricity (location-based)"}
        and context.get("electricity_use") == "purchased_and_consumed"
        and context.get("geography_code") == "INDIA_GRID"
    ):
        return None, (
            "CO2_FACTOR_NOT_VERIFIED: purchased electricity, kWh, Scope 2, confirmed location-based use, "
            "and India grid geography are required."
        )
    if not context.get("applicable_period"):
        return None, "CO2_FACTOR_NOT_VERIFIED: the electricity billing period is required to match the selected FY2025-26 factor."

    matches = [row for row in load_factors() if row.get("factor_id") == CEA_V22_ELECTRICITY_FACTOR_ID]
    if len(matches) != 1:
        return None, "CO2_FACTOR_NOT_VERIFIED: the selected CEA V22 electricity reference is missing or ambiguous."
    factor = matches[0]
    if context.get("applicable_period") != factor.get("applicable_period"):
        return None, "CO2_FACTOR_NOT_VERIFIED: the electricity billing period does not match the selected factor period FY2025-26."
    if not (
        factor.get("normalized_activity") == "purchased_electricity"
        and factor.get("activity_unit") == "kWh"
        and factor.get("scope") == "Scope 2"
        and factor.get("scope_category") == "purchased electricity (location-based)"
        and factor.get("factor_unit") == "kgCO2/kWh"
        and factor.get("applicable_year") == "FY2025-26"
        and factor.get("verification_status") == "VERIFIED_CO2_ONLY_SELECTED_REFERENCE"
        and factor.get("factor_value")
        and factor.get("gas_basis") == "CO2"
        and factor.get("system_boundary") == "SCOPE2_LOCATION_BASED_GRID_AVERAGE"
        and factor.get("geography_code") == "INDIA_GRID"
        and factor.get("applicable_period") == "FY2025-26"
        and factor.get("methodology_id") == "CEA_V22_WEIGHTED_AVERAGE_GRID_INCL_RES_CAPTIVE"
        and factor.get("product_class") == "GRID_ELECTRICITY"
    ):
        return None, "CO2_FACTOR_NOT_VERIFIED: the selected CEA V22 electricity reference does not match its approved CO2-only applicability."
    return factor, "Verified CEA V22 CO2-only electricity reference matched."


def _multiply_by_factor(quantity, factor):
    """Use exact decimal multiplication for either explicitly labeled gas basis."""
    return quantity * Decimal(factor["factor_value"])


def normalize_transport_activity_data(activity, fields):
    """Convert explicit freight mass and distance to tonne-kilometres using SI scaling."""
    mass = parse_quantity(fields.get("shipment_mass")) if (fields.get("shipment_mass") or "").strip() else None
    distance = parse_quantity(fields.get("distance")) if (fields.get("distance") or "").strip() else None
    mass_unit = normalize_unit(activity, fields.get("mass_unit")) if mass is not None else None
    distance_unit = normalize_unit(activity, fields.get("distance_unit")) if distance is not None else None

    mass_to_tonnes = {"kg": Decimal("0.001"), "tonne": Decimal("1")}
    distance_to_km = {"m": Decimal("0.001"), "km": Decimal("1")}
    if mass is not None and mass_unit not in mass_to_tonnes:
        raise ValidationError("Road-freight shipment mass must be entered in kg or tonnes.")
    if distance is not None and distance_unit not in distance_to_km:
        raise ValidationError("Road-freight distance must be entered in metres or kilometres.")

    mass_tonnes = mass * mass_to_tonnes[mass_unit] if mass is not None else None
    distance_km = distance * distance_to_km[distance_unit] if distance is not None else None
    tonne_km = mass_tonnes * distance_km if mass_tonnes is not None and distance_km is not None else None
    parts = []
    if mass is None:
        parts.append("shipment mass is missing")
    else:
        parts.append("{} {} × {} = {} tonnes".format(mass, mass_unit, mass_to_tonnes[mass_unit], mass_tonnes))
    if distance is None:
        parts.append("distance is missing")
    else:
        parts.append("{} {} × {} = {} km".format(distance, distance_unit, distance_to_km[distance_unit], distance_km))
    if tonne_km is not None:
        parts.append("{} tonnes × {} km = {} tonne_km".format(mass_tonnes, distance_km, tonne_km))
    trace = "; ".join(parts) + " Exact SI scaling; factor basis is tonne_km."
    return {
        "shipment_mass_input": mass,
        "mass_unit_input": mass_unit,
        "shipment_mass_tonnes": mass_tonnes,
        "distance_input": distance,
        "distance_unit_input": distance_unit,
        "distance_km": distance_km,
        "tonne_km": tonne_km,
        "conversion_trace": trace,
    }


def evaluate_submission(fields):
    activity = normalize_activity(fields.get("activity"))
    transport_data = None
    material_identity = normalize_material_identity(fields.get("material_identity"))
    if activity["id"] == "selected_transport":
        transport_data = normalize_transport_activity_data(activity, fields)
        quantity_normalized = transport_data["tonne_km"]
        canonical_unit = "tonne_km"
        quantity = quantity_normalized
        unit = "tonne_km"
        conversion_trace = transport_data["conversion_trace"]
    else:
        quantity = parse_quantity(fields.get("quantity"))
        unit = normalize_unit(activity, fields.get("unit"))
        quantity_normalized, canonical_unit, conversion_trace = normalize_quantity(activity, quantity, unit)
    context = {key: fields.get(key, "unknown") for key in (
        "electricity_use", "combusted", "controlled", "source_type",
        "commercial_institutional", "transport_scenario", "transport_mode", "geography_code",
        "vehicle_class", "applicable_period"
    )}
    context["material_identity"] = material_identity
    context["transport_vehicle_class"] = normalize_transport_vehicle_class(fields.get("transport_vehicle_class"))
    scope, category, classification_status = classify_scope(activity["id"], context)
    if quantity_normalized is None:
        factor = None
        if activity["id"] == "selected_transport":
            missing = []
            if transport_data["shipment_mass_tonnes"] is None:
                missing.append("shipment mass")
            if transport_data["distance_km"] is None:
                missing.append("distance")
            factor_status = "FACTOR_NOT_VERIFIED: required road-freight input(s) missing: {}.".format(" and ".join(missing))
        else:
            factor_status = "FACTOR_NOT_VERIFIED: the activity quantity could not be normalized to its canonical unit."
    else:
        factor, factor_status = retrieve_factor(activity, canonical_unit, scope, category, context)

    if quantity_normalized is None:
        co2_factor = None
        co2_factor_status = "CO2_FACTOR_NOT_VERIFIED: the activity quantity could not be normalized to its canonical unit."
    else:
        co2_factor, co2_factor_status = retrieve_co2_factor(activity, canonical_unit, scope, category, context)

    confirmed = fields.get("fields_confirmed") == "yes"

    co2e = None
    calculation_trace = None
    if confirmed and scope and quantity_normalized is not None and factor is not None:
        co2e = _multiply_by_factor(quantity_normalized, factor)
        calculation_trace = "{} {} × {} {} = {} kgCO2e".format(
            quantity_normalized, canonical_unit, factor["factor_value"], factor["factor_unit"], co2e
        )

    co2_kg = None
    co2_calculation_trace = None
    if confirmed and scope and quantity_normalized is not None and co2_factor is not None:
        co2_kg = _multiply_by_factor(quantity_normalized, co2_factor)
        co2_calculation_trace = "{} {} × {} {} = {} kgCO2".format(
            quantity_normalized, canonical_unit, co2_factor["factor_value"], co2_factor["factor_unit"], co2_kg
        )

    review_reasons = []
    if not confirmed:
        review_reasons.append("Confirm extracted/manual fields against the source document.")
    if not scope:
        review_reasons.append(classification_status)
    if quantity_normalized is None:
        review_reasons.append("Unit conversion is unavailable; quantity cannot be normalized safely.")
    if not factor and co2_kg is None:
        review_reasons.append(factor_status)
        if activity["id"] == "purchased_electricity":
            review_reasons.append(co2_factor_status)

    return {
        "activity": activity,
        "document_type": activity.get("document_types", ["unknown"])[0],
        "document_date": (fields.get("document_date") or "").strip() or None,
        "supplier": (fields.get("supplier") or "").strip() or None,
        "quantity": quantity,
        "unit": unit,
        "normalized_quantity": quantity_normalized,
        "canonical_unit": canonical_unit,
        "conversion_trace": conversion_trace,
        "scope": scope,
        "scope_category": category,
        "classification_status": classification_status,
        "factor": factor,
        "factor_status": factor_status,
        "material_identity": material_identity,
        "transport_vehicle_class": context["transport_vehicle_class"],
        "transport_mode": fields.get("transport_mode"),
        "transport_data": transport_data,
        "co2e": co2e,
        "calculation_trace": calculation_trace,
        "co2_factor": co2_factor,
        "co2_factor_status": co2_factor_status,
        "co2_kg": co2_kg,
        "co2_gas_basis": "CO2",
        "co2_result_unit": "kgCO2",
        "co2_calculation_trace": co2_calculation_trace,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
        "confidence": "Not assessed: carbon-field confidence is not calibrated; values were entered manually.",
        "human_verification": "USER_CONFIRMED" if confirmed else "PENDING",
    }


def make_json_trace(result, document_name=None, ocr_result=None):
    factor = result["factor"]
    return {
        "application": "GreenLedger local baseline",
        "document": {
            "filename": document_name,
            "date_or_period_entered": result["document_date"],
            "supplier_entered": result["supplier"],
            "processing": "transient local OCR and manual field entry; uploaded document is not persisted" if ocr_result else "manual entry; uploaded document is not persisted",
            "source_sha256": ocr_result.get("sha256") if ocr_result else None,
        },
        "document_type": result["document_type"],
        "activity": result["activity"]["id"],
        "extraction": {
            "mode": "manual human input; OCR transcript is assistive only; no AI field extraction was run" if ocr_result else "manual human input; no OCR or AI extraction was run",
            "quantity": str(result["quantity"]),
            "unit": result["unit"],
            "human_verification": result["human_verification"],
            "confidence": result["confidence"],
            "ocr_result": ocr_result,
            "material_identity": result["material_identity"],
            "transport_vehicle_class": result["transport_vehicle_class"],
        },
        "normalized_activity_data": {
            "quantity": str(result["normalized_quantity"]) if result["normalized_quantity"] is not None else None,
            "unit": result["canonical_unit"],
            "conversion_trace": result["conversion_trace"],
            "material_identity": result["material_identity"],
            "transport": ({
                "mode": result["transport_mode"],
                "vehicle_class": result["transport_vehicle_class"],
                "shipment_mass_input": str(result["transport_data"]["shipment_mass_input"]) if result["transport_data"]["shipment_mass_input"] is not None else None,
                "mass_unit_input": result["transport_data"]["mass_unit_input"],
                "shipment_mass_tonnes": str(result["transport_data"]["shipment_mass_tonnes"]) if result["transport_data"]["shipment_mass_tonnes"] is not None else None,
                "distance_input": str(result["transport_data"]["distance_input"]) if result["transport_data"]["distance_input"] is not None else None,
                "distance_unit_input": result["transport_data"]["distance_unit_input"],
                "distance_km": str(result["transport_data"]["distance_km"]) if result["transport_data"]["distance_km"] is not None else None,
                "tonne_km": str(result["transport_data"]["tonne_km"]) if result["transport_data"]["tonne_km"] is not None else None,
            } if result["transport_data"] else None),
        },
        "classification": {
            "scope": result["scope"],
            "scope_category": result["scope_category"],
            "status": result["classification_status"],
        },
        "factor": ({
            "factor_id": factor["factor_id"],
            "scope": factor["scope"],
            "scope_category": factor["scope_category"],
            "factor_value": factor["factor_value"],
            "factor_unit": factor["factor_unit"],
            "gas_basis": factor["gas_basis"],
            "system_boundary": factor["system_boundary"],
            "geography_code": factor["geography_code"],
            "applicable_period": factor["applicable_period"],
            "methodology_id": factor["methodology_id"],
            "vehicle_class": factor["vehicle_class"],
            "product_class": factor["product_class"],
            "source": factor["source"],
            "source_version": factor["source_version"],
            "source_url": factor["source_url"],
            "geography": factor["geography"],
            "applicable_year": factor["applicable_year"],
            "methodology": factor["methodology"],
            "verification_status": factor["verification_status"],
            "source_sha256": factor["source_sha256"],
        } if factor else {"status": result["factor_status"]}),
        "calculation": {"co2e_kg": str(result["co2e"]) if result["co2e"] is not None else None, "trace": result["calculation_trace"]},
        "co2_calculation": ({
            "gas_basis": "CO2",
            "result_unit": "kgCO2",
            "co2_kg": str(result["co2_kg"]),
            "factor": {
                "factor_id": result["co2_factor"]["factor_id"],
                "factor_value": result["co2_factor"]["factor_value"],
                "factor_unit": result["co2_factor"]["factor_unit"],
                "gas_basis": "CO2",
                "system_boundary": result["co2_factor"]["system_boundary"],
                "scope": result["scope"],
                "category": result["co2_factor"]["scope_category"],
                "geography": result["co2_factor"]["geography"],
                "geography_code": result["co2_factor"]["geography_code"],
                "applicable_year": result["co2_factor"]["applicable_year"],
                "applicable_period": result["co2_factor"]["applicable_period"],
                "methodology": result["co2_factor"]["methodology"],
                "methodology_id": result["co2_factor"]["methodology_id"],
                "vehicle_class": result["co2_factor"]["vehicle_class"],
                "product_class": result["co2_factor"]["product_class"],
                "source": result["co2_factor"]["source"],
                "source_version": result["co2_factor"]["source_version"],
                "source_url": result["co2_factor"]["source_url"],
                "verification_status": result["co2_factor"]["verification_status"],
                "source_sha256": result["co2_factor"]["source_sha256"],
            },
            "trace": result["co2_calculation_trace"],
        } if result["co2_kg"] is not None else {
            "gas_basis": "CO2",
            "result_unit": "kgCO2",
            "co2_kg": None,
            "status": result["co2_factor_status"],
            "trace": None,
        }),
        "human_review": {"required": result["review_required"], "reasons": result["review_reasons"]},
    }
