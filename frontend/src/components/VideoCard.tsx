'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { RecommendedItem } from '@/types';
import { ReasonBadge } from './ReasonBadge';
import { postFeedback } from '@/lib/api';

interface Props {
  item: RecommendedItem;
  userId: string;
  modelId: string;
}

export const VideoCard: React.FC<Props> = ({ item, userId, modelId }) => {
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const video = item.video;
  const title = video ? video.title : `KuaiRec Video #${item.item_id}`;
  const category = video ? video.category : 'General';
  const duration = video ? `${video.duration_seconds}s` : '30s';
  const views = video ? video.total_views.toLocaleString() : 'N/A';

  const handleAction = async (action: 'click' | 'play' | 'skip' | 'hide') => {
    try {
      setIsSubmitting(true);
      await postFeedback(userId, item.item_id, action, modelId);
      setFeedbackStatus(action);
      setTimeout(() => setFeedbackStatus(null), 3000);
    } catch (err) {
      console.error('Feedback error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-md transition-all duration-200 overflow-hidden flex flex-col justify-between">
      <div>
        {/* Placeholder Video Thumbnail with Category Banner */}
        <div className="relative h-36 bg-gradient-to-br from-slate-800 to-slate-950 flex flex-col items-center justify-center p-4 text-white">
          <div className="absolute top-2 left-2 bg-indigo-600 text-white font-black text-xs px-2.5 py-1 rounded shadow">
            Rank #{item.rank}
          </div>
          <div className="absolute top-2 right-2 bg-black/60 text-slate-200 font-mono text-[11px] px-2 py-0.5 rounded">
            Score: {item.score.toFixed(3)}
          </div>
          
          <div className="text-center">
            <span className="text-xs uppercase tracking-widest text-indigo-300 font-semibold">{category}</span>
            <p className="font-bold text-sm mt-1 line-clamp-2 px-2 text-slate-100">{title}</p>
          </div>

          <div className="absolute bottom-2 left-2 right-2 flex justify-between text-[11px] text-slate-400">
            <span>⏱ {duration}</span>
            <span>👁 {views} views</span>
          </div>
        </div>

        {/* Card Body */}
        <div className="p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span className="font-mono text-slate-700 dark:text-slate-300">ID: {item.item_id}</span>
            <span className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded font-medium">Source: {item.source}</span>
          </div>

          {/* Explanation Reason Badges */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Why recommended:</span>
            {item.reasons.map((r, idx) => (
              <ReasonBadge key={idx} reason={r} />
            ))}
          </div>
        </div>
      </div>

      {/* Card Footer: Details Link & Feedback Buttons */}
      <div className="p-4 pt-0 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-2">
        <div className="flex items-center justify-between pt-3">
          <Link 
            href={`/videos/${item.item_id}`} 
            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 hover:underline"
          >
            Inspect Video Details →
          </Link>
          {feedbackStatus && (
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded animate-pulse">
              ✓ Logged: {feedbackStatus}
            </span>
          )}
        </div>

        {/* Feedback Action Buttons */}
        <div className="grid grid-cols-4 gap-1.5 mt-1">
          <button
            onClick={() => handleAction('play')}
            disabled={isSubmitting}
            className="text-[11px] font-medium py-1.5 px-1 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900 text-indigo-700 dark:text-indigo-300 rounded transition text-center"
            title="Mark as played"
          >
            ▶ Play
          </button>
          <button
            onClick={() => handleAction('click')}
            disabled={isSubmitting}
            className="text-[11px] font-medium py-1.5 px-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded transition text-center"
            title="Mark as clicked"
          >
            👆 Click
          </button>
          <button
            onClick={() => handleAction('skip')}
            disabled={isSubmitting}
            className="text-[11px] font-medium py-1.5 px-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded transition text-center"
            title="Skip item"
          >
            ⏭ Skip
          </button>
          <button
            onClick={() => handleAction('hide')}
            disabled={isSubmitting}
            className="text-[11px] font-medium py-1.5 px-1 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 dark:hover:bg-rose-900 text-rose-700 dark:text-rose-300 rounded transition text-center"
            title="Hide recommendation"
          >
            ✕ Hide
          </button>
        </div>
      </div>
    </div>
  );
};
