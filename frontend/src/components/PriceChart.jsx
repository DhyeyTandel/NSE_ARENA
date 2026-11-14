// components/PriceChart.jsx
import { createChart, CandlestickSeries } from 'lightweight-charts';
import { useEffect, useRef } from 'react';
import { chartTheme, candleColors, cssVar, useThemeName } from '../theme';

export function PriceChart({ data }) {
  const theme = useThemeName();
  const ref = useRef();

  useEffect(() => {
    if (!ref.current || !data || data.length === 0) return;

    const base = chartTheme();
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 160,
      ...base,
      layout: { ...base.layout, background: { color: 'transparent' }, fontFamily: cssVar('--font') },
      crosshair: { ...base.crosshair, mode: 1 },
      timeScale: { ...base.timeScale, timeVisible: true },
    });

    const series = chart.addSeries(CandlestickSeries, candleColors());

    series.setData(data);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (ref.current) {
        chart.applyOptions({ width: ref.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, theme]);

  return <div ref={ref} style={{ width: '100%', height: '160px' }} />;
}
