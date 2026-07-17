# Ultra simulation — long-horizon mission orchestration

Date: 2026-07-16
Verdict: GO with controls below

## Scenario matrix

| Scenario | Expected behavior | Required control |
|---|---|---|
| Judge says done | Mission loop becomes done; no new run | Unique judgement per run |
| Judge says continue | Exactly one next run under same mission | Transactional allocation + one worker owner |
| Judge transport fails | Continue without wedging, bounded by run budget | Fail-open receipt + budget |
| Judge emits invalid JSON repeatedly | Pause after three consecutive parse failures | Persist parse-failure counter |
| Agent run fails/cancels | Stop loop; never auto-retry destructive work | Judge successful runs only |
| Worker crashes after verdict | Durable state explains last decision; resume is explicit | Receipt committed before allocation |
| Worker crashes after allocation | New run is visible and resumable; no duplicate allocation | Prior-run/next-run linkage and state guard |
| Two resume requests race | At most one running run exists for mission | Locked transaction checks active run |
| Session model changes mid-mission | Explicit override is stable; inherit resolves from initiating session | Persist session id and effective receipt model |
| Surface disconnects | Worker continues; Runs page remains authoritative | No UI-owned orchestration |
| User sends ordinary chat prompt | Existing one-run behavior remains | Goal mode is explicit only |
| Retention purge executes | Policy and receipts are removed with mission evidence | Extend purge ordering |

## Pre-mortem

Most likely failure: continuation is spawned independently by WebUI, TUI, and
runtime, producing duplicate runs. Mitigation: surfaces only request/configure;
the detached runtime worker is the sole continuation owner.

Second failure: the judge silently uses the light auxiliary model despite the
operator expecting session inheritance. Mitigation: a dedicated judge slot and
an immutable receipt containing the effective provider/model.

Third failure: a failed tool run is judged from a polished error summary and
incorrectly marked done. Mitigation: only successful runs are judge-eligible;
failed and cancelled attempts stop the loop.

## Go/no-go checks

- GO only with a hard run budget.
- GO only if judgement and next-run allocation are durable and idempotent.
- GO only if normal prompts remain outside the loop.
- NO-GO for any design where browser/TUI reconnect behavior owns progress.

