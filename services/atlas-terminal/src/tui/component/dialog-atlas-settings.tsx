import { createSignal, onMount } from "solid-js"
import { createStore } from "solid-js/store"
import { useSDK } from "../context/sdk"
import { useDialog } from "@tui/ui/dialog"
import { useToast } from "../ui/toast"
import { DialogSelect } from "@tui/ui/dialog-select"
import { DialogPrompt } from "../ui/dialog-prompt"
import { readinessFor, mockAllowed, type ProviderStatus } from "../util/readiness"

/**
 * ATLAS provider settings — ported from services/atlas-tui/internal/tui/
 * settings.go onto the donor presentation shell. Talks to the ATLAS-native
 * routes added in src/adapter/atlasFetch.ts (/atlas/config, /atlas/provider/
 * status, /atlas/auth/providers, /atlas/auth/codex/import), which forward to
 * the exact same gateway contract (GET/PATCH /v1/config, POST /v1/auth/*,
 * GET /v1/provider/status) the working Go TUI already uses.
 *
 * Scope cut vs the Go TUI: the post-save connectivity probe (settings.go's
 * startProbe/archiveProbe, which runs an ephemeral mission to classify
 * live/mock/failed) is not ported here — save + a provider/status refresh
 * covers the same readiness signal without the extra mission plumbing.
 */

interface AtlasProviderConfig {
	name: string
	model: string
	auth_mode: string
	api_key: string
	base_url: string | null
	reasoning_effort: string
}

interface AtlasConfigSnapshot {
	schema_version: number
	revision: number
	provider: AtlasProviderConfig
}

const PROVIDER_MODES = ["api_key", "oauth_import", "claude_code", "freellmapi"] as const
const EFFORT_LEVELS = ["", "minimal", "low", "medium", "high"] as const

interface Draft {
	provider: string
	model: string
	mode: (typeof PROVIDER_MODES)[number]
	baseURL: string
	effort: (typeof EFFORT_LEVELS)[number]
}

