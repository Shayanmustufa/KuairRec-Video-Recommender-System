import React from 'react';
import { describeError } from '@/lib/api';
import type { StateMessage } from '@/lib/format';

/** Error state that distinguishes timeout, backend-unavailable and HTTP errors. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, detail } = describeError(error);
  return (
    <div
      role="alert"
      className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-100"
    >
      <p className="font-bold">{title}</p>
      <p className="mt-1">{detail}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg bg-rose-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-800"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function StateBanner({ message }: { message: StateMessage }) {
  const tone =
    message.tone === 'warning'
      ? 'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100'
      : 'border-indigo-200 bg-indigo-50 text-indigo-950 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-100';
  return (
    <div role="status" className={`rounded-xl border p-4 text-sm ${tone}`} data-testid="state-banner">
      <p className="font-bold">{message.title}</p>
      <p className="mt-0.5">{message.detail}</p>
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
      {children}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p role="status" aria-live="polite" className="py-12 text-center font-mono text-sm text-slate-500 dark:text-slate-400">
      {label}
    </p>
  );
}
