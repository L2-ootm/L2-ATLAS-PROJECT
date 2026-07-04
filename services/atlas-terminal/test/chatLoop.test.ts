import { describe, expect, it } from 'bun:test';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import type { DonorEvent } from '../src/adapter/events';

const GW = 'http://127.0.0.1:8484';

interface StubState {
	missions: Array<{ id: string; title: string; intent: string }>;
	runsStarted: Array<{ missionID: string; agent: string; surface: string }>;
	approvals: Array<Record<string, unknown>>;
	decisions: Array<{ id: string; decision: string }>;
	ownerHeaders: string[];
}

/** Full ATLAS gateway stub for the chat loop: surface, mission, run, SSE, approvals. */
function stubGateway(state: StubState, sseFrames: string[]): typeof fetch {
	return (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();
		const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, string>) : {};
		const owner = new Headers(init?.headers).get('X-Atlas-Surface-Owner');
		if (owner) state.ownerHeaders.push(owner);

		if (method === 'POST' && path === '/v1/surface-sessions') {
			return Response.json({ id: 'surf-1', owner_token: 'tok-secret', state: 'active' });
		}
		if (method === 'POST' && path === '/v1/missions') {
			const mission = { id: `mis-${state.missions.length + 1}`, title: body['title']!, intent: body['intent']! };
			state.missions.push(mission);
			return Response.json({ mission: { id: mission.id, title: mission.title, status: 'pending' } });
		}
		const runMatch = /^\/v1\/missions\/([^/]+)\/run$/.exec(path);
		if (method === 'POST' && runMatch) {
			state.runsStarted.push({
				missionID: runMatch[1]!,
				agent: body['agent']!,
				surface: body['surface_session_id']!
			});
			return Response.json({ run: { id: 'run-1' }, executing: true });
		}
		if (method === 'GET' && path === '/v1/runs/run-1/stream') {
			return new Response(sseFrames.join(''), {
				status: 200,
				headers: { 'content-type': 'text/event-stream' }
			});
		}
		if (method === 'GET' && path === '/v1/surface-sessions/surf-1/approvals') {
			return Response.json({ approvals: state.approvals });
		}
		const decideMatch = /^\/v1\/surface-sessions\/surf-1\/approvals\/([^/]+)\/(approve|reject)$/.exec(path);
		if (method === 'POST' && decideMatch) {
			state.decisions.push({ id: decideMatch[1]!, decision: decideMatch[2]! });
			return Response.json({ ok: true });
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

function frame(event: string, data: unknown): string {
	return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function newState(): StubState {
	return { missions: [], runsStarted: [], approvals: [], decisions: [], ownerHeaders: [] };
}

async function settle(): Promise<void> {
	// let the background stream promise chain flush
	for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
}

describe('STAGE 1 chat loop', () => {
	it('prompt_async drives mission→run→SSE and emits donor part events', async () => {
		const state = newState();
		const sse = [
			frame('audit', {
				event_type: 'tool_call',
				tool_name: 'read_file',
				tool_call_id: 'call-1',
				data: { summary: 'read README.md' }
			}),
			frame('audit', {
				event_type: 'tool_completed',
				tool_name: 'read_file',
				tool_call_id: 'call-1',
				data: { summary: 'ok' }
			}),
			frame('audit', { event_type: 'llm_call', data: { text: 'Here is the answer.' } }),
			frame('end', { status: 'succeeded' })
		];
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state, sse),
			permissionPollMs: 0
		});
		const events: DonorEvent[] = [];
		handle.bus.subscribe((e) => events.push(e));

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		expect(session.id.startsWith('ses_')).toBe(true);

		const res = await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ type: 'text', text: 'review the repo' }] })
		});
		expect(res.status).toBe(200);
		await settle();

		// gateway side: mission carries the prompt; run bound to the owned surface
		expect(state.missions[0]!.intent).toBe('review the repo');
		expect(state.runsStarted[0]).toEqual({ missionID: 'mis-1', agent: 'native', surface: 'surf-1' });

		// donor side: transcript is user text → tool running/completed → assistant text
		const msgRes = await handle.fetch(`http://donor.local/session/${session.id}/message`);
		const messages = (await msgRes.json()) as Array<{
			info: { role: string; time: { completed?: number } };
			parts: Array<{ type: string; text?: string; state?: { status: string } }>;
		}>;
		expect(messages).toHaveLength(2);
		expect(messages[0]!.parts[0]!.text).toBe('review the repo');
		const assistant = messages[1]!;
		expect(assistant.info.time.completed).toBeGreaterThan(0);
		const tool = assistant.parts.find((p) => p.type === 'tool');
		expect(tool?.state?.status).toBe('completed');
		expect(assistant.parts.some((p) => p.type === 'text' && p.text === 'Here is the answer.')).toBe(true);

		// event bus: busy → parts → idle, in donor vocabulary
		const types = events.map((e) => e.type);
		expect(types).toContain('session.status');
		expect(types).toContain('message.part.updated');
		expect(types).toContain('session.idle');
	});

	it('bridges pending approvals to permission.asked and replies through the gateway', async () => {
		const state = newState();
		state.approvals.push({
			id: 'appr-1',
			tool_name: 'shell',
			risk_level: 'high',
			args: 'rm -rf build',
			summary: 'shell command',
			status: 'pending',
			run_id: 'run-1',
			surface_session_id: 'surf-1',
			requested_at: new Date().toISOString()
		});
		const sse = [frame('end', { status: 'succeeded' })];
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state, sse),
			permissionPollMs: 0
		});
		const events: DonorEvent[] = [];
		handle.bus.subscribe((e) => events.push(e));

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'do it' }] })
		});
		await settle();

		await handle.chat.pollPermissions();
		const asked = events.find((e) => e.type === 'permission.asked');
		expect(asked).toBeDefined();
		expect((asked!.properties as { id: string }).id).toBe('appr-1');
		// approvals were read with the owner token
		expect(state.ownerHeaders).toContain('tok-secret');

		const reply = await handle.fetch('http://donor.local/permission/appr-1/reply', {
			method: 'POST',
			body: JSON.stringify({ response: 'once' })
		});
		expect(reply.status).toBe(200);
		expect(state.decisions).toEqual([{ id: 'appr-1', decision: 'approve' }]);
		expect(events.some((e) => e.type === 'permission.replied')).toBe(true);

		// second poll must not re-ask
		await handle.chat.pollPermissions();
		expect(events.filter((e) => e.type === 'permission.asked')).toHaveLength(1);
	});

	it('run failure surfaces as session.error and an honest transcript line', async () => {
		const state = newState();
		const sse = [
			frame('audit', { event_type: 'tool_call', data: { transition: 'failed', summary: 'provider 401' } }),
			frame('end', { status: 'failed' })
		];
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state, sse),
			permissionPollMs: 0
		});
		const events: DonorEvent[] = [];
		handle.bus.subscribe((e) => events.push(e));

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'break' }] })
		});
		await settle();

		expect(events.some((e) => e.type === 'session.error')).toBe(true);
		const msgs = (await (await handle.fetch(`http://donor.local/session/${session.id}/message`)).json()) as Array<{
			parts: Array<{ text?: string }>;
		}>;
		expect(msgs[1]!.parts.some((p) => p.text === 'provider 401')).toBe(true);
	});

	it('SSE /event stream replays recent chat events to late subscribers', async () => {
		const state = newState();
		const sse = [frame('end', { status: 'succeeded' })];
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state, sse),
			permissionPollMs: 0
		});
		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'hi' }] })
		});
		await settle();

		// open the donor event stream AFTER the activity — replay must include it
		const res = await handle.fetch('http://donor.local/event');
		const reader = res.body!.getReader();
		const decoder = new TextDecoder();
		let text = '';
		// events are enqueued as separate chunks; read until replay is visible
		for (let i = 0; i < 20 && !text.includes('message.part.updated'); i++) {
			const { value, done } = await reader.read();
			if (done) break;
			text += decoder.decode(value, { stream: true });
		}
		expect(text).toContain('server.connected');
		expect(text).toContain('session.updated');
		expect(text).toContain('message.part.updated');
		await reader.cancel();
	});
});
