# Problems

Append-only log of real problems hit during this project — what broke,
how it was noticed, how it was diagnosed, and how it was fixed. This is
the "what went wrong and how I solved it" companion to
`docs/DECISIONS.md`, which covers "why I built it this way." Where a
single incident is both a bug and a design choice, the war story lives
here and the design choice lives in DECISIONS.md, cross-referenced.

Do not rewrite or tidy earlier entries.

## Phantom-sell bug: malformed trade side/type recorded a fake "executed" trade that moved no money

**What the problem was** — `api/routes/trades.py`'s `TradeRequest.side`
and `.order_type` were typed as bare `str`. A non-canonical value like
`"Sell"` (capital S) or any value outside the exact lowercase set
`{"buy", "sell"}` passed FastAPI's request validation (any string is a
valid `str`), built an internal order object, and got recorded as an
"executed" `TradeRecord` in the database — but the actual cash/position
mutation code only matched the exact strings `"buy"`/`"sell"`. A request
with `side: "Sell"` would fall through both mutation branches, touching
no cash and no position, while still writing a `TradeRecord` row
claiming the trade succeeded.

**How it manifested / was noticed** — Found during a read-only audit
(`docs/RESUME_AUDIT.md`) that specifically traced every branch of
`submit_trade`'s mutation logic against every possible value of `side`
reaching that code, rather than only testing the documented/expected
`"buy"`/`"sell"` values — not caught by the existing test suite before
that audit, since every existing test only ever sent exact-lowercase
values.

