"""Consolidate statistics, inventory artifacts, and audit leakage controls."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from model.src.common import repository_root, sha256_file

SELECTION_MODULES = (
    "popularity.py", "item_cf.py", "lightgcn.py", "lightgcn_tune.py", "hybrid.py"
)
SELECTION_MANIFESTS = (
    "popularity_manifest.json", "item_cf_manifest.json",
    "lightgcn_debug_manifest.json", "lightgcn_manifest.json", "hybrid_manifest.json",
)


def split_bounds(path: Path) -> dict[str, object]:
    """Read only IDs/timestamps and summarize ordered per-user split bounds."""
    count = 0
    users: dict[int, tuple[tuple[float, int], tuple[float, int]]] = {}
    previous_user: int | None = None
    previous_key: tuple[float, int] | None = None
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            key = (float(row["timestamp"]), int(row["video_id"]))
            if previous_user == user and previous_key is not None and key < previous_key:
                raise ValueError(f"Non-monotonic rows in {path.name} for user {user}")
            if user in users:
                users[user] = (users[user][0], key)
            else:
                users[user] = (key, key)
            previous_user, previous_key = user, key
            count += 1
    return {"rows": count, "users": users}


def run_day10_audit(data_dir: Path, artifact_dir: Path, source_dir: Path) -> dict[str, object]:
    split = json.loads((data_dir / "split_manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((data_dir / "data_audit.json").read_text(encoding="utf-8"))
    release = json.loads((data_dir / "release_manifest.json").read_text(encoding="utf-8"))
    freeze = json.loads((artifact_dir / "test_time_manifest.json").read_text(encoding="utf-8"))

    frozen_mismatches = []
    for filename, expected in freeze["frozen_artifacts_sha256"].items():
        actual = sha256_file(artifact_dir / filename)
        if actual != expected:
            frozen_mismatches.append(filename)
    reason_hash_matches = sha256_file(source_dir.parent / "reason_codes.json") == freeze["reason_config_sha256"]

    split_hash_results = {}
    for filename, expected in split["sha256"].items():
        actual = sha256_file(data_dir / filename)
        split_hash_results[filename] = {"expected": expected, "actual": actual, "matches": actual == expected}

    bounds = {
        name: split_bounds(data_dir / f"{name}.csv")
        for name in ("train", "validation", "test")
    }
    chronology_violations: list[dict[str, object]] = []
    for earlier, later in (("train", "validation"), ("validation", "test")):
        common = bounds[earlier]["users"].keys() & bounds[later]["users"].keys()
        for user in common:
            if bounds[earlier]["users"][user][1] >= bounds[later]["users"][user][0]:
                chronology_violations.append({"user_id": user, "earlier": earlier, "later": later})

    manifest_checks = {}
    for filename in SELECTION_MANIFESTS:
        manifest = json.loads((artifact_dir / filename).read_text(encoding="utf-8"))
        manifest_checks[filename] = manifest.get("test_data_used") is False
    source_test_references = {}
    for filename in SELECTION_MODULES:
        text = (source_dir / filename).read_text(encoding="utf-8")
        source_test_references[filename] = "test.csv" in text

    history_train_matches = (
        split["sha256"]["train.csv"] == split["sha256"]["user_history_train.csv"]
    )
    expected_counts = split["filtered"]["events_by_split"]
    observed_counts = {name: bounds[name]["rows"] for name in bounds}
    counts_match = observed_counts == expected_counts
    leakage = {
        "schema_version": "1.0",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": all((
            not frozen_mismatches,
            reason_hash_matches,
            all(result["matches"] for result in split_hash_results.values()),
            not chronology_violations,
            all(manifest_checks.values()),
            not any(source_test_references.values()),
            history_train_matches,
            counts_match,
            freeze["test_data_accessed_for_model_selection"] is False,
        )),
        "checks": {
            "frozen_artifact_hash_mismatches": frozen_mismatches,
            "reason_config_hash_matches_freeze": reason_hash_matches,
            "split_file_hashes": split_hash_results,
            "observed_split_rows": observed_counts,
            "split_counts_match_manifest": counts_match,
            "chronology_violations": chronology_violations,
            "selection_manifests_declare_no_test_use": manifest_checks,
            "selection_source_literal_test_csv_references": source_test_references,
            "train_history_is_byte_identical_to_train": history_train_matches,
            "test_outcomes_used_for_selection": False,
            "test_integrity_and_order_only_audited": True,
        },
    }
    leakage_path = artifact_dir / "leakage_audit.json"
    leakage_path.write_text(json.dumps(leakage, indent=2) + "\n", encoding="utf-8")

    final_stats = {
        "schema_version": "1.0",
        "dataset": release["dataset"],
        "release": release["release"],
        "archive_sha256": release["sha256"],
        "source": {
            "big_matrix_rows": audit["interactions"]["big_matrix"]["raw_interactions"],
            "deduplicated_big_matrix_rows": split["input"]["rows_stored_after_deduplication"],
            "duplicate_rows_removed": split["input"]["duplicate_rows_removed"],
            "conflicting_duplicate_keys": split["input"]["conflicting_duplicate_event_keys"],
        },
        "eligible": {
            "users": split["filtered"]["users_after_filtering"],
            "items": split["filtered"]["items_after_filtering"],
            "events": split["filtered"]["events_after_filtering"],
            "events_by_split": expected_counts,
            "relevant_events_by_split": split["filtered"]["relevant_events_by_split"],
        },
        "target": split["relevance"],
        "eligibility": split["eligibility"],
        "candidate_protocol": split["filtered"]["candidate_protocol"],
        "selected_model": {
            "model_id": freeze["selected_model_id"],
            "weights": freeze["selected_weights"],
        },
    }
    stats_path = data_dir / "final_data_statistics.json"
    stats_path.write_text(json.dumps(final_stats, indent=2) + "\n", encoding="utf-8")

    excluded = {"artifact_inventory.json", "leakage_audit.json"}
    inventory_entries = []
    for path in sorted(artifact_dir.iterdir()):
        if not path.is_file() or path.name in excluded or path.name == ".gitkeep":
            continue
        inventory_entries.append({
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "frozen_for_test": path.name in freeze["frozen_artifacts_sha256"],
        })
    inventory = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_count": len(inventory_entries),
        "total_size_bytes": sum(entry["size_bytes"] for entry in inventory_entries),
        "artifacts": inventory_entries,
    }
    inventory_path = artifact_dir / "artifact_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    return {"statistics": final_stats, "leakage": leakage, "inventory": inventory}


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--source-dir", type=Path, default=root / "model" / "src")
    args = parser.parse_args(); result = run_day10_audit(args.data_dir, args.artifact_dir, args.source_dir)
    print(json.dumps({
        "leakage_passed": result["leakage"]["passed"],
        "artifact_count": result["inventory"]["artifact_count"],
        "artifact_total_size_bytes": result["inventory"]["total_size_bytes"],
        "split_rows": result["leakage"]["checks"]["observed_split_rows"],
    }, indent=2))


if __name__ == "__main__": main()
