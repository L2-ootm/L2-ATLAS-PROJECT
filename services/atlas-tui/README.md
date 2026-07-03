# atlas-tui — ATLAS terminal workbench (Go/BubbleTea sidecar)

A state-of-the-art terminal workbench for ATLAS, with a Go +
[BubbleTea](https://github.com/charmbracelet/bubbletea) presentation layer
derived from the MIT-licensed opencode/MiMo-Code family.
It is a **thin client of the ATLAS Rust gateway** over HTTP + SSE — the same
contract the cockpit uses. The Rust runtime and Python services stay authoritative
(D-022); this binary only renders and takes input.

## Status

The 2026-07-01 operator UAT correction replaced the dashboard-first prototype with a chat-first
agent surface. `atlas` and `atlas tui` launch this Go sidecar. Working today:

- Opens with the composer focused. Type immediately and press `enter`; no compose mode or mission
  shortcut is required.
- Keeps one visible conversation over the owning surface session. Internal mission/run records
  remain audit mechanics rather than primary navigation.
- **Streams each agent turn live** over SSE (`/v1/runs/{id}/stream`) into the transcript.
- Renders assistant text, reasoning, tool calls/results, diffs, retrieval, and failures from the
  append-only audit stream using a display-field allowlist (unknown payload maps stay opaque).
- Refuses implicit mock conversations. An unavailable provider produces an onboarding state and
  preserves the draft; mock execution requires `ATLAS_TUI_ALLOW_MOCK=1`.
- Polls only `/v1/surface-sessions/{id}/approvals` with the owner token. A pending decision keeps
  transcript context visible and offers once/session/durable/deny choices.
- Maps Claude Code auth mode to the `claude_code` runtime; other provider modes use the native
  runtime/provider mesh.
- **Provider settings**: press `ctrl+p` to edit mode/provider/model/base URL, store an API key through
  the stdin-safe gateway boundary, or import Codex auth. Config writes use optimistic revisions.
- **Provider probe**: `ctrl+t` from settings saves, runs one real mission through the active
  provider, labels the outcome `LIVE`, `MOCK MODE`, or `FAILED`, then archives the probe mission.
  Credential writes are refused when the gateway URL is not loopback.
- Shows provider/session/workspace/policy/approval context in an optional wide-terminal sidebar;
  missions and operational controls are available through slash commands.

### Keys

| Surface | Keys |
|---|---|
| conversation | `enter` submit · `alt+enter` newline · `ctrl+p` settings · `ctrl+o` context · `ctrl+c` cancel/exit |
| commands | `/settings` · `/mode` · `/history` · `/permissions` · `/sidebar` · `/new` · `/quit` |
| approval | arrows or `j`/`k` · number/`enter` select · `esc` deny |
| settings | `tab` fields · left/right mode · `ctrl+s` save · `ctrl+t` save + probe · `esc` conversation |

## Run

```sh
# installed operator path (default gateway http://127.0.0.1:8484)
atlas
atlas tui --gateway http://127.0.0.1:8484

# source development
go run . --gateway http://127.0.0.1:8484
```

The installers build a stripped binary into `$ATLAS_HOME/bin` (default `~/.atlas/bin`). Resolution
order is `ATLAS_TUI_BIN`, ATLAS-owned bin, source checkout, then `PATH`. In a source checkout the
launcher compares the executable timestamp with Go sources and rebuilds a missing/stale binary
before launch. `atlas-tui --version` prints the embedded build identity.

### Glyphs on legacy terminals

The TUI uses Unicode glyphs (`●…┃▌»•—`) and falls back to ASCII automatically on legacy
Windows consoles (detected by the absence of `WT_SESSION`). Force either with
`ATLAS_TUI_ASCII=1` or `ATLAS_TUI_UNICODE=1`.

## Build / test

```sh
go build -o atlas-tui .
go test ./...
go vet ./...
```

P8 Windows/amd64 stripped baseline (2026-06-28): 8,198,144 bytes / 7.82 MiB, within the locked
15 MiB ceiling. A cold Python-launcher smoke observed the Go process in 839 ms; after settling,
Python + Go working set was 63.17 MiB (47.89 + 15.28 MiB). No dependency was added.

## Roadmap

- P6: complete — rich transcript + 80x24/140x40 ASCII/Unicode render tests.
- P7: complete — typed config/model/auth client, four-mode settings, optimistic save, and
  live/mock/failure probe with automatic cleanup.
- P8: complete — launcher/installer cutover and source/PATH fallback.
- 2026-07-01 correction: chat-first shell, explicit readiness, visible conversation, contextual
  approvals/sidebar, cancellation-first Ctrl-C, and resolved-artifact integrity.
- Phase 10.8 owns broader cross-surface UAT and cutover evidence.

See `docs/plans/2026-06-28-atlas-go-tui-and-provider-mesh-design.md`.
