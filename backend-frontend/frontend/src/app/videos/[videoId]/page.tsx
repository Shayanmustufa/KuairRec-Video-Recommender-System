'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ApiError, fetchSimilarItems, fetchVideoDetails } from '@/lib/api';
import type { SimilarItem, VideoItem } from '@/types';
import { EmptyState, ErrorState, Loading } from '@/components/States';
import { formatDuration } from '@/lib/format';

const NOT_PROVIDED = 'not provided in the release';

export default function VideoDetailPage() {
  const params = useParams<{ videoId: string }>();
  const videoId = decodeURIComponent(params?.videoId ?? '');
  const [video, setVideo] = useState<VideoItem | null>(null);
  const [similar, setSimilar] = useState<SimilarItem[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [similarError, setSimilarError] = useState<unknown>(null);

  const load = useCallback(() => {
    if (!videoId) return;
    setError(null);
    setVideo(null);
    setSimilar(null);
    fetchVideoDetails(videoId)
      .then((v) => {
        setVideo(v);
        return fetchSimilarItems(videoId, 8).then(setSimilar).catch(setSimilarError);
      })
      .catch(setError);
  }, [videoId]);
  useEffect(load, [load]);

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm font-semibold text-indigo-700 hover:underline dark:text-indigo-300">
          ← Back to recommendations
        </Link>
        {notFound ? (
          <EmptyState>Video {videoId} is not in the eligible KuaiRec catalog.</EmptyState>
        ) : (
          <ErrorState error={error} onRetry={load} />
        )}
      </div>
    );
  }
  if (!video) return <Loading label={`Loading video ${videoId}…`} />;

  const facts: [string, string][] = [
    ['Video ID', video.item_id],
    ['Categories', video.categories.length ? video.categories.join(' › ') : NOT_PROVIDED],
    ['Topic tags', video.tags.length ? video.tags.join(', ') : NOT_PROVIDED],
    ['Author ID', video.author_id || NOT_PROVIDED],
    ['Upload date', video.upload_date || NOT_PROVIDED],
    ['Video type', video.video_type || NOT_PROVIDED],
    ['Duration', formatDuration(video.duration_seconds)],
    ['Positive training events', `${video.positive_training_events.toLocaleString('en-US')} (training events with watch_ratio > 2.0)`],
  ];

  return (
    <div className="space-y-8">
      <Link href="/" className="text-sm font-semibold text-indigo-700 hover:underline dark:text-indigo-300">
        ← Back to recommendations
      </Link>
      <article className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:grid-cols-3 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col justify-center bg-gradient-to-br from-slate-700 to-slate-900 p-8 text-white">
          <span className="w-fit rounded bg-indigo-600 px-2.5 py-1 text-xs font-bold uppercase">{video.category || 'Uncategorised'}</span>
          <h1 className="mt-4 text-xl font-extrabold leading-snug">{video.title || `Video ${video.item_id}`}</h1>
          {!video.has_caption && <p className="mt-2 text-xs text-slate-300">The release has no caption for this video.</p>}
        </div>
        <div className="p-8 md:col-span-2">
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">Official catalog metadata</h2>
          <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
            {facts.map(([label, value]) => (
              <React.Fragment key={label}>
                <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
                <dd className="break-words">{value}</dd>
              </React.Fragment>
            ))}
          </dl>
          <p className="mt-4 text-xs text-slate-600 dark:text-slate-400">
            Metadata comes from <code>kuairec_caption_category.csv</code> and the first daily row of <code>item_daily_features.csv</code>. A
            positive interaction in this project means <strong>watch_ratio &gt; 2.0</strong> — a derived proxy, not an official like label.
          </p>
        </div>
      </article>

      <section aria-labelledby="similar-heading" className="space-y-3">
        <h2 id="similar-heading" className="text-lg font-bold">
          Similar items (Item-CF)
        </h2>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          Nearest neighbours in the frozen Item-CF cosine similarity matrix, trained on positive training interactions only.
        </p>
        {similarError ? (
          <ErrorState error={similarError} onRetry={load} />
        ) : similar === null ? (
          <Loading label="Loading neighbours…" />
        ) : similar.length === 0 ? (
          <EmptyState>This video has no Item-CF neighbours (no positive co-occurrence in training).</EmptyState>
        ) : (
          <ol className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {similar.map((item) => (
              <li
                key={item.item_id}
                className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
                    {item.video?.category || 'Uncategorised'}
                  </span>
                  <h3 className="mt-1 line-clamp-2 text-sm font-bold">{item.video?.title || `Video ${item.item_id}`}</h3>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
                  <span className="font-mono">cosine {item.score.toFixed(4)}</span>
                  <Link
                    href={`/videos/${encodeURIComponent(item.item_id)}`}
                    className="font-semibold text-indigo-700 hover:underline dark:text-indigo-300"
                  >
                    Open →
                  </Link>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
