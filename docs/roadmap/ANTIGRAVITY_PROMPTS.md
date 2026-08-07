# Antigravity Implementation Prompts — StockPaper Production Fixes

Run these **in order**, one prompt per Antigravity session/task. Each is self-contained. After each task, run the verification step before moving on. Source of truth for findings: `CODE_REVIEW.md`.

**Global instruction to paste at the top of every session:**

> You are working in the StockPaper repo (FastAPI async backend in `backend/`, React/Vite frontend in `frontend/`). Read `CODE_REVIEW.md` first. Do not refactor beyond the task scope. Every change must come with pytest tests in `backend/tests/`. Run the full test suite (`pytest backend/tests/`) before declaring done. Do not touch `.env` values other than as instructed.

---

## Task 0 — Fix the boot-blocking syntax error

**Prompt:**

> `backend/api/routes/portfolio.py` line 46 contains `for pos in positions:5` — a stray `5` making the file unparseable, so the server can't start. Remove the stray character, then verify with `python3 -c "import ast; ast.parse(open('backend/api/routes/portfolio.py').read())"` and confirm `uvicorn main:app` boots. Do nothing else in this task.

**Acceptance:** app boots; ast.parse passes.

---

## Task 1 — Route `/trades` through the existing Validator (closes 3 critical holes)

**Prompt:**

> In `backend/api/routes/trades.py::submit_trade`, the endpoint reimplements a naive buy/sell path and bypasses `engine/validator.py`, `engine/models.py` (Order), and the circuit breaker entirely. Fix:
>
> 1. Construct an `Order` from the request and call `Validator.validate(order, balance, holdings, previous_close, market_price)` **before** any portfolio mutation. Map each validator error to an appropriate 4xx with a clear detail message (insufficient funds → 400/402, market closed → 400, circuit breaker → 400, invalid quantity → 422).
> 2. Defense in depth on the Pydantic `TradeRequest`: `quantity: conint(gt=0)`, `limit_price: Optional[confloat(gt=0)]`, `side: Literal["buy","sell"]`, `order_type: Literal["market","limit"]`, and normalize/validate `ticker` (uppercase, non-empty, alphanumeric + `.` `-`, max length ~20).
> 3. Limit orders must never execute at the user's price without a market reference: fetch current price, run the ±10% circuit-breaker check from the validator against `previous_close`, and reject limit prices outside the band. Decide and document fill semantics: a limit buy above market fills at market (price improvement), a limit buy below market is rejected or queued — do NOT fill at the stale limit price.
> 4. Sell path: validate the user holds ≥ quantity of confirmed (not pending) shares; reject short sells.
>
> **Edge cases to handle and test:**
> - quantity = 0, negative, non-integer (e.g. `1.5`, `"10"` as string), and huge values (overflow / cost > any balance)
> - limit_price = 0, negative, None on a limit order, present on a market order (ignore or reject — pick one, document it)
> - ticker: lowercase input, unknown ticker (yfinance returns None/NaN price → 502/404, never execute at price 0), empty string, injection-ish strings
> - market price fetch fails mid-request → trade must be rejected, portfolio untouched
> - selling exactly the full holding, selling 1 more than held, selling with a pending sell already open on the same shares
> - trade at exactly the ±10% circuit-breaker boundary (define inclusive/exclusive and test both sides)
> - market hours: exactly 09:15:00 and 15:30:00 IST, weekends, and confirm the check uses IST (`Asia/Kolkata`), not server-local time
>
> **Tests to add (these should fail on the current code, pass after):** `test_negative_quantity_rejected`, `test_zero_quantity_rejected`, `test_limit_far_below_market_rejected`, `test_trade_rejected_outside_market_hours`, `test_unknown_ticker_rejected`, `test_oversell_rejected`, `test_price_fetch_failure_no_mutation`.

**Acceptance:** all new tests pass; the reproduction snippets in CODE_REVIEW.md §1 no longer mint cash or fill at 0.01.

---

## Task 2 — Atomic cash debit / holdings credit (fix TOCTOU race)

**Prompt:**

