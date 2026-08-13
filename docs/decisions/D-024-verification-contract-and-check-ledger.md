# D-024 — The Operator Declares What "Done" Means; ATLAS Remembers What Can Check It

**Date:** 2026-08-13
**Status:** Accepted
**Refines:** D-002 (audit-first runtime)
**Evidence:** `docs/research/2026-08-13-upstream-harnesses-and-contribution-surface.md` §3.1

## Context

The verification gate (shipped 2026-08-13) classifies every terminal run against
its own audit trail: `no_mutations`, `verified`, `contradicted`, `unverified`,
with an enforced check turn when a run changed state and never checked it. It
works, and measuring it against hermes-agent v0.18.0 — which built the same
thing independently in the same window — exposed three gaps that are structural
rather than incidental:

1. **The gate infers what "done" should have meant.** It has no statement from
   the operator to compare against, so "a check ran" is the whole standard. A
   project where done means tests *and* a typecheck cannot say so.
2. **Nothing survives the run.** The trail records that a run ran `pytest`; it
   does not record that this project *has* a suite. A later run — and the
   enforced check turn itself — starts from zero and can only say "run a real
   check", which is advice the agent cannot act on.
3. **The gate applies uniformly to changes that carry no executable check.** A
   run that edits a README is `unverified` and is charged a turn demanding a
   test that cannot exist. Hermes hit this and exempted doc-only edits.

The upstream repo is 12,412 commits ahead of ATLAS's vendored pin. Re-vendoring
to acquire these is a migration, not a maintenance task.

## Decision

1. **Port the shapes, not the code.** Three ideas are adopted from hermes-agent
   v0.18.0's completion contracts and verification evidence ledger. No upstream
   code is copied and ATLAS keeps its own verdict vocabulary.
2. **A workspace may declare a verification contract** at
   `.atlas/verification.json`: `{"required": ["tests", "lint"]}`. The gate
   compares what passed against what was declared. Meeting part of a contract is
   `unverified` with the remainder named — not `contradicted`, which is reserved
   for a run whose checks actually failed.
3. **Declaring nothing changes nothing.** A project with no contract is judged
   exactly as before. A gate that silently raised its own bar would fail runs
   that met the standard they were held to, which is the same unverified
   self-modification the gate exists to catch.
4. **A contract may only require checks the gate can observe** (`tests`,
   `typecheck`, `lint`, `build`, `exercised`). An unknown kind is dropped with a
   warning rather than made permanently unsatisfiable.
5. **`verification_checks` (migration 0036) is the durable ledger** of the
   checks a workspace has: `source='detected'` from marker files
   (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `tsconfig.json`,
   `Makefile`), `source='observed'` from commands runs actually executed and the
   gate classified. Detection never downgrades an observation.
6. **The ledger is keyed by workspace root, not project id.** A run reaches a
   root through its surface session long before anyone registers a project, and
   the checks belong to the directory either way.
7. **The enforced check turn names this project's own checks**, drawn from the
   ledger, and states the contract shortfall when there is one. An instruction
   the agent cannot act on becomes an offer it can.
8. **Documentation-only runs are `exempt`, a fifth verdict.** Prose has no
   executable check; demanding one teaches agents that the checkpoint is noise.
   Configuration (`.json`, `.toml`, `.yaml`) is *not* documentation. Version
   control commands do not by themselves deny the exemption — what needs
   checking is what was committed, and the other mutations already say what that
   was. `exempt` renders no operator badge, like `no_mutations`.
9. **Everything here stays fail-open.** An unreadable contract, an unwritable
   ledger or an unresolvable workspace degrades to today's behaviour. This is a
   reporting layer; a bug in it must never change whether a run completes.

## Consequences

- The L1 prompt gains one clause (the contract), and `loop-discipline.md` gains
  the full five-verdict table plus the ledger. Prompt goldens and the frozen
  cache-prefix hashes were regenerated in all three fixture locations.
- Runs in a project with a contract can now be `unverified` for a second,
  more specific reason. `describe()` and `summarize()` name the missing kind, so
  the compounding-loop observation the next run inherits is actionable.
- The ledger accumulates silently and is currently read by one consumer (the
  check-turn hint). An operator-facing view of it is deliberately deferred until
  there is enough data to be worth reading.
- **Not adopted:** hermes's surface-aware gating of verify-on-stop for messaging
  surfaces. ATLAS has no run-level messaging surface marker today — surface
  kinds are `cli|tui|webui|api|native|test` and the Discord sidecar does not
  create surface sessions — so the exemption would be code that never fires.
  Revisit when a messaging surface records a session.
