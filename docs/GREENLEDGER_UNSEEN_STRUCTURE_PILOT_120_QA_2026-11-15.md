# GreenLedger Unseen-Structure Pilot (120) — Final Visual QA and Freeze Audit

**Audit date:** 2026-11-15  
**Final status:** **PASS WITH CAVEATS**  
**Dataset:** `data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/`  
**Freeze marker SHA-256:** `e3fcac4917e621a860b29e8924b28f2bd9f764cee3e13b6aaadaa91d251d7c0a`

## Outcome

The final 120-document pilot passes the visual and annotation checks performed for this audit and is frozen for evaluation-only use. The evidence-state balance remains **40 ready / 40 incomplete / 40 ambiguous**. There are **0 unresolved critical, 0 unresolved major, and 0 unresolved minor issues**. Corrections made before freezing are recorded below; no open document correction is required.

This is a synthetic challenge set. The result does not establish performance on real SME paperwork or statistical representativeness.

## Visual review and diversity

All **120 documents / 156 rendered pages** were visually covered in eight batched page contact sheets. Selected full-page views were also used to examine repaired overlaps and evidence placement. The final document bytes are identical to the reviewed final page set. Contact sheets are available here:

- [Pages 1–20](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_01.png)
- [Pages 21–40](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_02.png)
- [Pages 41–60](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_03.png)
- [Pages 61–80](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_04.png)
- [Pages 81–100](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_05.png)
- [Pages 101–120](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_06.png)
- [Pages 121–140](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_07.png)
- [Pages 141–156](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/final_qa_pages_08.png)
- [Coarse-hash candidates reviewed together](assets/greenledger_unseen_structure_pilot_120_qa_2026-11-15/zero_hash_candidates.png)

The set contains 27 named layout families, six visibly distinct structural forms (table, thermal, prose, floating-card, ledger, and annex), 36 supplier identities, and 113 field-order signatures. No family contains more than five documents; no field-order signature appears more than three times. Forms include utility/account statements, registers, purchase schedules and orders, delivery and weighbridge records, fuel slips, carrier documents, and multi-page annex-style records. They are not all invoice-shaped.

| Property | Final observed distribution |
|---|---:|
| Domains | Electricity 20; diesel 20; LPG 20; materials 30; freight 30 |
| Formats | Born-digital PDF 40; simulated image-only/scanned PDF 40; PNG 20; JPEG 20 |
| Pages per document | 1 page 90; 2 pages 24; 3 pages 6 (156 pages total) |
| Page-size/orientation templates | A4 portrait 41; A4 landscape 35; letter portrait 27; narrow receipt 10; legal portrait 7 |
| Typography groups | Mono 32; serif 30; sans 30; humanist 28 |
| Raster quality treatments | Clean 25; faint 18; mild skew 14; JPEG artifacts 12; soft/low contrast 6; light blur 5 |

Multi-page records were visually coherent across their pages. Repaired table and thermal rows no longer collide with adjacent text; headers and evidence blocks are readable in the final pages. The layout/content variation is meaningful for a pilot challenge, but all documents still originate from one synthetic scene-rendering system. Raster degradation is simulated: there are **no genuinely scanned or phone-photographed source documents**. The typography groups and page-size counts describe renderer choices, not independently sourced real-world designs.

## Evidence-state review

The domain-by-state allocation is:

| Domain | Ready | Incomplete | Ambiguous | Total |
|---|---:|---:|---:|---:|
| Electricity | 7 | 7 | 6 | 20 |
| Diesel | 7 | 7 | 6 | 20 |
| LPG | 7 | 7 | 6 | 20 |
| Materials | 10 | 10 | 10 | 30 |
| Freight | 9 | 9 | 12 | 30 |
| **Total** | **40** | **40** | **40** | **120** |

**Ready:** Visual evidence is present for required activity-specific inputs. The 40 annotated expected results were recomputed using the current deterministic accounting engine; there were **0 mismatches**.

**Incomplete:** The annotated required evidence is visibly absent, so additional evidence is needed rather than inference. All 40 have a missing-evidence reason, and none carries a numeric expected accounting result.

**Ambiguous:** Conflicting or unclear evidence is visible and requires clarification. The 128 ambiguity-candidate evidence entries were checked against their anchors; there were **0 mismatches**. The 12 freight vehicle-class conflicts now identify two distinct supported classes per case. Ambiguous records have no numeric expected result.

