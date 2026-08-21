# Decisions

Append-only log of architectural decisions for this project.
Entries are added via the `/log` command. Do not rewrite or
tidy earlier entries.

## [2026-08-20] Extract services/trading.py instead of routing the AI agent through engine/matching.py

**Problem** — `ai/scheduler.py` hardcoded `AIAgent(portfolio_data, order_engine=None)`.
There is no `OrderEngine` class anywhere in the codebase, so any
guardrail-approved AI decision hit `self.order_engine.submit(...)` on
`None`, raised an `AttributeError` outside the agent's own try/except, and
was swallowed by `scheduler.py`'s broad `except Exception` — the AI
trading feature could never place a real trade, and it failed silently
(no `AIDecision` row was even written for that cycle). Separately,
`api/routes/trades.py:33-34` typed `side`/`order_type` as bare `str`, so a
non-canonical value like `"Sell"` (capital S) passed validation, built an
internal SELL order, and got recorded as an "executed" `TradeRecord" —
but the mutation branches only matched exact lowercase `"buy"`/`"sell"`,
so no cash or position ever moved.

**Options considered**
1. Wire the AI agent's order execution through `engine/matching.py` /
   `engine/order_book.py` (the existing, unused SortedDict order-book
   matching engine) — rejected. That module has never been imported by
   `api/` or `main.py`; the live trade path has never rested an order on
   a book, it fills immediately at the current market quote. Routing the
   AI through it would mean the AI trades under different rules than
   humans (a resting-order model vs. immediate-fill), a much larger
   architectural change, and would leave the phantom-sell bug's mutation
   logic duplicated a third time instead of unified.
2. Duplicate the validation/fee/mutation logic from `trades.py` directly
   into a new AI order-execution path — rejected. Two independent copies
   of balance/circuit-breaker/position-mutation logic are exactly the
   kind of divergence risk a trading platform can't afford (the fee
   calculation was already computed two different ways in two places
   before this work — validator ignored fees, execution didn't).
3. Extract the validation + fee calculation + atomic guarded-UPDATE
   cash/position mutation + `TradeRecord` bookkeeping out of
   `api/routes/trades.py` into a standalone `services/trading.py::execute_validated_trade()`,
   have both the human `/trades` route and a new `ai/execution.py::AIOrderExecutionService`
   call it — chosen. Same `Validator` checks, same atomic mutation, same
   bookkeeping for both paths; the AI physically cannot bypass a
   guardrail the human path enforces, because it is calling the same
   function.

**Decision** — Extract the trade-execution core into
`services/trading.py` (option 3). `api/routes/trades.py` still owns
price-resolution (Redis-cached quote + staleness handling + refetch) and
portfolio-row locking — that part differs enough between callers (the AI
already has a fresh quote from its watchlist fetch each cycle) that it
stayed in each caller rather than being forced into the shared function.
`ai/execution.py::AIOrderExecutionService` opens its own DB session,
locks the AI user's portfolio row, and calls the same
`execute_validated_trade()`. Also retyped `TradeRequest.side`/`order_type`
as `Literal["buy","sell"]`/`Literal["market","limit"]` so FastAPI rejects
malformed values with 422 before the mutation path is reachable at all.

**Tradeoff accepted** — `services/trading.py` now sits between two
callers with different transaction-management needs (one HTTP
request-scoped session, one scheduler-owned session per AI cycle), so the
function takes an already-locked `portfolio` object and an already-resolved
`current_price`/`previous_close` rather than owning the whole request
lifecycle itself — callers must remember to lock the portfolio row and
resolve prices correctly before calling it, which is an implicit contract
enforced only by a docstring, not the type system. `engine/matching.py`
remains dead code in the live path; it was not deleted, only documented
as a standalone exercise (module docstrings + README), since integrating
it live was explicitly ruled a separate, larger decision.

**What went wrong** — nothing on the implementation side (full suite
stayed green — 91 → 94 → 96 → 99 passing — at every commit). The main
risk during the refactor was silently changing `/trades` response
behavior while extracting; caught by running the full existing suite
before writing a single line of AI-side code, confirming the extraction
was behavior-preserving before building on top of it.

**Scale/limits** — `AIOrderExecutionService.submit()` opens a brand-new
`async_session()` per call rather than reusing the scheduler's read-only
session; fine at the current cadence (one AI cycle per 30 minutes, single
AI user), but would need connection-pool awareness if the AI watchlist or
trading frequency grows significantly. `AIRiskMemory` rehydration reads
the last 50 `AIDecision` rows every cycle with no index hint beyond
`created_at` ordering — fine at current volume, would want an index if
`ai_decisions` grows into the tens of thousands of rows.

## [2026-08-20] Drop the unused alembic dependency instead of standing up real migrations

**Problem** — `requirements.txt` listed `alembic==1.13.0`, but there was
no `alembic/` directory, no `alembic.ini`, and no code anywhere importing
it (confirmed by grep). Actual schema management is
`Base.metadata.create_all()` on startup (`database.py`, `main.py`). A
careful reviewer inspecting dependencies would notice the unused package
and read it as either an abandoned migration attempt or a stale copy-paste
from a template — neither is accurate, and this same night's session had
just changed the schema itself (Priority C: `TraderScore.season_id` → FK,
new `CheckConstraint`s, new indexes on `Position`/`TradeRecord`), so the
gap between "declares a migration tool" and "has no migrations" was
freshly wider, not narrower.

**Options considered**
1. Configure real Alembic migrations against the async SQLAlchemy setup
   (`alembic init`, wire `env.py` to the app's `Base` metadata and
   `DATABASE_URL`, autogenerate a baseline migration matching the schema
   Priority C just landed) — rejected for tonight specifically, not in
   general. The autogenerate step needs to run against a real database
   to diff correctly, and production runs Postgres
   (`config.py` refuses to boot `ENV=production` against SQLite) while
   this session has no Postgres instance available — `docker-compose.yml`
   and all deploy infra are explicitly Pam's file ownership this round,
   not mine to spin up. Standing up Alembic's async engine wiring
   correctly (SQLAlchemy 2.0 async + Alembic's still-primarily-sync
   autogenerate tooling has known rough edges) and shipping it
   *unvalidated* against the actual target database felt like a worse
   outcome than not shipping it — a broken migration path masquerading as
   a working one is strictly worse than an honestly-absent one.
2. Leave `alembic` in `requirements.txt` untouched and do nothing —
   rejected. That's the exact state the audit flagged as misleading;
   doing nothing doesn't resolve the "declares a tool it doesn't use"
   problem, it just leaves it for the next person to notice.
3. Drop the dependency and document `Base.metadata.create_all()` as the
   deliberately-chosen schema strategy for the project's current size —
   chosen. Honest about what actually runs today; doesn't block a real
   migration setup later by whoever has Postgres access to validate
   against.

**Decision** — Removed `alembic==1.13.0` from `backend/requirements.txt`.
`Base.metadata.create_all()` remains the schema-management strategy.

**Tradeoff accepted** — There is still no migration path. Any future
schema change (including further money/schema work from this session's
own punch list) requires either a fresh DB or a hand-written `ALTER
TABLE`, same as before this decision — this doesn't fix that gap, it just
stops the dependency list from claiming otherwise. Standing up real
Alembic migrations against Postgres, with the schema now including this
session's Numeric/CheckConstraint/index/FK changes, is an explicit,
concrete follow-up for whoever next has a live Postgres environment to
validate autogenerate output against.

**What went wrong** — nothing; this was a scope decision made before
writing any Alembic code, not a rollback from a failed attempt.

**Scale/limits** — N/A — this is the absence of a migration tool, not a
capability with a scale boundary.

## [2026-08-21] Frontend served same-origin behind Caddy, not via a hardcoded backend URL

**Problem** — `docs/RESUME_AUDIT.md` §4 flagged that `docker-compose.yml`
had no frontend service at all: only `caddy`, `backend`, `postgres`,
`redis`, with `Caddyfile` reverse-proxying everything to `backend:8000`.
The README's "Docker (Full Stack)" section claimed to run the whole app
but only ever started the API. Adding a frontend service meant deciding
how the built React app would find the backend once both live behind the
same Caddy host — the existing `frontend/src/config.js` defaults
`API_URL`/`WS_URL` to `http://localhost:8000`, which is only correct for
the native (non-Docker) dev setup where Vite's dev server and uvicorn run
on different ports on the same machine.

