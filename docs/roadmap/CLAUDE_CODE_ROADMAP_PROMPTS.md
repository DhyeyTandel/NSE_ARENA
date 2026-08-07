# Claude Code Prompts — NSE Arena Roadmap (2026-07-17)

One prompt per session, in order. Items 1–3 make it resume-ready; 4–6 deepen the interview story; 7 is the portfolio showcase.

**Paste at the top of every session:**
> StockPaper repo: FastAPI async backend in `backend/`, React 19 + Vite frontend in `frontend/`. Read `CODE_REVIEW.md`, `ANTIGRAVITY_NEXT.md`, and `ANTIGRAVITY_FOLLOWUP.md` first. Stay in scope. Add pytest tests for backend changes; run `pytest backend/tests/` before declaring done.

---

## 1 — Execute the open fix list (do this first)

**Prompt:**
> Read `ANTIGRAVITY_NEXT.md` and execute items 1 through 8 in the suggested order, one at a time: (1) limit-order fill semantics, (2) dialect-agnostic guarded UPDATE backstop for SQLite, (3) load_dotenv + `.env.example`, (4) WebSocket auth + resource bounds, (5) rate limiting on `/api/scripts/run` and auth routes, (6) Docker Compose secrets + unpublished DB ports, (7) JWT out of localStorage, (8) NSE holiday calendar. After each item, run the full test suite and commit with a message referencing the item number. Finish with the final verification prompt at the bottom of that file. Do not start a new item until the previous one's tests pass.

---

## 2 — Deploy live with a demo account

**Prompt:**
> Prepare NSE Arena for a live deployment: backend (FastAPI + Postgres + Redis) on Railway, frontend on Vercel. Tasks: (a) make `backend/config.py` read all secrets/URLs from env with production-safe defaults and fail loudly on missing `SECRET_KEY`; (b) add a production Dockerfile for the backend (multi-stage, non-root user, uvicorn with `--workers`); (c) add a `railway.json`/deploy config and document exact deploy steps in `DEPLOY.md`; (d) set frontend API/WS base URLs from `VITE_API_URL` env instead of hardcoded localhost; (e) add a seed script `backend/scripts/seed_demo.py` that creates a `demo@nsearena.com` account with an active season, a realistic trade history, and leaderboard entries; (f) add a "Try demo" button on the login screen that signs into the demo account. CORS must allow only the Vercel domain in production. Don't deploy — get everything deploy-ready and give me the click-by-click steps.

---

## 3 — CI with GitHub Actions

**Prompt:**
> Add `.github/workflows/ci.yml`: on push and PR, (1) set up Python, install backend deps, run `pytest backend/tests/` with a Postgres service container so the row-locking tests run against the real dialect; (2) build the frontend (`npm ci && npm run build`); (3) build both Docker images to verify Dockerfiles. Cache pip and npm. Add a status badge to the top of `README.md`. Keep total runtime under ~5 minutes.

---

## 4 — Real resting order book (matching engine upgrade)

**Prompt:**
> Upgrade limit orders from instant fill-or-reject to a real resting order book. Design: (a) new `orders` table (id, user, symbol, side, type, limit_price, quantity, status: open/filled/cancelled/expired, created_at, filled_at, execution_price); (b) `POST /api/orders` validates via `engine/validator.py`, **reserves** cash (buys) or shares (sells) atomically at placement, and stores the order as `open` when the limit price doesn't cross; (c) a background asyncio worker subscribed to the Redis price stream that, on each tick, fills crossed open orders at the market price (price improvement allowed), settles atomically with the same guarded-UPDATE pattern as `submit_trade`, and publishes a fill event over the user's WebSocket; (d) `GET /api/orders` + `DELETE /api/orders/{id}` (cancel releases the reservation); (e) orders expire at market close (day orders). Reuse/extend `engine/matching.py` rather than duplicating logic. Tests: crossed-at-placement fills immediately, resting order fills only when price crosses, cancel releases reserved cash, concurrent fills can't double-spend, expiry at close. Frontend: an "Open orders" panel on the dashboard with cancel buttons and live fill updates.

