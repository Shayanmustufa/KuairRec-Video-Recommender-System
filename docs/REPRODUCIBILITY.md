# Reproducibility and Leakage Review

## Frozen experimental protocol

- Dataset: KuaiRec 2.0, archive SHA-256
  `c23f211cf109c7a060a25a4afe9e8c681b1ccbbc816cca921d87ad37dd11c70c`
- Seed: `2026`
- Relevance: `watch_ratio > 2.0`
- Eligibility: distinct-edge training-only user/item 5-core
- Split: per-user chronological 70/15/15 before catalog filtering
- Validation candidates: eligible catalog minus training-seen items
- Test candidates: eligible catalog minus training- and validation-seen items
- Selected model: `hybrid-validation-selected-v1`
- Selected weights: 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN
- Primary K: 10; secondary K: 20
- Test outcomes used for selection: no

## Final data statistics

| Statistic | Value |
|---|---:|
| Raw Big Matrix rows | 12,530,806 |
| Deduplicated rows | 11,562,801 |
| Duplicate rows removed | 968,005 |
| Conflicting duplicate keys | 1 |
| Eligible users | 7,176 |
| Eligible items | 8,418 |
| Eligible events | 11,299,325 |
| Training events / relevant | 8,088,376 / 611,760 |
| Validation events / relevant | 1,714,495 / 118,362 |
| Test events / relevant | 1,496,454 / 107,002 |

The machine-readable source is `data/processed/final_data_statistics.json`.

## Experiment table

| Stage | Configuration / selection | Validation outcome |
|---|---|---|
| Popularity | Positive training-event count | NDCG@10 0.016763; Recall@10 0.015693 |
| Item-CF | 5 neighbors, shrinkage 200 | NDCG@10 0.015370; Recall@10 0.012228; coverage@20 0.661796 |
| LightGCN debug | 32 dimensions, 2 layers, LR 0.001, 10 epochs | Finite; debug feasibility passed |
| LightGCN selected | 32 dimensions, 2 layers, LR 0.002, 15 epochs | NDCG@10 0.009279; rejected standalone |
| Hybrid | 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN | NDCG@10 0.016448; NDCG@20 0.021916; Hit Rate@20 0.208697 |
| Explanations | Item-CF contribution + training popularity evidence | 143,520/143,520 recommendations supported |

Full grids, metrics, ablations, runtimes, and hardware are recorded in
`docs/EXPERIMENTS.md` and generated JSON artifacts.

## Reproduction commands

Run from the repository root in this order:

```powershell
python -m pip install -r model/requirements.txt
python -m model.src.verify_release
python -m model.src.audit --data-dir data/raw/KuaiRec
python -m model.src.split --data-dir data/raw/KuaiRec --output-dir data/processed --min-interactions 5 --watch-ratio-threshold 2.0 --seed 2026
python -m model.src.popularity
python -m model.src.item_cf
python -m model.src.lightgcn
python -m model.src.lightgcn_tune
python -m model.src.hybrid
python -m model.src.freeze_day9
python -m model.src.day10_audit
python -m model.src.controlled_test
python -m model.src.finalize_day12
python -m model.src.day13_analysis
python -m model.src.day14_report
python -m model.src.day15_final_audit
python -m unittest discover -s model/tests -v
```

Generated data and artifacts are ignored by Git. Re-running the freeze after a
model/configuration change creates a new checksum baseline and must occur before
the controlled test pass.

## Runtime environment

- Python 3.11.9
- NumPy 2.4.6
- SciPy 1.17.1
- PyTorch 2.6.0+cu124
- GPU used for full LightGCN: NVIDIA RTX 4000 Ada Generation, 20 GiB
- Popularity, Item-CF, preprocessing, audit, and hybrid orchestration run on CPU

Pinned direct numerical dependencies are in `model/requirements.txt`. Standard
library modules implement release verification, CSV processing, audit, and
split construction.

## Artifact inventory

The generated inventory contains 25 experiment artifacts totaling 102,230,389
bytes (about 97.5 MiB). Twelve artifacts are checksum-frozen for the controlled
test. `model/artifacts/artifact_inventory.json` records every filename, size,
SHA-256, and freeze status. Large predictions and evidence remain untracked.

## Leakage review

The automated Day 10 audit passed all checks:

- all six split/history/catalog files match their recorded SHA-256 hashes;
- actual train/validation/test row counts match the split manifest;
- no per-user train→validation or validation→test chronology violation exists;
- training history is byte-identical to `train.csv`;
- all five model-selection manifests declare `test_data_used: false`;
- model-selection source modules contain no literal `test.csv` reference;
- all Day 9 frozen artifacts and the tracked reason configuration match hashes;
- test outcomes were not used for training, tuning, weighting, or explanations.

Day 10 hashes the test file and inspects only user/video/timestamp ordering for
integrity. It does not calculate test relevance metrics. The exact report is
`model/artifacts/leakage_audit.json` and reports `passed: true`.

## Controlled-test record

The Day 11 evaluator verified `test_time_manifest.json` and
`leakage_audit.json`, then ran once. It produced 143,520 predictions and the
required ranking and coverage metrics with zero duplicate or previously seen
recommendations.

The output guard is now active: `python -m model.src.controlled_test` refuses to
run while controlled output files exist. Model weights and hyperparameters are
locked. Output, freeze, leakage-audit, test-split, and evaluator-source hashes
are recorded in `model/artifacts/controlled_test_manifest.json`.

## Final serving metadata

Day 12 exports `model/artifacts/model_manifest.json` as the canonical model and
dataset identity, plus `model/artifacts/system_metadata.json` as the frontend
contract. `model/artifacts/claim_audit.json` verifies the supported baseline
comparisons, zero LightGCN weight/reasons, explanation coverage, leakage result,
and locked test selection. UI rendering is pending the separately owned
frontend integration.

## Post-test diagnostics

Day 13 analyzes only the saved controlled-test output. It independently derives
the failure table and cold-start behavior, measures popularity concentration,
and runs three seeded user-level bootstrap resampling checks. It neither reruns
the controlled evaluator nor reopens model selection. The complete evidence and
interpretation are in `docs/FAILURE_ANALYSIS.md`.

## Final WBS audit and archive

Day 15 performs a fresh, non-mutating leakage verification over all split rows,
checks every frozen and controlled-test hash, verifies model/metric/chart/claim
consistency, and scans source documentation for secrets and machine-local paths.
It passed all 15 Syed-owned days and all cross-cutting checks. The indexed
archive is `model/artifacts/final_archive_manifest.json`; the human-readable
walkthrough and results summary are `docs/SYED_WBS_AUDIT.md` and
`docs/RESULTS_APPENDIX.md`.
