import { describe, expect, it } from 'vitest';
import {
	actorDisplayName,
	hasNamedRole,
	subagentFromConsoleEvent,
	subagentsFromSurfaceEvents
} from '../lib/subagents';

const payload = (phase: string, extra: Record<string, unknown> = {}) => ({
	orchestration: 'subagent',
	subagent_id: 'actor-12345678',
	phase,
	goal: 'Inspect the runtime',
	...extra
});

describe('subagent activity projection', () => {
	it('folds replayed lifecycle rows to one latest actor state', () => {
		const actors = subagentsFromSurfaceEvents([
			{ session_id: 's', seq: 1, kind: 'task', run_id: 'r', occurred_at: '', payload_json: JSON.stringify(payload('running')) },
			{ session_id: 's', seq: 2, kind: 'task', run_id: 'r', occurred_at: '', payload_json: JSON.stringify(payload('working', { tool: 'search', tool_count: 2 })) }
		]);
		expect(actors).toHaveLength(1);
		expect(actors[0]).toMatchObject({ phase: 'working', tool: 'search', toolCount: 2 });
	});

	it('retains the live child run link for actor stream projection', () => {
		const actors = subagentsFromSurfaceEvents([
			{ session_id: 's', seq: 1, kind: 'task', run_id: 'parent', occurred_at: '', payload_json: JSON.stringify(payload('working', { child_run_id: 'child-run' })) }
		]);
		expect(actors[0].childRunId).toBe('child-run');
	});

	it('maps a failed completion to a failed visual state', () => {
		const actor = subagentFromConsoleEvent({ type: 'task', content: payload('completed', { status: 'failed' }) });
		expect(actor?.phase).toBe('failed');
	});

	it('maps a timed-out completion to a failed terminal state', () => {
		const actor = subagentFromConsoleEvent({ type: 'task', content: payload('completed', { status: 'timeout' }) });
		expect(actor?.phase).toBe('failed');
	});

	it('carries the roster role through the projection so a collaborator can be named', () => {
		const actor = subagentFromConsoleEvent({
			type: 'task',
			content: payload('working', { role: 'Precision Reviewer' })
		});
		expect(actor?.role).toBe('Precision Reviewer');
	});

	it('defaults role to empty rather than undefined when the producer omits it', () => {
		const actor = subagentFromConsoleEvent({ type: 'task', content: payload('working') });
		expect(actor?.role).toBe('');
	});
});

describe('actor display name', () => {
	const actor = (id: string, role: string, goal = 'Inspect the runtime') => ({ id, role, goal });

	it('names a team member by its roster role label', () => {
		expect(actorDisplayName(actor('actor-12345678', 'Precision Reviewer'))).toBe('Precision Reviewer');
	});

	it('treats the schema default role as an absence of identity, not a name', () => {
		expect(actorDisplayName(actor('actor-12345678', 'worker'))).toBe('Actor 12345678');
		expect(hasNamedRole({ role: 'worker' })).toBe(false);
		expect(hasNamedRole({ role: 'Precision Reviewer' })).toBe(true);
	});

	it('falls back to the short actor id when no role was ever set', () => {
		expect(actorDisplayName(actor('actor-abcdef01', ''))).toBe('Actor ABCDEF01');
	});

	it('never names an actor after its goal — the goal changes, the identity does not', () => {
		expect(actorDisplayName(actor('actor-12345678', '', 'Review the precision model')))
			.not.toBe('Review the precision model');
	});

	it('uses the requested goal for a dispatch slot that has no actor id yet', () => {
		expect(actorDisplayName(actor('dispatch:call-1:0', '', 'Review the precision model')))
			.toBe('Review the precision model');
	});
});
