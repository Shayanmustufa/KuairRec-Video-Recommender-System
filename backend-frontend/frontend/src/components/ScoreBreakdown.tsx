import React from 'react';
import type { Component } from '@/types';

const LABELS: Record<string, string> = { item_cf: 'Item-CF', lightgcn: 'LightGCN', popularity: 'Popularity' };
const ORDER = ['item_cf', 'lightgcn', 'popularity'];

/** Per-item hybrid score: weight × normalized component score (WBS §5.4). */
export function ScoreBreakdown({ components, total }: { components: Record<string, Component>; total: number }) {
  const names = ORDER.filter((name) => components[name]);
  return (
    <table className="w-full text-[11px]" aria-label="Hybrid score breakdown">
      <caption className="mb-1 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Score breakdown
      </caption>
      <thead className="text-slate-500 dark:text-slate-400">
        <tr>
          <th scope="col" className="text-left font-medium">
            Component
          </th>
          <th scope="col" className="text-right font-medium">
            weight
          </th>
          <th scope="col" className="text-right font-medium">
            normalized
          </th>
          <th scope="col" className="text-right font-medium">
            contribution
          </th>
        </tr>
      </thead>
      <tbody className="font-mono">
        {names.map((name) => (
          <tr key={name}>
            <th scope="row" className="text-left font-sans font-normal">
              {LABELS[name] ?? name}
            </th>
            <td className="text-right">{components[name].weight.toFixed(1)}</td>
            <td className="text-right">{components[name].normalized_score.toFixed(3)}</td>
            <td className="text-right">{components[name].contribution.toFixed(3)}</td>
          </tr>
        ))}
        <tr className="border-t border-slate-200 font-semibold dark:border-slate-700">
          <th scope="row" className="text-left font-sans">
            Hybrid score
          </th>
          <td colSpan={3} className="text-right">
            {total.toFixed(3)}
          </td>
        </tr>
      </tbody>
    </table>
  );
}
