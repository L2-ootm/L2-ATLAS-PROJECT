# atlas-tui — ATLAS terminal workbench (Go/BubbleTea sidecar)

A state-of-the-art terminal workbench for ATLAS, reimplementing opencode/MiMo-Code
terminal patterns in Go + [BubbleTea](https://github.com/charmbracelet/bubbletea).
It is a **thin client of the ATLAS Rust gateway** over HTTP + SSE — the same
contract the cockpit uses. The Rust runtime and Python services stay authoritative
(D-022); this binary only renders and takes input.

## Status

Phase P8 complete: `atlas` and `atlas tui` now launch this Go sidecar; the Python Rich client is
retained only as hidden `atlas dev-rich-tui` rollback through Phase 10.8. Working today:

- Connects to the gateway and renders the **provider mesh** (`/v1/provider/status`,
  `/v1/provider/modes`) — which ways you can wire a model and what's active.
- Lists **missions** (`/v1/missions`).
- **Streams a run live** over SSE (`/v1/runs/{id}/stream`) into a scrollback viewport.
- Renders assistant text, reasoning, tool calls/results, diffs, retrieval, and failures from the
  append-only audit stream using a display-field allowlist (unknown payload maps stay opaque).
- **Composer**: press `n`, type a mission, `ctrl+s` — creates the mission, starts an
  executing run (`/v1/missions`, `/v1/missions/{id}/run` with `execute:true`) and streams it.
- **Permission pane**: polls `/v1/tools/approvals` and lets you `a`pprove / re`x`ject the
  selected pending tool call (the 10.5 surface-scoped broker queue).
- **Provider settings**: press `s` to edit mode/provider/model/base URL, store an API key through
  the stdin-safe gateway boundary, or import Codex auth. Config writes use optimistic revisions.
- **Provider probe**: `ctrl+t` from settings saves, runs one real mission through the active
  provider, labels the outcome `LIVE`, `MOCK MODE`, or `FAILED`, then archives the probe mission.
  Credential writes are refused when the gateway URL is not loopback.

### Keys

| Focus | Keys |
|---|---|
| global | `tab` cycle missions/permissions · `n` compose · `s` settings · `p` perms · `m` missions · `r` refresh · `q` quit |
| missions | `j`/`k` move · `enter` stream selected mission's latest run |
| permissions | `j`/`k` move · `a`/`enter` approve · `x` reject |
| composer | `ctrl+s` run · `esc` cancel |
| settings | `tab` fields · `left`/`right` mode · `ctrl+s` save · `ctrl+t` save + probe · `esc` close |

## Run

```sh
# installed operator path (default gateway http://127.0.0.1:8484)
atlas
atlas tui --gateway http://127.0.0.1:8484

# source development
go run . --gateway http://127.0.0.1:8484
```

The installers build a stripped binary into `$ATLAS_HOME/bin` (default `~/.atlas/bin`). Resolution
order is `ATLAS_TUI_BIN`, ATLAS-owned bin, source-checkout build output, then `PATH`.

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
- P8: complete — launcher/installer cutover, source/PATH fallback, and hidden Rich rollback.
- Phase 10.8 owns the evidence-based final retirement decision for that rollback.

See `docs/plans/2026-06-28-atlas-go-tui-and-provider-mesh-design.md`.