**Options considered**
1. Bake an absolute URL into the frontend build from `DOMAIN`
   (`https://${DOMAIN}` as a Docker build arg) — rejected. `DOMAIN`
   controls whether Caddy serves HTTP or automatic HTTPS (plain HTTP for
   `localhost`/unset, HTTPS otherwise per the existing Caddyfile
   comment), so a hardcoded `https://` prefix would break the local
   `docker-compose up` path, and a hardcoded `http://` would break real
   deploys. Getting this right would mean templating protocol *and* host
   into the image, coupling the frontend build to `DOMAIN` and forcing a
   rebuild on every domain change.
2. Serve the frontend's static build directly out of the `caddy`
   container via a shared volume, no separate frontend container —
   rejected even though it avoids an extra hop. It would mean the
   frontend's build step (npm ci / vite build) has to happen in an init
   container or on the host before `caddy` starts, which is more moving
   parts than a standard multi-stage Dockerfile, and it's not what was
   asked for (a frontend service + Dockerfile in the stack).
3. Same-origin relative URLs: build the frontend with `VITE_API_URL=""`
   /`VITE_WS_URL=""` (Docker build args, baked in at `vite build` time),
   so `fetch()`/`WebSocket()` calls go out as relative paths
   (`/auth/login`, `/ws/prices`) that resolve against whatever origin
   served the page. Caddy then path-routes: an explicit allowlist of
   backend path prefixes (`/auth`, `/trades`, `/portfolio`,
   `/leaderboard`, `/seasons`, `/ai`, `/api`, `/price`, `/score`, `/ws`,
   `/health`, `/docs`, `/redoc`, `/openapi.json` — enumerated from
   `main.py` and every `api/routes/*.py` router prefix, since the
   backend has no single common `/api` prefix) to `backend:8000`, and
   everything else (the SPA) to a new `frontend:80` nginx container —
   chosen. One frontend image now works unmodified behind `localhost` or
   any real `DOMAIN`, with no rebuild-per-environment and no
   protocol/host coupling.

