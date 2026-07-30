# ATLAS v1.1 Operator UAT

## Scope and safety

Run this on the dated target Windows environment in a real interactive terminal. Do not record
provider credentials, prompts containing personal data, or raw model transcripts. Capture only
the redacted IDs, terminal output, screenshots, and diagnostic paths named below.

Before beginning, keep the candidate and fallback terminals available:

```powershell
Set-Location C:\Users\Davi\Desktop\Projects\L2-ATLAS-PROJECT\services\agent-runtime
python -m atlas_runtime.cli.main doctor --json
python -m atlas_runtime.cli.main terminal status --json
python -m atlas_runtime.cli.main models list --all
```

Expected: `doctor` reports the loopback services and selected provider state without a secret;
`terminal status` reports the atlas-terminal checkout, build state, version, and gateway reachability.
If either health probe fails, stop UAT, preserve its redacted output in the UAT record, and select
`defer` or `no-go`; do not attempt cutover.

## 1. Existing release evidence and configuration

1. Open `.planning/phases/10.8-cross-surface-conformance-uat-cutover/10.8-RUN-EVIDENCE.md`.
   Confirm `aggregate.successful` is 20, all CLI/WebUI/TUI cohort counts meet their minimums,
   `rubric.score` is 10, `rubric.passed` is true, and `failed_gates` is empty. Record the
   threshold hash and report timestamp in the UAT record.
2. Run `python -m atlas_runtime.cli.main config show` and
   `python -m atlas_runtime.cli.main models list --all`. Confirm config, auth, and model state are
   visible with secrets masked. For the selected real provider, run
   `python -m atlas_runtime.cli.main auth status <provider-id>` and record only its masked status.
3. Start one global session from the target terminal (`atlas` or
   `python -m atlas_runtime.cli.main tui`) and one project-scoped session from a registered project
   directory. In each, send a harmless prompt that requests the active workspace and a concise
   explanation of the available context. Record each redacted surface/session/run receipt.

Expected: sessions are distinct, preserve their scopes, and no raw credential is displayed.

## 2. Real provider, Brain/wiki, and provenance

1. In the selected real-provider session, submit a harmless task that requires one Brain/wiki lookup,
   such as "Summarize the ATLAS project objective and identify the source used." Do not use private
   notes or customer data.
2. Confirm that the response distinguishes retrieved material from its own conclusion and exposes
   provenance or an explicit abstention. Open the corresponding audit/evidence receipt and capture
   its opaque ID, availability state, and any redaction/partial marker.
3. In Cockpit, inspect the same run's actor/evidence history. Confirm the actor, surface, run, and
   parent/child references agree with the terminal receipt; this is the attribution check. For a large diff artifact, use the
   Evidence Inspector's bounded preview and authorized export; confirm paging/range behavior and
   explicit unavailable, binary, partial, or redacted labels where applicable.

Expected: provenance is present or retrieval abstains explicitly; evidence review never injects a
full large diff into the list/SSE view, and exports require the owner-authorized route.

## 3. Permission, cancellation, recovery, and resume

1. Trigger a harmless policy-gated action in a session that owns the request. Confirm only the
   initiating surface renders the actionable approval and that the four scope choices are available.
   Choose a safe outcome (deny is acceptable) and confirm a durable audit receipt.
2. Start a cancellable real task, then press `Ctrl+C` while it is active. Confirm cancellation is
   requested for that owning surface, the result is not rendered as success, and the session reaches
   a terminal state without an orphan worker.
3. Start a new harmless run, stop the loopback gateway deliberately with the standard local control,
   then restart it:

   ```powershell
   python -m atlas_runtime.cli.main gateway stop
   python -m atlas_runtime.cli.main gateway start
   python -m atlas_runtime.cli.main doctor --json
   ```

   Reconnect the original surface and resume or inspect the conversation. Record the redacted
   recovery receipt and verify no pending approval became visible on a non-owning surface.

Expected: permission ownership remains surface-scoped; cancellation, gateway loss, and reconnect
produce explicit lifecycle states and auditable receipts rather than a false success.

## 4. atlas-terminal F12 diagnostic capture gate

1. Record the diagnostic file path before testing:

   ```powershell
   $diag = Join-Path ([System.IO.Path]::GetTempPath()) 'atlas-terminal-diagnostics.log'
   if (Test-Path $diag) { Get-Content $diag -Tail 20 }
   ```

2. From a target session, exercise a deliberately invalid or unavailable session-create path that
   is safe for the environment (for example, point only that temporary test launch at an unused
   loopback port), then return to the healthy gateway. Do not alter provider credentials.
3. Confirm the TUI shows actionable remediation and that `$diag` receives a new redacted
   `ATLAS_SESSION_CREATE_ERROR`, `ATLAS_GATEWAY_ERROR`, or `ATLAS_ADAPTER_ERROR` line with method,
   path, and failure classification but no bearer token, API key, prompt body, or response body.
4. Relaunch against the healthy loopback gateway and create a session successfully. Record the
   diagnostic line timestamp and successful redacted session receipt.

Expected: F12 failure capture is durable and secret-safe, and recovery works without clearing or
hand-editing the diagnostic log.

## 5. Go TUI corrective checklist

Launch the retained fallback only with `python -m atlas_runtime.cli.main dev-go-tui --gateway
http://127.0.0.1:8484`. Do not set `ATLAS_TUI_ALLOW_MOCK` for this production UAT.

1. At launch, type immediately; confirm the composer is focused and `Enter` submits while
   `Alt+Enter` adds a line.
2. With an unavailable API-key profile, confirm provider onboarding preserves the draft and offers
   API key, Codex OAuth, Claude Code, and reported provider modes; select and save a real provider.
3. Submit a real prompt, observe a streamed response, then submit a second turn. Confirm one visible
   transcript and the same surface identity are retained.
4. Resize the terminal narrow and wide; repeat under its normal glyph mode and one explicit
   `ATLAS_TUI_ASCII=1` or `ATLAS_TUI_UNICODE=1` launch. Confirm the information hierarchy remains
   usable.
5. Trigger a harmless owned approval. Confirm contextual transcript remains visible, all four scope
   choices work, and a non-owning surface cannot resolve it.
6. During active work press `Ctrl+C`; confirm it requests cancellation. When idle press `Ctrl+C` and
   confirm the application exits.
7. Interrupt and restore the gateway as in section 3, then confirm reconnect/resume preserves the
   transcript/session relationship.
8. Verify artifact integrity:

   ```powershell
   python -m atlas_runtime.cli.main dev-go-tui --gateway http://127.0.0.1:8484
   # In a second terminal, after launch/rebuild:
   & ..\atlas-tui\atlas-tui.exe --version
   ```

   Record the version/build identity and confirm the resolved executable is current. If the binary
   is rebuilt, repeat its `--version` probe after the build.

Expected: all eight checks pass in Windows Terminal with a real provider; a redirected-stdin run is
not UAT evidence.

## Failure capture and decision rule

For every failure, record: time, surface, redacted session/run/evidence IDs, command or UI step,
expected versus observed state, diagnostic-file path, and whether recovery succeeded. Never paste
secrets or transcripts into the UAT record.

Proceed to the rollback rehearsal only when every required check passes. Any failed hard gate,
unapproved mutation, secret disclosure, false terminal state, silent evidence truncation, or orphan
worker is an immediate `no-go`. Missing operator time or incomplete evidence is `defer`.
