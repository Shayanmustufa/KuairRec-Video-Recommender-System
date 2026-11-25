import React from 'react';
import Link from 'next/link';
import type { ExplanationReason } from '@/types';
import { REASON_TITLES, evidenceLabel, formatEvidenceValue } from '@/lib/format';

const STYLES: Record<string, string> = {
  similar_to_recent: 'bg-blue-50 text-blue-950 border-blue-200 dark:bg-blue-950/60 dark:text-blue-100 dark:border-blue-800',
  popular_in_training: 'bg-amber-50 text-amber-950 border-amber-200 dark:bg-amber-950/60 dark:text-amber-100 dark:border-amber-800',
  liked_by_similar_users:
    'bg-violet-50 text-violet-950 border-violet-200 dark:bg-violet-950/60 dark:text-violet-100 dark:border-violet-800',
  extension_model_match:
    'bg-emerald-50 text-emerald-950 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-100 dark:border-emerald-800',
  cold_start: 'bg-rose-50 text-rose-950 border-rose-200 dark:bg-rose-950/60 dark:text-rose-100 dark:border-rose-800',
};

/** Shows one reason with its machine-readable evidence (WBS §6). */
export function ReasonBadge({ reason }: { reason: ExplanationReason }) {
  const style =
    STYLES[reason.code] ?? 'bg-slate-50 text-slate-900 border-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700';
  const entries = Object.entries(reason.evidence ?? {});
  return (
    <div className={`rounded-lg border px-2.5 py-1.5 text-xs ${style}`} data-reason-code={reason.code}>
      <p className="font-semibold">
        {REASON_TITLES[reason.code] ?? reason.code} <code className="font-mono text-[10px] opacity-70">{reason.code}</code>
      </p>
      <p className="mt-0.5 leading-snug">{reason.text}</p>
      {entries.length > 0 && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 border-t border-black/10 pt-1 font-mono text-[10px] dark:border-white/10">
          {entries.map(([key, value]) => (
            <React.Fragment key={key}>
              <dt className="opacity-75">{evidenceLabel(key)}</dt>
              <dd className="font-semibold">
                {key === 'source_video_id' ? (
                  <Link className="underline" href={`/videos/${encodeURIComponent(String(value))}`}>
                    {String(value)}
                  </Link>
                ) : (
                  formatEvidenceValue(key, value)
                )}
              </dd>
            </React.Fragment>
          ))}
        </dl>
      )}
    </div>
  );
}
