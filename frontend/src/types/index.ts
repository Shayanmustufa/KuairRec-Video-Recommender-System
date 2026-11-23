export interface VideoItem {
  item_id: string;
  title: string;
  category: string;
  duration_seconds: number;
  tags: string[];
  author_id: string;
  upload_date: string;
  watch_ratio_avg: number;
  total_views: number;
}

export interface ExplanationReason {
  code: string;
  text: string;
  evidence?: Record<string, any>;
}

export interface RecommendedItem {
  item_id: string;
  rank: number;
  score: number;
  source: string;
  video?: VideoItem;
  reasons: ExplanationReason[];
}

export interface RecommendationResponse {
  user_id: string;
  model: string;
  top_k: number;
  recommendations: RecommendedItem[];
  fallback: boolean;
  generated_at: string;
  latency_ms?: number;
}

export interface ModelMetrics {
  recall_at_10: number;
  recall_at_20?: number;
  ndcg_at_10: number;
  ndcg_at_20?: number;
  hit_rate_at_10: number;
  precision_at_10: number;
  catalog_coverage: number;
  cold_start_coverage?: number;
}

export interface ModelMeta {
  id: string;
  name: string;
  type: string;
  description: string;
  is_fallback: boolean;
  weights?: {
    alpha_cf?: number;
    beta_extension?: number;
    gamma_popularity?: number;
  };
  metrics: ModelMetrics;
}

export interface ModelManifest {
  manifest_version: string;
  generated_at: string;
  dataset_release: {
    name: string;
    paper: string;
    official_url: string;
    source_repo: string;
    protocol: string;
    target_definition: string;
  };
  current_model: string;
  models: ModelMeta[];
  reason_code_rules: Array<{
    code: string;
    description: string;
  }>;
}

export interface CompareResponse {
  user_id: string;
  top_k: number;
  models: Record<string, RecommendationResponse>;
}

export interface DemoUser {
  user_id: string;
  interaction_count: number;
  is_cold_start: boolean;
}
