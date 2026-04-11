// screens/Dashboard.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock PriceChart — it needs canvas which jsdom doesn't support
vi.mock('../components/PriceChart', () => ({
  PriceChart: ({ ticker }) => <div data-testid="price-chart">{ticker}</div>,
}));

// Mock fetch to avoid network calls
globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }));

import { Dashboard } from './Dashboard';

describe('Dashboard', () => {
  it('renders all 4 KPI card labels', () => {
    render(<Dashboard token={null} />);

    expect(screen.getByText('Portfolio value')).toBeTruthy();
    expect(screen.getByText("Today's P&L")).toBeTruthy();
    expect(screen.getByText('Trader score')).toBeTruthy();
    expect(screen.getByText('Season rank')).toBeTruthy();
  });

  it('renders the selected ticker name', () => {
    render(<Dashboard token={null} />);
    // "RELIANCE" appears in both the ticker label and the mocked PriceChart
    const matches = screen.getAllByText('RELIANCE');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders demo positions in the table', () => {
    render(<Dashboard token={null} />);

    // Demo positions from Dashboard.jsx
    expect(screen.getByText('TCS')).toBeTruthy();
    expect(screen.getByText('INFY')).toBeTruthy();
  });
});
