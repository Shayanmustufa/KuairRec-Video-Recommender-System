import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReasonBadge } from '@/components/ReasonBadge';
import { VideoCard } from '@/components/VideoCard';
import { HybridPanel } from '@/components/HybridPanel';
import { ErrorState, StateBanner } from '@/components/States';
import { ApiError } from '@/lib/api';
import { describeUserState } from '@/lib/format';
import type { ModelManifest } from '@/types';
import { item, response } from './fixtures';

describe('ReasonBadge', () => {
  it('shows the reason code, text and machine-readable evidence', () => {
    render(<ReasonBadge reason={item().reasons[0]} />);
    expect(screen.getByText('liked_by_similar_users')).toBeInTheDocument();
    expect(screen.getByText(/collaborative patterns/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '3289' })).toHaveAttribute('href', '/videos/3289');
    expect(screen.getByText('preference strength')).toBeInTheDocument();
    expect(screen.getByText('4.500')).toBeInTheDocument();
  });

  it('keeps counts exact', () => {
    render(<ReasonBadge reason={item().reasons[1]} />);
    expect(screen.getByText('1,210')).toBeInTheDocument();
  });
});

describe('VideoCard', () => {
  it('renders rank, metadata, score breakdown and reasons', () => {
    render(<VideoCard item={item()} userId="0" modelId="hybrid-validation-selected-v1" />);
    const card = screen.getByTestId('recommendation-card');
    expect(within(card).getByText('Rank #1')).toBeInTheDocument();
    expect(within(card).getByText('score 0.921')).toBeInTheDocument();
    expect(within(card).getByText('Comedy')).toBeInTheDocument();
    expect(within(card).getByRole('table', { name: 'Hybrid score breakdown' })).toBeInTheDocument();
    expect(card.querySelectorAll('[data-reason-code]')).toHaveLength(2);
  });

  it('labels videos without an official caption instead of inventing one', () => {
    const base = item();
    render(<VideoCard item={item({ video: { ...base.video!, title: '', has_caption: false } })} userId="0" modelId="m" />);
    expect(screen.getByText('Video 10 (no official caption)')).toBeInTheDocument();
  });

  it('posts feedback with the item rank and confirms it', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: 'recorded' }), { status: 201, headers: { 'X-Request-ID': 'r1' } }));
    vi.stubGlobal('fetch', fetchMock);
    render(<VideoCard item={item({ rank: 3 })} userId="0" modelId="hybrid-validation-selected-v1" />);
    await userEvent.click(screen.getByRole('button', { name: 'Play video 10' }));
    expect(await screen.findByText('Recorded “play”')).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/feedback');
    expect(JSON.parse(init.body)).toEqual({
      user_id: '0',
      item_id: '10',
      action: 'play',
      model_id: 'hybrid-validation-selected-v1',
      rank: 3,
    });
  });

  it('reports a feedback failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    render(<VideoCard item={item()} userId="0" modelId="m" />);
    await userEvent.click(screen.getByRole('button', { name: 'Hide video 10' }));
    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
  });
});

describe('HybridPanel', () => {
  it('shows the frozen weights and component shares', () => {
    const manifest = { selected_weights: { item_cf: 0.9, lightgcn: 0, popularity: 0.1 } } as unknown as ModelManifest;
    render(<HybridPanel manifest={manifest} items={[item()]} />);
    expect(screen.getByText(/Item-CF \(α\)/)).toBeInTheDocument();
    expect(screen.getByText('97.7% of shown score')).toBeInTheDocument();
    expect(screen.getByText('0.0% of shown score')).toBeInTheDocument();
  });
});

describe('states', () => {
  it('distinguishes unknown, no-history and forced cold start', () => {
    const { rerender } = render(
      <StateBanner
        message={describeUserState(response({ fallback: true, fallback_reason: 'unknown_user', user_id: 'x', user_status: 'unknown' }))}
      />,
    );
    expect(screen.getByText('Unknown user “x”')).toBeInTheDocument();
    rerender(
      <StateBanner
        message={describeUserState(
          response({ fallback: true, fallback_reason: 'no_positive_history', user_status: 'no_positive_history' }),
        )}
      />,
    );
    expect(screen.getByText('No positive history')).toBeInTheDocument();
    rerender(<StateBanner message={describeUserState(response({ fallback: true, fallback_reason: 'cold_start_requested' }))} />);
    expect(screen.getByText('Cold-start view requested')).toBeInTheDocument();
  });

  it('renders timeout and backend-unavailable errors with retry', async () => {
    const retry = vi.fn();
    const { rerender } = render(<ErrorState error={new ApiError('timeout', 'No response after 8 s')} onRetry={retry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('The API did not respond in time');
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
    rerender(<ErrorState error={new ApiError('unavailable', 'x')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Backend unavailable');
  });
});
