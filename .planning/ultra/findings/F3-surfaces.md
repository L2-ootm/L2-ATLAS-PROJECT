# F3 — FreeLLMAPI Integration Across ATLAS Surfaces

> **Scope**: How the FreeLLMAPI sidecar is discovered, displayed, toggled, and privacy-warned across every ATLAS UI surface.
> **Files read**: 11 source files across cockpit (React), Go TUI, and atlas-terminal (Solid/TypeScript).

---

## 1. Cockpit (React web-ui-react)

### 1.1 Type and API Layer (`services/web-ui-react/src/lib/api.ts`)

**FreellmapiStatus type** — `api.ts:605-612`:
```ts
export interface FreellmapiStatus {
  running: boolean;
  base_url: string;
  dir: string | null;
  installed: boolean;
  api_key?: string | null;
  remediation: string | null;
}
```

**ProviderAuthMode union** — `api.ts:937`: `'freellmapi'` is one of four auth modes alongside `api_key`, `oauth_import`, `claude_code`.

**API functions** — `api.ts:614-631`:
- `freellmapiStatus()` — `GET /v1/freellmapi/status`. Gracefully degrades to `{ running: false, base_url: '', dir: null, installed: false, remediation: null }` on 404/503 (`api.ts:617-619`).
- `freellmapiStart()` — `POST /v1/freellmapi/start`. Returns `{ ok: boolean; message: string }` (`api.ts:625-627`).
- `freellmapiStop()` — `POST /v1/freellmapi/stop`. Same return shape (`api.ts:629-631`).

**ProviderStatusView** — `api.ts:986-997`: Contains `privacy_warning?: string | null` (`api.ts:996`), which the gateway populates when the active auth mode is `freellmapi`.

### 1.2 Settings UI (`services/web-ui-react/src/routes/Settings.tsx`)

**Mode hint** — `Settings.tsx:38`:
```ts
freellmapi: 'Free OpenAI-compatible endpoint. Privacy cost: prompts may be logged.'
```
This is the human-readable hint shown under the mode selector when freellmapi is selected.

**State management** — `Settings.tsx:72-73`: `sidecar` (type `FreellmapiStatus | null`) and `sidecarBusy` track the sidecar lifecycle independently of the provider config.

**Refresh** — `Settings.tsx:76-108`: `freellmapiStatus()` is called as part of `Promise.allSettled` alongside `getConfig`, `getProviderStatus`, `getProviderModes`, and `listModels`. The result is stored via `setSidecar()` at line 108.

**Mode selection** — `Settings.tsx:190-199` (`selectMode`): When switching to `freellmapi`:
1. Sets `providerName` to `'freellmapi'` (line 195).
2. Auto-fills `baseUrl` from `sidecar.base_url` if present (line 196).
3. Auto-fills `apiKey` from `sidecar.api_key` if present (line 197).

**Save validation** — `Settings.tsx:120-123`: When auth mode is `freellmapi` and `baseUrl` is empty, the save is rejected with the message "FreeLLMAPI mode requires a base URL."

**Key storage** — `Settings.tsx:127-129`: When auth mode is `api_key` or `freellmapi` and an API key is provided, `storeProviderKey()` is called before the config patch.

**Provider name input** — `Settings.tsx:356-363`: When `authMode` is `freellmapi`, the provider name field is editable (same as `api_key`), with placeholder `"freellmapi"`.

**Base URL input** — `Settings.tsx:383`: Placeholder changes to `"http://127.0.0.1:3001/v1"` when in freellmapi mode.

**API key input** — `Settings.tsx:387-396`: When `authMode` is `freellmapi` or `api_key`, the API key field is shown with placeholder `"(Optional) freellmapi-..."`.

### 1.3 Sidecar Toggle Panel (`Settings.tsx:305-341`)

Rendered conditionally when `authMode === 'freellmapi'`:

**Privacy warning** — `Settings.tsx:307-312`:
```tsx
<div role="alert" style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
  <ShieldAlert size={13} color="var(--l2-warning)" />
  <span style={mono(10.5, 'var(--l2-warning)')}>
    Privacy warning: free endpoints may log prompts — never send secrets. Every run is
    audit-stamped with this warning.
  </span>
</div>
```
Uses `role="alert"` for screen reader accessibility and the `ShieldAlert` icon from lucide-react.

**Sidecar status pill** — `Settings.tsx:314-340`: Shown when `sidecar` is non-null:
- Displays a running indicator dot (green for running, muted for stopped) — line 318.
- Shows `RUNNING` or `STOPPED` text — line 319.
- Shows `base_url` truncated to 240px max width — line 320.
- Toggle button labeled `START` or `STOP` — line 337.
- Button is disabled when `sidecarBusy` or when the sidecar is not installed and not running — line 323.

**Toggle behavior** — `Settings.tsx:201-221` (`toggleSidecar`):
1. Calls `freellmapiStop()` if running, `freellmapiStart()` otherwise — line 205.
2. If the response has `ok === false`, displays the error as a banner — line 207.
3. Polls `freellmapiStatus()` up to 5 times at 1.2s intervals to detect the state flip — lines 210-215.
4. The sidecar boots asynchronously; polling bridges the gap until the pill reflects the new state.

### 1.4 Active Status Panel (`Settings.tsx:468-501`)

The `ActiveStatusPanel` component receives the `ProviderStatusView` and renders:
- `LIVE` or `MOCK MODE` indicator — line 483.
- Provider/model string — line 486.
- Auth mode label — line 488.
- **Privacy warning** — `Settings.tsx:493-495`: When `status.privacy_warning` is present (set by the gateway when freellmapi is the active mode), it renders as a warning-colored paragraph below the status line.

### 1.5 Test Coverage (`services/web-ui-react/src/test/settings.test.tsx`)

**Mock setup** — `settings.test.tsx:31-33`: `freellmapiStatus`, `freellmapiStart`, `freellmapiStop` are all mocked.

**Mode board fixture** — `settings.test.tsx:76`: Includes `{ mode: 'freellmapi', label: 'FREE LLM API', active: false, available: false, detail: 'needs base URL' }`.

**Sidecar mock** — `settings.test.tsx:91-98`: `freellmapiStatus` returns a stopped, not-installed sidecar by default.

**Test: privacy warning + base URL requirement** — `settings.test.tsx:154-164`:
1. Switches to freellmapi mode by clicking the `FREE LLM API` button.
2. Asserts `role="alert"` contains "Privacy warning" — line 160.
3. Clicks SAVE and asserts `patchConfig` was NOT called (no base URL) — line 162.
4. Asserts the error message "FreeLLMAPI mode requires a base URL." appears — line 163.

---

## 2. Go TUI (atlas-tui)

### 2.1 Type Definitions (`services/atlas-tui/internal/client/types.go`)

**FreellmapiStatus** — `types.go:180-187`:
```go
type FreellmapiStatus struct {
    Running     bool   `json:"running"`
    BaseURL     string `json:"base_url"`
    Dir         string `json:"dir"`
    Installed   bool   `json:"installed"`
    Remediation string `json:"remediation"`
}
```
Note: Unlike the React version, this does NOT include `api_key` — the Go TUI never sees the raw key.

**FreellmapiAction** — `types.go:189-192`:
```go
type FreellmapiAction struct {
    OK      bool   `json:"ok"`
    Message string `json:"message"`
}
```

**ProviderStatus** — `types.go:58-69`: Contains `PrivacyWarning *string` at line 68, received from the gateway when freellmapi is active.

### 2.2 Client Methods (`services/atlas-tui/internal/client/client.go`)

**FreellmapiStatus** — `client.go:372-376`: `GET /v1/freellmapi/status`, decodes into `FreellmapiStatus`.