export function DialogAtlasSettings() {
	const sdk = useSDK()
	const dialog = useDialog()
	const toast = useToast()

	const [revision, setRevision] = createSignal(0)
	const [status, setStatus] = createSignal<ProviderStatus | null>(null)
	const [pendingApiKey, setPendingApiKey] = createSignal("")
	const [busy, setBusy] = createSignal(false)
	const [draft, setDraft] = createStore<Draft>({
		provider: "",
		model: "",
		mode: "api_key",
		baseURL: "",
		effort: "",
	})

	const call = (path: string, init?: RequestInit) => (sdk.fetch ?? fetch)(`${sdk.url}${path}`, init)

	async function load() {
		const [cfgRes, statusRes] = await Promise.all([call("/atlas/config"), call("/atlas/provider/status")])
		if (cfgRes.ok) {
			const snap = (await cfgRes.json()) as AtlasConfigSnapshot
			setRevision(snap.revision)
			setDraft({
				provider: snap.provider.name ?? "",
				model: snap.provider.model ?? "",
				mode: (PROVIDER_MODES as readonly string[]).includes(snap.provider.auth_mode)
					? (snap.provider.auth_mode as Draft["mode"])
					: "api_key",
				baseURL: snap.provider.base_url ?? "",
				effort: (EFFORT_LEVELS as readonly string[]).includes(snap.provider.reasoning_effort)
					? (snap.provider.reasoning_effort as Draft["effort"])
					: "",
			})
		}
		if (statusRes.ok) setStatus((await statusRes.json()) as ProviderStatus)
	}

	onMount(() => {
		openMenu()
		void load().then(() => openMenu())
	})

	function readiness() {
		const s = status()
		return s ? readinessFor(s, mockAllowed()) : undefined
	}

	function openMenu() {
		const r = readiness()
		dialog.replace(() => (
			<DialogSelect
				title="Provider settings"
				hint={r ? `${r.label}${r.remediation ? " — " + r.remediation : ""}` : "loading…"}
				options={[
					{
						title: "Provider",
						value: "provider",
						description: draft.provider || "(unset)",
						onSelect: () => editText("Provider", draft.provider, "openrouter", (v) => setDraft("provider", v)),
					},
					{
						title: "Model",
						value: "model",
						description: draft.model || "(unset)",
						onSelect: () => editText("Model", draft.model, "provider/model", (v) => setDraft("model", v)),
					},
					{
						title: "Auth mode",
						value: "auth_mode",
						description: draft.mode,
						onSelect: () => editMode(),
					},
					{
						title: "Base URL",
						value: "base_url",
						description: draft.baseURL || "(none)",
						onSelect: () =>
							editText("Base URL", draft.baseURL, "optional OpenAI-compatible endpoint", (v) =>
								setDraft("baseURL", v),
							),
					},
					{
						title: "API key",
						value: "api_key",
						description: pendingApiKey() ? "(pending — will be saved)" : "(leave blank to keep existing)",
						onSelect: () =>
							editText("API key", "", "leave blank to keep existing credential", (v) => setPendingApiKey(v)),
					},
					{
						title: "Reasoning effort",
						value: "effort",
						description: draft.effort || "(provider default)",
						onSelect: () => editEffort(),
					},
					{
						title: busy() ? "Saving…" : "Save",
						value: "save",
						onSelect: () => void save(),
					},
				]}
			/>
		))
	}

	function editText(title: string, value: string, placeholder: string, onSet: (v: string) => void) {
		dialog.replace(
			() => (
				<DialogPrompt
					title={title}
					value={value}
					placeholder={placeholder}
					onConfirm={(v) => {
						onSet(v.trim())
						openMenu()
					}}
				/>
			),
			() => openMenu(),
		)
	}

	function editMode() {
		dialog.replace(() => (
			<DialogSelect
				title="Auth mode"
				current={draft.mode}
				options={PROVIDER_MODES.map((mode) => ({
					title: mode,
					value: mode,
					onSelect: () => {
						setDraft("mode", mode)
						openMenu()
					},
				}))}
			/>
		))
	}

	function editEffort() {
		dialog.replace(() => (
			<DialogSelect
				title="Reasoning effort"
				current={draft.effort}
				options={EFFORT_LEVELS.map((effort) => ({
					title: effort || "provider default",
					value: effort,
					onSelect: () => {
						setDraft("effort", effort)
						openMenu()
					},
				}))}
			/>
		))
	}

	async function save() {
		if (busy()) return
		if (!draft.provider || !draft.model) {
			toast.show({ message: "Provider and model are required", variant: "error" })
			openMenu()
			return
		}
		if (draft.mode === "freellmapi" && !draft.baseURL) {
			toast.show({ message: "FreeLLMAPI mode requires a base URL", variant: "error" })
			openMenu()
			return
		}
		setBusy(true)
		try {
			if (draft.mode === "api_key" && pendingApiKey()) {
				const r = await call("/atlas/auth/providers", {
					method: "POST",
					headers: { "content-type": "application/json" },
					body: JSON.stringify({
						provider: draft.provider,
						api_key: pendingApiKey(),
						base_url: draft.baseURL || undefined,
					}),
				})
				if (!r.ok) throw new Error("failed to store API key")
			} else if (draft.mode === "oauth_import") {
				const r = await call("/atlas/auth/codex/import", { method: "POST" })
				const body = (await r.json().catch(() => ({}))) as { imported?: boolean; reason?: string }
				if (!r.ok || !body.imported) throw new Error(body.reason || "Codex login was not importable")
			}

			const res = await call("/atlas/config", {
				method: "PATCH",
				headers: { "content-type": "application/json" },
				body: JSON.stringify({
					expected_revision: revision(),
					changes: {
						"provider.name": draft.provider,
						"provider.model": draft.model,
						"provider.auth_mode": draft.mode,
						"provider.base_url": draft.baseURL || null,
						"provider.reasoning_effort": draft.effort,
					},
				}),
			})
			const body = (await res.json().catch(() => ({}))) as {
				revision?: number
				error?: { message?: string }
			}
			if (!res.ok) throw new Error(body.error?.message || "save failed")
			if (typeof body.revision === "number") setRevision(body.revision)
			setPendingApiKey("")
			toast.show({ message: "Provider configuration saved", variant: "success" })

			const statusRes = await call("/atlas/provider/status")
			if (statusRes.ok) setStatus((await statusRes.json()) as ProviderStatus)
		} catch (err) {
			toast.show({ message: err instanceof Error ? err.message : "save failed", variant: "error" })
		} finally {
			setBusy(false)
			openMenu()
		}
	}

	return null
}
