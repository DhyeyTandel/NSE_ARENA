// screens/Dashboard.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import axios from 'axios';

// Mock TradingViewChart — it needs canvas which jsdom doesn't support
vi.mock('../components/TradingViewChart', () => ({
  TradingViewChart: ({ symbol, range, onRangeChange }) => (
    <div data-testid="price-chart" data-range={range}>
      {symbol}
      <button aria-label="mock-1W" onClick={() => onRangeChange('1W')} />
    </div>
  ),
}));

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({ prices: {}, connected: false })),
}));

import { useWebSocket } from '../hooks/useWebSocket';
import { Dashboard } from './Dashboard';

const FAKE = ['Season 4', 'Monsoon', '1,204', '#23', '412', '1,840', '▲2', 'TATAMOTORS', '12 days', '+1.55%'];

const endDate = new Date(Date.now() + 9.5 * 86400000).toISOString();
const TICKERS = { tickers: ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'ITC', 'LT'] };
const real = {
  '/tickers': TICKERS,
  '/seasons/active': { id: 7, name: 'Season 7', end_date: endDate },
  '/leaderboard': [
    { user_id: 11, username: 'a', rank: 1, total_value: 120000, total_return_pct: 20, trader_score: 500, grade: 'Disciplined' },
    { user_id: 12, username: 'me', rank: 2, total_value: 110500, total_return_pct: 10.5, trader_score: 350, grade: 'Steady' },
    { user_id: 13, username: 'c', rank: 3, total_value: 90000, total_return_pct: -10, trader_score: 300, grade: 'Beginner' },
  ],
  '/score/12': { user_id: 12, final_score: 351, grade: 'Steady', breakdown: {} },
  '/portfolio': { total_value: 110500, total_return: 10500, total_return_pct: 10.5, cash_balance: 50000, holdings: [], starting_capital: 100000 },
};

function mockApi(map) {
  axios.get.mockImplementation((url) => {
    const path = url.replace(/^https?:\/\/[^/]+/, '');
    return path in map ? Promise.resolve({ data: map[path] }) : Promise.reject(new Error('no data'));
  });
}

describe('Dashboard (logged out preview)', () => {
  beforeEach(() => { mockApi({}); });

  it('renders the four stat labels', () => {
    render(<Dashboard authenticated={false} />);
    expect(screen.getByText('Portfolio value')).toBeTruthy();
    expect(screen.getByText('Season P&L')).toBeTruthy();
    expect(screen.getByText('Trader score')).toBeTruthy();
    expect(screen.getByText('Rank')).toBeTruthy();
  });

  it('renders the selected ticker name', () => {
    render(<Dashboard authenticated={false} />);
    expect(screen.getAllByText('RELIANCE').length).toBeGreaterThanOrEqual(1);
  });

  it('renders demo positions in the table', () => {
    render(<Dashboard authenticated={false} />);
    expect(screen.getAllByText('TCS').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('INFY').length).toBeGreaterThanOrEqual(1);
  });
});

