import { describe, expect, it } from 'bun:test';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import {
	ATLAS_COMMANDS,
	executeEvidenceCommand,
	expandCommandTemplate,
	formatEvidenceReceipt,
	parseEvidenceCommand
} from '../src/adapter/commands';
import {
	GatewayClient,
	type EvidenceContentPage,
	type EvidenceReceipt,
	type SurfaceSession
} from '../src/adapter/gateway';

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
		expect(names).toEqual(['init', 'review', 'dream', 'distill', 'goal', 'mission', 'deep-research']);
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

describe('Evidence Plane terminal commands', () => {
	const session: SurfaceSession = { id: 'surf-1', owner_token: 'owner-1', state: 'active' };

	it('renders the shared semantic receipt and unknown ui.kind fallback', () => {
		const receipt: EvidenceReceipt = {
			ui_kind: 'file.change',
			operation: 'edit',
			path: 'services/runtime/worker.py',
			additions: 42,
			deletions: 11,
			actor: 'EULER',
			duration_ms: 184,
			evidence_id: 'file-1',
			availability: 'partial'
		};
		const rendered = formatEvidenceReceipt(receipt, 'normal');
		for (const field of [
			'EDITED',
			'services/runtime/worker.py',
			'+42',
			'-11',
			'EULER',
			'184 ms',
			'file-1',
			'partial'
		]) {
			expect(rendered).toContain(field);
		}
		expect(
			formatEvidenceReceipt(
				{ ...receipt, ui_kind: 'future.semantic.kind', evidence_id: 'evidence-9' },
				'verbose'
			)
		).toContain('EVIDENCE');
	});

	it('parses explicit inspect/fetch/export commands', () => {
		expect(parseEvidenceCommand('/evidence inspect change-set change-1')).toEqual({
			action: 'inspect',
			target: 'change-set',
			id: 'change-1'
		});
		expect(parseEvidenceCommand('/evidence fetch patch file-1')).toEqual({
			action: 'fetch',
			target: 'patch',
			id: 'file-1'
		});
		expect(parseEvidenceCommand('/evidence export result result-1')).toEqual({
			action: 'export',
			target: 'result',
			id: 'result-1'
		});
		expect(parseEvidenceCommand('/evidence fetch patch')).toBeNull();
	});

	it('pages metadata and streams bounded authorized content without local diffing', async () => {
		const requests: Array<{ path: string; query: string; owner: string | null }> = [];
		const content = '0123456789';
		const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url);
			requests.push({
				path: url.pathname,
				query: url.search,
				owner: new Headers(init?.headers).get('X-Atlas-Surface-Owner')
			});
			if (url.pathname === '/v1/change-sets/change-1/files') {
				return Response.json({
					files: [
						{
							id: 'file-1',
							change_set_id: 'change-1',
							path: 'services/runtime/worker.py',
							operation: 'edit',
							availability: 'partial',
							additions: 42,
							deletions: 11
						}
					],
					next_cursor: 'opaque:file:2'
				});
			}
			if (url.pathname === '/v1/file-changes/file-1/patch') {
				const offset = Number(url.searchParams.get('offset') ?? 0);
				const end = Math.min(offset + 4, content.length);
				const page: EvidenceContentPage = {
					availability: 'available',
					media_type: 'text/x-diff',
					sha256: 'abc',
					range: { start: offset, end, total_bytes: content.length },
					content: content.slice(offset, end)
				};
				return Response.json(page, { status: end < content.length ? 206 : 200 });
			}
			return new Response('{}', { status: 404 });
		}) as typeof fetch;

		const gateway = new GatewayClient(GW, fetchImpl);
		const inspected = await executeEvidenceCommand(
			gateway,
			session,
			{ action: 'inspect', target: 'change-set', id: 'change-1' },
			() => undefined
		);
		expect(inspected.availability).toBe('partial');
		expect(inspected.evidence_ids).toEqual(['file-1']);

		const chunks: string[] = [];
		const fetched = await executeEvidenceCommand(
			gateway,
			session,
			{ action: 'fetch', target: 'patch', id: 'file-1' },
			(chunk) => chunks.push(chunk)
		);
		expect(fetched.availability).toBe('available');
		expect(chunks.join('')).toBe(content);
		expect(requests.every((request) => request.owner === 'owner-1')).toBe(true);
		const patchRequests = requests.filter((request) => request.path.includes('/patch'));
		expect(patchRequests.length).toBeGreaterThan(1);
		for (const request of patchRequests) {
			const limit = Number(new URLSearchParams(request.query).get('limit'));
			expect(limit).toBeGreaterThan(0);
			expect(limit).toBeLessThanOrEqual(64 * 1024);
		}
	});

	it('preserves typed unavailable content without emitting bytes', async () => {
		const fetchImpl = (async () =>
			Response.json({
				availability: 'redacted',
				media_type: 'text/plain',
				sha256: null,
				range: { start: 0, end: 0, total_bytes: 0 }
			})) as typeof fetch;
		const chunks: string[] = [];
		const result = await executeEvidenceCommand(
			new GatewayClient(GW, fetchImpl),
			session,
			{ action: 'export', target: 'result', id: 'result-1' },
			(chunk) => chunks.push(chunk)
		);
		expect(result.availability).toBe('redacted');
		expect(chunks).toEqual([]);
	});
});
