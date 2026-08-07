# StockPaper / NSE Arena — Production Readiness Review

**Scope:** `backend/` (FastAPI, SQLAlchemy async, yfinance, Gemini) and `frontend/` (React/Vite).
**Date:** 2026-07-11
**Method:** Static read-through of the full source tree plus a pure-logic simulation of the trade endpoint's arithmetic. No repository files or database state were modified; the verification script below runs standalone.

---

## Executive summary

The engine layer (`engine/validator.py`, `engine/order_book.py`, `engine/matching.py`) is well designed — it has market-hours checks, a ±10% circuit breaker, balance/holdings validation, and a locked matching engine. **The problem is that the live `/trades` endpoint doesn't use any of it.** It reimplements a naive, unvalidated buy/sell path that skips every one of those safeguards. As a result, the single highest-leverage fix (routing the endpoint through the code you already wrote and tested) closes the three most severe issues at once.

The second theme is **blocking I/O on the async event loop**: `yfinance` calls run synchronously inside `async def` handlers in the trade, portfolio, and price paths, so one slow upstream call stalls the entire server.

Ranked below by leverage — impact of the flaw multiplied by how cheaply it's fixed.

> **⚠️ Blocker found first:** `api/routes/portfolio.py` line 46 reads `for pos in positions:5` — a stray `5` that is a hard `SyntaxError`/`IndentationError`. The file does **not** parse (`python3 -c "import ast; ast.parse(open('api/routes/portfolio.py').read())"` raises), so `main.py`'s `from api.routes import ... portfolio` fails and **the server cannot start at all** in its current state. Fix this one character before anything else. Verified this session.

---

## #1 — Trade endpoint bypasses validation → economic integrity broken (money can be minted)

**Severity: Critical · Effort: Low · Leverage: Highest**

`api/routes/trades.py::submit_trade` is the real order path, but it never constructs an `Order`, never calls `Validator.validate`, and never touches the `MatchingEngine`. Three exploitable holes fall out of this:

1. **No `quantity > 0` check.** `TradeRequest.quantity` is a bare `int`. A negative quantity makes `total_cost = execution_price * quantity + fees` negative, so the balance check `total_cost > cash_balance` passes, and `cash_balance -= total_cost` _adds_ cash. Free money, plus a position with negative quantity that corrupts P&L and the leaderboard.
2. **User-named limit price fills instantly with no market reference.** `execution_price = request.limit_price if order_type=="limit" and limit_price>0 else current_price`. A limit buy at `0.01` executes immediately at `0.01` regardless of the real price — the circuit breaker in `validator.py` that would catch this is never called.
3. **No market-hours enforcement.** `_check_market_hours` exists but is unreachable from this endpoint, so trades execute 24/7.

The `Validator` class already prevents all three. This is dead-code risk: the correct logic exists and is simply not wired in.

