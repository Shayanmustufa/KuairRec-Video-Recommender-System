import { describe, expect, it, vi } from 'vitest';
import { ApiError, fetchRecommendations } from '@/lib/api';
import { formatDuration, formatEvidenceValue, hybridTotals, sortItems } from '@/lib/format';
import { item } from './fixtures';

describe('api client', () => {
  it('sends the WBS request body and per-request model', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"recommendations":[]}', { status: 200, headers: { 'X-Request-ID': 'a' } }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchRecommendations({ user_id: '0', top_k: 10, exclude_seen: true, model: 'item-cf-cosine-v1', force_cold_start: false });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/recommendations');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toMatchObject({ user_id: '0', top_k: 10, exclude_seen: true, model: 'item-cf-cosine-v1' });
  });

  it('maps API errors to http errors with the request ID', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"error":"top_k must be between 1 and 20"}', { status: 400, headers: { 'X-Request-ID': 'req-9' } }),
        ),
    );
    await expect(fetchRecommendations({ user_id: '0', top_k: 99, exclude_seen: true })).rejects.toMatchObject({
      kind: 'http',
      status: 400,
      requestId: 'req-9',
      message: 'top_k must be between 1 and 20',
    });
  });

  it('treats a proxy 5xx without request ID as backend unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Internal Server Error', { status: 500 })));
    await expect(fetchRecommendations({ user_id: '0', top_k: 5, exclude_seen: true })).rejects.toMatchObject({ kind: 'unavailable' });
  });

  it('times out hung requests', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) =>
            init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))),
          ),
      ),
    );
    const pending = fetchRecommendations({ user_id: '0', top_k: 5, exclude_seen: true });
    const assertion = expect(pending).rejects.toBeInstanceOf(ApiError);
    await vi.advanceTimersByTimeAsync(8001);
    await assertion;
    await expect(pending).rejects.toMatchObject({ kind: 'timeout' });
  });
});

describe('format helpers', () => {
  it('formats evidence without mangling IDs or counts', () => {
    expect(formatEvidenceValue('source_video_id', '8585')).toBe('8585');
    expect(formatEvidenceValue('positive_training_event_count', 1210)).toBe('1,210');
    expect(formatEvidenceValue('similarity', 0.2986)).toBe('0.2986');
    expect(formatEvidenceValue('similarity', 0.00044)).toBe('4.40e-4');
    expect(formatEvidenceValue('forced', true)).toBe('yes');
  });

  it('formats missing durations honestly', () => {
    expect(formatDuration(null)).toBe('not provided');
    expect(formatDuration(12.5)).toBe('12.5 s');
    expect(formatDuration(75)).toBe('1 min 15 s');
  });

  it('sorts a copy and keeps model ranks', () => {
    const a = item({ item_id: 'a', rank: 1, score: 0.5 });
    const b = item({ item_id: 'b', rank: 2, score: 0.9 });
    const sorted = sortItems([a, b], 'score');
    expect(sorted.map((i) => i.item_id)).toEqual(['b', 'a']);
    expect(sorted[0].rank).toBe(2);
    expect(sortItems(sorted, 'rank').map((i) => i.item_id)).toEqual(['a', 'b']);
  });

  it('sums hybrid contributions per component', () => {
    expect(hybridTotals([item(), item()])).toEqual({ item_cf: 1.8, lightgcn: 0, popularity: 0.04262 });
  });
});
