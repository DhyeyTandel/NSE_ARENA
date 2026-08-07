# Antigravity Follow-up — Verified Gaps After First Implementation Pass

Verified against actual code on 2026-07-12. The first pass fixed most of CODE_REVIEW.md correctly. These are the gaps that remain, ranked. Items 1–3 are worth doing before trusting competition numbers; 4–7 are hardening.

---

## Gap 1 — Limit orders still self-fill at the user's price (economic hole, CRITICAL)

`trades.py` line ~77: `execution_price = request.limit_price if order_type=="limit" and limit_price > 0 else current_price`. The circuit breaker now blocks prices outside ±10% of previous close — but **inside the band, a limit buy fills instantly at the user's own price**. A limit buy 9% below market fills immediately → instant ~9% fake profit, repeatable every trade → leaderboard is still corruptible.

**Prompt:**

> In `backend/api/routes/trades.py`, limit orders currently execute at the user's `limit_price` unconditionally (after circuit-breaker check). This lets users buy below market / sell above market within the ±10% band. Fix the fill semantics:
> - Limit BUY: if `limit_price >= current_price`, fill at `current_price` (price improvement); if `limit_price < current_price`, reject with 400 "limit price below market — order would not fill" (we don't support resting orders).
> - Limit SELL: mirror — fill at `current_price` if `limit_price <= current_price`, else reject.
> - Market orders unchanged (fill at `current_price`).
> Edge cases: limit exactly equal to market (fills, both sides); ensure fees are computed on the actual execution price; update any frontend copy that promises limit-price fills.
> Tests: `test_limit_buy_below_market_rejected`, `test_limit_buy_above_market_fills_at_market`, `test_limit_sell_above_market_rejected`, and an assertion that no trade can ever execute at a price != current market price.

---

## Gap 2 — Circuit breaker silently disabled when `previous_close` is missing (CRITICAL path re-opens)

`validator.py::_check_circuit_breaker` returns silently if `previous_close` is `None` or `0`, and `trades.py` passes `price_data.get("previous_close", 0.0)`. If the Redis-cached price entry doesn't include `previous_close` (check what `broadcaster` actually stores), the breaker never runs — the 0.01-limit exploit comes back through the cache path.

**Prompt:**

> Audit what `PriceBroadcaster` writes to Redis (`broadcaster.py`): does the cached payload include `previous_close`? In `trades.py`, if `previous_close` is missing or <= 0 at trade time, do NOT skip the circuit breaker — instead fetch the full quote (threaded) or reject the trade with 503 "reference price unavailable". Change `Validator._check_circuit_breaker` to raise on missing `previous_close` when called from the trade path (or add a `strict=True` flag) rather than silently passing. Test: cached price without `previous_close` → trade rejected, not executed.

---

## Gap 3 — Row locking is a silent no-op on SQLite (race fix only real on Postgres)

`with_for_update()` works on Postgres (docker-compose target ✓) but is **silently ignored by SQLite**, and the default `DATABASE_URL` in `config.py` is sqlite — which is also what pytest runs on. So the TOCTOU fix is unverified where it matters and absent in local dev. The `CheckConstraint` also won't exist in a pre-existing sqlite DB file without recreation/migration.

**Prompt:**

> 1. Run the concurrent-buy race test against the docker-compose Postgres (10 concurrent ~99k buys on 100k balance; exactly one succeeds, balance never negative). Add a CI/test marker `@pytest.mark.postgres` and document how to run it.
> 2. In `config.py`, if `ENV=production` (or `DATABASE_URL` unset in a non-dev context) and the URL is sqlite, raise at boot: locking guarantees require Postgres.
> 3. Optionally add the dialect-agnostic backstop: guarded UPDATE `SET cash_balance = cash_balance - :cost WHERE id=:id AND cash_balance >= :cost`, treating rowcount=0 as insufficient funds — this protects sqlite dev too.
> 4. Note: existing `nse_arena.db` files predate the CheckConstraint; document that dev DBs must be recreated.

---

## Gap 4 — Trades can execute on a price up to 2 minutes old

Redis cache TTL is 120 s (`broadcaster.py`) and `trades.py` uses the cached price with no staleness check. Fine for portfolio display; questionable for execution.

**Prompt:**

> Store a `fetched_at` timestamp in the cached price payload. In `submit_trade`, if the cached price is older than 15 s, refetch (threaded) before executing; if refetch fails, reject the trade rather than executing on the stale price. Portfolio/display paths keep using the 120 s cache. Test both branches.

---

## Gap 5 — `/api/scripts/run` has auth but no rate limit; regex backtracking uninterruptible

The 8 s in-interpreter deadline stops loop-based CPU burn ✓, but a single catastrophic-backtracking `re` call inside the tokenizer can't be interrupted by that check, and one user can still queue unlimited runs.

**Prompt:**

> 1. Add a per-user rate limit to `/api/scripts/run` (e.g. 10/min, Redis-based since Redis is already a dependency; return 429). Test it.
> 2. Review the tokenizer regexes in `scripting/engine.py` for catastrophic backtracking (nested quantifiers, ambiguous alternation on long inputs); anchor/bound them. Add a test feeding a pathological ~10k-char input and assert tokenization completes < 1 s.

---

## Gap 6 — JWT still in localStorage (Task 5.4 not done)

`frontend/src/hooks/useAuth.js` still stores the token in `localStorage`. Either implement the httpOnly-cookie flow (see ANTIGRAVITY_PROMPTS.md Task 5.4, including the CSRF and WebSocket-auth edge cases) or explicitly accept the XSS tradeoff in README/walkthrough. Don't leave it undecided.

---

## Gap 7 — `backend/.env` exists but is never loaded

`config.py` uses `os.getenv` only — no `load_dotenv` anywhere. Values in `backend/.env` (e.g. the Postgres `DATABASE_URL`) are silently ignored when running locally without docker. Footgun: someone edits `.env` and nothing changes.

**Prompt:**

> Either add `python-dotenv` loading at the top of `config.py` (`load_dotenv()` before any `os.getenv`), or delete `backend/.env` and keep only `backend/.env.example`, documenting that local runs must export env vars / use docker-compose. Pick one; don't keep a half-live `.env`.

---

## Also verify (claimed done, not confirmed in code)

- **Season uniqueness:** `db/models.py` shows no unique constraint on `Season.is_active` — the race fix may be logic-only. Confirm a partial unique index or idempotent create-with-catch exists; two workers booting simultaneously is the test.
- **AI agent async:** claimed `generate_content_async` — confirm no remaining sync Gemini call in `ai/agent.py` / `ai/scheduler.py`, and that a hung call has a timeout.

## Final regression prompt

> Re-run all CODE_REVIEW.md reproductions PLUS: limit-buy 9% below market (must reject, Gap 1), trade via cached price lacking previous_close (must reject, Gap 2), and the concurrency test on Postgres (Gap 3). Report failures honestly.
