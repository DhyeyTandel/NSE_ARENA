# Deployment Security, Logic/Product Ideas — StockPaper

Verified against actual code on 2026-07-12. Part A = must-fix before public deploy. Part B = product/logic improvements. UI is discussed separately in chat.

---

# Part A — Security issues for deployment

## A1 — Hardcoded Postgres password in docker-compose (CRITICAL for deploy)

`docker-compose.yml` ships `POSTGRES_PASSWORD: password` and bakes it into `DATABASE_URL`. Postgres port `5432` is also published to the host (`ports: ["5432:5432"]`), so the DB is reachable from outside the compose network with a trivial password.

**Prompt:** Move all secrets to env vars: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?required}`, build `DATABASE_URL` from it, and remove the `5432:5432` port mapping in production (the backend reaches Postgres over the internal network; only expose it if you need external admin access, and then behind a firewall). Same for Redis — don't publish `6379` publicly. Provide a `.env.example` listing `POSTGRES_PASSWORD`, `SECRET_KEY`, `GEMINI_API_KEY`.

## A2 — No rate limiting on `/auth/login` or `/auth/register` (CRITICAL)

`auth.py` has zero throttling. Login is a straight bcrypt check — an attacker can brute-force passwords and enumerate usernames (the register endpoint even returns distinct "Username already registered" vs "Email already registered", confirming which accounts exist).

**Prompt:** Add IP-based rate limiting to `/auth/login` and `/auth/register` (e.g. `slowapi` or a Redis counter — 5 login attempts/min/IP, 3 registrations/hour/IP; 429 on exceed). Make register responses generic ("registration failed") to stop account enumeration, or accept enumeration as a tradeoff and document it. Add a small artificial delay / constant-time path so timing doesn't leak valid usernames.

## A3 — No password strength or input validation on register (HIGH)

`RegisterRequest` accepts any `username`/`email`/`password` string. No min length, no email-format check, no max length (a 10MB password string gets bcrypt-hashed → CPU DoS; bcrypt also silently truncates at 72 bytes). Username has no charset limit → XSS-in-username reflected on the leaderboard.

**Prompt:** On `RegisterRequest` add: `username: constr(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")`, `email: EmailStr`, `password: constr(min_length=8, max_length=128)`. Reject before hashing. This also closes the leaderboard XSS vector (Gap: `username` is rendered in the UI).

## A4 — WebSocket `/ws/prices` is completely unauthenticated (MEDIUM)

`websocket.py` accepts any connection, appends to a global `connected_clients` list, and each client opens its own Redis pubsub subscription. Unauthenticated + unbounded = trivial resource-exhaustion DoS (open thousands of sockets → thousands of Redis subscriptions). Price data isn't secret, so auth is optional, but the resource bound is not.

**Prompt:** Add a connection cap and per-IP limit on `/ws/prices`; share ONE Redis pubsub subscription across all clients (fan out in-process) instead of one subscription per socket — the current design scales Redis connections linearly with users. Optionally require a valid token on the WS handshake (query param or cookie) so only logged-in users stream. Add a max message rate / idle timeout.

## A5 — Errors leak internals to clients (MEDIUM)

`scripts.py` returns `HTTPException(500, f"Script execution error: {str(e)}")` and `500, str(e)` in places — raw exception text (stack details, internal paths) reaches the client. `submit_trade` similarly surfaces `str(e)`.

**Prompt:** Audit all routes for `detail=str(e)` / f-strings interpolating exceptions into responses. Log the full exception server-side (with a request ID) and return a generic message + the request ID to the client. Add a global exception handler in `main.py` so unhandled errors never return tracebacks (FastAPI does this by default only when `debug=False` — confirm debug is off in prod).

## A6 — No security headers / HTTPS enforcement (MEDIUM)

No HSTS, X-Content-Type-Options, X-Frame-Options, or Referrer-Policy. If tokens ever move to cookies (Task 5.4), `Secure`/`SameSite` matters; even with localStorage, clickjacking and MIME-sniffing are open.

**Prompt:** Add a middleware setting `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`. Terminate TLS at the reverse proxy (nginx/Caddy/Traefik) and redirect HTTP→HTTPS. Document the deploy topology.

## A7 — AI/decisions and other GET routes — confirm intended exposure (LOW)

`ai.py::/decisions` has no auth. Probably fine (public feed), but confirm it can't leak another user's private strategy/reasoning. Leaderboard exposes `username` + `is_ai` only (good — no email). Just verify no route returns `email` or `hashed_password` anywhere.

**Prompt:** Grep every serializer/response for `email`, `hashed_password`, and internal IDs you don't want public. Confirm `/ai/decisions` is intentionally public and contains nothing user-private.

## A8 — Deploy hygiene checklist

- `ACCESS_TOKEN_EXPIRE_MINUTES` — confirm it's short (tokens can't be revoked without a denylist; a 24h token stolen via XSS is 24h of access). Consider refresh tokens or a shorter expiry.
- No token revocation/logout server-side — document or add a denylist.
- Dockerfile: run as non-root user, pin base image digest, `.dockerignore` excludes `.env` and `.git`.
- Dependency scan: `pip-audit` on `requirements.txt` before deploy.
- DB migrations: you're relying on `init_db` / `create_all`; for a real deploy adopt Alembic so schema changes (and the new CheckConstraints) apply to existing data.

---

# Part B — Logic & product ideas

## B1 — Trade correctness (fixes trust in the whole game)
Covered in ANTIGRAVITY_FOLLOWUP.md — limit-fill semantics (Gap 1), stale-price execution (Gap 4), SQLite locking no-op (Gap 3). These are logic bugs, not just security. Do them first; the leaderboard is meaningless until they're closed.

## B2 — Fees & settlement realism
You already model fees (STT, brokerage, GST) and T+1 settlement — nice. Ideas: show a fee breakdown preview in the order panel *before* confirm; enforce that pending (unsettled) shares can't be sold (verify the `state=="confirmed"` filter in trades actually blocks selling T+0 buys); handle corporate actions (splits/dividends) or explicitly declare them out of scope so prices don't jump inexplicably.

## B3 — Leaderboard integrity
Rank by a risk-adjusted score (you have `TraderScore` / Sharpe-like logic) not raw P&L, so users can't top the board with one lucky leveraged bet. Add a minimum-trades threshold to appear. Consider a "days active" tiebreaker. Guard against wash-trading between two accounts to inflate volume-based metrics.

## B4 — AI opponents as a feature
`is_ai` flag + AI agent is a strong differentiator. Ideas: give each AI a named persona + visible strategy blurb ("momentum", "mean-reversion"); show the AI's recent decisions in the feed (you have `/ai/decisions`) to make it feel alive; let users "challenge" an AI. Make sure AI trades go through the *same* validated `/trades` path, not a privileged shortcut — otherwise the AI can cheat the circuit breaker.

## B5 — Onboarding & the PineScript editor
The Monaco-based script editor is powerful but intimidating. Offer 2–3 starter templates (you have "20 SMA vs 50 SMA" already), a "backtest this on last 90 days" button showing hypothetical P&L, and inline error highlighting. Gate live deployment of a script-driven strategy behind a successful backtest.

## B6 — Anti-abuse / fairness
One human = one account (email verification), else the leaderboard fills with sockpuppets. Season reset archiving (you have `SeasonHistory`) — confirm P&L is snapshotted, not recomputed from live prices later. Rate-limit trades per user to stop scripted spam even within market hours.

---

See chat for UI direction — I want a couple of decisions from you before proposing specifics.
