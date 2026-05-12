// screens/ScriptEditor.jsx
/**
 * Script Editor Screen — write and run PineScript-lite indicators.
 * Left: chart with indicator overlays. Right: Monaco code editor.
 * Bottom: output console with logs and errors.
 */
import { useState, useEffect, useCallback } from 'react';
import { MonacoEditor } from '../components/MonacoEditor';
import { IndicatorChart } from '../components/IndicatorChart';
import './ScriptEditor.css';

const API = 'http://localhost:8000';

const DEFAULT_CODE = `//@version=5
indicator("RSI", overlay=false)

// RSI calculation
rsiLength = 14
rsiValue = ta.rsi(close, rsiLength)

// Plot RSI line
plot(rsiValue, title="RSI", color=color.purple)

// Overbought / Oversold levels
hline(70, title="Overbought", color=color.red)
hline(30, title="Oversold", color=color.green)
hline(50, title="Midline", color=color.gray)
`;

const PERIODS = ['1mo', '3mo', '6mo', '1y'];

export function ScriptEditor({ token }) {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [ticker, setTicker] = useState('RELIANCE');
  const [period, setPeriod] = useState('3mo');
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');

  // Results from script execution
  const [ohlcv, setOhlcv] = useState([]);
  const [plots, setPlots] = useState([]);
  const [hlines, setHlines] = useState([]);
  const [indicatorTitle, setIndicatorTitle] = useState('');
  const [barCount, setBarCount] = useState(0);

  // Console
  const [consoleLogs, setConsoleLogs] = useState([
    { type: 'info', text: 'Pine Script Editor ready. Write your indicator and click ▶ Run.' },
  ]);

  // Fetch templates on mount
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await fetch(`${API}/api/scripts/templates`);
        if (res.ok) {
          const data = await res.json();
          setTemplates(data);
        }
      } catch {
        // Templates will be empty — not critical
      }
    };
    fetchTemplates();
  }, []);

  // Handle template selection
  const handleTemplateChange = useCallback((e) => {
    const name = e.target.value;
    setSelectedTemplate(name);
    if (name) {
      const template = templates.find(t => t.name === name);
      if (template) {
        setCode(template.code);
        setConsoleLogs(prev => [...prev,
          { type: 'info', text: `Loaded template: ${template.name}` },
        ]);
      }
    }
  }, [templates]);

  // Run script
  const handleRun = useCallback(async () => {
    if (loading) return;
    setLoading(true);

    const startTime = Date.now();
    setConsoleLogs(prev => [...prev,
      { type: 'info', text: `Running script for ${ticker} (${period})...` },
    ]);

    try {
      const res = await fetch(`${API}/api/scripts/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, ticker, period }),
      });

      const data = await res.json();

      if (!res.ok) {
        setConsoleLogs(prev => [...prev,
          { type: 'error', text: `Error: ${data.detail || 'Script execution failed'}` },
        ]);
        setLoading(false);
        return;
      }

      const elapsed = Date.now() - startTime;

      // Update chart data
      setOhlcv(data.ohlcv || []);
      setPlots(data.plots || []);
      setHlines(data.hlines || []);
      setIndicatorTitle(data.indicator_title || 'Custom Indicator');
      setBarCount(data.bars || 0);

      // Update console
      const newLogs = [];
      if (data.errors?.length > 0) {
        for (const err of data.errors) {
          newLogs.push({ type: 'error', text: err });
        }
      }
      if (data.logs?.length > 0) {
        for (const log of data.logs) {
          newLogs.push({ type: 'success', text: log });
        }
      }
      newLogs.push({
        type: 'success',
        text: `✓ ${data.plots?.length || 0} plot(s) rendered · ${data.bars} bars · ${elapsed}ms`,
      });

      setConsoleLogs(prev => [...prev, ...newLogs]);
    } catch (err) {
      setConsoleLogs(prev => [...prev,
        { type: 'error', text: `Network error: ${err.message}. Is the backend running?` },
      ]);
    }

    setLoading(false);
  }, [code, ticker, period, loading]);

  // Save script
  const handleSave = useCallback(async () => {
    if (!token) {
      setConsoleLogs(prev => [...prev,
        { type: 'error', text: 'Login required to save scripts.' },
      ]);
      return;
    }

    const name = prompt('Script name:');
    if (!name) return;

    try {
      const res = await fetch(`${API}/api/scripts/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ name, code }),
      });

      if (res.ok) {
        setConsoleLogs(prev => [...prev,
          { type: 'success', text: `Script "${name}" saved successfully.` },
        ]);
      } else {
        setConsoleLogs(prev => [...prev,
          { type: 'error', text: 'Failed to save script.' },
        ]);
      }
    } catch {
      setConsoleLogs(prev => [...prev,
        { type: 'error', text: 'Network error — could not save.' },
      ]);
    }
  }, [code, token]);

  // Keyboard shortcut: Ctrl/Cmd + Enter to run
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        handleRun();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleRun]);

  return (
    <div className="script-editor">
      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div className="se-toolbar">
        <div className="se-toolbar__title">
          pine<span>script</span>
        </div>

        {/* Ticker input */}
        <input
          className="se-toolbar__input"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="TICKER"
          id="script-ticker-input"
        />

        {/* Period selector */}
        <div className="se-toolbar__period">
          {PERIODS.map(p => (
            <button
              key={p}
              className={`se-toolbar__period-btn ${period === p ? 'active' : ''}`}
              onClick={() => setPeriod(p)}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Template selector */}
        <select
          className="se-toolbar__select"
          value={selectedTemplate}
          onChange={handleTemplateChange}
          id="script-template-select"
        >
          <option value="">Load template...</option>
          {templates.map(t => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
        </select>

        {/* Action buttons */}
        <button
          className="se-toolbar__btn se-toolbar__btn--secondary"
          onClick={handleSave}
          id="script-save-btn"
        >
          💾 Save
        </button>

        <button
          className={`se-toolbar__btn se-toolbar__btn--run ${loading ? 'loading' : ''}`}
          onClick={handleRun}
          disabled={loading}
          id="script-run-btn"
        >
          {loading ? <span className="se-spinner" /> : '▶'}
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>

      {/* ── Chart Pane ──────────────────────────────────────────────── */}
      <div className="se-chart">
        <div className="se-chart__header">
          {indicatorTitle && (
            <div className="se-chart__indicator-title">{indicatorTitle}</div>
          )}
          {barCount > 0 && (
            <div className="se-chart__status">
              {ticker} · {barCount} bars · {plots.length} overlay(s)
            </div>
          )}
        </div>
        <div className="se-chart__body">
          {ohlcv.length > 0 ? (
            <IndicatorChart
              ohlcv={ohlcv}
              plots={plots}
              hlines={hlines}
              height={350}
            />
          ) : (
            <div className="se-empty">
              <div className="se-empty__icon">📊</div>
              <div className="se-empty__text">
                Write a script and click <strong>▶ Run</strong> to see your indicator on the chart
              </div>
              <div style={{
                fontSize: '10px',
                color: 'var(--text3)',
                fontFamily: 'DM Mono, monospace',
              }}>
                ⌘+Enter to run
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Editor Pane ─────────────────────────────────────────────── */}
      <div className="se-editor">
        <div className="se-editor__header">
          <button className="se-editor__tab active">Editor</button>
        </div>
        <div className="se-editor__body">
          <MonacoEditor
            value={code}
            onChange={setCode}
            height="100%"
          />
        </div>
      </div>

      {/* ── Console ─────────────────────────────────────────────────── */}
      <div className="se-console" id="script-console">
        <div className="se-console__header">
          <div className="se-console__title">Console</div>
          <button
            className="se-console__clear"
            onClick={() => setConsoleLogs([])}
          >
            Clear
          </button>
        </div>
        <div className="se-console__body">
          {consoleLogs.map((log, i) => (
            <div key={i} className={`se-console__line se-console__line--${log.type}`}>
              {log.text}
            </div>
          ))}
          {consoleLogs.length === 0 && (
            <div className="se-console__line" style={{ color: 'var(--text3)' }}>
              No output yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
