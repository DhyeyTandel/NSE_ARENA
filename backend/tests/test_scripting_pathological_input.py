# tests/test_scripting_pathological_input.py
"""Priority E item 4: scripting/engine.py had a tokenize()/TOKEN_SPEC
tokenizer with its own regex-safety review and pathological-input perf
test, but the actual interpreter (PineEngine.execute/_eval_expr) never
consumed its output — the live parsing path is entirely separate
hand-rolled string scanning. Testing the tokenizer's safety was testing
code an attacker's script submission never reaches; the real attack
surface is run_script() itself. Deleted the unused tokenizer (see
DECISIONS.md) and replaced its regression coverage with pathological
inputs run through the actual live entry point.

Probed manually before writing this: long operator chains and deeply
nested parens both hit Python's recursion limit (_eval_expr recurses
once per operator/paren level) and raise RecursionError — but that's
already caught by execute()'s per-line try/except and surfaces as a
normal script error, not a crash or hang. This test locks that in.
"""
import time

from scripting.engine import run_script, PineEngine

OHLCV = [
    {"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100.5 + i, "volume": 1000}
    for i in range(50)
]
TIMESTAMPS = list(range(50))

PATHOLOGICAL_INPUTS = {
    "long_operator_chain": "x = 1" + "+1" * 2500,
    "deeply_nested_parens": "x = " + "(" * 2000 + "1" + ")" * 2000,
    "long_identifier_line": "x = " + "a" * 10000,
    "unterminated_string": 'x = "' + "a" * 10000,
    "if_else_block": "if close > open\n    x = 1\nelse\n    x = 2",
}


def test_pathological_inputs_complete_quickly_without_crashing():
    for name, code in PATHOLOGICAL_INPUTS.items():
        start = time.perf_counter()
        result = run_script(code, OHLCV, TIMESTAMPS)
        elapsed = time.perf_counter() - start
        assert elapsed < 8.0, f"{name} took {elapsed:.3f}s — approaching the engine's own 8s CPU budget"
        assert result is not None


def test_if_else_line_raises_actionable_error_not_silent_noop():
    """The bug this whole item started from: an if/else line used to
    match none of _execute_line's branches and silently do nothing. It
    must now show up as a clear, specific error."""
    result = run_script("if close > open\n    x = 1", OHLCV, TIMESTAMPS)
    assert len(result.errors) == 1
    assert "ternary" in result.errors[0]


def test_variable_named_if_prefix_is_not_mistaken_for_an_if_block():
    """ifValue is a legal identifier; only the `if` keyword (word
    boundary) should trigger the not-supported error. This also covers a
    second, adjacent pre-existing bug: the assignment branch used to
    exclude any line starting with the literal characters "if" (no word
    boundary), so `ifValue = 5` silently failed to assign at all, the
    same silent-no-op failure mode as the if/else gap itself."""
    engine = PineEngine(OHLCV, TIMESTAMPS)
    engine.execute("ifValue = 5")
    assert engine.result.errors == []
    assert engine.variables["ifValue"] == 5
