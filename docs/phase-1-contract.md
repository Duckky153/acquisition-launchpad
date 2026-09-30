# Phase 1 product contract

## Outcome

Phase 1 answers one operational question with evidence: **is each acquired entity's opening
finance data prepared well enough to enter a controlled onboarding sequence?** It does not claim
that the entity is fully migrated, integrated, eliminated, closed, or production-ready.

## Versioned intake

`POST /v1/packages` accepts schema version `1.0` and requires `Idempotency-Key`.

- Replaying the same key and same canonical payload returns the original package.
- Reusing the key for different content returns `409 CONFLICT`.
- Reusing an external key and package version for different content also returns `409`.
- A new content revision must increment `package_version`.
- Entity IDs, account codes, hierarchy references, balance references, and mapping references are
  validated as a single unit before persistent state is accepted.

The checked-in Horizon fixture is deliberately labeled synthetic. Amounts are integer cents,
not binary floating-point values.

## Human mapping boundary

Suggestions are evidence for a decision, never the decision itself. Confidence can be produced
by a deterministic rule, an AI model, or a human analyst, but every suggestion enters as
`SUGGESTED`. Only the explicit approve endpoint records `APPROVED`, the human actor, decision
note, timestamp, and audit event. Approving one target displaces any previously approved target
for that source account. Broad source and canonical account types must match before approval.
Optimistic versions prevent a stale screen from silently overwriting a newer decision, while a
source-account row lock and partial unique index prevent concurrent double approval.

For demonstration ergonomics, the local seed script replays 17 fictional historical decisions via
that same explicit approve endpoint and labels them with `synthetic-demo-preparer`. This is seeded
demo history, not an automated application feature or a claim about a real reviewer. It
deliberately leaves HZ-115 suggested so the demonstrator performs the only live decision.

## Exact readiness gate

An entity receives `DATA_PREPARATION_READY` only when all six checks pass:

1. `HIERARCHY_VALIDATED` — all parents exist and the hierarchy is acyclic.
2. `SOURCE_ACCOUNTS_PRESENT` — the entity has at least one imported source account.
3. `OPENING_BALANCES_COMPLETE` — every source account has exactly one opening balance.
4. `TRIAL_BALANCE_TIED` — integer-cent debits equal credits exactly.
5. `ACCOUNT_MAPPINGS_APPROVED` — every source account has a human-approved target.
6. `NO_BLOCKING_BLOCKERS` — no open package-level or entity-level blocking exception remains.

The package becomes ready only when every entity is ready. There is no confidence override,
rounding tolerance, hidden admin switch, or AI approval path.

System blockers mirror failing deterministic conditions and resolve only when the underlying
condition passes. Human-created blockers require a human resolution note. Both transitions are
audited.

## Dependency sequence

Every entity has five steps: intake, map accounts, tie out, resolve blockers, and data-preparation
ready. Dependencies enforce ordering. Child intake depends on parent intake; child mapping also
depends on parent mapping. A topological sort rejects missing or cyclic dependencies. Each
generated plan is immutable, versioned, input-hashed, and audited.

## Demonstration workflow

1. Run `make demo-up`; the seed creates 17 fictional historical decisions and leaves HZ-115 open.
2. Show that all three trial balances tie while one source-derived blocker keeps readiness
   `NOT_READY`.
3. Follow the in-product guide to HZ-115, inspect its rationale, and approve it as a human.
4. Show `DATA_PREPARATION_READY`, zero open blockers, 15 complete sequence steps, and verified audit
   evidence.
5. Refresh to prove persistence. Use `make demo-reset` only when intentionally restoring the exact
   one-decision-left demonstration.

## Explicit non-claims

Phase 1 does not implement intercompany eliminations, live ERP/API synchronization, first-close
simulation, or a full migration audit packet. It does not contain production authentication,
private customer data, legal advice, or a customer result. The project remains **In Progress**.
