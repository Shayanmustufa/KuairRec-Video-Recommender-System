# Final Results Appendix

## Frozen model and test result

- Model: `hybrid-validation-selected-v1`
- Weights: 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN
- Test Recall@10 / Recall@20: 0.012742 / 0.025472
- Test NDCG@10 / NDCG@20: 0.015098 / 0.019188
- Test Precision@10 / Precision@20: 0.012902 / 0.013397
- Test Hit Rate@10 / Hit Rate@20: 0.109033 / 0.198721
- Test catalog coverage@20: 0.638513 (5,375 items)
- Metric-eligible users: 6,255 of 7,176
- Duplicate / seen-item violations: 0 / 0

## Final verification

Syed's WBS audit passed 15 of 15 days and
all 15 cross-cutting checks. The test was not rerun,
model selection remained locked, the leakage and claim audits passed, and chart
inputs/outputs matched their checksum manifest.

## Archive locator

`model/artifacts/final_archive_manifest.json` indexes 71
files totaling 1727405980 bytes. Manifest SHA-256:
`5c86d9bcb5289d51ec4ed06b18cacb734e35aae15dd29698a29c7ea13807a84f`.

Generated data and large artifacts remain ignored by Git; the archive manifest
provides integrity and location metadata rather than duplicating those files.
