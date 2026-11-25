'use client';

import React from 'react';
import { ExplanationReason } from '@/types';

interface Props {
  reason: ExplanationReason;
}

export const ReasonBadge: React.FC<Props> = ({ reason }) => {
  const getBadgeStyle = (code: string) => {
    switch (code) {
      case 'similar_to_recent':
        return 'bg-blue-100 text-blue-900 border-blue-200 dark:bg-blue-950/70 dark:text-blue-200 dark:border-blue-800';
      case 'popular_in_training':
        return 'bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:border-amber-800';
      case 'liked_by_similar_users':
        return 'bg-purple-100 text-purple-900 border-purple-200 dark:bg-purple-950/70 dark:text-purple-200 dark:border-purple-800';
      case 'extension_model_match':
        return 'bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-950/70 dark:text-emerald-200 dark:border-emerald-800';
      case 'cold_start':
        return 'bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-950/70 dark:text-rose-200 dark:border-rose-800';
      default:
        return 'bg-slate-100 text-slate-900 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700';
    }
  };

  const getCodeTitle = (code: string) => {
    switch (code) {
      case 'similar_to_recent':
        return 'Item Similarity';
      case 'popular_in_training':
        return 'Trending';
      case 'liked_by_similar_users':
        return 'Collaborative';
      case 'extension_model_match':
        return 'LightGCN Graph';
      case 'cold_start':
        return 'Cold-Start Fallback';
      default:
        return code;
    }
  };

  return (
    <div className={`text-xs px-2.5 py-1.5 rounded-lg border flex flex-col gap-0.5 shadow-sm transition-colors ${getBadgeStyle(reason.code)}`}>
      <div className="flex items-center gap-1 font-semibold uppercase tracking-wider text-[10px]">
        <span>●</span>
        <span>{getCodeTitle(reason.code)}</span>
      </div>
      <p className="text-[11px] leading-tight font-medium text-slate-800 dark:text-slate-100">{reason.text}</p>
      {reason.evidence && (
        <div className="mt-1 pt-1 border-t border-black/10 dark:border-white/10 flex flex-wrap gap-2 text-[10px] text-slate-600 dark:text-slate-300 font-mono">
          {Object.entries(reason.evidence).map(([k, v]) => (
            <span key={k}>
              {k}: <strong className="text-slate-900 dark:text-white">{typeof v === 'number' ? v.toFixed(3) : String(v)}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
