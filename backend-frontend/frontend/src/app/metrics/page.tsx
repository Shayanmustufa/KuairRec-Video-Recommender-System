'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { fetchOfflineMetrics } from '@/lib/api';
import type { ModelMetrics, OfflineMetrics } from '@/types';
import { ErrorState, Loading } from '@/components/States';
import { MODEL_LABELS } from '@/lib/format';

const COLUMNS: { key: keyof ModelMetrics; label: string; primary?: boolean }[] = [
  { key: 'recall_at_10', label: 'Recall@10', primary: true },
  { key: 'ndcg_at_10', label: 'NDCG@10', primary: true },
  { key: 'hit_rate_at_10', label: 'Hit Rate@10', primary: true },
  { key: 'precision_at_10', label: 'Precision@10', primary: true },
  { key: 'recall_at_20', label: 'Recall@20' },
  { key: 'ndcg_at_20', label: 'NDCG@20' },
  { key: 'catalog_coverage', label: 'Catalog coverage@20' },
];

function Bars({ data }: { data: OfflineMetrics }) {
  const max = Math.max(...data.validation_metrics.map((m) => m.metrics.ndcg_at_10));
  return (
    <figure className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <figcaption className="text-base font-bold">Validation NDCG@10 by model</figcaption>
      <ul className="mt-4 space-y-3">
        {data.validation_metrics.map((m) => (
          <li key={m.id} className="text-xs">
            <div className="flex justify-between">
              <span>{MODEL_LABELS[m.id] ?? m.name}</span>
              <span className="font-mono">{m.metrics.ndcg_at_10.toFixed(4)}</span>
            </div>
            <div className="mt-1 h-3 rounded bg-slate-100 dark:bg-slate-800" aria-hidden="true">
              <div
                className={`h-3 rounded ${m.status === 'selected' ? 'bg-indigo-600' : m.status === 'rejected' ? 'bg-rose-400' : 'bg-slate-500'}`}
                style={{ width: `${(m.metrics.ndcg_at_10 / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </figure>
  );
}

export default function MetricsPage() {
  const [data, setData] = useState<OfflineMetrics | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => {
    setError(null);
    fetchOfflineMetrics().then(setData).catch(setError);
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!data) return <Loading label="Loading evaluation metrics…" />;
  const protocol = data.evaluation_protocol;
  const test = data.controlled_test;
  const checks = test.behavior_checks;

  return (
    <div className="space-y-8">
      <header className="border-b border-slate-200 pb-4 dark:border-slate-800">
        <h1 className="text-2xl font-extrabold tracking-tight">Offline evaluation</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">
          Validation results were used for model selection; the selected hybrid then had one controlled test pass. Primary K is 10; K = 20
          is secondary. Relevance is the derived proxy {String(protocol.target_threshold)}, not an explicit like label.
        </p>
      </header>

      <section
        aria-labelledby="protocol-heading"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 id="protocol-heading" className="text-base font-bold">
          Validation / test split summary
        </h2>
        <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Train', protocol.training_split],
            ['Validation', protocol.validation_split],
            ['Test', protocol.test_split],
            ['Relevance', protocol.target_threshold],
            ['Candidates', protocol.candidate_pool],
            ['Users', Number(protocol.evaluation_users_count).toLocaleString('en-US')],
            ['Catalog', Number(protocol.catalog_size).toLocaleString('en-US')],
            ['Split seed', protocol.seed],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
              <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
              <dd className="font-mono font-semibold">{String(value)}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">{String(protocol.metric_denominator_policy)}</p>
      </section>

      <section
        aria-labelledby="validation-heading"
        className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 id="validation-heading" className="p-5 pb-0 text-base font-bold">
          Validation comparison (model selection)
        </h2>
        <div className="overflow-x-auto p-5">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 font-mono text-xs uppercase text-slate-600 dark:border-slate-700 dark:text-slate-300">
              <tr>
                <th scope="col" className="py-2 pr-4">
                  Model
                </th>
                {COLUMNS.map((c) => (
                  <th scope="col" key={c.key} className={`py-2 pr-4 ${c.primary ? '' : 'text-slate-400'}`}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono dark:divide-slate-800">
              {data.validation_metrics.map((m) => (
                <tr key={m.id} className={m.status === 'selected' ? 'bg-indigo-50 dark:bg-indigo-950/40' : ''}>
                  <th scope="row" className="py-2 pr-4 font-sans font-semibold">
                    {m.name} <span className="ml-1 rounded bg-slate-200 px-1 text-[10px] uppercase dark:bg-slate-700">{m.status}</span>
                  </th>
                  {COLUMNS.map((c) => (
                    <td key={c.key} className="py-2 pr-4">
                      {c.key === 'catalog_coverage' ? `${(m.metrics[c.key] * 100).toFixed(1)}%` : m.metrics[c.key].toFixed(4)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Bars data={data} />

      <section
        aria-labelledby="test-heading"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 id="test-heading" className="text-base font-bold">
          Controlled test pass · {MODEL_LABELS[test.model_id] ?? test.model_id}
        </h2>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          {test.users_metric_eligible.toLocaleString('en-US')} of {Number(protocol.evaluation_users_count).toLocaleString('en-US')} users
          had an eligible relevant test item ({(test.all_user_evaluation_coverage * 100).toFixed(1)}% evaluation coverage). Runtime{' '}
          {test.runtime_seconds.toFixed(1)} s on {test.runtime_environment.platform}.
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-3 font-mono text-sm md:grid-cols-4">
          {COLUMNS.map((c) => (
            <div key={c.key} className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
              <dt className="font-sans text-xs text-slate-500 dark:text-slate-400">{c.label}</dt>
              <dd className="font-semibold">
                {c.key === 'catalog_coverage' ? `${(test[c.key] * 100).toFixed(1)}%` : test[c.key].toFixed(4)}
              </dd>
            </div>
          ))}
        </dl>
        <h3 className="mt-5 text-sm font-bold">Cold-start and seen-item checks</h3>
        <ul className="mt-2 list-disc pl-5 text-xs text-slate-700 dark:text-slate-300">
          <li>
            Users without positive pre-test history: {String(checks.users_without_positive_pretest_history)} — served by the popularity
            fallback.
          </li>
          <li>Known-user recommendation coverage: {(Number(checks.known_user_recommendation_coverage) * 100).toFixed(0)}%.</li>
          <li>
            Seen-item violations: {String(checks.seen_item_violations)}; duplicate recommendations:{' '}
            {String(checks.duplicate_recommendations)}.
          </li>
          <li>Unknown users: {String(checks.unknown_user_test_population)} — handled at serving time by the cold-start fallback.</li>
        </ul>
      </section>
    </div>
  );
}
