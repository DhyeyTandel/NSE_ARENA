import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import axios from 'axios';

vi.mock('axios', () => ({ default: { get: vi.fn() } }));

import { NavBar } from './NavBar';

const endDate = new Date(Date.now() + 9.5 * 86400000).toISOString();
const real = {
  '/seasons/active': { id: 7, name: 'Season 7', end_date: endDate },
  '/leaderboard': [
    { user_id: 11, username: 'a', rank: 1, total_value: 120000, total_return_pct: 20, trader_score: 500 },
    { user_id: 12, username: 'me', rank: 2, total_value: 110500, total_return_pct: 10.5, trader_score: 350 },
    { user_id: 13, username: 'c', rank: 3, total_value: 90000, total_return_pct: -10, trader_score: 300 },
  ],
  '/score/12': { user_id: 12, final_score: 351, grade: 'Steady', breakdown: {} },
};

describe('NavBar', () => {
  beforeEach(() => {
    axios.get.mockImplementation((url) => {
      const path = url.replace(/^https?:\/\/[^/]+/, '');
      return path in real ? Promise.resolve({ data: real[path] }) : Promise.reject(new Error('no data'));
    });
  });

  it('shows the real season line and marks the active link', async () => {
    render(<NavBar activeScreen="leaderboard" onNavigate={() => {}} user={{ id: 12, username: 'me', initials: 'ME' }} onLogout={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('season-line').textContent).toBe('Season 7 · 10 days left · Rank #2 of 3'));
    expect(screen.getByText('Leaderboard').getAttribute('aria-current')).toBe('page');
    expect(screen.getByText('Dashboard').getAttribute('aria-current')).toBeNull();
  });

  it('opens the account menu with Sign out', async () => {
    const onLogout = vi.fn();
    render(<NavBar activeScreen="dashboard" onNavigate={() => {}} user={{ id: 12, username: 'me', initials: 'ME' }} onLogout={onLogout} />);
    expect(screen.queryByText('Sign out')).toBeNull();
    fireEvent.click(screen.getByLabelText('Account menu'));
    fireEvent.click(screen.getByText('Sign out'));
    expect(onLogout).toHaveBeenCalled();
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
  });
});
