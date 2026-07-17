// components/PriceChart.jsx
import { createChart, CandlestickSeries } from 'lightweight-charts';
import { useEffect, useRef } from 'react';

export function PriceChart({ data, ticker }) {
  const ref = useRef();

  useEffect(() => {
    if (!ref.current || !data || data.length === 0) return;

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 160,
      layout: {
        background: { color: 'transparent' },
        textColor: '#7C7367',
        fontFamily: 'JetBrains Mono'
      },
      grid: {
        vertLines: { color: '#17140F0A' },
        horzLines: { color: '#17140F0A' }
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#17140F14' },
      timeScale: { borderColor: '#17140F14', timeVisible: true }
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#1E8A5A', downColor: '#D0342C',
      borderUpColor: '#1E8A5A', borderDownColor: '#D0342C',
      wickUpColor: '#1E8A5A66', wickDownColor: '#D0342C66'
    });

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
  }, [data]);

  return <div ref={ref} style={{ width: '100%', height: '160px' }} />;
}
