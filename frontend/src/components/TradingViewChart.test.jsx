// components/TradingViewChart.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { useState } from 'react';

vi.mock('lightweight-charts', () => {
  const series = { setData: vi.fn(), applyOptions: vi.fn() };
  const timeScale = { fitContent: vi.fn(), setVisibleLogicalRange: vi.fn() };
  const chart = {
    addSeries: vi.fn(() => series),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    timeScale: vi.fn(() => timeScale),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  };
  return {
    createChart: vi.fn(() => chart),
    CandlestickSeries: 'CandlestickSeries',
    HistogramSeries: 'HistogramSeries',
    __chart: chart, __series: series, __timeScale: timeScale,
  };
});

import * as lwc from 'lightweight-charts';
import { TradingViewChart } from './TradingViewChart';
import { IST_OFFSET_SECONDS } from './chartRange';

const BARS = [{ time: 1000, open: 1, high: 2, low: 1, close: 2, volume: 5 }];

function Harness({ symbol = 'RELIANCE' }) {
  const [range, setRange] = useState('1M');
  return <TradingViewChart symbol={symbol} range={range} onRangeChange={setRange} />;
}

describe('TradingViewChart range tabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ ohlcv: BARS }) }));
  });

  it('renders 1D 1W 1M 1Y with 1M active and requests range=1M', async () => {
    render(<Harness />);
    for (const r of ['1D', '1W', '1M', '1Y']) expect(screen.getByRole('button', { name: r })).toBeTruthy();
    expect(screen.getByRole('button', { name: '1M' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: '1D' }).getAttribute('aria-pressed')).toBe('false');
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(fetch.mock.calls[0][0]).toMatch(/\/price\/RELIANCE\?range=1M$/);
  });

  it('clicking 1D refetches with range=1D, marks it active, shows times, shifts to IST', async () => {
    render(<Harness />);
    await waitFor(() => expect(lwc.__timeScale.setVisibleLogicalRange).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: '1D' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(fetch.mock.calls[1][0]).toMatch(/\?range=1D$/);
    expect(screen.getByRole('button', { name: '1D' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: '1M' }).getAttribute('aria-pressed')).toBe('false');
    await waitFor(() => expect(lwc.__timeScale.setVisibleLogicalRange).toHaveBeenCalledTimes(2));
    expect(lwc.__chart.applyOptions).toHaveBeenCalledWith({ timeScale: { timeVisible: true, secondsVisible: false } });
    expect(lwc.__series.setData.mock.calls.at(-1)[0][0].time).toBe(1000 + IST_OFFSET_SECONDS);
    const lastSet = lwc.__series.setData.mock.invocationCallOrder.at(-1);
    const lastFit = lwc.__timeScale.setVisibleLogicalRange.mock.invocationCallOrder.at(-1);
    expect(lastFit).toBeGreaterThan(lastSet);
    expect(lwc.__timeScale.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: -0.5, to: BARS.length - 0.5 });
    // range change must not rebuild the chart
    expect(lwc.createChart).toHaveBeenCalledTimes(1);
  });

  it('shows the error state when the fetch fails', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500 }));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<Harness />);
    expect(await screen.findByText('Failed to load chart data')).toBeTruthy();
  });
});
