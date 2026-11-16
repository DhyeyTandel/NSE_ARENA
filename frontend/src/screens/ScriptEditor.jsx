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

export function ScriptEditor({ authenticated }) {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [ticker] = useState('RELIANCE');
  const [period, setPeriod] = useState('3mo');
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [myScripts, setMyScripts] = useState(null); // null while loading; [] when none saved
  const [activeName, setActiveName] = useState(''); // name of the loaded saved script / template

  const [ohlcv, setOhlcv] = useState([]);
  const [plots, setPlots] = useState([]);
  const [hlines, setHlines] = useState([]);

  const [indicatorTitle, setIndicatorTitle] = useState('');
  const [consoleLogs, setConsoleLogs] = useState([]);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await fetch(`${API}/api/scripts/templates`);
        if (res.ok) setTemplates(await res.json());
      } catch { /* no templates shown if the request fails */ }
    };
    fetchTemplates();
  }, []);

  const fetchMine = useCallback(async () => {
    if (!authenticated) { setMyScripts([]); return; }
    try {
      const res = await fetch(`${API}/api/scripts/mine`, { credentials: 'include' });
      const rows = res.ok ? await res.json() : [];
      setMyScripts(Array.isArray(rows) ? rows : []);
    } catch { setMyScripts([]); }
  }, [authenticated]);
  useEffect(() => { fetchMine(); }, [fetchMine]);

  const loadScript = (item) => {
    if (typeof item?.code !== 'string') return;
    setCode(item.code);
    setActiveName(item.name);
  };

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
      setIndicatorTitle(data.indicator_title || '');

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
      if (res.ok) { setActiveName(name); fetchMine(); }
    } catch {
      setConsoleLogs(prev => [...prev, { type: 'error', text: 'Network error: could not save.' }]);
    }
  }, [code, authenticated, fetchMine]);

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
          <h1>{activeName || 'Untitled script'}</h1>
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
            {myScripts === null && (
              <div className="se-rail__skel" aria-hidden="true">
                <span className="skel" style={{ '--w': '80%' }} /><span className="skel" style={{ '--w': '65%' }} />
              </div>
            )}
            {myScripts !== null && myScripts.length === 0 && (
              <div className="se-rail__empty">{authenticated ? 'No saved scripts yet. Use Save to keep one.' : 'Sign in to save scripts.'}</div>
            )}
            {(myScripts || []).map(f => (
              <button type="button" key={f.id} onClick={() => loadScript(f)}
                className={`se-rail__item${activeName === f.name ? ' se-rail__item--active' : ''}`}>
                {f.name}
              </button>
            ))}
            <div className="se-rail__label se-rail__gap">Templates</div>
            {templates.length === 0 && <div className="se-rail__empty">No templates available.</div>}
            {templates.map(t => (
              <button type="button" key={t.name} title={t.description} onClick={() => loadScript(t)}
                className={`se-rail__item${activeName === t.name ? ' se-rail__item--active' : ''}`}>
                {t.name}
              </button>
            ))}
          </div>

          <div className="se-code">
            <div className="se-code__scroll">
              <MonacoEditor value={code} onChange={setCode} height="100%" />
            </div>
            <div className="se-code__console">
              <div style={{ marginBottom: 'var(--s1)' }}>// console</div>
              {consoleLogs.length === 0 && <div>Run output will appear here.</div>}
              {consoleLogs.slice(-3).map((log, i) => (
                <div key={i} className={log.type === 'success' ? 'se-code__console-ok' : log.type === 'error' ? 'dn' : ''}>
                  {log.text}
                </div>
              ))}
            </div>
          </div>

          <div className="se-output">
            <div className="se-output__header">
              <span>{indicatorTitle ? `${indicatorTitle} · ${ticker}` : `${ticker} · 1D`}</span>
              <span className="se-legend">
                {plots.filter(p => p.title).map((p, i) => (
                  <span key={i} className="se-legend__item">
                    <span className="se-legend__swatch" style={{ background: p.color || 'var(--chart-series-1)' }} aria-hidden="true" />
                    {p.title}
                  </span>
                ))}
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