The rendered documents do not expose the labels `ready`, `incomplete`, or `ambiguous`, nor the expected accounting results. Labels and expected results remain in the separate annotation file.

## Annotation and file consistency checks

- 120 document IDs matched 120 annotation records.
- 1,130 present/ambiguous evidence anchors were checked.
- Born-digital evidence text misses: **0**.
- Born-digital bounding-box coverage misses: **0**.
- Raster evidence boxes without visible ink: **0**.
- Born-digital text overlap pairs after repair: **0**.
- Ambiguous candidate evidence mismatches: **0 / 128**.
- Ready deterministic result mismatches: **0 / 40**.
- Non-ready records with numeric expected-result leakage: **0**.
- Domain/state missing-reason inconsistencies: **0**.
- Freight ambiguous pairs with unrecognized or equal classes: **0 / 12**.
- The existing training/validation reader returned **0 pilot records** for both train and validation requests.

The pilot has 126 files covered by the freeze marker (documents, annotations, manifest, provenance, integrity report, README, and contact sheet). Every covered path and SHA-256/byte count matches; `FROZEN.json` is excluded from its own hash list to avoid self-reference. The marker records 120 documents, 120 annotations, 156 pages, the 40/40/40 state split, and the use restrictions. The report and QA contact sheets are stored outside the frozen dataset directory.

## Similarity and leakage review

The coarse 8×8 average-hash screen produced 11 zero-distance candidates: `GLP-F-003`, `GLP-F-004`, `GLP-D-004`, `GLP-F-007`, `GLP-E-004`, `GLP-L-004`, `GLP-E-010`, `GLP-F-017`, `GLP-M-017`, `GLP-M-030`, and `GLP-F-030`. These were compared visually with each other and against accessible old train/validation examples. **No accidental duplicate, near-duplicate, or same-template derivative was identified.** The zero-distance results are hash collisions on sparse, mostly white page compositions; the screen is not discriminative. The median nearest-hash distance was 12. The displayed contact sheet gives reviewers the flagged pilot candidates together.

The cross-set checks used only the accessible old train/validation material: 390 documents. Exact-file overlap was 0 and supplier-name overlap was 0. The quarantined old test split was **not opened, read, or used**. The reader-isolation check above also confirmed zero pilot rows returned under its train and validation paths.

## Corrections made before freeze

The initial visual pass found overlap/readability defects; layout sizing and placement were corrected and the dataset was regenerated without changing IDs or the 40/40/40 split. The affected overlap-review IDs were: `GLP-D-001`, `GLP-E-003`, `GLP-E-007`, `GLP-E-009`, `GLP-L-007`, `GLP-F-016`, `GLP-M-016`, `GLP-F-019`, `GLP-M-024`, `GLP-F-024`, and `GLP-M-029`.

Annotation/evidence review also corrected ambiguity candidate anchoring for six diesel records: `GLP-D-004`, `GLP-D-005`, `GLP-D-007`, `GLP-D-010`, `GLP-D-013`, and `GLP-D-017`. Freight ambiguity candidates were made distinct and valid supported classes. The generator changes and corrected IDs are recorded in `integrity_report.json`; all 120 document hashes were refreshed in the manifest. The final hash verification passed. There are no remaining known corrections to make.

## Issue classification

| Class | Unresolved findings |
|---|---:|
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Acceptable limitations | 3 |

Acceptable limitations:

1. Single synthetic renderer; layout diversity is designed, not sampled from unseen real vendors.
2. Scan/phone-like appearance uses simulated raster effects, not genuine scans or photographs.
3. No real or consented SME documents or independent external annotator review are present; this is not real-world validation. The coarse perceptual-hash metric is also weak, with manual visual review used to resolve its flagged candidates.

## Freeze decision and use policy

The pilot is **FROZEN for evaluation-only use**. Training, fine-tuning, prompt tuning, threshold tuning, and model tuning on its annotations are prohibited. Model selection may use it only after an evaluation protocol is registered. Keep annotations separate and load them only through an evaluation-only path. Do not add the pilot to generic recursive training-data discovery.

- Dataset directory: `data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/`
- Final manifest: [manifest.json](../data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/manifest.json)
- Freeze marker: [FROZEN.json](../data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/FROZEN.json)
- Integrity and correction log: [integrity_report.json](../data/benchmark/greenledger_unseen_structure_pilot_120_2026-11-15/integrity_report.json)

No model was benchmarked and no production accounting, OCR, or Candidate A implementation was changed in this QA/freeze step.
