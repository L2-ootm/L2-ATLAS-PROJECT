# Attribution — atlas-tui

This terminal workbench **reimplements patterns** from prior-art terminal agents.
No donor runtime, configuration, auth, identity, or source code is imported or
vendored — only UX/architecture patterns were studied (per the v1.1/v1.2
"adapters only" constraint and the Phase 10.1 intake regime).

## Pattern references (design history only)

- **opencode** — Go + Charm/BubbleTea terminal UI architecture (thin client over an
  HTTP/SSE server). Studied for component structure and the client-server split.
- **XiaomiMiMo/MiMo-Code** (v0.1.2, MIT; TypeScript/Bun fork of opencode) — studied
  for terminal interaction/behavior patterns. Reference checkout is gitignored under
  `_EXTERNAL_REPOS/mimo-code/`. Note: MiMo-Code carries a `USE_RESTRICTIONS.md`
  beyond MIT; only patterns (not code) are reused here.

## Direct dependencies (their own licenses apply)

- github.com/charmbracelet/bubbletea (MIT)
- github.com/charmbracelet/lipgloss (MIT)

ATLAS identity, the gateway contract, the provider mesh, and all rendered copy are
ATLAS-native. See `ATTRIBUTION.md` at the repo root for the project-wide notices.
