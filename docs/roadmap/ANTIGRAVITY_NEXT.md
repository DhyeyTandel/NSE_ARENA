# Antigravity Prompts — What's Still Incomplete (verified 2026-07-15)

Checked the actual code against `CODE_REVIEW.md`, `ANTIGRAVITY_PROMPTS.md`, `ANTIGRAVITY_FOLLOWUP.md`, and `ANTIGRAVITY_PHASE2.md`. Confirmed done: boot-blocking syntax fix, trades routed through `Validator`, yfinance moved off the event loop (async facade + cache), `SECRET_KEY` mandatory, CORS methods/headers pinned, `.env` untracked, `/api/scripts/run` has auth.

Everything below is **verified still open** in the current code — paste one prompt per Antigravity session, in order.

**Paste at the top of every session:**
> StockPaper repo: FastAPI async backend in `backend/`, React 19 + Vite frontend in `frontend/`. Read `CODE_REVIEW.md`, `ANTIGRAVITY_FOLLOWUP.md`, and this file first. Stay in scope. Add pytest tests for backend changes; run `pytest backend/tests/` before declaring done.

---

## 1 — Limit orders still self-fill at the user's price (CRITICAL, live money bug)

`backend/api/routes/trades.py`, the execution_price line still reads:
`execution_price = request.limit_price if request.order_type == "limit" and request.limit_price > 0 else current_price`
This was flagged in `ANTIGRAVITY_FOLLOWUP.md` Gap 1 and is **still unfixed** — a limit buy 9% below market (inside the ±10% circuit-breaker band) fills instantly at that price, an easy repeatable fake-profit exploit that corrupts the leaderboard.

**Prompt:**
> In `backend/api/routes/trades.py::submit_trade`, fix limit-order fill semantics: limit BUY fills at `current_price` if `limit_price >= current_price` (price improvement), else reject with 400 "limit price below market — order would not fill". Limit SELL mirrors this (fill at `current_price` if `limit_price <= current_price`, else reject). Market orders unchanged. Compute fees on the actual execution price. Add tests: `test_limit_buy_below_market_rejected`, `test_limit_buy_above_market_fills_at_market`, `test_limit_sell_above_market_rejected`, plus an assertion that no trade can ever execute at a price different from current market price.

---

## 2 — Row locking is a no-op on SQLite; no dialect-agnostic backstop

`trades.py` uses `.with_for_update()`, which SQLite silently ignores, and the default `DATABASE_URL` in `config.py` (and in pytest) is SQLite — so the concurrency fix from Task 2 is unverified where it actually runs.

**Prompt:**
> Add a dialect-agnostic guarded UPDATE as a backstop in `submit_trade`'s buy/sell paths: `UPDATE portfolio SET cash_balance = cash_balance - :cost WHERE id = :id AND cash_balance >= :cost`, treating `rowcount == 0` as insufficient funds (same pattern for decrementing position quantity on sell). Keep `with_for_update()` for Postgres. In `config.py`, raise at boot if `ENV=production` and the resolved `DATABASE_URL` is SQLite. Add a test that fires 10 concurrent ~99k buys against a 100k balance on SQLite and asserts exactly one succeeds and balance never goes negative.

---

## 3 — `backend/.env` still isn't loaded, and `.env.example` doesn't exist

`config.py` reads only `os.getenv`, no `load_dotenv` anywhere — so editing `backend/.env` locally does nothing. There's also no `.env.example`, so a fresh clone has no record of required vars.

