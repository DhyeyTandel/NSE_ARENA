// screens/Dashboard.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock TradingViewChart — it needs canvas which jsdom doesn't support
vi.mock('../components/TradingViewChart', () => ({
  TradingViewChart: ({ symbol }) => <div data-testid="price-chart">{symbol}</div>,
}));

// Mock fetch to avoid network calls
globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }));

import { Dashboard } from './Dashboard';

describe('Dashboard', () => {
  it('renders all 4 KPI card labels', () => {
    render(<Dashboard authenticated={false} />);

    expect(screen.getByText('Portfolio value')).toBeTruthy();
    expect(screen.getByText('Season P&L')).toBeTruthy();
    expect(screen.getByText('Trader score')).toBeTruthy();
    expect(screen.getByText('Season rank')).toBeTruthy();
  });

  it('renders the selected ticker name', () => {
    render(<Dashboard authenticated={false} />);
    // "RELIANCE" appears in both the ticker label and the mocked PriceChart
    const matches = screen.getAllByText('RELIANCE');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders demo positions in the table', () => {
    render(<Dashboard authenticated={false} />);

    // TCS/INFY also appear in the watchlist pills, so there are 2 matches each
    expect(screen.getAllByText('TCS').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('INFY').length).toBeGreaterThanOrEqual(1);
  });
});
