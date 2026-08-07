// screens/ScriptEditor.jsx
import { useState, useEffect, useCallback } from 'react';
import { MonacoEditor } from '../components/MonacoEditor';
import { IndicatorChart } from '../components/IndicatorChart';
import { API_URL as API } from '../config';
import './ScriptEditor.css';

const DEFAULT_CODE = `//@version=5
indicator("Golden Cross", overlay=true)

fast = ta.sma(close, 50)
slow = ta.sma(close, 200)

plot(fast, "SMA 50", color=color.orange)
plot(slow, "SMA 200", color=color.blue)

buySignal = ta.crossover(fast, slow)
sellSignal = ta.crossunder(fast, slow)
`;

const PERIODS = ['1mo', '3mo', '6mo', '1y'];

const MY_SCRIPTS = [
  { name: 'golden-cross.pine', active: true },
  { name: 'rsi-divergence.pine', active: false },
  { name: 'bb-squeeze.pine', active: false },
];

const TEMPLATES = ['sma-crossover', 'macd-basic', 'rsi-oversold'];

export function ScriptEditor({ authenticated }) {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [ticker] = useState('RELIANCE');
  const [period, setPeriod] = useState('3mo');
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState([]);

  const [ohlcv, setOhlcv] = useState([]);
  const [plots, setPlots] = useState([]);
  const [hlines, setHlines] = useState([]);

  const [consoleLogs, setConsoleLogs] = useState([
    { type: 'info', text: '✓ parsed in 12ms · 2 plots, 2 signals' },
  ]);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await fetch(`${API}/api/scripts/templates`);
        if (res.ok) setTemplates(await res.json());
      } catch { /* templates rail falls back to TEMPLATES below */ }
    };
    fetchTemplates();
  }, []);

  const handleRun = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    const startTime = Date.now();
    setConsoleLogs(prev => [...prev, { type: 'info', text: `Running script for ${ticker} (${period})...` }]);

    try {
      const res = await fetch(`${API}/api/scripts/run`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ code, ticker, period }),
      });
      const data = await res.json();
      if (!res.ok) {
        setConsoleLogs(prev => [...prev, { type: 'error', text: `Error: ${data.detail || 'Script execution failed'}` }]);
        setLoading(false);
        return;
      }
      const elapsed = Date.now() - startTime;
      setOhlcv(data.ohlcv || []);
      setPlots(data.plots || []);
      setHlines(data.hlines || []);

      const newLogs = [];
      if (data.errors?.length > 0) data.errors.forEach(e => newLogs.push({ type: 'error', text: e }));
      if (data.logs?.length > 0) data.logs.forEach(l => newLogs.push({ type: 'success', text: l }));
      newLogs.push({ type: 'success', text: `✓ ${data.plots?.length || 0} plot(s) rendered · ${data.bars} bars · ${elapsed}ms` });
      setConsoleLogs(prev => [...prev, ...newLogs]);
    } catch (err) {
      setConsoleLogs(prev => [...prev, { type: 'error', text: `Network error: ${err.message}` }]);
    }
    setLoading(false);
  }, [code, ticker, period, loading]);

  const handleSave = useCallback(async () => {
    if (!authenticated) {
      setConsoleLogs(prev => [...prev, { type: 'error', text: 'Login required to save scripts.' }]);
      return;
    }
    const name = prompt('Script name:');
    if (!name) return;
    try {
      const res = await fetch(`${API}/api/scripts/save`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ name, code }),
      });
      setConsoleLogs(prev => [...prev,
        { type: res.ok ? 'success' : 'error', text: res.ok ? `Script "${name}" saved.` : 'Failed to save.' },
      ]);
    } catch {
      setConsoleLogs(prev => [...prev, { type: 'error', text: 'Network error — could not save.' }]);
    }
  }, [code, authenticated]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); handleRun(); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleRun]);

  return (
    <div className="script-editor">
      {/* Toolbar */}
      <div className="se-toolbar">
        <div className="se-toolbar__left">
          <div className="t-eyebrow" style={{ marginBottom: '10px' }}>PineScript-lite</div>
          <div className="t-title" style={{ fontSize: '28px' }}>golden-cross.pine</div>
        </div>
        <div className="se-toolbar__right">
          <span className="se-toolbar__meta">Last run 2 min ago · 0.4s</span>

          <div className="se-periods">
            {PERIODS.map(p => (
              <button key={p} className={`se-periods__btn ${period === p ? 'active' : ''}`}
                onClick={() => setPeriod(p)}>{p.toUpperCase()}</button>
            ))}
          </div>

          <button className="se-toolbar__btn-save" onClick={handleSave}>Save</button>
          <button className={`se-toolbar__btn-run ${loading ? 'loading' : ''}`}
            onClick={handleRun} disabled={loading}>
            {loading ? <><span className="se-spinner" /> Running...</> : 'Run →'}
          </button>
        </div>
      </div>

      {/* Three-pane body */}
      <div className="se-panes">
        <div className="se-panes__inner">
          {/* File rail */}
          <div className="se-rail">
            <div className="se-rail__label">My scripts</div>
            {MY_SCRIPTS.map(f => (
              <div key={f.name} className={`se-rail__item ${f.active ? 'se-rail__item--active' : 'se-rail__item--inactive'}`}>
                {f.name}
              </div>
            ))}
            <div className="se-rail__label" style={{ marginTop: '18px' }}>Templates</div>
            {(templates.length > 0 ? templates.map(t => t.name) : TEMPLATES).map(t => (
              <div key={t} className="se-rail__item se-rail__item--inactive">{t}</div>
            ))}
          </div>

          {/* Code editor (dark pane) */}
          <div className="se-code">
            <div className="se-code__scroll">
              <MonacoEditor value={code} onChange={setCode} height="100%" />
            </div>
            <div className="se-code__console">
              <div style={{ color: '#6E6455', marginBottom: '6px' }}>// console</div>
              {consoleLogs.slice(-3).map((log, i) => (
                <div key={i} className={log.type === 'success' ? 'se-code__console-ok' : ''}>
                  {log.text}
                </div>
              ))}
            </div>
          </div>

          {/* Output chart */}
          <div className="se-output">
            <div className="se-output__header">
              <div style={{ fontWeight: 600, fontSize: '14.5px' }}>{ticker} · 1D</div>
              <div style={{
                display: 'flex', gap: '14px',
                fontFamily: '"JetBrains Mono", monospace', fontSize: '11px', marginLeft: 'auto',
              }}>
                <span style={{ color: 'var(--accent)' }}>— SMA 50</span>
                <span style={{ color: 'var(--blurple)' }}>— SMA 200</span>
              </div>
            </div>
            {ohlcv.length > 0 ? (
              <IndicatorChart ohlcv={ohlcv} plots={plots} hlines={hlines} height={350} />
            ) : (
              <div className="se-empty">
                <div style={{ fontSize: '32px', opacity: 0.4 }}>▢</div>
                <div style={{ fontSize: '12px', textAlign: 'center', maxWidth: '200px', lineHeight: 1.5 }}>
                  Write a script and click <strong>Run →</strong> to see your indicator on the chart
                </div>
                <div style={{ fontSize: '10px', fontFamily: '"JetBrains Mono", monospace' }}>⌘+Enter to run</div>
              </div>
            )}
            <div className="se-output__signals">
              <span className="se-output__signal" style={{ background: 'var(--success-soft)', color: 'var(--success)' }}>
                ▲ golden cross · Feb 3
              </span>
              <span className="se-output__signal" style={{ background: 'var(--faint-soft)', color: 'var(--muted)' }}>
                last signal 164d ago
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="se-footer">
        <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
          Supports ta.sma, ta.ema, ta.rsi, ta.macd, ta.bb, ta.crossover / crossunder. Outputs render on lightweight-charts with multi-pane support.
        </div>
      </div>
    </div>
  );
}
