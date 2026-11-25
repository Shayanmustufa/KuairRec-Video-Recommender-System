"""Finalize the model manifest, UI metadata contract, and claim audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from model.src.common import repository_root, sha256_file


def finalize_day12(
    data_dir: Path,
    artifact_dir: Path,
    docs_dir: Path,
    frontend_candidates: tuple[Path, ...],
) -> dict[str, object]:
    release = json.loads((data_dir / "release_manifest.json").read_text(encoding="utf-8"))
    stats = json.loads((data_dir / "final_data_statistics.json").read_text(encoding="utf-8"))
    hybrid = json.loads((artifact_dir / "hybrid_validation_metrics.json").read_text(encoding="utf-8"))
    test = json.loads((artifact_dir / "controlled_test_metrics.json").read_text(encoding="utf-8"))
    controlled_manifest = json.loads((artifact_dir / "controlled_test_manifest.json").read_text(encoding="utf-8"))
    explanations = json.loads((artifact_dir / "explanation_validation.json").read_text(encoding="utf-8"))
    leakage = json.loads((artifact_dir / "leakage_audit.json").read_text(encoding="utf-8"))
    config = json.loads((artifact_dir / "hybrid_config.json").read_text(encoding="utf-8"))

    item_cf_deltas = hybrid["full_validation_deltas"]["item_cf"]
    popularity_deltas = hybrid["full_validation_deltas"]["popularity"]
    weights = config["selected_weights"]
    claims = {
        "hybrid_beats_item_cf_on_all_reported_validation_ranking_metrics": all(
            value > 0 for value in item_cf_deltas.values()
        ),
        "hybrid_does_not_dominate_popularity_at_primary_k": (
            popularity_deltas["recall@10"] < 0
            and popularity_deltas["ndcg@10"] < 0
        ),
        "lightgcn_rejected_and_zero_weight": weights["lightgcn"] == 0,
        "no_lightgcn_explanations_at_zero_weight": (
            explanations["extension_model_reasons_at_zero_weight"] == 0
        ),
        "all_explanations_supported": explanations["passed"],
        "controlled_test_selection_remained_locked": (
            test["selection_locked_after_test"]
            and controlled_manifest["model_selection_reopened"] is False
        ),
        "leakage_audit_passed": leakage["passed"],
    }
    unsupported = [name for name, passed in claims.items() if not passed]
    frontend_present = any(
        path.is_dir() and any(candidate.is_file() for candidate in path.rglob("*"))
        for path in frontend_candidates
    )

    document_references = {}
    for filename in ("MODEL_CARD.md", "EXPERIMENTS.md", "REPRODUCIBILITY.md", "DATA_CARD.md"):
        path = docs_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required Day 12 document is missing: {path}")
        document_references[f"docs/{filename}"] = sha256_file(path)

    artifact_references = {}
    for filename in (
        "popularity_manifest.json", "item_cf_manifest.json", "lightgcn_manifest.json",
        "hybrid_manifest.json", "test_time_manifest.json", "controlled_test_manifest.json",
        "explanation_validation.json", "leakage_audit.json",
    ):
        artifact_references[filename] = sha256_file(artifact_dir / filename)
    model_manifest = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {
            "model_id": config["model_id"],
            "display_name": "KuaiRec validation-selected hybrid",
            "status": "controlled_test_complete_selection_locked",
            "selected_weights": weights,
            "components": {
                "popularity": "active",
                "item_cf": "active",
                "lightgcn": "evaluated_rejected_zero_weight",
            },
        },
        "dataset": {
            "name": release["dataset"],
            "release": release["release"],
            "doi": release["doi"],
            "archive_sha256": release["sha256"],
            "license_note": (
                "GitHub LICENSE says CC BY-SA 4.0 while Zenodo metadata says CC BY 4.0; "
                "follow CC BY-SA 4.0 pending clarification."
            ),
            "eligible_users": stats["eligible"]["users"],
            "eligible_items": stats["eligible"]["items"],
            "target": stats["target"],
        },
        "protocol": {
            "seed": test["seed"],
            "split": "per-user chronological train/validation/test",
            "validation_candidates": "eligible catalog minus training-seen items",
            "test_candidates": test["candidate_protocol"],
            "metric_denominator_policy": test["metric_denominator_policy"],
        },
        "validation": hybrid["full_validation"],
        "controlled_test": {
            "run_at_utc": test["run_at_utc"],
            "evaluation": test["evaluation"],
            "behavior_checks": test["behavior_checks"],
            "selection_locked_after_test": True,
        },
        "explanations": {
            "reason_config": "model/reason_codes.json",
            "evidence_coverage": explanations["evidence_coverage"],
            "recommendations_checked": explanations["recommendations_checked"],
            "enabled_offline_codes": sorted(explanations["reason_instances_by_code"]),
            "cold_start_code_available": True,
        },
        "limitations": [
            "watch_ratio > 2.0 is a derived engagement proxy, not an explicit like",
            "offline metrics do not establish user satisfaction or production readiness",
            "popularity may reinforce exposure bias and Item-CF may over-specialize",
            "demographic, creator, category, and content-safety fairness are not evaluated",
            "unknown users are not present in the offline controlled-test population",
        ],
        "artifact_manifests_sha256": artifact_references,
    }
    manifest_path = artifact_dir / "model_manifest.json"
    manifest_path.write_text(json.dumps(model_manifest, indent=2) + "\n", encoding="utf-8")

    system_metadata = {
        "schema_version": "1.0",
        "dataset": model_manifest["dataset"],
        "model": model_manifest["model"],
        "test_summary": {
            "metrics": test["evaluation"]["metrics"],
            "catalog_coverage_at_20": test["evaluation"]["catalog_coverage@20"],
            "evaluation_coverage": test["evaluation"]["all_user_evaluation_coverage"],
        },
        "explanations": model_manifest["explanations"],
        "manifest_sha256": sha256_file(manifest_path),
    }
    metadata_path = artifact_dir / "system_metadata.json"
    metadata_path.write_text(json.dumps(system_metadata, indent=2) + "\n", encoding="utf-8")

    claim_audit = {
        "schema_version": "1.0",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": not unsupported,
        "evidence_checks": claims,
        "unsupported_claims": unsupported,
        "documents_reviewed": [
            "docs/MODEL_CARD.md", "docs/EXPERIMENTS.md",
            "docs/REPRODUCIBILITY.md", "docs/DATA_CARD.md",
        ],
        "documents_sha256": document_references,
        "ui_metadata_contract": {
            "path": "model/artifacts/system_metadata.json",
            "contains_dataset_release": True,
            "contains_model_identity": True,
            "contains_controlled_test_summary": True,
            "frontend_present": frontend_present,
            "ui_rendering_verified": False,
            "pending_owner": "Abdul Qadir Satti" if not frontend_present else "frontend integration review",
        },
        "model_manifest_sha256": sha256_file(manifest_path),
        "system_metadata_sha256": sha256_file(metadata_path),
    }
    audit_path = artifact_dir / "claim_audit.json"
    audit_path.write_text(json.dumps(claim_audit, indent=2) + "\n", encoding="utf-8")
    if unsupported:
        raise ValueError(f"Unsupported model claims: {', '.join(unsupported)}")
    return {"model_manifest": model_manifest, "claim_audit": claim_audit}


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--docs-dir", type=Path, default=root / "docs")
    args = parser.parse_args()
    result = finalize_day12(
        args.data_dir, args.artifact_dir, args.docs_dir,
        (root / "frontend", root / "client"),
    )
    print(json.dumps({
        "model_id": result["model_manifest"]["model"]["model_id"],
        "claim_audit_passed": result["claim_audit"]["passed"],
        "ui_metadata_contract": result["claim_audit"]["ui_metadata_contract"],
    }, indent=2))


if __name__ == "__main__": main()
