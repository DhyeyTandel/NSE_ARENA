// components/Logo.jsx
// NSE Arena mark: an N built from two candlesticks (body + wick) joined by a
// diagonal stroke. The right candle sits higher than the left, so the whole
// glyph climbs. Colours come from CSS variables, so it follows the theme.
import './Logo.css';

export function LogoMark({ size = 28 }) {
  return (
    <svg
      className="logo-mark" width={size} height={size} viewBox="0 0 32 32"
      aria-hidden="true" focusable="false"
    >
      <rect width="32" height="32" rx="8" style={{ fill: 'var(--logo-bg)' }} />
      <path d="M10.5 11 L21.5 21" strokeWidth="3.4" fill="none" style={{ stroke: 'var(--logo-up)' }} />
      <path d="M10.5 8v20M21.5 4v20" strokeWidth="1.8" fill="none" style={{ stroke: 'var(--logo-ink)' }} />
      <rect x="8" y="11" width="5" height="14" rx="1" style={{ fill: 'var(--logo-ink)' }} />
      <rect x="19" y="7" width="5" height="14" rx="1" style={{ fill: 'var(--logo-ink)' }} />
    </svg>
  );
}

/**
 * size: height of the mark in px.
 * variant: "mark" (badge only) or "full" (badge + "NSE Arena" wordmark).
 */
export function Logo({ size = 28, variant = 'mark', className = '' }) {
  if (variant === 'full') {
    return (
      <span className={`logo logo--full ${className}`.trim()} role="img" aria-label="NSE Arena">
        <LogoMark size={size} />
        <span className="logo-word" aria-hidden="true" style={{ fontSize: Math.round(size * 0.7) }}>
          <span className="logo-word-strong">NSE</span> <span className="logo-word-light">Arena</span>
        </span>
      </span>
    );
  }
  return (
    <span className={`logo ${className}`.trim()} role="img" aria-label="NSE Arena">
      <LogoMark size={size} />
    </span>
  );
}
