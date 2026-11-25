import React from 'react';
import type { ModelManifest, RecommendedItem } from '@/types';
import { hybridTotals } from '@/lib/format';

const ROWS = [
  { key: 'item_cf', label: 'Item-CF (α)' },
  { key: 'lightgcn', label: 'LightGCN (β)' },
  { key: 'popularity', label: 'Popularity (γ)' },
];

/** Hybrid explanation panel (WBS Day 8): frozen weights and how much each
 * component contributed to the visible list. */
export function HybridPanel({ manifest, items }: { manifest: ModelManifest | null; items: RecommendedItem[] }) {
  const weights = manifest?.selected_weights ?? {};
  const totals = hybridTotals(items);
  const sum = Object.values(totals).reduce((a, b) => a + b, 0) || 1;
  return (
    <section
      aria-labelledby="hybrid-heading"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 id="hybrid-heading" className="text-base font-bold">
        Hybrid explanation
      </h2>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        score = α·Item-CF + β·LightGCN + γ·popularity, each normalised per user to [0, 1]. Weights were selected on validation only;
        LightGCN was rejected, so β = 0.
      </p>
      <ul className="mt-3 space-y-2">
        {ROWS.map(({ key, label }) => {
          const share = (totals[key] ?? 0) / sum;
          return (
            <li key={key} className="text-xs">
              <div className="flex justify-between">
                <span>
                  {label} — weight <strong className="font-mono">{(weights[key] ?? 0).toFixed(1)}</strong>
                </span>
                <span className="font-mono">{(share * 100).toFixed(1)}% of shown score</span>
              </div>
              <div className="mt-1 h-2 rounded bg-slate-100 dark:bg-slate-800" aria-hidden="true">
                <div className="h-2 rounded bg-indigo-600" style={{ width: `${Math.max(share * 100, 0)}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
