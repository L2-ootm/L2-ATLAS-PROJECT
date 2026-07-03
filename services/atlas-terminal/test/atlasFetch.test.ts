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
		const res = await f('http://donor.local/session', { method: 'POST' });
		expect(res.status).toBe(501);
		const body = (await res.json()) as { error: string; path: string };
		expect(body.error).toBe('not_implemented');
		expect(body.path).toBe('POST /session');
	});

	it('propagates gateway failure as 502 rather than fake data', async () => {
		const f = createAtlasFetch({ gateway: GW, fetchImpl: stubGateway({}) });
		const res = await f('http://donor.local/config');
		expect(res.status).toBe(502);
	});
});
