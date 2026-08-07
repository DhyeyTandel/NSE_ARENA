# Antigravity Phase 2 — Deployment Security · Product Logic · UI Redesign

Three workstreams. A (security) before you deploy publicly; B (logic) makes the game trustworthy and fun; C (UI) is the pink-paper editorial redesign. Run prompts in order within each workstream; A and C can run in parallel sessions.

**Paste at the top of every session:**

> StockPaper repo: FastAPI async backend in `backend/`, React 19 + Vite frontend in `frontend/` (plain CSS with tokens in `frontend/src/tokens.css`, charts via `lightweight-charts` v5). Read `CODE_REVIEW.md` and `ANTIGRAVITY_FOLLOWUP.md` for prior context. Stay in scope, add tests for backend changes, run `pytest backend/tests/` and `npm test` before declaring done.

---

# Workstream A — Security before public deployment

What's already handled: SECRET_KEY mandatory, CORS pinned, `.env` untracked, script-runner auth + CPU deadline, trade validation. These are the remaining deploy-blockers.

## A1 — Infrastructure & docker-compose hardening

**Prompt:**

> Harden `docker-compose.yml` and deployment config for public exposure:
> 1. Postgres credentials are `user:password` — move to env-file-driven secrets (`POSTGRES_PASSWORD` from an untracked `.env.deploy`), and do NOT publish the Postgres or Redis ports to the host (`ports:` → remove; services talk over the compose network only). Redis currently has no password — add `requirepass` via config and update `REDIS_URL`.
> 2. Add a reverse proxy service (Caddy is simplest — automatic HTTPS) in front of the backend and the built frontend. Backend must not be directly exposed. Run uvicorn with `--proxy-headers --forwarded-allow-ips` so client IPs are correct for rate limiting.
> 3. Security headers at the proxy: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a starter `Content-Security-Policy` (allow self + Google Fonts + the yfinance-free frontend; NO `unsafe-eval` — verify Monaco editor works, it may need a worker-src carve-out).
> 4. Production FastAPI: ensure no debug/reload, and add a global exception handler that returns a generic 500 without stack traces (log the trace server-side instead).
> 5. Container hygiene: non-root user in the backend Dockerfile, `restart: unless-stopped`, healthchecks for postgres/redis/backend.
>
> Edge cases: CORS origins must be updated to the real deployed domain (config-driven, not hardcoded localhost); WebSocket upgrade must pass through the proxy (`/ws` route); Vite build-time API URL must be configurable (`VITE_API_URL`), not hardcoded localhost.

## A2 — Auth hardening (brute force, tokens, WebSocket)

**Prompt:**

