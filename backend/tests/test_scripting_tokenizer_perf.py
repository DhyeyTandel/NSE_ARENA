# tests/test_scripting_tokenizer_perf.py
"""Item 5 (ANTIGRAVITY_NEXT.md): tokenizer regex backtracking review.

Reviewed every regex in scripting/engine.py's TOKEN_SPEC plus the two ad
hoc `re.match` calls in expression parsing — none use nested quantifiers
or ambiguous alternation (the classic ReDoS shapes like `(a+)+` or
`(a|a)+`), so none are exponential. The one pattern with an unbounded
scan is STRING (`"[^"]*"` / `'[^']*'`), which is O(n) per unmatched
start — worst case O(n^2) for adversarial input with many unterminated
quotes, not exponential. This asserts that worst case still finishes
comfortably under budget.
"""
import time

from scripting.engine import tokenize

PATHOLOGICAL_INPUTS = {
    "unterminated_double_quotes": '"' * 10_000,
    "unterminated_single_quotes": "'" * 10_000,
    "alternating_quote_chars": ('"' + "'") * 5_000,
    "long_identifier": "a" * 10_000,
    "long_repeated_expression": "x=1+" * 2_500,
}


def test_tokenizer_handles_pathological_input_under_one_second():
    for name, code in PATHOLOGICAL_INPUTS.items():
        start = time.perf_counter()
        tokenize(code)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"{name} took {elapsed:.3f}s — possible ReDoS regression"
