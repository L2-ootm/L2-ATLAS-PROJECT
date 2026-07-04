import { describe, expect, it } from 'bun:test';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import { ATLAS_COMMANDS, expandCommandTemplate } from '../src/adapter/commands';

const GW = 'http://127.0.0.1:8484';

interface StubState {
	missions: Array<{ title: string; intent: string }>;
}

function stubGateway(state: StubState): typeof fetch {
	return (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();
		const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, string>) : {};

		if (method === 'POST' && path === '/v1/surface-sessions') {
			return Response.json({ id: 'surf-1', owner_token: 'tok', state: 'active' });
		}
		if (method === 'POST' && path === '/v1/missions') {
			state.missions.push({ title: body['title']!, intent: body['intent']! });
			return Response.json({ mission: { id: 'mis-1', title: body['title'], status: 'pending' } });
		}
		if (method === 'POST' && /^\/v1\/missions\/[^/]+\/run$/.test(path)) {
			return Response.json({ run: { id: 'run-1' }, executing: true });
		}
		if (method === 'GET' && path === '/v1/runs/run-1/stream') {
			return new Response('event: end\ndata: {"status":"succeeded"}\n\n', {
				status: 200,
				headers: { 'content-type': 'text/event-stream' }
			});
		}
		if (method === 'GET' && path === '/v1/surface-sessions/surf-1/approvals') {
			return Response.json({ approvals: [] });
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

async function settle(): Promise<void> {
	for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
}

describe('ATLAS built-in slash commands', () => {
	it('GET /command lists every ATLAS-authored command with its template', async () => {
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway({ missions: [] }) });
		const res = await handle.fetch('http://donor.local/command');
		expect(res.status).toBe(200);
		const list = (await res.json()) as Array<{ name: string; template: string }>;
		const names = list.map((c) => c.name);
		expect(names).toEqual(['init', 'review', 'dream', 'distill', 'goal', 'deep-research']);
		expect(list.every((c) => c.template.length > 0)).toBe(true);
	});

	it('POST /session/{id}/command expands the template and drives it through mission/run', async () => {
		const state: StubState = { missions: [] };
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(state), permissionPollMs: 0 });

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };

		const res = await handle.fetch(`http://donor.local/session/${session.id}/command`, {
			method: 'POST',
			body: JSON.stringify({ command: 'deep-research', arguments: 'ATLAS gateway architecture' })
		});
		expect(res.status).toBe(200);
		await settle();

		expect(state.missions).toHaveLength(1);
		expect(state.missions[0]!.intent).toContain('ATLAS gateway architecture');
		expect(state.missions[0]!.intent).toContain('multi-source, fact-checked research report');
	});

	it('rejects an unknown command name with 404 instead of silently no-op-ing', async () => {
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway({ missions: [] }) });
		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		const res = await handle.fetch(`http://donor.local/session/${session.id}/command`, {
			method: 'POST',
			body: JSON.stringify({ command: 'not-a-real-command', arguments: '' })
		});
		expect(res.status).toBe(404);
	});
});

describe('expandCommandTemplate', () => {
	it('substitutes $ARGUMENTS when the template has the placeholder', () => {
		const goal = ATLAS_COMMANDS.find((c) => c.name === 'goal')!;
		const out = expandCommandTemplate(goal.template, 'ship WS-B installer');
		expect(out).toContain('ship WS-B installer');
		expect(out).not.toContain('$ARGUMENTS');
	});

	it('appends arguments when the template has no placeholder', () => {
		const init = ATLAS_COMMANDS.find((c) => c.name === 'init')!;
		const out = expandCommandTemplate(init.template, 'focus on the CLI');
		expect(out.endsWith('focus on the CLI')).toBe(true);
	});
});
