'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchVideoDetails, fetchSimilarItems } from '@/lib/api';
import { VideoItem, SimilarItem } from '@/types';

export default function VideoDetailPage() {
  const params = useParams();
  const videoId = params?.videoId as string;

  const [video, setVideo] = useState<VideoItem | null>(null);
  const [similarItems, setSimilarItems] = useState<SimilarItem[]>([]);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      if (!videoId) return;
      try {
        setLoading(true);
        const v = await fetchVideoDetails(videoId);
        setVideo(v);
        try {
          const neighbors = await fetchSimilarItems(videoId, 5);
          setSimilarItems(neighbors);
          setSimilarError(null);
        } catch (similarErr: any) {
          setSimilarError(similarErr.message || 'Similar videos are unavailable');
        }
      } catch (err: any) {
        setError(err.message || 'Video not found');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [videoId]);

  if (loading) {
    return (
      <div className="py-16 text-center text-slate-500 dark:text-slate-400 font-mono animate-pulse">
        Loading video metadata and similarity index for {videoId}...
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="p-8 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 rounded-xl text-rose-800 dark:text-rose-200">
        <h2 className="font-bold text-lg">Video Not Found</h2>
        <p className="mt-2 text-sm">{error || 'Requested video could not be located in the catalog index.'}</p>
        <Link href="/" className="mt-4 inline-block font-semibold text-indigo-600 dark:text-indigo-400 hover:underline text-sm">
          ← Return to Recommendation Feed
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Back button */}
      <div>
        <Link href="/" className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 flex items-center gap-1">
          ← Back to All Recommendations
        </Link>
      </div>

      {/* Main Video Details Card */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden grid grid-cols-1 md:grid-cols-3 transition-colors">
        {/* Visual Preview Banner */}
        <div className="md:col-span-1 bg-gradient-to-br from-slate-900 to-indigo-950 p-8 flex flex-col justify-between text-white">
          <div>
            <span className="bg-indigo-600 text-white text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded">
              {video.category}
            </span>
            <h1 className="mt-4 text-xl font-extrabold leading-snug">{video.title}</h1>
            <p className="mt-2 text-xs font-mono text-indigo-300">Catalog ID: {video.item_id}</p>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-700/60 space-y-2 text-xs text-slate-300 font-mono">
            <div className="flex justify-between">
              <span>Author ID:</span>
              <span className="font-semibold text-white">{video.author_id}</span>
            </div>
            <div className="flex justify-between">
              <span>Duration:</span>
              <span className="font-semibold text-white">{video.duration_seconds} seconds</span>
            </div>
            <div className="flex justify-between">
              <span>Total Views:</span>
              <span className="font-semibold text-white">{video.total_views.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Avg Watch Ratio:</span>
              <span className="font-semibold text-emerald-400">{(video.watch_ratio_avg * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Video Technical Metadata & Semantics */}
        <div className="md:col-span-2 p-8 flex flex-col justify-between">
          <div className="space-y-6">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Official Catalog Tags</h2>
              <div className="flex flex-wrap gap-2 mt-2">
                {video.tags.map((tag, i) => (
                  <span key={i} className="px-3 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-full">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Engagement Protocol</h2>
              <p className="mt-2 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                Under the KuaiRec evaluation protocol, this item qualifies as a <strong>positive interaction</strong>{' '}
                when a user completes at least 100% of the video duration (watch ratio &ge; 1.0). The recorded average
                completion ratio for this item in the training set is <strong>{video.watch_ratio_avg.toFixed(2)}x</strong>.
              </p>
            </div>

            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Category Relevance</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Videos in the <span className="font-bold text-slate-900 dark:text-slate-100">{video.category}</span> cluster exhibit strong intra-category
                collaborative filtering co-occurrence within user viewing sessions.
              </p>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
            <span>Uploaded: {new Date(video.upload_date).toLocaleDateString()}</span>
            <span>Dataset: KuaiRec Official Release v2.0</span>
          </div>
        </div>
      </div>

      {/* Similar Items Section */}
      <div className="space-y-4">
        <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Items Co-Engaged with This Video</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Ranked by the frozen Item-CF cosine similarity artifact trained on positive training interactions.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {similarError && <p className="text-sm text-rose-600">{similarError}</p>}
          {!similarError && similarItems.length === 0 && <p className="text-sm text-slate-500">No Item-CF neighbors are available for this video.</p>}
          {similarItems.map((item) => (
            <div key={item.item_id} className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between transition-colors">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-600 dark:text-indigo-400">
                  {item.video?.category || 'Video'}
                </span>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white mt-1 line-clamp-2">
                  {item.video?.title || item.item_id}
                </h3>
                <div className="mt-3 flex flex-col gap-1">
                  <span className="text-xs text-slate-500 dark:text-slate-400">Item-CF similarity</span>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">Similarity: {item.score.toFixed(3)}</span>
                <Link
                  href={`/videos/${item.item_id}`}
                  className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300"
                >
                  View Details →
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
