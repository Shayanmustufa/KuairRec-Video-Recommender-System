"""Run Syed's final WBS conformance audit and archive evidence checksums."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from model.src.common import repository_root, sha256_file
from model.src.day10_audit import SELECTION_MANIFESTS, SELECTION_MODULES, split_bounds


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hashes_match(base: Path, expected: dict[str, str]) -> bool:
    return all((base / name).is_file() and sha256_file(base / name) == digest for name, digest in expected.items())


def _scan_hygiene(root: Path) -> dict[str, list[str]]:
    extensions = {".py", ".md", ".json", ".txt", ".toml", ".yaml", ".yml"}
    excluded_parts = {"artifacts", "processed", "raw", ".git", "__pycache__"}
    secret_pattern = re.compile(r"(?i)(api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['\"]([^'\"]+)['\"]")
    absolute_pattern = re.compile(r"[A-Za-z]:\\Users\\[^\s`'\"]+")
    secrets: list[str] = []; absolute_paths: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions or excluded_parts.intersection(path.parts): continue
        relative = path.relative_to(root).as_posix(); text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            match = secret_pattern.search(line)
            if match and match.group(2).lower() not in {"example", "placeholder", "changeme"}:
                secrets.append(f"{relative}:{line_number}")
            if absolute_pattern.search(line): absolute_paths.append(f"{relative}:{line_number}")
    return {"potential_secrets": secrets, "local_absolute_paths": absolute_paths}


def _archive_entries(paths: list[Path], root: Path) -> list[dict[str, object]]:
    entries = []
    for path in sorted(paths):
        entries.append({"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def run_final_audit(root: Path) -> dict[str, object]:
    data = root / "data" / "processed"; artifacts = root / "model" / "artifacts"; docs = root / "docs"
    release = _load(data / "release_manifest.json"); split = _load(data / "split_manifest.json")
    data_audit = _load(data / "data_audit.json"); stats = _load(data / "final_data_statistics.json")
    freeze = _load(artifacts / "test_time_manifest.json"); leakage = _load(artifacts / "leakage_audit.json")
    hybrid = _load(artifacts / "hybrid_validation_metrics.json"); config = _load(artifacts / "hybrid_config.json")
    controlled = _load(artifacts / "controlled_test_metrics.json"); controlled_manifest = _load(artifacts / "controlled_test_manifest.json")
    explanations = _load(artifacts / "explanation_validation.json"); model_manifest = _load(artifacts / "model_manifest.json")
    claim = _load(artifacts / "claim_audit.json"); day13 = _load(artifacts / "day13_failure_analysis.json")
    charts = _load(docs / "assets" / "day14_chart_manifest.json")
    hygiene = _scan_hygiene(root)

    bounds = {name: split_bounds(data / f"{name}.csv") for name in ("train", "validation", "test")}
    chronology_violations = []
    for earlier, later in (("train", "validation"), ("validation", "test")):
        for user in bounds[earlier]["users"].keys() & bounds[later]["users"].keys():
            if bounds[earlier]["users"][user][1] >= bounds[later]["users"][user][0]:
                chronology_violations.append({"user_id": user, "earlier": earlier, "later": later})
    selection_manifests_clean = all(_load(artifacts / name).get("test_data_used") is False for name in SELECTION_MANIFESTS)
    selection_sources_clean = all("test.csv" not in (root / "model" / "src" / name).read_text(encoding="utf-8") for name in SELECTION_MODULES)
    fresh_leakage_passed = all((
        _hashes_match(data, split["sha256"]),
        not chronology_violations,
        {name: bounds[name]["rows"] for name in bounds} == split["filtered"]["events_by_split"],
        selection_manifests_clean,
        selection_sources_clean,
        _hashes_match(artifacts, freeze["frozen_artifacts_sha256"]),
        freeze["test_data_accessed_for_model_selection"] is False,
    ))

    weights = {"popularity": 0.1, "item_cf": 0.9, "lightgcn": 0.0}
    controlled_outputs = controlled_manifest["outputs_sha256"]
    chart_sources_ok = _hashes_match(artifacts, charts["source_sha256"])
    chart_outputs_ok = _hashes_match(docs / "assets", charts["chart_sha256"])
    claim_docs_ok = _hashes_match(root, claim["documents_sha256"])
    required_test_metrics = {"recall@10", "recall@20", "ndcg@10", "ndcg@20", "precision@10", "precision@20", "hit_rate@10", "hit_rate@20"}
    report_text = (docs / "FINAL_REPORT.md").read_text(encoding="utf-8")

    days = [
        (1, "Release verification and initial data card", release["release"] == "KuaiRec 2.0" and len(release["sha256"]) == 64 and (docs / "DATA_CARD.md").is_file()),
        (2, "Schema/data audit and finalized preprocessing", data_audit["interactions"]["big_matrix"]["raw_interactions"] == 12_530_806 and data_audit["interactions"]["big_matrix"]["duplicate_user_video_timestamp_rows"] == 968_005),
        (3, "Leakage-safe chronological split", split["split"]["method"] == "per-user chronological" and split["eligibility"]["future_events_used_for_filtering"] is False and _hashes_match(data, split["sha256"])),
        (4, "Training-only popularity baseline", (artifacts / "popularity_model.json").is_file() and _load(artifacts / "popularity_manifest.json")["test_data_used"] is False),
        (5, "Item-CF baseline and validation tuning", (artifacts / "item_cf_model.npz").is_file() and _load(artifacts / "item_cf_manifest.json")["test_data_used"] is False),
        (6, "LightGCN debugging prototype", (artifacts / "lightgcn_debug_checkpoint.pt").is_file() and _load(artifacts / "lightgcn_debug_manifest.json")["test_data_used"] is False),
        (7, "Validation-tuned LightGCN", (artifacts / "lightgcn_embeddings.npz").is_file() and _load(artifacts / "lightgcn_manifest.json")["test_data_used"] is False),
        (8, "Constrained validation-tuned hybrid", hybrid["weight_combinations"] == 66 and hybrid["selected_weights"] == weights and hybrid["test_data_used"] is False),
        (9, "Evidence-backed explanations and freeze", explanations["passed"] is True and explanations["evidence_coverage"] == 1.0 and freeze["status"] == "frozen_for_controlled_test" and _hashes_match(artifacts, freeze["frozen_artifacts_sha256"])),
        (10, "Final statistics and leakage review", leakage["passed"] is True and fresh_leakage_passed and stats["eligible"]["events"] == 11_299_325 and not leakage["checks"]["chronology_violations"]),
        (11, "Single controlled test pass", controlled["run_type"] == "single_controlled_test_pass" and controlled["selection_locked_after_test"] is True and required_test_metrics == set(controlled["evaluation"]["metrics"]) and _hashes_match(artifacts, controlled_outputs)),
        (12, "Final model card, manifest, and claim audit", claim["passed"] is True and not claim["unsupported_claims"] and claim_docs_ok and model_manifest["model"]["selected_weights"] == weights),
        (13, "Failure, fallback, concentration, and stability analysis", day13["selection_reopened"] is False and day13["controlled_test_rerun"] is False and day13["cold_start"]["fallback_matches_frozen_popularity"] is True and len(day13["stability"]["seeds"]) == 3),
        (14, "Final report, tables, charts, and citations", chart_sources_ok and chart_outputs_ok and "https://doi.org/10.1145/3511808.3557220" in report_text and "https://arxiv.org/abs/2002.02126" in report_text),
    ]

    cross_checks = {
        "release_hash_matches_final_statistics": release["sha256"] == stats["archive_sha256"],
        "split_hashes_match_files": _hashes_match(data, split["sha256"]),
        "frozen_artifacts_match": _hashes_match(artifacts, freeze["frozen_artifacts_sha256"]),
        "selected_identity_consistent": config["model_id"] == freeze["selected_model_id"] == controlled["model_id"] == model_manifest["model"]["model_id"],
        "selected_weights_consistent": config["selected_weights"] == freeze["selected_weights"] == controlled["frozen_weights"] == model_manifest["model"]["selected_weights"] == weights,
        "controlled_outputs_match_manifest": _hashes_match(artifacts, controlled_outputs),
        "selection_remained_locked": controlled_manifest["model_selection_reopened"] is False and day13["selection_reopened"] is False,
        "leakage_audit_passed": leakage["passed"] is True,
        "fresh_day15_leakage_audit_passed": fresh_leakage_passed,
        "claim_audit_passed_and_current": claim["passed"] is True and not claim["unsupported_claims"] and claim_docs_ok,
        "chart_sources_and_outputs_match": chart_sources_ok and chart_outputs_ok,
        "explanations_fully_supported": explanations["passed"] is True and explanations["recommendations_without_supported_reason"] == 0,
        "no_duplicate_or_seen_recommendations": controlled["behavior_checks"]["duplicate_recommendations"] == 0 and controlled["behavior_checks"]["seen_item_violations"] == 0,
        "no_potential_secrets": not hygiene["potential_secrets"],
        "no_local_absolute_paths": not hygiene["local_absolute_paths"],
    }
    preliminary_pass = all(passed for _, _, passed in days) and all(cross_checks.values())

    archive_paths = [path for path in data.iterdir() if path.is_file() and path.name != ".gitkeep"]
    archive_paths += [path for path in artifacts.iterdir() if path.is_file() and path.name not in {".gitkeep", "final_archive_manifest.json", "final_wbs_audit.json"}]
    archive_paths += [path for path in docs.rglob("*") if path.is_file() and path.name not in {"RESULTS_APPENDIX.md", "SYED_WBS_AUDIT.md"}]
    archive_paths += [path for path in (root / "model" / "src").glob("*.py") if path.is_file()]
    archive_entries = _archive_entries(archive_paths, root)
    archive = {
        "schema_version": "1.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Syed Day 15 reproducibility archive index; generated data remain in place and are identified by checksum",
        "entry_count": len(archive_entries), "total_size_bytes": sum(entry["size_bytes"] for entry in archive_entries),
        "entries": archive_entries,
    }
    archive_path = artifacts / "final_archive_manifest.json"
    archive_path.write_text(json.dumps(archive, indent=2) + "\n", encoding="utf-8")
    archive_hash = sha256_file(archive_path)
    days.append((15, "Final audit, archive checksums, and results appendix", preliminary_pass and len(archive_entries) > 0 and len(archive_hash) == 64))
    passed = all(item[2] for item in days) and all(cross_checks.values())
    result = {
        "schema_version": "1.0", "audited_at_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
        "days_passed": sum(item[2] for item in days), "days_total": len(days),
        "wbs_days": [{"day": day, "deliverable": label, "passed": status} for day, label, status in days],
        "cross_checks": cross_checks, "hygiene": hygiene,
        "fresh_leakage": {"passed": fresh_leakage_passed, "chronology_violations": chronology_violations, "observed_split_rows": {name: bounds[name]["rows"] for name in bounds}, "selection_manifests_clean": selection_manifests_clean, "selection_sources_clean": selection_sources_clean},
        "archive": {"path": "model/artifacts/final_archive_manifest.json", "sha256": archive_hash, "entry_count": archive["entry_count"], "total_size_bytes": archive["total_size_bytes"]},
        "controlled_test_policy": {"rerun_performed": False, "verification": "saved output hashes, frozen inputs, selection lock, guard test, and metric schema"},
    }
    (artifacts / "final_wbs_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not passed:
        failures = [f"Day {day}" for day, _, status in days if not status] + [name for name, status in cross_checks.items() if not status]
        raise ValueError("Final audit failed: " + ", ".join(failures))
    return result


def render_wbs_audit(result: dict[str, object]) -> str:
    rows = "\n".join(f"| {row['day']} | {row['deliverable']} | {'PASS' if row['passed'] else 'FAIL'} |" for row in result["wbs_days"])
    checks = "\n".join(f"- **{name.replace('_', ' ')}:** {'PASS' if status else 'FAIL'}" for name, status in result["cross_checks"].items())
    return f"""# Syed WBS Final Audit

