import React from 'react';

export const SkeletonCard: React.FC = () => {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-pulse flex flex-col justify-between">
      <div>
        <div className="h-36 bg-slate-200 dark:bg-slate-800" />
        <div className="p-4 space-y-3">
          <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-3/4" />
          <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-1/2" />
          <div className="space-y-1.5 pt-2">
            <div className="h-10 bg-slate-100 dark:bg-slate-800/60 rounded-lg" />
            <div className="h-10 bg-slate-100 dark:bg-slate-800/60 rounded-lg" />
          </div>
        </div>
      </div>
      <div className="p-4 pt-0">
        <div className="h-8 bg-slate-100 dark:bg-slate-800/60 rounded" />
      </div>
    </div>
  );
};
