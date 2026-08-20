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