**FreellmapiStart** — `client.go:379-382`: `POST /v1/freellmapi/start`, decodes into `FreellmapiAction`.

**FreellmapiStop** — `client.go:385-389`: `POST /v1/freellmapi/stop`, decodes into `FreellmapiAction`.

All three use the shared `getJSON`/`postJSON` helpers with the standard 15s HTTP timeout (`client.go:64`).

### 2.3 Slash Command (`services/atlas-tui/internal/tui/commands.go`)

**Registration** — `commands.go:27`:
```go
{"/freellmapi", "control the free endpoint sidecar: status, start, stop"},
```

**Execution** — `commands.go:210-219`:
```go
case "/freellmapi":
    verb := "status"
    if len(fields) > 1 {
        verb = strings.ToLower(fields[1])
    }
    if verb != "status" && verb != "start" && verb != "stop" {
        m.appendSystem("usage: /freellmapi [status|start|stop]")
        return true, m, nil
    }
    return true, m, m.freellmapiAction(verb)
```
Default verb is `status`. Invalid verbs produce a usage hint.

### 2.4 Model Message Type (`services/atlas-tui/internal/tui/model.go`)

**freellmapiMsg** — `model.go:90-95`:
```go
type freellmapiMsg struct {
    verb   string // "status" | "start" | "stop"
    status client.FreellmapiStatus
    action client.FreellmapiAction
    err    error
}
```

**freellmapiAction command** — `model.go:321-336`: Dispatches the appropriate client method based on the verb. Status returns `freellmapiMsg` with `status` populated; start/stop return it with `action` populated.

**Update handler** — `model.go:500-518`:
- **Error case** (line 501-504): Appends an error transcript item with label `"freellmapi"`.
- **Status case** (lines 505-514): Renders `"FREELLMAPI RUNNING|STOPPED  <bullet>  <base_url>"`. If not installed and remediation is non-empty, appends `"  <bullet>  <remediation>"`.
- **Start/Stop case** (line 516): Renders `"FREELLMAPI START|STOP  <bullet>  <message>"`.

### 2.5 Settings Integration (`services/atlas-tui/internal/tui/settings.go`)

**Provider modes list** — `settings.go:17`:
```go
var providerModes = []string{"api_key", "oauth_import", "claude_code", "freellmapi"}
```
`freellmapi` is the fourth entry, navigable via left/right arrow keys in the mode cycler.

**Mode description** — `settings.go:217-218`:
```go
case "freellmapi":
    b.WriteString(styleWarn.Render("Privacy warning: free endpoints may log prompts; never send secrets."))
```
Displayed at the bottom of the settings form when the mode is `freellmapi`, using warning styling.

**Save validation** — `settings.go:274-278`:
```go
if mode == "freellmapi" && baseURL == "" {
    m.settings.message = "FreeLLMAPI mode requires a base URL"
    m.settings.messageBad = true
    return m, nil
}
```
Same validation as the React cockpit: base URL is mandatory for freellmapi mode.

**Key storage** — `settings.go:286-291`: When `mode == "api_key"` and an API key is provided, `StoreAPIKey` is called. The `freellmapi` mode does NOT trigger key storage (no `case "freellmapi"` branch in the switch), meaning the freellmapi API key is only set through the base URL/config patch, not the auth store.

### 2.6 Events Display (`services/atlas-tui/internal/tui/events.go`)

**Privacy warning in audit stream** — `events.go:135-139`:
```go
case "freellmapi":
    if warning := firstString(data, "privacy_warning"); warning != "" {
        return []transcriptItem{{kind: itemSystem, text: warning}}
    }
```
When a `tool_call` audit event has `tool_name == "freellmapi"`, the TUI extracts the `privacy_warning` field from the event data and renders it as a system-level transcript item. This means every run that goes through the freellmapi sidecar emits a visible privacy warning in the TUI transcript.

---

## 3. atlas-terminal (Solid/TypeScript)

