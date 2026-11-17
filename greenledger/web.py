"""Small dependency-free local web interface for GreenLedger's first baseline."""

import html
import json
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from greenledger.core import ValidationError, evaluate_submission, load_activities, make_json_trace
from greenledger.field_extraction import extract_carbon_fields
from greenledger.ocr import get_ocr_runtime_status, recognize_upload


MAX_REQUEST_BYTES = 8 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

OCR_PREVIEW_SCRIPT = r"""
document.addEventListener('DOMContentLoaded', function () {
  const form = document.querySelector('form[action="/evaluate"]');
  const button = document.getElementById('read-ocr');
  const panel = document.getElementById('ocr-preview');
  const fileInput = document.getElementById('document');
  if (!form || !button || !panel || !fileInput) return;
  button.addEventListener('click', async function () {
    panel.hidden = false;
    panel.replaceChildren();
    const heading = document.createElement('h2');
    heading.textContent = 'OCR transcript';
    const status = document.createElement('p');
    status.className = 'notice';
      const transcript = document.createElement('pre');
      transcript.className = 'trace';
    const candidates = document.createElement('pre');
    candidates.className = 'trace';
    const applyButton = document.createElement('button');
    applyButton.type = 'button';
    applyButton.textContent = 'Copy suggestions into fields';
    applyButton.hidden = true;
    const meta = document.createElement('p');
    meta.className = 'hint';
    panel.append(heading, status, meta, transcript);
    if (!fileInput.files.length) {
      status.textContent = 'Choose a PDF or image first.';
      return;
    }
    status.textContent = 'Running local OCR…';
    button.disabled = true;
    try {
      const response = await fetch('/ocr', { method: 'POST', body: new FormData(form) });
      const result = await response.json();
      status.textContent = result.warning || result.status || 'OCR finished.';
      meta.textContent = [result.engine, result.engine_version,
        result.page_count_processed ? result.page_count_processed + ' page(s)' : '',
        result.latency_seconds ? result.latency_seconds + ' s' : '',
        result.sha256 ? 'source SHA256 ' + result.sha256 : ''].filter(Boolean).join(' · ');
      transcript.textContent = result.transcription || 'No transcript available.';
      if (result.field_candidates) {
        const candidateHeading = document.createElement('h3');
        candidateHeading.textContent = 'Unconfirmed rule-based field suggestions';
        candidates.textContent = JSON.stringify(result.field_candidates, null, 2);
        applyButton.hidden = false;
        applyButton.addEventListener('click', function () {
          const fields = result.field_candidates;
          const setValue = function (name, value) {
            const input = form.elements.namedItem(name);
            if (input && value !== null && value !== undefined) input.value = String(value);
          };
          setValue('activity', fields.activity && fields.activity.value);
          setValue('quantity', fields.quantity && fields.quantity.value);
          setValue('unit', fields.unit && fields.unit.raw_text);
          setValue('document_date', fields.invoice_date && fields.invoice_date.value);
          setValue('supplier', fields.supplier_name && fields.supplier_name.value);
          const confirmation = form.elements.namedItem('fields_confirmed');
          if (confirmation) confirmation.checked = false;
          status.textContent = 'Suggestions copied. Review and correct them against the document; confirmation remains unchecked.';
        });
        panel.append(candidateHeading, candidates, applyButton);
      }
      if (result.truncated) {
        const note = document.createElement('p');
        note.className = 'hint';
        note.textContent = 'Only the first ' + result.page_limit + ' pages were read. Review the remaining pages manually.';
        panel.append(note);
      }
    } catch (error) {
      status.textContent = 'The OCR preview request failed. Check the local server and try again.';
    } finally {
      button.disabled = false;
    }
  });
});
"""


