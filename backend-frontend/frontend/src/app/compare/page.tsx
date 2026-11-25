'use client';

import React, { useEffect, useState } from 'react';
import { fetchComparison, fetchDemoUsers } from '@/lib/api';
import { CompareResponse, DemoUser } from '@/types';
import { ReasonBadge } from '@/components/ReasonBadge';

export default function ComparePage() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [topK, setTopK] = useState<number>(5);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDemoUsers().then((loaded) => {
      setUsers(loaded);
      const initial = loaded.find((user) => user.interaction_count > 0) || loaded[0];
      if (initial) setSelectedUser(initial.user_id);
    }).catch((err) => setError(err.message || 'Failed to fetch users'));
  }, []);

  useEffect(() => {
    async function loadCompare() {
      if (!selectedUser) return;
      try {
        setLoading(true);
        setError(null);
        const res = await fetchComparison(selectedUser, topK);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch comparison');
      } finally {
        setLoading(false);
      }
    }
    loadCompare();
  }, [selectedUser, topK]);

  const modelColumns = [
    {
      id: 'popularity-positive-event-count-v1',
      title: 'Popularity Baseline',
      badge: 'Unpersonalized',
      badgeColor: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
      description: 'Global exposure and completion volume. Used as universal cold-start fallback.',
    },
    {
      id: 'item-cf-cosine-v1',
      title: 'Item-Based CF',
      badge: 'Collaborative',
      badgeColor: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-200 dark:border-blue-800',
      description: 'Shrunk cosine similarity over user interaction vectors with already-seen filtering.',
    },
    {
      id: 'lightgcn-validation-selected-v1',
      title: 'LightGCN Graph',
      badge: 'Graph Neural Net',
      badgeColor: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800',
      description: 'Evaluated extension experiment; it was rejected and receives zero weight in the selected model.',
    },
    {
      id: 'hybrid-validation-selected-v1',
      title: 'Validation Hybrid',
      badge: 'Proposed Best',
      badgeColor: 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950 dark:text-indigo-200 dark:border-indigo-800',
      description: 'Selected validation-tuned ranker: 90% Item-CF + 10% popularity + 0% LightGCN.',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 pb-5">
        <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight">
          Algorithm Comparison Matrix
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Compare recommendation rankings across all four models for the exact same user and candidate universe.
        </p>
      </div>

      {/* Control Bar */}
      <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4 shadow-sm transition-colors">
        <div className="flex items-center gap-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">Target User:</label>
          <select
            value={selectedUser}
            onChange={(e) => setSelectedUser(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.user_id} ({u.is_cold_start ? 'Cold Start' : u.history_available === false ? 'known evaluation user' : `${u.interaction_count} past events`})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">Items Per Model:</span>
          {[3, 5, 10].map((k) => (
            <button
              key={k}
              onClick={() => setTopK(k)}
              className={`w-8 h-8 rounded-lg text-xs font-bold transition ${
                topK === k
                  ? 'bg-slate-900 dark:bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 rounded-lg text-rose-800 dark:text-rose-200 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-slate-500 dark:text-slate-400 font-mono animate-pulse">
          Computing candidate projections across 4 models for {selectedUser}...
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {modelColumns.map((col) => {
            const modelResp = data.models[col.id];
            const items = modelResp?.recommendations || [];

            return (
              <div
                key={col.id}
                className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between overflow-hidden transition-colors"
              >
                <div>
                  {/* Column Header */}
                  <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${col.badgeColor}`}>
                        {col.badge}
                      </span>
                      {modelResp?.fallback && (
                        <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950 px-1.5 py-0.5 rounded">
                          Fallback
                        </span>
                      )}
                    </div>
                    <h3 className="font-extrabold text-base text-slate-900 dark:text-white mt-2">{col.title}</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">{col.description}</p>
                  </div>

                  {/* Recommendations List */}
                  <div className="p-4 space-y-3">
                    {items.map((it, idx) => (
                      <div
                        key={it.item_id}
                        className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:bg-white dark:hover:bg-slate-850 hover:border-indigo-200 dark:hover:border-indigo-800 transition space-y-2"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="w-5 h-5 rounded-full bg-slate-800 dark:bg-indigo-600 text-white font-bold text-[11px] flex items-center justify-center shrink-0">
                            {idx + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <span className="text-[10px] uppercase font-bold text-indigo-600 dark:text-indigo-400 block">
                              {it.video?.category || 'General'}
                            </span>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                              {it.video?.title || it.item_id}
                            </h4>
                          </div>
                          <span className="text-[11px] font-mono font-bold text-slate-700 dark:text-slate-300 shrink-0">
                            {it.score.toFixed(3)}
                          </span>
                        </div>

                        {/* Top Reason */}
                        {it.reasons.length > 0 && (
                          <div className="pt-1">
                            <ReasonBadge reason={it.reasons[0]} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/80 text-[11px] text-slate-500 dark:text-slate-400 font-mono text-center">
                  Model Key: {col.id}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