### 3.1 Adapter Proxy (`services/atlas-terminal/src/adapter/atlasFetch.ts`)

**handleAtlasFreellmapi** — `atlasFetch.ts:142-147`:
```ts
async function handleAtlasFreellmapi(gw: string, f: typeof fetch, action: 'status' | 'start' | 'stop'): Promise<Response> {
  const method = action === 'status' ? 'GET' : 'POST';
  const res = await f(`${gw}/v1/freellmapi/${action}`, ...);
  const payload = await res.json().catch(() => ({}));
  return json(payload, res.status);
}
```
The adapter translates three internal paths to gateway routes:
- `GET /atlas/freellmapi/status` → `GET /v1/freellmapi/status` — `atlasFetch.ts:344`
- `POST /atlas/freellmapi/start` → `POST /v1/freellmapi/start` — `atlasFetch.ts:345`
- `POST /atlas/freellmapi/stop` → `POST /v1/freellmapi/stop` — `atlasFetch.ts:346`

The comment at `atlasFetch.ts:137-141` notes this was identified by a parity audit as "the one real gap" between the Go TUI and the atlas-terminal adapter.

### 3.2 Slash Commands (`services/atlas-terminal/src/tui/app.tsx`)

Three slash commands registered in the command system:

**`/freellmapi-status`** — `app.tsx:651-665`:
```ts
{
  title: "FreeLLMAPI: check sidecar status",
  value: "atlas.freellmapi.status",
  slash: { name: "freellmapi-status" },
  onSelect: async () => {
    const res = await (sdk.fetch ?? fetch)(`${sdk.url}/atlas/freellmapi/status`)
    const body = (await res.json().catch(() => ({}))) as { running?: boolean; base_url?: string; installed?: boolean; remediation?: string }
    toast.show({
      variant: res.ok && body.running ? "success" : "info",
      message: res.ok
        ? `FreeLLMAPI: ${body.running ? `running at ${body.base_url}` : body.installed ? "installed, not running" : body.remediation || "not installed"}`
        : "FreeLLMAPI status check failed",
    })
  },
  category: "provider",
}
```
Displays a toast with status. Three-state display: running (with URL), installed but stopped, or not installed (with remediation).

**`/freellmapi-start`** — `app.tsx:667-676`:
```ts
{
  title: "FreeLLMAPI: start sidecar",
  value: "atlas.freellmapi.start",
  slash: { name: "freellmapi-start" },
  onSelect: async () => {
    const res = await (sdk.fetch ?? fetch)(`${sdk.url}/atlas/freellmapi/start`, { method: "POST" })
    const body = (await res.json().catch(() => ({}))) as { ok?: boolean; message?: string }
    toast.show({ variant: res.ok && body.ok ? "success" : "error", message: body.message || ... })
  },
  category: "provider",
}
```

**`/freellmapi-stop`** — `app.tsx:677-687`: Same pattern as start, calling `/atlas/freellmapi/stop`.

All three are categorized under `"provider"`.

---

## 4. Status Discovery Across Surfaces

| Surface | Status Endpoint | Trigger | Display |
|---------|----------------|---------|---------|
| **Cockpit** | `GET /v1/freellmapi/status` | On mount (`refresh()`, line 81) + after toggle (poll loop, lines 210-215) | Sidecar pill: running/stopped dot + text + URL (`Settings.tsx:314-340`) |
| **Go TUI** | `GET /v1/freellmapi/status` | On `/freellmapi status` command (line 211-213 in commands.go) | Transcript system line: `FREELLMAPI RUNNING/STOPPED <url>` (`model.go:505-514`) |
| **atlas-terminal** | `GET /atlas/freellmapi/status` → `GET /v1/freellmapi/status` | On `/freellmapi-status` slash command (`app.tsx:655`) | Toast notification (`app.tsx:657-662`) |

Key difference: The cockpit fetches status eagerly on page load; the Go TUI and atlas-terminal only fetch on explicit user command.

---

