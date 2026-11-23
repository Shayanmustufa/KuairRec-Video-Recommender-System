import { 
  RecommendationResponse, 
  ModelManifest, 
  CompareResponse, 
  DemoUser, 
  VideoItem 
} from '@/types';

const API_BASE = typeof window !== 'undefined' ? '' : (process.env.API_INTERNAL_URL || 'http://127.0.0.1:8080');

export async function fetchRecommendations(
  userId: string, 
  topK: number = 10, 
  excludeSeen: boolean = true
): Promise<RecommendationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      top_k: topK,
      exclude_seen: excludeSeen,
    }),
    cache: 'no-store',
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to fetch recommendations (${res.status}): ${errorBody}`);
  }

  return res.json();
}

export async function postFeedback(
  userId: string, 
  itemId: string, 
  action: 'click' | 'play' | 'skip' | 'hide',
  modelId: string
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      item_id: itemId,
      action: action,
      model_id: modelId,
    }),
  });

  if (!res.ok) {
    throw new Error('Failed to record feedback');
  }

  return res.json();
}

export async function fetchModelManifest(): Promise<ModelManifest> {
  const res = await fetch(`${API_BASE}/api/v1/models/current`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch model manifest');
  return res.json();
}

export async function switchActiveModel(modelId: string): Promise<{ status: string; current_model: string }> {
  const res = await fetch(`${API_BASE}/api/v1/models/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId }),
  });
  if (!res.ok) throw new Error('Failed to switch model');
  return res.json();
}

export async function fetchComparison(userId: string, topK: number = 5): Promise<CompareResponse> {
  const res = await fetch(`${API_BASE}/api/v1/compare?user_id=${encodeURIComponent(userId)}&top_k=${topK}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch model comparison');
  return res.json();
}

export async function fetchDemoUsers(): Promise<DemoUser[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/users`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    return data.users;
  } catch (err) {
    return [
      { user_id: 'user_1001', interaction_count: 3, is_cold_start: false },
      { user_id: 'user_1002', interaction_count: 3, is_cold_start: false },
      { user_id: 'user_1003', interaction_count: 3, is_cold_start: false },
      { user_id: 'user_cold_start', interaction_count: 0, is_cold_start: true },
    ];
  }
}

export async function fetchVideoDetails(videoId: string): Promise<VideoItem> {
  const res = await fetch(`${API_BASE}/api/v1/videos/${videoId}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Video not found: ${videoId}`);
  return res.json();
}

export async function fetchOfflineMetrics(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/metrics/offline`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch offline metrics');
  return res.json();
}

export async function checkHealth(): Promise<{ status: string; latency: number }> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/healthz`, { cache: 'no-store' });
    const latency = Date.now() - start;
    if (res.ok) return { status: 'healthy', latency };
    return { status: 'degraded', latency };
  } catch {
    return { status: 'unreachable', latency: -1 };
  }
}

export async function fetchTelemetryMetrics(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/metrics-api`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
