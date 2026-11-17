# Real SME Validation Specification

This specification defines the future real-world validation layer for GreenLedger. It is intentionally small and realistic for a final-year research project.

## 1. Objective

The real-SME validation set is used to answer one practical question: does the GreenLedger workflow still work on realistic SME invoices and bills when the vendor format, OCR noise, and accounting conventions are messy?

This dataset is not used for early model development. It is used to test external validity.

## 2. Target range

Minimum viable target:
- 60 documents total
- across 10 SMEs or small business units
- spread across the v1 document categories

Ideal target:
- 150–200 documents total
- across 20–30 SMEs
- with enough variety to assess vendor-template drift and document noise

## 3. Recommended distribution

A realistic distribution for v1 is:
- electricity bills: 15–20%
- diesel fuel receipts/invoices: 20–25%
- LPG receipts/invoices: 15–20%
- purchased-material invoices: 20–25%
- transport/freight bills: 15–20%

The exact distribution should reflect actual SME availability rather than a perfectly balanced theoretical sample.

## 4. Anonymization requirements

All real SME data must be anonymized before use in the repository. Required steps:
- replace or redact names, email addresses, phone numbers, account numbers, GST or tax identifiers, and payment references
- remove customer addresses and supplier addresses where possible
- crop or redact any visually identifying logos or signatures not required for the extraction task
- replace exact amounts with values retained only if needed for the ground truth record
- store the deidentified dataset separately from the participant consent file

## 5. Consent and data-use requirements

Real SME documents should only be collected with:
- explicit informed consent
- a clear explanation of research use
- a statement that the data will be anonymized and limited to the project
- a commitment that the data will not be publicly redistributed without approval
- a clear description of whether the data will be used only for validation or later benchmark construction

## 6. Ground-truth annotation workflow

Each real SME document should undergo:
- document-level classification by a reviewer,
- field-level extraction review,
- normalization to canonical GreenLedger activity and unit,
- factor lookup and CO2e calculation review,
- final validation status assigned by a second reviewer when uncertainty is high

Documents with ambiguity should be marked:
- uncertain
- pending review
- rejected for evaluation if the accounting interpretation remains unresolved

## 7. Double-review requirement

A second review is recommended for:
- all documents with uncertain activity mapping,
- all documents requiring a manual decision on material type or transport category,
- all final CO2e records that are used in evaluation metrics

This reduces the chance that a minor billing ambiguity becomes a false benchmark result.

## 8. Privacy safeguards

To protect the SMEs:
- no raw document images should be placed in the public repository
- only deidentified benchmark entries should remain in the project workspace
- metadata should be stored separately from the document files
- all annotations should store only the minimal fields needed for research

## 9. Minimal viable benchmark acceptance criteria

A real SME document should be used in validation only if:
- the activity is within the v1 supported scope,
- the relevant fields are extractable or can be verified,
- the final quantity can be normalized to a canonical unit,
- an authoritative factor can be identified,
- a human reviewer can confirm the interpretation without guessing

If any of these are not true, the document should be excluded from the benchmark or flagged as uncertain.