PAGE_CSS = """
<style>
:root{--ink:#172a24;--muted:#61746c;--green:#176b4b;--green2:#e9f4ed;--line:#dce6df;--paper:#f5f8f5;--amber:#fff4d7;--red:#9b392c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Segoe UI,Arial,sans-serif}
header{background:#123d2d;color:white;padding:24px max(24px,calc((100% - 1040px)/2));display:flex;align-items:center;justify-content:space-between}
.brand{font-size:24px;font-weight:700;letter-spacing:.2px}.badge{font-size:12px;border:1px solid #8ab69c;padding:5px 10px;border-radius:99px;color:#d5eee0}
main{max-width:1040px;margin:28px auto;padding:0 20px}.intro h1{font-size:30px;margin:0 0 4px}.intro p{color:var(--muted);margin:0 0 20px}
.notice{background:var(--amber);border:1px solid #ead79a;border-radius:10px;padding:12px 15px;margin:16px 0 20px}.grid{display:grid;grid-template-columns:1.08fr .92fr;gap:18px}
.card{background:white;border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:0 3px 14px #153b2810}.card h2{font-size:18px;margin:0 0 14px}.field{margin:0 0 14px}.field label,.label{display:block;font-weight:600;margin-bottom:5px}
input,select{width:100%;padding:10px 11px;border:1px solid #bdcdc2;border-radius:8px;font:inherit;background:white;color:var(--ink)}input[type=checkbox]{width:auto;margin-right:8px;transform:scale(1.1)}.hint{font-size:12px;color:var(--muted);margin-top:4px}
.contexts{border-top:1px solid var(--line);padding-top:12px;margin-top:14px}.contexts .field{margin-bottom:12px}.check{display:flex;align-items:flex-start;font-weight:500!important}.actions{display:flex;gap:10px;align-items:center;margin-top:18px}
button,.button{border:0;border-radius:8px;background:var(--green);color:white;font:600 15px Segoe UI,Arial;padding:11px 17px;cursor:pointer;text-decoration:none}.result{margin-top:20px}.status{padding:10px 12px;border-radius:8px;background:var(--green2);margin:10px 0}.status.warn{background:var(--amber)}.data{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px}.data div{padding:7px 0;border-bottom:1px solid #edf1ed}.k{font-size:12px;color:var(--muted)}.v{font-weight:600;overflow-wrap:anywhere}.trace{background:#f3f6f3;border-radius:8px;padding:12px;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:13px}
details{margin-top:12px}summary{cursor:pointer;font-weight:600}footer{text-align:center;color:var(--muted);padding:24px;font-size:12px}
@media(max-width:760px){.grid{grid-template-columns:1fr}header{padding:18px 20px}main{margin:18px auto}.data{grid-template-columns:1fr}}
</style>
"""


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def base_page(content, title="GreenLedger"):
    return "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{}</title>{}<script src='/app.js' defer></script></head><body><header><div class='brand'>GreenLedger</div><div class='badge'>Local research baseline</div></header><main>{}</main><footer>Local only · uploads are processed in memory and are not saved · no AI field extraction is active</footer></body></html>".format(esc(title), PAGE_CSS, content)


