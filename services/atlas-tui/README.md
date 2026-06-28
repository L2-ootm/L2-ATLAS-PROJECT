# atlas-tui — ATLAS terminal workbench (Go/BubbleTea sidecar)

A state-of-the-art terminal workbench for ATLAS, reimplementing opencode/MiMo-Code
terminal patterns in Go + [BubbleTea](https://github.com/charmbracelet/bubbletea).
It is a **thin client of the ATLAS Rust gateway** over HTTP + SSE — the same
contract the cockpit uses. The Rust runtime and Python services stay authoritative
(D-022); this binary only renders and takes input.

## Status

Phase P5 (scaffold + gateway client). Working today:

- Connects to the gateway and renders the **provider mesh** (`/v1/provider/status`,
  `/v1/provider/modes`) — which ways you can wire a model and what's active.
- Lists **missions** (`/v1/missions`).
- **Streams a run live** over SSE (`/v1/runs/{id}/stream`): select a mission, press
  `enter`, and audit events render as they arrive.

Keys: `j`/`k` move · `enter` stream selected mission's latest run · `r` refresh · `q` quit.

## Run

```sh
# point at a running ATLAS gateway (default http://127.0.0.1:8484)
go run . --gateway http://127.0.0.1:8484
# or: ATLAS_GATEWAY_URL=http://127.0.0.1:8484 go run .
```

## Build / test

```sh
go build -o atlas-tui .
go test ./...
```

## Roadmap (P5 → P8)

- P5 (back half): composer + permission pane, viewport scrollback, theming polish.
- P6: full pane set (header/transcript/composer/permission) across terminals.
- P7: in-TUI provider/settings flow with a "test-probe" action (wire any mode, run a probe).
- P8: `atlas tui` launches this binary; retire the Python Rich workbench (10.8-style cutover).

See `docs/plans/2026-06-28-atlas-go-tui-and-provider-mesh-design.md`.
