# scripting/engine.py
"""
PineScript-lite interpreter.

Supports a safe subset of PineScript v5 syntax:
  - indicator(title)
  - plot(series, title?, color?, style?)
  - hline(price, title?, color?)
  - Built-in vars: open, high, low, close, volume, bar_index
  - ta.* indicator functions
  - math.* helpers
  - var declarations, arithmetic, comparisons
  - if/else, ternary ? :
  - Series lookback: close[1]

Security: NO eval(), NO imports, NO file/network access.
Execution is time-limited by the calling API route.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from scripting import indicators as ta

logger = logging.getLogger(__name__)

# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class PlotResult:
    title: str
    data: list[dict]          # [{time, value}, ...]
    color: str = "#c9a84c"    # default gold
    style: str = "line"       # line | histogram | area | circles
    linewidth: int = 2
    pane: int = 0             # 0 = overlay, 1 = separate pane


@dataclass
class HLineResult:
    price: float
    title: str = ""
    color: str = "#52525b"
    linestyle: str = "dashed"


@dataclass
class ExecutionResult:
    plots: list[PlotResult] = field(default_factory=list)
    hlines: list[HLineResult] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    indicator_title: str = "Custom Indicator"


# ── Color mapping ───────────────────────────────────────────────────────────

PINE_COLORS = {
    "color.green": "#34d399",
    "color.red": "#f87171",
    "color.blue": "#60a5fa",
    "color.orange": "#fb923c",
    "color.yellow": "#facc15",
    "color.purple": "#a78bfa",
    "color.white": "#fafafa",
    "color.gray": "#a1a1aa",
    "color.aqua": "#22d3ee",
    "color.lime": "#a3e635",
    "color.fuchsia": "#e879f9",
    "color.teal": "#2dd4bf",
    "color.silver": "#d4d4d8",
    "color.maroon": "#be123c",
    "color.navy": "#1e3a5f",
    "color.olive": "#65a30d",
    "color.black": "#0a0a0b",
}

PLOT_STYLES = {
    "plot.style_line": "line",
    "plot.style_histogram": "histogram",
    "plot.style_area": "area",
    "plot.style_circles": "circles",
    "plot.style_columns": "histogram",
    "plot.style_cross": "circles",
}


# ── Tokenizer ───────────────────────────────────────────────────────────────

TOKEN_SPEC = [
    ("COMMENT",   r"//[^\n]*"),
    ("FLOAT",     r"\d+\.\d+"),
    ("INT",       r"\d+"),
    ("STRING",    r'"[^"]*"|\'[^\']*\''),
    ("IDENT",     r"[A-Za-z_][A-Za-z0-9_.]*"),
    ("LBRACKET",  r"\["),
    ("RBRACKET",  r"\]"),
    ("LPAREN",    r"\("),
    ("RPAREN",    r"\)"),
    ("COMMA",     r","),
    ("ASSIGN",    r"="),
    ("PLUS",      r"\+"),
    ("MINUS",     r"-"),
    ("MUL",       r"\*"),
    ("DIV",       r"/"),
    ("GT",        r">"),
    ("LT",        r"<"),
    ("GE",        r">="),
    ("LE",        r"<="),
    ("EQ",        r"=="),
    ("NE",        r"!="),
    ("QUESTION",  r"\?"),
    ("COLON",     r":"),
    ("AND",       r"and"),
    ("OR",        r"or"),
    ("NOT",       r"not"),
    ("NEWLINE",   r"\n"),
    ("SKIP",      r"[ \t]+"),
]

TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
)


@dataclass
class Token:
    type: str
    value: str
    line: int


def tokenize(code: str) -> list[Token]:
    tokens = []
    for lineno, line_text in enumerate(code.split("\n"), 1):
        for m in TOKEN_RE.finditer(line_text):
            kind = m.lastgroup
            val = m.group()
            if kind == "COMMENT" or kind == "SKIP":
                continue
            tokens.append(Token(kind, val, lineno))
        tokens.append(Token("NEWLINE", "\\n", lineno))
    return tokens


# ── Execution Engine ────────────────────────────────────────────────────────

class PineEngine:
    """
    Executes a PineScript-lite program against OHLCV data.
    """

    def __init__(self, ohlcv: list[dict], timestamps: list[int]):
        n = len(ohlcv)
        self.n = n
        self.timestamps = timestamps

        # Built-in series from OHLCV data
        self.open = np.array([bar["open"] for bar in ohlcv], dtype=float)
        self.high = np.array([bar["high"] for bar in ohlcv], dtype=float)
        self.low = np.array([bar["low"] for bar in ohlcv], dtype=float)
        self.close = np.array([bar["close"] for bar in ohlcv], dtype=float)
        self.volume = np.array([bar.get("volume", 0) for bar in ohlcv], dtype=float)
        self.bar_index = np.arange(n, dtype=float)
        self.hl2 = (self.high + self.low) / 2.0
        self.hlc3 = (self.high + self.low + self.close) / 3.0
        self.ohlc4 = (self.open + self.high + self.low + self.close) / 4.0

        # Variable storage
        self.variables: dict[str, Any] = {}

        # Results
        self.result = ExecutionResult()

    def _resolve(self, name: str) -> Any:
        """Resolve a variable name to its value (series or scalar)."""
        builtins = {
            "open": self.open, "high": self.high, "low": self.low,
            "close": self.close, "volume": self.volume,
            "bar_index": self.bar_index,
            "hl2": self.hl2, "hlc3": self.hlc3, "ohlc4": self.ohlc4,
        }
        if name in builtins:
            return builtins[name]
        if name in self.variables:
            return self.variables[name]
        if name in PINE_COLORS:
            return PINE_COLORS[name]
        if name in PLOT_STYLES:
            return PLOT_STYLES[name]
        if name == "true":
            return True
        if name == "false":
            return False
        if name == "na":
            return np.nan
        return None

    def _call_ta(self, func_name: str, args: list) -> Any:
        """Dispatch a ta.* function call."""
        fn_map = {
            "ta.sma": lambda a: ta.sma(self._to_array(a[0]), int(a[1])),
            "ta.ema": lambda a: ta.ema(self._to_array(a[0]), int(a[1])),
            "ta.wma": lambda a: ta.wma(self._to_array(a[0]), int(a[1])),
            "ta.rsi": lambda a: ta.rsi(self._to_array(a[0]), int(a[1])),
            "ta.roc": lambda a: ta.roc(self._to_array(a[0]), int(a[1])),
            "ta.atr": lambda a: ta.atr(
                self._to_array(a[0]), self._to_array(a[1]),
                self._to_array(a[2]), int(a[3]) if len(a) > 3 else 14
            ),
            "ta.vwap": lambda a: ta.vwap(
                self._to_array(a[0]), self._to_array(a[1])
            ),
            "ta.macd": lambda a: ta.macd(
                self._to_array(a[0]),
                int(a[1]) if len(a) > 1 else 12,
                int(a[2]) if len(a) > 2 else 26,
                int(a[3]) if len(a) > 3 else 9,
            ),
            "ta.bbands": lambda a: ta.bbands(
                self._to_array(a[0]),
                int(a[1]) if len(a) > 1 else 20,
                float(a[2]) if len(a) > 2 else 2.0,
            ),
            "ta.stoch": lambda a: ta.stoch(
                self._to_array(a[0]), self._to_array(a[1]),
                self._to_array(a[2]),
                int(a[3]) if len(a) > 3 else 14,
            ),
            "ta.crossover": lambda a: ta.crossover(
                self._to_array(a[0]), self._to_array(a[1])
            ),
            "ta.crossunder": lambda a: ta.crossunder(
                self._to_array(a[0]), self._to_array(a[1])
            ),
            "ta.highest": lambda a: ta.highest(
                self._to_array(a[0]), int(a[1])
            ),
            "ta.lowest": lambda a: ta.lowest(
                self._to_array(a[0]), int(a[1])
            ),
            "ta.sma": lambda a: ta.sma(self._to_array(a[0]), int(a[1])),
        }

        if func_name in fn_map:
            return fn_map[func_name](args)
        raise ValueError(f"Unknown function: {func_name}")

    def _call_math(self, func_name: str, args: list) -> Any:
        """Dispatch math.* functions."""
        a = [self._to_array(x) if isinstance(x, np.ndarray) else x for x in args]
        if func_name == "math.abs":
            return np.abs(self._to_array(a[0]))
        if func_name == "math.max":
            return np.maximum(self._to_array(a[0]), self._to_array(a[1]))
        if func_name == "math.min":
            return np.minimum(self._to_array(a[0]), self._to_array(a[1]))
        if func_name == "math.round":
            return np.round(self._to_array(a[0]),
                            int(a[1]) if len(a) > 1 else 0)
        if func_name == "math.sqrt":
            return np.sqrt(self._to_array(a[0]))
        if func_name == "math.log":
            return np.log(self._to_array(a[0]))
        raise ValueError(f"Unknown function: {func_name}")

    def _to_array(self, val) -> np.ndarray:
        """Convert a value to a numpy array (broadcast scalars)."""
        if isinstance(val, np.ndarray):
            return val
        if isinstance(val, (int, float)):
            return np.full(self.n, val, dtype=float)
        if isinstance(val, bool):
            return np.full(self.n, float(val), dtype=float)
        return np.full(self.n, np.nan, dtype=float)

    def _series_to_plot_data(self, series: np.ndarray) -> list[dict]:
        """Convert a numpy series to [{time, value}] for the frontend."""
        data = []
        for i in range(len(series)):
            if np.isnan(series[i]):
                continue
            data.append({
                "time": self.timestamps[i],
                "value": round(float(series[i]), 4),
            })
        return data

    # ── High-level line-by-line interpreter ──────────────────────────────

    def execute(self, code: str) -> ExecutionResult:
        """Parse and execute a PineScript-lite program."""
        lines = code.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1

            # Skip empty lines and comments
            if not line or line.startswith("//") or line.startswith("//@"):
                continue

            try:
                self._execute_line(line)
            except Exception as e:
                self.result.errors.append(f"Line {i}: {str(e)}")
                logger.warning("Script error at line %d: %s", i, e)

        self.result.logs.append(
            f"Executed: {len(self.result.plots)} plot(s), "
            f"{self.n} bars processed"
        )
        return self.result

    def _execute_line(self, line: str):
        """Execute a single line of PineScript-lite."""
        # indicator() declaration
        if line.startswith("indicator("):
            args = self._parse_call_args(line, "indicator")
            if args:
                title = self._eval_expr(args[0])
                if isinstance(title, str):
                    self.result.indicator_title = title
                # Check for overlay parameter
                for arg in args:
                    arg = arg.strip()
                    if arg.startswith("overlay"):
                        pass  # Just accept it
            return

        # plot() call
        if line.startswith("plot("):
            args = self._parse_call_args(line, "plot")
            if not args:
                return
            series = self._eval_expr(args[0])
            title = "Plot"
            color = "#c9a84c"
            style = "line"
            linewidth = 2

            # Parse named parameters
            for arg in args[1:]:
                arg = arg.strip()
                if "=" in arg:
                    key, val = arg.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "title":
                        title = self._eval_expr(val)
                    elif key == "color":
                        title_check = self._eval_expr(val)
                        if isinstance(title_check, str):
                            color = title_check
                    elif key == "style":
                        s = self._eval_expr(val)
                        if isinstance(s, str):
                            style = s
                    elif key == "linewidth":
                        linewidth = int(val)
                else:
                    # Positional: title, color, ...
                    evaled = self._eval_expr(arg)
                    if isinstance(evaled, str):
                        if evaled.startswith("#") or evaled.startswith("rgb"):
                            color = evaled
                        else:
                            title = evaled

            arr = self._to_array(series)
            # Determine pane: overlays on main, oscillators on separate
            pane = 0
            if title.lower() in ("rsi", "macd", "stochastic", "histogram",
                                  "signal", "stoch", "roc", "momentum"):
                pane = 1
            # Auto-detect: if values are mostly 0-100 range, use separate pane
            valid = arr[~np.isnan(arr)]
            if len(valid) > 0:
                vmin, vmax = np.min(valid), np.max(valid)
                close_range = (np.min(self.close), np.max(self.close))
                if vmax <= 100 and vmin >= 0 and close_range[0] > 100:
                    pane = 1

            self.result.plots.append(PlotResult(
                title=title if isinstance(title, str) else "Plot",
                data=self._series_to_plot_data(arr),
                color=color if isinstance(color, str) else "#c9a84c",
                style=style,
                linewidth=linewidth,
                pane=pane,
            ))
            return

        # hline() call
        if line.startswith("hline("):
            args = self._parse_call_args(line, "hline")
            if args:
                price = float(self._eval_expr(args[0]))
                title = ""
                color = "#52525b"
                for arg in args[1:]:
                    arg = arg.strip()
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k == "title":
                            title = self._eval_expr(v)
                        elif k == "color":
                            c = self._eval_expr(v)
                            if isinstance(c, str):
                                color = c
                self.result.hlines.append(HLineResult(
                    price=price, title=title, color=color
                ))
            return

        # Variable assignment: varName = expression
        if "=" in line and not line.startswith("if") and "==" not in line.replace("==", ""):
            # Handle multi-assignment for tuple returns: [a, b, c] = ta.macd(...)
            if line.startswith("["):
                bracket_end = line.index("]")
                var_names = [v.strip() for v in line[1:bracket_end].split(",")]
                expr = line[bracket_end + 1:].strip()
                if expr.startswith("="):
                    expr = expr[1:].strip()
                result = self._eval_expr(expr)
                if isinstance(result, tuple):
                    for j, name in enumerate(var_names):
                        if j < len(result):
                            self.variables[name] = result[j]
                return

            parts = line.split("=", 1)
            var_part = parts[0].strip()
            expr = parts[1].strip()

            # Handle "var name = ..." syntax
            if var_part.startswith("var "):
                var_part = var_part[4:].strip()

            # Handle type annotations: "float name = ..."
            for typ in ("float", "int", "bool", "string", "series"):
                if var_part.startswith(typ + " "):
                    var_part = var_part[len(typ) + 1:].strip()
                    break

            self.variables[var_part] = self._eval_expr(expr)
            return

    def _parse_call_args(self, line: str, func_name: str) -> list[str]:
        """Extract arguments from a function call like func(a, b, c)."""
        start = line.index("(")
        # Find matching closing paren
        depth = 0
        end = start
        for ci in range(start, len(line)):
            if line[ci] == "(":
                depth += 1
            elif line[ci] == ")":
                depth -= 1
                if depth == 0:
                    end = ci
                    break

        inner = line[start + 1:end].strip()
        if not inner:
            return []

        # Split by commas, respecting nested parens
        args = []
        depth = 0
        current = []
        for ch in inner:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue
            current.append(ch)
        if current:
            args.append("".join(current).strip())

        return args

    def _eval_expr(self, expr: str) -> Any:
        """Evaluate an expression and return a value (array, scalar, or string)."""
        expr = expr.strip()

        # String literal
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # Numeric literal
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # Ternary: condition ? true_val : false_val
        if "?" in expr and ":" in expr:
            q_idx = expr.index("?")
            c_idx = expr.index(":", q_idx)
            cond = self._eval_expr(expr[:q_idx])
            true_val = self._eval_expr(expr[q_idx + 1:c_idx])
            false_val = self._eval_expr(expr[c_idx + 1:])
            cond_arr = self._to_array(cond)
            true_arr = self._to_array(true_val)
            false_arr = self._to_array(false_val)
            return np.where(cond_arr > 0, true_arr, false_arr)

        # Binary arithmetic: handle + - * /  (simple left-to-right)
        # Look for top-level operators (not inside parens)
        for ops in [("+" , "-"), ("*", "/")]:
            depth = 0
            for i in range(len(expr) - 1, 0, -1):
                if expr[i] == ")":
                    depth += 1
                elif expr[i] == "(":
                    depth -= 1
                elif depth == 0 and expr[i] in ops:
                    # Make sure it's not part of a negative number or identifier
                    if expr[i] == "-" and i > 0 and expr[i-1] in "(,= ":
                        continue
                    left = self._eval_expr(expr[:i])
                    right = self._eval_expr(expr[i + 1:])
                    left_arr = self._to_array(left)
                    right_arr = self._to_array(right)
                    if expr[i] == "+":
                        return left_arr + right_arr
                    elif expr[i] == "-":
                        return left_arr - right_arr
                    elif expr[i] == "*":
                        return left_arr * right_arr
                    elif expr[i] == "/":
                        return np.divide(left_arr, right_arr,
                                         out=np.full_like(left_arr, np.nan),
                                         where=right_arr != 0)

        # Comparison operators
        for op in (">=", "<=", "==", "!=", ">", "<"):
            depth = 0
            for i in range(len(expr) - len(op), 0, -1):
                if expr[i] == ")":
                    depth += 1
                elif expr[i] == "(":
                    depth -= 1
                elif depth == 0 and expr[i:i + len(op)] == op:
                    left_arr = self._to_array(self._eval_expr(expr[:i]))
                    right_arr = self._to_array(self._eval_expr(expr[i + len(op):]))
                    if op == ">=":
                        return (left_arr >= right_arr).astype(float)
                    elif op == "<=":
                        return (left_arr <= right_arr).astype(float)
                    elif op == "==":
                        return (left_arr == right_arr).astype(float)
                    elif op == "!=":
                        return (left_arr != right_arr).astype(float)
                    elif op == ">":
                        return (left_arr > right_arr).astype(float)
                    elif op == "<":
                        return (left_arr < right_arr).astype(float)

        # Parenthesized expression
        if expr.startswith("(") and expr.endswith(")"):
            return self._eval_expr(expr[1:-1])

        # Series lookback: close[1], myVar[3]
        bracket_match = re.match(r"^([A-Za-z_]\w*)\[(\d+)\]$", expr)
        if bracket_match:
            var_name = bracket_match.group(1)
            offset = int(bracket_match.group(2))
            base = self._resolve(var_name)
            if base is not None and isinstance(base, np.ndarray):
                shifted = np.full_like(base, np.nan)
                if offset < len(base):
                    shifted[offset:] = base[:-offset] if offset > 0 else base
                return shifted
            return np.nan

        # Function call: ta.sma(close, 14), math.abs(x), nz(x)
        func_match = re.match(r"^([A-Za-z_][\w.]*)\((.*)$", expr)
        if func_match and expr.endswith(")"):
            func_name = func_match.group(1)
            args = self._parse_call_args(expr, func_name)
            evaled_args = [self._eval_expr(a) for a in args]

            if func_name.startswith("ta."):
                return self._call_ta(func_name, evaled_args)
            if func_name.startswith("math."):
                return self._call_math(func_name, evaled_args)
            if func_name == "nz":
                arr = self._to_array(evaled_args[0])
                fallback = float(evaled_args[1]) if len(evaled_args) > 1 else 0.0
                return np.where(np.isnan(arr), fallback, arr)
            if func_name == "na":
                arr = self._to_array(evaled_args[0])
                return np.isnan(arr).astype(float)
            if func_name == "fixnan":
                arr = self._to_array(evaled_args[0]).copy()
                for idx in range(1, len(arr)):
                    if np.isnan(arr[idx]):
                        arr[idx] = arr[idx - 1]
                return arr

            raise ValueError(f"Unknown function: {func_name}")

        # Variable/constant reference
        resolved = self._resolve(expr)
        if resolved is not None:
            return resolved

        # If nothing matched, it might be an unrecognized identifier
        raise ValueError(f"Cannot evaluate: '{expr}'")


# ── Public API ──────────────────────────────────────────────────────────────

def run_script(code: str, ohlcv: list[dict],
               timestamps: list[int]) -> ExecutionResult:
    """
    Execute a PineScript-lite program against OHLCV data.

    Args:
        code: The PineScript-lite source code
        ohlcv: List of {open, high, low, close, volume} dicts
        timestamps: List of Unix timestamps (seconds) for each bar

    Returns:
        ExecutionResult with plots, hlines, logs, and errors
    """
    if not ohlcv:
        result = ExecutionResult()
        result.errors.append("No market data available")
        return result

    engine = PineEngine(ohlcv, timestamps)
    return engine.execute(code)
