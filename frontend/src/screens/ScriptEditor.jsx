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

const PERIODS = ['1mo', '3mo', '6mo', '1y']; // sent to the API as-is

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
      <div className="se-toolbar">
        <div>
          <h1>golden-cross.pine</h1>
          <div className="se-toolbar__sub">PineScript-lite</div>
        </div>
        <div className="se-toolbar__right">

          <div className="seg" role="group" aria-label="Period">
            {PERIODS.map(p => (
              <button key={p} type="button" className={period === p ? 'is-active' : ''}
                onClick={() => setPeriod(p)}>{p}</button>
            ))}
          </div>

          <button type="button" className="btn btn--ghost" onClick={handleSave}>Save</button>
          <button type="button" className="btn" onClick={handleRun} disabled={loading}>
            {loading ? <><span className="se-spinner" /> Running</> : 'Run'}
          </button>
        </div>
      </div>

      <div className="se-panes">
        <div className="se-panes__inner">
          <div className="se-rail">
            <div className="se-rail__label">My scripts</div>
            {MY_SCRIPTS.map(f => (
              <div key={f.name} className={`se-rail__item${f.active ? ' se-rail__item--active' : ''}`}>
                {f.name}
              </div>
            ))}
            <div className="se-rail__label se-rail__gap">Templates</div>
            {(templates.length > 0 ? templates.map(t => t.name) : TEMPLATES).map(t => (
              <div key={t} className="se-rail__item">{t}</div>
            ))}
          </div>

          <div className="se-code">
            <div className="se-code__scroll">
              <MonacoEditor value={code} onChange={setCode} height="100%" />
            </div>
            <div className="se-code__console">
              <div style={{ marginBottom: 'var(--s1)' }}>// console</div>
              {consoleLogs.slice(-3).map((log, i) => (
                <div key={i} className={log.type === 'success' ? 'se-code__console-ok' : log.type === 'error' ? 'dn' : ''}>
                  {log.text}
                </div>
              ))}
            </div>
          </div>

          <div className="se-output">
            <div className="se-output__header">
              <span>{ticker} · 1D</span>
              <span className="se-legend">
                <span style={{ color: 'var(--accent-text)' }}>SMA 50</span>
                <span style={{ color: 'var(--sell-text)' }}>SMA 200</span>
              </span>
            </div>
            {ohlcv.length > 0 ? (
              <IndicatorChart ohlcv={ohlcv} plots={plots} hlines={hlines} height={350} />
            ) : (
              <div className="se-empty">
                <div>Write a script and click <strong>Run</strong> to see your indicator on the chart</div>
                <div>Cmd+Enter to run</div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="se-footer">
        Supports ta.sma, ta.ema, ta.rsi, ta.macd, ta.bb, ta.crossover / crossunder. Outputs render on lightweight-charts with multi-pane support.
      </div>
    </div>
  );
}