---

## 5 — Load test + performance numbers

**Prompt:**
> Add a `loadtest/` directory using k6: (a) `trades.js` — ramp authenticated users submitting market orders, report p50/p95/p99 latency and error rate at increasing RPS; (b) `ws.js` — open N concurrent WebSocket price-stream clients and measure connect success and message latency at N = 100/500/1000; (c) a `README.md` in that folder explaining how to run against local Docker Compose and interpret results. Then run both against the local stack, and write the headline numbers into a `PERFORMANCE.md` (setup, methodology, results table, bottlenecks found). If an obvious cheap bottleneck shows up (e.g., missing DB index, per-request yfinance call), fix it and re-run.

---

## 6 — AI agent trade journal (visible reasoning)

**Prompt:**
> Make the Gemini agents' reasoning visible. Backend: when an agent decides a trade, persist a journal entry (agent, symbol, action, quantity, price, timestamp, and the model's reasoning summary — request a 2–3 sentence rationale in the agent's prompt and store it). Expose `GET /api/agents/{id}/journal` (paginated) and include the latest entry in the leaderboard payload for agent rows. Frontend: an "Agent journal" drawer on the leaderboard — click an agent to see its trade log with reasoning, newest first, live-updating via WebSocket. Style with the existing `frontend/src/tokens.css` design system: white cards with 1px hairline borders and 4px radius on the cream canvas, JetBrains Mono for tickers/prices/timestamps, Sofia Sans body, serif card title, ▲/▼ glyphs for buy/sell in success/error colors (no emoji), staggered fade-up entrance on entries, `prefers-reduced-motion` respected.

---

## 7 — Portfolio case study page (portfolio-react repo)

