import { describe, expect, it } from 'bun:test';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';
import { readGitBranch } from '../src/util/gitBranch';

const GW = 'http://127.0.0.1:8484';

// ── readGitBranch ──────────────────────────────────────────────────────────

function gitFixture(head: string): string {
	const root = mkdtempSync(join(tmpdir(), 'atlas-vcs-'));
	mkdirSync(join(root, '.git'));
	writeFileSync(join(root, '.git', 'HEAD'), head);
	return root;
}

describe('readGitBranch', () => {
	it('reads the branch from .git/HEAD', () => {
		const root = gitFixture('ref: refs/heads/feature-x\n');
		expect(readGitBranch(root)).toBe('feature-x');
	});

	it('walks up from a nested directory to the repo root', () => {
		const root = gitFixture('ref: refs/heads/main\n');
		const nested = join(root, 'src', 'deep');
		mkdirSync(nested, { recursive: true });
		expect(readGitBranch(nested)).toBe('main');
	});

	it('returns the short commit id on detached HEAD', () => {
		const root = gitFixture('0123456789abcdef0123456789abcdef01234567\n');
		expect(readGitBranch(root)).toBe('01234567');
	});

	it('follows a worktree-style .git pointer file', () => {
		const root = mkdtempSync(join(tmpdir(), 'atlas-vcs-wt-'));
		const gitdir = join(root, 'real-gitdir');
		mkdirSync(gitdir);
		writeFileSync(join(gitdir, 'HEAD'), 'ref: refs/heads/wt-branch\n');
		const work = join(root, 'worktree');
		mkdirSync(work);
		writeFileSync(join(work, '.git'), `gitdir: ${gitdir}\n`);
		expect(readGitBranch(work)).toBe('wt-branch');
	});

	it('returns undefined outside any git repository', () => {
		const bare = mkdtempSync(join(tmpdir(), 'atlas-novcs-'));
		expect(readGitBranch(bare)).toBeUndefined();
	});
});

// ── wired bootstrap routes + surface heartbeat ─────────────────────────────

interface HeartbeatState {
	surfacesCreated: number;
	heartbeats: Array<{ surface: string; ownerToken: string }>;
	/** status the next heartbeat responds with */
	heartbeatStatus: number;
}

function stubGateway(state: HeartbeatState, sseFrames: string[]): typeof fetch {
	return (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const path = new URL(url).pathname;
		const method = (init?.method ?? 'GET').toUpperCase();
		const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, string>) : {};

		if (method === 'POST' && path === '/v1/surface-sessions') {
			state.surfacesCreated += 1;
			return Response.json({ id: `surf-${state.surfacesCreated}`, owner_token: `tok-${state.surfacesCreated}`, state: 'active' });
		}
		const hbMatch = /^\/v1\/surface-sessions\/([^/]+)\/heartbeat$/.exec(path);
		if (method === 'POST' && hbMatch) {
			state.heartbeats.push({ surface: hbMatch[1]!, ownerToken: body['owner_token']! });
			if (state.heartbeatStatus !== 200) return new Response('{"error":"gone"}', { status: state.heartbeatStatus });
			return Response.json({ id: hbMatch[1], owner_token: body['owner_token'], state: 'active' });
		}
		if (method === 'POST' && path === '/v1/missions') {
			return Response.json({ mission: { id: 'mis-1', title: body['title'], status: 'pending' } });
		}
		if (method === 'POST' && /^\/v1\/missions\/[^/]+\/run$/.test(path)) {
			return Response.json({ run: { id: 'run-1' }, executing: true });
		}
		if (method === 'GET' && path === '/v1/runs/run-1/stream') {
			return new Response(sseFrames.join(''), { status: 200, headers: { 'content-type': 'text/event-stream' } });
		}
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
}

function frame(event: string, data: unknown): string {
	return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

async function settle(): Promise<void> {
	for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
}

function newState(): HeartbeatState {
	return { surfacesCreated: 0, heartbeats: [], heartbeatStatus: 200 };
}

describe('wired bootstrap routes', () => {
	it('GET /project lists the single ATLAS project matching /project/current', async () => {
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(newState(), []), permissionPollMs: 0, heartbeatMs: 0 });
		const list = (await (await handle.fetch('http://donor.local/project')).json()) as Array<{ id: string; worktree: string }>;
		const current = (await (await handle.fetch('http://donor.local/project/current')).json()) as { id: string; worktree: string };
		expect(list).toHaveLength(1);
		expect(list[0]!.id).toBe(current.id);
		expect(list[0]!.worktree).toBe(current.worktree);
	});

	it('GET /vcs reports this repo branch (adapter runs inside a git checkout)', async () => {
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(newState(), []), permissionPollMs: 0, heartbeatMs: 0 });
		const res = await handle.fetch('http://donor.local/vcs');
		expect(res.status).toBe(200);
		const body = (await res.json()) as { branch?: string };
		// test process cwd is inside the ATLAS repo — a branch must be present
		expect(typeof body.branch).toBe('string');
		expect(body.branch!.length).toBeGreaterThan(0);
	});

	it('GET /session/status reflects real idle/busy state per session', async () => {
		const state = newState();
		const sse = [frame('end', { status: 'succeeded' })];
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(state, sse), permissionPollMs: 0, heartbeatMs: 0 });

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };

		let statuses = (await (await handle.fetch('http://donor.local/session/status')).json()) as Record<string, { type: string }>;
		expect(statuses[session.id]).toEqual({ type: 'idle' });

		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'go' }] })
		});
		await settle();

		statuses = (await (await handle.fetch('http://donor.local/session/status')).json()) as Record<string, { type: string }>;
		expect(statuses[session.id]).toEqual({ type: 'idle' }); // run completed
	});
});

describe('surface heartbeat', () => {
	it('heartbeatOnce posts the owner lease keepalive for the active surface', async () => {
		const state = newState();
		const sse = [frame('end', { status: 'succeeded' })];
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(state, sse), permissionPollMs: 0, heartbeatMs: 0 });

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'hi' }] })
		});
		await settle();

		await handle.chat.heartbeatOnce();
		expect(state.heartbeats).toEqual([{ surface: 'surf-1', ownerToken: 'tok-1' }]);
	});

	it('drops a reaped surface on 4xx heartbeat and re-surfaces on the next prompt', async () => {
		const state = newState();
		const sse = [frame('end', { status: 'succeeded' })];
		const handle = createAtlasFetchHandle({ gateway: GW, fetchImpl: stubGateway(state, sse), permissionPollMs: 0, heartbeatMs: 0 });

		const created = await handle.fetch('http://donor.local/session', { method: 'POST', body: '{}' });
		const session = (await created.json()) as { id: string };
		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'first' }] })
		});
		await settle();
		expect(state.surfacesCreated).toBe(1);

		// gateway reaped the surface (restart / SURF-05 sweep)
		state.heartbeatStatus = 410;
		await handle.chat.heartbeatOnce();

		await handle.fetch(`http://donor.local/session/${session.id}/prompt_async`, {
			method: 'POST',
			body: JSON.stringify({ parts: [{ text: 'second' }] })
		});
		await settle();
		expect(state.surfacesCreated).toBe(2); // fresh surface, no stale lease reuse
	});
});
