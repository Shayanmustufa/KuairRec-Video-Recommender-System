import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UserHistoryPanel } from '@/components/UserHistoryPanel';

const base = { user_id: '0', status: 'known' as const, seen_items: 10, has_comparison_export: false, recent_positive: [] };

describe('UserHistoryPanel', () => {
  it('does not claim "no history" for a user whose recent list is simply not exported', () => {
    render(<UserHistoryPanel user={{ ...base, positive_history_items: 218 }} />);
    expect(screen.queryByText('No positive history is recorded for this user.')).not.toBeInTheDocument();
    expect(screen.getByText(/exported for the 100 demo users only/)).toBeInTheDocument();
  });

  it('states no history when the user has none', () => {
    render(<UserHistoryPanel user={{ ...base, status: 'no_positive_history', positive_history_items: 0 }} />);
    expect(screen.getByText('No positive history is recorded for this user.')).toBeInTheDocument();
  });

  it('lists recent positive videos with links', () => {
    render(
      <UserHistoryPanel
        user={{ ...base, positive_history_items: 1, recent_positive: [{ item_id: '5', timestamp: 1593878903, watch_ratio: 2.5 }] }}
      />,
    );
    expect(screen.getByRole('link', { name: 'Video 5 (no official caption)' })).toHaveAttribute('href', '/videos/5');
    expect(screen.getByText(/2020-07-04 · ratio 2.50/)).toBeInTheDocument();
  });
});
