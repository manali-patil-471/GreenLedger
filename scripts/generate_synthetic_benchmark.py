"""Generate a reproducible, explicitly synthetic GreenLedger document slice.

This first release covers only electricity, diesel, and LPG. It intentionally
does not emit material/freight documents or CO2e ground truth because the
project's corresponding accounting decisions/factors are not complete.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import textwrap
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


SCRIPT_VERSION = "0.1.1"
SEED_DEFAULT = 20260924
COUNTS = {"electricity": 200, "diesel": 160, "lpg": 160}
FAMILIES_PER_TYPE = 8
FONT_FILES = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\calibri.ttf"),
    Path(r"C:\Windows\Fonts\times.ttf"),
    Path(r"C:\Windows\Fonts\cour.ttf"),
]
THEMES = [
    ("#183D5B", "#E7EFF4"),
    ("#245B46", "#E7F1EB"),
    ("#673B5D", "#F2EAF0"),
    ("#735227", "#F4EFE6"),
    ("#3B4C82", "#EAECF5"),
    ("#4F5961", "#ECEFF1"),
    ("#8B3F36", "#F5EAE8"),
    ("#27616B", "#E7F0F1"),
]
LAYOUT_SPLITS = {
    "layout_A": "train",
    "layout_B": "train",
    "layout_C": "train",
    "layout_D": "train",
    "layout_E": "train",
    "layout_F": "validation",
    "layout_G": "test",
    "layout_H": "test",
}


def font(size: int, family_index: int = 0) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidate = FONT_FILES[family_index % len(FONT_FILES)]
    if candidate.exists():
        return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fmt_number(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}"


def fmt_date(value: date, style: int) -> str:
    formats = ["%d/%m/%Y", "%d-%b-%Y", "%Y-%m-%d", "%d %b %Y"]
    return value.strftime(formats[style % len(formats)])


def date_for_index(kind: str, index: int, rng: random.Random) -> tuple[date, date | None, str | None]:
    if kind == "electricity":
        # CEA V22 has a selected CO2-only reference series for these two fiscal years.
        fiscal_start = date(2024, 4, 1) if index % 2 == 0 else date(2025, 4, 1)
        month_offset = rng.randrange(12)
        year = fiscal_start.year + (fiscal_start.month - 1 + month_offset) // 12
        month = (fiscal_start.month - 1 + month_offset) % 12 + 1
        start = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        end = next_month - timedelta(days=1)
        fy = "FY2024-25" if start < date(2025, 4, 1) else "FY2025-26"
        return start, end, fy
    day_offset = rng.randrange(0, 730)
    start = date(2024, 10, 1) + timedelta(days=day_offset)
    return start, None, None


def add_bbox(box: tuple[int, int, int, int], width: int, height: int, angle: float) -> dict[str, float]:
    x0, y0, x1, y1 = box
    if angle:
        theta = math.radians(angle)
        cosine, sine = math.cos(theta), math.sin(theta)
        cx, cy = width / 2, height / 2
        points = []
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            dx, dy = x - cx, y - cy
            points.append((cx + cosine * dx + sine * dy, cy - sine * dx + cosine * dy))
        x0 = max(0, min(p[0] for p in points))
        y0 = max(0, min(p[1] for p in points))
        x1 = min(width, max(p[0] for p in points))
        y1 = min(height, max(p[1] for p in points))
    return {
        "x": round(x0 / width, 6),
        "y": round(y0 / height, 6),
        "width": round(max(0, x1 - x0) / width, 6),
        "height": round(max(0, y1 - y0) / height, 6),
    }


class Page:
    def __init__(self, width: int, height: int, family_index: int, rng: random.Random):
        self.width = width
        self.height = height
        self.family_index = family_index
        self.rng = rng
        self.primary, self.pale = THEMES[family_index]
        self.image = Image.new("RGB", (width, height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.lines: list[str] = []
        self.boxes: dict[str, tuple[int, int, int, int]] = {}
        self.field_strings: dict[str, str] = {}

    def header(self, title: str, subtitle: str, supplier: str) -> None:
        style = self.family_index % 8
        if style in (0, 3, 6):
            self.draw.rectangle((0, 0, self.width, 210), fill=self.primary)
            x, anchor = 54, "la"
            self.draw.text((x, 42), supplier.upper(), fill="white", font=font(23, self.family_index))
            self.draw.text((x, 88), title, fill="white", font=font(34, self.family_index))
            self.draw.text((x, 145), subtitle, fill="#EDF3F6", font=font(18, self.family_index))
            self.lines.extend([supplier.upper(), title, subtitle])
        elif style in (1, 4):
            self.draw.rectangle((28, 28, self.width - 28, 202), fill=self.pale, outline=self.primary, width=3)
            x = self.width // 2
            self.draw.text((x, 54), supplier.upper(), fill=self.primary, font=font(21, self.family_index), anchor="mt")
            self.draw.text((x, 91), title, fill="#1C252B", font=font(32, self.family_index), anchor="mt")
            self.draw.text((x, 146), subtitle, fill="#47535D", font=font(17, self.family_index), anchor="mt")
            self.lines.extend([supplier.upper(), title, subtitle])
        else:
            self.draw.rectangle((0, 0, 20, self.height), fill=self.primary)
            self.draw.text((54, 40), title, fill=self.primary, font=font(34, self.family_index))
            self.draw.text((54, 93), supplier.upper(), fill="#24313A", font=font(22, self.family_index))
            self.draw.text((54, 143), subtitle, fill="#5B6770", font=font(17, self.family_index))
            self.draw.line((54, 196, self.width - 54, 196), fill=self.primary, width=4)
            self.lines.extend([title, supplier.upper(), subtitle])

    def field(self, field_name: str, label: str, raw_value: str) -> None:
        self.field_strings[field_name] = f"{label}: {raw_value}"

    def finish_body(self, title: str, header_lines: list[str], body_items: list[str]) -> float:
        style = self.family_index % 8
        margin = 54 if self.width > 900 else 42
        top = 240
        usable_w = self.width - margin * 2
        body_font = font(19 if self.width > 900 else 17, self.family_index)
        small_font = font(15, self.family_index)
        lines: list[tuple[str, str | None]] = []
        for item in header_lines:
            lines.append((item, None))
        if style in (2, 6):
            # Boxed rows with alternating fills and a clear key-value structure.
            y = top
            row_h = 54
            for i, item in enumerate(body_items):
                fill = self.pale if i % 2 == 0 else "#FFFFFF"
                self.draw.rectangle((margin, y, self.width - margin, y + row_h), fill=fill, outline="#C7D0D6", width=1)
                wrapped = self._wrap(item, body_font, usable_w - 28)
                baseline = y + 14
                for part in wrapped:
                    self.draw.text((margin + 14, baseline), part, fill="#1C252B", font=body_font)
                    baseline += 25
                self._save_box(item, (margin + 10, y + 3, self.width - margin - 6, y + row_h - 3))
                y += row_h
                lines.append((item, None))
                self.lines.append(item)
            return y
        if style in (3, 7):
            # Two-column form; visual row pairs remain explicit in the OCR transcript.
            half = (usable_w - 22) // 2
            y = top
            for i in range(0, len(body_items), 2):
                row_items = body_items[i:i + 2]
                for j, item in enumerate(row_items):
                    x = margin + j * (half + 22)
                    self.draw.rectangle((x, y, x + half, y + 82), fill=self.pale, outline="#B8C4CB", width=2)
                    wrapped = self._wrap(item, body_font, half - 22)
                    baseline = y + 18
                    for part in wrapped:
                        self.draw.text((x + 12, baseline), part, fill="#1C252B", font=body_font)
                        baseline += 24
                    self._save_box(item, (x + 5, y + 5, x + half - 5, y + 77))
                    lines.append((item, None))
                    self.lines.append(item)
                y += 100
            return y
        if style == 5:
            # Receipt-style centered rows, with dotted separators.
            y = top
            for item in body_items:
                for part in self._wrap(item, body_font, usable_w - 36):
                    self.draw.text((self.width // 2, y), part, fill="#252C31", font=body_font, anchor="mt")
                    y += 26
                self.draw.line((margin + 20, y + 5, self.width - margin - 20, y + 5), fill="#AFB8BE", width=1)
                self._save_box(item, (margin + 12, y - 26, self.width - margin - 12, y + 6))
                y += 22
                lines.append((item, None))
                self.lines.append(item)
            return y
        # Default: invoice rows with mixed separators and optional row numbering.
        y = top
        for i, item in enumerate(body_items):
            if style == 1:
                self.draw.rectangle((margin, y - 4, self.width - margin, y + 40), fill=self.pale if i % 2 == 0 else "white")
            prefix = f"{i + 1:02d}  " if style == 4 else ""
            rendered = prefix + item
            wrapped = self._wrap(rendered, body_font, usable_w - 18)
            line_top = y
            for part in wrapped:
                self.draw.text((margin + 8, y), part, fill="#20282E", font=body_font)
                y += 28
            if style == 0:
                self.draw.line((margin, y + 2, self.width - margin, y + 2), fill="#D5DDE1", width=1)
            self._save_box(item, (margin + 3, line_top - 1, self.width - margin - 3, y - 2))
            lines.append((rendered, None))
            self.lines.append(rendered)
            y += 22
        return y

    def _wrap(self, text: str, selected_font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        out: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and self.draw.textbbox((0, 0), candidate, font=selected_font)[2] > max_width:
                out.append(current)
                current = word
            else:
                current = candidate
        if current:
            out.append(current)
        return out or [""]

    def _save_box(self, evidence: str, box: tuple[int, int, int, int]) -> None:
        for key, value in self.field_strings.items():
            if evidence == value:
                self.boxes[key] = box
                return

    def footer(self, y: float, document_id: str) -> None:
        y = min(max(int(y) + 20, 350), self.height - 110)
        self.draw.line((42, y, self.width - 42, y), fill="#AEB7BD", width=2)
        footer = "SYNTHETIC RESEARCH SAMPLE - NOT A REAL TRANSACTION"
        self.draw.text((self.width // 2, y + 17), footer, fill="#6B7378", font=font(15, self.family_index), anchor="mt")
        reference = f"Reference: {document_id}  |  Fictional supplier and values"
        self.draw.text((self.width // 2, y + 47), reference, fill="#7D858A", font=font(13, self.family_index), anchor="mt")
        self.lines.extend([footer, reference])


def make_field(name: str, display: str, raw: str | None, normalized, normalized_unit=None,
               presence="present", review=False, reason="", bbox=None) -> dict:
    result = {
        "field_name": name,
        "presence_status": presence,
        "expected_review_required": review,
    }
    if raw is not None:
        result["raw_text"] = raw
        result["evidence_text"] = display
    if normalized is not None or presence == "present":
        result["normalized_value"] = normalized
    if normalized_unit is not None or name in ("quantity", "unit"):
        result["normalized_unit"] = normalized_unit
    if bbox is not None:
        result["evidence_bbox"] = bbox
    if reason:
        result["uncertainty_reason"] = reason
    return result


def field_record(name: str, page: Page, raw: str | None, normalized, unit=None,
                 presence="present", review=False, reason="") -> dict:
    evidence = page.field_strings.get(name)
    box = page.boxes.get(name)
    return make_field(name, evidence or "", raw, normalized, unit, presence, review, reason, box)


def unit_trace(input_value: Decimal, input_unit: str, output_value: Decimal, rule: str, basis: str) -> list[dict]:
    return [{
        "rule_id": rule,
        "input_value": float(input_value),
        "input_unit": input_unit,
        "output_value": float(output_value),
        "output_unit": "kWh" if rule == "electricity_mwh_to_kwh" else "L",
        "basis": basis,
    }]


def apply_quality(image: Image.Image, tag: str, angle: float) -> Image.Image:
    if tag == "low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.60)
    elif tag == "blur":
        image = image.filter(ImageFilter.GaussianBlur(radius=0.65))
    elif tag == "jpeg_compression":
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=46, optimize=True)
        buffer.seek(0)
        image = Image.open(buffer).convert("RGB")
    elif tag == "faint_scan":
        image = ImageEnhance.Brightness(image).enhance(1.07)
        image = ImageEnhance.Contrast(image).enhance(0.73)
    if angle:
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
    return image


def synthetic_vendor(kind: str, family: int) -> str:
    prefix = {"electricity": "Fictional Utility", "diesel": "Sample Fuel Depot", "lpg": "Example Gas Supply"}[kind]
    return f"{prefix} {family + 1:02d}"


def choose_quality(index: int, rng: random.Random) -> tuple[str, float]:
    options = ["clean", "low_contrast", "blur", "jpeg_compression", "faint_scan", "slight_skew"]
    weights = [34, 12, 10, 13, 10, 21]
    tag = rng.choices(options, weights=weights, k=1)[0]
    angle = round(rng.choice([-1.5, -1.0, -0.6, 0.6, 1.0, 1.5]), 1) if tag == "slight_skew" else 0.0
    return tag, angle


def make_electricity(index: int, rng: random.Random, factors: dict[str, dict]) -> tuple[dict, Image.Image]:
    family = index % FAMILIES_PER_TYPE
    layout = f"layout_{chr(ord('A') + family)}"
    vendor = synthetic_vendor("electricity", family)
    customer = f"GreenLedger Test SME {index + 1:04d}"
    period_start, period_end, fiscal_year = date_for_index("electricity", index, rng)
    invoice_date = min(period_end + timedelta(days=rng.randrange(1, 19)), date(2026, 8, 31))
    amount_kwh = rng.randint(50, 10000)
    use_mwh = family in (2, 5, 7) and amount_kwh >= 1000
    if use_mwh:
        raw_quantity = Decimal(amount_kwh) / Decimal(1000)
        raw_unit = "MWh"
        quantity_text = f"{raw_quantity:,.3f} MWh"
        trace = unit_trace(raw_quantity, "MWh", Decimal(amount_kwh), "electricity_mwh_to_kwh", "1 MWh = 1000 kWh; exact SI unit scaling.")
    else:
        raw_quantity = Decimal(amount_kwh)
        raw_unit = "kWh"
        quantity_text = f"{fmt_number(raw_quantity)} kWh"
        trace = []
    invoice_id = None if index % 29 == 0 else f"SYN-E-{index + 1:04d}"
    account = f"ACCT-S-{rng.randrange(100000, 999999)}"
    meter = None if index % 13 == 0 else f"MTR-X{rng.randrange(10000, 99999)}"
    period_text = f"{fmt_date(period_start, family)} - {fmt_date(period_end, family + 1)}"
    amount = Decimal(amount_kwh) * Decimal(rng.choice(["7.25", "8.10", "9.35", "10.20"])) + Decimal(rng.randrange(35, 300))
    amount_text = f"{rng.choice(['INR', 'Rs.', 'Rupees'])} {fmt_number(amount)}"
    currency_symbol = rng.choice(["INR", "Rs.", "Rupees"])
    page = Page(1040 if family not in (5, 6) else 850, 1450 if family not in (5, 6) else 1370, family, rng)
    page.header("ELECTRICITY SERVICE STATEMENT" if family % 2 == 0 else "MONTHLY POWER BILL",
                "Business account | Billing period summary", vendor)
    fields = [
        ("supplier_name", "Supplier", vendor),
        ("customer_name", "Customer", customer),
        ("invoice_number", "Bill reference", invoice_id),
        ("invoice_date", "Issue date", fmt_date(invoice_date, family + 2)),
        ("billing_period", "Service period", period_text),
        ("account_number", "Account", account),
        ("meter_id", "Meter", meter),
        ("activity_description", "Energy charge", rng.choice(["Grid electricity consumed", "Active energy used", "Electricity units billed", "Purchased grid power"])),
        ("quantity", rng.choice(["Consumption", "Units billed", "Energy used", "Total active energy"]), quantity_text),
        ("unit", "Quantity unit", raw_unit),
        ("total_amount", "Amount due", amount_text),
        ("currency", "Currency", currency_symbol),
    ]
    for name, label, value in fields:
        page.field(name, label, value)
    body = [f"{label}: {value}" for _, label, value in fields if value is not None]
    body += [f"Payment note: {rng.choice(['Pay by the printed due date', 'Keep this bill for account records', 'Meter reading is for the stated service period'])}", "No payment card or bank details are included in this sample."]
    y = page.finish_body("", [], body)
    page.footer(y, f"GL-SYN-E-{index + 1:04d}")
    tag, angle = choose_quality(index, rng)
    factor = factors[fiscal_year]
    gt_fields = []
    for name, label, value in fields:
        if name == "quantity":
            raw = quantity_text
            gt_fields.append(field_record(name, page, raw, float(amount_kwh), "kWh"))
        elif name == "unit":
            gt_fields.append(field_record(name, page, raw_unit, "kWh", "kWh"))
        elif name == "invoice_date":
            gt_fields.append(field_record(name, page, value, invoice_date.isoformat()))
        elif name == "billing_period":
            gt_fields.append(field_record(name, page, value, f"{period_start.isoformat()}/{period_end.isoformat()}"))
        elif name == "total_amount":
            gt_fields.append(field_record(name, page, amount_text, float(amount.quantize(Decimal('0.01'))), "INR"))
        elif name == "currency":
            gt_fields.append(field_record(name, page, currency_symbol, "INR"))
        elif value is None:
            gt_fields.append(make_field(name, "", None, None, None, "not_present"))
        else:
            gt_fields.append(field_record(name, page, value, value))
    ground_truth = {
        "ocr": {"transcription": "\n".join(page.lines)},
        "fields": gt_fields,
        "activity_normalization": {"status": "normalized", "raw_activity_text": dict((n, v) for n, _, v in fields)["activity_description"], "activity": "Purchased electricity", "normalized_activity": "purchased_electricity"},
        "unit_normalization": {
            "status": "normalized", "raw_quantity_text": quantity_text, "raw_quantity": float(raw_quantity), "raw_unit": raw_unit,
            "normalized_quantity": amount_kwh, "normalized_unit": "kWh", "conversion_trace": trace,
        },
        "ghg_classification": {
            "status": "classified", "scope": "Scope 2", "scope_category": "purchased electricity",
            "context_fields": {"account_issued_to_reporting_entity": True, "business_site_metered_consumption": True},
        },
        "factor_retrieval": {
            "status": "co2_only_reference_only", "factor_id": factor["factor_id"], "factor_value": float(factor["factor_value"]),
            "factor_unit": factor["factor_unit"], "source": factor["source"], "source_version": factor["source_version"],
            "source_url": factor["source_url"], "source_sha256": factor["source_sha256"], "geography": factor["geography"],
            "applicable_year": factor["applicable_year"], "methodology": factor["methodology"],
            "unresolved_reason": "CEA reference reports CO2 only. No verified GHG-complete Scope 2 CO2e factor/method is selected; do not calculate CO2e.",
        },
        "co2e_calculation": {"status": "not_calculable_missing_factor", "unresolved_reason": "The available CEA value is CO2-only, not a CO2e factor."},
        "review_truth": {"review_required": True, "fields": ["factor_retrieval", "co2e_calculation"], "reason_codes": ["co2_only_reference", "missing_verified_co2e_factor"], "expected_action": "escalate"},
    }
    record = make_record(f"GL-SYN-E-{index + 1:04d}", "electricity_bill", vendor, layout, period_start, page, ground_truth,
                         ["document_type_classification", "ocr_text_extraction", "carbon_field_extraction", "activity_normalization", "unit_normalization", "scope_classification", "factor_retrieval", "co2e_calculation", "confidence_estimation", "human_review_decision"], tag, angle)
    return record, apply_quality(page.image, tag, angle)


def make_diesel(index: int, rng: random.Random) -> tuple[dict, Image.Image]:
    family = index % FAMILIES_PER_TYPE
    layout = f"layout_{chr(ord('A') + family)}"
    vendor = synthetic_vendor("diesel", family)
    customer = f"GreenLedger Test SME {index + 2001:04d}"
    trans_date, _, _ = date_for_index("diesel", index, rng)
    invoice_date = trans_date + timedelta(days=rng.randrange(0, 4))
    invoice_id = None if index % 21 == 0 else f"SYN-D-{index + 1:04d}"
    ambiguous_unit = (index % 10 == 0)
    unit_choices = ["L", "litres", "liters", "kL", "mL"]
    unit = "" if ambiguous_unit else unit_choices[(index + family) % len(unit_choices)]
    if ambiguous_unit:
        raw_quantity = Decimal(rng.choice(["2.5", "75", "250", "1200"]))
        normalized_quantity = None
        quantity_text = f"Qty: {fmt_number(raw_quantity)}"
        conversion = []
    elif unit == "kL":
        normalized_quantity = Decimal(rng.randrange(1, 51)) * Decimal(100)
        raw_quantity = normalized_quantity / Decimal(1000)
        quantity_text = f"Volume supplied: {fmt_number(raw_quantity)} kL"
        conversion = unit_trace(raw_quantity, "kL", normalized_quantity, "diesel_kl_to_l", "1 kL = 1000 L; exact metric volume scaling.")
    elif unit == "mL":
        normalized_quantity = Decimal(rng.randrange(10, 300))
        raw_quantity = normalized_quantity * Decimal(1000)
        quantity_text = f"Quantity: {fmt_number(raw_quantity)} mL"
        conversion = unit_trace(raw_quantity, "mL", normalized_quantity, "diesel_ml_to_l", "1000 mL = 1 L; exact metric volume scaling.")
    else:
        normalized_quantity = Decimal(rng.randrange(25, 4201))
        if index % 4 == 0:
            normalized_quantity += Decimal("0.50")
        raw_quantity = normalized_quantity
        quantity_text = f"{rng.choice(['Volume', 'Fuel quantity', 'Qty supplied'])}: {fmt_number(raw_quantity)} {unit}"
        conversion = []
    product = rng.choice(["HSD - High Speed Diesel", "Diesel fuel", "Automotive diesel", "High-speed diesel (HSD)"])
    amount = Decimal(rng.randrange(800, 250000))
    amount_text = f"{rng.choice(['INR', 'Rs.'])} {fmt_number(amount)}"
    page = Page(900 if family in (5, 6) else 1020, 1320 if family in (5, 6) else 1450, family, rng)
    page.header(rng.choice(["FUEL SUPPLY INVOICE", "DIESEL RECEIPT", "TAX INVOICE - FUEL"]), "Counter sale / delivery record", vendor)
    fields = [
        ("supplier_name", "Supplier", vendor),
        ("customer_name", "Customer", customer),
        ("invoice_number", "Receipt / invoice no.", invoice_id),
        ("invoice_date", "Date", fmt_date(invoice_date, family + 1)),
        ("activity_description", "Product", product),
        ("quantity", "Quantity", quantity_text),
        ("unit", "Unit", unit if unit else None),
        ("vehicle_reference", "Vehicle / equipment ref.", None if index % 7 == 0 else f"TEST-{rng.choice(['VAN', 'GEN', 'EQP'])}-{rng.randrange(100,999)}"),
        ("total_amount", "Total paid", amount_text),
        ("currency", "Currency", rng.choice(["INR", "Rs."])),
    ]
    for name, label, value in fields:
        if value is not None:
            page.field(name, label, value)
    body = [f"{label}: {value}" for _, label, value in fields if value is not None]
    body += [f"Tax note: {rng.choice(['Printed total includes listed taxes', 'Document amount is for the transaction only'])}", "Keep this synthetic copy with the test records."]
    y = page.finish_body("", [], body)
    page.footer(y, f"GL-SYN-D-{index + 1:04d}")
    tag, angle = choose_quality(index, rng)
    gt_fields = []
    for name, label, value in fields:
        if name == "quantity":
            gt_fields.append(field_record(name, page, value, float(raw_quantity) if normalized_quantity is None else float(normalized_quantity), "L" if normalized_quantity is not None else None, "present", ambiguous_unit, "Quantity has no printed unit; do not assume litres." if ambiguous_unit else ""))
        elif name == "unit" and value is None:
            gt_fields.append(make_field("unit", "", None, None, None, "not_present", True, "The document does not print a unit."))
        elif name == "unit":
            gt_fields.append(field_record(name, page, value, "L", "L"))
        elif name == "invoice_date":
            gt_fields.append(field_record(name, page, value, invoice_date.isoformat()))
        elif name == "total_amount":
            gt_fields.append(field_record(name, page, value, float(amount), "INR"))
        elif name == "currency":
            gt_fields.append(field_record(name, page, value, "INR"))
        elif value is not None:
            gt_fields.append(field_record(name, page, value, value))
        else:
            gt_fields.append(make_field(name, "", None, None, None, "not_present"))
    activity = next(v for n, _, v in fields if n == "activity_description")
    unit_state = "ambiguous" if ambiguous_unit else "normalized"
    unit_gt = {
        "status": unit_state, "raw_quantity_text": quantity_text, "raw_quantity": float(raw_quantity),
    }
    if normalized_quantity is not None:
        unit_gt.update({"raw_unit": unit, "normalized_quantity": float(normalized_quantity), "normalized_unit": "L", "conversion_trace": conversion})
    else:
        unit_gt["ambiguity_reason"] = "No unit is printed beside the quantity. A litre value cannot be assumed."
    ground_truth = {
        "ocr": {"transcription": "\n".join(page.lines)}, "fields": gt_fields,
        "activity_normalization": {"status": "normalized", "raw_activity_text": activity, "activity": "Diesel fuel", "normalized_activity": "diesel_fuel"},
        "unit_normalization": unit_gt,
        "ghg_classification": {"status": "ambiguous", "scope": None, "scope_category": None, "context_fields": {"purchase_visible": True, "fuel_consumed": None, "operational_control": None}, "ambiguity_reason": "This receipt establishes a purchase, but not whether the diesel was consumed by an owned or controlled source."},
        "factor_retrieval": {"status": "method_selection_required", "unresolved_reason": "The catalogue contains CO2-only diesel values on an MJ basis; no GHG-complete fuel-specific CO2e factor or source-matched L-to-MJ conversion is selected."},
        "co2e_calculation": {"status": "not_calculable_missing_factor", "unresolved_reason": "No eligible GHG-complete CO2e factor is available for this purchase record."},
        "review_truth": {"review_required": True, "fields": ["scope", "factor_retrieval", "co2e_calculation"] + (["quantity", "unit"] if ambiguous_unit else []), "reason_codes": ["missing_boundary_context", "method_selection_required", "missing_verified_co2e_factor"] + (["missing_unit"] if ambiguous_unit else []), "expected_action": "escalate"},
    }
    record = make_record(f"GL-SYN-D-{index + 1:04d}", "diesel_fuel_invoice", vendor, layout, invoice_date, page, ground_truth,
                         ["document_type_classification", "ocr_text_extraction", "carbon_field_extraction", "activity_normalization", "unit_normalization", "scope_classification", "factor_retrieval", "co2e_calculation", "confidence_estimation", "human_review_decision"], tag, angle)
    return record, apply_quality(page.image, tag, angle)


def make_lpg(index: int, rng: random.Random) -> tuple[dict, Image.Image]:
    family = index % FAMILIES_PER_TYPE
    layout = f"layout_{chr(ord('A') + family)}"
    vendor = synthetic_vendor("lpg", family)
    customer = f"GreenLedger Test SME {index + 4001:04d}"
    transaction_date, _, _ = date_for_index("lpg", index, rng)
    invoice_date = transaction_date + timedelta(days=rng.randrange(0, 4))
    invoice_id = None if index % 23 == 0 else f"SYN-L-{index + 1:04d}"
    count_only = (index % 5 == 0)
    if count_only:
        quantity = Decimal(rng.randrange(1, 8))
        unit = "cylinder_count"
        quantity_text = f"{rng.choice(['Cylinder qty', 'Refill count', 'Units delivered'])}: {int(quantity)} cylinders"
        normalized_quantity = None
        conversion = []
    else:
        quantity = Decimal(rng.randrange(5, 101)) + Decimal(rng.choice(["0", "0.5", "1.0"]))
        unit = "kg"
        quantity_text = f"{rng.choice(['Net LPG', 'Product mass', 'Quantity supplied'])}: {fmt_number(quantity)} kg"
        normalized_quantity = quantity
        conversion = []
    product = rng.choice(["Commercial LPG", "Liquefied petroleum gas", "Cooking gas refill", "LPG cylinder supply"])
    amount = Decimal(rng.randrange(500, 45000))
    amount_text = f"{rng.choice(['INR', 'Rs.'])} {fmt_number(amount)}"
    page = Page(850 if family in (4, 5) else 1020, 1340 if family in (4, 5) else 1440, family, rng)
    page.header(rng.choice(["LPG REFILL RECEIPT", "GAS SUPPLY INVOICE", "DELIVERY NOTE - LPG"]), "Commercial supply record", vendor)
    fields = [
        ("supplier_name", "Supplier", vendor),
        ("customer_name", "Customer", customer),
        ("invoice_number", "Invoice / slip no.", invoice_id),
        ("invoice_date", "Supply date", fmt_date(invoice_date, family + 2)),
        ("activity_description", "Product", product),
        ("quantity", "Quantity", quantity_text),
        ("unit", "Unit", unit if not count_only else "cylinder count"),
        ("cylinder_net_mass", "Net fill mass", None if count_only else f"{fmt_number(quantity)} kg"),
        ("total_amount", "Amount paid", amount_text),
        ("currency", "Currency", rng.choice(["INR", "Rs."])),
    ]
    for name, label, value in fields:
        if value is not None:
            page.field(name, label, value)
    body = [f"{label}: {value}" for _, label, value in fields if value is not None]
    body += [f"Delivery note: {rng.choice(['Keep the slip for stock records', 'Container return may be recorded separately', 'Customer signature field intentionally blank'])}", "Synthetic transaction - no real supplier or purchase."]
    y = page.finish_body("", [], body)
    page.footer(y, f"GL-SYN-L-{index + 1:04d}")
    tag, angle = choose_quality(index, rng)
    gt_fields = []
    for name, label, value in fields:
        if name == "quantity":
            gt_fields.append(field_record(name, page, value, float(quantity) if normalized_quantity is not None else float(quantity), "kg" if normalized_quantity is not None else None, "present", count_only, "Cylinder count is shown without printed net gas mass." if count_only else ""))
        elif name == "unit":
            gt_fields.append(field_record(name, page, value, "kg" if not count_only else None, "kg" if not count_only else None, "present", count_only, "Cylinder count is not a mass unit." if count_only else ""))
        elif name == "cylinder_net_mass" and value is None:
            gt_fields.append(make_field("cylinder_net_mass", "", None, None, None, "not_present", True, "The receipt does not state a net fill mass."))
        elif name == "invoice_date":
            gt_fields.append(field_record(name, page, value, invoice_date.isoformat()))
        elif name == "total_amount":
            gt_fields.append(field_record(name, page, value, float(amount), "INR"))
        elif name == "currency":
            gt_fields.append(field_record(name, page, value, "INR"))
        elif value is not None:
            gt_fields.append(field_record(name, page, value, value))
        else:
            gt_fields.append(make_field(name, "", None, None, None, "not_present"))
    activity = next(v for n, _, v in fields if n == "activity_description")
    unit_gt = {"status": "ambiguous" if count_only else "normalized", "raw_quantity_text": quantity_text, "raw_quantity": float(quantity), "raw_unit": unit}
    if normalized_quantity is not None:
        unit_gt.update({"normalized_quantity": float(normalized_quantity), "normalized_unit": "kg", "conversion_trace": conversion})
    else:
        unit_gt["ambiguity_reason"] = "A cylinder count does not establish kg. The net fill mass is not printed and must not be assumed."
    ground_truth = {
        "ocr": {"transcription": "\n".join(page.lines)}, "fields": gt_fields,
        "activity_normalization": {"status": "normalized", "raw_activity_text": activity, "activity": "Liquefied petroleum gas (LPG)", "normalized_activity": "lpg"},
        "unit_normalization": unit_gt,
        "ghg_classification": {"status": "ambiguous", "scope": None, "scope_category": None, "context_fields": {"purchase_visible": True, "fuel_consumed": None, "operational_control": None}, "ambiguity_reason": "The supply slip does not establish combustion or ownership/operational control."},
        "factor_retrieval": {"status": "factor_not_verified", "unresolved_reason": "No verified, geography/year/basis-matched GHG-complete LPG CO2e factor is selected in the catalogue."},
        "co2e_calculation": {"status": "not_calculable_missing_factor", "unresolved_reason": "No verified CO2e factor is available for LPG."},
        "review_truth": {"review_required": True, "fields": ["scope", "factor_retrieval", "co2e_calculation"] + (["quantity", "unit", "cylinder_net_mass"] if count_only else []), "reason_codes": ["missing_boundary_context", "factor_not_verified"] + (["cylinder_mass_unknown"] if count_only else []), "expected_action": "escalate"},
    }
    record = make_record(f"GL-SYN-L-{index + 1:04d}", "lpg_receipt", vendor, layout, invoice_date, page, ground_truth,
                         ["document_type_classification", "ocr_text_extraction", "carbon_field_extraction", "activity_normalization", "unit_normalization", "scope_classification", "factor_retrieval", "co2e_calculation", "confidence_estimation", "human_review_decision"], tag, angle)
    return record, apply_quality(page.image, tag, angle)


def make_record(document_id: str, document_type: str, vendor: str, layout: str, local_date: date, page: Page,
                ground_truth: dict, task_coverage: list[str], quality="clean", angle=0.0) -> dict:
    final_boxes = {key: add_bbox(box, page.width, page.height, angle) for key, box in page.boxes.items()}
    for field in ground_truth.get("fields", []):
        name = field.get("field_name")
        if name in final_boxes:
            field["evidence_bbox"] = final_boxes[name]
    return {
        "document_id": document_id,
        "document_type": document_type,
        "source_type": "synthetic",
        "split": LAYOUT_SPLITS[layout],
        "source_document": {"path_or_id": "", "sha256": ""},
        "task_coverage": task_coverage,
        "layout_family": layout,
        "vendor_pseudonym": vendor,
        "quality_tags": sorted({quality} | ({"slight_skew"} if angle else set())),
        "geography_context": {"country": "India"},
        "ground_truth": ground_truth,
        "annotation_metadata": {
            "validation_status": "verified",
            "annotator_id": f"synthetic_generator_v{SCRIPT_VERSION}",
            "adjudication_notes": "Exact labels generated from the structured synthetic source record and checked by automated schema/content validation. Synthetic only; not real SME evidence.",
        },
    }


def load_factors(root: Path) -> dict[str, dict]:
    path = root / "knowledge_base" / "emission_factors" / "GREENLEDGER_V1_FACTOR_CATALOGUE.csv"
    factors = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("normalized_activity") == "purchased_electricity" and row.get("verification_status") == "VERIFIED_CO2_ONLY_SELECTED_REFERENCE":
                factors[row["applicable_year"]] = row
    for year in ("FY2024-25", "FY2025-26"):
        if year not in factors:
            raise RuntimeError(f"Required CO2-only reference missing from factor catalogue: {year}")
    return factors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/synthetic/greenledger_v0_1_1_partial", help="Output directory, relative to repo root by default")
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output}")
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise SystemExit(f"Refusing to reuse existing staging directory: {staging}")
    factors = load_factors(root)
    rng = random.Random(args.seed)
    staging.mkdir(parents=True)
    records: list[dict] = []
    counts_by_split: dict[str, dict[str, int]] = {kind: {split: 0 for split in ("train", "validation", "test")} for kind in COUNTS}

    for kind, count in COUNTS.items():
        (staging / "documents" / kind).mkdir(parents=True)
        for i in range(count):
            local_rng = random.Random(rng.getrandbits(64))
            if kind == "electricity":
                record, image = make_electricity(i, local_rng, factors)
            elif kind == "diesel":
                record, image = make_diesel(i, local_rng)
            else:
                record, image = make_lpg(i, local_rng)
            layout = record["layout_family"]
            split = LAYOUT_SPLITS[layout]
            records.append(record)
            counts_by_split[kind][split] += 1
            image = image.convert("RGB")
            filename = f"{record['document_id']}.png"
            document_path = staging / "documents" / kind / filename
            image.save(document_path, format="PNG", optimize=True)
            record["source_document"]["path_or_id"] = document_path.relative_to(staging).as_posix()
            record["source_document"]["sha256"] = sha256_file(document_path)
            if record["ground_truth"].get("ocr", {}).get("transcription") is None:
                raise AssertionError("Synthetic record has no OCR transcription")

    annotations = staging / "annotations.jsonl"
    with annotations.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "dataset_id": "greenledger_synthetic_v0_1_1_partial",
        "synthetic_only": True,
        "generator_version": SCRIPT_VERSION,
        "seed": args.seed,
        "python_version": __import__("platform").python_version(),
        "pillow_version": __import__("PIL").__version__,
        "annotation_schema": "data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json",
        "annotation_schema_version": "0.3",
        "proposed_total_from_spec": 800,
        "generated_total": len(records),
        "generated_counts": {kind: COUNTS[kind] for kind in COUNTS},
        "generated_counts_by_split": counts_by_split,
        "not_generated": {"purchased_materials": 160, "selected_transport": 120},
        "not_generated_reason": "Exact v1 material/transport subsets and category/boundary rules are not finalized.",
        "co2e_ground_truth_count": 0,
        "factor_handling": "This release contains no expected CO2e values. Its LPG records do not establish combustion, boundary, or commercial/institutional stationary-source context required by the conditional LPG catalogue factor; these records retain unresolved factor statuses.",
        "currency_scope": "India-focused synthetic documents use INR display variants; no cross-geography factors are implied.",
        "counts_by_document_type": {
            "electricity_bill": 200,
            "diesel_fuel_invoice": 160,
            "lpg_receipt": 160,
        },
        "counts_by_quality_tag": {},
        "limitations": [
            "Synthetic documents do not establish real SME performance.",
            "Materials and transport are omitted pending scope decisions.",
            "No CO2e calculation target exists in this partial release.",
            "Layout-family splits are controlled; this is not a random population sample.",
        ],
    }
    for record in records:
        for tag in record["quality_tags"]:
            manifest["counts_by_quality_tag"][tag] = manifest["counts_by_quality_tag"].get(tag, 0) + 1
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readme = """# GreenLedger synthetic v0.1.1 (partial)

This directory contains explicitly synthetic electricity, diesel, and LPG documents with one exact annotation record per image. These are controlled document-understanding samples, not real SME records or empirical findings. No CO2e result is included.

- Images: `documents/{electricity,diesel,lpg}/`
- Ground truth: `annotations.jsonl` (one JSON record per image)
- Counts, splits, seed, dependencies, and limitations: `manifest.json`
- Rebuild: `python scripts/generate_synthetic_benchmark.py` (requires Pillow 12.3.0)

The proposed benchmark allocation remains 800 documents. This partial release contains 520; 160 material and 120 transport documents are withheld until the exact approved subsets and category/boundary rules are decided. The release uses held-out layout families for validation and test. Split labels are stored in each record and are derived from `layout_family`: A-E train, F validation, G-H test.

Electricity annotations retain the verified CEA V22.0 grid-average CO2-only source record and mark CO2e as non-calculable. Diesel and LPG have unresolved factor statuses. Factor status is not a numerical result; do not treat CO2-only values as CO2e.
"""
    (staging / "README.md").write_text(readme, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(output)
    print(json.dumps({"output": str(output), "generated_total": len(records), "counts_by_type": COUNTS, "split_counts": counts_by_split}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
