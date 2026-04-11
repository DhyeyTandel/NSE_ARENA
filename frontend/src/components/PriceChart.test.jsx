// components/PriceChart.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

// Mock lightweight-charts — jsdom doesn't support canvas
vi.mock('lightweight-charts', () => {
  const mockSeries = { setData: vi.fn() };
  const mockTimeScale = { fitContent: vi.fn() };
  const mockChart = {
    addSeries: vi.fn(() => mockSeries),
    timeScale: vi.fn(() => mockTimeScale),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  };
  return {
    createChart: vi.fn(() => mockChart),
    CandlestickSeries: 'CandlestickSeries',
    __mockChart: mockChart,
    __mockSeries: mockSeries,
  };
});

import { PriceChart } from './PriceChart';
import { createChart } from 'lightweight-charts';

const SAMPLE_DATA = [
  { time: 1710100000, open: 2850, high: 2880, low: 2830, close: 2870, volume: 5000000 },
  { time: 1710186400, open: 2870, high: 2900, low: 2850, close: 2880, volume: 4500000 },
];

describe('PriceChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a container div', () => {
    const { container } = render(<PriceChart data={SAMPLE_DATA} ticker="RELIANCE" />);
    const chartDiv = container.querySelector('div');
    expect(chartDiv).toBeTruthy();
    expect(chartDiv.style.width).toBe('100%');
    expect(chartDiv.style.height).toBe('160px');
  });

  it('creates chart and sets data when data is provided', () => {
    // Mock clientWidth since jsdom doesn't have layout
    Object.defineProperty(HTMLDivElement.prototype, 'clientWidth', { value: 800, configurable: true });

    render(<PriceChart data={SAMPLE_DATA} ticker="RELIANCE" />);

    expect(createChart).toHaveBeenCalledTimes(1);
    const mockChart = createChart.mock.results[0].value;
    expect(mockChart.addSeries).toHaveBeenCalledTimes(1);
  });

  it('does not create chart when data is empty', () => {
    render(<PriceChart data={[]} ticker="RELIANCE" />);
    expect(createChart).not.toHaveBeenCalled();
  });
});
