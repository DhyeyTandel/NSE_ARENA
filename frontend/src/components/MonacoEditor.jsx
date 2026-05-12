// components/MonacoEditor.jsx
/**
 * Monaco Editor wrapper with custom PineScript-lite language support.
 * Provides syntax highlighting, auto-completion, and dark theme matching the app.
 */
import { useRef, useCallback } from 'react';
import Editor from '@monaco-editor/react';

// ── PineScript-lite language definition (Monarch tokenizer) ────────────────

const PINE_LANG_ID = 'pinescript';

const PINE_KEYWORDS = [
  'indicator', 'strategy', 'plot', 'hline', 'fill', 'bgcolor',
  'if', 'else', 'for', 'while', 'switch', 'var', 'varip',
  'true', 'false', 'na', 'and', 'or', 'not',
  'float', 'int', 'bool', 'string', 'series', 'color',
  'import', 'export', 'type', 'method',
];

const PINE_BUILTINS = [
  // ta.* functions
  'ta.sma', 'ta.ema', 'ta.wma', 'ta.rsi', 'ta.macd', 'ta.bbands',
  'ta.stoch', 'ta.atr', 'ta.vwap', 'ta.roc',
  'ta.crossover', 'ta.crossunder', 'ta.highest', 'ta.lowest',
  // math.* functions
  'math.abs', 'math.max', 'math.min', 'math.round', 'math.sqrt', 'math.log',
  // utility functions
  'nz', 'na', 'fixnan',
];

const PINE_VARIABLES = [
  'open', 'high', 'low', 'close', 'volume',
  'bar_index', 'hl2', 'hlc3', 'ohlc4',
];

const PINE_COLORS = [
  'color.green', 'color.red', 'color.blue', 'color.orange',
  'color.yellow', 'color.purple', 'color.white', 'color.gray',
  'color.aqua', 'color.lime', 'color.fuchsia', 'color.teal',
  'color.silver', 'color.maroon', 'color.navy', 'color.olive',
  'color.black',
];

const PINE_STYLES = [
  'plot.style_line', 'plot.style_histogram', 'plot.style_area',
  'plot.style_circles', 'plot.style_columns', 'plot.style_cross',
];