**Decision** — Option 3. Added `frontend/Dockerfile` (multi-stage:
`node:20-alpine` build → `nginx:1.27-alpine` serve, with SPA fallback via
`try_files $uri /index.html` in `frontend/nginx.conf`), a `frontend`
service in `docker-compose.yml` with `VITE_API_URL`/`VITE_WS_URL` build
args pinned to `""`, and rewrote `Caddyfile` with a named `@backend`
path matcher followed by a catch-all `reverse_proxy frontend:80`. This
required one small change outside the strict "deploy config" boundary:
`frontend/src/config.js` used `import.meta.env.VITE_API_URL ||
'http://localhost:8000'` — `||` treats an explicitly-empty string the
same as unset and falls through to the localhost default, which would
have silently defeated the whole same-origin approach. Changed that one
line's operator to `??` (nullish coalescing) so an explicit empty string
is honored while the unset-in-native-dev case still gets the
`localhost:8000` default unchanged. Judged in-scope because this file's
entire purpose (per its own header comment, added when it was extracted
in commit `c5f21b9`) is deploy-time backend-URL configuration — not
application logic — and the alternative was leaving the Docker "full
stack" claim false in a different way (frontend built, but silently
unable to reach the API in any Docker deployment).

**Tradeoff accepted** — The Caddy path allowlist is a manually-maintained
list that has to be kept in sync with backend route prefixes; if a future
route is added under a new top-level prefix and `Caddyfile` isn't
updated, it will silently 404 through the frontend's SPA fallback instead
of reaching the backend. A `/api/*`-prefix convention on every backend
router would make this self-maintaining, but reprefixing existing routes
is a backend/`main.py` change outside this track's file ownership
(backend/*.py is owned by the parallel backend-track agent on this repo)
— left as a follow-up rather than done here.

**What went wrong** — nothing required a redo; the main risk (getting
`||` vs `??` wrong in `config.js`, or Caddy's same-directive-name
ordering for the two `reverse_proxy` lines) was caught by reasoning
through both before writing them, not by trial and error, since Docker
wasn't available in this sandbox to run the stack directly. `docker
compose config`/build could not be executed here (no `docker` binary) —
`docker-compose.yml` was instead validated by parsing it with a real YAML
parser (`js-yaml` under `node`) and reading the resulting structure back;
`.github/workflows/ci.yml` was validated the same way. Whoever next has a
Docker daemon available should do a real `docker compose up --build` pass
before this is called done.

**Scale/limits** — N/A for this change (docs/DevOps only).

## [2026-08-21] Numeric(14,2)/Decimal for stored money, boundary-coerced via Decimal(str(x))

**Problem-context** — Every money column (`Portfolio.cash_balance`,
`Position.avg_price`, `TradeRecord.price`/`fees`,
`DailyPortfolioValue.total_value`) was `Float`. Binary floating point
cannot represent most decimal fractions exactly; on a ledger that
accumulates balance changes across many trades, individually tiny
rounding errors compound and can eventually trip the
`cash_balance >= 0` `CheckConstraint` on a balance that is conceptually
exactly zero, or produce paisa-level discrepancies a real trading
platform's books can't tolerate.

**Options considered**
1. Leave columns as `Float`, round defensively wherever a balance is
   displayed or compared — rejected. Rounding at display time doesn't
   fix the stored ledger; the error is already baked into what's
   persisted, just hidden from the user.
2. Integer paise (store every amount as an integer count of the
   smallest currency unit) — rejected. Exact, but every existing
   money-touching line (dozens, across `engine/`, `services/`,
   `api/routes/`) would need `/100` conversions at every display
   boundary instead of a type swap; Postgres/SQLAlchemy already support
   exact decimal storage natively via `Numeric`, so this bought little
   over option 3 for meaningfully more churn.
3. `Numeric(14, 2)` columns, `Decimal` throughout every function that
   computes or mutates money (`engine/fee_engine.py`,
   `engine/validator.py`, `services/trading.py`) — chosen.

**Decision** — Money columns are `Numeric(14, 2)`; money arithmetic
uses Python's `decimal.Decimal`. Boundary rule, applied everywhere a
`float`/`int`/`str` value enters Decimal space (a Pydantic request
body, a yfinance quote dict, a test literal): `Decimal(str(value))`,
never `Decimal(value)` directly — the latter bakes in the float's own
binary-representation error (`Decimal(0.1) != Decimal("0.1")`, but
`Decimal(str(0.1)) == Decimal("0.1")`). The coercion helper was
initially duplicated as a private `_to_decimal` in three files during
implementation and later consolidated into `engine/money.py::to_decimal()`
during a self-directed code-review pass (see `docs/problems.md`).
Ratios/percentages/scores (`position_size_pct`, `TraderScore.*`) stay
`Float` deliberately — they're derived display values, not accumulated
ledger amounts, and don't share the compounding-error problem.

**Tradeoff accepted** — Read-only display code that mixes a stored
`Decimal` field with a live `float` market quote (yfinance/Redis) needs
an explicit `float(...)` cast at that exact boundary
(`api/routes/portfolio.py`, `api/routes/leaderboard.py`,
`ai/scheduler.py`'s AI-prompt data dict). This is an ongoing discipline
cost, not a one-time fix: every new code path that reads a Decimal
field and mixes it with a float has to remember this, and nothing in
the type system enforces it — a missed cast raises a `TypeError` at
runtime (caught once during this work by an HTTP-level regression test,
see `docs/problems.md`), not at review time.

**Scale/limits** — `Numeric(14, 2)` caps a stored balance at
~₹999,999,999,999.99, far beyond anything a ₹1,00,000-starting-capital
paper-trading platform will ever reach.

## [2026-08-21] Fee-aware balance validation — unify the two places trade cost was computed

**Problem-context** — `Validator._check_balance` estimated a buy
order's cost as `price * quantity`, ignoring fees entirely.
`services/trading.py`'s actual execution computed the real cost as
`execution_price * quantity + fees.total`. A trade could pass
validation (which said the balance was sufficient, having ignored fees)
and only then fail — or in a scenario where the two calculations
diverged further, succeed with an under-counted cost — at the DB-layer
guarded UPDATE that uses the real, fee-inclusive number.

**Options considered**
1. Leave validation fee-blind and rely on the guarded UPDATE as the
   real backstop — rejected. The user-facing validation error would be
   actively misleading ("sufficient balance") right up until a
   different, confusing failure at execution time.
2. Duplicate the fee calculation inside `Validator` — rejected. This is
   exactly the "two independent copies of money logic" risk already
   named and rejected in the very first `services/trading.py` decision
   above; fee calculation had already been wrong-by-omission in one of
   two places before this fix, which is the concrete failure mode this
   option would keep alive.
3. Give `Validator` its own `FeeEngine` instance and have
   `_check_balance` call the same `calculate()` the execution path
   calls — chosen.

**Decision** — `Validator.__init__` constructs `self._fee_engine =
FeeEngine()`. `_check_balance` computes `estimated_fees =
self._fee_engine.calculate(price=price, quantity=order.quantity,
side="buy", trade_type="delivery").total` and includes it in
`estimated_cost`, so the validation-time estimate and the
execution-time real cost are computed by the same code.

**Tradeoff accepted** — `Validator` now has a direct dependency on
`FeeEngine` it didn't have before, a coupling between two previously
separate `engine/` modules. Acceptable: both are pure,
side-effect-free, deterministic calculators living in the same package,
so the coupling doesn't cross a meaningful boundary.

**Scale/limits** — N/A — this is a correctness fix, not a capacity
boundary.

## [2026-08-21] Holiday-aware T+1 settlement reuses market_calendar instead of a second holiday list

**Problem-context** — `SettlementEngine.calculate_settlement_date` only
skipped weekends (`next_day.weekday() >= 5`), not NSE holidays. A trade
placed the day before an NSE holiday would settle "the next calendar
weekday" even when that day is a declared market holiday — marking a
position sellable a day earlier than it should be.

**Options considered**
1. Hardcode a second NSE holiday list inside `settlement.py` — rejected.
   `engine/market_calendar.py` already holds the 2026 NSE holiday list
   (added earlier for market-hours validation); a second, independently
   maintained list is a guaranteed future drift bug — someone updates
   one calendar for 2027 and forgets the other.
2. Import and reuse `market_calendar.is_trading_day()` — chosen.

**Decision** — `calculate_settlement_date` now loops
`while not market_calendar.is_trading_day(next_day.date()): next_day
+= timedelta(days=1)` in place of the bare weekday check.

**Tradeoff accepted** — `engine/settlement.py` now depends on
`engine/market_calendar.py`'s holiday list being kept current
year-over-year. If nobody extends the list past 2026, settlement dates
silently degrade back to weekend-only correctness — no error is
raised, the function just stops accounting for holidays it doesn't
know about, and a trade near a future undated holiday will settle one
day earlier than the real NSE calendar allows.

**Scale/limits** — N/A.

## [2026-08-21] Schema hardening: real FK, CheckConstraints, and hot-column indexes

**Problem-context** — `TraderScore.season_id` was a bare `Integer`, not
a `ForeignKey` — nothing at the database layer stopped a `TraderScore`
row from referencing a season that doesn't exist. `Position.quantity`
and `TradeRecord.quantity` had no non-negativity/positivity
constraints — a bug anywhere in the mutation code (present or future)
could silently persist a negative position or a zero-quantity trade
record with no error. `Position.portfolio_id` and
`TradeRecord.portfolio_id` — queried on every leaderboard and trade
history load — had no index; Postgres does not auto-index foreign key
columns the way some other databases do.

**Options considered** — for all three, the only real alternative was
"leave it as an application-level-only invariant, trust every current
and future code path to get it right." Rejected uniformly: that's
precisely the class of invariant a `CheckConstraint`/`ForeignKey`
enforces for free at the database layer, independent of which code path
(current or not-yet-written) performs the write.

**Decision** — `TraderScore.season_id` →
`Column(Integer, ForeignKey("seasons.id"), nullable=False)`.
`CheckConstraint("quantity >= 0", name="chk_position_quantity_non_negative")`
on `Position`; `CheckConstraint("quantity > 0",
name="chk_trade_quantity_positive")` on `TradeRecord`. `index=True`
added to both `portfolio_id` columns.

**Tradeoff accepted** — SQLite, used by every test in this suite, does
not enforce foreign key constraints at runtime unless
`PRAGMA foreign_keys=ON` is explicitly set per connection — unlike
Postgres (production), which always enforces them. This means a test
asserting the FK exists has to check the SQLAlchemy metadata
declaration directly (`Table.c.<col>.foreign_keys`) rather than
triggering a runtime `IntegrityError`, and a developer running against
a local SQLite dev database would not see the FK actually enforced even
though it's correctly declared — a real behavioral gap between the dev
and production database engines that has to be understood, not just
tested around (see `docs/problems.md` for how this was discovered).

**Scale/limits** — The new indexes trade a small write-time cost (index
maintenance on every `Position`/`TradeRecord` insert) for read-time
speed on the leaderboard/history queries that filter by
`portfolio_id` — the right tradeoff for a read-heavy leaderboard at any
realistic scale for this app.

## [2026-08-21] Concurrency correctness: row locks + a SQLite-safe conditional-UPDATE backstop + refuse-boot-on-SQLite-in-production

This pattern predates this session's work — it is documented here
because god's dispatch flagged it as interview-critical and it had
never been written up in `DECISIONS.md`. This is retroactive
documentation of existing design, not a decision made during Phase 1,
Phase 2, or Priority E.

**Problem-context** — Two concurrent trades against the same portfolio
or position (two browser tabs, a race between the AI scheduler and a
human trader, two API workers) can both read the same `cash_balance` or
share `quantity`, both independently conclude they have enough, and
both write — overdrawing the balance or overselling shares that
neither trade alone would have overdrawn.

**Options considered**
1. `SELECT ... FOR UPDATE` row locking alone (`with_for_update()`) —
   insufficient by itself: on SQLite, `with_for_update()` is a silent
   no-op (SQLite has no row-level locking model at all), so relying on
   it alone would be correct on Postgres and silently unsafe on any
   SQLite deployment, with no error or warning that the guarantee isn't
   actually being provided.
2. An application-level mutex/semaphore per portfolio — rejected.
   Doesn't generalize across multiple worker processes without a
   distributed lock (e.g. a Redis-based lock), which adds an external
   dependency and its own failure modes for something the database can
   already guarantee natively.
3. `with_for_update()` (correct on Postgres) *plus* a guarded
   conditional `UPDATE ... WHERE cash_balance >= cost` /
   `WHERE quantity >= qty`, checking the resulting `rowcount` — chosen.
   A conditional `UPDATE` is atomic at the database engine level
   regardless of row-locking support, so it is the real correctness
   backstop on SQLite and a defense-in-depth backstop on Postgres.

**Decision** — Every cash-debiting and share-debiting write in
`services/trading.py` goes through a guarded
`UPDATE ... WHERE <balance/quantity check>` and checks `rowcount == 0`
to detect a lost race, raising `TradeRejected` instead of silently
overdrawing. Additionally, `config.py` raises `RuntimeError` at import
time if `ENV=production` and `DATABASE_URL` starts with `sqlite` —
since `with_for_update()`'s silent no-op makes SQLite an unsafe
production database under this concurrency model, the app refuses to
boot into that configuration rather than running unsafely without any
indication.

**Tradeoff accepted** — The guarded-UPDATE pattern means a losing
concurrent trade gets a generic "insufficient balance/shares" rejection
even if it might have been perfectly valid moments earlier — there's no
retry-with-backoff, just a clean rejection surfaced to the caller.
Acceptable for a paper-trading platform (a rejected trade costs nothing
real); a system where a race-lost order MUST eventually fill would need
a queued-retry strategy instead.

**Scale/limits** — The boot-time refuse-on-SQLite guard is a hard
availability tradeoff by design: a production Postgres outage has no
automatic SQLite fallback. The alternative (allow it) would trade a
clean startup failure for silent data-integrity risk under concurrent
load — judged the wrong tradeoff for a ledger.

## [2026-08-21] Security hardening: rate limiting, ticker validation, indicator DoS guards, error-message hygiene

**Problem-context** — `POST /trades` had no rate limit, unlike
`/auth/register` and the scripts endpoints, which already had one —
each trade request does real work (portfolio row lock, position query,
full validator pass, mutation), making it a meaningfully expensive
endpoint to leave unbounded. `TradeRequest.ticker` was an unconstrained
string. `scripting/indicators.py`'s `roc`/`highest`/`lowest`/`atr` had
no guard against a negative or zero `length` argument reachable from
user-submitted script code (`ta.roc(close, -1)` etc.) — `stoch` already
had this guard, so the gap was an inconsistency, not a from-scratch
decision. `POST /api/scripts/run`'s error handler returned the raw
Python exception string to the client on any failure, a potential
internal-detail leak (file paths, variable state) with no upside over a
generic message plus a server-side log.

**Options considered** — the general choice for all four was "trust
the input is well-formed" vs. "validate/bound it explicitly at the
boundary." Chose the latter for all four, extending patterns already
established elsewhere in the app rather than inventing new ones:
rate limiting reuses the existing `check_rate_limit` helper and bucket
pattern; ticker validation mirrors the existing regex-`Field(pattern=...)`
style; the indicator guard makes the four functions consistent with
`stoch`, which already had it; the error-leak fix follows the same
"log server-side, generic message to client" shape used elsewhere.

**Decision** — `check_rate_limit(bucket="trades", identity=f"user:{user.id}",
limit=20, window_seconds=60)` as the first statement in `submit_trade`.
`TICKER_PATTERN = r"^[A-Z0-9&\-]{1,20}$"` applied via Pydantic
`Field(pattern=TICKER_PATTERN)` on `TradeRequest.ticker`. `if length < 1:
return out` guards added to `roc`, `highest`, `lowest`, and `atr`'s
second loop. `scripts.py`'s broad `except Exception` now logs the real
exception server-side and returns a generic message to the client.

**Tradeoff accepted** — The 20/minute rate limit on trades is a
reasonable-guess number, not derived from load testing — it could be
too tight for a legitimate high-frequency paper-trading strategy or too
loose to meaningfully slow a determined abuser. Chosen to match the
existing `scripts` bucket's limit for consistency rather than a
load-tested figure.

**Scale/limits** — Rate limiting is Redis-backed and fails open on
Redis errors (pre-existing `check_rate_limit` behavior, unchanged here)
— under a Redis outage, `/trades` is completely unprotected by rate
limiting. This favors trading availability over strict protection
during an infrastructure outage, consistent with how the other
rate-limited endpoints already behave.

## [2026-08-21] Naive-UTC-in-DB convention: why datetime.utcnow() wasn't blindly replaced everywhere

**Problem-context** — `datetime.utcnow()` is deprecated (~360 warnings
across the test suite). The obvious mechanical fix,
`datetime.now(timezone.utc)`, produces a timezone-*aware* object — but
every `DateTime` column in `db/models.py` is naive, and (verified
directly with a throwaway round-trip test, not assumed from
documentation) SQLite silently drops `tzinfo` on read-back even when a
column is declared `DateTime(timezone=True)`. A blind repo-wide
replacement would raise `TypeError: can't compare offset-naive and
offset-aware datetimes` the moment an aware "now" was compared against
a DB-loaded value — which happens in `api/routes/seasons.py` and
`ai/scheduler.py` (`season.end_date - now`).

**Options considered**
1. Blind find-and-replace to `datetime.now(timezone.utc)` everywhere —
   rejected; verified by trying it first, confirmed it breaks the two
   comparison sites above with exactly the `TypeError` predicted.
2. Change every `DateTime` column to `DateTime(timezone=True)` so
   storage is genuinely aware — rejected for this session. SQLite
   (used by every test in this suite) does not actually preserve
   `tzinfo` through that column type either, verified directly — so the
   test suite could never confirm the change works, and "correct on
   Postgres, silently wrong on SQLite" is a worse, harder-to-notice
   state than one consistent naive convention applied everywhere a
   value touches the database.
3. Split the replacement by whether a value touches or is compared
   against a DB `DateTime` column — chosen.

**Decision** — New `database.py::db_utcnow()` —
`datetime.now(timezone.utc).replace(tzinfo=None)`, the identical
naive-UTC value `datetime.utcnow()` produced, just not the removed API
— used for every `Column(DateTime, default=...)` in `db/models.py` and
every comparison against a DB-loaded datetime
(`api/routes/seasons.py`, `ai/scheduler.py`, `main.py`'s Season
creation). Genuinely-aware `datetime.now(timezone.utc)` used everywhere
else: the JWT `exp` claim in `auth.py` (verified `python-jose`'s
`utctimetuple()`-based conversion handles both naive and aware inputs
correctly, so no risk there), in-memory dataclass timestamps in
`engine/models.py`/`engine/settlement.py`, display-only `.isoformat()`
strings in `ai/position_monitor.py`/`ai/risk_memory.py`, and the
settlement-date calculation in `services/trading.py` (which already
branched correctly on `.tzinfo` — see `docs/problems.md` for the real
bug this incidentally fixed).

**Tradeoff accepted** — The codebase now has two conventions for "the
current time" — `db_utcnow()` and `datetime.now(timezone.utc)` — where
before there was inconsistently one deprecated function. A future
contributor has to know which applies at a new call site, and nothing
in the type system enforces the right choice; picking wrong at a new
DB-comparison site reintroduces the exact `TypeError` this decision
prevents.

**Scale/limits** — N/A — this is a correctness convention, not a
capacity boundary. A real long-term fix would be a Postgres-only
`DateTime(timezone=True)` migration with SQLite dropped from the test
matrix entirely (Postgres genuinely preserves `tzinfo`) — a larger
change than this session's scope, and blocked on the same "no Postgres
instance available in this environment" constraint as the Alembic
decision above.

## [2026-08-21] Trader-score normalization: average penalty per trade, and real streak-weighting instead of flat win-rate

Note: `scoring/trader_score.py` has zero live callers anywhere in
`api/`, `ai/`, or `main.py` — confirmed by grep before starting this
work, and it was already true before this session. This decision
applies to code with no current runtime impact; it was still worth
fixing correctly since it was in explicit dispatch scope and now has
its first-ever test coverage.

**Problem-context** — `_discipline_score` summed violation penalties
across every trade with a fixed floor of 0: an active trader with a
*low* violation rate could score worse than a quiet trader at the exact
same rate, purely because more trades meant more chances to accumulate
penalty points against a floor that doesn't move. `_consistency_score`'s
docstring claimed "weighted by streak," but the implementation was flat
win-rate with no streak logic at all.

**Options considered — discipline**
1. Keep the summed-penalty/fixed-floor design, just retune the point
   values — rejected; doesn't fix the volume-penalizes-frequency
   property, only changes how quickly it manifests.
2. Normalize to average penalty per trade — chosen; makes the score a
   function of violation *rate*, decoupled from trade count.

**Options considered — consistency**
1. Fix the docstring only, drop the streak claim — the smaller, safer
   option, and would have been the right call for a live feature.
2. Actually implement streak/magnitude awareness — chosen. Because this
   module has zero production callers, the usual "minimize risk to a
   live feature" argument that shaped several other decisions this
   session doesn't apply here; a real streak/magnitude-aware score is
   more substantive and more interesting to explain than a one-line
   docstring edit, for equivalent implementation risk.

**Decision** — `_discipline_score` = `100 - (total_penalty /
trade_count)`. `_consistency_score` = `win_rate * 50 + streak_ratio *
25 + magnitude_ratio * 25`, where `streak_ratio` is the longest run of
consecutive positive-return days normalized by period length (rewards
sustained runs over the same win count scattered randomly), and
`magnitude_ratio` is `avg_gain / (avg_gain + avg_loss)` (rewards wins
proportionally bigger than losses, not just more frequent).

**Tradeoff accepted** — The discipline-score floor is no longer 0 for a
trader who violates every single check on every single trade — the
worst possible average penalty (10 + 15 + 5 = 30 per trade, if all
three checks fail every time) floors the score at 70, not 0. This is a
deliberate scope choice: the metric now measures per-trade compliance
*rate*, not aggregate risk exposure (that's already `_risk_score`'s job
via drawdown/volatility) — but it does mean `discipline_score` alone
can no longer distinguish an all-violations trader from a
mostly-compliant one once both are below that 70 floor.

**Scale/limits** — N/A — dead code, no live traffic to bound.

## [2026-08-21] google.genai migration: eager API-key validation required a placeholder-key fallback

**Problem-context** — `google-generativeai` is EOL/deprecated; the
dispatch required migrating to the unified `google.genai` SDK. The new
SDK's `genai.Client(api_key=...)` validates the key eagerly at
construction and raises `ValueError` on an empty string — this was
discovered via a cascade of test failures after the migration, not by
reading the SDK's validation behavior ahead of time. `config.GEMINI_API_KEY`
defaults to `""` when the env var is unset, true in this dev/test
environment, so every `AIAgent()` construction started raising
immediately, unlike the old SDK's `genai.configure(api_key="")`, which
never validated at all.

**Options considered**
1. Make `GEMINI_API_KEY` a hard startup requirement, the same way
   `config.py` already refuses to boot without a real `SECRET_KEY` —
   rejected as a bigger behavior change than this item's scope. The AI
   feature is explicitly designed to be optional today:
   `AIScheduler.start()` already checks `if not GEMINI_API_KEY: ...
   return` and disables itself gracefully with a warning. An app-wide
   hard requirement would contradict that existing "AI is optional"
   design rather than extend it.
2. Fall back to a placeholder key string when the real one is unset —
   chosen. Preserves the old SDK's lenient-construction behavior
   exactly; a real Gemini API call still fails cleanly against Google's
   servers if the key is genuinely unset in production — the same
   ultimate failure mode as before, just surfacing at call-time instead
   of never surfacing at all (since the old SDK's lenient `configure()`
   would have also failed on the first real call with an empty key,
   just with a different underlying error).

**Decision** — `self.client = genai.Client(api_key=GEMINI_API_KEY or
"unset-gemini-api-key")` in `ai/agent.py`.

**Tradeoff accepted** — A genuinely-misconfigured production deployment
(env var unset) now fails at the first Gemini call rather than at
process startup — later failure detection than a hard startup check
would give, accepted in exchange for not changing the existing
"AI trading is optional, disables itself gracefully" design contract.

**Scale/limits** — N/A.

## [2026-08-21] Scripting engine: if/else raises a clear error rather than being implemented; tokenizer deleted rather than wired in

**Problem-context** — The module docstring claimed if/else support;
`_execute_line` had no branch for it at all — an if/else line matched
none of the existing branches (`indicator`/`plot`/`hline`/assignment)
and fell through silently: the script "ran" with no error, but the
conditional logic inside it simply never executed. Separately,
`tokenize()`/`TOKEN_SPEC`/`Token` were built, with their own prior
ReDoS-safety review and a dedicated regression test, but never actually
consumed — the real interpreter does its own hand-rolled character
scanning in `_execute_line`/`_eval_expr`, never touching the token
stream `tokenize()` produces.

**Options considered — if/else**
1. Implement real block-structured if/else (indentation or explicit
   block-delimiter tracking, conditional line-skipping inside
   `execute()`'s line loop) — rejected for this pass. This is a live,
   user-facing feature (scripts are reachable via `POST
   /api/scripts/run`), and the current architecture processes every
   line independently with no concept of a "block" at all — this would
   be a rewrite of `execute()`'s control flow, not a line-local fix. A
   shallow implementation risks a *worse* failure mode than today's gap:
   silently-wrong execution of complex nested conditionals is harder for
   a script author to notice and debug than a clear "not supported"
   error.
2. Fix the docstring only — the smaller, safer option on its own.
3. Fix the docstring *and* make the previously-silent no-op raise a
   clear, actionable error pointing at the ternary operator — chosen.
   Strictly better than option 2 alone: it also turns a confusing
   silent failure into an immediate, understandable one for anyone who
   writes if/else syntax.

**Options considered — the tokenizer**
1. Wire it into the real execute path — rejected, same "rewrite-scale
   change to a live feature, disproportionate to a polish pass"
   reasoning as if/else above.
2. Delete it as vestigial — chosen; it is genuinely unused by anything
   reachable at runtime.
3. Leave it in place, unused, indefinitely — rejected; that is exactly
   the dead-code accumulation a polish pass should address, and this
   dispatch item's own framing ("wire in OR delete") didn't offer
   "leave as-is" as a real option.

**Decision** — `_execute_line` now matches `^(if|elif|else)\b` and
raises `ValueError("if/else blocks are not supported — use the ternary
operator instead: condition ? true_val : false_val")`, caught by the
existing per-line exception handling and surfaced in
`result.errors` like any other script error. The module docstring now
states only ternary is supported, and why (no indentation/block
tracking in a line-by-line interpreter). `tokenize()`, `TOKEN_SPEC`,
`Token`, and `TOKEN_RE` were deleted. The deleted test's ReDoS-safety
*purpose* was preserved, not lost — new pathological-input tests
(`tests/test_scripting_pathological_input.py`) target the actual live
entry point (`run_script`/`PineEngine.execute`) instead of the unused
tokenizer, which is more correct anyway: an attacker's script
submission never reaches `tokenize()`, so testing its safety was
testing code outside the real attack surface.

**Tradeoff accepted** — if/else support is a real, commonly-expected
PineScript feature that this DSL still doesn't have after this
session — user scripts that need branching logic must restructure as
ternary or be rejected outright. This is a genuine capability gap for a
"safe subset" interpreter, not just cleanup — deferred, not resolved.

**Scale/limits** — N/A.

## [2026-08-21] Structured logging: contextvar-based request ID, JSON formatter, deliberately minimal

**Problem-context** — Application logs were free-text
(`"%(asctime)s [%(name)s] %(levelname)s: %(message)s"`), with no way to
correlate every log line touched by handling one request across
different modules (a trade submission logs from `trades.py`,
`services/trading.py`, and the rate limiter, with nothing tying those
lines together).

**Options considered**
1. Thread a `request_id` parameter explicitly through every
   function/logger call on the request's path — rejected. Would touch
   dozens of call sites across the whole codebase, disproportionate to
   the dispatch's own explicit "keep it lightweight, don't
   over-engineer" framing for this item.
2. A `contextvars.ContextVar` set once by middleware at the start of
   each request, read by a `logging.Filter` that stamps it onto every
   `LogRecord` — chosen. Every existing `logger.info()`/`.warning()`
   call anywhere in the codebase picks up the request ID automatically,
   with zero changes to any of those call sites.

**Decision** — New `logging_setup.py`: `JSONFormatter` (one JSON object
per log line) + `RequestIdFilter` (reads the contextvar). New
`RequestIdMiddleware` in `main.py` sets the contextvar once per request
— reusing an incoming `X-Request-ID` header if a reverse proxy already
set one, otherwise generating a `uuid4` — and echoes it back in the
response header for client-side correlation.

**Tradeoff accepted** — `contextvars` do not automatically propagate
into work that escapes the current async context — specifically,
`asyncio.to_thread(...)` (used for blocking `yfinance` calls in
`main.py`'s `/price/{ticker}` route) runs in a separate thread and
loses the contextvar, so log lines emitted from inside that threaded
call will show `request_id: "-"` rather than the request's real ID.
This is a known, accepted gap for a "lightweight" pass rather than an
oversight — closing it would mean explicitly passing the request ID
into every `asyncio.to_thread` call site, more plumbing than this
dispatch item asked for.

**Scale/limits** — JSON-per-line logging is marginally more verbose on
disk than the previous single-line format; irrelevant at this
application's current log volume.
