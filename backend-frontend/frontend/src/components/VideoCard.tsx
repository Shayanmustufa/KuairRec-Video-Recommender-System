'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import type { FeedbackAction, RecommendedItem } from '@/types';
import { ReasonBadge } from './ReasonBadge';
import { ScoreBreakdown } from './ScoreBreakdown';
import { describeError, postFeedback } from '@/lib/api';
import { formatDuration, videoTitle } from '@/lib/format';

interface Props {
  item: RecommendedItem;
  userId: string;
  modelId: string;
}

const ACTIONS: { action: FeedbackAction; label: string }[] = [
  { action: 'play', label: 'Play' },
  { action: 'click', label: 'Click' },
  { action: 'skip', label: 'Skip' },
  { action: 'hide', label: 'Hide' },
];

/** Recommendation card: rank, official metadata, score, explanation and feedback (WBS §8). */
export function VideoCard({ item, userId, modelId }: Props) {
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const video = item.video;
  const title = videoTitle(item);

  async function send(action: FeedbackAction) {
    setBusy(true);
    try {
      await postFeedback(userId, item.item_id, action, modelId, item.rank);
      setStatus({ ok: true, text: `Recorded “${action}”` });
    } catch (err) {
      setStatus({ ok: false, text: describeError(err).title });
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      aria-labelledby={`title-${item.item_id}`}
      className="flex flex-col justify-between overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
      data-testid="recommendation-card"
    >
      <div>
        {/* Neutral placeholder: the release has no thumbnails, so none are invented (WBS §8). */}
        <div className="relative flex h-32 flex-col items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900 p-4 text-center text-white">
          <span className="absolute left-2 top-2 rounded bg-indigo-600 px-2 py-0.5 text-xs font-bold">Rank #{item.rank}</span>
          <span className="absolute right-2 top-2 rounded bg-black/60 px-2 py-0.5 font-mono text-[11px]">
            score {item.score.toFixed(3)}
          </span>
          <span className="text-xs font-semibold uppercase tracking-wide text-indigo-200">{video?.category || 'Uncategorised'}</span>
          <p id={`title-${item.item_id}`} className="mt-1 line-clamp-2 px-2 text-sm font-bold">
            {title}
          </p>
        </div>
        <div className="flex flex-col gap-3 p-4">
          <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-slate-600 dark:text-slate-300">
            <dt>Video ID</dt>
            <dd className="font-mono text-slate-900 dark:text-slate-100">{item.item_id}</dd>
            <dt>Duration</dt>
            <dd>{formatDuration(video?.duration_seconds)}</dd>
            <dt>Positive training events</dt>
            <dd>{video ? video.positive_training_events.toLocaleString('en-US') : '—'}</dd>
            <dt>Source</dt>
            <dd className="break-all font-mono">{item.source}</dd>
          </dl>
          {item.components && <ScoreBreakdown components={item.components} total={item.score} />}
          <div className="flex flex-col gap-1.5">
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Why recommended</h3>
            {item.reasons.map((reason, idx) => (
              <ReasonBadge key={`${reason.code}-${idx}`} reason={reason} />
            ))}
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-2 border-t border-slate-100 p-4 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <Link
            href={`/videos/${encodeURIComponent(item.item_id)}`}
            className="text-xs font-semibold text-indigo-700 hover:underline dark:text-indigo-300"
          >
            Video details →
          </Link>
          <span
            role="status"
            aria-live="polite"
            className={`text-xs font-semibold ${status?.ok === false ? 'text-rose-600' : 'text-emerald-600 dark:text-emerald-400'}`}
          >
            {status?.text}
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1.5" role="group" aria-label={`Feedback for video ${item.item_id}`}>
          {ACTIONS.map(({ action, label }) => (
            <button
              key={action}
              type="button"
              onClick={() => send(action)}
              disabled={busy}
              aria-label={`${label} video ${item.item_id}`}
              className="rounded bg-slate-100 px-1 py-1.5 text-[11px] font-medium text-slate-800 hover:bg-slate-200 disabled:opacity-50 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}
