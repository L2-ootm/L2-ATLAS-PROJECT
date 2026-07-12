import { describe, expect, it } from 'bun:test';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import { GatewayClient, GatewayError } from '../src/adapter/gateway';

const GW = 'http://127.0.0.1:8484';

function frame(event: string, data: unknown): string {
	return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe('stream idle watchdog', () => {
	it('aborts a silent run stream and reports a 504 GatewayError', async () => {
		// SSE body that sends one frame then goes silent (closed only AFTER the
		// assertion — the deadline must fire while the stream is still open)
		let ctrl: ReadableStreamDefaultController<Uint8Array> | undefined;
		const silentAfterOne = new ReadableStream<Uint8Array>({
			start(controller) {
				ctrl = controller;
				controller.enqueue(new TextEncoder().encode(frame('audit', { event_type: 'llm_call', data: { text: 'hi' } })));
			}
		});
		const fetchImpl = (async () =>
			new Response(silentAfterOne, { status: 200, headers: { 'content-type': 'text/event-stream' } })) as unknown as typeof fetch;

		const gw = new GatewayClient(GW, fetchImpl, 50 /* ms idle deadline */);
		const events: string[] = [];
		const started = Date.now();
		await expect(gw.streamRun('run-1', (e) => events.push(e.name))).rejects.toThrow(/no stream activity/);
		expect(Date.now() - started).toBeLessThan(5_000);
		expect(events).toEqual(['audit']); // the frame before the hang still flowed
		try {
			ctrl?.close(); // release the stream so the test process can exit
		} catch {
			/* already canceled by the watchdog */
		}
	});

	it('keepalive comments reset the watchdog (no false timeout)', async () => {
		const body = new ReadableStream<Uint8Array>({
			async start(controller) {
				const enc = new TextEncoder();
				// keepalives at 20ms cadence beat a 60ms deadline; then finish
				for (let i = 0; i < 5; i++) {
					await new Promise((r) => setTimeout(r, 20));
					controller.enqueue(enc.encode(': keepalive\n\n'));
				}
				controller.enqueue(enc.encode(frame('end', { status: 'succeeded' })));
				controller.close();
			}
		});
		const fetchImpl = (async () =>
			new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } })) as unknown as typeof fetch;

		const gw = new GatewayClient(GW, fetchImpl, 60);
		const events: string[] = [];
		await gw.streamRun('run-1', (e) => events.push(e.name));
		expect(events).toEqual(['end']);
	});
});

describe('gateway error normalization', () => {
	it('surfaces GatewayError from the chat loop as a typed 502, not a 500 adapter bug', async () => {
		const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
			const path = new URL(url).pathname;
			const method = (init?.method ?? 'GET').toUpperCase();
			if (method === 'POST' && path === '/v1/surface-sessions') {
				return Response.json({ id: 'surf-1', owner_token: 'tok-1', state: 'active' });
			}
			if (method === 'POST' && path === '/v1/missions') {
				return new Response('mission store unavailable', { status: 503 });
			}
			return new Response('{}', { status: 404 });
		}) as typeof fetch;

		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl, permissionPollMs: 0, heartbeatMs: 0 });
		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };

		const res = await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'go' }] })
		});
		expect(res.status).toBe(502);
		const body = (await res.json()) as { error: string; status: number };
		expect(body.error).toBe('gateway');
		expect(body.status).toBe(503);
	});

	it('GatewayError carries status and path for diagnostics', () => {
		const err = new GatewayError(410, '/v1/surface-sessions/surf-1/heartbeat', 'gone');
		expect(err.status).toBe(410);
		expect(err.message).toContain('/v1/surface-sessions/surf-1/heartbeat');
	});
});
