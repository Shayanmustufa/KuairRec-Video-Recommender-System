"""Export the frozen Item-CF matrix to a compact Go-serving JSON index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scipy import sparse


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export(repo_root: Path, output_dir: Path, top_neighbors: int = 50) -> dict[str, object]:
    artifacts = repo_root / "model" / "artifacts"
    model_path = artifacts / "item_cf_model.npz"
    mapping_path = artifacts / "item_cf_mapping.json"
    manifest_path = artifacts / "item_cf_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for path in (model_path, mapping_path):
        expected = manifest["artifacts_sha256"][path.name]
        if sha256(path) != expected:
            raise ValueError(f"Frozen Item-CF checksum mismatch: {path.name}")

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    items = [str(item) for item in mapping["items"]]
    matrix = sparse.load_npz(model_path).tocsr()
    if list(matrix.shape) != [len(items), len(items)]:
        raise ValueError(f"Item-CF matrix shape {matrix.shape} does not match {len(items)} mapped items")

    neighbors: dict[str, dict[str, float]] = {}
    for row in range(matrix.shape[0]):
        start, end = int(matrix.indptr[row]), int(matrix.indptr[row + 1])
        indices = matrix.indices[start:end]
        values = matrix.data[start:end]
        ordered = sorted(zip(indices.tolist(), values.tolist()), key=lambda pair: (-pair[1], int(items[pair[0]])))[:top_neighbors]
        if ordered:
            neighbors[items[row]] = {items[index]: float(score) for index, score in ordered}

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "item_similarity.json"
    output_path.write_text(json.dumps(neighbors, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    export_manifest = {
        "schema_version": "1.0",
        "model_id": manifest["model_id"],
        "training_data": manifest["training_data"],
        "source_item_cf_manifest_sha256": sha256(manifest_path),
        "source_model_sha256": sha256(model_path),
        "source_mapping_sha256": sha256(mapping_path),
        "output_sha256": sha256(output_path),
        "items": len(items),
        "items_with_neighbors": len(neighbors),
        "maximum_neighbors_per_item": top_neighbors,
    }
    (output_dir / "item_similarity_manifest.json").write_text(json.dumps(export_manifest, indent=2) + "\n", encoding="utf-8")
    return export_manifest


def main() -> int:
    script_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=script_root)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "backend" / "serving_data")
    parser.add_argument("--top-neighbors", type=int, default=50)
    args = parser.parse_args()
    if args.top_neighbors < 1:
        parser.error("--top-neighbors must be positive")
    print(json.dumps(export(args.repo_root.resolve(), args.output_dir.resolve(), args.top_neighbors), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