**Reproduction (standalone, no repo state — replicates the endpoint's exact arithmetic):**

```python
def fee_total(price, qty):
    value = price * qty
    sub = value*0.001 + min(value*0.0003, 20.0) + value*0.0000345 + value*0.000001
    return round(sub + sub*0.18, 2)

def simulate_buy(cash, qty, order_type, limit_price, market_price):
    execution_price = limit_price if order_type=="limit" and limit_price>0 else market_price
    total_cost = execution_price*qty + fee_total(execution_price, qty)
    if total_cost > cash:              # exact check from trades.py
        return "REJECTED", cash
    cash -= total_cost
    return "EXECUTED", cash

# A: negative quantity mints cash
print(simulate_buy(100000, -1000, "market", 0, 2500))
# -> ('EXECUTED', 2603939.72)   cash grew by ~2.5M

# B: limit price of 0.01 buys a 2500-rupee stock for ~nothing
print(simulate_buy(100000, 100, "limit", 0.01, 2500))
# -> ('EXECUTED', 99999.00)     100 shares (worth 250k) acquired for ~1
```

Both lines were run and produced exactly the outputs shown.

**Unit tests to add (should currently FAIL):**

- `test_negative_quantity_rejected` — POST `/trades` with `quantity=-10` returns 4xx and leaves `cash_balance` unchanged.
- `test_limit_far_below_market_rejected` — limit buy at 1% of market price is rejected by the circuit breaker.
- `test_trade_rejected_outside_market_hours` — freeze clock to a weekend/after-hours and assert `MarketClosedError` → 4xx.

**Fix:** Build an `Order` in `submit_trade` and call `Validator.validate(order, balance, holdings, previous_close, market_price)` before mutating the portfolio. Add `quantity: conint(gt=0)` and `limit_price: confloat(ge=0)` to the Pydantic model as defense in depth.

---

## #2 — Cash-balance race condition (TOCTOU) → overdraw / double-spend

**Severity: Critical · Effort: Medium · Leverage: High**

The buy path does read-check-write with no atomicity:

```python
if total_cost > portfolio.cash_balance:   # check
    raise ...
portfolio.cash_balance -= total_cost      # write
```

Two concurrent requests for the same portfolio both read the same balance, both pass the check, and both deduct — the account goes negative (buy more than you can afford). SQLite via `aiosqlite` gives no row-level locking, and `get_db` commits per-request with no `SELECT … FOR UPDATE` or optimistic version column. The same pattern lets a user sell the same confirmed position twice.

**Reproduction (integration):**

```python
import asyncio, httpx
# user starts with 100_000; each order costs ~99_000
async def fire(c, tok):
    return await c.post("http://localhost:8000/trades",
        headers={"Authorization": f"Bearer {tok}"},
        json={"ticker":"RELIANCE","side":"buy","order_type":"limit",
              "limit_price":990,"quantity":100})
async def main(tok):
    async with httpx.AsyncClient() as c:
        await asyncio.gather(*[fire(c, tok) for _ in range(10)])
# Then GET /portfolio -> cash_balance is negative; multiple buys succeeded.
```

**Unit/integration test idea:** fire N concurrent buys that individually fit but collectively exceed the balance; assert exactly one (or the affordable subset) succeeds and `cash_balance >= 0` always.

**Fix:** Make the debit atomic and conditional. On Postgres (your `.env` target) use `SELECT … FOR UPDATE` on the portfolio row inside the transaction, or a guarded UPDATE: `UPDATE portfolio SET cash_balance = cash_balance - :cost WHERE id=:id AND cash_balance >= :cost` and treat `rowcount == 0` as insufficient funds. Add a DB `CHECK (cash_balance >= 0)` constraint as a backstop.

---

## #3 — Synchronous yfinance calls block the async event loop

**Severity: High · Effort: Low–Medium · Leverage: High**

`MarketDataFetcher.get_price` calls `yf.Ticker(...).info`, a slow blocking HTTP round-trip (often 1–3 s). It is invoked directly inside `async def` handlers:

- `trades.py::submit_trade` — every order.
- `portfolio.py::get_portfolio` — **once per position in a loop** (N blocking calls per page load).
- `main.py::get_price` and the `broadcaster._poll_loop`.

Because these run on the event loop thread, a single slow or hung yfinance call freezes _all_ concurrent requests — WebSocket price pushes included. The `/api/scripts/run` route already shows the right pattern (`await asyncio.to_thread(...)`); the trade and portfolio paths do not.

**Reproduction (demonstrates head-of-line blocking):**

```python
# monkeypatch the fetcher to sleep 3s, then:
import asyncio, httpx, time
async def main(tok):
    async with httpx.AsyncClient(timeout=30) as c:
        h={"Authorization":f"Bearer {tok}"}
        t=time.perf_counter()
        await asyncio.gather(*[c.get("http://localhost:8000/portfolio",headers=h) for _ in range(5)])
        print("elapsed", time.perf_counter()-t)  # ~15s (serialized) not ~3s
```

If the calls were non-blocking, five parallel requests would finish in ~3 s; blocking makes them ~15 s.

**Fix:** Wrap every fetch in `await asyncio.to_thread(...)`, and serve the trade/portfolio price from the Redis cache the broadcaster already maintains, falling back to a threaded fetch only on cache miss. Batch portfolio pricing into one `yf.download(tickers)` call instead of N calls.

---

## #4 — `/api/scripts/run` is unauthenticated and the 10s timeout doesn't stop CPU work

**Severity: High · Effort: Medium · Leverage: Medium-High**

Two compounding problems on the script runner:

1. **No auth.** `run_user_script` has no `Depends(get_current_user)`, unlike `/save` and `/mine`. Anyone on the network can drive unbounded market-data fetches (arbitrary `ticker`) and CPU-bound interpretation.
2. **The timeout is an illusion.** `asyncio.wait_for(asyncio.to_thread(run_script, ...), timeout=10)` cancels the _coroutine_ on timeout but cannot kill the worker thread — Python threads aren't preemptible. A script with a heavy or catastrophically-backtracking construct keeps burning a thread-pool slot after the client gets its 408. Enough of them exhaust the default thread pool and wedge every `to_thread` caller (including the script route itself).

The interpreter itself is sound (no `eval`, no imports, no file/network) — the risk is resource exhaustion, not RCE.

**Reproduction:**

- Auth: `curl -X POST localhost:8000/api/scripts/run -H 'Content-Type: application/json' -d '{"code":"indicator(\"x\")\nplot(close)","ticker":"RELIANCE"}'` succeeds with no token.
- Timeout: submit a large generated script (near the 10k-char cap) of chained arithmetic lines; observe the 408 returns at 10 s but CPU stays pinned afterward. Fire ~`os.cpu_count()+4` of them concurrently and watch subsequent `/api/scripts/run` and `/portfolio` calls stall.

**Test idea:** submit a deliberately expensive script; assert the endpoint returns within budget **and** that the process's CPU returns to baseline shortly after (proving the work was actually stopped). This fails today.

**Fix:** Add `Depends(get_current_user)` and rate-limit the route. For hard timeouts, run the interpreter in a `ProcessPoolExecutor` with a real kill on timeout, or add explicit instruction-count/line-count budgets inside `PineEngine.execute`. Anchor the tokenizer regexes to bound backtracking.

---

## #5 — Secrets and CORS defaults unsafe for production

**Severity: Medium-High · Effort: Low · Leverage: Medium**

- **Committed `.env`.** `backend/.env` is tracked in git even though `.gitignore` lists `.env` (it was committed before the ignore rule, so git keeps tracking it). Current values are placeholders, but the file will accumulate real secrets and the JWT `SECRET_KEY` there signs all auth tokens — if a real key ever lands in a commit, every token is forgeable.
- **Fallback secret.** `config.py` defaults `SECRET_KEY` to `"your-secret-key-change-in-production"`. If the env var is unset in prod, tokens are signed with a public constant → trivial admin impersonation. The app should refuse to boot instead of falling back.
- **CORS.** `allow_methods=["*"], allow_headers=["*"]` with `allow_credentials=True` and hardcoded localhost origins. Fine for dev, but the wildcards plus credentials are a footgun once origins become configurable.
- **JWT tokens in `localStorage`** (`frontend/src/hooks/useAuth.js`). Readable by any injected script, so any XSS becomes full account takeover with a 24h-valid token. Prefer an httpOnly cookie, or accept the tradeoff explicitly.

**Reproduction / checks:**

- `git ls-files backend/.env` → returns the path, proving it's tracked.
- Unset `SECRET_KEY`, start the app, mint a token, and forge a second token in a REPL with the known default key + `algorithm="HS256"`; `/auth/me` accepts it.
- Browser console: `localStorage.getItem('nse_arena_token')` returns the bearer token.

**Fix:** `git rm --cached backend/.env`, rotate any real keys, and make `SECRET_KEY` mandatory (raise on startup if missing). Pin CORS methods/headers to what's used. Move the token to an httpOnly, SameSite cookie or document the XSS tradeoff.

---

## Honorable mentions (lower leverage, worth a ticket)

- **WebSocket creates a new `PriceBroadcaster` (new Redis connection) per client** and `close()`s Redis in `finally`; under churn this leaks/thrashes connections. Share one broadcaster via app state.
- **AI agent calls `self.model.generate_content(...)` synchronously** in an `async` method (`ai/agent.py::run_cycle`) — same event-loop-blocking class as #3.
- **`ensure_active_season` in `main.py` and `register` in `auth.py` both create "Season 1"** with a race window at first boot — two near-simultaneous registrations can create duplicate active seasons. Add a unique constraint on `is_active`.
- **`get_db` commits on every request** even for read-only GETs; harmless but noisy and hides intent.

---

## Suggested order of work

0. Fix the `portfolio.py` syntax error (see blocker note at top) — the app doesn't boot without it.
1. Wire `/trades` through `Validator` + add Pydantic bounds (#1) — closes three critical holes in one change.
2. Make the cash debit atomic (#2).
3. Move all yfinance calls off the event loop and onto the Redis cache (#3).
4. Auth + real timeout on `/api/scripts/run` (#4).
5. Secrets/CORS/token hygiene (#5).

Items 1–2 are the ones that make the competition's numbers trustworthy; everything else is availability and hardening.
