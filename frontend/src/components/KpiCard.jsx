// components/KpiCard.jsx
export function KpiCard({ label, value, sub, variant }) {
  // variant: 'default' | 'up' | 'down' | 'gold' | 'blue'
  const colors = {
    default: 'var(--text)',
    up: 'var(--up)',
    down: 'var(--dn)',
    gold: 'var(--gold)',
    blue: 'var(--blue)'
  };

  return (
    <div style={{ padding: '18px 20px', borderRight: '1px solid var(--border)' }}>
      <div style={{ fontSize: '10px', fontWeight: 400, color: 'var(--text3)',
        textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '8px' }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'DM Mono, monospace', fontSize: '22px',
        fontWeight: 300, letterSpacing: '-.5px', lineHeight: 1,
        color: colors[variant] || colors.default
      }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '11px', color: 'var(--text3)',
          marginTop: '5px', fontFamily: 'DM Mono, monospace' }}>
          {sub}
        </div>
      )}
    </div>
  );
}
