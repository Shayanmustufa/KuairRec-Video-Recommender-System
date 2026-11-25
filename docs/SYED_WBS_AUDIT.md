# Syed WBS Final Audit

Overall result: **PASS** (15/15 days).

| Day | Evidence-backed deliverable | Result |
|---:|---|---|
| 1 | Release verification and initial data card | PASS |
| 2 | Schema/data audit and finalized preprocessing | PASS |
| 3 | Leakage-safe chronological split | PASS |
| 4 | Training-only popularity baseline | PASS |
| 5 | Item-CF baseline and validation tuning | PASS |
| 6 | LightGCN debugging prototype | PASS |
| 7 | Validation-tuned LightGCN | PASS |
| 8 | Constrained validation-tuned hybrid | PASS |
| 9 | Evidence-backed explanations and freeze | PASS |
| 10 | Final statistics and leakage review | PASS |
| 11 | Single controlled test pass | PASS |
| 12 | Final model card, manifest, and claim audit | PASS |
| 13 | Failure, fallback, concentration, and stability analysis | PASS |
| 14 | Final report, tables, charts, and citations | PASS |
| 15 | Final audit, archive checksums, and results appendix | PASS |

## Cross-cutting verification

- **release hash matches final statistics:** PASS
- **split hashes match files:** PASS
- **frozen artifacts match:** PASS
- **selected identity consistent:** PASS
- **selected weights consistent:** PASS
- **controlled outputs match manifest:** PASS
- **selection remained locked:** PASS
- **leakage audit passed:** PASS
- **fresh day15 leakage audit passed:** PASS
- **claim audit passed and current:** PASS
- **chart sources and outputs match:** PASS
- **explanations fully supported:** PASS
- **no duplicate or seen recommendations:** PASS
- **no potential secrets:** PASS
- **no local absolute paths:** PASS

## Controlled-test preservation

The controlled test was not rerun. Its saved output hashes, frozen dependencies,
selection lock, schema, leakage result, and rerun guard were verified instead.

## Archive

- Entries: 71
- Total bytes indexed: 1727405980
- Manifest SHA-256: `5c86d9bcb5289d51ec4ed06b18cacb734e35aae15dd29698a29c7ea13807a84f`
- Machine-readable audit: `model/artifacts/final_wbs_audit.json`
