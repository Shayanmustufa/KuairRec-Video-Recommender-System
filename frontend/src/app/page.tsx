'use client';

import React, { useEffect, useState } from 'react';
import { 
  fetchRecommendations, 
  fetchDemoUsers, 
  fetchModelManifest, 
  switchActiveModel 
} from '@/lib/api';
import { RecommendationResponse, DemoUser, ModelManifest } from '@/types';
import { VideoCard } from '@/components/VideoCard';
import { SkeletonCard } from '@/components/SkeletonLoader';

export default function HomePage() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('user_1001');
  const [topK, setTopK] = useState<number>(10);
  const [excludeSeen, setExcludeSeen] = useState<boolean>(true);
  const [isColdStartSimulated, setIsColdStartSimulated] = useState<boolean>(false);
  
  const [manifest, setManifest] = useState<ModelManifest | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('hybrid-v1');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [recData, setRecData] = useState<RecommendationResponse | null>(null);

  // Load demo users and model manifest
  useEffect(() => {
    async function init() {
      try {
        const [uList, mData] = await Promise.all([
          fetchDemoUsers(),
          fetchModelManifest().catch(() => null),
        ]);
        setUsers(uList);
        if (mData) {
          setManifest(mData);
          setSelectedModel(mData.current_model || 'hybrid-v1');
        }
      } catch (err) {
        console.error('Initialization error:', err);
      }
    }
    init();
  }, []);

  // Fetch recommendations whenever controls change
  useEffect(() => {
    async function loadRecs() {
      setLoading(true);
      setError(null);

      const targetUserId = isColdStartSimulated ? 'user_cold_start' : selectedUser;

      try {
        const resp = await fetchRecommendations(targetUserId, topK, excludeSeen);
        setRecData(resp);
      } catch (err: any) {
        setError(err.message || 'Failed to load recommendations');
        setRecData(null);
      } finally {
        setLoading(false);
      }
    }

    loadRecs();
  }, [selectedUser, topK, excludeSeen, isColdStartSimulated, selectedModel]);

  // Handle model switch
  const handleModelChange = async (newModel: string) => {
    try {
      setSelectedModel(newModel);
      await switchActiveModel(newModel);
      const resp = await fetchRecommendations(
        isColdStartSimulated ? 'user_cold_start' : selectedUser, 
        topK, 
        excludeSeen
      );
      setRecData(resp);
    } catch (err: any) {
      console.error('Failed to switch model:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Hero */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 dark:from-slate-900 dark:via-indigo-950/80 dark:to-slate-950 rounded-2xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden border border-transparent dark:border-slate-800">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-medium mb-3">
            <span>⚡ Go Chi / Fast API Backend</span>
            <span>•</span>
            <span>Next.js App Router</span>
            <span>•</span>
            <span>Evidence-Based Reason Codes</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Personalized Short-Video Recommendation Feed
          </h1>
          <p className="mt-2 text-slate-300 text-sm sm:text-base leading-relaxed">
            Live evaluation sandbox displaying real-time ranking scores, collaborative filtering signals,
            LightGCN graph embeddings, and verifiable reason codes from the KuaiRec benchmark.
          </p>
        </div>
      </div>

      {/* Control Panel / Toolbar */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-4 transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Select User Profile:
            </label>
            <select
              value={isColdStartSimulated ? 'user_cold_start' : selectedUser}
              onChange={(e) => {
                if (e.target.value === 'user_cold_start') {
                  setIsColdStartSimulated(true);
                } else {
                  setIsColdStartSimulated(false);
                  setSelectedUser(e.target.value);
                }
              }}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id} ({u.is_cold_start ? 'Cold Start / New User' : `${u.interaction_count} past videos`})
                </option>
              ))}
              <option value="custom_unseen_user">custom_unseen_user (Unknown User Test)</option>
            </select>
          </div>

          <div className="flex items-center gap-4">
            {/* Cold Start Simulator Toggle */}
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isColdStartSimulated}
                onChange={(e) => setIsColdStartSimulated(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded border-slate-300 dark:border-slate-700 focus:ring-indigo-500"
              />
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Force Cold-Start Fallback</span>
            </label>

            {/* Exclude Seen Toggle */}
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={excludeSeen}
                onChange={(e) => setExcludeSeen(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded border-slate-300 dark:border-slate-700 focus:ring-indigo-500"
              />
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Exclude Already Seen</span>
            </label>
          </div>
        </div>

        {/* Second Row: Model & Top-K Controls */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">Active Model:</span>
            <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 p-1">
              {[
                { id: 'popularity-v1', label: 'Popularity' },
                { id: 'itemcf-v1', label: 'Item-CF' },
                { id: 'lightgcn-v1', label: 'LightGCN' },
                { id: 'hybrid-v1', label: 'Hybrid (Best)' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => handleModelChange(m.id)}
                  className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                    selectedModel === m.id
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">Top-K:</span>
            {[5, 10, 15, 20].map((k) => (
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
      </div>

      {/* Status Bar */}
      {recData && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-500 dark:text-slate-400 font-mono">
          <div className="flex items-center gap-3">
            <span>
              Serving Model: <strong className="text-slate-800 dark:text-slate-200">{recData.model}</strong>
            </span>
            <span>•</span>
            <span>
              Fallback Triggered: <strong className={recData.fallback ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
                {recData.fallback ? 'YES (Cold Start Baseline)' : 'NO (Personalized)'}
              </strong>
            </span>
          </div>
          <div className="flex items-center gap-3">
            {recData.latency_ms !== undefined && (
              <span>Engine Latency: <strong className="text-slate-800 dark:text-slate-200">{recData.latency_ms.toFixed(2)} ms</strong></span>
            )}
            <span>Generated: {new Date(recData.generated_at).toLocaleTimeString()}</span>
          </div>
        </div>
      )}

      {/* Main Recommendations Grid */}
      {error && (
        <div className="p-6 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 rounded-xl text-rose-800 dark:text-rose-200 text-sm">
          <p className="font-bold">Error loading recommendations</p>
          <p className="mt-1">{error}</p>
          <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">Ensure the API backend is running on port 8080.</p>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: topK }).map((_, idx) => (
            <SkeletonCard key={idx} />
          ))}
        </div>
      ) : recData && recData.recommendations.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {recData.recommendations.map((item) => (
            <VideoCard
              key={item.item_id}
              item={item}
              userId={recData.user_id}
              modelId={recData.model}
            />
          ))}
        </div>
      ) : (
        !error && (
          <div className="text-center py-16 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
            <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">No candidates available for this filter combination.</p>
          </div>
        )
      )}
    </div>
  );
}
