// theme.js — light/dark theme state. The attribute on <html> is the source of truth
// (set before first paint by the inline script in index.html).
import { useSyncExternalStore } from 'react';

const KEY = 'nse-arena-theme';

export function getTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

export function initialTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* storage unavailable */ }
  try {
    if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  } catch { /* ignore */ }
  return 'light';
}

export function setTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  try { localStorage.setItem(KEY, name); } catch { /* storage unavailable */ }
}

export function toggleTheme() {
  setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

function subscribe(cb) {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  return () => obs.disconnect();
}

export function useThemeName() {
  return useSyncExternalStore(subscribe, getTheme, () => 'light');
}

// Resolve a CSS custom property to its current value (for canvas/Monaco consumers).
export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function chartTheme() {
  const v = cssVar;
  return {
    layout: { background: { color: v('--chart-bg') }, textColor: v('--chart-axis') },
    grid: { vertLines: { color: v('--chart-grid') }, horzLines: { color: v('--chart-grid') } },
    crosshair: {
      vertLine: { color: v('--chart-axis'), labelBackgroundColor: v('--chart-label') },
      horzLine: { color: v('--chart-axis'), labelBackgroundColor: v('--chart-label') },
    },
    rightPriceScale: { borderColor: v('--chart-line') },
    timeScale: { borderColor: v('--chart-line') },
  };
}

export function candleColors() {
  const g = cssVar('--gain'), l = cssVar('--loss');
  return {
    upColor: g, downColor: l, borderUpColor: g, borderDownColor: l, wickUpColor: g, wickDownColor: l,
  };
}
