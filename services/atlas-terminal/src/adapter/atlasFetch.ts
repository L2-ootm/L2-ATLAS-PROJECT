/**
 * ATLAS fetch adapter — the seam that lets the MiMo-Code donor TUI run over
 * the ATLAS Rust gateway without a second backend.
 *
 * The donor client (`createOpencodeClient({ fetch })`) accepts an injected
 * fetch; this module implements that fetch. It speaks the donor's HTTP+SSE
 * surface on the front and translates every call to ATLAS gateway contracts
 * on the back. ATLAS keeps runtime/provider/config/audit/session authority.
 *
 * STAGE 0 scope (see docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md):
 * config, provider/model projection, and the SSE event channel skeleton.
 * Session/prompt/permission translation lands in STAGE 1.
 */

export interface AtlasFetchOptions {
	/** ATLAS gateway base, e.g. http://127.0.0.1:8484 */
	gateway: string;
	/** Injectable for tests; defaults to global fetch. */
	fetchImpl?: typeof fetch;
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
 * GET /event — the donor's global SSE channel. STAGE 0 emits the connected
 * handshake and keeps the stream open; STAGE 1 bridges ATLAS SurfaceEvents
 * (run parts, session status, permission.asked) onto donor event names.
 */
function handleEventStream(): Response {
	const encoder = new TextEncoder();
	let keepalive: ReturnType<typeof setInterval> | undefined;
	const stream = new ReadableStream<Uint8Array>({
		start(controller) {
			const send = (payload: unknown) =>
				controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
			send({ type: 'server.connected', properties: {} });
			keepalive = setInterval(() => {
				try {
					controller.enqueue(encoder.encode(': keepalive\n\n'));
				} catch {
					if (keepalive) clearInterval(keepalive);
				}
			}, 15_000);
		},
		cancel() {
			if (keepalive) clearInterval(keepalive);
		}
	});
	return new Response(stream, {
		status: 200,
		headers: { 'content-type': 'text/event-stream' }
	});
}

/** Build the injected fetch for the donor client. */
export function createAtlasFetch(opts: AtlasFetchOptions): typeof fetch {
	const gw = opts.gateway.replace(/\/+$/, '');
	const f = opts.fetchImpl ?? fetch;

	const atlasFetch = (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
		const path = new URL(url, 'http://donor.local').pathname;

		if (method === 'GET' && path === '/config') return handleConfig(gw, f);
		if (method === 'GET' && path === '/config/providers') return handleProviders(gw, f);
		if (method === 'GET' && (path === '/event' || path === '/global/event')) return handleEventStream();
		if (method === 'GET' && path === '/app') {
			return json({ hostname: 'atlas', git: false, path: { cwd: process.cwd(), root: process.cwd() } });
		}
		return notImplemented(`${method} ${path}`);
	}) as typeof fetch;

	return atlasFetch;
}