describe('Dashboard (authenticated)', () => {
  beforeEach(() => {
    useWebSocket.mockReturnValue({ prices: {}, connected: false });
  });

  it('renders real season, rank, score and gap from the API', async () => {
    mockApi(real);
    useWebSocket.mockReturnValue({
      prices: { RELIANCE: { ticker: 'RELIANCE', price: 2900, change_pct: -0.42 } },
      connected: true,
    });
    const { container } = render(<Dashboard authenticated user={{ id: 12, username: 'me' }} />);

    await waitFor(() => expect(container.textContent).toContain('₹9,500 behind #1'));
    expect(screen.getByText('#2')).toBeTruthy(); // Rank stat
    expect(screen.getByText('351')).toBeTruthy();
    expect(screen.getByText('Steady')).toBeTruthy();
    // live change % in the stock header and on the watchlist row
    expect(screen.getAllByText('−0.42%').length).toBeGreaterThanOrEqual(1);
    expect(container.textContent).not.toContain('▲2 today');
  });

  it('shows neutral placeholders and no invented numbers when responses are empty', async () => {
    mockApi({});
    const { container } = render(<Dashboard authenticated user={{ id: 12, username: 'me' }} />);

    await waitFor(() => expect(axios.get.mock.calls.some(c => String(c[0]).includes('/seasons/active'))).toBe(true));
    await new Promise(r => setTimeout(r, 0));
    const text = container.textContent;
    for (const f of FAKE) expect(text).not.toContain(f);
    expect(screen.queryByText(/behind #/)).toBeNull();
    // score, rank and live change % are "—"
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });
});

describe('Dashboard watchlist', () => {
  beforeEach(() => {
    useWebSocket.mockReturnValue({
      prices: { INFY: { ticker: 'INFY', price: 1500, change_pct: 1.25 } },
      connected: true,
    });
  });

  it('loads the list from /tickers, shows live change and "—" until a tick', async () => {
    mockApi({ '/tickers': TICKERS });
    render(<Dashboard authenticated={false} />);
    const list = await screen.findByTestId('watchlist');
    await waitFor(() => expect(list.textContent).toContain('LT'));
    expect(list.querySelectorAll('[data-ticker]').length).toBe(7);
    expect(list.textContent).toContain('+1.25%');
    expect(list.textContent).toContain('1,500.00');
    expect(list.textContent).toContain('—');
  });

  it('filters the list and selects a ticker on click', async () => {
    mockApi({ '/tickers': TICKERS });
    render(<Dashboard authenticated={false} />);
    const list = await screen.findByTestId('watchlist');
    await waitFor(() => expect(list.querySelectorAll('[data-ticker]').length).toBe(7));

    fireEvent.change(screen.getByLabelText('Filter tickers'), { target: { value: 'bank' } });
    const buttons = list.querySelectorAll('[data-ticker]');
    expect(buttons.length).toBe(2); // HDFCBANK, ICICIBANK
    fireEvent.click(buttons[0]);
    expect(screen.getByTestId('price-chart').textContent).toBe('HDFCBANK');
  });

  it('falls back to tickers seen on the socket when /tickers fails', async () => {
    mockApi({});
    render(<Dashboard authenticated={false} />);
    const list = screen.getByTestId('watchlist');
    await waitFor(() => expect(list.textContent).toContain('INFY'));
    expect(list.querySelectorAll('[data-ticker]').length).toBe(1);
  });
});

describe('Dashboard chart range', () => {
  it('defaults to 1M and keeps the chosen range when the ticker changes', async () => {
    useWebSocket.mockReturnValue({ prices: {}, connected: true });
    mockApi({ '/tickers': TICKERS });
    render(<Dashboard authenticated={false} />);
    const list = await screen.findByTestId('watchlist');
    await waitFor(() => expect(list.querySelectorAll('[data-ticker]').length).toBe(7));
    expect(screen.getByTestId('price-chart').dataset.range).toBe('1M');
    fireEvent.click(screen.getByLabelText('mock-1W'));
    expect(screen.getByTestId('price-chart').dataset.range).toBe('1W');
    fireEvent.click(list.querySelectorAll('[data-ticker]')[1]);
    expect(screen.getByTestId('price-chart').textContent).not.toContain('RELIANCE');
    expect(screen.getByTestId('price-chart').dataset.range).toBe('1W');
  });
});

describe('Dashboard feed badge', () => {
  const tick = (source) => ({
    RELIANCE: { ticker: 'RELIANCE', price: 2900, change_pct: 0.1, market_open: true, ...(source ? { source } : {}) },
  });

  function renderWith(prices, status, user) {
    useWebSocket.mockReturnValue({ prices, connected: true });
    mockApi({ '/tickers': TICKERS, ...(status ? { '/api/kite/status': status } : {}) });
    return render(<Dashboard authenticated={!!user} user={user} />);
  }
  const ADMIN = { id: 1, username: 'boss', is_admin: true };
  const NON_ADMIN = { id: 2, username: 'joe', is_admin: false };

  it('says Live for a kite tick while the market is open', () => {
    renderWith(tick('kite'));
    expect(screen.getByText('Live')).toBeTruthy();
    expect(screen.queryByText('Delayed')).toBeNull();
  });

  it('says Delayed (muted) for a yahoo tick while the market is open', () => {
    renderWith(tick('yahoo'));
    const el = screen.getByText('Delayed');
    expect(el.style.color).toBe('var(--text-2)');
    expect(screen.queryByText('Live')).toBeNull();
  });

  it('keeps Market closed regardless of source', () => {
    renderWith({ RELIANCE: { ...tick('kite').RELIANCE, market_open: false } });
    expect(screen.getByText('Market closed')).toBeTruthy();
  });

  it('shows Connect Kite only when configured and not connected', async () => {
    renderWith(tick('yahoo'), { configured: true, connected: false, source: 'yahoo', last_tick_at: null }, ADMIN);
    const link = await screen.findByText('Connect Kite');
    expect(link.getAttribute('href')).toMatch(/\/api\/kite\/login$/);
  });

  it.each([[NON_ADMIN], [undefined]])('hides Connect Kite for non-admin %j', async (user) => {
    renderWith(tick('yahoo'), { configured: true, connected: false }, user);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/api/kite/status')));
    await new Promise(r => setTimeout(r, 0));
    expect(screen.queryByText('Connect Kite')).toBeNull();
    expect(screen.queryByText('Disconnect Kite')).toBeNull();
  });

  it('shows Disconnect Kite for admin when connected and POSTs with CSRF header', async () => {
    axios.post.mockResolvedValue({ data: { ok: true } });
    renderWith(tick('kite'), { configured: true, connected: true }, ADMIN);
    const btn = await screen.findByText('Disconnect Kite');
    expect(screen.queryByText('Connect Kite')).toBeNull();
    btn.click();
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/kite\/disconnect$/), null,
      { withCredentials: true, headers: { 'X-Requested-With': 'XMLHttpRequest' } },
    ));
  });

  it('hides Disconnect Kite for non-admin', async () => {
    renderWith(tick('kite'), { configured: true, connected: true }, NON_ADMIN);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/api/kite/status')));
    await new Promise(r => setTimeout(r, 0));
    expect(screen.queryByText('Disconnect Kite')).toBeNull();
  });

  it.each([
    [{ configured: false, connected: false }],
    [{ configured: true, connected: true }],
    [null],
  ])('hides Connect Kite for status %j', async (status) => {
    renderWith(tick('kite'), status);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/api/kite/status')));
    await new Promise(r => setTimeout(r, 0));
    expect(screen.queryByText('Connect Kite')).toBeNull();
  });
});

