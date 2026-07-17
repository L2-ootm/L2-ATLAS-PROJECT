import { describe, expect, it } from 'vitest';
import type { RunWithMission } from '../lib/api';
import { groupRunsBySession } from '../lib/runSessions';

function run(id: string, session_id: string | null, minute: number, status = 'succeeded'): RunWithMission {
	return {
		id,
		session_id,
		mission_id: `mission-${id}`,
		mission_title: `prompt ${id}`,
		status,
		started_at: `2026-07-16T12:${String(minute).padStart(2, '0')}:00Z`,
		finished_at: `2026-07-16T12:${String(minute).padStart(2, '0')}:10Z`,
		summary: `answer ${id}`
	};
}

describe('run session grouping', () => {
	it('groups prompt-runs by real session and orders turns newest first', () => {
		const groups = groupRunsBySession([
			run('a', 'session-1', 1),
			run('b', 'session-1', 3),
			run('c', 'session-2', 2)
		]);
		expect(groups.map((group) => group.id)).toEqual(['session-1', 'session-2']);
		expect(groups[0].runs.map((item) => item.id)).toEqual(['b', 'a']);
	});

	it('keeps legacy null-session runs separate', () => {
		const groups = groupRunsBySession([run('a', null, 1), run('b', null, 2)]);
		expect(groups).toHaveLength(2);
		expect(groups.map((group) => group.id)).toEqual(['run:b', 'run:a']);
	});

	it('raises active and mixed failure status to the session level', () => {
		const [active] = groupRunsBySession([
			run('a', 'session-1', 1, 'succeeded'),
			run('b', 'session-1', 2, 'running')
		]);
		expect(active).toMatchObject({ active: true, status: 'RUNNING' });
		const [partial] = groupRunsBySession([
			run('a', 'session-1', 1, 'succeeded'),
			run('b', 'session-1', 2, 'failed')
		]);
		expect(partial.status).toBe('PARTIAL');
	});
});