> 1. Rate-limit `/auth/login` and `/auth/register` (e.g. 5/min/IP via Redis) with exponential backoff on repeated failures for the same username; return 429. Verify password hashing uses bcrypt/argon2 with per-password salt (check `auth.py` — if it's anything weaker, migrate with rehash-on-login).
> 2. Enforce a minimal password policy (length ≥ 8; check against a small common-password list). Normalize emails; add basic email format validation.
> 3. JWT: check current expiry; set access-token expiry to ≤ 24 h. Since there's no revocation, add a `token_version` column on User — bump it to invalidate all tokens (used on password change); `get_current_user` compares versions.
> 4. WebSocket auth: audit `websocket.py` — if the token travels as a query param, it lands in proxy logs. Accept it via the first WS message ("auth frame") instead, or via cookie; close the socket with 4401 if not authenticated within 5 s.
> 5. Audit EVERY router for missing auth: `seasons.py`, `ai.py`, `leaderboard.py` — list each endpoint and its auth status in the PR description. Any endpoint that mutates state must require auth; anything admin-ish (creating seasons, starting AI agents) must check an `is_admin` flag, not just login.
>
> Edge cases: rate limiter behind proxy must use the forwarded client IP; multiple uvicorn workers share limits only if the limiter is Redis-backed; clock skew on JWT `exp` (small leeway); registration race on duplicate email (unique constraint → clean 409, not 500).

## A3 — Abuse & resource protection

**Prompt:**

> 1. Global rate limit (e.g. 60 req/min/user, stricter on `/trades` e.g. 10/min) — Redis-backed, applies to authenticated ID when present, IP otherwise.
> 2. Idempotency on trades: accept an optional `Idempotency-Key` header, store it with the trade, and return the original result on replay — protects against double-click/network-retry double orders. Frontend: send a UUID per order submission and disable the button while in flight.
> 3. Ticker input is passed into yfinance URL construction — restrict to `^[A-Z0-9.&-]{1,20}$` after uppercasing, and maintain an allowlist (NSE symbol list, refreshed weekly or shipped as a static JSON) so users can't make the server fetch arbitrary symbols/garbage.
> 4. AI agent cost control: hard daily cap on Gemini calls (counter in Redis); agent pauses with a logged warning when hit. Never expose GEMINI_API_KEY or raw model errors to clients.
> 5. Logging hygiene: grep for any logging of tokens, passwords, or Authorization headers; scrub. Add request-ID structured logging.
> 6. Run `pip-audit` on backend deps and `npm audit` on frontend; fix criticals.
>
> Edge cases: idempotency key collisions across users (scope keys per user); ticker allowlist must include indices if the UI supports them; audit-fix must not bump breaking major versions blindly.

## A4 — Data safety

**Prompt:**

> Add a nightly `pg_dump` backup service (compose sidecar or cron) writing to a mounted volume, keeping 7 days. Document restore steps in README. Add a startup migration story: we're on `create_all` — introduce Alembic now, generate a baseline migration matching current models, so future schema changes (like the CheckConstraint) apply to existing databases instead of requiring recreation.

---

# Workstream B — Logic & product improvements

Ranked by how much each improves trust in the competition or user retention.

## B1 — NSE holiday calendar (correctness bug, do first)

**Prompt:**

> `Validator._check_market_hours` only checks weekends + 09:15–15:30 IST. NSE has ~15 trading holidays/year (Diwali, Holi, Republic Day...) plus the special Muhurat trading session. Add `backend/engine/market_calendar.py` with a static holiday list for 2026 (source: NSE published calendar — verify dates from nseindia.com, don't invent them), a `is_trading_day(date)` / `is_market_open(datetime)` API, and wire it into the Validator. Structure it so next year is a data update, not a code change. Edge cases: half-days/special sessions flagged separately; timezone must remain `Asia/Kolkata`; tests freeze time on a holiday, a weekend, a normal day at 09:14:59 and 09:15:00.

## B2 — Risk-adjusted leaderboard (anti-lottery)

**Prompt:**

> Raw P&L leaderboards reward whoever YOLOs hardest — one lucky all-in beats a skilled trader. Extend `scoring/trader_score.py` and the leaderboard to rank on a composite: total return, max drawdown, Sharpe-style consistency (std-dev of daily returns), and a minimum-activity gate (e.g. ≥ 10 trades and ≥ 5 active days to be ranked). Show both "Return %" and "Trader Score" columns; rank by score. Edge cases: brand-new users (no history → unranked, not rank #1 with 0.0 std-dev); division by zero on zero-variance returns; users who never trade shouldn't clutter ranks; recompute cost — cache daily snapshots per portfolio rather than recomputing history per leaderboard view.

## B3 — Anti-gaming: multi-accounting & reset abuse

**Prompt:**

> The prize/leaderboard is only meaningful if it's hard to game. Add: (1) one portfolio per user per season, enforced by unique constraint; (2) no self-service portfolio reset mid-season; (3) a simple collusion heuristic flag — accounts created from the same IP within a short window that trade opposite sides of the same illiquid ticker near-simultaneously get flagged for review (store flags, surface in an admin view, take no automated action); (4) email verification on registration (token link; unverified accounts can browse but not trade). Edge cases: shared campus/hostel IPs are legitimate — flag, never auto-ban; email send failures must not block registration flow (queue + retry); verification link expiry.

## B4 — Execution realism: slippage + resting limit orders

**Prompt:**

> Two upgrades to make paper P&L believable:
> 1. **Slippage on market orders**: fill at `current_price × (1 ± slippage)` where slippage grows with order value (e.g. 0.05% base + 0.05% per ₹5 lakh notional, capped 0.5%). Buy pays up, sell receives less. Document the model in the UI ("estimated impact").
> 2. **Resting limit orders**: instead of rejecting non-marketable limits (current behavior after the Gap-1 fix), persist them as `open` orders; a background task (piggyback on the broadcaster poll) checks cached prices and fills orders whose limit is crossed, atomically via the same locked-transaction path as live trades. Cash for open buy orders must be *reserved* (deduct into a `reserved_cash` column) so users can't place 10 orders against the same rupees. Add cancel-order endpoint + UI.
> Edge cases: order fills while user is cancelling (first committed transaction wins — test it); expiry at market close (day orders); reservation released on cancel/expiry/partial rejection; broadcaster restart must not drop open orders (they live in the DB, not memory); a limit order placed outside market hours queues for the open.

## B5 — Engagement layer

**Prompt:**

> Pick from these, in order of value: (1) **Trade journal** — optional "why" note on each trade + a post-trade review view showing entry vs. subsequent price path; the differentiator for a learning-oriented product. (2) **Price alerts** — user sets a level, broadcaster checks, WebSocket/notification fires. (3) **Season badges** — top-10 finisher, best drawdown discipline, most consistent — stored on profile, rendered in the new UI. (4) **Strategy sharing** — publish a PineScript to a public gallery with fork counts. Skip social feeds and chat; moderation cost isn't worth it.

## B6 — Data source resilience (pre-deploy reality check)

**Prompt:**

> yfinance is unofficial, rate-limited, and breaks without notice — risky as the single price source for a live product. Mitigate: (1) centralize ALL price access through the broadcaster/cache module (one choke point, already mostly true); (2) add exponential backoff + jitter and a global concurrency semaphore on yfinance calls; (3) on repeated failures serve last-known price with a visible "delayed data" banner (never silently stale for trading — reject trades if data older than the Gap-4 threshold); (4) define a `PriceSource` interface so a paid/official API (or NSE bhavcopy EOD files as a fallback layer) can be slotted in without touching business logic. Document the swap procedure.

---

# Workstream C — UI redesign: "Pink Paper" editorial (light, print-inspired)

**Concept:** The app is a living financial newspaper — inspired by the salmon-pink paper of Indian business dailies. Warm pink-paper ground, ink typography, hairline rules instead of shadows and glass, trades rendered as contract-note tickets with rubber stamps, the AI agent as a named market columnist, the leaderboard as a league table on the sports page. Nobody else's trading app looks like this, and it's culturally native to the NSE.

**Kill list (the current "AI look"):** dark `#08090a` ground, gold glow accents, glassmorphism/backdrop-blur, rounded-2xl cards with soft shadows, uppercase micro-labels everywhere, Inter-for-everything.

## C1 — New design tokens (foundation, do first)

**Prompt:**

> Rewrite `frontend/src/tokens.css` completely with this system. Keep every existing CSS-variable NAME that components reference where practical (map old name → new value) so screens don't break before their restyle pass; add new tokens alongside.
>
> ```css
> :root {
>   /* Paper grounds */
>   --paper:      #F6E3D3;  /* app background — salmon pink-paper */
>   --paper-deep: #F0D6C2;  /* section bands, table header rows */
>   --paper-lift: #FBF0E6;  /* cards/panels — lighter sheet laid on top */
>   --paper-edge: #E4C4AC;  /* dividers between sheets */
>
>   /* Ink */
>   --ink:      #231A12;  /* primary text — warm near-black */
>   --ink-soft: #5C4F42;  /* secondary text */
>   --ink-faint:#94836F;  /* tertiary, captions */
>   --rule:      rgba(35,26,18,0.22);  /* hairline rules */
>   --rule-bold: rgba(35,26,18,0.65);  /* double-rule headers */
>
>   /* Print accents */
>   --stamp:   #B4372E;  /* oxblood red — stamps, alerts, sell */
>   --up:      #1E6B45;  /* printed green — gains, buy */
>   --dn:      #B4372E;  /* shares stamp red */
>   --byline:  #29527A;  /* printed blue — AI columnist, links */
>   --hilite:  #E8B84B;  /* marker-yellow — highlights, new entries */
>
>   /* Type */
>   --font-display: "Fraunces", Georgia, serif;        /* masthead, headlines, big numbers */
>   --font-body:    "Newsreader", Georgia, serif;      /* body copy, descriptions */
>   --font-data:    "Spline Sans Mono", "IBM Plex Mono", monospace; /* ALL numerals, tickers, tables */
>
>   /* Structure — print doesn't do soft UI */
>   --r: 2px;                 /* near-square corners everywhere */
>   --shadow: none;           /* depth comes from paper tones + rules, not shadows */
> }
> ```
>
> Rules of the system: (1) hierarchy via type size/weight and hairline rules, never box-shadows; (2) numerals ALWAYS `--font-data` with `font-variant-numeric: tabular-nums`; (3) section headers use the newspaper double-rule (thick over thin border-top); (4) gains/losses always pair color with a +/− sign and ▲/▼ glyph — never color alone (colorblind users); (5) buttons look like print buttons: 1.5px ink border, paper fill, ink text; primary action = solid ink fill with paper text; (6) subtle paper-grain texture on `body` via a tiny tiled SVG noise (opacity ≤ 0.03 — verify no scroll jank).
> Load Fraunces, Newsreader, Spline Sans Mono from Google Fonts with `font-display: swap` and preconnect.

## C2 — Masthead navigation + app shell

**Prompt:**

> Replace `NavBar.jsx` with a newspaper masthead: centered app name set in Fraunces black weight (rename display string to "The Paper Trader" or keep "NSE Arena" — ask the user), flanked left by the date line ("Saturday, 12 July 2026 · Season 2, Day 34") and right by a live market-status chip set like a print tag: "MARKET OPEN 14:02 IST" (green dot) / "MARKET CLOSED". Below the masthead, a full-width double rule, then a nav strip of plain ink links (Dashboard · Markets · Leaderboard · Scripts · Columnist · Profile) with the active one underlined by a 2px ink bar. User cash balance sits far right in mono. Sticky on scroll, collapsing to a single compact rule-line. Mobile: nav strip becomes horizontal scroll, masthead shrinks. Edge cases: very long usernames truncate; market-status chip must reflect the holiday calendar (B1) not just the clock.

## C3 — Dashboard as the front page

**Prompt:**

> Restyle `Dashboard.jsx` as a newspaper front page. Top: a full-width index strip (thin band on `--paper-deep`) showing NIFTY/SENSEX-style summary numbers in mono with ▲/▼. Lead column (left, ~2/3): the price chart as the "lead story" — restyle `lightweight-charts` for print: background `--paper-lift`, ink candles/line (up candles hollow with green stroke, down solid oxblood — classic print candle style), hairline grid, mono axis labels, Fraunces ticker-name headline above with the current price as a huge display numeral. Right column (~1/3): `OrderPanel` and `KpiCard`s stacked. KPI cards become "figures boxes": label in small caps Newsreader italic, value in large mono, hairline box, no shadow. `PositionsTable` beneath as a proper broadsheet table: double-rule header, hairline row separators, alternating none (no zebra — use rules), mono numerals right-aligned, P&L with sign+glyph+color. Edge cases: chart theme options for lightweight-charts v5 differ from v4 — use the v5 API; empty portfolio state gets an editorial touch ("No positions on the books. The market awaits your first order."); loading states as faint "typesetting…" text, not spinners.

## C4 — Order panel as a contract note

**Prompt:**

> Restyle `OrderPanel.jsx` as a broker's contract-note ticket: the panel is a `--paper-lift` sheet with a perforated top edge (CSS dashed/dotted border trick or tiny repeating radial-gradient), "ORDER TICKET" set as a small letterpress header, form fields with ink underlines (no filled input boxes — label above, value on a ruled line, like a paper form). Buy/Sell as two stamp-style toggle buttons (outlined; active = solid green/oxblood with paper text). The fee breakdown renders like a printed bill: right-aligned mono columns with a hairline above the total. On successful execution, show a confirmation overlay on the ticket: a rotated rubber-stamp "EXECUTED" (oxblood, slight rotation, coarse texture) with the trade summary beneath — this is the signature moment of the whole redesign, make it feel physical (subtle stamp-down scale animation, 200ms). On rejection, stamp "REJECTED" with the reason in small print. Edge cases: the in-flight/disabled state while awaiting the API (ties into the idempotency work in A3); keyboard submit; error text must remain selectable/copyable under the stamp.

## C5 — Leaderboard as the sports page

**Prompt:**

> Restyle `Leaderboard.jsx` + `LeaderboardRow.jsx` as a league table: "SEASON STANDINGS" headline in Fraunces with a kicker line above ("Sports pages · Season 2"). Columns: RANK (mono, top-3 get filled ink circles), TRADER (name + a small streak note like "3 green days"), RETURN %, TRADER SCORE (from B2), MOVEMENT (▲2 / ▼1 vs yesterday in green/oxblood). Rank movement needs a `previous_rank` from the API — add it if absent (daily snapshot from B2's cache). The current user's row gets the marker-yellow `--hilite` background like a highlighted newspaper line. Top of page: a small "podium" summary of the top 3 as three figure-boxes. Edge cases: ties in score (stable secondary sort by return, then join date); unranked users (B2 gate) listed below a rule with "— below qualification: 10 trades minimum —"; long usernames; pagination or virtualization beyond ~100 rows.

## C6 — AI feed as the market columnist

**Prompt:**

> Reframe `AIFeed.jsx` + `AIFeedEntry.jsx`: the AI agent becomes a named columnist (e.g. "By THE ALGORITHM, Markets Desk" byline in `--byline` printed blue, small caps). Each entry is a column clipping: Fraunces headline generated from the entry's key action ("Columnist trims RELIANCE position on momentum fade"), byline + timestamp line, body in Newsreader with a drop cap on the first paragraph, and the trade details (if any) as a small contract-note inset. Entries separated by column rules, laid out in 2 columns on wide screens (CSS columns). Edge cases: entries without trades (pure commentary) skip the inset; very long AI text clamps with a "Continue reading" expander; the headline generator must not invent facts — derive it mechanically from structured entry fields, not another LLM call.

## C7 — Auth screen as the front page above the fold

**Prompt:**

> Restyle `AuthScreen.jsx`/`.css`: full pink-paper page with the masthead huge and centered, a dateline, and a one-line standfirst ("Paper trading on the National Stock Exchange — no capital required, reputation at stake."). The login/register form sits in a single ruled box styled like a classifieds coupon ("SUBSCRIBE / SIGN IN"), fields on ruled lines, submit as a solid ink button. Optionally a faint background of typeset mock headlines at 4% opacity. Edge cases: error messages set in oxblood small print inside the coupon; password managers must still autofill (don't break input semantics for style); responsive down to 360px.

## C8 — Script editor & profile

**Prompt:**

> 1. `ScriptEditor.jsx`: Monaco gets a custom light theme matching the palette (define via `monaco.editor.defineTheme`: paper-lift background, ink default text, oxblood keywords, byline-blue functions, green strings). Frame the editor like a manuscript page with a ruled margin; the run/save buttons as print buttons; `IndicatorChart` output restyled per C3's print chart rules. Console/errors panel as "PROOFREADER'S MARKS" in oxblood mono.
> 2. `Profile.jsx`: a "trader's ledger page" — account summary as a figures box, trade history as a broadsheet table (C3 style), season badges (B5) as circular ink stamps, `TraderScoreCard` and `SeasonHistory` restyled to match.
> Edge cases: Monaco theme must apply after editor mount (theme registration order); chart colors for multiple indicator plots need a print-safe palette (ink, oxblood, byline blue, green, ochre — test on the pink ground).

## C9 — Motion, polish, and the human details

**Prompt:**

> Final pass across all screens: (1) page transitions: none/instant — print doesn't animate; reserve motion for three moments only: the EXECUTED stamp (C4), live price tick updates (a brief 300ms `--hilite` background flash on the changed numeral, like fresh ink), and rank-movement arrows on the leaderboard. (2) Replace every remaining spinner with typographic loading states. (3) Sweep for leftover dark-theme styles: grep all `.css` and inline styles for `#08090a`, `#111214`, `gold`, `rgba(255,255,255`, `backdrop-filter`, `box-shadow` and remove/replace. (4) Empty states get one editorial sentence each, in Newsreader italic. (5) Accessibility audit: WCAG AA contrast on every token pair (the pink ground is unusual — verify `--ink-faint` on `--paper` passes 4.5:1, adjust if not), focus states as 2px ink outlines, `prefers-reduced-motion` disables the stamp animation. (6) Favicon + page title styled to match ("₹" glyph in a serif on pink).

## C10 — Verification

**Prompt:**

> Run the frontend, screenshot every screen at 1440px and 390px widths, and review against the kill list (no dark surfaces, no glass, no glow, no shadow-cards, no uppercase micro-label spam, no Inter). Confirm: all numerals are mono/tabular, gains/losses always carry a sign glyph, charts match the print theme, fonts actually load (check network panel), and Lighthouse accessibility score ≥ 95. List any component still on old tokens.

---

## Suggested order overall

1. **A1–A2** (can't deploy without), **B1** (correctness), **C1** (unblocks all UI work) — first wave, parallel sessions.
2. **A3–A4, B2, C2–C5** — second wave.
3. **B3–B4, C6–C8** — third wave.
4. **B5–B6, C9–C10** — final polish.

Keep every task its own branch/commit. For C-tasks, review screenshots before accepting — agents drift back toward generic "clean SaaS" styling; hold the line on the newspaper rules (hairlines, serif display, square corners, no shadows).
