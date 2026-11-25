// Types mirror the Go API contract in docs/API_SPEC.md.

export interface VideoItem {
  item_id: string;
  title: string;
  has_caption: boolean;
  category: string;
  categories: string[];
  tags: string[];
  author_id: string;
  upload_date: string;
  video_type: string;
  duration_seconds: number | null;
  positive_training_events: number;
}

export type ReasonCode = 'similar_to_recent' | 'popular_in_training' | 'liked_by_similar_users' | 'extension_model_match' | 'cold_start';

export interface ExplanationReason {
  code: ReasonCode | string;
  text: string;
  evidence: Record<string, string | number | boolean>;
}

export interface Component {
  normalized_score: number;
  weight: number;
  contribution: number;
}

export interface RecommendedItem {
  item_id: string;
  rank: number;
  score: number;
  source: string;
  video?: VideoItem;
  components?: Record<string, Component>;
  reasons: ExplanationReason[];
}

export type UserStatus = 'known' | 'no_positive_history' | 'unknown';

export interface RecommendationResponse {
  user_id: string;
  model: string;
  top_k: number;
  recommendations: RecommendedItem[];
  fallback: boolean;
  fallback_reason?: 'unknown_user' | 'no_positive_history' | 'cold_start_requested';
  user_status: UserStatus;
  artifact_split: 'test' | 'validation' | 'train';
  exclude_seen: boolean;
  generated_at: string;
  latency_ms: number;
}

export interface RecommendationRequest {
  user_id: string;
  top_k: number;
  exclude_seen: boolean;
  model?: string;
  force_cold_start?: boolean;
  candidate_ids?: string[] | null;
}

export interface ModelMetrics {
  recall_at_10: number;
  recall_at_20: number;
  ndcg_at_10: number;
  ndcg_at_20: number;
  hit_rate_at_10: number;
  hit_rate_at_20: number;
  precision_at_10: number;
  precision_at_20: number;
  catalog_coverage: number;
}

export interface ModelMeta {
  id: string;
  name: string;
  type: string;
  description: string;
  is_fallback: boolean;
  status: 'baseline' | 'rejected' | 'selected' | string;
  weights?: { alpha_cf?: number; beta_extension?: number; gamma_popularity?: number };
  metrics: ModelMetrics;
}

export interface ReasonRule {
  code: string;
  enabled: boolean;
  description: string;
  required_evidence: string[];
}

export interface ModelManifest {
  manifest_version: string;
  generated_at: string;
  source_model_manifest_generated_at?: string;
  dataset_release: Record<string, string | number>;
  current_model: string;
  fallback_model: string;
  active_default_model?: string;
  selected_weights: Record<string, number>;
  models: ModelMeta[];
  serving: Record<string, Record<string, string | number>>;
  reason_code_rules: ReasonRule[];
  source_artifacts_sha256?: Record<string, string>;
  bundle_sha256?: Record<string, string>;
  bundle_verified_at_load: boolean;
}

export interface CompareColumn {
  model: string;
  recommendations: RecommendedItem[];
  empty_reason?: string;
}

export interface CompareResponse {
  user_id: string;
  user_status: UserStatus;
  top_k: number;
  artifact_split: string;
  candidates: string;
  models: Record<string, CompareColumn>;
}

export interface DemoUser {
  user_id: string;
  status: UserStatus;
  positive_history_items: number;
  seen_items: number;
}

export interface HistoryItem {
  item_id: string;
  timestamp: number;
  watch_ratio: number;
  video?: VideoItem;
}

export interface UserDetail {
  user_id: string;
  status: UserStatus;
  seen_items: number;
  positive_history_items: number;
  recent_positive: HistoryItem[];
  has_comparison_export: boolean;
}

export interface SimilarItem {
  item_id: string;
  score: number;
  video?: VideoItem;
}

export interface ControlledTest extends ModelMetrics {
  model_id: string;
  users_metric_eligible: number;
  users_without_eligible_relevant_item: number;
  all_user_evaluation_coverage: number;
  behavior_checks: Record<string, number | boolean | string>;
  runtime_seconds: number;
  runtime_environment: Record<string, string>;
}

export interface OfflineMetrics {
  evaluation_protocol: Record<string, string | number>;
  validation_metrics: ModelMeta[];
  controlled_test: ControlledTest;
}

export interface ReadyResponse {
  status: 'ready' | 'not_ready';
  checks: Record<string, string>;
  database_kind: string;
  catalog_items: number;
  known_users: number;
  default_model: string;
  server_time: string;
}

export interface TelemetrySnapshot {
  uptime_seconds: number;
  total_requests: number;
  responses_2xx: number;
  responses_4xx: number;
  responses_5xx: number;
  rate_limited: number;
  recommendations_served: number;
  fallback_responses: number;
  feedback_events_total: number;
  average_latency_ms: number;
  feedback_by_action: Record<string, number>;
  feedback_store_available: boolean;
  default_model: string;
}

export type FeedbackAction = 'click' | 'play' | 'skip' | 'hide';