**Prompt:**
> Add `python-dotenv` and call `load_dotenv()` at the top of `backend/config.py` before any `os.getenv` call. Create `backend/.env.example` documenting `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `GEMINI_API_KEY` with placeholder values and comments. Confirm `backend/.env` stays untracked (`git ls-files backend/.env` returns nothing) and update `README.md`'s setup steps to reference `.env.example`.

---

## 4 — WebSocket price stream has zero auth or resource bound

`api/routes/websocket.py` has no token check at all, and (per `CODE_REVIEW.md` honorable mentions) opens a fresh Redis pub/sub subscription per client. Combined, unauthenticated clients can open unbounded sockets and unbounded Redis subscriptions.

**Prompt:**
> Share one `PriceBroadcaster`/Redis subscription across all WebSocket clients via `app.state` (fan out in-process instead of one subscription per socket). Add a connection cap and per-IP limit on `/ws/prices`. Require a valid token on the WS handshake (accept via the first message frame, not a query param, since query params get logged); close with code 4401 if not authenticated within 5s. Test: unauthenticated socket is closed; N+1th connection from one IP is rejected.

---

## 5 — Rate limiting still missing on `/api/scripts/run`, `/auth/login`, `/auth/register`

Auth is present on the script runner now, but no rate limiter exists anywhere in the codebase (confirmed — no `slowapi`, no Redis counter). Login/register are wide open to brute-force and enumeration.

**Prompt:**
> Add Redis-backed rate limiting: `/api/scripts/run` (10/min/user, 429 on exceed), `/auth/login` (5/min/IP), `/auth/register` (3/hour/IP). Use the forwarded client IP if behind a proxy. Add tests hitting the limit and asserting 429. Also review the tokenizer regexes in `scripting/engine.py` for catastrophic backtracking on adversarial input — add a test with a ~10k-char pathological input asserting tokenization completes in under 1s.

---

## 6 — Docker Compose still ships a hardcoded DB password and publishes DB ports to the host

`docker-compose.yml` still has `POSTGRES_PASSWORD: password` and both `5432:5432` and `6379:6379` published — this is the single biggest blocker before any public deploy.

**Prompt:**
> In `docker-compose.yml`: move `POSTGRES_PASSWORD` to `${POSTGRES_PASSWORD:?required}` sourced from an untracked `.env.deploy`; remove the `5432:5432` and `6379:6379` host port mappings (services communicate over the internal compose network only); add `requirepass` to Redis and update `REDIS_URL` accordingly. Add a reverse proxy (Caddy is simplest) in front of the backend for HTTPS; backend should not be directly exposed. Document the required `.env.deploy` vars in README.

---

## 7 — JWT still stored in `localStorage`

`frontend/src/hooks/useAuth.js` still reads/writes the token via `localStorage` — undecided XSS tradeoff flagged twice already (Task 5.4, Gap 6) and never resolved either way.

**Prompt:**
> Either implement the httpOnly-cookie auth flow (backend sets `SameSite=Lax; Secure` cookie on login, `get_current_user` reads it with Bearer-header fallback for API clients/tests, add `/auth/logout` to clear it, add a CSRF mitigation like a required `X-Requested-With` header since all mutating routes are POST/PUT/DELETE), **or** explicitly document in `README.md` that localStorage is a deliberate tradeoff and why. Don't leave it undecided a third time. If implementing cookies, also fix WebSocket auth (item 4) to use the same cookie instead of a query-param token.

---

## 8 — NSE holiday calendar doesn't exist (correctness bug)

`Validator._check_market_hours` only checks weekend + 09:15–15:30 IST — no `market_calendar.py` file exists. Trades currently execute on Diwali, Holi, Republic Day, etc.

**Prompt:**
> Create `backend/engine/market_calendar.py` with a static NSE holiday list for 2026 (verify real dates from nseindia.com — don't invent them), `is_trading_day(date)` and `is_market_open(datetime)`, and wire it into `Validator._check_market_hours`. Keep timezone as `Asia/Kolkata`. Tests: freeze time on a known holiday, a weekend, a normal trading day at 09:14:59 and 09:15:00.

---

## Suggested order

Do 1–2 first (still-live economic bugs, make the leaderboard trustworthy). Then 3–5 (correctness/hardening you'll want before more users hit it). Then 6–7 before any public deploy. 8 whenever — it's a correctness nit, not urgent.

The Phase 2 UI redesign ("Pink Paper" editorial, `ANTIGRAVITY_PHASE2.md` workstream C) and product features (B2–B6 in the same file) haven't been started at all — last commit is still the dark-mode redesign. Those prompts are already written and don't need re-issuing; pull from `ANTIGRAVITY_PHASE2.md` directly when ready for that pass.

## Final verification prompt (run after 1–8)

> Re-run every reproduction in `CODE_REVIEW.md` and `ANTIGRAVITY_FOLLOWUP.md`, plus: limit-buy 9% below market (must reject), concurrent-buy race on SQLite (must hold), `/ws/prices` without a token (must close), unauthenticated `/auth/login` brute-force (must 429), `git ls-files backend/.env` (must be empty), and `docker-compose.yml` grep for the literal string `password` (must be gone). Report any repro that still succeeds as a failure — do not rationalize it.
