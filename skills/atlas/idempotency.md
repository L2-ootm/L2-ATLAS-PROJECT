# Skill: idempotency

**Use when:** writing or reviewing anything that can run twice — a webhook
handler, a queue consumer, a ledger or payment write, an actor spawn, a retry
after an ambiguous failure, a button an operator can double-click, a migration,
a sync loop, or any state machine that can be replayed. Also when deciding what
to do after a partial failure, a duplicate delivery, or a timeout with no
answer.

Three separate L2 systems arrived at the same discipline independently — ATLAS
(actor spawns, change reconciliation), Nodex (durable outbox, sequence
authority, fail-closed freshness) and Pattern Forge (idempotency keys, partial
unique indexes, duplicates reported as already-applied). It is written down once
here so the fourth project does not have to rediscover it.

The premise: **an operation that cannot be repeated safely has not been
implemented, only demonstrated.** Every delivery mechanism worth using is
at-least-once. Exactly-once is something the receiver constructs; it is never
something the sender provides.

1. **Name the operation before performing it.** Every effect carries a caller-
   supplied idempotency key derived from *what the caller meant* — the order id,
   the run id, the message id — never from a timestamp, a random value, or a
   hash of a payload that includes one. A retry that generates a new key is not
   a retry, it is a second operation.
2. **Enforce uniqueness in the store, not in the code path.** `SELECT` then
   `INSERT` is not a check; it is a race with a comfortable narrative. Use a
   unique (or partial unique) index and let the write fail. The constraint is
   the only participant that sees both attempts.
3. **A duplicate is a success with a different report.** Return the original
   result and say `already applied`. Not an error — the caller did nothing wrong
   and will retry harder if you tell it otherwise. Not a silent second effect —
   that is the failure this whole discipline exists to prevent. The distinction
   must be visible in the response and in the audit trail.
4. **Commit the intent with the state change; deliver it afterwards.** A durable
   outbox row written in the same transaction as the change is recoverable; a
   network call made inside the transaction is a coin flip about which half
   survives. Deliver from the outbox, retryably, after commit.
5. **One sequence authority.** Ordering derived from local clocks is not
   ordering. If two writers can disagree about what happened first, name the
   component that decides and route every ordering question through it.
6. **Fail closed on untrusted freshness.** If you cannot prove the data you are
   acting on is current, do not act on it as though it were. Stale-but-plausible
   is the input that turns a correct handler into a wrong effect.
7. **Partial failure is the normal case, so build the reconciler now.** Any
   effect spanning more than one store needs something that can be run at any
   time, against any state, and converge — and it must be safe to run when
   nothing is wrong. A reconciler you only dare run during an incident is not
   one.
8. **A retry needs a stopping rule.** Bounded attempts, a backoff, and a
   terminal state that a human can see. Infinite retry is how one bad message
   becomes an outage.
9. **Operator actions are effects too.** A double-clicked button, a re-run
   command and a replayed webhook are the same event. The key belongs to the
   intent, so the second click finds the first click's key.

**After an ambiguous failure, read before you write.** A timeout is not a
failure — it is an absence of information. Check the status of the operation you
already named; only then decide whether anything is left to do. ATLAS's own
actor spawns are idempotency-keyed for exactly this reason: after an unclear
spawn, `status` on the existing id is correct and a second spawn is a defect.

**What to check in review.** Can this run twice — with the same key, and
concurrently? What does the second call return? Is the uniqueness enforced by
the database or by a hopeful `if`? If the process dies between the write and the
notify, what recovers it, and can that recovery itself be run twice? If none of
those has an answer, the change is not finished, whatever the tests say.