> The buy path in `backend/api/routes/trades.py` does read-check-write on `portfolio.cash_balance` with no locking (CODE_REVIEW.md §2), so concurrent requests overdraw the account, and the sell path can double-sell one position. Fix:
>
> 1. Make the debit conditional and atomic: `UPDATE portfolio SET cash_balance = cash_balance - :cost WHERE id = :id AND cash_balance >= :cost`; treat `rowcount == 0` as insufficient funds. On Postgres you may instead use `SELECT ... FOR UPDATE` inside the transaction — but the guarded UPDATE works on both SQLite and Postgres, so prefer it.
> 2. Same pattern for sells: guarded UPDATE on the position row (`quantity >= :qty`), delete the row only when quantity reaches exactly 0.
> 3. The whole trade (balance change + position change + trade record) must be one transaction — all or nothing. Audit `get_db` in `database.py`: per-request autocommit must not commit a half-applied trade.
> 4. Backstops: DB `CHECK (cash_balance >= 0)` and `CHECK (quantity > 0)` constraints (note SQLite ALTER TABLE limitations — if migrations are messy, enforce for new schema and document).
>
> **Edge cases:**
> - N concurrent buys that individually fit but collectively don't → exactly the affordable subset succeeds, balance never negative
> - concurrent buy + sell on the same portfolio; concurrent sells of the same position
> - request that fails after the debit (e.g. position insert raises) → transaction rolls back, balance restored
> - float precision: fees use `round(..., 2)`; make sure balance comparisons don't fail on ε differences (consider storing money as Decimal/integer paise — if too invasive, document and quantize consistently)
>
> **Test:** async integration test firing 10 concurrent buys (~99k each on a 100k balance) via `httpx.AsyncClient` + `asyncio.gather`; assert exactly one succeeds and final balance ≥ 0. Also test concurrent double-sell.

**Acceptance:** concurrency test green under repeated runs (`pytest -x --count=5` if pytest-repeat available, else loop it).

---

## Task 3 — Get yfinance off the event loop, serve from cache

**Prompt:**

> `MarketDataFetcher.get_price` (`backend/market_data/fetcher.py`) does a blocking yfinance HTTP call and is invoked directly inside async handlers: `trades.py::submit_trade`, `portfolio.py::get_portfolio` (once per position in a loop!), `main.py::get_price`, and `broadcaster._poll_loop`. One slow call freezes the whole server (CODE_REVIEW.md §3). Fix:
>
> 1. Add an async facade on the fetcher: check the Redis cache the broadcaster already maintains first; on miss, `await asyncio.to_thread(...)` the blocking fetch and populate the cache with a short TTL (e.g. 5–15 s during market hours).
> 2. Replace every direct blocking call in async context with the facade. Grep for `yf.Ticker`, `.info`, and direct `fetcher.get_price` calls to make sure none remain on the loop — including `ai/agent.py` and the broadcaster.
> 3. Portfolio pricing: replace the N-calls loop with one batched fetch (`yf.download(list_of_tickers)` in a thread) or N cache reads.
> 4. Add a timeout (e.g. 5 s) around the threaded fetch; on timeout/failure return the last cached price with a `stale: true` flag, or fail the request cleanly — never hang.
>
> **Edge cases:**
> - Redis down → degrade to threaded direct fetch, don't crash; log once, not per-request
> - cache hit with very stale data (Redis TTL expired vs. broadcaster stopped) — decide max acceptable staleness for *trades* specifically (executing on stale price is a correctness issue, not just latency); consider rejecting trades if price is older than X seconds
> - yfinance returns None/NaN/0 → treat as fetch failure, never trade at 0
> - batched download with one bad ticker among many → others still resolve
>
> **Test:** monkeypatch the fetch to sleep 3 s, fire 5 concurrent `/portfolio` requests, assert total elapsed ≈ 3–4 s not 15 s. Test the trade-on-stale-price rejection.

**Acceptance:** parallel-latency test passes; no bare yfinance call reachable from an async handler.

---

## Task 4 — Lock down `/api/scripts/run` (auth + real timeout)

**Prompt:**

> `backend/api/routes/scripts.py::run_user_script` has two issues (CODE_REVIEW.md §4): no auth (unlike `/save` and `/mine`), and `asyncio.wait_for(asyncio.to_thread(...), timeout=10)` cannot actually kill the worker thread, so timed-out scripts keep burning CPU and exhaust the shared thread pool. Fix:
>
> 1. Add `Depends(get_current_user)` (same pattern as `/save`), plus a simple per-user rate limit (e.g. 10 runs/min — in-memory or Redis).
> 2. Real cancellation: run `PineEngine.execute` in a `ProcessPoolExecutor` (dedicated, small, e.g. 2 workers) and on timeout kill the worker process. **Alternatively** (simpler, no process management): add an instruction/step budget inside `PineEngine.execute` — a counter checked every N operations that raises `ScriptBudgetExceeded`. Prefer the budget approach unless the engine holds unpicklable state.
> 3. Anchor/bound the tokenizer regexes in `scripting/engine.py` to prevent catastrophic backtracking on adversarial input.
> 4. Keep the existing 10 s outer timeout as a backstop.
>
> **Edge cases:**
> - script at exactly the 10k-char cap; deeply nested expressions (recursion limit → clean 400, not a 500 stack-overflow leak)
> - if using ProcessPoolExecutor: pool worker crash/OOM → pool self-heals, endpoint returns 500 once, next request works; app shutdown cleans up the pool (lifespan handler)
> - if using instruction budget: budget must also cover the market-data fetch time, and loops in user scripts
> - concurrent runs at the rate-limit boundary; rate-limit state across multiple uvicorn workers (document that in-memory limits are per-worker)
> - unauthenticated request → 401 (test this explicitly)
>
> **Test:** unauthenticated POST → 401; expensive script returns within budget AND CPU returns to baseline after (assert via a follow-up cheap request completing fast); rate limit returns 429.

