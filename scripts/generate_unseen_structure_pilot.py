"""Generate a separate synthetic GreenLedger document-structure pilot.

This generator is independent of generate_synthetic_benchmark.py. It uses a
ReportLab vector-PDF renderer and a separate raster scene renderer. Rasterized
scan and phone-style effects are explicitly simulations, not real captures.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get(
    "GREENLEDGER_PILOT_OUTPUT",
    str(ROOT / "data" / "benchmark" / "greenledger_unseen_structure_pilot_120_2026-11-15"),
)).resolve()
STAGING = OUTPUT.with_name(OUTPUT.name + ".building")
SEED = 20261115
GENERATOR_VERSION = "1.0.1"
PIXELS_PER_POINT = 2

sys.path.insert(0, str(ROOT))
from greenledger.core import (  # noqa: E402
    evaluate_submission, make_json_trace, normalize_activity, normalize_quantity,
    normalize_unit, parse_quantity,
)


DOMAIN_CODES = {
    "electricity": "E",
    "diesel": "D",
    "lpg": "L",
    "materials": "M",
    "freight": "F",
}

SUPPLIERS = {
    "electricity": [
        "Alderbrook Metering Cooperative", "Meridian Vale Power", "Copper Finch Electric",
        "Harborlight Grid Services", "Juniper Current Works", "Northwind Utility House",
        "Cinderleaf Energy Office", "Mosaic River Power",
    ],
    "diesel": [
        "Ternway Fuel Merchants", "Moss Harbor Petroleum", "Red Kite Fleet Supply",
        "Ironwood Motor Fuels", "Cobalt Road Energy", "Brackenfield Fuel Depot",
        "Westmere Pump House", "Lantern Ridge Oil Supply",
    ],
    "lpg": [
        "Willow Arc Gas Trading", "Blue Thistle Cylinder Co.", "Saffron Gate Energy",
        "Pineglass Gas Services", "Oriole Hearth Supply", "Dunefield LPG House",
        "Silver Quay Gasworks", "Cloverline Fuel Partners",
    ],
    "materials": [
        "Stonebridge Materials Exchange", "Redfern Cement & Metals", "Kestrel Build Supply",
        "Marlowe Industrial Stores", "Cedarspan Works", "Quarrylight Procurement",
        "Aster Forge Materials", "Maple Strand Builders Supply",
    ],
    "freight": [
        "Longway Carriage Office", "Hearthside Road Logistics", "Peregrine Haulage Group",
        "Westhaven Cartage", "Milepost Freight Union", "Cairn Route Services",
        "Tallowwood Carriers", "Cloudbank Transit House",
    ],
}

CUSTOMERS = [
    "Blue Orchard Foods", "Asterloom Components", "Morrowfield Workshop", "Sandalwood Health Kitchen",
    "Pinecone Paper Works", "Red Clay Fabrication", "Maple Lantern Textiles", "Crescent Bay Traders",
    "Hilltop Grain Rooms", "Copper Fern Packaging", "North Gate Engineering", "Willow Bend Hospitality",
]

PALETTES = [
    ("#20364A", "#EEF3F6", "#D5E0E7"), ("#385442", "#EFF4EF", "#DCE8DC"),
    ("#643F56", "#F5EFF3", "#E7DCE4"), ("#795B2C", "#F7F2E8", "#E9DFC7"),
    ("#334F83", "#EEF1F8", "#DCE3F1"), ("#4D555C", "#F1F2F2", "#DDE0E2"),
    ("#8A463C", "#F7EFED", "#EBDDD9"), ("#28636B", "#EDF5F5", "#D6E8E8"),
]

FONT_PATHS = {
    ("sans", False): Path(r"C:\Windows\Fonts\arial.ttf"),
    ("sans", True): Path(r"C:\Windows\Fonts\arialbd.ttf"),
    ("serif", False): Path(r"C:\Windows\Fonts\times.ttf"),
    ("serif", True): Path(r"C:\Windows\Fonts\timesbd.ttf"),
    ("mono", False): Path(r"C:\Windows\Fonts\cour.ttf"),
    ("mono", True): Path(r"C:\Windows\Fonts\courbd.ttf"),
    ("humanist", False): Path(r"C:\Windows\Fonts\calibri.ttf"),
    ("humanist", True): Path(r"C:\Windows\Fonts\calibrib.ttf"),
}

PDF_FONTS = {
    ("sans", False): "Helvetica", ("sans", True): "Helvetica-Bold",
    ("serif", False): "Times-Roman", ("serif", True): "Times-Bold",
    ("mono", False): "Courier", ("mono", True): "Courier-Bold",
    ("humanist", False): "Helvetica", ("humanist", True): "Helvetica-Bold",
}

LAYOUTS = {
    "electricity": [
        ("utility_account_statement", "ledger"), ("meter_reading_register", "table"),
        ("billing_portal_export", "floating_cards"), ("consumption_adjustment_letter", "prose"),
        ("site_usage_schedule", "annex"),
    ],
    "diesel": [
        ("forecourt_purchase_slip", "thermal"), ("fleet_card_period_statement", "ledger"),
        ("bulk_delivery_ticket", "table"), ("vehicle_fuel_claim", "prose"),
        ("tank_issue_record", "floating_cards"),
    ],
    "lpg": [
        ("cylinder_delivery_note", "thermal"), ("commercial_gas_account", "ledger"),
        ("bulk_tank_gauge_log", "table"), ("refill_counter_record", "floating_cards"),
        ("institutional_supply_letter", "prose"),
    ],
    "materials": [
        ("purchase_schedule", "table"), ("weighbridge_ticket", "thermal"),
        ("purchase_order_memo", "prose"), ("goods_receipt_cards", "floating_cards"),
        ("mill_dispatch_ledger", "ledger"), ("warehouse_issue_schedule", "annex"),
    ],
    "freight": [
        ("consignment_note", "floating_cards"), ("lorry_receipt", "thermal"),
        ("carrier_invoice_lines", "table"), ("dispatch_manifest", "ledger"),
        ("route_service_letter", "prose"), ("proof_of_delivery_schedule", "annex"),
    ],
}

PAGE_SIZES = {
    "A4_portrait": (595.0, 842.0),
    "letter_portrait": (612.0, 792.0),
    "A4_landscape": (842.0, 595.0),
    "legal_portrait": (612.0, 1008.0),
    "narrow_receipt": (300.0, 720.0),
}

VEHICLE_CLASSES = [
    ("ROAD_GVW_LT_3_5_T", "<3.5 t"),
    ("ROAD_GVW_3_5_T", "3-5 t"),
    ("ROAD_GVW_5_12_T", "5-12 t"),
    ("ROAD_GVW_12_20_T", "12-20 t"),
    ("ROAD_GVW_20_30_T", "20-30 t"),
    ("ROAD_GVW_30_50_T", "30-50 t"),
    ("ROAD_TRACTOR_TRAILER_GVW_30_60_T", "30-60 t tractor-trailer"),
]

FORBIDDEN_VISIBLE_TERMS = (
    "accounting-ready", "accounting ready", "incomplete evidence", "ambiguous",
    "ground truth", "expected result", "kgco2e", "factor_id", "scope 1", "scope 2", "scope 3",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_ref(name: str, candidate_index: int | None = None, candidate_value: Any = None,
             candidate_unit: str | None = None) -> dict[str, Any]:
    return {
        "field_name": name,
        "candidate_index": candidate_index,
        "candidate_value": candidate_value,
        "candidate_unit": candidate_unit,
    }


def make_field(name: str, status: str, raw_value: Any = None, normalized_value: Any = None,
              raw_unit: str | None = None, normalized_unit: str | None = None,
              missing_reason: str | None = None, ambiguity_reason: str | None = None,
              candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "field_name": name,
        "presence_status": status,
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "raw_unit": raw_unit,
        "normalized_unit": normalized_unit,
        "evidence": [],
        "missing_evidence_reason": missing_reason,
        "ambiguity_reason": ambiguity_reason,
        "candidates": candidates or [],
    }


def make_item(text: str, refs: list[dict[str, Any]] | None = None, group: str = "body") -> dict[str, Any]:
    return {"text": text, "refs": refs or [], "group": group}


def add_visible_field(fields: dict[str, dict[str, Any]], items: list[dict[str, Any]], name: str,
                      label: str, raw_value: Any, normalized_value: Any = None,
                      raw_unit: str | None = None, normalized_unit: str | None = None,
                      displayed_value: str | None = None, group: str = "body") -> None:
    fields[name] = make_field(name, "present", raw_value, normalized_value, raw_unit, normalized_unit)
    display = str(raw_value if displayed_value is None else displayed_value)
    unit_suffix = f" {raw_unit}" if raw_unit and raw_unit.casefold() not in display.casefold() else ""
    text = f"{label}: {display}{unit_suffix}"
    refs = [make_ref(name)]
    items.append(make_item(text, refs, group))
    unit_name = {"quantity": "unit", "shipment_mass": "shipment_mass_unit", "distance": "distance_unit"}.get(name)
    if unit_name and raw_unit:
        fields[unit_name] = make_field(unit_name, "present", raw_unit, normalized_unit, raw_unit, normalized_unit)
        refs.append(make_ref(unit_name))


def add_ambiguous_field(fields: dict[str, dict[str, Any]], items: list[dict[str, Any]], name: str,
                        label_values: list[tuple[str, Any, str | None]], reason: str,
                        group: str = "body") -> None:
    candidates = [{"raw_value": raw, "raw_unit": unit} for _label, raw, unit in label_values]
    fields[name] = make_field(name, "ambiguous", ambiguity_reason=reason, candidates=candidates)
    for i, (label, raw, unit) in enumerate(label_values):
        suffix = f" {unit}" if unit else ""
        items.append(make_item(f"{label}: {raw}{suffix}", [make_ref(name, i, raw, unit)], group))


def add_missing_field(fields: dict[str, dict[str, Any]], name: str, reason: str,
                      raw_unit: str | None = None) -> None:
    fields[name] = make_field(name, "not_present", raw_unit=raw_unit, missing_reason=reason)


def fmt_date(rng: random.Random, value: date) -> str:
    styles = [
        value.strftime("%d/%m/%Y"), value.strftime("%d-%b-%Y"),
        value.strftime("%Y-%m-%d"), value.strftime("%d %B %Y"),
    ]
    return rng.choice(styles)


def add_common_header_data(domain: str, local_index: int, rng: random.Random,
                           fields: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> tuple[str, str, str]:
    supplier = SUPPLIERS[domain][local_index % len(SUPPLIERS[domain])]
    customer = CUSTOMERS[(local_index * 3 + list(DOMAIN_CODES).index(domain)) % len(CUSTOMERS)]
    doc_date = date(2025, 4, 1) + timedelta(days=rng.randrange(0, 500))
    fields["supplier_name"] = make_field("supplier_name", "present", supplier, supplier)
    fields["document_date"] = make_field("document_date", "present", fmt_date(rng, doc_date), doc_date.isoformat())
    items.append(make_item(f"Prepared for {customer}", [], "metadata"))
    items.append(make_item(f"Desk reference: {rng.choice(['RV', 'QF', 'LN', 'VX'])}-{rng.randrange(14000, 99000)}", [], "noise"))
    return supplier, customer, fmt_date(rng, doc_date)


def build_electricity(local_index: int, state: str, rng: random.Random) -> tuple[dict, list[dict], dict]:
    fields: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    supplier, customer, doc_date = add_common_header_data("electricity", local_index, rng, fields, items)
    items.append(make_item(f"Account folio: {rng.randrange(100000, 999999)}", [], "noise"))
    activity_text = rng.choice(["Purchased grid electricity", "Electricity supplied to the business site", "Utility energy service"])
    add_visible_field(fields, items, "activity_description", rng.choice(["Service", "Charge class", "Supply description"]), activity_text, "purchased_electricity")
    add_visible_field(fields, items, "document_date", "Issue date", doc_date, fields["document_date"]["normalized_value"], displayed_value=doc_date)
    context_text = f"Account holder: {customer}; service address: {rng.choice(['Pune, Maharashtra', 'Kochi, Kerala', 'Indore, Madhya Pradesh', 'Jaipur, Rajasthan'])}; business site meter, grid supply used on premises"
    add_visible_field(fields, items, "electricity_use", "Service context", "purchased and consumed at business site", "purchased_and_consumed", displayed_value=context_text)
    fields["geography"] = make_field("geography", "present", "India grid", "INDIA_GRID")
    items.append(make_item(f"Grid area: India; service region {rng.choice(['West', 'South', 'Central', 'North'])} network", [make_ref("geography")]))
    q = f"{rng.randrange(85, 980)}.{rng.randrange(0, 10)}"
    unit = rng.choice(["kWh", "MWh"])
    if unit == "MWh":
        q = f"{rng.randrange(1, 8)}.{rng.randrange(1, 999):03d}"
        normalized = str(Decimal(q) * Decimal("1000"))
    else:
        normalized = q
    period_start = date(2025, rng.randrange(4, 13), 1)
    period_end = (period_start + timedelta(days=35)).replace(day=1) - timedelta(days=1)
    period = f"{fmt_date(rng, period_start)} to {fmt_date(rng, period_end)} (FY 2025-26)"
    engine = {"activity": "purchased_electricity", "quantity": q, "unit": unit,
              "electricity_use": "purchased_and_consumed", "geography_code": "INDIA_GRID",
              "applicable_period": "FY2025-26", "fields_confirmed": "yes"}

    if state == "ready":
        add_visible_field(fields, items, "quantity", rng.choice(["Billed energy", "Metered consumption", "Active units"]), q, normalized, unit, "kWh", displayed_value=f"{q} {unit}")
        fields["unit"]["normalized_value"] = "kWh"
        fields["unit"]["normalized_unit"] = "kWh"
        add_visible_field(fields, items, "billing_period", "Billing window", period, "FY2025-26", displayed_value=period)
        items.append(make_item(f"Prior read: {rng.randrange(8000, 50000)}; current read: {rng.randrange(50000, 90000)}", [], "noise"))
        items.append(make_item(f"Total payable: INR {rng.randrange(1800, 89000)} incl. service charge", [], "noise"))
    elif state == "incomplete":
        missing = local_index % 3
        if missing == 0:
            add_visible_field(fields, items, "quantity", "Energy used", q, q, displayed_value=q)
            add_missing_field(fields, "unit", "The document gives a number but no consumption unit.")
            add_visible_field(fields, items, "billing_period", "Billing window", period, "FY2025-26", displayed_value=period)
        elif missing == 1:
            add_visible_field(fields, items, "quantity", "Energy used", q, q, unit, "kWh", displayed_value=f"{q} {unit}")
            fields["unit"]["normalized_value"] = "kWh"
            fields["unit"]["normalized_unit"] = "kWh"
            add_missing_field(fields, "billing_period", "No service/billing period is printed; the applicable factor period cannot be matched.")
        else:
            add_missing_field(fields, "quantity", "The bill shows a service period but no consumption quantity.")
            add_missing_field(fields, "unit", "No consumption unit is printed.")
            add_visible_field(fields, items, "billing_period", "Billing window", period, "FY2025-26", displayed_value=period)
        items.append(make_item(f"Network fee INR {rng.randrange(100, 900)}; tax line INR {rng.randrange(50, 500)}", [], "noise"))
    else:
        if local_index == 0:
            raw_quantity = "285"
            add_visible_field(fields, items, "quantity", "Energy used", raw_quantity,
                              normalized_value=None, displayed_value=raw_quantity)
            fields["unit"] = make_field(
                "unit", "ambiguous", ambiguity_reason="The quantity is shown without a unit and two nearby unit notations conflict.",
                candidates=[{"raw_value": "kWh"}, {"raw_value": "MWh"}],
            )
            items.append(make_item("Meter unit entry: kWh", [make_ref("unit", 0, "kWh")]))
            items.append(make_item("Billing unit entry: MWh", [make_ref("unit", 1, "MWh")]))
        else:
            add_ambiguous_field(fields, items, "quantity", [
                ("Consumption entry (statement copy)", q, unit),
                ("Consumption entry (account copy)", f"{rng.randrange(110, 850)}.{rng.randrange(0, 10)}", unit),
            ], "Two different consumption values are shown for the same period without a signed reconciliation or clear precedence.")
            fields["unit"] = make_field("unit", "present", unit, unit, unit, "kWh")
            items[-2]["refs"].append(make_ref("unit", 0, unit, unit))
            items[-1]["refs"].append(make_ref("unit", 0, unit, unit))
        add_visible_field(fields, items, "billing_period", "Service cycle", period, "FY2025-26", displayed_value=period)
        items.append(make_item(f"Payment reference {rng.randrange(1000000, 9999999)}", [], "noise"))

    if "billing_period" not in fields:
        add_missing_field(fields, "billing_period", "The document omits the billing period required to match the FY2025-26 electricity reference.")
    if "quantity" not in fields:
        add_missing_field(fields, "quantity", "No electricity consumption quantity is stated.")
    if "unit" not in fields:
        add_missing_field(fields, "unit", "No electricity consumption unit is stated.")
    return {"fields": fields, "items": items, "engine_fields": engine if state == "ready" else None, "supplier": supplier,
            "document_date": doc_date, "customer": customer, "domain": "electricity"}, items, engine if state == "ready" else None


def build_diesel(local_index: int, state: str, rng: random.Random) -> tuple[dict, list[dict], dict]:
    fields: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    supplier, customer, doc_date = add_common_header_data("diesel", local_index, rng, fields, items)
    activity_text = rng.choice(["High speed diesel", "Automotive diesel fuel", "HSD fuel supply"])
    add_visible_field(fields, items, "activity_description", rng.choice(["Fuel grade", "Product supplied", "Fuel type"]), activity_text, "diesel_fuel")
    add_visible_field(fields, items, "document_date", "Transaction date", doc_date, fields["document_date"]["normalized_value"], displayed_value=doc_date)
    q = str(rng.choice(["86.5", "245", "1.25", "320000"]))
    unit = {"86.5": "L", "245": "L", "1.25": "kL", "320000": "mL"}[q]
    engine = {"activity": "diesel_fuel", "quantity": q, "unit": unit, "combusted": "yes", "controlled": "yes",
              "source_type": "mobile", "vehicle_class": "ROAD_VEHICLE", "geography_code": "INDIA", "fields_confirmed": "yes"}
    fields["geography"] = make_field("geography", "present", "India", "INDIA")
    items.append(make_item("Place of supply: India; Maharashtra", [make_ref("geography")]))
    if state == "ready":
        add_visible_field(fields, items, "quantity", rng.choice(["Volume issued", "Net fuel dispensed", "Litres supplied"]), q, q, unit, "L", displayed_value=f"{q} {unit}")
        fields["unit"]["normalized_value"] = "L"
        fields["unit"]["normalized_unit"] = "L"
        vehicle_ref = f"company-operated service van {rng.choice(['MH-12-KX', 'KA-03-QM', 'GJ-01-TR'])}-{rng.randrange(1200, 9900)}"
        fields["vehicle_reference"] = make_field("vehicle_reference", "present", vehicle_ref, "ROAD_VEHICLE")
        items.append(make_item(f"Vehicle: {vehicle_ref}; fuel issued and consumed during route operations", [make_ref("source_type"), make_ref("combustion_status"), make_ref("operational_control"), make_ref("vehicle_reference")]))
        fields["source_type"] = make_field("source_type", "present", "company road vehicle", "mobile")
        fields["combustion_status"] = make_field("combustion_status", "present", "fuel consumed", "yes")
        fields["operational_control"] = make_field("operational_control", "present", "company-operated", "yes")
        fields["vehicle_reference"] = make_field("vehicle_reference", "present", f"company-operated service van", "ROAD_VEHICLE")
    elif state == "incomplete":
        add_visible_field(fields, items, "quantity", "Fuel issued", q, q, unit, "L", displayed_value=f"{q} {unit}")
        fields["unit"]["normalized_value"] = "L"
        fields["unit"]["normalized_unit"] = "L"
        items.append(make_item("Counter sale for customer collection; the record does not identify the consuming vehicle or operator", []))
        add_missing_field(fields, "source_type", "The document does not establish that the fuel was combusted by an owned or controlled road vehicle.")
        add_missing_field(fields, "operational_control", "The purchaser/vehicle control relationship is not stated.")
        add_missing_field(fields, "combustion_status", "A purchase is shown, but actual fuel consumption is not evidenced.")
        add_missing_field(fields, "vehicle_reference", "No vehicle or equipment reference is stated.")
    else:
        add_ambiguous_field(fields, items, "quantity", [
            ("Volume on issue docket", q, unit),
            ("Volume on fleet ledger", str(rng.choice(["79", "231", "1.05"])), unit),
        ], "The docket and fleet ledger show different fuel quantities without a signed reconciliation or clear precedence.")
        fields["unit"] = make_field("unit", "present", unit, unit, unit, "L")
        items[-2]["refs"].append(make_ref("unit", 0, unit, unit))
        items[-1]["refs"].append(make_ref("unit", 0, unit, unit))
        fields["source_type"] = make_field("source_type", "ambiguous", ambiguity_reason="The record alternately describes a company fleet issue and a customer collection.", candidates=[{"raw_value": "company vehicle"}, {"raw_value": "customer collection"}])
        fields["operational_control"] = make_field("operational_control", "ambiguous", ambiguity_reason="The ownership/control evidence conflicts.", candidates=[{"raw_value": "company vehicle"}, {"raw_value": "customer collection"}])
        items.append(make_item("Fleet allocation: company vehicle", [make_ref("source_type", 0, "company vehicle"), make_ref("operational_control", 0, "company vehicle")]))
        items.append(make_item("Counter record: customer collection", [make_ref("source_type", 1, "customer collection"), make_ref("operational_control", 1, "customer collection")]))
        fields["combustion_status"] = make_field(
            "combustion_status", "not_present",
            missing_reason="The document says fuel was issued to the fleet but does not state whether it was consumed."
        )
        items.append(make_item("Fuel issue note: issued to fleet; engine use not recorded", []))
    for name, reason in (("quantity", "No fuel volume is stated."), ("unit", "No fuel unit is stated."), ("source_type", "Road/mobile source type is not stated."), ("operational_control", "Control evidence is not stated."), ("combustion_status", "Consumption status is not stated."), ("vehicle_reference", "Vehicle reference is not stated.")):
        if name not in fields:
            add_missing_field(fields, name, reason)
    items.append(make_item(f"Taxable value INR {rng.randrange(1200, 38000)}; receipt code {rng.randrange(10000, 99999)}", [], "noise"))
    return {"fields": fields, "items": items, "engine_fields": engine if state == "ready" else None, "supplier": supplier,
            "document_date": doc_date, "customer": customer, "domain": "diesel"}, items, engine if state == "ready" else None


def build_lpg(local_index: int, state: str, rng: random.Random) -> tuple[dict, list[dict], dict]:
    fields: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    supplier, customer, doc_date = add_common_header_data("lpg", local_index, rng, fields, items)
    activity_text = rng.choice(["Commercial LPG refill", "Liquefied petroleum gas", "LPG supply for kitchen use"])
    add_visible_field(fields, items, "activity_description", rng.choice(["Commodity", "Supply description", "Product line"]), activity_text, "lpg")
    add_visible_field(fields, items, "document_date", "Delivery date", doc_date, fields["document_date"]["normalized_value"], displayed_value=doc_date)
    q = str(rng.choice(["14.2", "19", "28.5", "7.75"]))
    engine = {"activity": "lpg", "quantity": q, "unit": "kg", "combusted": "yes", "controlled": "yes",
              "source_type": "stationary", "commercial_institutional": "yes", "fields_confirmed": "yes"}
    fields["geography"] = make_field("geography", "present", "India", "INDIA")
    items.append(make_item("Delivery territory: India; business customer account", [make_ref("geography")]))
    if state == "ready":
        add_visible_field(fields, items, "quantity", "Net LPG mass", q, q, "kg", "kg", displayed_value=f"{q} kg")
        fields["unit"]["normalized_value"] = "kg"
        fields["unit"]["normalized_unit"] = "kg"
        fields["net_lpg_mass"] = make_field("net_lpg_mass", "present", q, q, "kg", "kg")
        items[-1]["refs"].append(make_ref("net_lpg_mass"))
        items.append(make_item("Use location: company-controlled commercial kitchen; LPG burned in fixed cooking equipment", [make_ref("combustion_status"), make_ref("operational_control"), make_ref("source_type"), make_ref("commercial_institutional")]))
        for name, raw, norm in (("combustion_status", "burned in fixed equipment", "yes"), ("operational_control", "company-controlled", "yes"), ("source_type", "fixed cooking equipment", "stationary"), ("commercial_institutional", "commercial kitchen", "yes")):
            fields[name] = make_field(name, "present", raw, norm)
    elif state == "incomplete":
        count = rng.randrange(1, 7)
        add_visible_field(fields, items, "quantity", "Refills delivered", str(count), str(count), "cylinder_count", None, displayed_value=f"{count} cylinders")
        fields["unit"]["normalized_value"] = None
        fields["unit"]["normalized_unit"] = None
        fields["net_lpg_mass"] = make_field("net_lpg_mass", "not_present", missing_reason="The receipt gives a cylinder count but no net LPG mass.")
        items.append(make_item("Commercial kitchen account; equipment details are not included on this supply copy", []))
        add_missing_field(fields, "combustion_status", "A refill purchase is shown, but actual combustion is not evidenced.")
        add_missing_field(fields, "operational_control", "The document does not establish that the source is owned or controlled by the reporting entity.")
        add_missing_field(fields, "source_type", "Stationary source context is not stated.")
        add_missing_field(fields, "commercial_institutional", "Commercial/institutional stationary use is not confirmed by the document.")
    else:
        q2 = str(rng.choice(["12.8", "17.4", "21.0"]))
        add_ambiguous_field(fields, items, "quantity", [
            ("Net fill mass (delivery copy)", q, "kg"),
            ("Net fill mass (account copy)", q2, "kg"),
        ], "Two different net LPG masses appear on separate copies without a signed reconciliation or clear precedence.")
        fields["unit"] = make_field("unit", "present", "kg", "kg", "kg", "kg")
        items[-2]["refs"].append(make_ref("unit", 0, "kg", "kg"))
        items[-1]["refs"].append(make_ref("unit", 1, "kg", "kg"))
        fields["net_lpg_mass"] = make_field("net_lpg_mass", "ambiguous", ambiguity_reason="The net-mass entries conflict.", candidates=[{"raw_value": q, "raw_unit": "kg"}, {"raw_value": q2, "raw_unit": "kg"}])
        items[-2]["refs"].append(make_ref("net_lpg_mass", 0, q, "kg"))
        items[-1]["refs"].append(make_ref("net_lpg_mass", 1, q2, "kg"))
        fields["commercial_institutional"] = make_field("commercial_institutional", "ambiguous", ambiguity_reason="Two customer-use entries conflict between institutional and residential contexts, with no reconciliation identifying the applicable site.", candidates=[{"raw_value": "institutional kitchen"}, {"raw_value": "residential use"}])
        items.append(make_item("Customer class entry (delivery copy): institutional kitchen", [make_ref("commercial_institutional", 0, "institutional kitchen")]))
        items.append(make_item("Customer class entry (account copy): residential use", [make_ref("commercial_institutional", 1, "residential use")]))
        for name, reason in (("combustion_status", "Actual combustion is not stated."), ("operational_control", "Control evidence is absent."), ("source_type", "Stationary source is not confirmed.")):
            add_missing_field(fields, name, reason)
    for name, reason in (("quantity", "LPG quantity is not stated."), ("unit", "LPG mass unit is not stated."), ("net_lpg_mass", "Net LPG mass is not stated."), ("combustion_status", "Actual LPG combustion is not evidenced."), ("operational_control", "Control context is not evidenced."), ("source_type", "Stationary source context is not evidenced."), ("commercial_institutional", "Commercial/institutional use is not evidenced.")):
        if name not in fields:
            add_missing_field(fields, name, reason)
    items.append(make_item(f"Container deposit INR {rng.randrange(250, 1800)}; account slip {rng.randrange(10000, 99999)}", [], "noise"))
    return {"fields": fields, "items": items, "engine_fields": engine if state == "ready" else None, "supplier": supplier,
            "document_date": doc_date, "customer": customer, "domain": "lpg"}, items, engine if state == "ready" else None


def build_material(local_index: int, state: str, identity: str, rng: random.Random) -> tuple[dict, list[dict], dict]:
    fields: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    supplier, customer, doc_date = add_common_header_data("materials", local_index, rng, fields, items)
    descriptions = {
        "ppc_cement": "Portland Pozzolana Cement (PPC)",
        "steel_rebar": "Reinforcing steel bar / rebar",
        "generic_steel": "Generic steel stock",
    }
    description = descriptions[identity]
    engine = {"activity": "purchased_materials", "quantity": "1250", "unit": "kg",
              "material_identity": identity, "geography_code": "INDIA", "fields_confirmed": "yes"}
    fields["geography"] = make_field("geography", "present", "India", "INDIA")
    fields["activity_description"] = make_field("activity_description", "present", description, "purchased_materials")
    items.append(make_item(f"Goods ordered: {description}", [make_ref("activity_description"), make_ref("material_identity")]))
    fields["material_identity"] = make_field("material_identity", "present", description, identity)
    items.append(make_item(f"Ship-to works: India; receiving entity {customer}", [make_ref("geography")]))
    add_visible_field(fields, items, "document_date", "Document date", doc_date, fields["document_date"]["normalized_value"], displayed_value=doc_date)
    if state == "ready":
        mass = rng.choice(["1250", "1.25", "980000"])
        unit = {"1250": "kg", "1.25": "tonne", "980000": "g"}[mass]
        engine.update({"quantity": mass, "unit": unit})
        add_visible_field(fields, items, "quantity", "Net delivered mass", mass, mass, unit, "kg", displayed_value=f"{mass} {unit}")
        fields["unit"]["normalized_value"] = "kg"
        fields["unit"]["normalized_unit"] = "kg"
    elif state == "incomplete":
        fields["quantity"] = make_field("quantity", "not_present", missing_reason="The order identifies the approved material but provides no delivered mass.")
        fields["unit"] = make_field("unit", "not_present", missing_reason="No mass unit or conversion basis is printed.")
        items.append(make_item("Supply against purchase order; quantity to be confirmed on receiving docket", [], "body"))
    else:
        alternate = {
            "ppc_cement": "Ordinary Portland Cement (OPC), grade 53",
            "steel_rebar": "Steel plate stock",
            "generic_steel": "Reinforcing steel bar / rebar",
        }[identity]
        for item in items:
            item["refs"] = [ref for ref in item["refs"] if ref["field_name"] != "material_identity"]
        add_ambiguous_field(fields, items, "material_identity", [("Invoice item", description, None), ("Receiving note item", alternate, None)], "The invoice and receiving note identify different material products; no signed reconciliation establishes which product was received.")
        mass = "1250"
        add_visible_field(fields, items, "quantity", "Scale mass", mass, mass, "kg", "kg", displayed_value=f"{mass} kg")
        fields["unit"]["normalized_value"] = "kg"
        fields["unit"]["normalized_unit"] = "kg"
    purchase_note = rng.choice([
        "business construction inputs",
        "company works material supply",
        "materials for the operating site",
        "business project procurement",
    ])
    add_visible_field(fields, items, "purchase_evidence",
                      rng.choice(["Purchase context", "Buyer designation", "Procurement basis", "Use of goods"]),
                      "purchased for business use", "purchased", displayed_value=purchase_note)
    if "quantity" not in fields:
        fields["quantity"] = make_field("quantity", "not_present", missing_reason="Mass is absent.")
    if "unit" not in fields:
        fields["unit"] = make_field("unit", "not_present", missing_reason="Mass unit is absent.")
    items.append(make_item(f"Commercial total INR {rng.randrange(18000, 280000)}; tax code {rng.randrange(100, 999)}", [], "noise"))
    return {"fields": fields, "items": items, "engine_fields": engine if state == "ready" else None, "supplier": supplier,
            "document_date": doc_date, "customer": customer, "domain": "materials", "material_identity": identity}, items, engine if state == "ready" else None


def build_freight(local_index: int, state: str, vehicle: tuple[str, str], rng: random.Random) -> tuple[dict, list[dict], dict]:
    fields: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    supplier, customer, doc_date = add_common_header_data("freight", local_index, rng, fields, items)
    add_visible_field(fields, items, "document_date", "Record date", doc_date,
                      fields["document_date"]["normalized_value"], displayed_value=doc_date)
    class_code, class_text = vehicle
    fields["activity_description"] = make_field("activity_description", "present", "India road freight service", "selected_transport")
    fields["geography"] = make_field("geography", "present", "India", "INDIA")
    items.append(make_item("Movement: road carriage within India", [make_ref("activity_description"), make_ref("transport_mode"), make_ref("geography")]))
    fields["transport_mode"] = make_field("transport_mode", "present", "road", "road")
    scenario = rng.choice(["upstream_purchased", "downstream_sold_product"])
    flow_text = "Inbound carriage for purchased goods" if scenario == "upstream_purchased" else "Outbound delivery of sold products"
    fields["transport_scenario"] = make_field("transport_scenario", "present", flow_text, scenario)
    items.append(make_item(f"Business flow: {flow_text}; third-party carrier", [make_ref("transport_scenario")]))
    mass = str(rng.choice(["2400", "2.4", "1850"]))
    mass_unit = {"2400": "kg", "2.4": "tonne", "1850": "kg"}[mass]
    distance = str(rng.choice(["86", "125", "74000"]))
    distance_unit = {"86": "km", "125": "km", "74000": "m"}[distance]
    engine = {"activity": "selected_transport", "shipment_mass": mass, "mass_unit": mass_unit,
              "distance": distance, "distance_unit": distance_unit, "transport_vehicle_class": class_code,
              "transport_mode": "road", "transport_scenario": scenario, "geography_code": "INDIA", "fields_confirmed": "yes"}
    if state == "ready":
        add_visible_field(fields, items, "shipment_mass", "Shipment gross mass", mass, mass, mass_unit, "tonne", displayed_value=f"{mass} {mass_unit}")
        fields["shipment_mass_unit"]["normalized_value"] = "tonne"
        fields["shipment_mass_unit"]["normalized_unit"] = "tonne"
        add_visible_field(fields, items, "distance", rng.choice(["Road distance", "Route km", "Loaded leg length"]), distance, distance, distance_unit, "km", displayed_value=f"{distance} {distance_unit}")
        fields["distance_unit"]["normalized_value"] = "km"
        fields["distance_unit"]["normalized_unit"] = "km"
        add_visible_field(fields, items, "transport_vehicle_class", "Vehicle GVW class", class_text, class_code, displayed_value=class_text)
    elif state == "incomplete":
        add_visible_field(fields, items, "shipment_mass", "Consignment mass", mass, mass, mass_unit, "tonne", displayed_value=f"{mass} {mass_unit}")
        fields["shipment_mass_unit"]["normalized_value"] = "tonne"
        fields["shipment_mass_unit"]["normalized_unit"] = "tonne"
        if local_index % 2:
            add_missing_field(fields, "distance", "The road movement record does not state a distance.")
            add_missing_field(fields, "distance_unit", "No distance unit is provided.")
            items.append(make_item("Route to be confirmed by carrier; dispatch number " + str(rng.randrange(10000, 99999)), [], "noise"))
            add_missing_field(fields, "transport_vehicle_class", "The document does not identify the vehicle GVW class.")
        else:
            add_visible_field(fields, items, "distance", "Road distance", distance, distance, distance_unit, "km", displayed_value=f"{distance} {distance_unit}")
            fields["distance_unit"]["normalized_value"] = "km"
            fields["distance_unit"]["normalized_unit"] = "km"
            add_missing_field(fields, "transport_vehicle_class", "Vehicle GVW or supported vehicle class is absent.")
    else:
        add_visible_field(fields, items, "shipment_mass", "Shipment mass", mass, mass, mass_unit, "tonne", displayed_value=f"{mass} {mass_unit}")
        fields["shipment_mass_unit"]["normalized_value"] = "tonne"
        fields["shipment_mass_unit"]["normalized_unit"] = "tonne"
        add_visible_field(fields, items, "distance", "Route distance", distance, distance, distance_unit, "km", displayed_value=f"{distance} {distance_unit}")
        fields["distance_unit"]["normalized_value"] = "km"
        fields["distance_unit"]["normalized_unit"] = "km"
        alternate_class_code, alternate = rng.choice([item for item in VEHICLE_CLASSES if item[0] != class_code])
        if alternate_class_code == class_code:
            raise ValueError("Ambiguous freight candidates must name distinct supported vehicle classes.")
        add_ambiguous_field(fields, items, "transport_vehicle_class", [("Vehicle class entry (dispatch copy)", class_text, None), ("Vehicle class entry (carrier copy)", alternate, None)], "The dispatch and carrier copies list incompatible vehicle classes, with no signed reconciliation or clear precedence.")
    for name, reason in (("shipment_mass", "Shipment mass is absent."), ("shipment_mass_unit", "Shipment mass unit is absent."), ("distance", "Transport distance is absent."), ("distance_unit", "Transport distance unit is absent."), ("transport_vehicle_class", "Vehicle class is absent or unsupported.")):
        if name not in fields:
            add_missing_field(fields, name, reason)
    items.append(make_item(f"Freight charge INR {rng.randrange(2800, 64000)}; consignment ref {rng.randrange(10000, 99999)}", [], "noise"))
    return {"fields": fields, "items": items, "engine_fields": engine if state == "ready" else None, "supplier": supplier,
            "document_date": doc_date, "customer": customer, "domain": "freight", "intended_vehicle_class_for_balance_only": class_code}, items, engine if state == "ready" else None


def make_plan(rng: random.Random) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    # Electricity, diesel and LPG each have 7 ready, 7 incomplete, and 6 ambiguous cases.
    for domain in ("electricity", "diesel", "lpg"):
        states = ["ready"] * 7 + ["incomplete"] * 7 + ["ambiguous"] * 6
        rng.shuffle(states)
        for local_index, state in enumerate(states):
            plan.append({"domain": domain, "local_index": local_index, "state": state})
    material_states = {
        "ppc_cement": ["ready"] * 4 + ["incomplete"] * 3 + ["ambiguous"] * 3,
        "steel_rebar": ["ready"] * 3 + ["incomplete"] * 4 + ["ambiguous"] * 3,
        "generic_steel": ["ready"] * 3 + ["incomplete"] * 3 + ["ambiguous"] * 4,
    }
    for identity, states in material_states.items():
        local_states = states[:]
        rng.shuffle(local_states)
        for local_index, state in enumerate(local_states):
            plan.append({"domain": "materials", "local_index": local_index + len(plan), "state": state, "material_identity": identity})
    # Freight totals: 9 ready, 9 incomplete, 12 ambiguous; supported classes are balanced across the set.
    freight_pairs: list[tuple[str, tuple[str, str]]] = []
    for class_index, vehicle in enumerate(VEHICLE_CLASSES):
        count = 5 if class_index < 2 else 4
        ready_count = 2 if class_index < 2 else 1
        incomplete_count = 2 if class_index in {2, 3} else 1
        ambiguous_count = count - ready_count - incomplete_count
        freight_pairs.extend([("ready", vehicle)] * ready_count)
        freight_pairs.extend([("incomplete", vehicle)] * incomplete_count)
        freight_pairs.extend([("ambiguous", vehicle)] * ambiguous_count)
    rng.shuffle(freight_pairs)
    for local_index, (state, vehicle) in enumerate(freight_pairs):
        plan.append({"domain": "freight", "local_index": local_index, "state": state, "vehicle": vehicle})
    # The 4 supported output formats are balanced globally and assigned independently of the labels.
    formats = (["born_digital_pdf"] * 40 + ["simulated_scanned_pdf"] * 40 + ["standalone_png"] * 20 + ["standalone_jpeg"] * 20)
    rng.shuffle(formats)
    rng.shuffle(plan)
    for i, row in enumerate(plan):
        row["pilot_index"] = i + 1
        row["format"] = formats[i]
    # Exactly 30 multi-page records: 15 per PDF format; image-only records remain single page.
    for pdf_format in ("born_digital_pdf", "simulated_scanned_pdf"):
        pdf_rows = [r for r in plan if r["format"] == pdf_format]
        rng.shuffle(pdf_rows)
        for i, row in enumerate(pdf_rows):
            row["page_count"] = 2 if i < 12 else (3 if i < 15 else 1)
    for row in plan:
        if row["format"] in {"standalone_png", "standalone_jpeg"}:
            row["page_count"] = 1
        row["phone_style_simulated"] = row["format"] == "standalone_jpeg" and row["pilot_index"] % 2 == 0
    return sorted(plan, key=lambda r: r["pilot_index"])


@dataclass(frozen=True)
class Template:
    family: str
    structure: str
    header_style: int


class PageScene:
    """A small scene graph shared by this pilot's vector and raster outputs."""

    def __init__(self, width: float, height: float, palette: tuple[str, str, str],
                 font_family: str, fields: dict[str, dict[str, Any]], page_number: int):
        self.width = width
        self.height = height
        self.palette = palette
        self.font_family = font_family
        self.fields = fields
        self.page_number = page_number
        self.elements: list[dict[str, Any]] = []
        self.visible_text: list[str] = []

    def rect(self, x: float, y: float, w: float, h: float, fill: str | None = None,
             stroke: str | None = None, stroke_width: float = 1.0, radius: float = 0.0) -> None:
        self.elements.append({"kind": "rect", "x": x, "y": y, "w": w, "h": h,
                              "fill": fill, "stroke": stroke, "stroke_width": stroke_width, "radius": radius})

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, width: float = 1.0,
             dash: list[float] | None = None) -> None:
        self.elements.append({"kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                              "color": color, "width": width, "dash": dash})

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str | None = None) -> None:
        self.elements.append({"kind": "circle", "cx": cx, "cy": cy, "r": r, "fill": fill, "stroke": stroke})

    def text(self, value: str, x: float, y: float, size: float = 10.0, color: str = "#263238",
             face: str | None = None, bold: bool = False, align: str = "left",
             max_width: float | None = None, refs: list[dict[str, Any]] | None = None,
             italic: bool = False) -> tuple[float, float, float, float]:
        face = face or self.font_family
        pdf_face = PDF_FONTS.get((face, bold), "Helvetica")
        original = value
        lines = wrap_for_width(value, pdf_face, size, max_width) if max_width else [value]
        widths = [stringWidth(line, pdf_face, size) for line in lines]
        height = max(size * 1.34 * len(lines), size * 1.15)
        widest = max(widths or [0.0])
        if align == "center":
            x -= widest / 2
        elif align == "right":
            x -= widest
        for index, line in enumerate(lines):
            self.elements.append({"kind": "text", "value": line, "x": x, "y": y + index * size * 1.34,
                                  "size": size, "color": color, "face": face, "bold": bold, "italic": italic,
                                  "align": "left"})
            self.visible_text.append(line)
        box = (max(0.0, x), max(0.0, y), min(self.width, x + widest), min(self.height, y + height))
        if refs:
            bbox = normalized_box(box, self.width, self.height)
            for ref in refs:
                field = self.fields.get(ref["field_name"])
                if field is None:
                    raise ValueError(f"Evidence reference has no field annotation: {ref['field_name']}")
                evidence = {
                    "text": original,
                    "page_number": self.page_number,
                    "bbox": dict(bbox),
                }
                if ref.get("candidate_index") is not None:
                    evidence.update({
                        "candidate_index": ref["candidate_index"],
                        "candidate_value": ref.get("candidate_value"),
                        "candidate_unit": ref.get("candidate_unit"),
                    })
                field["evidence"].append(evidence)
        return box


def wrap_for_width(text: str, pdf_face: str, size: float, max_width: float) -> list[str]:
    words = text.split()
    out: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, pdf_face, size) > max_width:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out or [""]


