# atlas-tui — ATLAS terminal workbench (Go/BubbleTea sidecar)

A state-of-the-art terminal workbench for ATLAS, reimplementing opencode/MiMo-Code
terminal patterns in Go + [BubbleTea](https://github.com/charmbracelet/bubbletea).
It is a **thin client of the ATLAS Rust gateway** over HTTP + SSE — the same
contract the cockpit uses. The Rust runtime and Python services stay authoritative
(D-022); this binary only renders and takes input.

## Status

Phase P5 complete (scaffold + gateway client + composer/permissions/scrollback). Working today:

- Connects to the gateway and renders the **provider mesh** (`/v1/provider/status`,
  `/v1/provider/modes`) — which ways you can wire a model and what's active.
- Lists **missions** (`/v1/missions`).
- **Streams a run live** over SSE (`/v1/runs/{id}/stream`) into a scrollback viewport.
- **Composer**: press `n`, type a mission, `ctrl+s` — creates the mission, starts an
  executing run (`/v1/missions`, `/v1/missions/{id}/run` with `execute:true`) and streams it.
- **Permission pane**: polls `/v1/tools/approvals` and lets you `a`pprove / re`x`ject the
  selected pending tool call (the 10.5 surface-scoped broker queue).

### Keys

| Focus | Keys |
|---|---|
| global | `tab` cycle missions/permissions · `n` compose · `p` perms · `m` missions · `r` refresh · `q` quit |
| missions | `j`/`k` move · `enter` stream selected mission's latest run |
| permissions | `j`/`k` move · `a`/`enter` approve · `x` reject |
| composer | `ctrl+s` run · `esc` cancel |

## Run

```sh
# point at a running ATLAS gateway (default http://127.0.0.1:8484)
go run . --gateway http://127.0.0.1:8484
# or: ATLAS_GATEWAY_URL=http://127.0.0.1:8484 go run .
```

### Glyphs on legacy terminals

The TUI uses Unicode glyphs (`●…┃▌»•—`) and falls back to ASCII automatically on legacy
Windows consoles (detected by the absence of `WT_SESSION`). Force either with
`ATLAS_TUI_ASCII=1` or `ATLAS_TUI_UNICODE=1`.

## Build / test

```sh
go build -o atlas-tui .
go test ./...
```

## Roadmap (P6 → P8)

- P6: full pane set (richer transcript: reasoning/tool/diff/retrieval) across terminals.
- P7: in-TUI provider/settings flow with a "test-probe" action (wire any mode, run a probe).
- P8: `atlas tui` launches this binary; retire the Python Rich workbench (10.8-style cutover).

See `docs/plans/2026-06-28-atlas-go-tui-and-provider-mesh-design.md`.