**Prompt:**
> In my portfolio-react repo (Vite + React + TS), add a case study page for NSE Arena at `/work/nse-arena`, following my design system exactly (`src/tokens.css` + existing components — reuse them, don't restyle). Structure, top to bottom: (1) hero — mono eyebrow with 7px orange dot "• CASE STUDY — NSE ARENA", Newsreader display headline at regular weight with one italic orange word (e.g., "A paper-trading arena with *real* market mechanics"), muted one-line summary; (2) spec rows (▸ glyph, mono labels): stack (FastAPI · React 19 · PostgreSQL · Redis · Docker), role, timeline, links (live demo ↗, GitHub ↗); (3) metrics band — JetBrains Mono numbers from `PERFORMANCE.md` (concurrent WS clients, p95 latency, test count), numbers do the bragging; (4) three narrative sections with the standard stack (eyebrow → serif h2 → body at Sofia Sans 450): "The problem", "The matching engine" (limit-order exploit found → resting order book built), "The AI agents"; (5) media frames at 24px radius for screenshots/demo GIF; (6) exactly one warm-black `--ink-surface` band — a featured "What I'd build next" card; (7) footer CTA pill button "View the code →". Orange is the only bright on the page. Staggered fade-up entrances with the spring easing, hover lift on cards (`translateY(-2px)` + `--shadow-lift`), sentence case throughout, first-person voice, no emoji. Add the project card to the work grid on the homepage linking to this page.

---

---

# Part 2 — Market-logic fixes (integrity bugs, treat like the fix list)

## 8 — Delayed-feed exploit (CRITICAL for leaderboard integrity)

**Prompt:**
> Our yfinance NSE data is ~15 minutes delayed, so anyone watching a real-time feed can buy stale spikes for guaranteed fake profit. Mitigate: (a) execute market orders at the **next** fetched tick after order receipt, never the tick the user saw when clicking (queue the order, fill on the following price update from the fetcher); (b) add configurable random slippage of ±0.05–0.15% on all market fills, applied symmetrically; (c) surface "prices delayed ~15 min" in the UI near the ticker. Document the threat and mitigation in `CODE_REVIEW.md`. Tests: order placed at tick T fills at tick T+1's price, slippage stays within bounds, sell and buy slippage are symmetric over many samples.

## 9 — Restrict the tradeable universe

**Prompt:**
> Illiquid small-caps are free leaderboard money. Add a curated symbol universe: a `symbols` table (or JSON config) seeded with NIFTY 500 constituents, validated on every trade/order/script run — reject anything outside it with 400 "symbol not in tradeable universe". Make the universe swappable via config. Frontend: symbol search/autocomplete only offers universe symbols. Test: trade in an off-universe symbol is rejected on every entry point (trades, orders, agents, scripts).

## 10 — Risk-adjusted scoring + anti-gaming

**Prompt:**
> Read `scoring/` first. Make risk-adjusted metrics first-class: compute per-user Sharpe, Sortino, and max drawdown from daily portfolio snapshots (add a daily snapshot job if one doesn't exist). Leaderboard ranking = existing multi-factor score but with risk-adjusted return weighted above raw return. Anti-gaming rules: minimum 10 closed trades and minimum 5 distinct trading days to be ranked; unranked users shown greyed at the bottom. Show Sharpe and max drawdown as columns on the leaderboard UI (mono font). Tests: a one-lucky-trade account ranks below a steady account with equal returns; sub-minimum accounts are unranked.

## 11 — Corporate actions (splits at minimum)

**Prompt:**
> A 1:5 split currently makes a holding show −80% overnight. Add a daily corporate-actions job: detect splits via yfinance (`splits` history) for all held symbols, and on detection atomically adjust position quantity and average price (qty × ratio, avg ÷ ratio) with an audit row in a `corporate_actions` table. Also credit cash dividends to portfolio balance when detected. Tests: split adjustment preserves position market value exactly; dividend credits cash and writes an audit row; job is idempotent (running twice doesn't double-apply).

## 12 — Realistic Indian cost engine

**Prompt:**
> Read `engine/` fee code and `test_fee_engine.py` first. Replace the flat fee model with real Indian equity delivery costs: brokerage (₹0 delivery, Zerodha-style), STT 0.1% on both sides, exchange txn charge 0.00297% (NSE), SEBI charge 0.0001%, stamp duty 0.015% buy-side only, GST 18% on (brokerage + exchange + SEBI). Return an itemized breakdown from the fee engine, store it per trade, and show it in the trade confirmation UI. Keep rates in config, not code. Tests: known worked example matches to the paisa; sell-side has no stamp duty; breakdown sums to total charged.

## 13 — Season lifecycle automation

**Prompt:**
> Seasons must roll over without manual DB edits. Add a scheduler job that at season end: (a) marks all open positions to market and computes final scores, (b) freezes the final leaderboard into a `season_results` table, (c) awards badges (top 3, best Sharpe, most consistent) stored on user profiles, (d) archives the season and auto-creates the next one with fresh ₹1,00,000 balances, (e) expires all open orders. Frontend: past-seasons page with frozen leaderboards and badges on profiles. Tests: rollover is idempotent, mid-rollover trade attempts are rejected, balances reset only after results freeze.

## 14 — Agent strategy cohorts

**Prompt:**
> Give each Gemini agent an explicit strategy persona (momentum, mean-reversion, value/quality — strategy name + rules in its prompt, stored on the agent row). Track per-strategy cohort stats across seasons: return, Sharpe, win rate vs the human median. Expose `GET /api/agents/stats` and add a "Humans vs agents" panel on the leaderboard (e.g., "humans beat the momentum agent in 62% of seasons"). Tests: cohort aggregation math on fixture data.

---

# Part 3 — Core concept additions (the platform story)

## 15 — Backtester for PineScript-lite (do before 16)

**Prompt:**
> Read `scripting/` first. Add a backtesting engine: `POST /api/scripts/{id}/backtest` with {symbol, timeframe, start, end, initial_capital}. Interpret the script's buy/sell signals against historical OHLCV (fetch + cache in Redis), simulate fills at next-bar open with the standard fee engine, and return an equity curve, total return, max drawdown, Sharpe, win rate, and trade list. Enforce the same sandbox/timeout limits as `/api/scripts/run`, rate-limit it, and cap the date range (e.g., 2 years daily / 60 days intraday). Frontend: "Backtest" tab in the script editor — equity curve on lightweight-charts, stats row in mono, trade list table. Tests: deterministic fixture script on fixture data produces exact known stats; look-ahead bias check (signal at bar N can't fill at bar N's close).

## 16 — User trading bots (scripts trade live)

**Prompt:**
> Read `scripting/` and the backtester (task 15) first. Let users promote a script to a live bot: `POST /api/bots` {script_id, symbol, max_position_pct}, max 2 active bots per user. A background worker evaluates each active bot on new price ticks (same pattern as the AI agents), places paper trades through the standard validated trade path, and logs each action with the triggering signal to a bot journal. Bots trade the user's own portfolio and respect all limits (universe, market hours, funds). Kill switch: auto-disable a bot after 3 consecutive rejected orders or on runtime error, notify via WebSocket. UI: bots panel with enable/disable, journal, and PnL attribution (bot trades vs manual trades). Tests: bot trades go through Validator; kill switch triggers; per-user bot cap enforced.

## 17 — Replay mode (market time-travel)

**Prompt:**
> NSE is closed when most people will demo this. Add replay mode: `POST /api/replay/start` {date, speed: 1–60x} streams that day's historical intraday bars through the **existing** Redis pub/sub price pipeline on a per-user channel, so charts, open orders, bots, and agents all behave live. Scope: replay sessions are per-user sandboxes using a cloned throwaway portfolio (real season portfolio untouched), auto-expire after 2h, one active replay per user. UI: a "Replay" toggle with date picker and speed control, and a persistent banner "REPLAY — {date} @ {speed}x" while active. Tests: replay trades never touch the season portfolio; stream ordering is chronological; expiry cleans up.

## 18 — Intraday margin + short selling

**Prompt:**
> Add MIS-style intraday trading: order flag `product: CNC|MIS`. MIS gives 5x leverage (margin blocked = value/5) and allows short selling (sell without holdings, margin blocked on the short). Track margin per position; on adverse moves, when portfolio equity < 20% of blocked margin, auto-liquidate at market (margin call, journaled + WebSocket notify). All MIS positions force-square-off at 15:15 IST via scheduler. Shorts: PnL = (sell − buy) × qty, buy-to-cover closes. Update scoring to include leverage in risk metrics. Tests: margin blocking math, short PnL both directions, margin-call trigger, square-off closes everything and releases margin, CNC unaffected.

## 19 — Behavioral analytics report

**Prompt:**
> From existing trade history, build a per-user "Trading behavior" report: win rate, profit factor, avg hold time winners vs losers (disposition effect flag when losers held ≥2x longer), max consecutive losses with time-between-trades after losses (revenge-trading flag), sector concentration, best/worst weekday. Endpoint `GET /api/analytics/behavior`, computed on demand with a short cache. UI: analytics page with the stats in mono, one-line plain-language insights per flag ("You hold losers 2.7x longer than winners"), and an end-of-season summary version. Tests: each metric on fixture trade histories, flags fire at the documented thresholds.

## 20 — (Later, optional) Copy trading & options

Copy trading (follow/mirror traders — a fan-out problem) and NIFTY options (pricing, expiry, settlement) are real projects each. Park them; revisit only if the platform gets actual users.

---

## Suggested order

**Resume-ready:** 1 → 3 → 2 (CI before deploy so the badge is green on day one).
**Integrity (before anyone competes):** 8 → 9 → 10, then 11 → 12 → 13 → 14.
**Depth:** 4 → 15 → 16 → 17, then 5 (load test after the heavy features), 6, 18 → 19.
**Showcase:** 7 last, once there are real numbers and screenshots — and replay mode (17) means the demo works at any hour.
