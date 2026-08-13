# Admissions

The college application campaign — deadlines, materials, activities and the
package review — reachable from ATLAS without ATLAS owning any of it.

Ships **inactive**, like every bundled module. `atlas module activate admissions`
turns it on; the MCP server stays disabled separately until you point it at a
real endpoint and issue a credential.

## What makes this one different

Every other module keeps its records in `module_records`. This one declares
**no collections at all**. Pattern Forge owns the application record: it has the
surface the applicant actually works in, the accounts, and row-level security.
ATLAS reads it over the API with a scoped service key and writes back only what
it was asked to change.

That is the point of the design rather than a limitation of it. Copying colleges
and deadlines into ATLAS would create a second live writer for the same fact —
the mechanism that produced two canonical documents disagreeing about a single
SAT score, and a scheduled day to reconcile them. A test asserts the absence of
collections, because it is the property the whole integration rests on.

This is also the shape every future integration with an external product should
take: doctrine and workflows here, records where the product that owns them
already is.

## Wiring it up

1. Pattern Forge exposes `GET /api/application` and
   `GET /api/application/validate`. Both require a signed-in learner today.
2. Issue a service credential. `apiKeys.kind` in that project already carries a
   `service` variant, written for exactly this before there was anything to
   connect.
3. Set `PATTERNFORGE_SERVICE_KEY`, point the `pattern-forge-application` MCP
   entry at the deployment, and enable it. The manifest requires `${VAR}`
   references and rejects a literal-looking credential at sync time.

Until step 3, the module is doctrine and workflows only — useful on its own,
since the rules it carries are the ones that were being re-derived by hand every
session.

## Why the validator matters more than it looks

`package_check` calls Pattern Forge's validator instead of recomputing anything.
Two reasons.

The plain one: a character count computed inside a run is a second definition of
the same thing, and the two disagree the first time one of them handles trailing
whitespace differently.

The load-bearing one: ATLAS's verification gate classifies a run that changed
state and never checked it as `unverified`, which now costs that run an enforced
extra turn. A run editing the application record has nothing to spend that turn
on unless a real command exists that re-reads what it wrote and asserts the
invariants. The validator is that command. **Any new write path into this record
needs a matching check, or the gate has nothing to credit and every admissions
run lands `unverified`.**

## Commands

| Command | What it does |
|---|---|
| `/app-status` | deadlines, blockers and the package check in one read |
| `/deadline-sweep` | what is due in the next fortnight, and what is stuck behind something |
| `/package-check` | run the validator, report what it found, add nothing |

## Doctrine

| File | Injected | Carries |
|---|---|---|
| `context/doctrine.md` | always | the record lives elsewhere; the real deadline is the internal review gate, not the published one; never write the essay; no chancing; provenance on every college fact |
| `context/limits.md` | always | limits are data with a verification date, not memory; where a limit binds; the restrictive-plan rule |
| `context/essays.md` | matched | how to review a draft without writing it |
| `context/list.md` | matched | the two facts that shape an international applicant's list, and how to cull |

Each has a delivery test in `test_module_service.py`. A doctrine file with no
delivery test rots silently — it stays on disk, reads well, and reaches no run.
