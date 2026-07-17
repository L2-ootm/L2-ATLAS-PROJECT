# Mission and chat execution semantics

## Decision

ATLAS will distinguish the operator-facing Mission concept from the internal
execution record required by the current runtime. `missions.record_kind` is the
compatibility boundary:

- `mission`: an explicit Command Center, Missions page, or goal-operation launch;
- `chat`: an ordinary Chat/Console prompt;
- `system`: a synthetic runtime/audit anchor such as the operator sentinel.

The Missions API lists only `mission` records. Detail and run APIs retain access
by id, so existing audit links and execution history remain valid. The runtime's
non-null `runs.mission_id` foreign key stays unchanged.

## Alternatives considered

1. Make `runs.mission_id` nullable and add a second execution parent. This is the
   cleanest eventual schema, but it touches execution, audit, cancellation,
   retention, actor lifecycle, and every consumer at once.
2. Filter prompt-shaped rows only in the WebUI. This hides the symptom while the
   gateway, TUI, project detail, counts, and future clients still report false
   Missions.
3. Classify execution records at the shared persistence/API boundary. This is the
   selected vertical slice: small migration, explicit semantics, no lost history,
   and all clients receive the same Mission view.

## Data flow

Ordinary Chat and Console submissions call the execution-record API with
`record_kind=chat`, then start the resulting run exactly as today. Explicit
Command Center and Missions launches omit the field and therefore default to
`mission`. Synthetic operator rows are written as `system`.

Migration 0024 safely classifies the existing operator sentinel as `system` and
records attached to a surface session as `chat`. Command Center launches are not
surface-attached, so they remain `mission`. No rows or run history are deleted.

## Verification

Service tests cover creation, persistence, validation, and Mission-list
filtering. Gateway tests prove chat records are excluded from `/v1/missions` and
the requested kind is forwarded to the CLI. WebUI tests prove ordinary prompts
request `chat` while Command Center creation remains a Mission. Full migration,
runtime, gateway, and WebUI suites remain the release gate.
