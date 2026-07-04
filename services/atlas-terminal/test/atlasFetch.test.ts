import { describe, expect, it } from 'bun:test';
import { createAtlasFetch } from '../src/adapter/atlasFetch';

// Stubbed ATLAS gateway: the adapter must translate donor paths onto these.
function stubGateway(routes: Record<string, unknown>): typeof fetch {
	return (async (input: RequestInfo | URL) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		if (path in routes) return new Response(JSON.stringify(routes[path]), { status: 200 });
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

const GW = 'http://127.0.0.1:8484';

describe('createAtlasFetch', () => {
	it('maps donor GET /config onto the masked ATLAS config', async () => {
		const f = createAtlasFetch({
			gateway: GW,
			fetchImpl: stubGateway({
				'/v1/config': { revision: 3, provider: { name: 'openai-codex', model: 'gpt-5.5' } }
			})
		});
		const res = await f('http://donor.local/config');
		expect(res.status).toBe(200);
		const body = (await res.json()) as { model: string };
		expect(body.model).toBe('openai-codex/gpt-5.5');
	});

	it('projects the model registry into donor provider maps with the active default', async () => {
		const f = createAtlasFetch({
			gateway: GW,
			fetchImpl: stubGateway({
				'/v1/models': {
					models: [
						{ model_id: 'gpt-5.5', provider: 'openai-codex', active: true },
						{ model_id: 'gpt-5.4-mini', provider: 'openai-codex', active: true },
						{ model_id: 'dead', provider: 'legacy', active: false }
					]
				},
				'/v1/config': { provider: { name: 'openai-codex', model: 'gpt-5.5' } }
			})
		});
		const res = await f('http://donor.local/config/providers');
		expect(res.status).toBe(200);
		const body = (await res.json()) as {
			providers: Array<{ id: string; models: Record<string, unknown> }>;
			default: Record<string, string>;
		};
		expect(body.providers).toHaveLength(1);
		expect(Object.keys(body.providers[0]!.models)).toEqual(['gpt-5.5', 'gpt-5.4-mini']);
		expect(body.default['openai-codex']).toBe('gpt-5.5');
	});

	it('serves the donor SSE channel with the connected handshake', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubGateway({}) });
		const res = await f('http://donor.local/event');
		expect(res.status).toBe(200);
		expect(res.headers.get('content-type')).toBe('text/event-stream');
		const reader = res.body!.getReader();
		const { value } = await reader.read();
		const text = new TextDecoder().decode(value);
		expect(text).toContain('server.connected');
		await reader.cancel();
	});

	it('answers unimplemented donor endpoints with a typed 501, never a crash', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubGateway({}) });
		const res = await f('http://donor.local/mcp', { method: 'POST' });
		expect(res.status).toBe(501);
		const body = (await res.json()) as { error: string; path: string };
		expect(body.error).toBe('not_implemented');
		expect(body.path).toBe('POST /mcp');
	});

	it('propagates gateway failure as 502 rather than fake data', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubGateway({}) });
		const res = await f('http://donor.local/config');
		expect(res.status).toBe(502);
	});
});

