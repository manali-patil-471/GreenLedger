GreenLedger - Real SME data acquisition and validation plan
Created: 2026-08-18

Objective
Collect a small, anonymized validation dataset from real SMEs for human-verified evaluation of extraction and emission calculation pipelines. This dataset is for validation only and will be collected under explicit consent with strict anonymization.

1) Document types to collect
- Electricity bills (monthly commercial/industrial accounts)
- Fuel invoices / receipts (diesel, LPG)
- Purchase invoices for selected materials (paper, steel, packaging)
- Transport/freight invoices or delivery notes (preferably with route/distance or mass data)

2) Approximate target quantity (initial realistic pilot)
- Aim for 5–15 SMEs across sectors (retail, manufacturing, hospitality, services)
- Per SME: 10–30 documents (mix across categories), total initial validation set: ~100–300 documents
Rationale: realistic small, human-annotated validation set that is achievable with outreach and consent; not thousands.

3) Anonymization requirements
- Redact or pseudonymize directly identifying fields: company registration numbers, tax IDs, bank account numbers, full legal names if requested, customer names, personal addresses of individuals.
- Keep contextual fields needed for emissions calculations: meter identifiers (if necessary) and non-identifying location info (e.g., city/region but not full personal address) — seek consent for any fields that could re-identify.
- Strip embedded metadata from scanned files (EXIF) that might contain device or location information.

4) Sensitive fields to redact
- Personal names (unless SME consents to include business name)
- Email addresses and phone numbers (unless needed and explicitly consented)
- Bank/IBAN/account numbers, tax ID numbers, credit card numbers
- Any employee personal data on receipts

5) Suggested outreach message (short template)
Subject: Invitation to participate in GreenLedger SME pilot (voluntary — data will be anonymized)

Dear [SME contact],

GreenLedger is a research project from [University / Team]. We are building a system to help SMEs measure and report their carbon footprint more easily. We seek a small, anonymized sample of your business documents (e.g., electricity bills, fuel invoices, purchase invoices) to validate our extraction and calculation methods.

Participation is voluntary. Documents will be anonymized, and any sensitive fields will be redacted. We will ask you to sign a consent form describing permitted uses (research, model validation) and retention limits. Participants will receive a short validation report showing how the extracted data maps to emissions estimates for review.

If you are interested, please reply to this message and we will provide details about consent and secure transfer options.

Thank you,
[Contact person, affiliation, contact details]

6) Consent and data-use considerations
- Use a written consent form specifying: purpose, types of documents requested, retention period (e.g., 12 months), anonymization measures, who will have access, and right to withdraw (data deletion on request).
- Prefer secure transfer channels (encrypted email, secure upload portal). Avoid public cloud links without access controls.
- Log access and maintain an audit trail of who accessed raw vs anonymized data.

7) Annotation and ground-truthing process
- Use a controlled annotation tool (e.g., label-studio, or spreadsheet with defined fields) and the current `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json` contract, adapted only through documented schema changes. Synthetic values and labels must never be copied as if they were real SME ground truth.
- Each document should be annotated by one trained annotator and reviewed by a second annotator for critical fields (e.g., total_kwh, fuel quantity, transport distance). Resolve disagreements via adjudication.
- Record provenance metadata: original filename (hashed), upload date, consent ID, annotator IDs, and redaction summary.

8) Privacy, retention and legal
- Store raw documents in an encrypted, access-controlled location. Store only anonymized derivatives in the working dataset.
- Retention: keep raw data only as long as necessary for annotation and validation (recommendation: up to 12 months), then delete raw copies unless explicit consent allows longer storage.
- Consult institutional legal/ethics offices if this data collection involves personal data or requires IRB/ethics approval.

9) Annotation scale and timeline
- Pilot: collect from 5 SMEs, annotate ~100 documents over 4–8 weeks.
- Evaluate extraction accuracy and revise schema and outreach as needed before scaling.

Notes
- Do not fabricate sample documents; only accept documents with explicit SME consent.
- Prioritize SMEs that are willing to provide clear copies and minimal sensitive personal data to reduce redaction effort.
