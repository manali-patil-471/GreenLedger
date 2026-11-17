# CORD v2 Usage Assessment for GreenLedger

## A. What CORD v2 actually provides

CORD v2 is a public receipt OCR and semantic parsing dataset from Naver Clova.
The local metadata and a downloaded parquet file show the following:

- Official dataset source: https://huggingface.co/datasets/naver-clova-ix/cord-v2
- Dataset type: generic receipt/document understanding dataset
- Splits declared in the official dataset metadata: train=800, validation=100, test=100
- Total declared dataset size in the HF metadata: approx. 2.3 GB download, approx. 2.3 GB dataset size, and ~4.6 GB total size in bytes as reported by the repository metadata
- Local parquet schema (observed from the available test file):
  - image: struct<bytes: binary, path: string>
  - ground_truth: string
- Each example is a receipt image plus a JSON string annotation payload.
- The annotation payload includes keys such as:
  - gt_parse
  - meta
  - valid_line
  - roi
  - repeating_symbol
  - dontcare
- The `valid_line` entries contain OCR words, quad coordinates, row IDs, and categories such as `menu.num`, `menu.nm`, `sub_total`, and `total`.
- The `meta` block includes version, split, and image size.
- The image is not an external URL in the locally available parquet file; it is embedded as binary bytes inside the row itself.

This is a strong OCR and structured receipt parsing dataset, but it is not a carbon accounting or emissions dataset.

## B. What GreenLedger can use from it

CORD is useful only for generic document-understanding support, especially if GreenLedger later needs a receipt parser or document-layout baseline.

Potential GreenLedger uses:

- understanding generic receipt layout patterns
- establishing a baseline OCR + semantic parsing pipeline on receipt-like documents
- learning how business receipts represent totals, dates, line items, and table structures
- extracting non-carbon document structure when GreenLedger is receiving purchase receipts or invoice-like documents

This is most relevant only if GreenLedger later needs a generic receipt OCR/field extraction foundation.

## C. What CORD does NOT provide for GreenLedger

CORD does not provide the information GreenLedger actually needs for carbon accounting.

It does not provide:

- electricity meter readings or billing periods
- fuel quantity, type, or unit conversion truth
- LPG purchase data or gas-cylinder mass/energy details
- purchase-material quantities with material type and supplier category
- transport activity data such as distance, vehicle class, payload, route, or fuel used
- emissions coefficients or emission-factor sources
- accounting category mappings to GHG Protocol scope/category classes
- real SME carbon ground truth

In other words, CORD helps with document layout recognition. It does not help GreenLedger answer the actual carbon question: what activity occurred, what accounting category it belongs to, and which emission factor applies.

## D. Whether the full multi-GB download is justified

At this stage, no.

The current evidence shows that CORD is valuable as a generic receipt understanding corpus, but GreenLedger's immediate scope is to establish carbon-specific data foundations, not to build a generic receipt parser yet.

The full CORD v2 download is not justified now because:

- it is a multi-GB dataset that is unrelated to carbon-accounting labels
- it does not contain the GreenLedger-required activity categories
- GreenLedger's immediate needs are better served by a minimalist, explicit data plan for: public generic invoice/receipt documents, synthetic benchmark documents, and real SME validation documents
- the actual GreenLedger research problem is not generic receipt parsing alone; it is activity extraction + emission-factor mapping + verification

Therefore, downloading the full multi-GB CORD payload is not a high-priority step before finalizing the minimum GreenLedger data requirements and acquisition plan.

## E. Recommended subset, if applicable

If a generic receipt-baseline experiment is needed later, a much smaller and more defensible subset would be preferred, such as:

- a small sample of representative receipt pages from the test split only
- a few dozen to a few hundred examples for OCR/layout sanity checks
- a research-specific subset selected to cover vendor layout variability, table layouts, and line-item structures

This should be treated as a document-understanding auxiliary dataset, not as a carbon dataset.

At present, the one local parquet test file and the public dataset metadata already show enough to confirm the real value and the limits of CORD for GreenLedger. There is no need to blindly fetch the remaining LFS files now.

## F. Exact next download action, if any

Recommended next action: No additional CORD download right now.

Instead:

1. Keep the current CORD metadata and one local parquet file as evidence of the dataset's real scope.
2. Proceed with FATURA verification and extraction as completed data-source evidence for generic invoice documents.
3. Continue building the GreenLedger-specific data plan around carbon-accounting sources and actual required activity data rather than downloading a large generic receipt dataset prematurely.

If a future document-understanding baseline is required, the next action would be a narrowly targeted subset download from the official HF dataset page, not a full blind multi-GB fetch.

## Summary verdict

CORD v2 is useful as a generic receipt document-understanding resource, but it is not a GreenLedger carbon-accounting dataset and does not justify a full multi-GB download as part of the current minimal data foundation step.
