'use client';

import { useCatalogEnglish } from '@/components/CatalogEnglish';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchDemoUsers, fetchModelManifest, fetchRecommendations, fetchUser } from '@/lib/api';
import type { DemoUser, ModelManifest, RecommendationResponse, UserDetail } from '@/types';
import { MODEL_LABELS, SortKey, describeUserState, sortItems } from '@/lib/format';
import { VideoCard } from '@/components/VideoCard';
import { SkeletonCard } from '@/components/SkeletonLoader';
import { HybridPanel } from '@/components/HybridPanel';
import { UserHistoryPanel } from '@/components/UserHistoryPanel';
import { EmptyState, ErrorState, StateBanner } from '@/components/States';

const SELECTED = 'hybrid-validation-selected-v1';
const TOP_K_OPTIONS = [5, 10, 15, 20];

function statusLabel(user: DemoUser): string {
  return user.status === 'no_positive_history'
    ? 'no positive history'
    : `${user.positive_history_items.toLocaleString('en-US')} positive events`;
}

const control =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100';

export default function HomePage() {
  const translations = useCatalogEnglish();
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [manifest, setManifest] = useState<ModelManifest | null>(null);
  const [userId, setUserId] = useState('');
  const [customId, setCustomId] = useState('');
  const [model, setModel] = useState(SELECTED);
  const [topK, setTopK] = useState(10);
  const [excludeSeen, setExcludeSeen] = useState(true);
  const [coldStart, setColdStart] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('rank');
  const [refreshToken, setRefreshToken] = useState(0);

  const [initError, setInitError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [userDetail, setUserDetail] = useState<UserDetail | null>(null);

  const init = useCallback(async () => {
    setInitError(null);
    try {
      const [list, m] = await Promise.all([fetchDemoUsers(), fetchModelManifest()]);
      setUsers(list);
      setManifest(m);
      setUserId((current) => current || list.find((u) => u.status === 'known')?.user_id || list[0]?.user_id || '');
    } catch (err) {
      setInitError(err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRecommendations({ user_id: userId, top_k: topK, exclude_seen: excludeSeen, model, force_cold_start: coldStart })
      .then((resp) => !cancelled && setData(resp))
      .catch((err) => {
        if (!cancelled) {
          setError(err);
          setData(null);
        }
      })
      .finally(() => !cancelled && setLoading(false));
    fetchUser(userId)
      .then((detail) => !cancelled && setUserDetail(detail))
      .catch(() => !cancelled && setUserDetail(null));
    return () => {
      cancelled = true;
    };
  }, [userId, topK, excludeSeen, model, coldStart, refreshToken]);

  const items = useMemo(() => sortItems(data?.recommendations ?? [], sortKey, translations), [data, sortKey, translations]);
  const isCustom = userId !== '' && !users.some((u) => u.user_id === userId);

  function submitCustom(event: React.FormEvent) {
    event.preventDefault();
    const id = customId.trim();
    if (id) setUserId(id);
  }

  if (initError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-extrabold">Recommendations</h1>
        <ErrorState error={initError} onRetry={init} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">Explainable short-video recommendations</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">
          Frozen KuaiRec 2.0 rankings served by the Go API. Every result shows its rank, English catalog metadata, score and the
          machine-readable evidence behind its explanation. The selected model is the validation-tuned hybrid (0.9 Item-CF, 0.1 popularity,
          0 LightGCN).
        </p>
      </header>

      <section
        aria-label="Recommendation controls"
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="user-select" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              Demo user
            </label>
            <select
              id="user-select"
              className={control}
              value={isCustom ? '' : userId}
              onChange={(e) => e.target.value && setUserId(e.target.value)}
            >
              {isCustom && <option value="">Custom ID: {userId}</option>}
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id} ({statusLabel(u)})
                </option>
              ))}
            </select>
          </div>
          <form onSubmit={submitCustom} className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="custom-user" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
                Or enter any user ID
              </label>
              <input
                id="custom-user"
                className={`${control} w-40`}
                value={customId}
                onChange={(e) => setCustomId(e.target.value)}
                placeholder="e.g. 0 or new-user"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700 dark:bg-indigo-600"
            >
              Load
            </button>
          </form>
          <div className="flex flex-col gap-1">
            <label htmlFor="model-select" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              Model (this request only)
            </label>
            <select id="model-select" className={control} value={model} onChange={(e) => setModel(e.target.value)}>
              {(manifest?.models ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {MODEL_LABELS[m.id] ?? m.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="topk-select" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              Top-K
            </label>
            <select id="topk-select" className={control} value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
              {TOP_K_OPTIONS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="sort-select" className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              Sort shown results
            </label>
            <select id="sort-select" className={control} value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
              <option value="rank">Model rank</option>
              <option value="score">Score (high → low)</option>
              <option value="popularity">Positive training events</option>
              <option value="category">Category (A → Z)</option>
            </select>
          </div>
          <button
            type="button"
            onClick={() => setRefreshToken((n) => n + 1)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>
        <div className="flex flex-wrap gap-6">
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={coldStart} onChange={(e) => setColdStart(e.target.checked)} className="h-4 w-4" />
            Cold-start view (popularity fallback)
          </label>
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={excludeSeen} onChange={(e) => setExcludeSeen(e.target.checked)} className="h-4 w-4" />
            Exclude already-seen videos
          </label>
        </div>
        {model !== SELECTED && (
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Non-selected models serve their saved validation-time lists, which are exported for the demo users only.
          </p>
        )}
      </section>

      {data && !loading && <StateBanner message={describeUserState(data)} />}

      {data && !loading && (
        <p className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-slate-600 dark:text-slate-400" aria-live="polite">
          <span>
            model: <strong className="text-slate-900 dark:text-slate-100">{data.model}</strong>
          </span>
          <span>split: {data.artifact_split}</span>
          <span>fallback: {data.fallback ? 'yes' : 'no'}</span>
          <span>results: {data.top_k}</span>
          <span>engine latency: {data.latency_ms.toFixed(3)} ms</span>
          <span>generated: {new Date(data.generated_at).toLocaleTimeString()}</span>
        </p>
      )}

      {error ? <ErrorState error={error} onRetry={() => setRefreshToken((n) => n + 1)} /> : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          {loading ? (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading recommendations">
              {Array.from({ length: Math.min(topK, 6) }).map((_, idx) => (
                <SkeletonCard key={idx} />
              ))}
            </div>
          ) : items.length > 0 ? (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((item) => (
                <VideoCard key={item.item_id} item={item} userId={data!.user_id} modelId={data!.model} />
              ))}
            </div>
          ) : (
            !error && <EmptyState>No recommendations match these filters for this user.</EmptyState>
          )}
        </div>
        <aside className="space-y-6">
          {data && !data.fallback && data.recommendations.some((i) => i.components) && (
            <HybridPanel manifest={manifest} items={data.recommendations} />
          )}
          {userDetail ? (
            <UserHistoryPanel user={userDetail} />
          ) : (
            data?.user_status === 'unknown' && <EmptyState>No history: user {data.user_id} is not in the training data.</EmptyState>
          )}
        </aside>
      </div>
    </div>
  );
}
