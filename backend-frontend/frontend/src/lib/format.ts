import type { RecommendationResponse, RecommendedItem } from '@/types';

export const MODEL_LABELS: Record<string, string> = {
  'popularity-positive-event-count-v1': 'Popularity',
  'item-cf-cosine-v1': 'Item-CF',
  'lightgcn-validation-selected-v1': 'LightGCN (rejected)',
  'hybrid-validation-selected-v1': 'Hybrid (selected)',
};

export const REASON_TITLES: Record<string, string> = {
  similar_to_recent: 'Similar to recent history',
  popular_in_training: 'Popular in training data',
  liked_by_similar_users: 'Collaborative filtering',
  extension_model_match: 'LightGCN score',
  cold_start: 'Cold-start fallback',
};

const EVIDENCE_LABELS: Record<string, string> = {
  source_video_id: 'source video',
  similarity: 'similarity',
  preference_strength: 'preference strength',
  contribution: 'contribution',
  item_cf_weight: 'Item-CF weight',
  positive_training_event_count: 'positive training events',
  popularity_weight: 'popularity weight',
  fallback_model_id: 'fallback model',
  user_status: 'user status',
  forced: 'requested',
  lightgcn_score: 'LightGCN score',
  lightgcn_weight: 'LightGCN weight in hybrid',
};

export function evidenceLabel(key: string): string {
  return EVIDENCE_LABELS[key] ?? key.replace(/_/g, ' ');
}

/** Formats evidence values: IDs and counts stay exact, real numbers get 3–4 significant digits. */
export function formatEvidenceValue(key: string, value: string | number | boolean): string {
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string') return value;
  if (key.endsWith('_id') || key.endsWith('_count') || Number.isInteger(value)) return value.toLocaleString('en-US');
  if (Math.abs(value) < 0.001 && value !== 0) return value.toExponential(2);
  return value.toFixed(Math.abs(value) < 1 ? 4 : 3);
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return 'not provided';
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

export type CatalogTranslations = Readonly<Record<string, string>>;
const HAN = new RegExp('\\p{Script=Han}', 'u');

export function englishCatalogText(value: string | undefined, translations: CatalogTranslations, missing: string, unavailable = 'English translation unavailable'): string {
  const source = value?.trim();
  if (!source) return missing;
  if (!HAN.test(source)) return source;
  const translated = translations[source]?.trim();
  return translated && !HAN.test(translated) ? translated : unavailable;
}

export function videoCategory(category: string | undefined, translations: CatalogTranslations): string {
  return englishCatalogText(category, translations, 'Uncategorised', 'Category translation unavailable');
}

export function videoTitle(item: { item_id: string; video?: { title: string } }, translations: CatalogTranslations = {}): string {
  return englishCatalogText(item.video?.title, translations, `Video ${item.item_id} (no official caption)`, `Video ${item.item_id} (English caption unavailable)`);
}

export type SortKey = 'rank' | 'score' | 'popularity' | 'category';

/** Client-side sort of an already-ranked list. Ranks are preserved so the
 * model's order stays visible; this only changes the display order. */
export function sortItems(items: RecommendedItem[], key: SortKey, translations: CatalogTranslations = {}): RecommendedItem[] {
  const copy = [...items];
  switch (key) {
    case 'score':
      return copy.sort((a, b) => b.score - a.score || a.rank - b.rank);
    case 'popularity':
      return copy.sort((a, b) => (b.video?.positive_training_events ?? 0) - (a.video?.positive_training_events ?? 0) || a.rank - b.rank);
    case 'category':
      return copy.sort((a, b) => videoCategory(a.video?.category, translations).localeCompare(videoCategory(b.video?.category, translations), 'en') || a.rank - b.rank);
    default:
      return copy.sort((a, b) => a.rank - b.rank);
  }
}

export interface StateMessage {
  tone: 'info' | 'warning';
  title: string;
  detail: string;
}

/** Explains the user state behind a response (WBS Day 9 no-history and unknown-user states). */
export function describeUserState(resp: RecommendationResponse): StateMessage {
  switch (resp.fallback_reason) {
    case 'unknown_user':
      return {
        tone: 'warning',
        title: `Unknown user “${resp.user_id}”`,
        detail: 'This ID is not in the training data, so the frozen training-only popularity ranking is shown as a cold-start fallback.',
      };
    case 'no_positive_history':
      return {
        tone: 'warning',
        title: 'No positive history',
        detail:
          'This user is known but has no positive (watch_ratio > 2.0) pre-test interactions, so personalised scores have no evidence; the popularity fallback is shown.',
      };
    case 'cold_start_requested':
      return {
        tone: 'info',
        title: 'Cold-start view requested',
        detail:
          'Showing the popularity fallback a new user would receive. Items this user has already seen are excluded when the history is available.',
      };
    default:
      return {
        tone: 'info',
        title: 'Personalised recommendations',
        detail:
          resp.artifact_split === 'test'
            ? 'Frozen controlled-test ranking from train + validation history. Feedback is stored but does not retrain the model.'
            : 'Validation-time ranking from training history only (used for model comparison).',
      };
  }
}

export function hybridTotals(items: RecommendedItem[]): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const item of items) {
    for (const [name, part] of Object.entries(item.components ?? {})) {
      totals[name] = (totals[name] ?? 0) + part.contribution;
    }
  }
  return totals;
}