**How it was diagnosed** — Traced the code path by hand: FastAPI/Pydantic
validates `side: str` against nothing but "is this a string," so any
casing or typo reaches the handler. The mutation code's `if side ==
"buy": ... elif side == "sell": ...` structure has no `else` branch —
anything else silently does nothing, but execution continues past that
point to the `TradeRecord` insert, which has no dependency on which
mutation branch ran.

**How it was fixed** — Retyped `TradeRequest.side` and `.order_type` as
Pydantic `Literal["buy", "sell"]` / `Literal["market", "limit"]`, so
FastAPI rejects any other value with a 422 before the handler body ever
runs — the phantom-trade code path becomes unreachable rather than
patched with an `else` clause. Regression test in
`tests/test_phantom_trade_fix.py` sends a mixed-case `side` and asserts
a 422, plus a well-formed-lowercase test confirming the legitimate path
still executes and moves money. See `docs/DECISIONS.md`'s
"Extract services/trading.py" entry for the related architectural
decision this fix was bundled with (unifying the human and AI trade
paths so this class of bug can't recur independently in two places).

**Lesson / takeaway** — A field typed as `str` when it's really a
closed enum is a validation gap, and the gap is invisible until you
trace every code path for values *outside* the documented set, not just
the ones you expect callers to send. Pydantic `Literal` makes the type
system do this check permanently, for free, at the request boundary —
cheaper than remembering to audit every enum-like `str` field by hand
again.

## The guardrail quantity>0 gap: caught during a manual review after the automated code-review tool mis-scoped its diff

**What the problem was** — `ai/guardrails.py`'s `RiskGuardrail.validate()`
read `quantity = decision.get("quantity", 0) or 0` from the AI's
(Gemini's) JSON decision, with no check that it was positive. A
hallucinated or malformed negative/zero quantity from the LLM would
sail through the position-size check trivially (`quantity * price <= 0`
is never greater than the 20% max-position-size limit) and reach
`execute_validated_trade`, which — as of this same session's Priority C
schema-hardening work — now has a `TradeRecord.quantity > 0`
`CheckConstraint`. The result: an uncaught `IntegrityError` instead of a
clean guardrail rejection, which would have taken down that AI trading
cycle with an unhandled exception rather than a logged, recoverable
"blocked" decision.

**How it manifested / was noticed** — Not caught by an automated tool.
`/code-review high` (a mandatory gate before declaring Phase 2 done) was
run on the branch, but its git-diff scoping had defaulted to a stale
`origin/main` (see the next entry) and returned findings entirely in
`frontend/*.jsx` files outside this session's actual diff or file
ownership. Rather than act on wrong-scope findings, the automated
review's output was disregarded entirely, and a manual line-by-line
correctness pass was done over the actual diff instead — that manual
pass is what found this gap.

**How it was diagnosed** — Traced what happens to a guardrail-approved
decision with `quantity <= 0` end to end: the position-size percentage
check divides `quantity * price` by portfolio value, and a non-positive
numerator can never exceed a positive percentage threshold, so the
`position_size_pct > MAX_POSITION_PCT` check is structurally unable to
reject it. The only other checks (drawdown kill switch, stop-loss
presence, unrecognized-action rejection) don't examine quantity at all.
The path was already unguarded before this session added the
`CheckConstraint` — the constraint just turned a previously-silent
"nothing happens" outcome into a previously-untested crash.

**How it was fixed** — Added an explicit check immediately after
reading `quantity`: `if quantity <= 0: return GuardrailResult(approved=False,
reason=f"Invalid quantity {quantity!r} — must be a positive integer.")`.
Extended `tests/test_guardrails.py` with a case asserting a negative
quantity is rejected with `approved=False`, not left to fail downstream.

**Lesson / takeaway** — When an automated review tool's output looks
implausible (wrong file set, wrong ownership, findings nowhere near the
actual diff), the correct response is to distrust and manually verify,
not to skip verification because the tool "already looked." The tool
running and returning *something* isn't the same as the tool having
actually reviewed the real change — and the bug it would have missed
here was a real, live crash risk, not a style nit. See the next entry
for the root cause of why the tool's scope was wrong in the first
place, and `docs/DECISIONS.md`'s AI-guardrail-hardening context for why
recomputing values instead of trusting the LLM's self-report is the
guiding design principle this bug reinforces.

## The review-tooling stale-origin-HEAD scoping bug

**What the problem was** — Both `/security-review` and `/code-review
high` compute their diff scope against `origin/HEAD` (equivalently,
`origin/main`) by default. In this repository, the local `main` branch
was significantly ahead of the actual `origin/main` on GitHub — a
parallel agent's frontend redesign, docs archiving, and other work had
been committed to local `main` but never pushed to the remote. Both
review tools' auto-computed diff therefore included roughly 70
unrelated files (an entire frontend redesign, docs reorganization) as
if they were part of *this* session's pull request, none of which were
in this session's actual file ownership (`backend/*.py`, `main.py`,
Alembic) or real diff.

**How it manifested / was noticed** — `/security-review`'s underlying
git commands initially failed outright with `fatal: ambiguous argument
'origin/HEAD...'` — the symbolic ref was unset in this checkout. Fixing
that (`git remote set-head origin main`) made the commands run, but the
*file list* the tool then reported was implausible: dozens of
`frontend/src/*.jsx` files and docs, when the actual session diff was
under 40 backend Python files. The mismatch in both file count and file
ownership was the tell that something was wrong with scope, not that
the diff had genuinely grown that large.

**How it was diagnosed** — Compared the tool's computed base against
the actual merge-base of the working branch: `git log --oneline -1
origin/main` vs. `git log --oneline -1 main` showed local `main` had
many commits `origin/main` didn't have. The tool's `origin/HEAD...`
diff was therefore diffing against a stale snapshot of `main`, not the
actual current `main` this branch was built from.

**How it was fixed** — For `/security-review`: recomputed the correct
scope manually via `git diff main...fix/p0-audit-remediation` (using
the real local merge-base, confirmed via `git merge-base`), and
performed the security analysis directly against that correct diff
(19 backend files; no HIGH/MEDIUM findings) rather than trusting the
tool's own file list. For `/code-review high` (which runs as a forked
background execution and returns findings rather than a file list to
sanity-check up front): let it run, then discarded its findings
entirely once they were confirmed to be scoped to the wrong files, and
did a manual correctness pass over the actual diff instead — which is
what found the guardrail quantity bug in the previous entry. This
happened a *second* time later in the Priority E phase and was handled
the same way each time: don't trust an automated diff-scoping tool's
output without first confirming its file list matches the real,
intended diff.

**Lesson / takeaway** — A tool that computes its own scope
automatically can be silently wrong in a multi-branch, multi-agent
repository where the "obvious" remote-tracking reference (`origin/main`)
doesn't match the actual local development base. The fix isn't to trust
the tool less across the board — it's to always sanity-check an
auto-computed diff's file count and file list against
`git diff --stat <known-good-base>...<branch>` before acting on
anything the tool reports, especially in exactly this kind of
environment (this repo, worked on by multiple parallel agents on
different branches, is precisely that environment).

## The Decimal(float) precision trap

**What the problem was** — Constructing a `Decimal` directly from a
`float` — `Decimal(0.1)` — does not produce the decimal value `0.1`. It
produces the exact binary floating-point value closest to 0.1, which is
irrational in base 2 and prints as
`Decimal('0.1000000000000000055511151231257827021181583404541015625')`.
Any money arithmetic built by wrapping incoming floats this way would
inherit float's own representation error while looking, at a glance,
like it had been "fixed" by switching to `Decimal`.

**How it manifested / was noticed** — Not caught by a failing test in
production code — caught proactively while writing the Decimal
migration itself, before committing any of the money-column changes:
this exact behavior was verified directly in a sandbox
(`Decimal(0.1) == Decimal("0.1")` evaluates to `False`) before deciding
how the coercion helper should be written, specifically because this is
a well-known Python gotcha worth checking rather than assuming. A
dedicated test, `tests/test_money_decimal.py`, was written to lock the
correct behavior in and *did* catch one real, separate bug during
development: a `float`/`Decimal` type-mixing `TypeError` in
`api/routes/portfolio.py`/`leaderboard.py`, where a stored `Decimal`
field was being used directly in arithmetic with a live `float` market
quote.

**How it was diagnosed** — Confirmed the float-precision trap directly
in a Python shell before writing any migration code: `Decimal(0.1) !=
Decimal("0.1")` but `Decimal(str(0.1)) == Decimal("0.1")`. This
established the rule *before* writing `to_decimal()`, rather than
discovering the bug after it had already been baked into stored data.

**How it was fixed** — Every coercion from an external
`float`/`int`/`str` into `Decimal` space goes through
`Decimal(str(value))`, never `Decimal(value)` on a float directly. This
was written as a small private `_to_decimal` helper independently in
three files during initial implementation
(`engine/fee_engine.py`, `engine/validator.py`,
`services/trading.py`), then consolidated into one shared
`engine/money.py::to_decimal()` during a later self-directed
code-review pass, once it was clear the same three-line function had
been copy-pasted three times with the exact same docstring.

**Lesson / takeaway** — "Switch to Decimal for money" is necessary but
not sufficient — *how* a `Decimal` gets constructed from external input
matters just as much as using the type at all. A `Decimal` built from a
float, even a "trivial-looking" one like `0.1`, silently reintroduces
the exact class of error the switch was meant to eliminate. This is
exactly the kind of gotcha worth verifying directly rather than trusting
memory or documentation summary — the sandbox check took under a
minute and prevented shipping a Decimal migration that only looked
correct.

## The account usage-limit pause mid-Decimal-migration

**What the problem was** — Partway through the Priority A Decimal
migration (Phase 2), an account-wide claude.ai usage limit paused all
work floor-wide for roughly three hours. The pause landed right after
the `engine/validator.py` Decimal-coercion fix had been written and
verified locally, but *before* it had been committed to git — the
riskiest possible moment for an interruption, since the work existed
only as an uncommitted diff in a live checkout.

**How it manifested / was noticed** — The session simply stopped
mid-task; there was no in-band warning before the pause hit. On resume
(via a dispatch from the hive orchestrator), the first action was
`git status`/`git diff` rather than assuming anything about prior
state, following the general principle of checking real state before
acting on assumed state.

**How it was diagnosed** — `git status`/`git diff` on resume confirmed
the uncommitted validator.py change was still present in the working
tree, untouched — a real git checkout's uncommitted changes persist
across a session pause exactly as they would across any other
interruption (a laptop closing, a network drop). The interruption
itself hadn't caused any data loss; the *risk* had been in how much
verified-but-uncommitted work could have been lost had the pause
coincided with, say, a disk issue or a forced session termination
rather than a clean pause.

**How it was fixed** — No fix was needed for that specific instance —
the work was intact and was committed immediately once the session
resumed. The actual fix was a change in working practice going forward:
commit every logically-complete, test-verified sub-step immediately
once it's green, rather than batching several verified sub-steps before
committing. This was explicit guidance from the hive orchestrator on
resume and was followed consistently for the remainder of the session —
Priority E's five items each landed as their own commit immediately
after their own tests passed, rather than as one large end-of-session
commit.

**Lesson / takeaway** — Uncommitted work in a real git checkout is safe
across an *unplanned pause*, but "safe today" isn't the same as "cheap
to lose nothing from" — the real cost of a pause landing mid-work is
proportional to how much verified-but-uncommitted work exists at that
moment. Committing immediately after each verified sub-step, rather
than batching, converts "the pause was fine, this time" into "the pause
would always be fine, regardless of timing" — a durability property
worth having by default, not just after being burned by a specific
close call.

## Priority E problems: the google.genai eager key-validation cascade, and the settlement.py bug the utcnow migration surfaced

**What the problem was (part 1 — google.genai)** — After migrating
`ai/agent.py` from `google-generativeai` to `google.genai` (see
`docs/DECISIONS.md` for the design rationale), the full test suite went
from 129 passing to 8 failing. Three failures were directly in the
AI-agent tests, expected to need updated mock targets — but two more
failures were in `tests/test_phantom_trade_fix.py` and
`tests/test_readiness_fixes.py`, tests with no AI code anywhere in
their own path, which made the failure look at first like unrelated
flakiness rather than a consequence of the migration.

**How it manifested / was noticed** — `pytest -q` output showed
`ValueError: No API key was provided` on the three direct AI-agent
tests — `genai.Client(api_key="")` raises eagerly at construction,
unlike the old SDK's lenient `configure()`. The two seemingly-unrelated
failures showed different symptoms entirely (a price-fetch error and an
assertion mismatch on an HTTP status code), which is what made them
look disconnected from the API-key issue at first glance.

**How it was diagnosed** — Fixed the direct cause first (see
`docs/DECISIONS.md`'s google.genai entry for the placeholder-key fix)
and reran the full suite before investigating the other two failures
further — they had vanished. The actual mechanism: one of the AI-agent
tests (`test_ai_order_execution.py`) wraps its assertions in
`unittest.mock.patch("engine.validator.datetime")` inside a
`try/finally: p.stop()` block. When the `AIAgent()` constructor raised
inside that `try` block (before Priority E's fix), the mock patch's
teardown timing interacted with pytest-asyncio's per-test event-loop
isolation in a way that left test state dirty for whichever test ran
next in the same session — manifesting as failures in tests that never
touch AI code at all.

**How it was fixed** — Fixing the root `ValueError` (the placeholder-key
fallback) made all five failures disappear together, confirming they
shared one root cause rather than being five independent problems.

**Lesson / takeaway** — When two or more test failures look completely
unrelated to each other and to the change just made, resist the
instinct to treat them as separate pre-existing flakiness — check
whether an earlier test in the same run crashed inside a
`mock.patch`/fixture-teardown block first. One root-cause fix
collapsing five failures at once is a strong signal that they were
never actually five separate problems.

**What the problem was (part 2 — the settlement.py bug)** —
`engine/settlement.py::calculate_settlement_date` already had logic
branching on whether its `trade_date` argument was timezone-aware:
`.astimezone(IST)` if aware, `IST.localize(trade_date)` if naive. Every
live caller, however, was passing a *naive UTC* value
(`datetime.utcnow()`) into that function — which took the naive branch,
and `pytz.timezone.localize()` doesn't convert a naive datetime's
represented instant, it just attaches the given timezone's label to the
wall-clock numbers as-is. A naive UTC wall-clock time of, say, 14:00 was
being treated as if it were already 14:00 *IST* wall-clock time — a
real ~5.5 hour settlement-date error for trades placed near a day
boundary.

**How it manifested / was noticed** — Not caught by any test failure —
`tests/test_settlement.py`'s unit tests all call
`calculate_settlement_date` directly with explicitly-constructed
timezone-aware datetimes (`IST.localize(datetime(2026, 3, 11, 10, 0))`),
which exercises only the already-correct aware branch and never
reaches the buggy naive branch that the live code path (via
`services/trading.py`) actually uses. The bug was found while writing
the naive-UTC-in-DB migration (see `docs/DECISIONS.md`) — reading
`calculate_settlement_date`'s existing branch logic closely, to decide
whether `services/trading.py`'s `datetime.utcnow()` call sites needed
to become aware or stay naive, surfaced that the naive branch's
`IST.localize()` call was doing something different from what the aware
branch's `.astimezone(IST)` call does, for what should be an equivalent
input.

**How it was diagnosed** — Traced through what `pytz`'s `localize()`
actually does versus `astimezone()`: `localize()` interprets its input
as already being in the target zone's wall-clock time and attaches that
zone's offset; `astimezone()` converts the represented instant into the
target zone. A naive UTC datetime passed to `localize(IST)` is
therefore silently mis-converted, while the same instant made aware
first and passed through `.astimezone(IST)` converts correctly.

**How it was fixed** — Changed `services/trading.py`'s two
`settlement_engine.calculate_settlement_date(datetime.utcnow())` calls
to pass a genuinely timezone-aware `datetime.now(timezone.utc)`
instead, which makes `calculate_settlement_date` take the correct
`.astimezone(IST)` branch rather than the buggy `IST.localize()` one —
fixed as a natural side effect of the timezone-convention decision, not
as a separately-scoped bug fix.

**Lesson / takeaway** — Code with an explicit branch for "handle both
aware and naive input" can still have a live bug if every real caller
only ever exercises one branch and the unit tests for that function
only ever exercise the *other* one. Test coverage that looks
comprehensive at the function level (both branches are tested!) can
still miss a real production bug if it doesn't verify which branch the
actual call sites take. This was found by reading code carefully during
an unrelated migration, not by a test catching it — worth remembering
as a case for deliberately tracing "which branch does production
actually take" as its own explicit check, separate from "are both
branches unit-tested."

## Reported a bug that wasn't real, then caught and retracted it before it cost anyone time

**What the problem was** — while demoing the app live (backend + frontend
running together, per a direct request), a single click on OrderPanel's
"Buy 5 RELIANCE" button appeared to fire 8 separate `POST /trades`
requests in a row, draining a fresh account's cash until it ran out and
the backend started correctly rejecting with 400s. I reported this as a
confirmed frontend bug — a real, serious one, since a user unintentionally
buying 8x their intended position is a genuine money-integrity concern.

**How it manifested / was noticed** — I noticed it by reading the
backend's access log after the demo, not by watching it happen in real
time: a burst of `POST /trades 200 OK` / `GET /portfolio 200 OK` pairs,
repeated 8 times, immediately following what I remembered as a single
click action in my own browser-automation batch.

**How it was diagnosed** — Before writing any fix, I read the actual
source of `OrderPanel.jsx`'s `handleSubmit` and `Dashboard.jsx`'s
`handleSubmit` end to end: both are plain, single-shot functions — no
loop, no retry-on-failure logic, nothing that could call itself twice.
Grepping the whole frontend for every `/trades` POST call site turned up
exactly one, in the place I'd already read. Nothing in the source
explained the observed behavior, which was the first sign the original
observation itself might be wrong rather than the code.

I then set up a controlled repro to settle it: a fresh backend and
frontend on fresh ports, a fresh account, `window.alert` neutralized via
injected JavaScript (so a failed trade's error dialog couldn't silently
block further testing — which is exactly what happened on the first
retry attempt: the tab became unresponsive to screenshots with "the page
is busy," which turned out to be nothing more than the app's own
`alert("Market is closed")` firing, since real IST time by then was
outside the 9:15am–3:30pm trading window — a correctly-working guard,
not a bug), and network-request tracking armed *before* each click so
nothing could be missed. A single deliberate click produced **exactly
one** `POST /trades`, every time, tested three separate times including
two clicks in a row producing exactly two requests. No amplification,
under any condition I could construct.

**How it was fixed** — There was nothing to fix, because there was no
bug at this location. I retracted the claim explicitly (a written
correction, not a quiet drop) rather than let an unverified report stand
or have someone else spend time chasing it. The most likely real
explanation: during the original faster-paced live demo, I issued more
click actions across my own batched browser-automation calls than I
tracked carefully in the moment, and attributed the resulting multiple
real trades to what I remembered as a single click.

While investigating, I did find two *different*, genuinely real bugs in
the same component by reading its source directly rather than only
observing behavior: `OrderPanel.jsx` computed its "Cash after" estimate
from a hardcoded `41210` instead of the trader's real cash balance, and
`Dashboard.jsx` fell back to hardcoded demo positions for any
authenticated account with zero real holdings, indistinguishable from
"still loading." Both are real bugs, not design choices, so they belong
here rather than in `docs/DECISIONS.md` — fixed and verified live in
commit `09e6f6f` on `fix/orderpanel-fake-data`.

**Lesson / takeaway** — A finding observed during a fast, interactive
demo is not the same thing as a finding verified under controlled
conditions, even when the log output looks damning. The discipline that
actually matters here isn't "don't make mistakes" — it's noticing the
mistake before it propagates: rereading the relevant source with fresh
eyes before writing a fix, and reproducing under isolated, instrumented
conditions (armed network tracking, neutralized side effects, one action
at a time) rather than trusting a fast-moving demo's log output at face
value. Retracting a wrong claim in writing, as soon as it's known to be
wrong, costs less than letting it stand costs everyone else.
