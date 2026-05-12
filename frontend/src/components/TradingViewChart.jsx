// components/TradingViewChart.jsx
/**
 * TradingView Advanced Chart Widget — free embeddable chart with real market data.
 * Uses an iframe-based widget that provides candlesticks, indicators, drawing tools,
 * and real-time data from TradingView's servers for NSE stocks.
 */
import { useEffect, useRef, memo } from 'react';

function TradingViewChartInner({ symbol = 'RELIANCE', height = 400 }) {
  const container = useRef(null);

  useEffect(() => {
    if (!container.current) return;

    // Clear previous widget
    container.current.innerHTML = '';

    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container__widget';
    widgetContainer.style.height = '100%';
    widgetContainer.style.width = '100%';
    container.current.appendChild(widgetContainer);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: `NSE:${symbol.replace('.NS', '')}`,
      interval: 'D',
      timezone: 'Asia/Kolkata',
      theme: 'dark',
      style: '1', // candlestick
      locale: 'en',
      backgroundColor: 'rgba(10, 10, 11, 1)',  // var(--ink)
      gridColor: 'rgba(255, 255, 255, 0.03)',
      allow_symbol_change: true,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: true,
      hide_volume: false,
      withdateranges: true,
      details: false,
      hotlist: false,
      show_popup_button: false,
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, [symbol]);

  return (
    <div
      className="tradingview-widget-container"
      ref={container}
      style={{
        height: `${height}px`,
        width: '100%',
        borderRadius: 'var(--r2)',
        overflow: 'hidden',
      }}
    />
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
