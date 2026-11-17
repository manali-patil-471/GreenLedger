# Synthetic Test Split Quarantine — 2026-11-10

## Decision

Quarantine the entire 130-record `test` partition of `greenledger_synthetic_v0_1_1_partial`. Do not use it for extraction development, tuning, candidate selection, or evaluation.

## Exposure record

During the 2026-09-25 repository audit, a broad `rg` search included the complete `data` directory and the one-line-per-record `annotations.jsonl`. Its returned output was truncated by the tool (the response reported 5,856,701 bytes omitted). The visible output explicitly included annotation `GL-SYN-L-0160`, which is assigned to the test split. The command therefore searched across the test annotations, and the retained conversation output is insufficient to enumerate every record whose annotation text may have been returned.

`GL-SYN-L-0160` is the only test record that can be identified with certainty from the retained output. It is not safe to infer that it was the only exposed annotation. No test metrics were computed from that search and the source annotations were not modified; however, the original partition can no longer be represented as a fully blind holdout.

## Repair

Do not remove only `GL-SYN-L-0160`: the omitted output prevents a complete exposure list, so that would guess. Preserve the original annotations for provenance and quarantine all 130 test records. Before a final blinded score is needed, create a separate replacement holdout from independently generated or consented documents after the candidate is frozen; document its provenance and keep it out of all development.

Evaluation loaders and command-line harnesses now reject this release's `test` split. Current development and evaluation are limited to `train` and `validation`.
