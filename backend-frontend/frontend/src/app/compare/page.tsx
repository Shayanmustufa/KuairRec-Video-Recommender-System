'use client';

import { useCatalogEnglish } from '@/components/CatalogEnglish';
import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchComparison, fetchDemoUsers, fetchModelManifest } from '@/lib/api';
import type { CompareResponse, DemoUser, ModelManifest } from '@/types';
import { ReasonBadge } from '@/components/ReasonBadge';
import { EmptyState, ErrorState, Loading } from '@/components/States';
import { MODEL_LABELS, videoTitle } from '@/lib/format';

const STATUS_BADGE: Record<string, string> = {
  selected: 'bg-indigo-600 text-white',
  baseline: 'bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-slate-100',
  rejected: 'bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-100',
};

export default function ComparePage() {
  const translations = useCatalogEnglish();
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [manifest, setManifest] = useState<ModelManifest | null>(null);
  const [userId, setUserId] = useState('');
  const [topK, setTopK] = useState(5);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [token, setToken] = useState(0);

  const init = useCallback(() => {
    setError(null);
    Promise.all([fetchDemoUsers(), fetchModelManifest()])
      .then(([list, m]) => {
        setUsers(list);
        setManifest(m);
        setUserId((cur) => cur || list.find((u) => u.status === 'known')?.user_id || list[0]?.user_id || '');
      })
      .catch((err) => {
        setError(err);
        setLoading(false);
      });
  }, []);
  useEffect(init, [init]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchComparison(userId, topK)
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [userId, topK, token]);

  return (
    <div className="space-y-6">
      <header className="border-b border-slate-200 pb-4 dark:border-slate-800">
        <h1 className="text-2xl font-extrabold tracking-tight">Model comparison</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">
          Popularity, Item-CF, the LightGCN extension and the selected hybrid for the same user and the same candidate set: the
          validation-time lists ranked from training history only, over the full eligible catalog minus training-seen items.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-1">
          <label htmlFor="compare-user" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            User
          </label>
          <select
            id="compare-user"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.user_id} ({u.status === 'known' ? `${u.positive_history_items} positive events` : 'no positive history'})
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="compare-k" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            Items per model
          </label>
          <select
            id="compare-k"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            {[3, 5, 10, 20].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => setToken((n) => n + 1)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => (users.length ? setToken((n) => n + 1) : init())} />
      ) : loading || !data ? (
        <Loading label={`Loading comparison for user ${userId || '…'}`} />
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {(manifest?.models ?? []).map((meta) => {
            const column = data.models[meta.id];
            return (
              <section
                key={meta.id}
                aria-labelledby={`col-${meta.id}`}
                className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <header className="border-b border-slate-100 p-4 dark:border-slate-800">
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_BADGE[meta.status] ?? STATUS_BADGE.baseline}`}
                  >
                    {meta.status}
                  </span>
                  <h2 id={`col-${meta.id}`} className="mt-2 text-base font-extrabold">
                    {MODEL_LABELS[meta.id] ?? meta.name}
                  </h2>
                  <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{meta.description}</p>
                  <p className="mt-1 font-mono text-[11px] text-slate-500">val NDCG@10 {meta.metrics.ndcg_at_10.toFixed(4)}</p>
                </header>
                <ol className="space-y-3 p-4">
                  {column?.recommendations.length ? (
                    column.recommendations.map((item) => (
                      <li key={item.item_id} className="space-y-2 rounded-lg border border-slate-100 p-3 dark:border-slate-800">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-xs font-bold">#{item.rank}</span>
                          <Link
                            href={`/videos/${encodeURIComponent(item.item_id)}`}
                            className="min-w-0 flex-1 truncate text-xs font-semibold hover:underline"
                          >
                            {videoTitle(item, translations)}
                          </Link>
                          <span className="font-mono text-[11px]">{item.score.toFixed(3)}</span>
                        </div>
                        {item.reasons[0] && <ReasonBadge reason={item.reasons[0]} />}
                      </li>
                    ))
                  ) : (
                    <li>
                      <EmptyState>{column?.empty_reason ?? 'No results.'}</EmptyState>
                    </li>
                  )}
                </ol>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
