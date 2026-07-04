/**
 * ATLAS fetch adapter — the seam that lets the ATLAS donor TUI run over
 * the ATLAS Rust gateway without a second backend.
 *
 * The donor client (`createOpencodeClient({ fetch })`) accepts an injected
 * fetch; this module implements that fetch. It speaks the donor's HTTP+SSE
 * surface on the front and translates every call to ATLAS gateway contracts
 * on the back. ATLAS keeps runtime/provider/config/audit/session authority.
 *
 * STAGE 1 scope (see docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md):
 * config/provider projection (STAGE 0) + the chat loop — donor sessions,
 * prompt_async → mission/run, SSE part bridge, and permission round trips —
 * plus empty-but-valid bootstrap stubs so the donor UI can boot.
 */

import { ChatAdapter } from './chat';
import { ATLAS_COMMANDS, findAtlasCommand, expandCommandTemplate } from './commands';
import { EventBus, type DonorEvent } from './events';
import { GatewayClient } from './gateway';

export interface AtlasFetchOptions {
	/** ATLAS gateway base, e.g. http://127.0.0.1:8484 */
	gateway: string;
	/** Injectable for tests; defaults to global fetch. */
	fetchImpl?: typeof fetch;
	/** Approval poll cadence in ms; 0 disables the timer (tests poll manually). */
	permissionPollMs?: number;
}

interface AtlasConfig {
	revision?: number;
	provider?: {
		name?: string;
		model?: string;
		auth_mode?: string;
		base_url?: string;
		reasoning_effort?: string;
	};
	mock_mode?: boolean;
}

interface AtlasModelEntry {
	model_id: string;
	provider: string;
	active: boolean;
}

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

function notImplemented(path: string): Response {
	return json(
		{
			error: 'not_implemented',
			path,
			remediation:
				'atlas-terminal STAGE 0 adapter — this donor endpoint is translated in a later stage'
		},
		501
	);
}

/** GET /config — donor shape (subset): the fields the donor TUI reads early. */
async function handleConfig(gw: string, f: typeof fetch): Promise<Response> {
	const res = await f(`${gw}/v1/config`);
	if (!res.ok) return json({ error: 'gateway', status: res.status }, 502);
	const cfg = (await res.json()) as AtlasConfig;
	return json({
		model: cfg.provider?.name && cfg.provider?.model ? `${cfg.provider.name}/${cfg.provider.model}` : undefined,
		theme: 'atlas',
		username: 'operator'
	});
}

/**
 * ATLAS-native settings surface (not part of the donor's own API) — mirrors
 * services/atlas-tui's internal/client contract (Config/PatchConfig/
 * StoreAPIKey/ImportCodex/ProviderStatus) so the atlas-terminal settings
 * dialog reuses the exact same gateway routes the working Go TUI already
 * uses. Passed through with no shape translation — this is ATLAS's own
 * contract end to end, not a donor-compat projection.
 */
async function handleAtlasConfigGet(gw: string, f: typeof fetch): Promise<Response> {
	const res = await f(`${gw}/v1/config`);
	if (!res.ok) return json({ error: 'gateway', status: res.status }, 502);
	return json(await res.json());
}

