# ULTRAPLAN — Long-horizon mission orchestration

Date: 2026-07-16
Status: implementation-ready

## Outcome

ATLAS chat surfaces gain one execution command with two aliases: `/goal` and
`/mission`. A commanded objective creates one mission containing one or more
auditable runs. After every successful run, a judge records `done` or
`continue`; `continue` allocates the next run under the same mission. A single
worker owns this loop, with a hard run budget and durable pause/failure state.

The Command Center `goals` hierarchy remains a strategic planning model. The
surface aliases target executable `missions`; they do not merge or rewrite the
strategic goal tables.

## Reused foundation

- Hermes `delegate_tool` remains the real subagent implementation.
- ATLAS `subagent_service.ensure_foundation_bridge` remains the audit bridge.
- Hermes goal-judge prompt, strict JSON parsing, fail-open transport behavior,
  parse-failure pause threshold, and continuation semantics are adopted.
- ATLAS SQLite/WAL remains the authority for mission/run/judgement state.
- Existing provider registry and surface-session model identity resolve model
  roles; no second model registry is introduced.

## Model resolution

Judge role precedence:

1. Mission-specific judge model, when supplied by a surface command.
2. Global `functions.judge_model`, when configured in Settings.
3. The initiating surface session's `model_provider` + `model_id`.
4. The active chat provider/model from ATLAS config.

The empty setting is rendered as **Inherit chat session**. An explicit value is
stored in `provider/model` form and validated using the existing model catalog.
The selected effective provider/model is written on every judgement receipt.

Subagents continue to inherit the parent run model unless the delegate call
explicitly selects another model. Curator/compression/title slots remain light
auxiliary roles; the judge is separate because completion decisions must not be
silently moved to a weaker model.

## Durable state

`mission_loops` (one row per long-horizon mission): objective, state, run budget,
runs used, judge override, initiating session, last verdict/reason/run, parse
failure count, timestamps.

`run_judgements` (one immutable receipt per run): verdict, reason, parse status,
effective provider/model, timestamp.

Allowed loop transitions:

`active -> done | paused | exhausted | failed`

Only `active` can allocate another run. Allocation uses a transaction that
checks the prior run, budget, and loop state before returning the mission to
`pending` and starting exactly one next run.

## Worker lifecycle

The detached `atlas run exec` process becomes the sole loop owner for a goal
mission:

1. execute the already-created run;
2. persist normal terminal run evidence;
3. judge the objective against the authoritative final response;
4. persist the judgement receipt and audit event;
5. stop on done, failure, cancellation, pause, or budget exhaustion;
6. atomically allocate and execute the next run on `continue`.

Ordinary chat prompts keep the existing one-mission/one-run path.

## Surface command contract

- `/goal <objective>` and `/mission <objective>` are exact aliases.
- `/goal` or `/mission` shows the current session mission status.
- `pause`, `resume`, and `clear` are reserved subcommands in the shared parser.
- `/goal model inherit|provider/model` controls the session's next mission.
- `/goal budget N` controls the next mission with a bounded safe range.

Both WebUI Chat/Console and the TUI use the same command grammar and gateway
payload. The initial implementation must never send command text as a normal
agent prompt.

## Lean budgets

- No new runtime dependency, queue, framework, or daemon.
- Default maximum: 12 runs per goal; configurable per mission, hard-capped.
- Judge prompt/response are bounded; judge timeout remains bounded.
- One judge call per successful run; failed/cancelled runs do not auto-continue.
- One immutable judgement row and one compact audit event per attempt.
- Existing retention deletion must delete loop/judgement rows with the mission.

## Verification gates

- Unit: model precedence, alias parser, state transitions, budget, parse failures,
  no judgement on failed runs, no duplicate next-run allocation.
- Integration: a fake agent + fake judge produces continue then done, yielding
  two runs under one mission and two receipts.
- Surface: `/goal` and `/mission` create identical payloads; ordinary prompts are
  unchanged; model selector persists inherit/override.
- Regression: agent-runtime, gateway Rust tests, WebUI tests, terminal tests.