def normalized_box(box: tuple[float, float, float, float], width: float, height: float) -> dict[str, float]:
    x0, y0, x1, y1 = box
    x0 = min(max(x0, 0.0), width)
    y0 = min(max(y0, 0.0), height)
    x1 = min(max(x1, x0), width)
    y1 = min(max(y1, y0), height)
    return {"x": round(x0 / width, 6), "y": round(y0 / height, 6),
            "width": round((x1 - x0) / width, 6), "height": round((y1 - y0) / height, 6)}


def layout_header(page: PageScene, title: str, supplier: str, supplier_ref: dict[str, Any],
                  style: int, doc_ref: str, page_number: int, total_pages: int,
                  rng: random.Random) -> float:
    ink, pale, edge = page.palette
    w = page.width
    margin = rng.choice([28.0, 34.0, 42.0, 48.0]) if w > 350 else 18.0
    top_title = rng.choice([22.0, 27.0, 34.0]) if w > 350 else 15.0
    if style % 7 == 0:
        supplier_box = page.text(supplier, margin, 14, top_title - 9, "#F4F6F7", "sans", True,
                                  max_width=w - margin * 2, refs=[supplier_ref])
        title_box = page.text(title, margin, max(42.0, supplier_box[3] + 6), top_title,
                              "#FFFFFF", "serif", True, max_width=w - margin * 2)
        ref_box = page.text(f"Reference {doc_ref}", w - margin, title_box[3] + 5, 8,
                            "#E7ECEF", "mono", align="right")
        header_bottom = ref_box[3] + 11
        page.elements.insert(1, {"kind": "rect", "x": 0, "y": 0, "w": w,
                                 "h": header_bottom, "fill": ink, "stroke": None,
                                 "stroke_width": 1.0, "radius": 0.0})
        y = header_bottom + 12
    elif style % 7 == 1:
        title_box = page.text(title, w / 2, 24, top_title + 1, ink, "sans", True, "center", max_width=w - 2 * margin)
        supplier_box = page.text(supplier, w / 2, title_box[3] + 6, 10, "#303A40", "serif", False,
                                 "center", max_width=w - 2 * margin, refs=[supplier_ref])
        rule_y = supplier_box[3] + 9
        page.line(margin, rule_y, w - margin, rule_y, ink, 2.0)
        doc_box = page.text(f"Document {doc_ref}", margin, rule_y + 9, 8, "#626D72", "mono")
        y = doc_box[3] + 18
    elif style % 7 == 2:
        page.rect(margin, 20, 78, 67, pale, ink, 1.5)
        page.circle(margin + 25, 44, 12, ink)
        page.circle(margin + 25, 44, 5, "#FFFFFF")
        supplier_box = page.text(supplier, margin + 88, 22, 10, ink, "humanist", True,
                                 max_width=w - margin - (margin + 88), refs=[supplier_ref])
        title_box = page.text(title, margin + 88, supplier_box[3] + 6, top_title - 6,
                              "#20282D", "serif", True, max_width=w - margin - (margin + 88))
        archive_box = page.text(f"Archive ref. {doc_ref}", margin + 88, title_box[3] + 6, 8, "#667078", "mono")
        y = max(108.0, archive_box[3] + 17)
    elif style % 7 == 3:
        title_box = page.text(title.upper(), w - margin, 19, top_title - 5, ink, "mono", True,
                              "right", max_width=w - 2 * margin)
        issuer_box = page.text("Issued by", margin, title_box[3] + 4, 8, "#6D767B", "sans")
        supplier_box = page.text(supplier, margin, issuer_box[3] + 3, 11, "#263238", "serif", True,
                                 max_width=w * 0.55, refs=[supplier_ref])
        ref_box = page.text(f"Ref {doc_ref}  |  Sheet {page_number}/{total_pages}", w - margin,
                            supplier_box[3] + 4, 8, "#5C666C", "humanist", align="right")
        rule_y = ref_box[3] + 7
        page.line(margin, rule_y, w - margin, rule_y, edge, 5.0)
        y = rule_y + 18
    elif style % 7 == 4:
        page.rect(0, 0, 14, page.height, ink)
        supplier_box = page.text(supplier, 40, 19, 10, ink, "sans", True,
                                 max_width=w - 70, refs=[supplier_ref])
        title_box = page.text(title, 40, supplier_box[3] + 6, top_title - 3,
                              "#242B30", "serif", False, max_width=w - 70)
        doc_box = page.text(f"{doc_ref} • Page {page_number} of {total_pages}",
                            40, title_box[3] + 6, 8, "#667078", "mono")
        y = max(112.0, doc_box[3] + 18)
    elif style % 7 == 5:
        masthead_box = page.text("TRANSIT / ACCOUNT RECORD", w / 2, 18, 7.5, ink, "mono", True, "center")
        title_box = page.text(title, w / 2, max(36.0, masthead_box[3] + 6), top_title - 4,
                              "#20282D", "humanist", True, "center", max_width=w - 28)
        supplier_box = page.text(supplier, w / 2, title_box[3] + 6, 8.5, "#4E5960", "sans", False,
                                 "center", max_width=w - 26, refs=[supplier_ref])
        rule_y = supplier_box[3] + 8
        page.line(18, rule_y, w - 18, rule_y, ink, 0.7, [3.0, 2.0])
        y = max(101.0, rule_y + 17)
    else:
        ref_box = page.text(f"{doc_ref}  /  {page_number:02d}", w - margin - 10, 25, 8,
                            ink, "mono", align="right")
        supplier_box = page.text(supplier, margin + 14, 30, 9.5, ink, "sans", True,
                                 max_width=max(70, (w - 2 * margin - 28) * 0.62), refs=[supplier_ref])
        title_box = page.text(title, margin + 14, max(53.0, supplier_box[3] + 6), top_title - 6,
                              "#29333A", "serif", True, max_width=w - 2 * margin - 28)
        panel_bottom = max(ref_box[3] + 10, title_box[3] + 10)
        page.elements.insert(1, {"kind": "rect", "x": margin, "y": 18, "w": w - margin * 2,
                                 "h": panel_bottom - 18, "fill": pale, "stroke": edge,
                                 "stroke_width": 1.0, "radius": 0.0})
        y = max(108.0, panel_bottom + 18)
    page.text(rng.choice(["Business copy", "Service record", "Dispatch office", "Customer account copy"]),
              w - margin, y - 5, 7.5, "#778188", "humanist", align="right")
    return y + rng.choice([6.0, 12.0, 18.0])


