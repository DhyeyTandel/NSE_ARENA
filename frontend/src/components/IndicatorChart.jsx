// components/IndicatorChart.jsx
/**
 * Chart with programmatic indicator overlays.
 * Uses lightweight-charts so we can add custom line/histogram series
 * from script execution results.
 */
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, AreaSeries } from 'lightweight-charts';
import { useEffect, useRef } from 'react';

const SERIES_FACTORY = {
  line: LineSeries,
  histogram: HistogramSeries,
  area: AreaSeries,
  circles: LineSeries,
};

export function IndicatorChart({ ohlcv = [], plots = [], hlines = [], height = 400 }) {
  const mainRef = useRef();
  const paneRef = useRef();
  const chartRef = useRef(null);
  const paneChartRef = useRef(null);

  // Separate overlays (pane=0) from oscillators (pane=1)
  const overlayPlots = plots.filter(p => p.pane === 0);
  const panePlots = plots.filter(p => p.pane === 1);
  const showPane = panePlots.length > 0;

  // ── Main chart (candlesticks + overlay indicators) ───────────────────
  useEffect(() => {
    if (!mainRef.current) return;

    const chart = createChart(mainRef.current, {
      width: mainRef.current.clientWidth,
      height: showPane ? Math.floor(height * 0.6) : height,
      layout: {
        background: { color: '#0a0a0b' },
        textColor: '#52525b',
        fontFamily: 'DM Mono, monospace',
      },
      grid: {
        vertLines: { color: '#ffffff06' },
        horzLines: { color: '#ffffff06' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#ffffff09' },
      timeScale: { borderColor: '#ffffff09', timeVisible: false },
    });
    chartRef.current = chart;

    // Candlestick series
    if (ohlcv.length > 0) {
      const candlestick = chart.addSeries(CandlestickSeries, {
        upColor: '#34d399',
        downColor: '#f87171',
        borderUpColor: '#34d399',
        borderDownColor: '#f87171',
        wickUpColor: '#34d39966',
        wickDownColor: '#f8717166',
      });
      candlestick.setData(ohlcv);
    }

    // Overlay indicator series
    for (const plot of overlayPlots) {
      if (!plot.data || plot.data.length === 0) continue;
      const SeriesType = SERIES_FACTORY[plot.style] || LineSeries;

      const seriesOpts = {
        color: plot.color || '#c9a84c',
        lineWidth: plot.linewidth || 2,
        title: plot.title,
        priceLineVisible: false,
        lastValueVisible: true,
      };

      if (plot.style === 'histogram') {
        seriesOpts.priceFormat = { type: 'volume' };
      }

      const series = chart.addSeries(SeriesType, seriesOpts);
      series.setData(plot.data);
    }

    // Horizontal lines (on main chart for overlay indicators)
    // lightweight-charts doesn't have native hlines, but we can use price lines

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (mainRef.current) {
        chart.applyOptions({ width: mainRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [ohlcv, overlayPlots, height, showPane]);

  // ── Separate pane (oscillator indicators) ────────────────────────────
  useEffect(() => {
    if (!showPane || !paneRef.current) return;

    const chart = createChart(paneRef.current, {
      width: paneRef.current.clientWidth,
      height: Math.floor(height * 0.38),
      layout: {
        background: { color: '#0a0a0b' },
        textColor: '#52525b',
        fontFamily: 'DM Mono, monospace',
      },
      grid: {
        vertLines: { color: '#ffffff06' },
        horzLines: { color: '#ffffff06' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#ffffff09' },
      timeScale: { borderColor: '#ffffff09', timeVisible: false },
    });
    paneChartRef.current = chart;

    for (const plot of panePlots) {
      if (!plot.data || plot.data.length === 0) continue;
      const SeriesType = SERIES_FACTORY[plot.style] || LineSeries;

      const seriesOpts = {
        color: plot.color || '#c9a84c',
        lineWidth: plot.linewidth || 2,
        title: plot.title,
        priceLineVisible: false,
        lastValueVisible: true,
      };

      if (plot.style === 'histogram') {
        seriesOpts.priceFormat = { type: 'volume' };
      }

      const series = chart.addSeries(SeriesType, seriesOpts);
      series.setData(plot.data);
    }

    // Add horizontal lines (hlines) — for RSI levels, zero lines, etc.
    if (panePlots.length > 0) {
      for (const hl of hlines) {
        // Create a constant series across all timestamps
        const data = panePlots[0].data.map(d => ({
          time: d.time,
          value: hl.price,
        }));
        const hlSeries = chart.addSeries(LineSeries, {
          color: hl.color || '#52525b',
          lineWidth: 1,
          lineStyle: 2, // dashed
          title: hl.title || '',
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        hlSeries.setData(data);
      }
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (paneRef.current) {
        chart.applyOptions({ width: paneRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      paneChartRef.current = null;
    };
  }, [panePlots, hlines, height, showPane]);

  return (
    <div style={{ width: '100%', height: `${height}px`, display: 'flex', flexDirection: 'column' }}>
      <div ref={mainRef} style={{
        width: '100%',
        flex: showPane ? '0 0 60%' : '1',
      }} />
      {showPane && (
        <>
          <div style={{
            height: '1px',
            background: 'var(--border2)',
            margin: '2px 0',
          }} />
          <div ref={paneRef} style={{
            width: '100%',
            flex: '0 0 38%',
          }} />
        </>
      )}
    </div>
  );
}
