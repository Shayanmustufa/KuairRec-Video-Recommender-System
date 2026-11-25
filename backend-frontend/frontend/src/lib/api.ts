import type {
  CompareResponse,
  DemoUser,
  FeedbackAction,
  ModelManifest,
  OfflineMetrics,
  ReadyResponse,
  RecommendationRequest,
  RecommendationResponse,
  SimilarItem,
  TelemetrySnapshot,
  UserDetail,
  VideoItem,
} from '@/types';

export const DEFAULT_TIMEOUT_MS = 8000;

export type ApiErrorKind = 'timeout' | 'unavailable' | 'http';

/** ApiError separates timeouts, an unreachable backend and HTTP errors so the
 * UI can show the correct state (WBS Day 9). */
export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    message: string,
    public readonly status?: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function describeError(error: unknown): { title: string; detail: string } {
  if (error instanceof ApiError) {
    switch (error.kind) {
      case 'timeout':
        return { title: 'The API did not respond in time', detail: error.message };
      case 'unavailable':
        return { title: 'Backend unavailable', detail: 'The recommendation API could not be reached. Check that the Go API is running.' };
      default:
        return {
          title: `Request failed (HTTP ${error.status})`,
          detail: error.requestId ? `${error.message} — request ID ${error.requestId}` : error.message,
        };
    }
  }
  return { title: 'Unexpected error', detail: error instanceof Error ? error.message : String(error) };
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(path, {
      cache: 'no-store',
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new ApiError('timeout', `No response after ${Math.round(timeoutMs / 1000)} s`);
    }
    throw new ApiError('unavailable', err instanceof Error ? err.message : 'Network error');
  } finally {
    clearTimeout(timer);
  }
  const requestId = res.headers.get('X-Request-ID') ?? undefined;
  if (!res.ok) {
    let message = res.statusText || 'Request failed';
    try {
      const body = await res.json();
      if (body && typeof body.error === 'string') message = body.error;
    } catch {
      /* non-JSON error body */
    }
    // Every Go API response carries X-Request-ID; a 5xx without it comes from
    // the Next.js proxy, which means the API process could not be reached.
    const proxyFailure = res.status >= 500 && !requestId;
    throw new ApiError(proxyFailure ? 'unavailable' : 'http', message, res.status, requestId);
  }
  return (await res.json()) as T;
}

export function fetchRecommendations(body: RecommendationRequest): Promise<RecommendationResponse> {
  return request('/api/v1/recommendations', { method: 'POST', body: JSON.stringify(body) });
}

export function postFeedback(userId: string, itemId: string, action: FeedbackAction, modelId: string, rank?: number) {
  return request<{ status: string }>('/api/v1/feedback', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, item_id: itemId, action, model_id: modelId, rank }),
  });
}

export const fetchModelManifest = () => request<ModelManifest>('/api/v1/models/current');

export const fetchComparison = (userId: string, topK = 5) =>
  request<CompareResponse>(`/api/v1/compare?user_id=${encodeURIComponent(userId)}&top_k=${topK}`);

export const fetchDemoUsers = async (): Promise<DemoUser[]> => (await request<{ users: DemoUser[] }>('/api/v1/users')).users;

export const fetchUser = (userId: string) => request<UserDetail>(`/api/v1/users/${encodeURIComponent(userId)}`);

export const fetchVideoDetails = (videoId: string) => request<VideoItem>(`/api/v1/videos/${encodeURIComponent(videoId)}`);

export const fetchSimilarItems = async (videoId: string, topK = 5): Promise<SimilarItem[]> =>
  (await request<{ similar_items: SimilarItem[] }>(`/api/v1/videos/${encodeURIComponent(videoId)}/similar?top_k=${topK}`)).similar_items;

export const fetchOfflineMetrics = () => request<OfflineMetrics>('/api/v1/metrics/offline');

export const fetchTelemetry = () => request<TelemetrySnapshot>('/metrics-api');

export const fetchReadiness = () => request<ReadyResponse>('/readyz', {}, 4000);

export async function checkHealth(): Promise<{ status: 'healthy' | 'degraded' | 'unreachable'; latency: number }> {
  const start = performance.now();
  try {
    await request('/healthz', {}, 4000);
    return { status: 'healthy', latency: Math.round(performance.now() - start) };
  } catch (err) {
    if (err instanceof ApiError && err.kind === 'http') return { status: 'degraded', latency: -1 };
    return { status: 'unreachable', latency: -1 };
  }
}