def render_form(error=None, selected=None):
    activities = load_activities()
    ocr_status = get_ocr_runtime_status()
    if ocr_status["available"]:
        ocr_notice = "Provisional local OCR baseline is available ({} {}). Its transcript is advisory; enter and verify every carbon field manually. No AI field extraction is active.".format(ocr_status["engine"], ocr_status["version"])
        understanding_label = "OCR transcript plus manual field entry"
        ocr_label = "No calibrated field confidence"
    else:
        ocr_notice = "OCR runtime is not installed in this Python environment. Uploaded values remain manual. A result is calculated only through an explicitly supported, matching factor path and required context."
        understanding_label = "Manual field entry"
        ocr_label = "Not available"
    selected = selected or {}
    def option_list(name, options):
        return "".join(
            "<option value='{}'{}>{}</option>".format(
                esc(value), " selected" if selected.get(name) == value else "", esc(label)
            )
            for value, label in options
        )

    choices = []
    for activity in activities:
        mark = " selected" if selected.get("activity") == activity["id"] else ""
        choices.append("<option value='{}'{}>{}</option>".format(esc(activity["id"]), mark, esc(activity["canonical_name"])))
    error_html = "<div class='notice' role='alert'>{}</div>".format(esc(error)) if error else ""
    content = """
    <section class="intro"><h1>Document to traceable carbon result</h1><p>Upload a bill or receipt, enter the values you have checked, then inspect the deterministic accounting trace.</p></section>
    <div class="notice"><strong>Current baseline:</strong> {ocr_notice}</div>
    {error}
    <form method="post" enctype="multipart/form-data" action="/evaluate">
      <div class="grid">
        <section class="card"><h2>Document and activity</h2>
          <div class="field"><label for="document">Document (PDF or image)</label><input id="document" name="document" type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"><div class="hint">Optional in this baseline. File is held in memory for this request and discarded.</div></div>
          <div class="field"><label for="activity">Activity</label><select id="activity" name="activity" required><option value="">Choose an activity</option>{choices}</select></div>
          <div class="field"><label for="quantity">Quantity (fuels/materials/electricity)</label><input id="quantity" name="quantity" inputmode="decimal" placeholder="e.g. 250" value="{quantity}"><div class="hint">For LPG, enter verified net LPG mass in kg. For materials, this is the exact material quantity. Freight uses its separate mass and distance fields below.</div></div>
          <div class="field"><label for="unit">Quantity unit</label><input id="unit" name="unit" placeholder="e.g. L, kg, kWh" value="{unit}"><div class="hint">A missing or unsupported unit is never guessed. Freight uses separate units below.</div></div>
          <div class="field"><label for="document_date">Document date or period (optional)</label><input id="document_date" name="document_date" placeholder="e.g. 2026-08" value="{date}"></div>
          <div class="field"><label for="supplier">Supplier (optional)</label><input id="supplier" name="supplier" value="{supplier}"></div>
          <div class="contexts"><div class="label">Accounting context required for classification</div>
            <div class="field"><label for="geography_code">Geography</label><select name="geography_code" id="geography_code">{geography_options}</select><div class="hint">Electricity requires India grid and FY2025-26 for the selected CEA CO₂ factor; road diesel and freight require India.</div></div>
            <div class="field"><label for="applicable_period">Electricity applicable period</label><select name="applicable_period" id="applicable_period">{period_options}</select></div>
            <div class="field"><label for="electricity_use">Electricity use</label><select name="electricity_use" id="electricity_use"><option value="unknown">Unknown / not applicable</option><option value="purchased_and_consumed"{electricity}>Purchased and consumed in company operations</option><option value="other">Other or not confirmed</option></select></div>
            <div class="field"><label for="combusted">Was the fuel actually combusted?</label><select name="combusted" id="combusted"><option value="unknown">Unknown / not applicable</option><option value="yes"{combusted}>Yes, confirmed</option><option value="no">No / purchase only</option></select></div>
            <div class="field"><label for="controlled">Does the company own or control the source?</label><select name="controlled" id="controlled"><option value="unknown">Unknown / not applicable</option><option value="yes"{controlled}>Yes, confirmed</option><option value="no">No / not confirmed</option></select></div>
            <div class="field"><label for="source_type">Fuel source</label><select name="source_type" id="source_type"><option value="unknown">Unknown / not applicable</option><option value="stationary"{stationary}>Stationary equipment or installation</option><option value="mobile"{mobile}>Mobile vehicle or equipment</option></select></div>
            <div class="field"><label for="vehicle_class">For road diesel: combustion vehicle context</label><select name="vehicle_class" id="vehicle_class"><option value="unknown">Unknown / not applicable</option><option value="ROAD_VEHICLE"{road_vehicle}>Road vehicle</option></select><div class="hint">The India diesel factor is for owned/controlled road-vehicle TTW combustion only; it does not cover stationary equipment.</div></div>
            <div class="field"><label for="commercial_institutional">For LPG: commercial/institutional stationary use?</label><select name="commercial_institutional" id="commercial_institutional"><option value="unknown">Unknown / not applicable</option><option value="yes"{commercial}>Yes, confirmed</option><option value="no">No / different source category</option></select><div class="hint">This specific context is required for the conditional IPCC LPG factor.</div></div>
            <div class="field"><label for="material_identity">For purchased materials: exact material identity</label><select name="material_identity" id="material_identity">{material_options}</select><div class="hint">Only PPC cement (CPWD row: 30% fly ash), steel rebar, or generic steel. “Steel” alone is ambiguous. Confirm the product against the invoice.</div></div>
            <div class="field"><label for="transport_scenario">For freight: business flow</label><select name="transport_scenario" id="transport_scenario"><option value="unknown">Unknown / not applicable</option><option value="upstream_purchased"{upstream}>Company purchased upstream transport service</option><option value="downstream_sold_product"{downstream}>Third party carried sold products after sale; company did not purchase service</option><option value="company_controlled"{company_transport}>Company owned/controlled vehicle</option></select></div>
            <div class="field"><label for="transport_mode">For freight: transport mode</label><select name="transport_mode" id="transport_mode">{mode_options}</select></div>
            <div class="field"><label for="transport_vehicle_class">For freight: vehicle GVW class</label><select name="transport_vehicle_class" id="transport_vehicle_class">{vehicle_options}</select><div class="hint">Select only the vehicle class evidenced for the shipment. No default class is selected.</div></div>
            <div class="field"><label for="shipment_mass">For freight: shipment mass</label><input id="shipment_mass" name="shipment_mass" inputmode="decimal" value="{shipment_mass}" placeholder="e.g. 2500"></div>
            <div class="field"><label for="mass_unit">Shipment mass unit</label><select name="mass_unit" id="mass_unit">{mass_unit_options}</select></div>
            <div class="field"><label for="distance">For freight: reviewed road distance</label><input id="distance" name="distance" inputmode="decimal" value="{distance}" placeholder="e.g. 120"></div>
            <div class="field"><label for="distance_unit">Distance unit</label><select name="distance_unit" id="distance_unit">{distance_unit_options}</select><div class="hint">Enter a documented/reviewed shortest-feasible road distance; GreenLedger does not infer distance or apply an unconfirmed route uplift.</div></div>
          </div>
          <div class="field"><label class="check"><input type="checkbox" name="fields_confirmed" value="yes"{confirmed}>I checked the activity, material identity or freight inputs, quantities, units, and accounting context against the source evidence.</label></div>
          <div class="actions"><button type="button" id="read-ocr">Read OCR transcript</button><button type="submit">Evaluate trace</button></div>
        </section>
        <aside class="card"><h2>What this version does</h2><div class="data">
          <div><div class="k">Document understanding</div><div class="v">{understanding_label}</div></div>
          <div><div class="k">Carbon-field confidence</div><div class="v">{ocr_label}</div></div>
          <div><div class="k">Scope mapping</div><div class="v">Existing approved rules with abstention</div></div>
          <div><div class="k">CO₂e calculation</div><div class="v">Deterministic, gated by factor eligibility</div></div>
          <div><div class="k">Current CO₂-only case</div><div class="v">India location-based electricity · CEA V22 · FY2025-26</div></div>
          <div><div class="k">Current CO₂e cases</div><div class="v">Conditional LPG; India road diesel; the three selected CPWD material references; India road freight</div></div>
          <div><div class="k">Still unresolved</div><div class="v">Electricity CO₂e; other LPG/diesel contexts; other materials and transport modes</div></div>
        </div><p class="hint">CEA electricity produces a separately labeled CO₂ result only and remains ineligible for CO₂e. Freight factors are WTW tonne-km intensities; road-diesel TTW litres use a separate factor. Materials and freight results are limited to the explicitly enabled v1 identities/classes and require all context plus human confirmation.</p></aside>
      </div>
    </form>
    <section class="card result" id="ocr-preview" aria-live="polite" hidden></section>
    """.format(
        error=error_html, ocr_notice=esc(ocr_notice), understanding_label=esc(understanding_label), ocr_label=esc(ocr_label),
        choices="".join(choices), quantity=esc(selected.get("quantity", "")), unit=esc(selected.get("unit", "")),
        geography_options="<option value='unknown'>Unknown / not applicable</option>" + option_list("geography_code", [("INDIA_GRID", "India grid"), ("INDIA", "India")]),
        period_options="<option value='unknown'>Unknown / not applicable</option>" + option_list("applicable_period", [("FY2025-26", "FY2025-26")]),
        material_options="<option value=''>Choose exact material</option>" + option_list("material_identity", [("ppc_cement", "PPC cement · CPWD 30% fly-ash reference"), ("steel_rebar", "Steel rebar"), ("generic_steel", "Generic steel")]),
        mode_options="<option value='unknown'>Unknown / not applicable</option>" + option_list("transport_mode", [("road", "India road freight")]),
        vehicle_options="<option value=''>Choose evidenced vehicle class</option>" + option_list("transport_vehicle_class", [("ROAD_GVW_LT_3_5_T", "GVW <3.5 t"), ("ROAD_GVW_3_5_T", "GVW 3–5 t"), ("ROAD_GVW_5_12_T", "GVW 5–12 t"), ("ROAD_GVW_12_20_T", "GVW 12–20 t"), ("ROAD_GVW_20_30_T", "GVW 20–30 t"), ("ROAD_GVW_30_50_T", "GVW 30–50 t"), ("ROAD_TRACTOR_TRAILER_GVW_30_60_T", "GVW 30–60 t tractor-trailer")]),
        mass_unit_options="<option value=''>Choose unit</option>" + option_list("mass_unit", [("kg", "kg"), ("tonne", "tonne")]),
        distance_unit_options="<option value=''>Choose unit</option>" + option_list("distance_unit", [("km", "km"), ("m", "m")]),
        shipment_mass=esc(selected.get("shipment_mass", "")), distance=esc(selected.get("distance", "")),
        date=esc(selected.get("document_date", "")), supplier=esc(selected.get("supplier", "")),
        electricity=" selected" if selected.get("electricity_use") == "purchased_and_consumed" else "",
        combusted=" selected" if selected.get("combusted") == "yes" else "",
        controlled=" selected" if selected.get("controlled") == "yes" else "",
        stationary=" selected" if selected.get("source_type") == "stationary" else "",
        mobile=" selected" if selected.get("source_type") == "mobile" else "",
        road_vehicle=" selected" if selected.get("vehicle_class") == "ROAD_VEHICLE" else "",
        commercial=" selected" if selected.get("commercial_institutional") == "yes" else "",
        upstream=" selected" if selected.get("transport_scenario") == "upstream_purchased" else "",
        downstream=" selected" if selected.get("transport_scenario") == "downstream_sold_product" else "",
        company_transport=" selected" if selected.get("transport_scenario") == "company_controlled" else "",
        confirmed=" checked" if selected.get("fields_confirmed") == "yes" else "",
    )
    return base_page(content, "GreenLedger · local baseline")


