# ATLAS Module & Plugin Framework

Date: 2026-07-16
Status: implementation contract (slice 1 implemented this session)

## Outcome

ATLAS is modular for operators and self-extensible by the agent:

1. **Deactivatable modules** — every optional capability (bundled or
   user-created) is a module the operator can enable/disable without touching
   source.
2. **User-created modules** — ATLAS builds modules for itself using the ATLAS
   skill pack. A module can contribute WebUI pages (schema-driven, visually
   constrained), slash commands (propagate to WebUI palette/slash AND the
   terminal automatically), and later tools and sidecar processes.
3. **Self-wiring** — the agent scaffolds, installs, and enables modules
   through the same CLI the operator uses (`atlas module create/sync/enable`),
   so "build me a voice module" ends with the module live in the running
   product.
4. **Plugin direction** — the manifest is deliberately compatible with a
   future plugin store: id/version/author/description + declared
   capabilities, no arbitrary code in v1.

## Design decisions

- **Manifest, not code.** A module is a directory with `module.yaml`. v1
  capabilities are declarative: `commands` (name/description/template) and
  `pages` (a constrained block schema). No module JS executes in the WebUI —
  pages render through ATLAS-owned components, which is what guarantees the
  visual constraints. Executable capabilities (tools, sidecars) come later
  through the existing tool-manifest and sidecar-control patterns.
- **Discovery in Python, serving from SQLite.** `module_service.sync` scans
  `<repo>/modules/*/module.yaml` (bundled) and `<ATLAS home>/modules/*/module.yaml`
  (user-installed) and upserts into the `modules` table (manifest JSON
  included). The Rust gateway serves `/v1/modules` and `/v1/commands`
  straight from the DB — no YAML in Rust, no file access races.
- **Enable state is data.** `modules.enabled` in SQLite; toggling requires no
  restart for command/page consumers (they poll/refetch). Missing-on-disk
  modules are flagged, not deleted (state survives a temporarily unmounted
  drive).
- **One command catalog.** The six built-in slash commands stay in the two
  existing TS files (unchanged contract); module commands ride
  `/v1/commands` and are merged by the WebUI palette/slash surfaces and the
  terminal adapter. A collision with a built-in name is ignored (built-ins
  win) and reported in the module list.

## Module manifest (v1)

```yaml
id: voice-notes            # [a-z0-9-], unique
name: Voice Notes
version: 0.1.0
description: Capture voice notes and act on them.
author: operator
capabilities:
  commands:
    - name: voice          # becomes /voice everywhere
      description: transcribe and act on a voice note
      template: |
        Transcribe and execute the following voice instruction: $ARGUMENTS
  pages:
    - id: main
      title: Voice Notes
      icon: mic
      blocks:
        - kind: heading
          text: Voice Notes
        - kind: markdown
          text: Capture a note and ATLAS will transcribe and act on it.
        - kind: actions
          items:
            - label: New note
              command: /voice capture
```

Page block kinds (v1): `heading`, `markdown`, `metrics` (static label/value
pairs), `actions` (buttons that dispatch a slash command / prompt through the
existing chat pipeline). Unknown kinds render as a labeled placeholder so
newer manifests degrade gracefully on older builds.

## Storage

Migration `0023_modules.sql`:

```
modules(id PK, name, version, description, source_path, manifest_json,
        enabled INTEGER DEFAULT 1, missing INTEGER DEFAULT 0,
        installed_at, updated_at)
```

## Surfaces

- Gateway: `GET /v1/modules` (full catalog + enabled/missing),
  `POST /v1/modules/{id}/enabled {enabled}`, `GET /v1/commands`
  (enabled modules' commands only).
- CLI: `atlas module list|sync|enable|disable|create`. `create` scaffolds a
  valid module directory (the self-wiring entry point; the agent runs it via
  the terminal tool). `sync` runs automatically inside `list`.
- WebUI: Control → MODULES tab (toggle, missing badge); CommandPalette and
  Chat/Console slash parsing merge module commands; sidebar MODULES section
  lists enabled modules with pages; `/m/:moduleId` renders the page schema.
- Terminal: command list merges module commands fetched from the gateway
  (best-effort; offline gateway = built-ins only).

## ATLAS skill pack

`skills/atlas/` in-repo: operating doctrine the agent loads when building on
ATLAS itself — distilled from the operator's GSD/ultra/L2 packs:

- `module-builder.md` — how to scaffold/validate/install a module.
- `loop-discipline.md` — GSD-style verify-before-claim execution loop.
- `handoff.md` — session handoff contract.

The pack ships as plain markdown the agent reads on demand (`skills/atlas/`
is referenced from the core policy); a future slice can bind it to Hermes'
skill loading.

## Later slices (documented, not implemented)

- Module-provided tools via the existing `tools/manifests` pattern with a
  per-module namespace + permission prompt.
- Sidecar processes (`capabilities.sidecar`) through the freellmapi-style
  control module (install/start/stop/health).
- Live data bindings for `metrics` blocks (gateway query allowlist).
- Signed module packages + store index (plugin store).
- Module-scoped agent runtimes (a module contributing an AgentRuntime).
