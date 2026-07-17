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
        background: { color: '#FFFFFF' },
        textColor: '#7C7367',
        fontFamily: '"JetBrains Mono", monospace',
      },
      grid: {
        vertLines: { color: '#17140F0A' },
        horzLines: { color: '#17140F0A' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#17140F14' },
      timeScale: { borderColor: '#17140F14', timeVisible: false },
    });
    chartRef.current = chart;

    // Candlestick series
    if (ohlcv.length > 0) {
      const candlestick = chart.addSeries(CandlestickSeries, {
        upColor: '#1E8A5A',
        downColor: '#D0342C',
        borderUpColor: '#1E8A5A',
        borderDownColor: '#D0342C',
        wickUpColor: '#1E8A5A66',
        wickDownColor: '#D0342C66',
      });
      candlestick.setData(ohlcv);
    }

    // Overlay indicator series
    for (const plot of overlayPlots) {
      if (!plot.data || plot.data.length === 0) continue;
      const SeriesType = SERIES_FACTORY[plot.style] || LineSeries;

      const seriesOpts = {
        color: plot.color || '#EE5308',
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
        background: { color: '#FFFFFF' },
        textColor: '#7C7367',
        fontFamily: '"JetBrains Mono", monospace',
      },
      grid: {
        vertLines: { color: '#17140F0A' },
        horzLines: { color: '#17140F0A' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#17140F14' },
      timeScale: { borderColor: '#17140F14', timeVisible: false },
    });
    paneChartRef.current = chart;

    for (const plot of panePlots) {
      if (!plot.data || plot.data.length === 0) continue;
      const SeriesType = SERIES_FACTORY[plot.style] || LineSeries;

      const seriesOpts = {
        color: plot.color || '#EE5308',
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
          color: hl.color || '#A89E90',
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
            background: 'var(--faint)',
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