async function handleAtlasConfigPatch(gw: string, f: typeof fetch, body: Record<string, unknown>): Promise<Response> {
	const res = await f(`${gw}/v1/config`, {
		method: 'PATCH',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
	const payload = await res.json().catch(() => ({}));
	return json(payload, res.status);
}

async function handleAtlasAuthProviders(gw: string, f: typeof fetch, body: Record<string, unknown>): Promise<Response> {
	const res = await f(`${gw}/v1/auth/providers`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
	const payload = await res.json().catch(() => ({}));
	return json(payload, res.status);
}

async function handleAtlasAuthCodexImport(gw: string, f: typeof fetch): Promise<Response> {
	const res = await f(`${gw}/v1/auth/codex/import`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
	const payload = await res.json().catch(() => ({}));
	return json(payload, res.status);
}

async function handleAtlasProviderStatus(gw: string, f: typeof fetch): Promise<Response> {
	const res = await f(`${gw}/v1/provider/status`);
	if (!res.ok) return json({ error: 'gateway', status: res.status }, 502);
	return json(await res.json());
}

/**
 * GET /config/providers — donor shape: providers with their model maps.
 * Projected from the ATLAS model registry + active provider resolution.
 */
async function handleProviders(gw: string, f: typeof fetch): Promise<Response> {
	const [modelsRes, cfgRes] = await Promise.all([f(`${gw}/v1/models`), f(`${gw}/v1/config`)]);
	if (!modelsRes.ok) return json({ error: 'gateway', status: modelsRes.status }, 502);
	const { models } = (await modelsRes.json()) as { models: AtlasModelEntry[] };
	const cfg = cfgRes.ok ? ((await cfgRes.json()) as AtlasConfig) : {};

	const byProvider = new Map<string, AtlasModelEntry[]>();
	for (const m of models) {
		if (!m.active) continue;
		const key = m.provider || 'unknown';
		const bucket = byProvider.get(key);
		if (bucket) bucket.push(m);
		else byProvider.set(key, [m]);
	}
	const providers = [...byProvider.entries()].map(([id, list]) => ({
		id,
		name: id,
		models: Object.fromEntries(list.map((m) => [m.model_id, { id: m.model_id, name: m.model_id }]))
	}));
	const active = cfg.provider;
	return json({
		providers,
		default: active?.name && active?.model ? { [active.name]: active.model } : {}
	});
}

/**
 * GET /event — the donor's global SSE channel: connected handshake, recent
 * replay, then live chat/permission events from the bus.
 */
function handleEventStream(bus: EventBus): Response {
	const encoder = new TextEncoder();
	let keepalive: ReturnType<typeof setInterval> | undefined;
	let unsubscribe: (() => void) | undefined;
	const stream = new ReadableStream<Uint8Array>({
		start(controller) {
			const send = (payload: unknown) => {
				try {
					controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
				} catch {
					unsubscribe?.();
					if (keepalive) clearInterval(keepalive);
				}
			};
			send({ type: 'server.connected', properties: {} });
			const forward = (event: DonorEvent) => send(event);
			bus.replayRecent(forward);
			unsubscribe = bus.subscribe(forward);
			keepalive = setInterval(() => {
				try {
					controller.enqueue(encoder.encode(': keepalive\n\n'));
				} catch {
					unsubscribe?.();
					if (keepalive) clearInterval(keepalive);
				}
			}, 15_000);
		},
		cancel() {
			unsubscribe?.();
			if (keepalive) clearInterval(keepalive);
		}
	});
	return new Response(stream, {
		status: 200,
		headers: { 'content-type': 'text/event-stream' }
	});
}

/** Real command list — see src/adapter/commands.ts for the ATLAS-authored templates. */
function handleCommandList(): Response {
	return json(
		ATLAS_COMMANDS.map((c) => ({
			name: c.name,
			description: c.description,
			source: 'command',
			template: c.template,
			subtask: false,
			hints: []
		}))
	);
}

/** Donor POST /session/{id}/command — expand the template, run it through the normal chat loop. */
async function handleSessionCommand(
	chat: ChatAdapter,
	sessionID: string,
	body: Record<string, unknown>
): Promise<Response> {
	const name = typeof body['command'] === 'string' ? body['command'] : '';
	const args = typeof body['arguments'] === 'string' ? body['arguments'] : '';
	const command = findAtlasCommand(name);
	if (!command) return json({ error: 'not_found', message: `unknown command: ${name}` }, 404);
	const text = expandCommandTemplate(command.template, args);
	await chat.promptAsync(sessionID, { parts: [{ type: 'text', text }] });
	return json({
		info: { id: `msg_${name}`, sessionID, role: 'assistant', time: { created: Date.now() } },
		parts: []
	});
}

/** Empty-but-valid bootstrap stubs so the donor UI boots before STAGE 2 fidelity. */
const BOOTSTRAP_STUBS: Record<string, unknown> = {
	'/skill': [],
	'/lsp': [],
	'/formatter': [],
	'/mcp': {},
	'/question': [],
	'/question/never-ask': [],
	'/session/status': {},
	'/experimental/resource': {},
	'/vcs': { branch: null },
	'/project': []
};

export interface AtlasFetchHandle {
	fetch: typeof fetch;
	chat: ChatAdapter;
	bus: EventBus;
}

/** Build the injected fetch for the donor client, exposing the chat adapter. */
export function createAtlasFetchHandle(opts: AtlasFetchOptions): AtlasFetchHandle {
	const gw = opts.gateway.replace(/\/+$/, '');
	const f = opts.fetchImpl ?? fetch;
	const bus = new EventBus();
	const chat = new ChatAdapter({
		gateway: new GatewayClient(gw, f),
		bus,
		permissionPollMs: opts.permissionPollMs
	});

	const atlasFetch = (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
		const path = new URL(url, 'http://donor.local').pathname;
		const readBody = async (): Promise<Record<string, unknown>> => {
			try {
				if (init?.body) return JSON.parse(String(init.body)) as Record<string, unknown>;
				if (input instanceof Request) return (await input.clone().json()) as Record<string, unknown>;
			} catch {
				/* tolerate empty/non-JSON bodies */
			}
			return {};
		};

		try {
			if (method === 'GET' && path === '/config') return handleConfig(gw, f);
			if (method === 'GET' && path === '/config/providers') return handleProviders(gw, f);
			if (method === 'GET' && (path === '/event' || path === '/global/event')) {
				return handleEventStream(bus);
			}
			if (method === 'GET' && path === '/app') {
				return json({ hostname: 'atlas', git: false, path: { cwd: process.cwd(), root: process.cwd() } });
			}
			if (method === 'GET' && path === '/path') {
				return json({ cwd: process.cwd(), root: process.cwd(), directory: process.cwd() });
			}
			if (method === 'GET' && path === '/project/current') {
				return json({ id: 'atlas', worktree: process.cwd(), time: { created: 0 } });
			}
			if (method === 'GET' && path === '/agent') {
				return json([
					{ name: 'native', description: 'ATLAS native runtime', mode: 'primary', builtIn: true },
					{ name: 'claude_code', description: 'Claude Code runtime', mode: 'primary', builtIn: true }
				]);
			}
			if (method === 'GET' && path === '/provider') return handleProviders(gw, f);

			// ── ATLAS-native settings surface (ported from services/atlas-tui) ──
			if (method === 'GET' && path === '/atlas/config') return handleAtlasConfigGet(gw, f);
			if (method === 'PATCH' && path === '/atlas/config') return handleAtlasConfigPatch(gw, f, await readBody());
			if (method === 'POST' && path === '/atlas/auth/providers') return handleAtlasAuthProviders(gw, f, await readBody());
			if (method === 'POST' && path === '/atlas/auth/codex/import') return handleAtlasAuthCodexImport(gw, f);
			if (method === 'GET' && path === '/atlas/provider/status') return handleAtlasProviderStatus(gw, f);
			if (method === 'GET' && path === '/command') return handleCommandList();

			// ── chat loop ──
			if (path === '/session' && method === 'POST') {
				const body = await readBody();
				const title = typeof body['title'] === 'string' && body['title'] ? body['title'] : 'New session';
				return json(chat.createSession(title));
			}
			if (path === '/session' && method === 'GET') return json(chat.listSessions());
			const sessionMatch = /^\/session\/([^/]+)(\/.*)?$/.exec(path);
			if (sessionMatch) {
				const sessionID = decodeURIComponent(sessionMatch[1]!);
				const rest = sessionMatch[2] ?? '';
				if (method === 'GET' && rest === '') {
					const session = chat.getSession(sessionID);
					return session ? json(session) : json({ error: 'not_found' }, 404);
				}
				if (method === 'GET' && rest === '/message') return json(chat.listMessages(sessionID));
				if (method === 'POST' && (rest === '/prompt_async' || rest === '/prompt')) {
					await chat.promptAsync(sessionID, await readBody());
					return json({ started: true });
				}
				if (method === 'POST' && rest === '/abort') return json(await chat.abort(sessionID));
				if (method === 'POST' && rest === '/command') return handleSessionCommand(chat, sessionID, await readBody());
				const permMatch = /^\/permissions\/([^/]+)$/.exec(rest);
				if (method === 'POST' && permMatch) {
					const body = await readBody();
					await chat.replyPermission(
						decodeURIComponent(permMatch[1]!),
						typeof body['response'] === 'string' ? body['response'] : 'once'
					);
					return json(true);
				}
			}
			if (method === 'GET' && path === '/permission') return json(chat.listPermissions());
			const replyMatch = /^\/permission\/([^/]+)\/reply$/.exec(path);
			if (method === 'POST' && replyMatch) {
				const body = await readBody();
				await chat.replyPermission(
					decodeURIComponent(replyMatch[1]!),
					typeof body['response'] === 'string' ? body['response'] : 'once'
				);
				return json(true);
			}

			if (method === 'GET' && path in BOOTSTRAP_STUBS) return json(BOOTSTRAP_STUBS[path]);
			return notImplemented(`${method} ${path}`);
		} catch (err) {
			return json({ error: 'adapter', message: err instanceof Error ? err.message : String(err) }, 500);
		}
	}) as typeof fetch;

	return { fetch: atlasFetch, chat, bus };
}

/** Back-compat STAGE 0 entry: just the injected fetch. */
export function createAtlasFetch(opts: AtlasFetchOptions): typeof fetch {
	return createAtlasFetchHandle(opts).fetch;
}
