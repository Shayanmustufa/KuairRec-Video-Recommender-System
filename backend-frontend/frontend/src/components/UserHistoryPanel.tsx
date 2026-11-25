import React from 'react';
import Link from 'next/link';
import type { UserDetail } from '@/types';

/** Evidence panel: the user's history summary and most recent positive videos,
 * which are the inputs the Item-CF reasons point to. */
export function UserHistoryPanel({ user }: { user: UserDetail }) {
  return (
    <section
      aria-labelledby="history-heading"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 id="history-heading" className="text-base font-bold">
        Recommendation evidence — user {user.user_id}
      </h2>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        {user.seen_items.toLocaleString('en-US')} distinct videos seen before the test period;{' '}
        {user.positive_history_items.toLocaleString('en-US')} of them were positive (watch_ratio &gt; 2.0).
      </p>
      {user.recent_positive.length > 0 ? (
        <ol className="mt-3 space-y-1 text-xs">
          {user.recent_positive.map((event) => (
            <li key={`${event.item_id}-${event.timestamp}`} className="flex justify-between gap-2">
              <Link
                className="truncate text-indigo-700 underline dark:text-indigo-300"
                href={`/videos/${encodeURIComponent(event.item_id)}`}
              >
                {event.video?.title || `Video ${event.item_id}`}
              </Link>
              <span className="shrink-0 font-mono">
                {new Date(event.timestamp * 1000).toISOString().slice(0, 10)} · ratio {event.watch_ratio.toFixed(2)}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
          {user.positive_history_items === 0
            ? 'No positive history is recorded for this user.'
            : 'The list of recent positive videos is exported for the 100 demo users only; each reason card links its source video.'}
        </p>
      )}
    </section>
  );
}
