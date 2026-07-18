# GSD/L2 · progress — situational awareness, then a route

Use at session start, after an interruption, or whenever the next step is
unclear. Progress never does the work — it reports and routes.

## Procedure

1. **Read the truth**: STATE.md, ROADMAP.md, the active phase directory, and
   `git status`/`git log` since the last recorded position. When they
   disagree, the repo wins and STATE.md gets corrected first.
2. **Report** (compact):
   - milestone + phase position, percent from real counts;
   - last verified work (with its evidence tier);
   - uncommitted/unpushed state, exactly as git reports it;
   - owed UAT and open blockers.
3. **Route** to exactly one next step:
   - no `.planning/` → `init.md`
   - phase without CONTEXT.md and with gray areas → `discuss.md`
   - phase without PLAN.md → `plan.md`
   - plan with unchecked tasks → `execute.md`
   - executed but unverified → `verify.md`
   - verified milestone-final phase → `ship.md`
   - anything failing → `debug.md`
4. State the route and why in one line; wait for the operator only when the
   route itself is a judgment call.

## Integrity checks (run when something feels off)

- STATE.md position exists in ROADMAP.md.
- Phase directories match ROADMAP numbering (no orphans).
- SUMMARY.md commit hashes exist in `git log`.
- File counts in handoff/state match `git status --short -uall`.
- No phase is both "complete" and holding unchecked plan tasks.
