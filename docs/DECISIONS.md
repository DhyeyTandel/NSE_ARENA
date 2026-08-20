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
