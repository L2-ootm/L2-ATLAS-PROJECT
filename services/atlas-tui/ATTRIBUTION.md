# Attribution — atlas-tui

This terminal workbench is an ATLAS Go/BubbleTea client whose presentation layer
is derived from permissively licensed terminal agents. MiMo-Code is MIT
licensed; its required copyright and permission notice is preserved in
`docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`.

## Presentation donors

- **opencode** — Go + Charm/BubbleTea terminal UI architecture (thin client over an
  HTTP/SSE server). Studied for component structure and the client-server split.
- **XiaomiMiMo/MiMo-Code** (v0.1.2, MIT; TypeScript/Bun fork of opencode) —
  presentation donor for the home/session composition, 50 ms motion clock,
  star/meteor cadence, breathing gradient, compact composer, and autocomplete
  geometry. The implementation is ported to the existing Go ATLAS client rather
  than importing MiMo-Code's Bun/Solid/OpenTUI runtime and dependency graph.

No donor agent runtime, provider layer, authentication, configuration, storage,
memory, telemetry, updater, hosted-service authority, or product identity is
shipped in this binary.

## Direct dependencies (their own licenses apply)

- github.com/charmbracelet/bubbletea (MIT)
- github.com/charmbracelet/lipgloss (MIT)

ATLAS identity, gateway contract, provider mesh, and rendered product copy remain
ATLAS-owned. See `ATTRIBUTION.md` at the repo root for project-wide notices.
