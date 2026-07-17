import { describe, expect, it } from 'vitest';
import { subagentFromConsoleEvent, subagentsFromSurfaceEvents } from '../lib/subagents';

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
});
