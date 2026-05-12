// components/TradingViewChart.jsx
/**
 * NSE Arena Chart — powered by lightweight-charts + yfinance backend data.
 * Replaces the TradingView embed widget so all NSE symbols work without restrictions.
 */
import { useEffect, useRef, useState, memo } from 'react';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

const API_BASE = 'http://localhost:8000';

function TradingViewChartInner({ symbol = 'RELIANCE', height = 400 }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#0a0a0b' },
        textColor: '#71717a',
        fontFamily: "'DM Mono', 'SF Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)' },
        horzLines: { color: 'rgba(255,255,255,0.03)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: 'rgba(255,255,255,0.15)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#27272a',
        },
        horzLine: {
          color: 'rgba(255,255,255,0.15)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#27272a',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.06)',
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.06)',
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 8,
        rightOffset: 5,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#34d399',
      downColor: '#f87171',
      borderUpColor: '#34d399',
      borderDownColor: '#f87171',
      wickUpColor: 'rgba(52,211,153,0.5)',
      wickDownColor: 'rgba(248,113,113,0.5)',
    });

    // Volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
      drawTicks: false,
      borderVisible: false,
    });

    // Fetch OHLCV data from our backend
    const ticker = symbol.replace('.NS', '');
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/price/${ticker}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (data.ohlcv && data.ohlcv.length > 0) {
          const candleData = data.ohlcv.map(bar => ({
            time: bar.date || bar.time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          }));

          const volumeData = data.ohlcv.map(bar => ({
            time: bar.date || bar.time,
            value: bar.volume,
            color: bar.close >= bar.open
              ? 'rgba(52,211,153,0.25)'
              : 'rgba(248,113,113,0.25)',
          }));

          candleSeries.setData(candleData);
          volumeSeries.setData(volumeData);
          chart.timeScale().fitContent();
        } else {
          setError('No data available');
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch OHLCV:', err);
        setError('Failed to load chart data');
        setLoading(false);
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

  return (
    <div style={{ position: 'relative', width: '100%', height: `${height}px` }}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          borderRadius: 'var(--r2, 8px)',
          overflow: 'hidden',
        }}
      />

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(10,10,11,0.8)',
          borderRadius: 'var(--r2, 8px)',
        }}>
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px',
          }}>
            <div style={{
              width: '24px', height: '24px',
              border: '2px solid rgba(255,255,255,0.1)',
              borderTopColor: '#c9a227',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }} />
            <span style={{
              fontSize: '11px', color: '#71717a',
              fontFamily: "'DM Mono', monospace",
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}>
              Loading {symbol}...
            </span>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {error && !loading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(10,10,11,0.8)',
          borderRadius: 'var(--r2, 8px)',
        }}>
          <span style={{
            fontSize: '12px', color: '#f87171',
            fontFamily: "'DM Mono', monospace",
          }}>
            {error}
          </span>
        </div>
      )}

      {/* Spinner keyframes */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
