# Graph Query, Slash Commands, and Composer Final Pass

## Intent

Finish the July 17 operator-chat slice with three changes that reinforce one another: ATLAS can inspect its own graph through a bounded read-only tool, WebUI slash commands share one discoverable catalog, and the chat composer stays responsive while the transcript is streaming.

## Decisions

### Graph query plane

- Register `atlas_graph` through the existing Hermes `PluginContext` seam; do not edit vendored Hermes code.
- Reuse `atlas_runtime.graph_service` as the backend so the tool and Knowledge Graph page see the same four scopes.
- Public scopes are `global`, `projects`, `obsidian`, and `agent`; `agent` maps to the existing `.planning` (`atlas`) graph.
- Support only bounded read operations: `search`, `node`, `neighbors`, `path`, `content`, and `stats`.
- Reject traversal, arbitrary Cypher, graph mutation, and unbounded result sizes. Content reads are restricted to Markdown nodes within the selected scope and truncated.
- Cache graph builds briefly per root/scope. Native runtime audit hooks already record the tool request/result.

### Slash command registry

- Keep built-ins and active-module commands in one client catalog with deterministic de-duplication (built-ins win).
- Cache module discovery instead of fetching every time the modal opens.
- Use the same matcher and expansion functions for the global palette and the chat inline completion rail.
- Typing `/` in Chat opens inline suggestions. Arrow keys select, Tab completes, and Enter completes a partial command before normal prompt submission.
- Keep the command palette as the full searchable index; expose command source and argument hints without adding another visual card layer.

### Composer performance and motion

- Move the live draft into `QueuedChatComposer`; the 500+ line Chat route receives updates only through a debounced persistence callback and on submit/edit/session reset.
- Do not use React state for the typing animation. Restart one Web Animation on a single overlay element, cancelling the previous animation.
- The scan is a restrained one-pixel teal/celestial band, 180ms, low opacity, transform/opacity only. Disable it under `prefers-reduced-motion`.
- Preserve the four-message queue, Enter/Shift+Enter behavior, session restore, and busy/cancel semantics.

## Visual contract

The existing ATLAS topographic cockpit remains the source of truth. The composer uses a calm near-black surface ladder, thin rails and dividers, scarce teal/celestial accents, and monospace metadata. Slash results read as a command index rather than nested cards. Focus and scan motion communicate state; they do not decorate idle surfaces.

## Verification

- Unit tests cover query bounds/path safety, bridge registration, catalog de-duplication/matching, inline slash completion, and composer submission.
- Run agent-runtime tests, WebUI tests/typecheck/build, then visually exercise Chat in a real browser with reduced-motion behavior considered.