def render_result(result, document_name, ocr_result=None):
    factor = result["factor"]
    def row(label, value):
        return "<div><div class='k'>{}</div><div class='v'>{}</div></div>".format(esc(label), esc(value if value not in (None, "") else "Unresolved"))

    status = "Needs human review" if result["review_required"] else "Calculation trace ready"
    notice_class = "status warn" if result["review_required"] else "status"
    lines = [
        row("Uploaded file", document_name or "No file uploaded"),
        row("Document type", result["document_type"] + " (user selected activity; not model-classified)"),
        row("Date or billing period entered", result["document_date"]),
        row("Supplier entered", result["supplier"]),
        row("Activity", result["activity"]["canonical_name"] + " · " + result["activity"]["id"]),
    ]
    if result["material_identity"]:
        lines.append(row("Confirmed material identity", result["material_identity"]))
    if result["transport_data"]:
        freight = result["transport_data"]
        lines.extend([
            row("Transport mode", result["transport_mode"]),
            row("Vehicle GVW class", result["transport_vehicle_class"]),
            row("Shipment mass input", "{} {}".format(freight["shipment_mass_input"], freight["mass_unit_input"]) if freight["shipment_mass_input"] is not None else None),
            row("Normalized shipment mass", "{} tonnes".format(freight["shipment_mass_tonnes"]) if freight["shipment_mass_tonnes"] is not None else None),
            row("Distance input", "{} {}".format(freight["distance_input"], freight["distance_unit_input"]) if freight["distance_input"] is not None else None),
            row("Normalized distance", "{} km".format(freight["distance_km"]) if freight["distance_km"] is not None else None),
            row("Derived activity quantity", "{} tonne-km".format(freight["tonne_km"]) if freight["tonne_km"] is not None else None),
            row("Unit conversion trace", result["conversion_trace"]),
        ])
    else:
        lines.extend([
            row("Entered quantity", "{} {}".format(result["quantity"], result["unit"])),
            row("Normalized quantity", "{} {}".format(result["normalized_quantity"], result["canonical_unit"]) if result["normalized_quantity"] is not None else "Unresolved"),
            row("Unit conversion trace", result["conversion_trace"]),
        ])
    lines.extend([
        row("Scope", result["scope"]),
        row("Scope category", result["scope_category"]),
        row("Confidence", result["confidence"]),
        row("Human field verification", result["human_verification"]),
    ])
    if factor:
        lines.extend([
            row("Factor", factor["factor_id"]),
            row("Factor value", "{} {}".format(factor["factor_value"], factor["factor_unit"])),
            row("Source", factor["source"]),
            row("Source version / year", factor["source_version"] + " · " + factor["applicable_year"]),
            row("Geography", factor["geography"]),
            row("Source URL", factor["source_url"]),
            row("Calculated CO₂e", "{} kg CO₂e".format(result["co2e"]) if result["co2e"] is not None else "Not calculated"),
        ])
    else:
        lines.extend([row("CO₂e factor status", result["factor_status"]), row("CO₂e", "Not calculated")])
    if result["co2_kg"] is not None:
        co2_factor = result["co2_factor"]
        lines.extend([
            row("CO₂-only factor", co2_factor["factor_id"]),
            row("CO₂-only factor value", "{} {}".format(co2_factor["factor_value"], co2_factor["factor_unit"])),
            row("Gas basis", result["co2_gas_basis"]),
            row("CO₂ factor source", co2_factor["source"]),
            row("CO₂ factor source version / year", co2_factor["source_version"] + " · " + co2_factor["applicable_year"]),
            row("CO₂ factor geography", co2_factor["geography"]),
            row("CO₂ factor source URL", co2_factor["source_url"]),
            row("Calculated CO₂", "{:.2f} kgCO2".format(result["co2_kg"])),
        ])
    else:
        lines.extend([row("CO₂ result status", result["co2_factor_status"]), row("CO₂", "Not calculated")])
    review = "<ul>{}</ul>".format("".join("<li>{}</li>".format(esc(reason)) for reason in result["review_reasons"])) if result["review_reasons"] else "<p>No unresolved review reasons recorded.</p>"
    trace = make_json_trace(result, document_name, ocr_result)
    ocr_section = ""
    if ocr_result:
        ocr_warning = "<div class='notice'>{}</div>".format(esc(ocr_result.get("warning"))) if ocr_result.get("warning") else ""
        page_text = "".join("<h3>Page {}</h3><pre class='trace'>{}</pre>".format(esc(page.get("page")), esc(page.get("text", ""))) for page in ocr_result.get("pages", []))
        truncated = "<p class='hint'>Only the first {} pages were processed; review the remaining pages manually.</p>".format(esc(ocr_result.get("page_limit"))) if ocr_result.get("truncated") else ""
        ocr_meta = "{} · {} · {} page(s) · {} s · source SHA256 {}".format(
            ocr_result.get("engine", "OCR unavailable"), ocr_result.get("engine_version", ""),
            ocr_result.get("page_count_processed", 0), ocr_result.get("latency_seconds", "—"),
            ocr_result.get("sha256", "not available"),
        )
        field_candidates = ocr_result.get("field_candidates")
        candidate_block = ""
        if field_candidates:
            candidate_warning = "<div class='notice'>Rule-based suggestions are unconfirmed. Review all fields and accounting context; this extractor does not choose a factor or calculate CO₂e.</div>"
            candidate_json = esc(json.dumps(field_candidates, indent=2, ensure_ascii=False))
            candidate_block = "<h3>Unconfirmed rule-based field suggestions</h3>{}<pre class='trace'>{}</pre>".format(candidate_warning, candidate_json)
        ocr_section = "<section class='card result'><h2>OCR transcript and field candidates</h2><p>{}</p>{}{}{}{}<p class='hint'>OCR and rule scores are not calibrated for carbon-field correctness. Entered quantities, units, activity, and context still require human verification.</p></section>".format(esc(ocr_meta), ocr_warning, page_text or "<p>No transcript available.</p>", truncated, candidate_block)
    calculation_display = result["co2_calculation_trace"] or result["calculation_trace"] or "No CO₂ or CO₂e calculation performed: required context or eligible factor is unavailable."
    content = "<section class='intro'><h1>Evaluation trace</h1><p>OCR, when available, supplies a transcript only. Carbon fields remain manual and the accounting rules and calculation are deterministic. CO₂ and CO₂e results use separate factor paths and labels.</p></section><section class='card result'><div class='{}'><strong>{}</strong></div><div class='data'>{}</div><h2>Calculation trace</h2><div class='trace'>{}</div><details open><summary>Human review reasons</summary>{}</details><details><summary>Complete JSON trace</summary><pre class='trace'>{}</pre></details><div class='actions'><a class='button' href='/'>Evaluate another document</a></div></section>{}".format(notice_class, esc(status), "".join(lines), esc(calculation_display), review, esc(json.dumps(trace, indent=2, ensure_ascii=False)), ocr_section)
    return base_page(content, "GreenLedger · evaluation trace")


