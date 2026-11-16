// components/TradingViewChart.jsx
/**
 * NSE Arena Chart — powered by lightweight-charts + yfinance backend data.
 * Replaces the TradingView embed widget so all NSE symbols work without restrictions.
 */
import { useEffect, useRef, useState, memo } from 'react';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import { API_URL as API_BASE } from '../config';
import { RANGES, INTRADAY, IST_OFFSET_SECONDS } from './chartRange';
import { chartTheme, candleColors, cssVar, useThemeName } from '../theme';

function TradingViewChartInner({ symbol = 'RELIANCE', height = 400, range = '1M', onRangeChange, header = null }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const volumeRef = useRef(null);
  const volumeDataRef = useRef([]);
  const rafRef = useRef(0);
  const theme = useThemeName();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const base = chartTheme();
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: height,
      layout: { ...base.layout, fontFamily: cssVar('--font'), fontSize: 11 },
      grid: base.grid,
      crosshair: {
        mode: 0,
        vertLine: { ...base.crosshair.vertLine, width: 1, style: 2 },
        horzLine: { ...base.crosshair.horzLine, width: 1, style: 2 },
      },
      rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.1, bottom: 0.25 } },
      timeScale: {
        ...base.timeScale,
        timeVisible: false,
        secondsVisible: false,
        barSpacing: 8,
        rightOffset: 5,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;
    setHasData(false);

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, candleColors());
    candleRef.current = candleSeries;

    // Volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeRef.current = volumeSeries;

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
      drawTicks: false,
      borderVisible: false,
    });

    // Resize handler
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [symbol, height]);

  // Fetch OHLCV for the symbol + range and swap the series data in place.
  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleRef.current;
    const volumeSeries = volumeRef.current;
    if (!chart || !candleSeries || !volumeSeries) return;
    let cancelled = false;
    const ticker = symbol.replace('.NS', '');
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/price/${ticker}?range=${range}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (cancelled) return;
        if (data.ohlcv && data.ohlcv.length > 0) {
          const t = bar => (bar.date || bar.time) + IST_OFFSET_SECONDS;
          const candleData = data.ohlcv.map(bar => ({
            time: t(bar),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          }));

          const volumeData = data.ohlcv.map(bar => ({
            time: t(bar),
            value: bar.volume,
            up: bar.close >= bar.open,
            color: bar.close >= bar.open ? cssVar('--chart-vol-up') : cssVar('--chart-vol-down'),
          }));
          volumeDataRef.current = volumeData;

          chart.applyOptions({ timeScale: { timeVisible: INTRADAY.has(range), secondsVisible: false } });
          candleSeries.setData(candleData);
          volumeSeries.setData(volumeData.map(({ time, value, color }) => ({ time, value, color })));
          // Fit explicitly once the library has processed the new data; a
          // synchronous fitContent right after setData can keep the previous
          // range's bar spacing/offset (daily -> intraday left candles squeezed).
          const count = candleData.length;
          cancelAnimationFrame(rafRef.current);
          rafRef.current = requestAnimationFrame(() => {
            if (cancelled || chartRef.current !== chart || count === 0) return;
            chart.timeScale().setVisibleLogicalRange({ from: -0.5, to: count - 0.5 });
          });
          setHasData(true);
        } else {
          setError('No data available');
        }
        setLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        console.error('Failed to fetch OHLCV:', err);
        setError('Failed to load chart data');
        setLoading(false);
      });

    return () => { cancelled = true; cancelAnimationFrame(rafRef.current); };
  }, [symbol, range, height]);

  // Follow the theme live without refetching data.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const base = chartTheme();
    chart.applyOptions({
      layout: base.layout, grid: base.grid, crosshair: base.crosshair,
      rightPriceScale: base.rightPriceScale, timeScale: base.timeScale,
    });
    candleRef.current?.applyOptions(candleColors());
    if (volumeRef.current && volumeDataRef.current.length) {
      volumeRef.current.setData(volumeDataRef.current.map(({ time, value, up }) => ({
        time, value, color: up ? cssVar('--chart-vol-up') : cssVar('--chart-vol-down'),
      })));
    }
  }, [theme]);

  return (
    <>
    <div className="chart-head">
      <div className="chart-head-main">{header}</div>
      <div className="seg" role="group" aria-label="Chart range">
        {RANGES.map(r => (
          <button key={r} type="button" aria-pressed={range === r}
            className={range === r ? 'is-active' : ''}
            onClick={() => onRangeChange?.(r)}>{r}</button>
        ))}
      </div>
    </div>
    <div style={{ position: 'relative', width: '100%', height: `${height}px` }}>
      <div
        ref={containerRef}
        aria-busy={loading}
        style={{
          width: '100%',
          height: '100%',
          overflow: 'hidden',
          opacity: loading && hasData ? 0.45 : 1,
          transition: 'opacity var(--t-base)',
        }}
      />

      {loading && !hasData && (
        <div className="chart-overlay" role="status">
          <span className="skel skel--block chart-skel" aria-hidden="true" />
          <span className="chart-overlay-label"><span className="spinner" aria-hidden="true" /> Loading {symbol}</span>
        </div>
      )}

      {error && !loading && (
        <div className="chart-overlay chart-overlay--error" role="alert">
          <span>{error}</span>
        </div>
      )}
    </div>
    </>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