def render_body(page: PageScene, items: list[dict[str, Any]], structure: str,
                rng: random.Random, start_y: float) -> float:
    w, h = page.width, page.height
    ink, pale, edge = page.palette
    margin = 28.0 if w < 360 else rng.choice([32.0, 39.0, 47.0, 54.0])
    usable = w - 2 * margin
    base_size = 8.0 if w < 360 else rng.choice([8.5, 9.0, 9.5, 10.0, 10.5])
    gap = 17.0 if w < 360 else 22.0
    y = start_y

    def measured_height(text: str, face: str, bold: bool, size: float, max_width: float) -> float:
        pdf_face = PDF_FONTS[(face, bold)]
        line_count = len(wrap_for_width(text, pdf_face, size, max_width))
        return max(size * 1.34 * line_count, size * 1.15)

    if structure in {"table", "ledger", "annex"}:
        heading = {
            "table": rng.choice(["Transaction detail", "Line register", "Supply schedule"]),
            "ledger": rng.choice(["Account activity", "Service entries", "Movement ledger"]),
            "annex": rng.choice(["Supporting schedule", "Continuation details", "Document particulars"]),
        }[structure]
        page.text(heading, margin, y, 11.5, ink, "serif", True, max_width=usable)
        y += 25
        col1 = usable * rng.choice([0.47, 0.54, 0.62])
        page.rect(margin, y, usable, 21, ink)
        page.text(rng.choice(["Description", "Entry", "Reference detail"]), margin + 7, y + 6, 7.4, "#FFFFFF", "sans", True)
        page.text(rng.choice(["Value / note", "Recorded", "Particulars"]), margin + col1, y + 6, 7.4, "#FFFFFF", "sans", True)
        y += 22
        for idx, item in enumerate(items):
            face = rng.choice(["sans", "humanist", "serif"])
            minimum_row = rng.choice([26.0, 29.0, 34.0]) if w < 360 else rng.choice([27.0, 31.0, 36.0])
            text_h = measured_height(item["text"], face, False, base_size, usable - 14)
            row_h = max(minimum_row, text_h + 13)
            if idx % 2 == 0:
                page.rect(margin, y, usable, row_h, pale)
            page.line(margin, y + row_h, w - margin, y + row_h, edge, 0.6)
            page.text(item["text"], margin + 7, y + 6, base_size, "#27343A", face,
                      max_width=usable - 14, refs=item["refs"])
            y += row_h
        page.text(rng.choice(["Carry forward →", "See attached advice", "Office ledger copy"]),
                  w - margin, min(y + 8, h - 45), 7.5, "#737D83", "mono", align="right")
        return y + 18
    if structure == "floating_cards":
        page.text(rng.choice(["Record fields", "Account details", "Receiving information"]), margin, y, 11.2, ink, "sans", True)
        y += 22
        cols = 2 if w > 430 else 1
        card_w = (usable - 12) / cols
        rows = [items[index:index + cols] for index in range(0, len(items), cols)]
        for row_index, row_items in enumerate(rows):
            prepared = []
            row_height = 0.0
            for col, item in enumerate(row_items):
                face = rng.choice(["sans", "serif", "humanist"])
                base_card_height = rng.choice([36.0, 41.0, 47.0])
                text_height = measured_height(item["text"], face, False, base_size, card_w - 14)
                card_height = max(base_card_height, text_height + 17)
                jitter_y = rng.uniform(-1.5, 2.5)
                x = margin + col * (card_w + 12) + rng.uniform(-2, 2)
                x = min(max(x, margin), w - margin - card_w)
                prepared.append((item, face, x, jitter_y, card_height))
                row_height = max(row_height, jitter_y + card_height)
            row_top = y
            for col, (item, face, x, jitter_y, card_height) in enumerate(prepared):
                iy = row_top + jitter_y
                idx = row_index * cols + col
                page.rect(x, iy, card_w, card_height, pale if idx % 3 else "#FFFFFF", edge, 0.8, radius=3)
                page.text(item["text"], x + 7, iy + 8, base_size, "#29343A", face,
                          max_width=card_w - 14, refs=item["refs"])
            y = row_top + row_height + rng.choice([9.0, 12.0, 15.0])
        return y
    if structure in {"prose", "letter"}:
        page.text(rng.choice(["Service correspondence", "Dispatch note", "Record narrative"]), margin, y, 12.0, ink, "serif", True)
        y += 27
        salutation = rng.choice(["For the attention of the receiving office,", "This record accompanies the transaction described below.", "The following particulars were entered at the point of service."])
        page.text(salutation, margin, y, base_size, "#465158", "serif", max_width=usable - 12)
        y += 28
        chunk = max(1, math.ceil(len(items) / max(1, min(4, len(items)))))
        for start in range(0, len(items), chunk):
            group = items[start:start + chunk]
            joined = "   ".join(item["text"] for item in group)
            refs = [ref for item in group for ref in item["refs"]]
            box = page.text(joined, margin + rng.uniform(0, 12), y, base_size + rng.choice([-0.4, 0, 0.4]),
                            "#2C373D", rng.choice(["serif", "sans", "humanist"]), max_width=usable - 12,
                            refs=refs)
            y = box[3] + rng.choice([11.0, 18.0, 24.0])
        page.text(rng.choice(["Filed by operations", "Retain with the account record", "Received subject to the listed terms"]),
                  margin, min(y, h - 60), 8.2, "#59646A", "serif", italic=True, max_width=usable)
        return y + 18
    if structure in {"thermal", "receipt"}:
        col_w = min(usable, rng.choice([220.0, 245.0, 270.0]))
        x = (w - col_w) / 2
        page.text(rng.choice(["TRANSACTION COPY", "DELIVERY RECORD", "CUSTOMER RECEIPT"]), w / 2, y, 7.5, ink, "mono", True, "center")
        y += 18
        page.line(x, y, x + col_w, y, ink, 0.7, [2, 2])
        y += 10
        for idx, item in enumerate(items):
            text = item["text"]
            if idx % 4 == 3:
                box = page.text(text, x + col_w, y, base_size, "#263238", "mono", align="right", max_width=col_w, refs=item["refs"])
            else:
                box = page.text(text, x + rng.choice([0, 4, 9]), y, base_size, "#263238", "mono", max_width=col_w - 8, refs=item["refs"])
            y = box[3] + rng.choice([8.0, 11.0, 15.0])
            if idx % 2:
                page.line(x, y - 4, x + col_w, y - 4, edge, 0.5, [1, 2])
        page.text("Keep this copy with the delivery papers", w / 2, min(y + 12, h - 42), 7.4, "#59646A", "mono", align="center")
        return y + 26
    if structure == "invoice_grid":
        page.text("Goods / service lines", margin, y, 11.0, ink, "sans", True)
        y += 23
        widths = [usable * 0.12, usable * 0.45, usable * 0.21, usable * 0.22]
        headers = ["Line", "Description", "Qty / unit", "Line value"]
        page.rect(margin, y, usable, 22, ink)
        x = margin
        for cell_w, title in zip(widths, headers):
            page.text(title, x + 4, y + 6, 7.0, "#FFFFFF", "sans", True, max_width=cell_w - 8)
            x += cell_w
        y += 23
        for idx, item in enumerate(items):
            text_h = measured_height(item["text"], "sans", False, base_size, widths[1] - 10)
            row_h = max(rng.choice([31.0, 35.0, 40.0]), text_h + 14)
            if idx % 2 == 0:
                page.rect(margin, y, usable, row_h, pale)
            page.line(margin, y + row_h, w - margin, y + row_h, edge, 0.55)
            page.text(f"{idx + 1:02d}", margin + 4, y + 8, 7.5, "#4B565D", "mono")
            page.text(item["text"], margin + widths[0] + 5, y + 7, base_size, "#273238", "sans", max_width=widths[1] - 10, refs=item["refs"])
            x3 = margin + widths[0] + widths[1]
            page.text(rng.choice(["1 lot", "1 line", "as listed"]), x3 + 4, y + 8, 7.2, "#59646A", "mono", max_width=widths[2] - 8)
            x4 = x3 + widths[2]
            page.text(f"INR {rng.randrange(900, 85000)}", x4 + 4, y + 8, 7.1, "#59646A", "sans", max_width=widths[3] - 8)
            y += row_h
        page.text(f"Subtotal INR {rng.randrange(4000, 120000)}   Tax INR {rng.randrange(150, 12000)}",
                  w - margin, min(y + 10, h - 40), 8.0, ink, "sans", True, "right")
        return y + 26
    # A document dossier: side index, offset notes, and a narrow evidence column.
    rail = min(118.0, usable * 0.31)
    page.rect(margin, y, rail, min(h - y - 48, 310), pale, edge, 0.8)
    page.text(rng.choice(["INDEX", "REGISTER", "ROUTE"]), margin + 9, y + 10, 8.0, ink, "mono", True)
    for n in range(3):
        page.line(margin + 9, y + 35 + n * 37, margin + rail - 9, y + 35 + n * 37, edge, 0.7)
        page.circle(margin + 16, y + 29 + n * 37, 3.2, ink)
        page.text(rng.choice(["Office", "Copy", "Entry"]), margin + 26, y + 24 + n * 37, 7.5, "#49555B", "sans")
    right_x = margin + rail + 18
    right_w = usable - rail - 18
    for idx, item in enumerate(items):
        iy = y
        page.text(f"{rng.choice(['A', 'B', 'C', 'D'])}{idx + 1}", right_x, iy, 7.0, ink, "mono", True)
        face = rng.choice(["sans", "serif", "humanist"])
        box = page.text(item["text"], right_x + 22, iy - 1, base_size, "#29343A", face,
                        max_width=max(30, right_w - 25), refs=item["refs"])
        y = box[3] + rng.choice([8.0, 12.0, 16.0])
    return y


