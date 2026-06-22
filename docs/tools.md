# Developer Integrations & Tool Manifest v0

ATLAS is an **extensible harness**: adding a developer integration is writing a
*manifest* (a small YAML file) plus an *adapter* (a Python function). Every tool
call flows through a single policy chokepoint, is audited, and — for anything that
writes — is gated behind an explicit operator approval.

## Safety model (read this first)

- **Read-only by default.** A tool's `risk_level` decides whether it runs:
  | `risk_level` | behavior |
  |--------------|----------|
  | `read`  | auto-allowed — runs immediately |
  | `write` | **requires explicit operator approval** (lands as a pending approval) |
  | `shell` | **requires explicit operator approval** |
- **No sensitive data is stored.** Credentials are `env:VAR` references only. Tool
  arguments and results are **redacted** (via the shared `SECRET_PATTERNS`) once at
  the audit boundary before any `audit_events` / `tool_approvals` row is written.
- **SSRF guard.** `web_fetch` / `webhook_notify` block non-`http(s)` schemes and any
  host resolving to a loopback / private / link-local / reserved address, with a size
  cap and timeout; `web_fetch` is GET-only.
- **Workspace boundary.** The `workspace` adapter gates every path through
  `policy.check_workspace_boundary` before any filesystem access (no CWD escape).
- **gateway is dispatch-only (D-022).** The Rust gateway validates and shells to the
  `atlas` CLI; all policy, state, and approvals live in Python/SQLite.

## The four shipped tools (v0)

| tool | risk | what it does |
|------|------|--------------|
| `workspace` | read | read a file / list a dir / grep within the workspace boundary |
| `github` | read | repo/issue/PR data via the operator's authenticated `gh` CLI (no token handled by ATLAS) |
| `web_fetch` | read | HTTP GET a public URL (SSRF-guarded, size-capped) |
| `webhook_notify` | write | POST a JSON payload to an outbound webhook (approval-gated) |

## Tool Manifest v0 schema

One YAML file per tool under `services/agent-runtime/atlas_runtime/tools/manifests/`,
validated at load against the frozen `atlas_core.schemas.tool.ToolManifest`:

```yaml
name: web_fetch                 # must match the adapter binding key in the registry
description: HTTP GET a public URL with an SSRF guard, size cap, and timeout.
risk_level: read                # read | write | shell
permissions: [net:get]          # informational capability tags
inputs:                         # declared parameters
  - name: url
    required: true
    description: http(s) URL (loopback/private targets blocked)
outputs: [content]
audit_events: [tool_requested, tool_completed, tool_failed]
```

An unknown `risk_level` or a missing required field is a **fail-fast** load error.

## Adding a tool (manifest + adapter)

1. **Write the adapter** — `tools/adapters/<name>.py` exposing
   `run(args: dict, ctx) -> ToolResult`. The adapter assumes it has already been
   authorized — it performs **no** policy checks (the chokepoint owns policy). Use
   only the stdlib (or an installed CLI like `gh`); no new third-party deps.
2. **Write the manifest** — `tools/manifests/<name>.yaml` per the schema above; the
   `name` must match.
3. **Bind it** — add `"<name>": <module>.run` to `_ADAPTERS` in `tools/registry.py`.

That is the whole contract — no core changes.

## Invoking tools

```bash
atlas tools list                       # known tool names
atlas tools manifests --json           # full manifests (consumed by the cockpit)
atlas tools call --json -- web_fetch --args '{"url":"https://example.com"}'
atlas tools approvals --status pending --json
atlas tools approve <approval-id> --json
atlas tools reject  <approval-id> --json
```

Read-class calls return a `ToolResult` immediately. Write/shell calls return a
**pending** `ToolApproval` and do not execute until `approve`. The cockpit **System**
page surfaces all of this: a TOOL POLICY panel (read-only badge, risk legend,
no-sensitive-data posture), a TOOLS list from the manifests, and a TOOL APPROVALS
queue (Approve / Reject).

Over HTTP (gateway, dispatch-only): `GET /v1/tools/manifests`, `POST /v1/tools/calls`,
`GET /v1/tools/approvals`, `POST /v1/tools/approvals/{id}/approve`, `.../reject`.

## Audit events — naming note (SC4)

Every tool call emits, on the existing audit bus, one of three lifecycle events:

- `tool_requested` — the call entered the chokepoint
- `tool_completed` — the adapter ran successfully (read-class, or after approval)
- `tool_failed` — the adapter raised or returned a failure

These enum values are **snake_case** to match the existing audit-bus convention
(`tool_call`, `discord_action`). The dotted form `tool.requested` / `tool.completed`
/ `tool.failed` used in the milestone success criteria is the **conceptual/external
label** for the same three events — there is no separate dotted enum.
