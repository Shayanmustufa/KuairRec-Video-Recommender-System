'use client';

import React, { useEffect, useState } from 'react';
import { fetchOfflineMetrics } from '@/lib/api';

export default function MetricsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadMetrics() {
      try {
        setLoading(true);
        const res = await fetchOfflineMetrics();
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch metrics summary');
      } finally {
        setLoading(false);
      }
    }
    loadMetrics();
  }, []);

  if (loading) {
    return (
      <div className="py-16 text-center text-slate-500 dark:text-slate-400 font-mono animate-pulse">
        Loading evaluation protocol and scientific benchmark metrics...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 rounded-xl text-rose-800 dark:text-rose-200 text-sm">
        {error || 'Metrics not available'}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 pb-5">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 text-xs font-semibold mb-2">
          ✓ Leakage-Free Temporal Protocol • Frozen Random Seed 42
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight">
          Offline Model Evaluation & Benchmark Metrics
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Controlled comparative results evaluated on held-out test data from the KuaiRec benchmark.
        </p>
      </div>

      {/* Dataset & Protocol Card */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm transition-colors">
        <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">Scientific Protocol Parameters</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm font-mono">
          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-xs text-slate-500 dark:text-slate-400 block">Training Partition</span>
            <strong className="text-slate-900 dark:text-slate-100 font-bold">{data.evaluation_protocol?.training_split}</strong>
          </div>
          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-xs text-slate-500 dark:text-slate-400 block">Validation Holdout</span>
            <strong className="text-slate-900 dark:text-slate-100 font-bold">{data.evaluation_protocol?.validation_split}</strong>
          </div>
          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-xs text-slate-500 dark:text-slate-400 block">Test Holdout</span>
            <strong className="text-slate-900 dark:text-slate-100 font-bold">{data.evaluation_protocol?.test_split}</strong>
          </div>
          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-xs text-slate-500 dark:text-slate-400 block">Positive Event Target</span>
            <strong className="text-slate-900 dark:text-slate-100 font-bold">{data.evaluation_protocol?.target_threshold}</strong>
          </div>
        </div>
      </div>

      {/* Primary Model Comparison Table */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden transition-colors">
        <div className="p-5 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Comparative Model Performance (Top-10 and Top-20)</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Primary Top-K value is 10. Secondary results reported at K=20.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700 text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 font-mono">
              <tr>
                <th className="px-5 py-3">Algorithm</th>
                <th className="px-5 py-3">Recall@10</th>
                <th className="px-5 py-3">Recall@20</th>
                <th className="px-5 py-3">NDCG@10</th>
                <th className="px-5 py-3">NDCG@20</th>
                <th className="px-5 py-3">Hit Rate@10</th>
                <th className="px-5 py-3">Precision@10</th>
                <th className="px-5 py-3">Coverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
              {data.overall_metrics?.map((m: any) => {
                const isBest = m.model_id === 'hybrid-v1';
                return (
                  <tr key={m.model_id} className={isBest ? 'bg-indigo-50/60 dark:bg-indigo-950/40 font-semibold' : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/40'}>
                    <td className="px-5 py-3.5 font-sans">
                      <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                        {m.model_name}
                        {isBest && (
                          <span className="text-[10px] bg-indigo-600 text-white font-mono px-1.5 py-0.5 rounded">
                            PROPOSED BEST
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">{m.model_id}</span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200">{m.recall_at_10.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-600 dark:text-slate-400">{m.recall_at_20.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200">{m.ndcg_at_10.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-600 dark:text-slate-400">{m.ndcg_at_20.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200">{m.hit_rate_at_10.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200">{m.precision_at_10.toFixed(4)}</td>
                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200">{(m.catalog_coverage * 100).toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hybrid Weight Ablation Table */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden transition-colors">
        <div className="p-5 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Hybrid Weight Ablation Study (Grid Search on Validation)</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Validation tuning of fusion weights: &alpha; (Item-CF) + &beta; (LightGCN) + &gamma; (Popularity) = 1.0.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700 text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 font-mono">
              <tr>
                <th className="px-5 py-3">Configuration</th>
                <th className="px-5 py-3">&alpha; (CF)</th>
                <th className="px-5 py-3">&beta; (Graph)</th>
                <th className="px-5 py-3">&gamma; (Popularity)</th>
                <th className="px-5 py-3">Recall@10</th>
                <th className="px-5 py-3">NDCG@10</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
              {data.hybrid_weight_ablations?.map((ab: any, idx: number) => {
                const isOptimal = ab.alpha_cf === 0.45;
                return (
                  <tr key={idx} className={isOptimal ? 'bg-emerald-50/70 dark:bg-emerald-950/40 font-bold text-emerald-950 dark:text-emerald-200' : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/40'}>
                    <td className="px-5 py-3 font-sans">
                      {ab.experiment}
                      {isOptimal && (
                        <span className="ml-2 text-[10px] bg-emerald-700 text-white font-mono px-1.5 py-0.5 rounded">
                          OPTIMAL
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">{ab.alpha_cf.toFixed(2)}</td>
                    <td className="px-5 py-3">{ab.beta_extension.toFixed(2)}</td>
                    <td className="px-5 py-3">{ab.gamma_popularity.toFixed(2)}</td>
                    <td className="px-5 py-3">{ab.recall_at_10.toFixed(4)}</td>
                    <td className="px-5 py-3">{ab.ndcg_at_10.toFixed(4)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
