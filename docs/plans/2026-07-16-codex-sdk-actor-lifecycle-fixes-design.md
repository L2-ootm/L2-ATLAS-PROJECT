# Codex SDK, actor bridge, and lifecycle fixes

## Decision

Replace the production Codex subprocess adapter with OpenAI's official Python
Codex SDK, installed only through an optional `codex` extra. The adapter will
lazy-import `openai_codex`, explicitly select the operator's current local Codex
binary, and use the existing Codex login. This avoids ATLAS handling an API key
and avoids the Windows argv limit. The SDK's notification stream will be
normalized into ATLAS's existing audit taxonomy so the runtime keeps command,
file, MCP, search, reasoning, usage, failure, and final-response parity. The
injectable event runner remains as the unit-test seam; there is no silent CLI
fallback in production.

This dependency is a deliberate exception to the normal Python dependency
ceiling. `openai-codex` is beta and currently brings a roughly 95 MB pinned CLI
runtime, so it is constrained to `>=0.1.0b3,<0.2`, excluded from default
installs, and loaded only when the Codex runtime is selected. A TypeScript SDK
bridge would add another process and protocol boundary to the Python runtime;
continuing with raw `codex exec -` would be smaller but would not satisfy the
requested SDK integration.

## Boundary fixes

`atlas_actor` must implement Hermes's plugin handler ABI: one positional
arguments dictionary plus framework context keywords. The handler will resolve
the ATLAS run from `parent_agent.session_id` when present, otherwise from the
Hermes `task_id`, and then call the existing durable actor service unchanged.
Coverage must dispatch through the real Hermes registry rather than calling the
handler directly.

On Windows, cockpit shutdown will use `taskkill /T /F` and verify the recorded
process is gone before removing its PID file or reporting success. POSIX keeps
its existing signal behavior. Tests will cover the command shape, failed
termination, retained PID state, and the restart abort contract. Live UAT must
prove Codex completion, actor creation/completion, and that port 5173 has no
listener after `atlas down`.
