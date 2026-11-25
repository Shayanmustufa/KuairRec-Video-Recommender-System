# KuaiRec Data Card

## Dataset identity and provenance

- **Dataset:** KuaiRec Dataset with Raw Features
- **Release:** KuaiRec 2.0; Zenodo record 18164998
- **Zenodo DOI:** [10.5281/zenodo.18164998](https://doi.org/10.5281/zenodo.18164998)
- **Official sources:** [KuaiRec website](https://kuairec.com/),
  [official repository](https://github.com/chongminggao/KuaiRec), and the
  [CIKM 2022 data paper](https://doi.org/10.1145/3511808.3557220).
- **Downloaded archive:** `data/raw/KuaiRec.zip`; Zenodo published size
  431,964,858 bytes, MD5 `261550d472c48eff4990fb13c0e5bcf7`.
- **Archive SHA-256:** generated locally after download and recorded in
  `data/processed/release_manifest.json`.
- **License discrepancy:** the official GitHub
  [LICENSE file](https://github.com/chongminggao/KuaiRec/blob/main/LICENSE) identifies CC BY-SA 4.0,
  while Zenodo record metadata identifies CC BY 4.0. This project follows the
  more restrictive CC BY-SA 4.0 terms until the maintainers clarify the
  discrepancy. Do not redistribute the dataset archive from this project.

## Data files and roles

- `big_matrix.csv` is the sole source of interaction events for the model.
- `small_matrix.csv` is audited separately and is not concatenated with the Big
  Matrix or treated as an independent ratings test.
- The official site notes that Small Matrix missing entries reflect blocked
  user-video recommendations. Its 181,992 rows missing time/date/timestamp are
  retained as matrix cells but are not temporal events for this project.
- `item_categories.csv`, when present, is audited as item tag metadata.
- `social_network.csv`, when present, is counted for audit only; social links
  are not treated as evidence of shared taste.

## Schema and semantics

The official Big/Small Matrix schema includes `user_id`, `video_id`,
`play_duration`, `video_duration`, human-readable `time`, integer `date`, Unix
`timestamp`, and `watch_ratio`. The official documentation defines
`watch_ratio = play_duration / video_duration`, says no explicit like signal is
provided, and gives `watch_ratio > 2.0` as an example of deriving a positive
binary signal.

## Frozen protocol for this implementation

- **Relevant event:** `watch_ratio > 2.0`. This is a fixed derived target based
  on the official README example, not a native like label.
- **Duplicate key:** `(user_id, video_id, timestamp)`. Retain the first row in
  source order and report duplicate rows with conflicting payloads.
- **Eligibility:** iteratively retain the user-item 5-core using distinct
  training user-item edges only, so repeated events do not inflate graph degree
  and validation/test data do not determine the warm-user set
  or eligible catalog.
- **Split:** sort each eligible user's Big Matrix events by timestamp, then
  `video_id` for deterministic ties; assign the first 70% to training, next 15%
  to validation, and final 15% to test using floor boundaries. Boundaries are
  determined on deduplicated history before catalog filtering; filtering can
  change the final row ratios and does not move future events into training.
- **Leakage control:** validation/test events are excluded from the training
  history. Small Matrix rows are never merged into training.
- **Candidates:** for validation, use the full training-eligible catalog minus
  training history; for test, remove items seen in training or validation.
  Generate candidate pairs lazily; report users with no
  held-out relevant item remaining after seen-item removal separately.
- **Popularity baseline:** count positive (`watch_ratio > 2.0`) training events;
  use this as the cold-start fallback.
- **Advanced model:** LightGCN is the single planned extension; social edges are
  audit-only, not taste signals.

## Audit results

The audit report at `data/processed/data_audit.json` contains exact interaction,
user, item, missing-value, duplicate, timestamp, and social-link counts. Watch
ratio percentiles are estimated from a deterministic sample of up to
100,000 valid interactions (seed 2026); the exact sample size and
percentiles are recorded in the JSON report.

- **Big Matrix:** 12,530,806 rows, 7,176
  users, 10,728 videos. There are
  968,005 duplicate event keys
  (1 with conflicting payloads);
  936,390 raw rows exceed the target
  threshold. Timestamp range: 2020-06-23T00:34:11.373000+00:00 to
  2020-09-09T23:32:12.427000+00:00.
- **Small Matrix:** 4,676,570 matrix rows,
  1,411 users, 3,327 videos, and
  181,992 rows without timestamps.
  These remain in published matrix counts but are excluded from temporal
  modeling.
- **Item categories:** 10,728 item rows, 31 distinct tag IDs, 0 malformed rows.
- **Social links:** 472 users and 670 directed friend entries; 0 malformed rows. Social links are audit-only.
- **Official published reference:** observed counts match the
  Big Matrix reference (12,530,806 rows / 7,176 users / 10,728 videos) at
  16.28% density. Small Matrix counts match its
  reference (4,676,570 rows / 1,411 users / 3,327 videos) at 99.62%
  density.
- **Filtered split counts:** 11,299,325 eligible events (8,088,376 train, 1,714,495 validation, 1,496,454 test).
  Relevant events: 611,760 train, 118,362 validation, 107,002 test.
  Eligible users/items: 7,176/8,418; training-only distinct-edge core excluded 0 users, 2,310 items, and 263,476 events.
- **Leakage/overlap and candidate coverage:** Train/test overlap is 7,175 users and 5,540 items.
  Test has 91,913 eligible relevant user-item instances in full-catalog candidates; 921 users have no remaining relevant candidate. Primary ranking metrics exclude those users, and all-user evaluation coverage is reported separately.

## Limitations

The target threshold is a derived proxy for positive engagement, not a ground
truth like. Big and Small Matrices have different collection/evaluation roles.
No friendship-based taste claim is made. The split is temporal per user; users
who do not satisfy the warm-user eligibility core are excluded from the warm
split and must be treated as cold-start in later evaluation.