function registerPineScript(monaco) {
  // Avoid re-registering
  if (monaco.__pineRegistered) return;
  monaco.__pineRegistered = true;

  // Register language
  monaco.languages.register({ id: PINE_LANG_ID });

  // Monarch tokenizer
  monaco.languages.setMonarchTokensProvider(PINE_LANG_ID, {
    keywords: PINE_KEYWORDS,
    builtins: [...PINE_BUILTINS, ...PINE_VARIABLES],
    colors: PINE_COLORS,
    styles: PINE_STYLES,

    tokenizer: {
      root: [
        // Comments
        [/\/\/.*$/, 'comment'],
        [/\/\/@.*$/, 'comment.directive'],

        // Strings
        [/"[^"]*"/, 'string'],
        [/'[^']*'/, 'string'],

        // Numbers
        [/\d+\.\d+/, 'number.float'],
        [/\d+/, 'number'],

        // Colors (color.green, etc.)
        [/color\.\w+/, 'constant.color'],

        // Plot styles
        [/plot\.style_\w+/, 'constant.style'],

        // Built-in functions (ta.*, math.*)
        [/(?:ta|math)\.\w+/, 'support.function'],

        // Built-in variables
        [/\b(?:open|high|low|close|volume|bar_index|hl2|hlc3|ohlc4)\b/, 'variable.predefined'],

        // Keywords
        [/[a-zA-Z_]\w*/, {
          cases: {
            '@keywords': 'keyword',
            '@default': 'identifier',
          }
        }],

        // Operators
        [/[+\-*/=<>!?:]/, 'operator'],
        [/[{}()\[\],]/, 'delimiter'],
      ],
    },
  });

  // ── Auto-completion ──────────────────────────────────────────────────

  monaco.languages.registerCompletionItemProvider(PINE_LANG_ID, {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };

      const suggestions = [];

      // ta.* functions with docs
      const taFuncs = [
        { label: 'ta.sma', detail: '(source, length) → Simple Moving Average', insert: 'ta.sma(close, 14)' },
        { label: 'ta.ema', detail: '(source, length) → Exponential Moving Average', insert: 'ta.ema(close, 14)' },
        { label: 'ta.wma', detail: '(source, length) → Weighted Moving Average', insert: 'ta.wma(close, 14)' },
        { label: 'ta.rsi', detail: '(source, length) → Relative Strength Index', insert: 'ta.rsi(close, 14)' },
        { label: 'ta.macd', detail: '(source, fast, slow, signal) → MACD tuple', insert: 'ta.macd(close, 12, 26, 9)' },
        { label: 'ta.bbands', detail: '(source, length, mult) → Bollinger Bands tuple', insert: 'ta.bbands(close, 20, 2.0)' },
        { label: 'ta.stoch', detail: '(close, high, low, length) → Stochastic %K', insert: 'ta.stoch(close, high, low, 14)' },
        { label: 'ta.atr', detail: '(high, low, close, length) → Average True Range', insert: 'ta.atr(high, low, close, 14)' },
        { label: 'ta.vwap', detail: '(close, volume) → Volume Weighted Avg Price', insert: 'ta.vwap(close, volume)' },
        { label: 'ta.roc', detail: '(source, length) → Rate of Change', insert: 'ta.roc(close, 14)' },
        { label: 'ta.crossover', detail: '(a, b) → Cross above detection', insert: 'ta.crossover(fast, slow)' },
        { label: 'ta.crossunder', detail: '(a, b) → Cross below detection', insert: 'ta.crossunder(fast, slow)' },
        { label: 'ta.highest', detail: '(source, length) → Highest value', insert: 'ta.highest(high, 14)' },
        { label: 'ta.lowest', detail: '(source, length) → Lowest value', insert: 'ta.lowest(low, 14)' },
      ];

      for (const f of taFuncs) {
        suggestions.push({
          label: f.label,
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: f.insert,
          detail: f.detail,
          range,
        });
      }

      // Built-in variables
      for (const v of PINE_VARIABLES) {
        suggestions.push({
          label: v,
          kind: monaco.languages.CompletionItemKind.Variable,
          insertText: v,
          detail: 'Built-in series',
          range,
        });
      }

      // Colors
      for (const c of PINE_COLORS) {
        suggestions.push({
          label: c,
          kind: monaco.languages.CompletionItemKind.Color,
          insertText: c,
          range,
        });
      }

      // Keywords
      for (const k of PINE_KEYWORDS) {
        suggestions.push({
          label: k,
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: k,
          range,
        });
      }

      // Snippet: indicator declaration
      suggestions.push({
        label: 'indicator',
        kind: monaco.languages.CompletionItemKind.Snippet,
        insertText: 'indicator("${1:My Indicator}", overlay=${2:false})',
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        detail: 'Declare an indicator',
        range,
      });

      // Snippet: plot
      suggestions.push({
        label: 'plot',
        kind: monaco.languages.CompletionItemKind.Snippet,
        insertText: 'plot(${1:series}, title="${2:Plot}", color=${3:color.blue})',
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        detail: 'Plot a series on the chart',
        range,
      });

      return { suggestions };
    },
  });

  // ── Hover provider ───────────────────────────────────────────────────

  monaco.languages.registerHoverProvider(PINE_LANG_ID, {
    provideHover: (model, position) => {
      const word = model.getWordAtPosition(position);
      if (!word) return null;

      const docs = {
        'sma': '**ta.sma(source, length)**\n\nSimple Moving Average — average of last `length` values.',
        'ema': '**ta.ema(source, length)**\n\nExponential Moving Average — weighted toward recent values.',
        'rsi': '**ta.rsi(source, length)**\n\nRelative Strength Index (0–100). >70 = overbought, <30 = oversold.',
        'macd': '**ta.macd(source, fast, slow, signal)**\n\nReturns [macdLine, signalLine, histogram].',
        'bbands': '**ta.bbands(source, length, mult)**\n\nReturns [upper, middle, lower] Bollinger Bands.',
        'atr': '**ta.atr(high, low, close, length)**\n\nAverage True Range — measures volatility.',
        'vwap': '**ta.vwap(close, volume)**\n\nVolume Weighted Average Price.',
        'close': '**close** — Closing price series for each bar.',
        'open': '**open** — Opening price series for each bar.',
        'high': '**high** — High price series for each bar.',
        'low': '**low** — Low price series for each bar.',
        'volume': '**volume** — Trading volume series for each bar.',
      };

      const doc = docs[word.word];
      if (doc) {
        return {
          range: new monaco.Range(
            position.lineNumber, word.startColumn,
            position.lineNumber, word.endColumn
          ),
          contents: [{ value: doc }],
        };
      }
      return null;
    },
  });

  // ── Theme ────────────────────────────────────────────────────────────

  monaco.editor.defineTheme('pine-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '52525b', fontStyle: 'italic' },
      { token: 'comment.directive', foreground: '52525b', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'c9a84c' },
      { token: 'number', foreground: '34d399' },
      { token: 'number.float', foreground: '34d399' },
      { token: 'string', foreground: 'fb923c' },
      { token: 'variable.predefined', foreground: '60a5fa' },
      { token: 'support.function', foreground: 'a78bfa' },
      { token: 'constant.color', foreground: 'e879f9' },
      { token: 'constant.style', foreground: 'e879f9' },
      { token: 'operator', foreground: 'a1a1aa' },
      { token: 'delimiter', foreground: '71717a' },
      { token: 'identifier', foreground: 'fafafa' },
    ],
    colors: {
      'editor.background': '#0a0a0b',
      'editor.foreground': '#fafafa',
      'editor.lineHighlightBackground': '#18181b',
      'editor.selectionBackground': '#c9a84c30',
      'editor.inactiveSelectionBackground': '#c9a84c15',
      'editorCursor.foreground': '#c9a84c',
      'editorIndentGuide.background': '#ffffff09',
      'editorIndentGuide.activeBackground': '#ffffff14',
      'editorLineNumber.foreground': '#3f3f46',
      'editorLineNumber.activeForeground': '#a1a1aa',
      'editorWidget.background': '#18181b',
      'editorWidget.border': '#ffffff14',
      'editorSuggestWidget.background': '#18181b',
      'editorSuggestWidget.border': '#ffffff14',
      'editorSuggestWidget.selectedBackground': '#27272a',
      'list.hoverBackground': '#27272a',
    },
  });
}


// ── Component ──────────────────────────────────────────────────────────────

export function MonacoEditor({ value, onChange, height = '100%' }) {
  const editorRef = useRef(null);

  const handleMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    registerPineScript(monaco);
    monaco.editor.setTheme('pine-dark');
  }, []);

  return (
    <Editor
      height={height}
      language={PINE_LANG_ID}
      theme="pine-dark"
      value={value}
      onChange={onChange}
      beforeMount={registerPineScript}
      onMount={handleMount}
      options={{
        fontSize: 13,
        fontFamily: "'DM Mono', 'Fira Code', monospace",
        fontLigatures: true,
        lineNumbers: 'on',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 2,
        wordWrap: 'on',
        padding: { top: 12, bottom: 12 },
        renderLineHighlight: 'line',
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        smoothScrolling: true,
        suggest: {
          showKeywords: true,
          showFunctions: true,
          showVariables: true,
        },
      }}
    />
  );
}
