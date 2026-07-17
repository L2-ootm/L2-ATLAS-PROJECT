import { describe, expect, it } from 'bun:test';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import { parseMissionCommand } from '../src/adapter/commands';
import { GatewayClient } from '../src/adapter/gateway';

const GW = 'http://127.0.0.1:8484';

interface CapturedGateway {
	surfaces: Array<Record<string, unknown>>;
	missions: Array<Record<string, unknown>>;
	runs: Array<Record<string, unknown>>;
	closes: number;
	stream?: string;
}

function stubGateway(state: CapturedGateway): typeof fetch {
	return (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();
		const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};

		if (method === 'POST' && path === '/v1/surface-sessions') {
			state.surfaces.push(body);
			return Response.json({
				id: `surf-${state.surfaces.length}`,
				owner_token: `owner-${state.surfaces.length}`,
				state: 'active'
			});
		}
		if (method === 'POST' && /^\/v1\/surface-sessions\/[^/]+\/close$/.test(path)) {
			state.closes += 1;
			return Response.json({ closed: true });
		}
		if (method === 'POST' && path === '/v1/missions') {
			state.missions.push(body);
			return Response.json({
				mission: { id: `mission-${state.missions.length}`, title: body['title'], status: 'pending' }
			});
		}
		if (method === 'POST' && /^\/v1\/missions\/[^/]+\/run$/.test(path)) {
			state.runs.push(body);
			return Response.json({ run: { id: `run-${state.runs.length}` }, executing: true });
		}
		if (method === 'GET' && /^\/v1\/runs\/[^/]+\/stream$/.test(path)) {
			return new Response(state.stream ?? 'event: end\ndata: {"status":"succeeded"}\n\n', {
				headers: { 'content-type': 'text/event-stream' }
			});
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

function captured(): CapturedGateway {
	return { surfaces: [], missions: [], runs: [], closes: 0 };
}

async function createSession(handle: ReturnType<typeof createAtlasFetchHandle>): Promise<string> {
	const response = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
	return ((await response.json()) as { id: string }).id;
}

async function settle(): Promise<void> {
	for (let i = 0; i < 4; i++) await new Promise((resolve) => setTimeout(resolve, 5));
}

describe('long-horizon mission command grammar', () => {
	it('parses only exact /goal and /mission aliases, including local status forms', () => {
		expect(parseMissionCommand('/goal ship the release')).toEqual({
			alias: 'goal',
			action: 'start',
			objective: 'ship the release'
		});
		expect(parseMissionCommand('/mission\nreconcile the ledgers')).toEqual({
			alias: 'mission',
			action: 'start',
			objective: 'reconcile the ledgers'
		});
		expect(parseMissionCommand('/goal')).toEqual({ alias: 'goal', action: 'status' });
		expect(parseMissionCommand('/mission status')).toEqual({ alias: 'mission', action: 'status' });
		expect(parseMissionCommand('/goalkeeper ship')).toBeNull();
		expect(parseMissionCommand('/Goal ship')).toBeNull();
	});

	it('GatewayClient serializes all optional goal-run fields', async () => {
		let sent: Record<string, unknown> | undefined;
		const client = new GatewayClient(
			GW,
			(async (_input: RequestInfo | URL, init?: RequestInit) => {
				sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
				return Response.json({ run: { id: 'run-goal' } });
			}) as typeof fetch
		);

		expect(await client.startRun('mission-1', 'native', 'surface-1', true, 'openai/gpt-5', 7)).toBe(
			'run-goal'
		);
		expect(sent).toEqual({
			agent: 'native',
			execute: true,
			surface_session_id: 'surface-1',
			goal_mode: true,
			judge_model: 'openai/gpt-5',
			max_runs: 7
		});
	});

	it('both aliases create the objective verbatim and start in goal mode without forwarding slash text', async () => {
		for (const alias of ['goal', 'mission'] as const) {
			const state = captured();
			const handle = createAtlasFetchHandle({
				gateway: GW,
				fetchImpl: stubGateway(state),
				permissionPollMs: 0,
				heartbeatMs: 0
			});
			const sessionID = await createSession(handle);
			await handle.fetch(`http://donor.local/session/${sessionID}/prompt_async`, {
				method: 'POST',
				body: JSON.stringify({
					parts: [{ type: 'text', text: `/${alias} ship the release` }],
					model: { providerID: 'openai', modelID: 'gpt-5' }
				})
			});
			await settle();

			expect(state.missions).toHaveLength(1);
			expect(state.missions[0]?.['intent']).toBe('ship the release');
			expect(state.runs[0]?.['goal_mode']).toBe(true);
			expect(state.surfaces[0]).toMatchObject({ provider: 'openai', model: 'gpt-5' });
			const messages = await handle.fetch(`http://donor.local/session/${sessionID}/message`);
			expect(JSON.stringify(await messages.json())).not.toContain(`/${alias}`);
			await handle.chat.dispose();
		}
	});

	it('the server command route delegates aliases to the same ChatAdapter grammar', async () => {
		const state = captured();
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state),
			permissionPollMs: 0,
			heartbeatMs: 0
		});
		const sessionID = await createSession(handle);
		await handle.fetch(`http://donor.local/session/${sessionID}/command`, {
			method: 'POST',
			body: JSON.stringify({
				command: 'mission',
				arguments: 'reconcile the ledgers',
				model: 'anthropic/claude-opus'
			})
		});

		expect(state.missions[0]?.['intent']).toBe('reconcile the ledgers');
		expect(state.runs[0]?.['goal_mode']).toBe(true);
		expect(state.surfaces[0]).toMatchObject({ provider: 'anthropic', model: 'claude-opus' });
		await handle.chat.dispose();
	});

	it('bare/status aliases render a local explanation without creating a mission', async () => {
		const state = captured();
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(state) });
		const sessionID = await createSession(handle);
		for (const text of ['/goal', '/mission status']) {
			await handle.fetch(`http://donor.local/session/${sessionID}/prompt_async`, {
				method: 'POST',
				body: JSON.stringify({ parts: [{ type: 'text', text }] })
			});
		}

		expect(state.surfaces).toHaveLength(0);
		expect(state.missions).toHaveLength(0);
		const messages = await handle.fetch(`http://donor.local/session/${sessionID}/message`);
		expect(JSON.stringify(await messages.json())).toContain('Mission status is not exposed');
	});

	it('recreates the owned surface when the selected prompt model changes', async () => {
		const state = captured();
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state),
			permissionPollMs: 0,
			heartbeatMs: 0
		});
		const sessionID = await createSession(handle);
		for (const model of [
			{ providerID: 'openai', modelID: 'gpt-5' },
			{ providerID: 'anthropic', modelID: 'claude-opus' }
		]) {
			await handle.fetch(`http://donor.local/session/${sessionID}/prompt_async`, {
				method: 'POST',
				body: JSON.stringify({ parts: [{ type: 'text', text: `use ${model.modelID}` }], model })
			});
			await settle();
		}

		expect(state.surfaces).toEqual([
			{ surface_kind: 'tui', workspace_kind: 'global', provider: 'openai', model: 'gpt-5' },
			{ surface_kind: 'tui', workspace_kind: 'global', provider: 'anthropic', model: 'claude-opus' }
		]);
		expect(state.closes).toBe(1);
		await handle.chat.dispose();
	});

	it('accepts next-run deltas on the same assistant response after a continuation event', async () => {
		const state = captured();
		state.stream = [
			'event: audit\ndata: {"event_type":"llm_call","data":{"text":"first run result"}}\n\n',
			'event: continuation\ndata: {"reason":"more work remains"}\n\n',
			'event: audit\ndata: {"event_type":"llm_delta","data":{"delta":"second run"}}\n\n',
			'event: audit\ndata: {"event_type":"llm_call","data":{"text":"second run result"}}\n\n',
			'event: end\ndata: {"status":"succeeded"}\n\n'
		].join('');
		const handle = createAtlasFetchHandle({
			gateway: GW,
			fetchImpl: stubGateway(state),
			permissionPollMs: 0,
			heartbeatMs: 0
		});
		const sessionID = await createSession(handle);
		await handle.fetch(`http://donor.local/session/${sessionID}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ type: 'text', text: '/goal finish the migration' }] })
		});
		await settle();

		const response = await handle.fetch(`http://donor.local/session/${sessionID}/message`);
		const messages = (await response.json()) as Array<{
			info: { role: string; time: { completed?: number } };
			parts: Array<{ type: string; text?: string }>;
		}>;
		const assistant = messages.find((message) => message.info.role === 'assistant');
		expect(assistant?.parts.some((part) => part.text === 'Continuing mission: more work remains')).toBe(true);
		expect(assistant?.parts.filter((part) => part.type === 'text').map((part) => part.text)).toEqual([
			'first run result',
			'second run result'
		]);
		expect(assistant?.info.time.completed).toBeNumber();
		await handle.chat.dispose();
	});
});
