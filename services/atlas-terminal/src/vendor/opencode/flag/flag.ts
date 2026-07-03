import { Config } from "effect"

function truthy(key: string) {
  const value = process.env[key]?.toLowerCase()
  return value === "true" || value === "1"
}

function falsy(key: string) {
  const value = process.env[key]?.toLowerCase()
  return value === "false" || value === "0"
}

function number(key: string) {
  const value = process.env[key]
  if (!value) return undefined
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

const ATLAS_TUI_EXPERIMENTAL = truthy("ATLAS_TUI_EXPERIMENTAL")

// Defaults to false. When enabled, atlas-tui runs in pure-mimo mode:
//   — does NOT inherit Claude Code's settings (CLAUDE.md, ~/.claude/skills, etc.)
//   — does NOT pick up provider API keys from environment variables
//   — falls back to the mimo-auto model as the default
// Set ATLAS_TUI_MIMO_ONLY=true to disable .claude inheritance and env-based
// provider auto-detection.
const ATLAS_TUI_MIMO_ONLY = truthy("ATLAS_TUI_MIMO_ONLY")
const ATLAS_TUI_DISABLE_CLAUDE_CODE_ENV = truthy("ATLAS_TUI_DISABLE_CLAUDE_CODE")
const ATLAS_TUI_DISABLE_CLAUDE_CODE = ATLAS_TUI_MIMO_ONLY || ATLAS_TUI_DISABLE_CLAUDE_CODE_ENV

const ATLAS_TUI_DISABLE_EXTERNAL_SKILLS = truthy("ATLAS_TUI_DISABLE_EXTERNAL_SKILLS")
const ATLAS_TUI_DISABLE_CLAUDE_CODE_SKILLS =
  ATLAS_TUI_DISABLE_EXTERNAL_SKILLS || ATLAS_TUI_DISABLE_CLAUDE_CODE || truthy("ATLAS_TUI_DISABLE_CLAUDE_CODE_SKILLS")
const copy = process.env["ATLAS_TUI_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"]

export const Flag = {
  OTEL_EXPORTER_OTLP_ENDPOINT: process.env["OTEL_EXPORTER_OTLP_ENDPOINT"],
  OTEL_EXPORTER_OTLP_HEADERS: process.env["OTEL_EXPORTER_OTLP_HEADERS"],

  ATLAS_TUI_AUTO_SHARE: truthy("ATLAS_TUI_AUTO_SHARE"),
  ATLAS_TUI_AUTO_HEAP_SNAPSHOT: truthy("ATLAS_TUI_AUTO_HEAP_SNAPSHOT"),
  ATLAS_TUI_GIT_BASH_PATH: process.env["ATLAS_TUI_GIT_BASH_PATH"],
  ATLAS_TUI_CONFIG: process.env["ATLAS_TUI_CONFIG"],
  ATLAS_TUI_CONFIG_CONTENT: process.env["ATLAS_TUI_CONFIG_CONTENT"],

  ATLAS_TUI_DISABLE_AUTOUPDATE: truthy("ATLAS_TUI_DISABLE_AUTOUPDATE"),

  // Defaults to false (rotation enabled). When enabled, the active log file is
  // never archived to <name>.log.<stamp> on hitting MAX_FILE_SIZE — it grows in
  // place. Useful when an external tool tails/manages the single log file.
  ATLAS_TUI_DISABLE_LOG_ROTATION: truthy("ATLAS_TUI_DISABLE_LOG_ROTATION"),

  // Defaults to true (analytics enabled). Set ATLAS_TUI_ENABLE_ANALYSIS=false
  // to opt out of POSTing model_call/tool_call/agent_request metrics.
  ATLAS_TUI_ENABLE_ANALYSIS: !falsy("ATLAS_TUI_ENABLE_ANALYSIS"),
  ATLAS_TUI_ALWAYS_NOTIFY_UPDATE: truthy("ATLAS_TUI_ALWAYS_NOTIFY_UPDATE"),
  ATLAS_TUI_DISABLE_PRUNE: truthy("ATLAS_TUI_DISABLE_PRUNE"),
  ATLAS_TUI_DISABLE_TERMINAL_TITLE: truthy("ATLAS_TUI_DISABLE_TERMINAL_TITLE"),
  ATLAS_TUI_SHOW_TTFD: truthy("ATLAS_TUI_SHOW_TTFD"),
  ATLAS_TUI_PERMISSION: process.env["ATLAS_TUI_PERMISSION"],
  ATLAS_TUI_DISABLE_DEFAULT_PLUGINS: truthy("ATLAS_TUI_DISABLE_DEFAULT_PLUGINS"),
  ATLAS_TUI_DISABLE_LSP_DOWNLOAD: truthy("ATLAS_TUI_DISABLE_LSP_DOWNLOAD"),
  ATLAS_TUI_ENABLE_EXPERIMENTAL_MODELS: truthy("ATLAS_TUI_ENABLE_EXPERIMENTAL_MODELS"),
  ATLAS_TUI_DISABLE_AUTOCOMPACT: truthy("ATLAS_TUI_DISABLE_AUTOCOMPACT"),
  ATLAS_TUI_DISABLE_MODELS_FETCH: truthy("ATLAS_TUI_DISABLE_MODELS_FETCH"),
  ATLAS_TUI_DISABLE_MOUSE: truthy("ATLAS_TUI_DISABLE_MOUSE"),
  ATLAS_TUI_OUTPUT_LENGTH_CONTINUATION_LIMIT: number("ATLAS_TUI_OUTPUT_LENGTH_CONTINUATION_LIMIT") ?? 3,
  ATLAS_TUI_INVALID_OUTPUT_CONTINUATION_LIMIT: number("ATLAS_TUI_INVALID_OUTPUT_CONTINUATION_LIMIT") ?? 2,

  // Sliding-window n-gram repetition detection for streamed reasoning + text.
  // An n-gram of size N appearing REPEAT_THRESHOLD times within the last
  // WINDOW_TOKENS tokens triggers recovery (remind → replan → terminate).
  ATLAS_TUI_TEXT_NGRAM_N: number("ATLAS_TUI_TEXT_NGRAM_N") ?? 6,
  ATLAS_TUI_TEXT_REPEAT_THRESHOLD: number("ATLAS_TUI_TEXT_REPEAT_THRESHOLD") ?? 3,
  ATLAS_TUI_TEXT_WINDOW_TOKENS: number("ATLAS_TUI_TEXT_WINDOW_TOKENS") ?? 500,

  // Caps applied to image attachments before a prompt is sent. Both default to
  // undefined (no limit). ATLAS_TUI_MAX_PROMPT_IMAGES bounds how many images may
  // be sent per request (oldest excess images are dropped); ATLAS_TUI_MAX_PROMPT_IMAGE_SIZE
  // bounds the decoded byte size of a single image. Values must be positive integers.
  ATLAS_TUI_MAX_PROMPT_IMAGES: number("ATLAS_TUI_MAX_PROMPT_IMAGES"),
  ATLAS_TUI_MAX_PROMPT_IMAGE_SIZE: number("ATLAS_TUI_MAX_PROMPT_IMAGE_SIZE"),
  ATLAS_TUI_MIMO_ONLY,
  ATLAS_TUI_DISABLE_PROVIDER_ENV: ATLAS_TUI_MIMO_ONLY || truthy("ATLAS_TUI_DISABLE_PROVIDER_ENV"),
  ATLAS_TUI_DISABLE_CLAUDE_CODE,
  get ATLAS_TUI_DISABLE_CLAUDE_CODE_MCP() {
    // MCP compatibility stays on in mimo-only mode so users can reuse Claude Code
    // MCP servers without inheriting prompts, skills, or provider env keys.
    return ATLAS_TUI_DISABLE_CLAUDE_CODE_ENV || truthy("ATLAS_TUI_DISABLE_CLAUDE_CODE_MCP")
  },
  ATLAS_TUI_DISABLE_CLAUDE_CODE_PROMPT: ATLAS_TUI_DISABLE_CLAUDE_CODE || truthy("ATLAS_TUI_DISABLE_CLAUDE_CODE_PROMPT"),
  // Defaults to false (enabled): markdown commands under ~/.claude/commands and
  // {project}/.claude/commands load as slash commands. Independent of the
  // mimo-only master switch. Set ATLAS_TUI_DISABLE_CLAUDE_CODE_COMMANDS=true to disable.
  ATLAS_TUI_DISABLE_CLAUDE_CODE_COMMANDS: truthy("ATLAS_TUI_DISABLE_CLAUDE_CODE_COMMANDS"),
  ATLAS_TUI_DISABLE_CLAUDE_CODE_SKILLS,
  ATLAS_TUI_DISABLE_EXTERNAL_SKILLS,
  ATLAS_TUI_DISABLE_CODEX_SKILLS: ATLAS_TUI_DISABLE_EXTERNAL_SKILLS || truthy("ATLAS_TUI_DISABLE_CODEX_SKILLS"),
  ATLAS_TUI_DISABLE_OPENCODE_SKILLS: ATLAS_TUI_DISABLE_EXTERNAL_SKILLS || truthy("ATLAS_TUI_DISABLE_OPENCODE_SKILLS"),
  ATLAS_TUI_FAKE_VCS: process.env["ATLAS_TUI_FAKE_VCS"],

  // When enabled, skips all git subprocess calls during project discovery
  // (which git, rev-parse --git-common-dir, rev-parse --show-toplevel) and
  // branch detection. The project is treated as a non-git directory rooted at
  // the working directory. Use to avoid touching git in restricted/sandboxed
  // environments or where git startup probing is undesirable.
  ATLAS_TUI_DISABLE_GIT: truthy("ATLAS_TUI_DISABLE_GIT"),
  ATLAS_TUI_SERVER_PASSWORD: process.env["ATLAS_TUI_SERVER_PASSWORD"],
  ATLAS_TUI_SERVER_USERNAME: process.env["ATLAS_TUI_SERVER_USERNAME"],
  ATLAS_TUI_ENABLE_QUESTION_TOOL: truthy("ATLAS_TUI_ENABLE_QUESTION_TOOL"),

  // Experimental
  ATLAS_TUI_EXPERIMENTAL,
  ATLAS_TUI_EXPERIMENTAL_FILEWATCHER: Config.boolean("ATLAS_TUI_EXPERIMENTAL_FILEWATCHER").pipe(
    Config.withDefault(false),
  ),
  ATLAS_TUI_EXPERIMENTAL_DISABLE_FILEWATCHER: Config.boolean("ATLAS_TUI_EXPERIMENTAL_DISABLE_FILEWATCHER").pipe(
    Config.withDefault(false),
  ),
  ATLAS_TUI_EXPERIMENTAL_ICON_DISCOVERY: ATLAS_TUI_EXPERIMENTAL || truthy("ATLAS_TUI_EXPERIMENTAL_ICON_DISCOVERY"),
  ATLAS_TUI_EXPERIMENTAL_DISABLE_COPY_ON_SELECT:
    copy === undefined ? process.platform === "win32" : truthy("ATLAS_TUI_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"),
  ATLAS_TUI_ENABLE_EXA: truthy("ATLAS_TUI_ENABLE_EXA") || ATLAS_TUI_EXPERIMENTAL || truthy("ATLAS_TUI_EXPERIMENTAL_EXA"),
  ATLAS_TUI_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS: number("ATLAS_TUI_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS"),
  ATLAS_TUI_EXPERIMENTAL_OUTPUT_TOKEN_MAX: number("ATLAS_TUI_EXPERIMENTAL_OUTPUT_TOKEN_MAX"),
  ATLAS_TUI_EXPERIMENTAL_OXFMT: ATLAS_TUI_EXPERIMENTAL || truthy("ATLAS_TUI_EXPERIMENTAL_OXFMT"),
  ATLAS_TUI_EXPERIMENTAL_LSP_TY: truthy("ATLAS_TUI_EXPERIMENTAL_LSP_TY"),
  ATLAS_TUI_EXPERIMENTAL_LSP_TOOL: ATLAS_TUI_EXPERIMENTAL || truthy("ATLAS_TUI_EXPERIMENTAL_LSP_TOOL"),
  // Defaults to true: dynamic workflow + built-in deep-research are on by default.
  // Set ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL=false to opt out. The env-var name is
  // kept for backwards compat (long-running experiments still pass it as `1`).
  ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL: !falsy("ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL"),
  ATLAS_TUI_EXPERIMENTAL_MARKDOWN: !falsy("ATLAS_TUI_EXPERIMENTAL_MARKDOWN"),
  ATLAS_TUI_MODELS_URL: process.env["ATLAS_TUI_MODELS_URL"],
  ATLAS_TUI_MODELS_PATH: process.env["ATLAS_TUI_MODELS_PATH"],
  ATLAS_TUI_DISABLE_EMBEDDED_WEB_UI: truthy("ATLAS_TUI_DISABLE_EMBEDDED_WEB_UI"),
  ATLAS_TUI_DB: process.env["ATLAS_TUI_DB"],

  // Defaults to true — all channels share a single atlas-tui.db. The per-channel
  // DB isolation (atlas-tui-{channel}.db) is unnecessary for atlas-tui since we
  // don't ship multiple release channels yet. Use ATLAS_TUI_HOME to isolate dev
  // environments instead. Set ATLAS_TUI_DISABLE_CHANNEL_DB=false to restore
  // per-channel isolation.
  ATLAS_TUI_DISABLE_CHANNEL_DB: !falsy("ATLAS_TUI_DISABLE_CHANNEL_DB"),
  ATLAS_TUI_SKIP_MIGRATIONS: truthy("ATLAS_TUI_SKIP_MIGRATIONS"),
  ATLAS_TUI_STRICT_CONFIG_DEPS: truthy("ATLAS_TUI_STRICT_CONFIG_DEPS"),

  ATLAS_TUI_WORKSPACE_ID: process.env["ATLAS_TUI_WORKSPACE_ID"],
  ATLAS_TUI_EXPERIMENTAL_HTTPAPI: truthy("ATLAS_TUI_EXPERIMENTAL_HTTPAPI"),
  ATLAS_TUI_EXPERIMENTAL_WORKSPACES: ATLAS_TUI_EXPERIMENTAL || truthy("ATLAS_TUI_EXPERIMENTAL_WORKSPACES"),

  // Evaluated at access time (not module load) because tests, the CLI, and
  // external tooling set these env vars at runtime.

  // Disables compose-agent-internal skills (e.g. compose:plan, compose:review,
  // compose:tdd). These are hidden workflow-orchestration skills only visible
  // to the compose agent and are NOT part of builtin skills.
  get ATLAS_TUI_DISABLE_COMPOSE_SKILLS() {
    return truthy("ATLAS_TUI_DISABLE_COMPOSE_SKILLS")
  },
  // Disables user-facing builtin skills shipped with the binary (e.g.
  // self-extend). Does not affect compose skills — the two sets are
  // independent and non-overlapping.
  get ATLAS_TUI_DISABLE_BUILTIN_SKILLS() {
    return truthy("ATLAS_TUI_DISABLE_BUILTIN_SKILLS")
  },
  get ATLAS_TUI_DISABLE_PROJECT_CONFIG() {
    return truthy("ATLAS_TUI_DISABLE_PROJECT_CONFIG")
  },
  get ATLAS_TUI_TUI_CONFIG() {
    return process.env["ATLAS_TUI_TUI_CONFIG"]
  },
  get ATLAS_TUI_CONFIG_DIR() {
    return process.env["ATLAS_TUI_CONFIG_DIR"]
  },
  get ATLAS_TUI_HOME() {
    return process.env["ATLAS_TUI_HOME"]
  },
  get ATLAS_TUI_PURE() {
    return truthy("ATLAS_TUI_PURE")
  },
  get ATLAS_TUI_PLUGIN_META_FILE() {
    return process.env["ATLAS_TUI_PLUGIN_META_FILE"]
  },
  get ATLAS_TUI_CLIENT() {
    return process.env["ATLAS_TUI_CLIENT"] ?? "cli"
  },
}
