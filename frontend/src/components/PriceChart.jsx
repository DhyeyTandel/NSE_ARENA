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
        textColor: '#52525b',
        fontFamily: 'DM Mono'
      },
      grid: {
        vertLines: { color: '#ffffff06' },
        horzLines: { color: '#ffffff06' }
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#ffffff09' },
      timeScale: { borderColor: '#ffffff09', timeVisible: true }
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#34d399', downColor: '#f87171',
      borderUpColor: '#34d399', borderDownColor: '#f87171',
      wickUpColor: '#34d39966', wickDownColor: '#f8717166'
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