def render_scene_pdf(path: Path, pages: list[PageScene]) -> None:
    pdf = canvas.Canvas(str(path), pageCompression=1, invariant=1)
    pdf.setTitle("Business record")
    pdf.setAuthor("GreenLedger synthetic pilot generator")
    for page in pages:
        pdf.setPageSize((page.width, page.height))
        for item in page.elements:
            kind = item["kind"]
            if kind == "rect":
                if item["fill"]:
                    pdf.setFillColor(HexColor(item["fill"]))
                if item["stroke"]:
                    pdf.setStrokeColor(HexColor(item["stroke"]))
                    pdf.setLineWidth(item["stroke_width"])
                else:
                    pdf.setStrokeColor(HexColor(item["fill"] or "#FFFFFF"))
                x, y = item["x"], page.height - item["y"] - item["h"]
                pdf.rect(x, y, item["w"], item["h"], fill=1 if item["fill"] else 0, stroke=1 if item["stroke"] else 0)
            elif kind == "line":
                pdf.setStrokeColor(HexColor(item["color"]))
                pdf.setLineWidth(item["width"])
                pdf.setDash(item["dash"] or [])
                pdf.line(item["x1"], page.height - item["y1"], item["x2"], page.height - item["y2"])
                pdf.setDash([])
            elif kind == "circle":
                pdf.setFillColor(HexColor(item["fill"]))
                if item["stroke"]:
                    pdf.setStrokeColor(HexColor(item["stroke"]))
                pdf.circle(item["cx"], page.height - item["cy"], item["r"], fill=1, stroke=1 if item["stroke"] else 0)
            elif kind == "text":
                pdf.setFillColor(HexColor(item["color"]))
                pdf.setFont(PDF_FONTS[(item["face"], item["bold"])], item["size"])
                baseline = page.height - item["y"] - item["size"]
                pdf.drawString(item["x"], baseline, item["value"])
        pdf.showPage()
    pdf.save()