## 5. Privacy Warning Implementation Across Surfaces

The privacy warning is the most consistently implemented cross-surface concern:

### 5.1 Warning Text Sources

| Source | Location | Text |
|--------|----------|------|
| **Cockpit MODE_HINTS** | `Settings.tsx:38` | `"Free OpenAI-compatible endpoint. Privacy cost: prompts may be logged."` |
| **Cockpit alert div** | `Settings.tsx:309-311` | `"Privacy warning: free endpoints may log prompts — never send secrets. Every run is audit-stamped with this warning."` |
| **Cockpit ActiveStatusPanel** | `Settings.tsx:493-495` | Dynamic: `status.privacy_warning` from gateway (`ProviderStatusView.privacy_warning`) |
| **Go TUI settings form** | `settings.go:218` | `"Privacy warning: free endpoints may log prompts; never send secrets."` |
| **Go TUI events/transcript** | `events.go:135-138` | Dynamic: `privacy_warning` field from audit event data |

### 5.2 Warning Surfaces

1. **Cockpit mode selector hint** (`Settings.tsx:38`): Always visible when freellmapi mode is selected, as the `MODE_HINTS[authMode]` paragraph at line 304.

2. **Cockpit inline alert** (`Settings.tsx:307-312`): Conditionally rendered when `authMode === 'freellmapi'`. Uses `role="alert"` for accessibility, `ShieldAlert` icon, and warning color. This is a static warning that appears whenever the mode is selected.

3. **Cockpit active status panel** (`Settings.tsx:493-495`): Dynamic — only appears when the gateway returns `privacy_warning` in the provider status response. This means the warning persists even after navigating away from settings, as long as freellmapi is the active mode.

4. **Go TUI settings form** (`settings.go:217-218`): Static warning shown at the bottom of the settings panel when the mode is `freellmapi`.

5. **Go TUI transcript** (`events.go:135-138`): Runtime warning emitted on every audit event where `tool_name == "freellmapi"` and `privacy_warning` is present in the event data. This ensures that every agent run through the sidecar is visibly stamped.

6. **atlas-terminal**: No explicit privacy warning in the slash command handlers. The status toast shows operational state (running/stopped) but does not display the privacy message. This is a parity gap compared to the Go TUI's transcript-level warning.

### 5.3 Warning Flow

```
Gateway (/v1/provider/status)
  └─> privacy_warning field (when auth_mode == freellmapi)
        ├─> Cockpit: ActiveStatusPanel renders it inline (Settings.tsx:493-495)
        └─> Go TUI: ProviderStatus.PrivacyWarning available but rendered
            only through the settings form mode hint (settings.go:218)
            and the audit event stream (events.go:135-138)

Gateway (audit events during a run)
  └─> tool_call event with tool_name == "freellmapi" and privacy_warning in data
        └─> Go TUI: renders as system transcript item (events.go:135-138)
```

---

## 6. Summary of Parity Gaps

1. **atlas-terminal has no privacy warning display** for freellmapi mode. The Go TUI shows it in both the settings form and the runtime transcript; the cockpit shows it in the mode selector, the inline alert, and the active status panel. The atlas-terminal only shows operational status toasts.

2. **atlas-terminal settings dialog** (`DialogAtlasSettings`) is referenced at `app.tsx:646` but its freellmapi-specific behavior was not in the files read — it likely delegates to the same `/atlas/config` and `/atlas/provider/status` adapter routes, which would carry the privacy_warning field if the dialog renders it.

3. **Go TUI does not auto-fetch sidecar status on startup** — unlike the cockpit which polls `freellmapiStatus()` on mount. The Go TUI only fetches it on explicit `/freellmapi` command.

4. **Go TUI settings save does not store freellmapi API keys** via the auth store — only `api_key` mode triggers `StoreAPIKey` (`settings.go:286-291`). The cockpit stores keys for both `api_key` and `freellmapi` modes (`Settings.tsx:127-129`).