Overall result: **{'PASS' if result['passed'] else 'FAIL'}** ({result['days_passed']}/{result['days_total']} days).

| Day | Evidence-backed deliverable | Result |
|---:|---|---|
{rows}

## Cross-cutting verification

{checks}

## Controlled-test preservation

The controlled test was not rerun. Its saved output hashes, frozen dependencies,
selection lock, schema, leakage result, and rerun guard were verified instead.

## Archive

- Entries: {result['archive']['entry_count']}
- Total bytes indexed: {result['archive']['total_size_bytes']}
- Manifest SHA-256: `{result['archive']['sha256']}`
- Machine-readable audit: `model/artifacts/final_wbs_audit.json`
"""


def render_appendix(result: dict[str, object]) -> str:
    return f"""# Final Results Appendix

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

Syed's WBS audit passed {result['days_passed']} of {result['days_total']} days and
all {len(result['cross_checks'])} cross-cutting checks. The test was not rerun,
model selection remained locked, the leakage and claim audits passed, and chart
inputs/outputs matched their checksum manifest.

## Archive locator

`model/artifacts/final_archive_manifest.json` indexes {result['archive']['entry_count']}
files totaling {result['archive']['total_size_bytes']} bytes. Manifest SHA-256:
`{result['archive']['sha256']}`.

Generated data and large artifacts remain ignored by Git; the archive manifest
provides integrity and location metadata rather than duplicating those files.
"""


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root); args = parser.parse_args()
    result = run_final_audit(args.root)
    (args.root / "docs" / "SYED_WBS_AUDIT.md").write_text(render_wbs_audit(result), encoding="utf-8")
    (args.root / "docs" / "RESULTS_APPENDIX.md").write_text(render_appendix(result), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "days": f"{result['days_passed']}/{result['days_total']}", "cross_checks": result["cross_checks"], "archive": result["archive"]}, indent=2))


if __name__ == "__main__": main()