// ATLAS-native settings surface (ported from services/atlas-tui): the adapter
// forwards these 1:1 onto the real gateway contract, no shape translation.
function stubSettingsGateway(): { fetch: typeof fetch; patched: unknown[] } {
	const patched: unknown[] = [];
	const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();

		if (method === 'GET' && path === '/v1/config') {
			return Response.json({
				schema_version: 1,
				revision: 4,
				provider: { name: 'openrouter', model: 'anthropic/claude-sonnet-4', auth_mode: 'api_key', api_key: '', base_url: null }
			});
		}
		if (method === 'PATCH' && path === '/v1/config') {
			const body = JSON.parse(String(init!.body)) as { expected_revision: number; changes: Record<string, unknown> };
			patched.push(body);
			return Response.json({
				schema_version: 1,
				revision: body.expected_revision + 1,
				provider: {
					name: body.changes['provider.name'],
					model: body.changes['provider.model'],
					auth_mode: body.changes['provider.auth_mode'],
					api_key: '',
					base_url: body.changes['provider.base_url']
				}
			});
		}
		if (method === 'GET' && path === '/v1/provider/status') {
			return Response.json({
				provider: 'openrouter',
				model: 'anthropic/claude-sonnet-4',
				auth_mode: 'api_key',
				auth_mode_label: 'API key',
				base_url: null,
				credentials_present: true,
				mock_mode: false,
				remediation: null,
				reasoning_effort: null,
				privacy_warning: null
			});
		}
		if (method === 'POST' && path === '/v1/auth/providers') {
			return Response.json({ provider: 'openrouter', auth_type: 'api', status: 'stored', source: 'operator', health: 'unknown', redacted_hint: '***', updated_at: null, remediation: null });
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
	return { fetch: fetchImpl, patched };
}

describe('ATLAS-native settings routes', () => {
	it('round-trips GET/PATCH /atlas/config onto GET/PATCH /v1/config', async () => {
		const { fetch: fetchImpl, patched } = stubSettingsGateway();
		const f = createAtlasFetch({ gateway: GW, fetchImpl });

		const got = await f('http://donor.local/atlas/config');
		expect(got.status).toBe(200);
		const snapshot = (await got.json()) as { revision: number; provider: { name: string } };
		expect(snapshot.revision).toBe(4);
		expect(snapshot.provider.name).toBe('openrouter');

		const patchRes = await f('http://donor.local/atlas/config', {
			method: 'PATCH',
			body: JSON.stringify({
				expected_revision: 4,
				changes: { 'provider.name': 'anthropic', 'provider.model': 'claude-opus-4-8', 'provider.auth_mode': 'api_key' }
			})
		});
		expect(patchRes.status).toBe(200);
		const patchedSnapshot = (await patchRes.json()) as { revision: number; provider: { name: string } };
		expect(patchedSnapshot.revision).toBe(5);
		expect(patchedSnapshot.provider.name).toBe('anthropic');
		expect(patched).toHaveLength(1);
	});

	it('forwards /atlas/provider/status onto GET /v1/provider/status untranslated', async () => {
		const { fetch: fetchImpl } = stubSettingsGateway();
		const f = createAtlasFetch({ gateway: GW, fetchImpl });
		const res = await f('http://donor.local/atlas/provider/status');
		expect(res.status).toBe(200);
		const body = (await res.json()) as { provider: string; mock_mode: boolean; credentials_present: boolean };
		expect(body.provider).toBe('openrouter');
		expect(body.mock_mode).toBe(false);
		expect(body.credentials_present).toBe(true);
	});

	it('forwards /atlas/auth/providers onto POST /v1/auth/providers', async () => {
		const { fetch: fetchImpl } = stubSettingsGateway();
		const f = createAtlasFetch({ gateway: GW, fetchImpl });
		const res = await f('http://donor.local/atlas/auth/providers', {
			method: 'POST',
			body: JSON.stringify({ provider: 'openrouter', api_key: 'sk-test' })
		});
		expect(res.status).toBe(200);
		const body = (await res.json()) as { status: string };
		expect(body.status).toBe('stored');
	});
});

// FreeLLMAPI sidecar control — mirrors services/atlas-tui's /freellmapi slash command.
function stubFreellmapiGateway(running: boolean): typeof fetch {
	return (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();
		if (method === 'GET' && path === '/v1/freellmapi/status') {
			return Response.json({ running, base_url: 'http://127.0.0.1:3001', dir: '/tmp/freellmapi', installed: true, remediation: '' });
		}
		if (method === 'POST' && path === '/v1/freellmapi/start') {
			return Response.json({ ok: true, message: 'started' });
		}
		if (method === 'POST' && path === '/v1/freellmapi/stop') {
			return Response.json({ ok: true, message: 'stopped' });
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

describe('ATLAS-native freellmapi routes', () => {
	it('forwards /atlas/freellmapi/status onto GET /v1/freellmapi/status', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubFreellmapiGateway(true) });
		const res = await f('http://donor.local/atlas/freellmapi/status');
		expect(res.status).toBe(200);
		const body = (await res.json()) as { running: boolean; base_url: string };
		expect(body.running).toBe(true);
		expect(body.base_url).toBe('http://127.0.0.1:3001');
	});

	it('forwards /atlas/freellmapi/start and /stop onto the matching POST routes', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubFreellmapiGateway(false) });
		const startRes = await f('http://donor.local/atlas/freellmapi/start', { method: 'POST' });
		expect((await startRes.json()) as { ok: boolean; message: string }).toEqual({ ok: true, message: 'started' });
		const stopRes = await f('http://donor.local/atlas/freellmapi/stop', { method: 'POST' });
		expect((await stopRes.json()) as { ok: boolean; message: string }).toEqual({ ok: true, message: 'stopped' });
	});
});
