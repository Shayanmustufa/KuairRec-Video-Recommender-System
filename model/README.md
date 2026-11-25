# Offline data pipeline

The Day 1–3 KuaiRec pipeline uses only Python's standard library. It streams the
official interaction CSVs, writes intermediate data to a temporary SQLite
database, and keeps generated outputs under the ignored `data/processed/`
directory.

## Prepare the official release

Download the archive from the official
[Zenodo record](https://zenodo.org/records/18164998) into `data/raw/KuaiRec.zip`.
Verify and extract it using the standard-library utility:

```powershell
python -m model.src.verify_release
```

The command checks the published 431,964,858-byte size and MD5
`261550d472c48eff4990fb13c0e5bcf7`, computes SHA-256, checks archive paths and
CRC, extracts the data, and writes `data/processed/release_manifest.json`.
Do not commit the archive or generated data.

## Audit (Day 2)

From the repository root:

```powershell
python -m model.src.audit --data-dir data/raw/KuaiRec
```

The command writes `data/processed/data_audit.json` and updates
`docs/DATA_CARD.md`. Interaction counts and missing/duplicate counts are exact;
watch-ratio percentiles use a deterministic reservoir sample of at most 100,000
valid rows.

## Deduplicate and split (Day 3)

```powershell
python -m model.src.split --data-dir data/raw/KuaiRec --output-dir data/processed --min-interactions 5 --watch-ratio-threshold 2.0 --seed 2026
```

Only `big_matrix.csv` is used. Repeated `(user_id, video_id, timestamp)` keys
keep their first source row. The filter is an iterative user-item 5-core based
on distinct edges from the chronological training partition only, preventing validation/test data
from deciding warm-user eligibility or the candidate catalog. Events are
ordered per user by `(timestamp, video_id)` and assigned 70/15/15 using floor
boundaries before catalog filtering. The target `watch_ratio > 2.0` is a derived
positive proxy, not an official like label.

Outputs:

- `train.csv`, `validation.csv`, `test.csv`
- `user_history_train.csv` (training events only)
- `user_history_test.csv` (training plus validation events available before test)
- `candidate_catalog.csv` (eligible Big Matrix item IDs)
- `split_manifest.json` (protocol, counts, train/test user/item overlap,
  full-catalog positive coverage, event digest, and SHA-256 checksums)

Validation candidates exclude training-seen items; test candidates exclude items
seen in training or validation. The full catalog is scored lazily, without writing a
dense user-item candidate matrix. Users with no held-out relevant item remaining
after seen-item removal are counted separately for evaluation.

`--seed` is recorded for reproducibility; the chronological split and candidate
catalog are deterministic and do not sample negatives. Dataset checksums and
split details are described in [the data card](../docs/DATA_CARD.md).

## Tests

```powershell
python -m unittest discover -s model/tests -v
```

## Popularity baseline (Day 4)

```powershell
python -m model.src.popularity
```

The baseline counts positive training events (`watch_ratio > 2.0`) per item,
orders ties by ascending video ID, and serves as the cold-start fallback. It
evaluates the full eligible validation catalog after removing training-seen
items, writes top-20 predictions and per-user examples, and reports Recall,
NDCG, Precision, and Hit Rate at 10 and 20 plus catalog/evaluation coverage.
Users without an eligible relevant validation item are excluded from ranking
metric means and counted separately. No test interaction is read.

## Item-CF baseline (Day 5)

Install the pinned numerical dependencies, then train and validate:

```powershell
python -m pip install -r model/requirements.txt
python -m model.src.item_cf
```

Item-CF builds binary-positive cosine similarities from training only, applies
cooccurrence shrinkage, removes training-seen candidates, and tunes neighborhood
size and shrinkage on a deterministic validation-user sample. User preference
strength is the maximum `log1p(watch_ratio)` for each positive training
user–item pair. The selected model is evaluated on the full validation set and
exported with predictions, mappings, the complete tuning grid, and checksums.
The test split is not read.

## LightGCN debugging prototype (Day 6)

```powershell
python -m model.src.lightgcn
```

The frozen CPU prototype uses a seed-2026 sample of 256 validation-eligible
users, the full eligible item catalog, 32-dimensional embeddings, two LightGCN
propagation layers, BPR loss, learning rate 0.001, L2 regularization 0.0001, and
10 epochs. It writes a debugging checkpoint, top-20 validation predictions,
metrics, and checksums. It verifies finite losses/embeddings/scores and does not
read test data. It is not the final model; Day 7 performs validation-only tuning.

## Validation-tuned LightGCN (Day 7)

```powershell
python -m model.src.lightgcn_tune
```

The command evaluates a fixed one-factor grid over only learning rate,
propagation layers, embedding dimension, and epochs on 1,024 deterministic
validation users. It retrains the validation-selected configuration on the full
training graph and exports propagated embeddings, mappings, top-20 validation
predictions, the complete tuning report, baseline comparisons, and checksums.
CUDA is used when available; pass `--device cpu` for CPU execution. Test data is
not read. The current selected LightGCN is retained as a rejected experiment
because it underperforms both frozen baselines on validation ranking metrics.

## Validation-tuned hybrid (Day 8)

```powershell
python -m model.src.hybrid
```

The hybrid verifies all component checksums, performs per-user min–max
normalization over unseen full-catalog candidates, and evaluates all 66
nonnegative weight triples in 0.1 increments that sum to one. Selection uses
validation NDCG@10 then Recall@10. It exports selected weights, full validation
predictions with component evidence, the complete grid, single-component and
pairwise ablations, metrics, and checksums. The selected weights are 0.1
popularity, 0.9 Item-CF, and 0.0 LightGCN. Test data is not read.

## Explanation evidence and test-time freeze (Day 9)

```powershell
python -m model.src.freeze_day9
```

The command validates the tracked `model/reason_codes.json` contract against
every frozen validation recommendation, writes recommendation-level evidence,
fails if any recommendation lacks support, and rejects LightGCN explanations at
zero selected weight. It then writes `test_time_manifest.json` with SHA-256
checksums for the selected model, dependencies, explanation evidence, dataset
manifests, and the predeclared test protocol. It does not calculate test metrics.

## Final statistics and leakage review (Day 10)

```powershell
python -m model.src.day10_audit
```

This command independently verifies split and freeze hashes, streams actual
split ordering/counts, checks selection manifests and source references for test
leakage, writes consolidated final data statistics, and inventories generated
artifacts. It hashes and checks test ordering for integrity but does not use test
relevance outcomes or calculate test metrics. The human-readable reproduction
table is in `docs/REPRODUCIBILITY.md`.

## Single controlled test pass (Day 11)

```powershell
python -m model.src.controlled_test
```

This command has already completed successfully. It verifies the freeze and
leakage audit, evaluates the locked hybrid exactly once, checks duplicates and
seen items, and writes predictions, metrics, and a checksum manifest. Its rerun
guard is now active. Do not remove the controlled outputs or change model
settings in response to test results.

## Final model manifest and claim audit (Day 12)

```powershell
python -m model.src.finalize_day12
```

The command verifies the frozen selection, test lock, leakage result,
explanation evidence, and supported validation comparisons. It writes the
canonical `model_manifest.json`, a compact `system_metadata.json` contract for
the `/system` UI, and `claim_audit.json`. It does not rerun the controlled test
or alter model selection. UI rendering remains a frontend integration check.

## Failure and stability analysis (Day 13)

```powershell
python -m model.src.day13_analysis
```

The command analyzes the saved controlled-test predictions without rerunning the
test or changing model selection. It writes a failure table, verifies fallback
behavior, measures popularity/exposure concentration, and performs seeded
user-level bootstrap stability checks. Results and interpretation are documented
in `docs/FAILURE_ANALYSIS.md`.

## Final report charts (Day 14)

```powershell
python -m model.src.day14_report
```

The command regenerates the accessible SVG comparison charts in `docs/assets/`
directly from frozen validation and controlled-test JSON artifacts. A checksum
manifest binds each chart to its inputs. The consolidated methodology, results,
ablations, limitations, and primary-source references are in
`docs/FINAL_REPORT.md`.

## Final WBS and archive audit (Day 15)

```powershell
python -m model.src.day15_final_audit
```

The final audit streams the complete split history, rechecks chronology and
leakage controls without overwriting the historical Day 10 audit, verifies every
frozen and controlled-test hash, checks model/metric/chart consistency, scans
source documentation for secrets and local absolute paths, and validates all 15
Syed-owned days. It writes the checksum archive manifest, machine-readable WBS
audit, final results appendix, and human-readable audit report.
