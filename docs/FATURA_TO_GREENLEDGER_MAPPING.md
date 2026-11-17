# FATURA-to-GreenLedger Mapping

FATURA can support generic invoice/document-understanding experiments. It is not a GreenLedger carbon-accounting dataset and does not provide GreenLedger carbon ground truth.

## Useful document-understanding labels

Where present and documented in the local FATURA annotations, fields such as invoice number/date, due date, seller/buyer names, addresses, totals, taxes, discounts, line-item descriptions, quantities, and prices can support generic OCR, layout parsing, invoice-field extraction, and line-item experiments.

Map only like-for-like generic concepts (for example, seller name to a generic supplier-name field and invoice date to invoice date). Preserve the original annotation and the mapping rule. Do not interpret an arbitrary invoice quantity, item description, or total as a GreenLedger activity.

## Not supplied by FATURA

FATURA does not provide GreenLedger activity labels, energy/fuel quantities, operational-boundary context, GHG scope/category labels, verified GreenLedger emission factors, or GreenLedger CO2e ground truth. It is not a carbon, activity, or factor dataset.

## Annotation and evaluation rules

- Use FATURA only for tasks its local documents and annotations actually support.
- Represent public records using `data/benchmark/GREENLEDGER_ANNOTATION_SCHEMA.json` with `source_type: public` and an explicit `task_coverage` mask. Generic public document labels are separate from the frozen GreenLedger v1 activity taxonomy.
- Keep carbon-specific sections absent when the source does not provide carbon ground truth. Do not infer carbon labels from invoice content alone.
- Preserve raw text and source evidence, and compare fields using the matching rules in `docs/GREENLEDGER_BENCHMARK_PLAN.md`; raw exact text equality is not sufficient for normalized quantities and units.
- Store system predictions separately from the ground-truth annotation.

Synthetic and real SME GreenLedger documents require their own independently created and verified carbon annotations. An `expected_co2e` value is included only where the relevant verified CO2e factor and every required conversion are available; FATURA cannot supply that value.
