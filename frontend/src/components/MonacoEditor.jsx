// components/MonacoEditor.jsx
/**
 * Monaco Editor wrapper with custom PineScript-lite language support.
 * Provides syntax highlighting, auto-completion, and a theme matching the app.
 */
import { useRef, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import '../monacoSetup';
import { cssVar, getTheme, useThemeName } from '../theme';

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


let pineRegistered = false;

function registerPineScript(monaco) {
  // Avoid re-registering
  // Module-level flag: the bundled monaco is an ES module namespace
  // object, which is frozen, so a flag cannot be stored on it.
  if (pineRegistered) return;
  pineRegistered = true;

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
  definePineTheme(monaco);
}

// Theme colours come from the CSS tokens of the active theme, so light and
// dark stay in sync with the rest of the app.
function definePineTheme(monaco) {
  const dark = getTheme() === 'dark';
  const hex = name => cssVar(name);
  const fg = name => cssVar(name).replace('#', '');
  monaco.editor.defineTheme(dark ? 'pine-dark' : 'pine-light', {
    base: dark ? 'vs-dark' : 'vs',
    inherit: true,
    rules: [
      { token: 'comment', foreground: fg('--code-comment'), fontStyle: 'italic' },
      { token: 'comment.directive', foreground: fg('--code-comment'), fontStyle: 'italic' },
      { token: 'keyword', foreground: fg('--code-keyword') },
      { token: 'number', foreground: fg('--code-number') },
      { token: 'number.float', foreground: fg('--code-number') },
      { token: 'string', foreground: fg('--code-string') },
      { token: 'variable.predefined', foreground: fg('--code-const') },
      { token: 'support.function', foreground: fg('--code-fn') },
      { token: 'constant.color', foreground: fg('--code-const') },
      { token: 'constant.style', foreground: fg('--code-const') },
      { token: 'operator', foreground: fg('--chart-axis') },
      { token: 'delimiter', foreground: fg('--chart-axis') },
      { token: 'identifier', foreground: fg('--text') },
    ],
    colors: {
      'editor.background': hex('--bg'),
      'editor.foreground': hex('--text'),
      'editor.lineHighlightBackground': hex('--canvas'),
      'editor.selectionBackground': hex('--selected'),
      'editor.inactiveSelectionBackground': hex('--hover'),
      'editorCursor.foreground': hex('--accent'),
      'editorIndentGuide.background1': hex('--border'),
      'editorLineNumber.foreground': hex('--chart-axis'),
      'editorLineNumber.activeForeground': hex('--text'),
      'editorWidget.background': hex('--bg'),
      'editorWidget.border': hex('--border'),
      'editorSuggestWidget.background': hex('--bg'),
      'editorSuggestWidget.border': hex('--border'),
      'editorSuggestWidget.selectedBackground': hex('--selected'),
      'list.hoverBackground': hex('--hover'),
    },
  });
}

// ── Component ──────────────────────────────────────────────────────────────

export function MonacoEditor({ value, onChange, height = '100%' }) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const theme = useThemeName();
  const themeId = `pine-${theme}`;

  const handleMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    registerPineScript(monaco);
    monaco.editor.setTheme(`pine-${getTheme()}`);
  }, []);

  // Re-define from the new tokens and switch live when the theme is toggled.
  useEffect(() => {
    const monaco = monacoRef.current;
    if (!monaco) return;
    definePineTheme(monaco);
    monaco.editor.setTheme(themeId);
  }, [themeId]);

  return (
    <Editor
      height={height}
      language={PINE_LANG_ID}
      theme={themeId}
      value={value}
      onChange={onChange}
      beforeMount={registerPineScript}
      onMount={handleMount}
      options={{
        fontSize: 13,
        fontFamily: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
        fontLigatures: false,
        lineNumbers: 'on',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 2,
        wordWrap: 'on',
        padding: { top: 12, bottom: 12 },
        renderLineHighlight: 'line',
        cursorBlinking: 'solid',
        smoothScrolling: false,
        suggest: {
          showKeywords: true,
          showFunctions: true,
          showVariables: true,
        },
      }}
    />
  );
}
