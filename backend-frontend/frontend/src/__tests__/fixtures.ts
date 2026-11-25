import type { RecommendationResponse, RecommendedItem } from '@/types';

export const item = (overrides: Partial<RecommendedItem> = {}): RecommendedItem => ({
  item_id: '10',
  rank: 1,
  score: 0.9213,
  source: 'hybrid-validation-selected-v1',
  video: {
    item_id: '10',
    title: 'Test caption',
    has_caption: true,
    category: 'Comedy',
    categories: ['Comedy'],
    tags: [],
    author_id: '1',
    upload_date: '2020-01-01',
    video_type: 'NORMAL',
    duration_seconds: 12.5,
    positive_training_events: 1210,
  },
  components: {
    item_cf: { normalized_score: 1, weight: 0.9, contribution: 0.9 },
    lightgcn: { normalized_score: 0.36, weight: 0, contribution: 0 },
    popularity: { normalized_score: 0.2131, weight: 0.1, contribution: 0.02131 },
  },
  reasons: [
    {
      code: 'liked_by_similar_users',
      text: 'Recommended from collaborative patterns linked to your positive history.',
      evidence: { source_video_id: '3289', similarity: 0.0044, preference_strength: 4.5, contribution: 0.0199, item_cf_weight: 0.9 },
    },
    {
      code: 'popular_in_training',
      text: 'Popular in positive training interactions.',
      evidence: { positive_training_event_count: 1210, popularity_weight: 0.1 },
    },
  ],
  ...overrides,
});

export const response = (overrides: Partial<RecommendationResponse> = {}): RecommendationResponse => ({
  user_id: '0',
  model: 'hybrid-validation-selected-v1',
  top_k: 1,
  recommendations: [item()],
  fallback: false,
  user_status: 'known',
  artifact_split: 'test',
  exclude_seen: true,
  generated_at: '2026-11-25T00:00:00Z',
  latency_ms: 0.12,
  ...overrides,
});