_PIL_FONTS: dict[tuple[str, bool, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def pil_font(face: str, bold: bool, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (face, bold, size)
    if key in _PIL_FONTS:
        return _PIL_FONTS[key]
    path = FONT_PATHS[(face, bold)]
    try:
        loaded = ImageFont.truetype(str(path), size=size) if path.exists() else ImageFont.load_default()
    except OSError:
        loaded = ImageFont.load_default()
    _PIL_FONTS[key] = loaded
    return loaded


def render_scene_image(page: PageScene) -> Image.Image:
    scale = PIXELS_PER_POINT
    image = Image.new("RGB", (round(page.width * scale), round(page.height * scale)), "white")
    draw = ImageDraw.Draw(image)
    for item in page.elements:
        kind = item["kind"]
        if kind == "rect":
            xy = (round(item["x"] * scale), round(item["y"] * scale),
                  round((item["x"] + item["w"]) * scale), round((item["y"] + item["h"]) * scale))
            fill = item["fill"]
            outline = item["stroke"]
            if item["radius"]:
                draw.rounded_rectangle(xy, radius=round(item["radius"] * scale), fill=fill, outline=outline,
                                       width=max(1, round(item["stroke_width"] * scale)))
            else:
                draw.rectangle(xy, fill=fill, outline=outline,
                               width=max(1, round(item["stroke_width"] * scale)) if outline else 1)
        elif kind == "line":
            draw.line((round(item["x1"] * scale), round(item["y1"] * scale),
                       round(item["x2"] * scale), round(item["y2"] * scale)), fill=item["color"],
                      width=max(1, round(item["width"] * scale)))
        elif kind == "circle":
            r = item["r"] * scale
            xy = (round(item["cx"] * scale - r), round(item["cy"] * scale - r),
                  round(item["cx"] * scale + r), round(item["cy"] * scale + r))
            draw.ellipse(xy, fill=item["fill"], outline=item["stroke"])
        elif kind == "text":
            size = max(6, round(item["size"] * scale))
            font = pil_font(item["face"], item["bold"], size)
            draw.text((round(item["x"] * scale), round(item["y"] * scale)), item["value"],
                      fill=item["color"], font=font, anchor="lt")
    return image


def rotate_bbox(bbox: dict[str, float], old_size: tuple[int, int], new_size: tuple[int, int],
                angle_degrees: float, offset: tuple[int, int] = (0, 0),
                output_size: tuple[int, int] | None = None) -> dict[str, float]:
    old_w, old_h = old_size
    new_w, new_h = output_size or new_size
    src_cx, src_cy = old_w / 2, old_h / 2
    dst_cx, dst_cy = new_size[0] / 2 + offset[0], new_size[1] / 2 + offset[1]
    theta = math.radians(angle_degrees)
    c, s = math.cos(theta), math.sin(theta)
    x0 = bbox["x"] * old_w
    y0 = bbox["y"] * old_h
    x1 = (bbox["x"] + bbox["width"]) * old_w
    y1 = (bbox["y"] + bbox["height"]) * old_h
    points = []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        dx, dy = x - src_cx, y - src_cy
        points.append((dst_cx + c * dx + s * dy, dst_cy - s * dx + c * dy))
    left = min(p[0] for p in points) / new_w
    top = min(p[1] for p in points) / new_h
    right = max(p[0] for p in points) / new_w
    bottom = max(p[1] for p in points) / new_h
    return {"x": round(max(0, left), 6), "y": round(max(0, top), 6),
            "width": round(max(0, min(1, right) - max(0, left)), 6),
            "height": round(max(0, min(1, bottom) - max(0, top)), 6)}


def apply_raster_effect(image: Image.Image, effect: str, rng: random.Random,
                        phone_style: bool = False) -> tuple[Image.Image, dict[str, Any]]:
    original_size = image.size
    angle = 0.0
    if effect == "mild_skew" or phone_style:
        angle = rng.choice([-1.8, -1.1, 0.8, 1.4])
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="#F7F7F4")
    rotated_size = image.size
    offset = (0, 0)
    if phone_style:
        margin = 44
        background = Image.new("RGB", (image.width + margin * 2, image.height + margin * 2), "#B9B8B2")
        shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rectangle((margin + 8, margin + 10, margin + image.width + 8, margin + image.height + 10), fill=(20, 23, 25, 75))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        background = Image.alpha_composite(background.convert("RGBA"), shadow).convert("RGB")
        offset = (margin, margin)
        background.paste(image, offset)
        image = background
    elif angle:
        offset = (0, 0)
    if effect == "soft_low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.74)
    elif effect == "faint_raster":
        image = ImageEnhance.Brightness(image).enhance(1.04)
        image = ImageEnhance.Contrast(image).enhance(0.78)
    elif effect == "light_blur":
        image = image.filter(ImageFilter.GaussianBlur(radius=0.85))
    elif effect == "jpeg_artifacts" or phone_style:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=58, optimize=True)
        buffer.seek(0)
        image = Image.open(buffer).convert("RGB")
    if phone_style:
        image = ImageEnhance.Brightness(image).enhance(0.98)
    transform = {
        "source_size": original_size,
        "rotated_size": rotated_size,
        "offset": offset,
        "output_size": image.size,
        "angle_degrees": angle,
        "phone_style_simulated": phone_style,
    }
    return image, transform


def update_evidence_geometry(fields: dict[str, dict[str, Any]], page_number: int,
                             transform: dict[str, Any] | None) -> None:
    if not transform:
        return
    for field in fields.values():
        for evidence in field.get("evidence", []):
            if evidence["page_number"] == page_number:
                evidence["bbox"] = rotate_bbox(
                    evidence["bbox"], transform["source_size"], transform["rotated_size"],
                    transform["angle_degrees"], transform["offset"], transform["output_size"],
                )


def make_visible_texts(domain: str, fields: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> list[str]:
    texts = [str(f.get("raw_value")) for f in fields.values() if f.get("raw_value") is not None]
    texts.extend(item["text"] for item in items)
    return texts


def choose_page_size(structure: str, rng: random.Random) -> tuple[str, tuple[float, float]]:
    if structure == "thermal" and rng.random() < 0.65:
        key = "narrow_receipt"
    elif structure in {"table", "ledger", "annex", "invoice_grid"} and rng.random() < 0.34:
        key = "A4_landscape"
    else:
        key = rng.choices(["A4_portrait", "letter_portrait", "legal_portrait", "A4_landscape"], [5, 3, 1, 2])[0]
    return key, PAGE_SIZES[key]


def split_page_items(items: list[dict[str, Any]], page_count: int, domain: str) -> list[list[dict[str, Any]]]:
    if page_count <= 1:
        return [items]
    page_keys = {
        "electricity": {"billing_period", "geography", "electricity_use"},
        "diesel": {"source_type", "operational_control", "vehicle_reference"},
        "lpg": {"net_lpg_mass", "commercial_institutional", "operational_control"},
        "materials": {"material_identity", "quantity", "unit", "purchase_evidence"},
        "freight": {"shipment_mass", "distance", "transport_vehicle_class", "transport_scenario"},
    }[domain]
    continuation = []
    primary = []
    for item in items:
        ref_names = {ref["field_name"] for ref in item["refs"]}
        (continuation if ref_names & page_keys else primary).append(item)
    if len(continuation) < 2 and primary:
        move_count = min(len(primary), max(2 - len(continuation), len(primary) // 3))
        moved = primary[-move_count:]
        primary = primary[:-move_count]
        continuation.extend(moved)
    pages = [[] for _ in range(page_count)]
    for idx, item in enumerate(primary):
        pages[idx % min(2, page_count)].append(item)
    continuation_page = 1 if page_count > 1 else 0
    for idx, item in enumerate(continuation):
        pages[continuation_page + idx % (page_count - continuation_page)].append(item)
    if page_count > 2 and not pages[2]:
        pages[2].extend(pages[1][-2:])
        del pages[1][-2:]
    for idx in range(page_count):
        if not pages[idx] and pages[0]:
            pages[idx].append(pages[0].pop())
    return pages


def create_scenes(doc_id: str, domain: str, title: str, supplier: str, fields: dict[str, dict[str, Any]],
                  items: list[dict[str, Any]], template: Template, page_count: int,
                  rng: random.Random) -> tuple[list[PageScene], list[str], list[str], str, str]:
    palette = rng.choice(PALETTES)
    font_family = rng.choice(["sans", "serif", "mono", "humanist"])
    size_name, size = choose_page_size(template.structure, rng)
    title_text = {
        "electricity": rng.choice(["Energy service statement", "Grid supply account", "Meter use record", "Electricity charge note"]),
        "diesel": rng.choice(["Fuel transaction", "Road fleet issue record", "Fuel dispatch docket", "Vehicle supply account"]),
        "lpg": rng.choice(["Gas delivery record", "LPG account note", "Cylinder supply docket", "Commercial gas statement"]),
        "materials": rng.choice(["Goods receipt", "Procurement record", "Material dispatch note", "Purchase schedule"]),
        "freight": rng.choice(["Carriage record", "Consignment particulars", "Road movement note", "Carrier account"]),
    }[domain]
    doc_ref = f"{rng.choice(['AC', 'MV', 'PX', 'RD', 'CN', 'WK'])}-{rng.randrange(100000, 999999)}"
    per_page = split_page_items(items, page_count, domain)
    scenes: list[PageScene] = []
    visible_text: list[str] = []
    visual_orders: list[list[str]] = []
    for page_idx in range(page_count):
        page = PageScene(size[0], size[1], palette, font_family, fields, page_idx + 1)
        background = rng.choice(["#FFFFFF", "#FCFBF7", "#F8F8F5", "#FBFCFE"])
        page.rect(0, 0, page.width, page.height, background)
        supplier_ref = make_ref("supplier_name")
        y = layout_header(page, title_text, supplier, supplier_ref, template.header_style,
                          doc_ref, page_idx + 1, page_count, rng)
        if page_idx > 0:
            page.text(rng.choice(["Continued particulars", "Supporting page", "Schedule continuation"]),
                      rng.choice([30.0, 40.0, 52.0]), y, 9.0, palette[0], "serif", True)
            y += 22
        current_items = per_page[page_idx]
        rng.shuffle(current_items)
        visual_orders.append([ref["field_name"] for item in current_items for ref in item["refs"]])
        render_body(page, current_items, template.structure, rng, y)
        footer_y = page.height - rng.choice([35, 43, 52])
        page.line(26, footer_y, page.width - 26, footer_y, palette[2], 0.8)
        footer = rng.choice([
            "Retain with the account papers", "Office copy • records desk", "Acknowledgement copy",
            "Issued subject to listed terms", "Delivery office reference", "Customer service record",
        ])
        page.text(footer, 31, footer_y + 8, 7.2, "#626D72", rng.choice(["sans", "serif", "mono"]))
        page.text(f"{doc_ref}   /   {page_idx + 1}-{page_count}", page.width - 31, footer_y + 8,
                  7.0, "#737D83", "mono", align="right")
        scenes.append(page)
        visible_text.extend(page.visible_text)
    logo_present = template.header_style % 7 in {2}
    return scenes, visible_text, [key for group in visual_orders for key in group], size_name, font_family


def quality_effect_for(fmt: str, rng: random.Random) -> str:
    if fmt == "born_digital_pdf":
        return "vector_clean"
    return rng.choices(
        ["clean_raster", "soft_low_contrast", "faint_raster", "light_blur", "jpeg_artifacts", "mild_skew"],
        [28, 16, 14, 12, 17, 13],
    )[0]


def output_extension(fmt: str) -> str:
    return {"born_digital_pdf": ".pdf", "simulated_scanned_pdf": ".pdf",
            "standalone_png": ".png", "standalone_jpeg": ".jpg"}[fmt]


def raster_pages(scenes: list[PageScene], effect: str, rng: random.Random,
                 phone_style: bool) -> tuple[list[Image.Image], list[dict[str, Any]]]:
    images: list[Image.Image] = []
    transforms: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        image = render_scene_image(scene)
        current_effect = effect if index == 0 else ("light_blur" if effect == "mild_skew" else effect)
        image, transform = apply_raster_effect(image, current_effect, rng, phone_style if index == 0 else False)
        images.append(image)
        transforms.append(transform)
    return images, transforms


def write_scanned_pdf(path: Path, images: list[Image.Image], scenes: list[PageScene]) -> None:
    pdf = canvas.Canvas(str(path), pageCompression=1, invariant=1)
    pdf.setTitle("Business record")
    pdf.setAuthor("GreenLedger synthetic pilot generator")
    for image, scene in zip(images, scenes):
        pdf.setPageSize((scene.width, scene.height))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        pdf.drawImage(ImageReader(buffer), 0, 0, width=scene.width, height=scene.height, mask="auto")
        pdf.showPage()
    pdf.save()


def map_visible_to_fields(row: dict[str, Any], result: dict[str, Any]) -> None:
    fields = row["fields"]
    if row["domain"] == "freight":
        data = result["transport_data"]
        mapping = {
            "shipment_mass": (str(data["shipment_mass_tonnes"]), "tonne"),
            "shipment_mass_unit": ("tonne", "tonne"),
            "distance": (str(data["distance_km"]), "km"),
            "distance_unit": ("km", "km"),
        }
    else:
        mapping = {
            "quantity": (str(result["normalized_quantity"]), result["canonical_unit"]),
            "unit": (result["canonical_unit"], result["canonical_unit"]),
        }
        if row["domain"] == "lpg":
            mapping["net_lpg_mass"] = (str(result["normalized_quantity"]), "kg")
    for name, (normalized, unit) in mapping.items():
        if name in fields and fields[name]["presence_status"] == "present":
            fields[name]["normalized_value"] = normalized
            fields[name]["normalized_unit"] = unit


def normalize_visible_field_values(domain: str, fields: dict[str, dict[str, Any]]) -> None:
    activity_id = {"electricity": "purchased_electricity", "diesel": "diesel_fuel", "lpg": "lpg",
                   "materials": "purchased_materials", "freight": "selected_transport"}[domain]
    activity = normalize_activity(activity_id)
    if domain != "freight":
        quantity = fields.get("quantity", {})
        if quantity.get("presence_status") != "present" or quantity.get("raw_unit") is None:
            return
        try:
            amount = parse_quantity(str(quantity.get("raw_value")))
            unit = normalize_unit(activity, quantity["raw_unit"])
            normalized, canonical, _trace = normalize_quantity(activity, amount, unit)
        except Exception:
            quantity["normalized_value"] = None
            quantity["normalized_unit"] = None
            unit_field = fields.get("unit")
            if unit_field and unit_field.get("presence_status") == "present":
                unit_field["normalized_value"] = None
                unit_field["normalized_unit"] = None
            return
        quantity["normalized_value"] = str(normalized) if normalized is not None else None
        quantity["normalized_unit"] = canonical if normalized is not None else None
        unit_field = fields.get("unit")
        if unit_field and unit_field.get("presence_status") == "present":
            unit_field["normalized_value"] = canonical if normalized is not None else None
            unit_field["normalized_unit"] = canonical if normalized is not None else None
        if "net_lpg_mass" in fields and fields["net_lpg_mass"]["presence_status"] == "present":
            fields["net_lpg_mass"]["normalized_value"] = str(normalized) if normalized is not None else None
            fields["net_lpg_mass"]["normalized_unit"] = canonical if normalized is not None else None
        return
    conversions = {
        "shipment_mass": ({"kg": (Decimal("0.001"), "tonne"), "tonne": (Decimal("1"), "tonne")}, "shipment_mass_unit"),
        "distance": ({"m": (Decimal("0.001"), "km"), "km": (Decimal("1"), "km")}, "distance_unit"),
    }
    for name, (rules, unit_name) in conversions.items():
        field = fields.get(name, {})
        if field.get("presence_status") != "present" or not field.get("raw_unit"):
            continue
        try:
            raw_amount = parse_quantity(str(field["raw_value"]))
            raw_unit = normalize_unit(activity, field["raw_unit"])
            multiplier, canonical = rules[raw_unit]
            normalized = raw_amount * multiplier
        except Exception:
            field["normalized_value"] = None
            field["normalized_unit"] = None
            continue
        field["normalized_value"] = str(normalized)
        field["normalized_unit"] = canonical
        unit_field = fields.get(unit_name)
        if unit_field and unit_field.get("presence_status") == "present":
            unit_field["normalized_value"] = canonical
            unit_field["normalized_unit"] = canonical


def expected_result(row: dict[str, Any], engine_fields: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = evaluate_submission(engine_fields)
    if result["co2_kg"] is not None:
        gas_basis = "CO2"
        result_value = str(result["co2_kg"])
        result_unit = "kgCO2"
        factor = result["co2_factor"]
    elif result["co2e"] is not None:
        gas_basis = "CO2e"
        result_value = str(result["co2e"])
        result_unit = "kgCO2e"
        factor = result["factor"]
    else:
        raise ValueError(f"Ready case did not calculate: {row['document_id']} {result['review_reasons']}")
    map_visible_to_fields(row, result)
    return result, {
        "status": "DETERMINISTIC_RESULT_AVAILABLE_AFTER_HUMAN_CONFIRMATION",
        "gas_basis": gas_basis,
        "value": result_value,
        "unit": result_unit,
        "factor_id": factor["factor_id"],
        "factor_value": factor["factor_value"],
        "factor_unit": factor["factor_unit"],
        "source": factor["source"],
        "source_version": factor["source_version"],
        "source_url": factor["source_url"],
        "source_sha256": factor["source_sha256"],
        "calculation_trace": result["co2_calculation_trace"] if gas_basis == "CO2" else result["calculation_trace"],
        "accounting_trace": make_json_trace(result, document_name=row["document_id"]),
    }


def build_one_document(plan_row: dict[str, Any], domain_sequence: int, domain_sequence_counts: Counter,
                       rng: random.Random, base_dir: Path,
                       contact_cache: dict[str, Image.Image]) -> tuple[dict[str, Any], dict[str, Any], list[str], int]:
    domain = plan_row["domain"]
    state = plan_row["state"]
    local_index = plan_row["local_index"]
    if domain == "electricity":
        spec, items, engine_fields = build_electricity(local_index, state, rng)
    elif domain == "diesel":
        spec, items, engine_fields = build_diesel(local_index, state, rng)
    elif domain == "lpg":
        spec, items, engine_fields = build_lpg(local_index, state, rng)
    elif domain == "materials":
        spec, items, engine_fields = build_material(local_index, state, plan_row["material_identity"], rng)
    else:
        spec, items, engine_fields = build_freight(local_index, state, plan_row["vehicle"], rng)
    normalize_visible_field_values(domain, spec["fields"])

    domain_sequence_counts[domain] += 1
    domain_number = domain_sequence_counts[domain]
    code = DOMAIN_CODES[domain]
    doc_id = f"GLP-{code}-{domain_number:03d}"
    layout_index = (domain_number - 1) % len(LAYOUTS[domain])
    template_name, structure = LAYOUTS[domain][layout_index]
    template = Template(template_name, structure, (layout_index + domain_number) % 7)
    page_count = plan_row["page_count"]
    rng.shuffle(items)
    scenes, visible_text, visual_order, page_size_name, font_family = create_scenes(
        doc_id, domain, template_name.replace("_", " ").title(), spec["supplier"],
        spec["fields"], items, template, page_count, rng,
    )
    effect = quality_effect_for(plan_row["format"], rng)
    phone_simulated = bool(plan_row["phone_style_simulated"])
    images: list[Image.Image] = []
    transforms: list[dict[str, Any]] = []
    if plan_row["format"] == "simulated_scanned_pdf":
        images, transforms = raster_pages(scenes, rng.choice(["clean_raster", effect]), rng, False)
    elif plan_row["format"] in {"standalone_png", "standalone_jpeg"}:
        images, transforms = raster_pages(scenes, effect, rng, phone_simulated)

    for page_number, transform in enumerate(transforms, 1):
        update_evidence_geometry(spec["fields"], page_number, transform)

    extension = output_extension(plan_row["format"])
    relative_path = Path("documents") / domain / f"{doc_id}{extension}"
    output_path = base_dir / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if plan_row["format"] == "born_digital_pdf":
        render_scene_pdf(output_path, scenes)
    elif plan_row["format"] == "simulated_scanned_pdf":
        write_scanned_pdf(output_path, images, scenes)
    else:
        img = images[0]
        img.save(output_path, format="PNG" if extension == ".png" else "JPEG", quality=88, optimize=True)

    if plan_row["format"] == "born_digital_pdf":
        contact_image = render_scene_image(scenes[0])
    else:
        contact_image = images[0]
    if plan_row["pilot_index"] in CONTACT_INDICES:
        contact_cache[doc_id] = contact_image.copy()
    visual_hash = average_hash(contact_image)

    if any(term in " ".join(visible_text).casefold() for term in FORBIDDEN_VISIBLE_TERMS):
        raise ValueError(f"A document appears to expose a ground-truth or accounting label: {doc_id}")

    if state == "ready":
        engine_result, expected = expected_result({"document_id": doc_id, "domain": domain,
                                                   "fields": spec["fields"]}, engine_fields)
        readiness = "READY_AFTER_HUMAN_CONFIRMATION"
        missing_reasons: list[str] = []
        ambiguity_reasons: list[str] = []
    elif state == "incomplete":
        engine_result = None
        readiness = "BLOCKED_MISSING_EVIDENCE"
        expected = {"status": "NO_RESULT_MISSING_REQUIRED_EVIDENCE", "unit": None, "value": None}
        missing_reasons = [field["missing_evidence_reason"] for field in spec["fields"].values() if field["presence_status"] == "not_present" and field.get("missing_evidence_reason")]
        ambiguity_reasons = []
    else:
        engine_result = None
        readiness = "HUMAN_CLARIFICATION_REQUIRED"
        expected = {"status": "NO_RESULT_CONFLICT_OR_AMBIGUITY", "unit": None, "value": None}
        missing_reasons = [field["missing_evidence_reason"] for field in spec["fields"].values()
                           if field["presence_status"] == "not_present" and field.get("missing_evidence_reason")]
        ambiguity_reasons = [field["ambiguity_reason"] for field in spec["fields"].values() if field["presence_status"] == "ambiguous" and field.get("ambiguity_reason")]

    field_rows = list(spec["fields"].values())
    for field in field_rows:
        if field["presence_status"] in {"present", "ambiguous"} and not field.get("evidence"):
            raise ValueError(f"Present/ambiguous field lacks an evidence anchor for {doc_id}: {field['field_name']}")
        if field["presence_status"] == "ambiguous" and field.get("candidates"):
            anchored = {evidence.get("candidate_index") for evidence in field["evidence"]
                        if evidence.get("candidate_index") is not None}
            if anchored != set(range(len(field["candidates"]))):
                raise ValueError(f"Ambiguity candidate evidence is incomplete for {doc_id}: {field['field_name']}")
        for evidence in field.get("evidence", []):
            if not evidence.get("text") or evidence["page_number"] > page_count:
                raise ValueError(f"Invalid evidence anchor for {doc_id}: {field['field_name']}")

    page_meta = []
    for page_index, scene in enumerate(scenes, 1):
        meta = {"page_number": page_index, "orientation": "landscape" if scene.width > scene.height else "portrait"}
        if plan_row["format"].endswith("pdf"):
            meta.update({"width_points": scene.width, "height_points": scene.height, "coordinate_system": "normalized_page_top_left"})
        else:
            image = images[page_index - 1]
            meta.update({"width_pixels": image.width, "height_pixels": image.height, "coordinate_system": "normalized_image_top_left"})
        page_meta.append(meta)

    annotation = {
        "annotation_schema": "greenledger_pilot_evidence_v1",
        "document_id": doc_id,
        "domain": domain,
        "activity_id": {"electricity": "purchased_electricity", "diesel": "diesel_fuel", "lpg": "lpg", "materials": "purchased_materials", "freight": "selected_transport"}[domain],
        "evidence_state": state,
        "expected_accounting_readiness": readiness,
        "human_confirmation_required": True,
        "document_type": {"electricity": "utility_bill_or_statement", "diesel": "fuel_receipt_invoice_or_fleet_record", "lpg": "lpg_supply_or_delivery_record", "materials": "purchase_or_goods_receipt", "freight": "india_road_freight_record"}[domain],
        "supplier_name": spec["supplier"],
        "template_family": template_name,
        "page_count": page_count,
        "pages": page_meta,
        "fields": field_rows,
        "missing_evidence_reasons": missing_reasons,
        "ambiguity_reasons": ambiguity_reasons,
        "expected_deterministic_result": expected,
        "evaluation_notes": [
            "Annotations are generated from the structured source objects and renderer evidence anchors.",
            "All expected numeric results were obtained from the existing deterministic GreenLedger accounting engine after human confirmation was simulated for ready cases.",
            "No model or OCR output was run or used to create these labels.",
        ],
        "layout_audit": {"visual_field_order": visual_order, "structure": structure,
                         "page_size_template": page_size_name, "font_family": font_family},
    }
    manifest_row = {
        "document_id": doc_id,
        "domain": domain,
        "activity_id": annotation["activity_id"],
        "document_type": annotation["document_type"],
        "format": plan_row["format"],
        "file": relative_path.as_posix(),
        "page_count": page_count,
        "evidence_state": state,
        "expected_accounting_readiness": readiness,
        "template_family": template_name,
        "layout_structure": structure,
        "page_size_template": page_size_name,
        "quality_effect": effect,
        "phone_style_simulated": phone_simulated,
        "logo_mark": (template.header_style % 7 == 2),
        "sha256": sha256(output_path),
        "file_bytes": output_path.stat().st_size,
        "supplier_identity": spec["supplier"],
    }
    return manifest_row, annotation, visible_text, visual_hash


def average_hash(image: Image.Image) -> int:
    gray = ImageOps.grayscale(image)
    dark_ink_mask = gray.point(lambda pixel: 255 if pixel < 238 else 0)
    crop = dark_ink_mask.getbbox()
    if crop:
        gray = gray.crop(crop)
    pixels = list(gray.resize((8, 8), Image.Resampling.LANCZOS).getdata())
    mean = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= mean)
    return value


def bit_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def accessible_existing_train_validation_images() -> list[Path]:
    """Return only the explicitly accessible A-F image filenames; never open G/H test files."""
    roots = {"electricity": 200, "diesel": 160, "lpg": 160}
    paths: list[Path] = []
    for domain, count in roots.items():
        for index in range(1, count + 1):
            family_index = (index - 1) % 8
            if family_index <= 5:  # A-E train and F validation; G/H are never accessed.
                path = ROOT / "data" / "synthetic" / "greenledger_v0_1_1_partial" / "documents" / domain / f"GL-SYN-{'E' if domain == 'electricity' else 'D' if domain == 'diesel' else 'L'}-{index:04d}.png"
                if path.is_file():
                    paths.append(path)
    return paths


def make_contact_sheet(cache: dict[str, Image.Image], manifest_rows: list[dict[str, Any]], path: Path) -> None:
    selected = [row for row in manifest_rows if row["document_id"] in cache]
    columns, cell_w, cell_h, label_h = 3, 330, 420, 56
    rows = math.ceil(len(selected) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * (cell_h + label_h)), "#E7E9EA")
    draw = ImageDraw.Draw(sheet)
    font_label = pil_font("sans", True, 22)
    font_sub = pil_font("sans", False, 18)
    for index, row in enumerate(selected):
        x = (index % columns) * cell_w
        y = (index // columns) * (cell_h + label_h)
        draw.rectangle((x + 8, y + 8, x + cell_w - 8, y + cell_h - 8), fill="#FFFFFF", outline="#B8C0C4", width=2)
        thumb = ImageOps.contain(cache[row["document_id"]].convert("RGB"), (cell_w - 30, cell_h - 30))
        sheet.paste(thumb, (x + (cell_w - thumb.width) // 2, y + (cell_h - thumb.height) // 2))
        draw.text((x + 12, y + cell_h), f"{row['document_id']}  |  {row['domain']}", fill="#20292E", font=font_label)
        draw.text((x + 12, y + cell_h + 28), f"{row['format']}  |  {row['page_count']} page(s)", fill="#4E5A60", font=font_sub)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)


def verify_pdf(path: Path, expected_pages: int) -> dict[str, Any]:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        process = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, check=False, timeout=30)
        if process.returncode != 0:
            raise ValueError(f"pdfinfo failed for {path.name}: {process.stderr[:300]}")
        match = re.search(r"^Pages:\s+(\d+)", process.stdout, re.MULTILINE)
        if not match:
            raise ValueError(f"pdfinfo did not report pages for {path.name}")
        actual = int(match.group(1))
        method = "pdfinfo"
    else:
        payload = path.read_bytes()
        actual = len(re.findall(rb"/Type\s*/Page\b", payload))
        method = "ReportLab page-object scan"
    if actual != expected_pages:
        raise ValueError(f"Page count mismatch for {path.name}: expected {expected_pages}, actual {actual}")
    return {"actual_page_count": actual, "verification_method": method}


def audit_dataset(base_dir: Path, manifest_rows: list[dict[str, Any]], annotations: list[dict[str, Any]],
                  annotation_path: Path, image_hashes_by_doc: dict[str, int], visible_text_by_doc: dict[str, list[str]]) -> dict[str, Any]:
    ids_manifest = [row["document_id"] for row in manifest_rows]
    ids_annotations = [row["document_id"] for row in annotations]
    if len(ids_manifest) != 120 or len(set(ids_manifest)) != 120:
        raise ValueError("Manifest must contain exactly 120 unique document IDs.")
    if set(ids_manifest) != set(ids_annotations) or len(ids_annotations) != 120:
        raise ValueError("Annotation IDs do not match manifest IDs exactly.")
    page_count_checks = {}
    image_format_checks = {}
    forbidden_hits = []
    digital_text_layer_checks = 0
    scanned_pdf_no_text_layer_checks = 0
    present_field_count = 0
    present_field_anchor_count = 0
    ambiguous_field_count = 0
    ambiguous_candidate_count = 0
    annotation_index = {row["document_id"]: row for row in annotations}
    for row in manifest_rows:
        path = base_dir / row["file"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise ValueError(f"Missing or checksum-invalid document file: {row['document_id']}")
        if path.suffix.casefold() == ".pdf":
            page_count_checks[row["document_id"]] = verify_pdf(path, row["page_count"])
            text_cmd = shutil.which("pdftotext")
            if text_cmd:
                extracted = subprocess.run([text_cmd, str(path), "-"], capture_output=True, text=True,
                                           check=False, timeout=30)
                if extracted.returncode != 0:
                    raise ValueError(f"pdftotext could not read {path.name}")
                if row["format"] == "simulated_scanned_pdf" and extracted.stdout.strip():
                    raise ValueError(f"Image-only scanned PDF unexpectedly has a text layer: {row['document_id']}")
                if row["format"] == "born_digital_pdf":
                    if not extracted.stdout.strip():
                        raise ValueError(f"Born-digital PDF has no extractable text layer: {row['document_id']}")
                    digital_text_layer_checks += 1
                elif row["format"] == "simulated_scanned_pdf":
                    scanned_pdf_no_text_layer_checks += 1
                visible = extracted.stdout.casefold()
                matches = [term for term in FORBIDDEN_VISIBLE_TERMS if term in visible]
                if matches:
                    forbidden_hits.append({"document_id": row["document_id"], "terms": matches})
        else:
            with Image.open(path) as image:
                actual_format = image.format
                image.verify()
            expected_format = "PNG" if path.suffix.casefold() == ".png" else "JPEG"
            if actual_format != expected_format:
                raise ValueError(f"Format mismatch for {path.name}: {actual_format} != {expected_format}")
            image_format_checks[row["document_id"]] = actual_format
        ann = annotation_index[row["document_id"]]
        if len(ann["pages"]) != row["page_count"]:
            raise ValueError(f"Annotation page count mismatch for {row['document_id']}")
        for field in ann["fields"]:
            if field["presence_status"] == "present":
                present_field_count += 1
                if not field.get("evidence"):
                    raise ValueError(f"Present field lacks evidence: {row['document_id']} {field['field_name']}")
                present_field_anchor_count += 1
            elif field["presence_status"] == "ambiguous":
                ambiguous_field_count += 1
                if not field.get("evidence"):
                    raise ValueError(f"Ambiguous field lacks evidence: {row['document_id']} {field['field_name']}")
                candidate_indexes = {evidence.get("candidate_index") for evidence in field["evidence"]
                                     if evidence.get("candidate_index") is not None}
                candidate_total = len(field.get("candidates", []))
                if candidate_total and candidate_indexes != set(range(candidate_total)):
                    raise ValueError(f"Ambiguity candidate lacks evidence: {row['document_id']} {field['field_name']}")
                ambiguous_candidate_count += candidate_total
            for evidence in field["evidence"]:
                if evidence["page_number"] < 1 or evidence["page_number"] > row["page_count"]:
                    raise ValueError(f"Invalid page index: {row['document_id']} {field['field_name']}")
                box = evidence["bbox"]
                if any(not isinstance(box[k], (int, float)) for k in ("x", "y", "width", "height")):
                    raise ValueError(f"Non-numeric bounding box: {row['document_id']}")
                if box["x"] < 0 or box["y"] < 0 or box["width"] <= 0 or box["height"] <= 0 or box["x"] + box["width"] > 1.00001 or box["y"] + box["height"] > 1.00001:
                    raise ValueError(f"Out-of-range evidence box: {row['document_id']} {field['field_name']} {box}")
                if not evidence.get("text"):
                    raise ValueError(f"Empty evidence text: {row['document_id']} {field['field_name']}")
        visible = " ".join(visible_text_by_doc[row["document_id"]]).casefold()
        hits = [term for term in FORBIDDEN_VISIBLE_TERMS if term in visible]
        if hits:
            forbidden_hits.append({"document_id": row["document_id"], "terms": hits})
        state = row["evidence_state"]
        expected = ann["expected_deterministic_result"]
        if state == "ready" and expected["status"] != "DETERMINISTIC_RESULT_AVAILABLE_AFTER_HUMAN_CONFIRMATION":
            raise ValueError(f"Ready record lacks an engine result: {row['document_id']}")
        if state != "ready" and expected.get("value") is not None:
            raise ValueError(f"Non-ready record has a numeric result: {row['document_id']}")
    if forbidden_hits:
        raise ValueError(f"Visible generated text contains an accounting label/result: {forbidden_hits[:3]}")

    exact_hashes = Counter(row["sha256"] for row in manifest_rows)
    if max(exact_hashes.values()) != 1:
        raise ValueError("Exact duplicate document files found within the pilot.")
    supplier_names = {row["supplier_identity"] for row in manifest_rows}
    current_known = {
        *(f"Fictional Utility {i:02d}" for i in range(1, 7)),
        *(f"Sample Fuel Depot {i:02d}" for i in range(1, 7)),
        *(f"Example Gas Supply {i:02d}" for i in range(1, 7)),
    }
    supplier_overlap = sorted(supplier_names & current_known)
    if supplier_overlap:
        raise ValueError(f"Supplier name overlaps current accessible benchmark: {supplier_overlap}")
    if any(re.search(r"\s\d{2}$", name) for name in supplier_names):
        raise ValueError("New supplier list unexpectedly uses the old numbered-suffix pattern.")

    accessible_paths = accessible_existing_train_validation_images()
    existing_hashes = {sha256(path) for path in accessible_paths}
    image_exact_overlap = sorted(set(existing_hashes) & {row["sha256"] for row in manifest_rows})
    existing_ahashes = []
    for path in accessible_paths:
        with Image.open(path) as image:
            existing_ahashes.append(average_hash(image.copy()))
    min_distances = []
    for image_hash in image_hashes_by_doc.values():
        if existing_ahashes:
            min_distances.append(min(bit_distance(image_hash, other) for other in existing_ahashes))

    domain_counts = dict(Counter(row["domain"] for row in manifest_rows))
    state_counts = dict(Counter(row["evidence_state"] for row in manifest_rows))
    format_counts = dict(Counter(row["format"] for row in manifest_rows))
    page_counts = dict(Counter(str(row["page_count"]) for row in manifest_rows))
    family_counts = dict(Counter(row["template_family"] for row in manifest_rows))
    structures = dict(Counter(row["layout_structure"] for row in manifest_rows))
    order_signatures = Counter(tuple(ann["layout_audit"]["visual_field_order"]) for ann in annotations)
    max_order_repeat = max(order_signatures.values()) if order_signatures else 0
    line_signatures = Counter(tuple(sorted(set(re.findall(r"[A-Za-z][A-Za-z /-]{2,32}:?", text)))) for doc in visible_text_by_doc.values() for text in doc)
    duplicate_line_examples = [text for text, count in line_signatures.most_common(10) if count > 10]
    report = {
        "status": "PASS",
        "document_count": len(manifest_rows),
        "annotation_count": len(annotations),
        "unique_document_hashes": len(exact_hashes),
        "document_files_checksum_verified": True,
        "file_integrity": {"pdfs_page_checked": len(page_count_checks), "images_format_checked": len(image_format_checks),
                           "born_digital_pdf_text_layers_checked": digital_text_layer_checks,
                           "simulated_scanned_pdf_no_text_layers_checked": scanned_pdf_no_text_layer_checks,
                           "page_count_checks": page_count_checks},
        "annotation_integrity": {"all_ids_match": True, "all_evidence_page_numbers_valid": True,
                                  "all_bounding_boxes_in_normalized_page_bounds": True,
                                  "all_present_fields_have_evidence": present_field_count == present_field_anchor_count,
                                  "all_ambiguous_fields_and_candidates_have_evidence": True,
                                  "present_fields_checked": present_field_count,
                                  "ambiguous_fields_checked": ambiguous_field_count,
                                  "ambiguous_candidates_checked": ambiguous_candidate_count,
                                  "non_ready_records_have_no_expected_numeric_result": True},
        "visible_ground_truth_leak_scan": {"forbidden_terms_found": 0, "terms_checked": list(FORBIDDEN_VISIBLE_TERMS)},
        "composition": {"domain": domain_counts, "evidence_state": state_counts,
                        "format": format_counts, "page_count": page_counts,
                        "template_family": family_counts, "layout_structure": structures},
        "variation": {"distinct_field_order_signatures": len(order_signatures),
                      "most_repeated_field_order_signature_count": max_order_repeat,
                      "supplier_count": len(supplier_names),
                      "template_family_count": len(family_counts),
                      "max_documents_per_template_family": max(family_counts.values()),
                      "repeated_wording_screen_examples_over_10_occurrences": duplicate_line_examples},
        "leakage_check_against_accessible_existing_train_validation_only": {
            "old_test_split_accessed": False,
            "existing_accessible_image_count": len(accessible_paths),
            "exact_image_sha256_overlaps": len(image_exact_overlap),
            "exact_supplier_name_overlaps": len(supplier_overlap),
            "new_template_names_collide_with_old_layout_A_to_F": False,
            "minimum_average_hash_distance_to_old_train_validation": min(min_distances) if min_distances else None,
            "median_per_document_minimum_average_hash_distance": sorted(min_distances)[len(min_distances)//2] if min_distances else None,
            "average_hash_note": "8x8 average-hash distance is a coarse visual screen, not proof of structural independence.",
        },
        "notes": [
            "The existing quarantined test annotation records and test images were not read by this audit.",
            "Existing comparison images were limited to filenames belonging to layouts A-E (train) and F (validation).",
            "Visual difference screening cannot prove complete template independence; manual contact-sheet review remains necessary.",
        ],
    }
    return report


def library_version(package: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(package)
    except Exception:
        return None


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


CONTACT_INDICES: set[int] = set()


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing pilot directory: {OUTPUT}")
    rng = random.Random(SEED)
    plan = make_plan(rng)
    if STAGING.exists():
        # A prior interrupted run may leave its first deterministic artifact behind.
        # Resume only that narrowly verifiable state; never overwrite an arbitrary tree.
        first = plan[0]
        first_extension = output_extension(first["format"])
        expected_first = STAGING / "documents" / first["domain"] / f"GLP-{DOMAIN_CODES[first['domain']]}-001{first_extension}"
        staged_files = sorted(path for path in STAGING.rglob("*") if path.is_file())
        if staged_files != [expected_first] or not expected_first.is_file():
            raise SystemExit(f"Refusing to resume unexpected staging contents: {STAGING}")
    else:
        STAGING.mkdir(parents=True)
        (STAGING / "documents").mkdir()
    global CONTACT_INDICES
    # Preview examples cover every domain/state without printing state labels into the sheet.
    chosen: set[int] = set()
    for domain in DOMAIN_CODES:
        for state in ("ready", "incomplete", "ambiguous"):
            candidate = next(row for row in plan if row["domain"] == domain and row["state"] == state)
            chosen.add(candidate["pilot_index"])
    CONTACT_INDICES = chosen
    contact_cache: dict[str, Image.Image] = {}
    manifest_rows: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    visible_text_by_doc: dict[str, list[str]] = {}
    preview_hashes: dict[str, int] = {}
    sequence_counts: Counter = Counter()
    for plan_row in plan:
        row, annotation, visible, visual_hash = build_one_document(plan_row, sequence_counts[plan_row["domain"]] + 1,
                                                                   sequence_counts, rng, STAGING, contact_cache)
        manifest_rows.append(row)
        annotations.append(annotation)
        visible_text_by_doc[row["document_id"]] = visible
        preview_hashes[row["document_id"]] = visual_hash

    annotations_path = STAGING / "annotations.jsonl"
    write_text(annotations_path, "".join(canonical_json(row) + "\n" for row in annotations))
    make_contact_sheet(contact_cache, manifest_rows, STAGING / "previews" / "contact_sheet.png")
    integrity = audit_dataset(STAGING, manifest_rows, annotations, annotations_path, preview_hashes, visible_text_by_doc)
    integrity["composition"]["material_identity"] = dict(Counter(
        row.get("material_identity") for row in plan if row["domain"] == "materials"
    ))
    integrity["composition"]["freight_vehicle_class_balance_only"] = dict(Counter(
        row["vehicle"][0] for row in plan if row["domain"] == "freight"
    ))
    manifest = {
        "dataset_id": "greenledger_unseen_structure_pilot_120_2026-11-15",
        "dataset_version": "1.0.1",
        "purpose": "Independent synthetic pilot challenge for unseen business-document structures and evidence completeness.",
        "synthetic_only": True,
        "used_for_model_training_or_benchmarking": False,
        "split": "SEPARATE_PILOT_CHALLENGE_NOT_TRAIN_VALIDATION_OR_TEST",
        "generated_total": len(manifest_rows),
        "seed": SEED,
        "generator_version": GENERATOR_VERSION,
        "generator_script": "scripts/generate_unseen_structure_pilot.py",
        "generator_script_sha256": sha256(Path(__file__).resolve()),
        "rendering_libraries": {"Pillow": library_version("Pillow"), "reportlab": library_version("reportlab")},
        "ground_truth_is_separate": True,
        "expected_result_method": "Ready cases passed through greenledger.core.evaluate_submission with fields_confirmed=yes; non-ready cases have no numeric expected result.",
        "old_quarantined_test_split_accessed": False,
        "not_real_world_validation": True,
        "counts": {
            "by_domain": dict(Counter(row["domain"] for row in manifest_rows)),
            "by_evidence_state": dict(Counter(row["evidence_state"] for row in manifest_rows)),
            "by_format": dict(Counter(row["format"] for row in manifest_rows)),
            "by_extension": dict(Counter(Path(row["file"]).suffix.casefold() for row in manifest_rows)),
            "by_page_count": dict(Counter(str(row["page_count"]) for row in manifest_rows)),
            "by_template_family": dict(Counter(row["template_family"] for row in manifest_rows)),
            "by_quality_effect": dict(Counter(row["quality_effect"] for row in manifest_rows)),
        },
        "documents": manifest_rows,
        "limitations": [
            "All documents are synthetic and rendered locally; they are not records from real vendors or SMEs.",
            "Simulated raster scans and phone-style page captures are explicitly image transformations, not genuine scans or photographs.",
            "The pilot is coverage-oriented and is not a statistically powered population estimate.",
            "Template novelty is supported by separate rendering code and a coarse visual screen; independent human review is still needed.",
        ],
    }
    write_text(STAGING / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(STAGING / "integrity_report.json", json.dumps(integrity, ensure_ascii=False, indent=2) + "\n")
    provenance = {
        "generator_version": GENERATOR_VERSION,
        "generator_script": "scripts/generate_unseen_structure_pilot.py",
        "generator_script_sha256": manifest["generator_script_sha256"],
        "seed": SEED,
        "render_backends": ["ReportLab vector PDF", "Pillow raster scene", "ReportLab image-only PDF wrapper"],
        "not_imported_or_called": ["scripts/generate_synthetic_benchmark.py", "old layout_A through layout_H templates"],
        "randomized_dimensions": ["document structure", "field order", "page size/orientation", "typeface", "color", "supplier", "wording", "quality simulation", "format", "page count"],
        "no_model_or_ocr_run": True,
        "accounting_oracle": "Existing deterministic greenledger.core.evaluate_submission; only complete and unambiguous cases are calculated.",
        "synthetic_capture_disclosure": "Scan/phone visual effects are simulated; no genuine scanned or photographed documents were available or claimed.",
    }
    write_text(STAGING / "GENERATION_PROVENANCE.json", json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    readme = """# GreenLedger unseen-structure pilot challenge (120 documents)

This is a separate, synthetic pilot challenge. It is not part of the existing 520-record benchmark and is not train/validation/test data. No model was trained or benchmarked on this dataset.

## Contents

- `documents/`: 120 documents across electricity, diesel, LPG, selected materials, and India road freight.
- `annotations.jsonl`: evidence-grounded labels and readiness expectations, separate from document files.
- `manifest.json`: document IDs, domains, file formats, page counts, evidence states, template family, hashes, and generator metadata.
- `integrity_report.json`: checksums, file/page/annotation checks, composition, and comparison to accessible existing train/validation images only.
- `GENERATION_PROVENANCE.json`: seed, renderer, source hash, and simulation disclosures.
- `previews/contact_sheet.png`: visual sample; labels show IDs/domain/format only.

## Evidence states

- `ready`: the visible document evidence is sufficient to proceed after mandatory human confirmation. Expected results were produced only by the existing deterministic accounting engine.
- `incomplete`: a required fact is absent; no expected numeric result is present.
- `ambiguous`: the document contains unresolved evidence alternatives or conflicts; no expected numeric result is present.

No evidence-state label or expected accounting result is printed in a document. The annotations include page numbers and normalized top-left bounding boxes. Coordinates refer to the rendered PDF page or final standalone image; simulated skew/capture effects are reflected in the boxes.

## Format disclosure

The dataset includes born-digital vector PDFs, image-only PDFs generated by rasterizing synthetic pages, and standalone PNG/JPEG images. Some standalone images have a simulated phone-style background/shadow and slight rotation. These are rendering simulations, not real scans or photographs.

## Limitations

All supplier identities and transactions are fictional. The dataset is a controlled synthetic stress pilot, not real-SME validation and not a statistically powered estimate of production performance. The contact sheet and automated checks cannot substitute for expert visual review.
"""
    write_text(STAGING / "README.md", readme)

    # Re-read the written JSONL, then recompute checksums and counts before publication.
    persisted_annotations = [json.loads(line) for line in annotations_path.read_text(encoding="utf-8").splitlines() if line]
    persisted_manifest = json.loads((STAGING / "manifest.json").read_text(encoding="utf-8"))
    persisted_integrity = audit_dataset(STAGING, persisted_manifest["documents"], persisted_annotations,
                                        annotations_path, preview_hashes, visible_text_by_doc)
    if persisted_integrity["status"] != "PASS":
        raise ValueError("Final persisted audit did not pass.")
    STAGING.rename(OUTPUT)
    print(json.dumps({"status": "GENERATED_AND_AUDITED", "output": str(OUTPUT),
                      "documents": manifest["generated_total"], "integrity": integrity["status"],
                      "evidence_states": manifest["counts"]["by_evidence_state"],
                      "formats": manifest["counts"]["by_format"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


