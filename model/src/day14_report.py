"""Generate presentation-ready Day 14 charts from frozen experiment artifacts."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from model.src.common import repository_root, sha256_file


COLORS = ("#2563eb", "#ea580c", "#7c3aed", "#059669")


def render_grouped_bars(title: str, groups: list[tuple[str, list[tuple[str, float]]]], width: int = 900) -> str:
    height = 105 + sum(35 + 24 * len(rows) for _, rows in groups)
    values = [value for _, rows in groups for _, value in rows]
    maximum = max(values) if values else 1.0
    plot_left, plot_width = 190, width - 255
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        '<desc id="desc">Horizontal bar chart generated from frozen experiment JSON artifacts.</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="24" y="34" font-family="sans-serif" font-size="22" font-weight="700" fill="#111827">{html.escape(title)}</text>',
    ]
    y = 70
    for group, rows in groups:
        parts.append(f'<text x="24" y="{y}" font-family="sans-serif" font-size="15" font-weight="700" fill="#374151">{html.escape(group)}</text>')
        y += 18
        for index, (label, value) in enumerate(rows):
            bar_width = 0 if maximum == 0 else value / maximum * plot_width
            parts.extend((
                f'<text x="{plot_left - 10}" y="{y + 15}" text-anchor="end" font-family="sans-serif" font-size="13" fill="#374151">{html.escape(label)}</text>',
                f'<rect x="{plot_left}" y="{y}" width="{bar_width:.2f}" height="18" rx="3" fill="{COLORS[index % len(COLORS)]}"/>',
                f'<text x="{plot_left + bar_width + 7:.2f}" y="{y + 14}" font-family="monospace" font-size="12" fill="#111827">{value:.6f}</text>',
            ))
            y += 24
        y += 17
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def generate_charts(artifact_dir: Path, output_dir: Path) -> dict[str, object]:
    popularity = json.loads((artifact_dir / "popularity_validation_metrics.json").read_text(encoding="utf-8"))
    item_cf = json.loads((artifact_dir / "item_cf_validation_metrics.json").read_text(encoding="utf-8"))
    lightgcn = json.loads((artifact_dir / "lightgcn_validation_metrics.json").read_text(encoding="utf-8"))
    hybrid = json.loads((artifact_dir / "hybrid_validation_metrics.json").read_text(encoding="utf-8"))
    test = json.loads((artifact_dir / "controlled_test_metrics.json").read_text(encoding="utf-8"))
    models = (
        ("Popularity", popularity["metrics"]),
        ("Item-CF", item_cf["metrics"]),
        ("LightGCN", lightgcn["validation"]["metrics"]),
        ("Hybrid", hybrid["full_validation"]["metrics"]),
    )
    comparison = render_grouped_bars(
        "Validation comparison (full catalog)",
        [(label, [("NDCG@10", metrics["ndcg@10"]), ("Recall@10", metrics["recall@10"])]) for label, metrics in models],
    )
    generalization = render_grouped_bars(
        "Frozen hybrid: validation and controlled test",
        [
            ("Validation", [("NDCG@10", hybrid["full_validation"]["metrics"]["ndcg@10"]), ("Recall@10", hybrid["full_validation"]["metrics"]["recall@10"]), ("Hit Rate@20", hybrid["full_validation"]["metrics"]["hit_rate@20"])]),
            ("Controlled test", [("NDCG@10", test["evaluation"]["metrics"]["ndcg@10"]), ("Recall@10", test["evaluation"]["metrics"]["recall@10"]), ("Hit Rate@20", test["evaluation"]["metrics"]["hit_rate@20"])]),
        ],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {"model_comparison.svg": comparison, "hybrid_validation_test.svg": generalization}
    for filename, content in paths.items(): (output_dir / filename).write_text(content, encoding="utf-8")
    sources = ("popularity_validation_metrics.json", "item_cf_validation_metrics.json", "lightgcn_validation_metrics.json", "hybrid_validation_metrics.json", "controlled_test_metrics.json")
    manifest = {
        "schema_version": "1.0",
        "generator": "model.src.day14_report",
        "source_sha256": {name: sha256_file(artifact_dir / name) for name in sources},
        "chart_sha256": {name: sha256_file(output_dir / name) for name in paths},
        "claims": {"test_used_for_selection": False, "lightgcn_selected_weight": 0.0},
    }
    (output_dir / "day14_chart_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--output-dir", type=Path, default=root / "docs" / "assets")
    args = parser.parse_args(); print(json.dumps(generate_charts(args.artifact_dir, args.output_dir), indent=2))


if __name__ == "__main__": main()