def parse_request(handler):
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        raise ValidationError("The form submission was empty.")
    if content_length > MAX_REQUEST_BYTES:
        raise ValidationError("The upload is larger than the 8 MB limit for this local baseline.")
    body = handler.rfile.read(content_length)
    content_type = handler.headers.get("Content-Type", "")
    if content_type.startswith("multipart/form-data"):
        message = BytesParser(policy=policy.default).parsebytes(
            ("Content-Type: {}\r\nMIME-Version: 1.0\r\n\r\n".format(content_type)).encode("ascii") + body
        )
        fields, document_name, document_content = {}, None, None
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                if payload:
                    clean_name = filename.replace("\\", "/").split("/")[-1]
                    extension = "." + clean_name.rsplit(".", 1)[-1].casefold() if "." in clean_name else ""
                    if extension not in ALLOWED_EXTENSIONS:
                        raise ValidationError("Upload a PDF or a supported image file (PNG, JPG, TIFF).")
                    document_name = clean_name[:180]
                    document_content = payload
                continue
            if name:
                fields[name] = payload.decode("utf-8", errors="replace")
        return fields, document_name, document_content
    if content_type.startswith("application/x-www-form-urlencoded"):
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items()}, None, None
    raise ValidationError("Submit the form using the page controls.")


class GreenLedgerHandler(BaseHTTPRequestHandler):
    server_version = "GreenLedgerLocal/0.1"

    def _send(self, content, status=200):
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_script(self):
        payload = OCR_PREVIEW_SCRIPT.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/app.js":
            self._send_script()
            return
        if self.path not in ("/", "/index.html"):
            self._send(base_page("<section class='card'><h1>Page not found</h1><a href='/'>Return to GreenLedger</a></section>"), 404)
            return
        self._send(render_form())

    def do_POST(self):
        if self.path == "/ocr":
            try:
                _fields, document_name, document_content = parse_request(self)
                result = recognize_upload(document_content, document_name) if document_content else {
                    "status": "NO_DOCUMENT",
                    "warning": "Select a document before requesting an OCR transcript.",
                    "transcription": "",
                    "pages": [],
                }
                if result and result.get("transcription"):
                    result["field_candidates"] = extract_carbon_fields(result["transcription"])
                self._send_json(result)
            except (ValidationError, ValueError) as error:
                self._send_json({"status": "INPUT_INVALID", "warning": str(error), "transcription": ""}, 400)
            except Exception:
                self._send_json({"status": "OCR_FAILED", "warning": "The upload could not be processed. Check the file and try again.", "transcription": ""}, 500)
            return
        if self.path != "/evaluate":
            self._send(base_page("<section class='card'><h1>Page not found</h1><a href='/'>Return to GreenLedger</a></section>"), 404)
            return
        fields = {}
        try:
            fields, document_name, document_content = parse_request(self)
            ocr_result = recognize_upload(document_content, document_name) if document_content else None
            if ocr_result and ocr_result.get("transcription"):
                ocr_result["field_candidates"] = extract_carbon_fields(ocr_result["transcription"])
            result = evaluate_submission(fields)
            self._send(render_result(result, document_name, ocr_result))
        except (ValidationError, ValueError) as error:
            self._send(render_form(str(error), fields), 400)
        except Exception:
            # Avoid reflecting server internals or submitted document contents to the browser.
            self._send(render_form("The request could not be processed. Check the local catalogue files and form values.", fields), 500)

    def log_message(self, fmt, *args):
        # Keep local terminal logs minimal; submitted values and document contents are not logged.
        print("GreenLedger local server: " + (fmt % args))


def run(host="127.0.0.1", port=8000):
    server = HTTPServer((host, port), GreenLedgerHandler)
    print("GreenLedger local baseline running at http://{}:{}/".format(host, port))
    ocr_status = get_ocr_runtime_status()
    print("Local OCR: {}. AI field extraction is not active.".format("{} {}".format(ocr_status.get("engine"), ocr_status.get("version")) if ocr_status["available"] else "unavailable in this Python environment"))
    print("Press Ctrl+C to stop. Uploads are processed in memory and not saved.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GreenLedger.")
    finally:
        server.server_close()