describe('Dashboard key stats and quick order buttons', () => {
  it('shows open/high/low/prev close/volume from the live tick and "—" when absent', () => {
    useWebSocket.mockReturnValue({
      prices: { RELIANCE: { ticker: 'RELIANCE', price: 2900, change_pct: 1, open: 2880, day_high: 2910, day_low: 2870, previous_close: 2871, volume: 1234567 } },
      connected: true,
    });
    mockApi({ '/tickers': TICKERS });
    const { container } = render(<Dashboard authenticated={false} />);
    const text = container.textContent;
    for (const t of ['Open', 'High', 'Low', 'Prev. close', 'Volume', '₹2,880.00', '₹2,910.00', '₹2,870.00', '₹2,871.00', '12,34,567']) {
      expect(text).toContain(t);
    }
  });

  it('B and S buttons select the ticker and switch the order side', async () => {
    useWebSocket.mockReturnValue({ prices: {}, connected: false });
    mockApi({ '/tickers': TICKERS });
    render(<Dashboard authenticated user={{ id: 1, username: 'u' }} />);
    const sell = await screen.findByLabelText('Sell TCS');
    fireEvent.click(sell);
    expect(screen.getByTestId('price-chart').textContent).toBe('TCS');
    expect(screen.getByRole('tab', { name: 'Sell' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByLabelText('Buy INFY'));
    expect(screen.getByRole('tab', { name: 'Buy' }).getAttribute('aria-selected')).toBe('true');
  });
});
