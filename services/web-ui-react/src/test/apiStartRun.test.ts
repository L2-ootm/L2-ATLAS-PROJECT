import { afterEach, describe, expect, it, vi } from 'vitest';
import { GATEWAY, startRun } from '../lib/api';

describe('startRun', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('serializes long-horizon options with gateway field names', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ run: { id: 'run-1' } }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);
		vi.stubGlobal('fetch', fetchMock);

		await startRun('mission/1', 'native', true, 'surface-1', {
			goalMode: true,
			judgeModel: 'openai-codex/gpt-5.4-mini',
			maxRuns: 8
		});

		expect(fetchMock).toHaveBeenCalledWith(
			`${GATEWAY}/v1/missions/mission%2F1/run`,
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({
					agent: 'native',
					execute: true,
					surface_session_id: 'surface-1',
					goal_mode: true,
					judge_model: 'openai-codex/gpt-5.4-mini',
					max_runs: 8
				})
			})
		);
	});
});