**Acceptance:** curl without token gets 401; hostile script can't wedge the thread pool.

---

## Task 5 — Secrets, CORS, token storage hygiene

**Prompt:**

> Per CODE_REVIEW.md §5, apply these hardening changes:
>
> 1. **Untrack `.env`:** `git rm --cached backend/.env` (file stays on disk, leaves the index). Add `backend/.env.example` with placeholder keys documenting every required var. Note in the PR description that any real keys ever committed must be rotated — git history retains them.
> 2. **Mandatory SECRET_KEY:** in `backend/config.py`, remove the `"your-secret-key-change-in-production"` fallback. On startup, if `SECRET_KEY` is missing or equals the old default, raise `RuntimeError` with a clear message. Allow an explicit `ENV=dev` escape hatch that generates a random per-boot key (invalidates tokens on restart — acceptable in dev).
> 3. **CORS:** pin `allow_methods=["GET","POST","PUT","DELETE","OPTIONS"]` and `allow_headers=["Authorization","Content-Type"]`; keep origins from config, and assert at startup that `allow_credentials=True` is never combined with a wildcard origin.
> 4. **JWT storage:** move the token from `localStorage` (`frontend/src/hooks/useAuth.js`) to an httpOnly, `SameSite=Lax`, `Secure` cookie set by the backend on login. Update `get_current_user` to read the cookie (keep Bearer-header support for tests/API clients). Add a `/auth/logout` that clears the cookie.
>
> **Edge cases:**
> - cookie auth introduces CSRF exposure: with `SameSite=Lax`, GETs are safe but cross-site POSTs from top-level navigation aren't fully — since all mutating routes are POST/PUT/DELETE with JSON bodies, add a simple CSRF mitigation (require a custom header like `X-Requested-With`, or double-submit token) and test it
> - WebSocket auth: `websocket.py` currently gets the token how? Cookies are sent on WS handshake for same-origin — verify and test; Bearer via query param must not be logged
> - existing logged-in users after deploy: localStorage token still works via Bearer fallback until expiry — document the migration
> - CORS with credentials requires exact origin match, no `*` — test preflight from the Vite dev origin still works
> - startup must fail loudly (non-zero exit) when SECRET_KEY missing in non-dev, and this must be covered by `test_config.py`
>
> **Test:** forge-token test (sign with old default key → 401); startup-fails test; frontend login flow works end-to-end in dev via cookie.

**Acceptance:** `git ls-files backend/.env` returns nothing; forged default-key token rejected; login works from the Vite frontend.

---

## Task 6 — Honorable mentions (one small PR)

**Prompt:**

> Four small fixes from CODE_REVIEW.md "Honorable mentions":
>
> 1. Share one `PriceBroadcaster` (and its Redis connection) via `app.state` created in the lifespan handler; `websocket.py` must stop creating/closing one per client. Edge case: client disconnect mid-broadcast must not close the shared Redis connection; last-client-disconnect should not kill the poll loop if it's meant to feed the cache for REST too.
> 2. `ai/agent.py::run_cycle`: wrap `self.model.generate_content(...)` in `await asyncio.to_thread(...)` with a timeout; on timeout skip the cycle, don't crash the scheduler.
> 3. Duplicate-season race: add a partial unique index / unique constraint so only one row can have `is_active=true`; make `ensure_active_season` and `register`'s season creation idempotent (catch the unique violation and re-fetch). Edge case: two workers booting simultaneously.
> 4. `get_db`: stop committing on read-only requests — commit only when the session is dirty, or move commits into the endpoints that write.
>
> Add regression tests for 1 and 3.

---

## Final verification pass (run after all tasks)

**Prompt:**

> Run the complete backend test suite. Then re-run every reproduction from `CODE_REVIEW.md` (§1 arithmetic simulation, §2 concurrent-buy script, §4 unauthenticated curl, §5 git ls-files / forged token) and confirm each is now blocked. Boot the full stack with `docker-compose up`, register a user via the frontend, place a market buy during simulated market hours (mock the clock if needed), and confirm portfolio + leaderboard update. Report any repro that still succeeds as a failure — do not rationalize it.

---

## Notes for you (Dhyey)

- Do tasks 0→2 first and in order; they're the ones that make competition numbers trustworthy. 3–6 are availability/hardening and can be parallel sessions.
- Review Antigravity's diffs before accepting, especially Task 2 (transactions) and Task 5.4 (auth flow) — agents commonly get cookie+CSRF and rollback semantics subtly wrong.
- Keep each task a separate git commit/branch so a bad change is easy to revert.
- If Antigravity proposes migrating SQLite→Postgres mid-task, defer it — the guarded-UPDATE pattern in Task 2 works on both.
