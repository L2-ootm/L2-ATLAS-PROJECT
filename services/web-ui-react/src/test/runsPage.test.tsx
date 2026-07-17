import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Runs from '../routes/Runs';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return { ...actual, listRuns: vi.fn() };
});

vi.mock('../lib/useGatewayHealth', () => ({
	useGatewayHealth: () => ({ online: true, epoch: 1 })
}));

beforeEach(() => {
	vi.mocked(api.listRuns).mockResolvedValue({
		runs: [
			{
				id: 'run-a111', mission_id: 'mission-a', session_id: 'abcdef01-session',
				status: 'succeeded', started_at: '2026-07-16T18:00:00Z', finished_at: '2026-07-16T18:00:04Z',
				summary: 'a', agent_runtime: 'native', mission_title: 'Second prompt'
			},
			{
				id: 'run-a000', mission_id: 'mission-b', session_id: 'abcdef01-session',
				status: 'succeeded', started_at: '2026-07-16T17:00:00Z', finished_at: '2026-07-16T17:00:03Z',
				summary: 'b', agent_runtime: 'native', mission_title: 'First prompt'
			},
			{
				id: 'run-c000', mission_id: 'mission-c', session_id: '76543210-session',
				status: 'failed', started_at: '2026-07-15T17:00:00Z', finished_at: '2026-07-15T17:00:02Z',
				summary: 'c', agent_runtime: 'native', mission_title: 'Other session'
			}
		]
	});
});

describe('Runs session hierarchy', () => {
	it('shows sessions first, then reveals prompt runs and opens their evidence', async () => {
		render(
			<MemoryRouter initialEntries={['/runs']}>
				<Routes>
					<Route path="/runs" element={<Runs />} />
					<Route path="/runs/:id" element={<div>RUN EVIDENCE</div>} />
				</Routes>
			</MemoryRouter>
		);

		expect(await screen.findByText('2 SESSIONS · 3 RUNS')).toBeInTheDocument();
		expect(screen.queryByText('RUN run-a111')).not.toBeInTheDocument();

		const sessionRow = screen.getByText('abcdef01').closest('[role="button"]');
		expect(sessionRow).not.toBeNull();
		await userEvent.click(sessionRow!);
		expect(screen.getByText('RUN run-a111')).toBeInTheDocument();
		expect(screen.getByText('RUN run-a000')).toBeInTheDocument();

		await userEvent.click(screen.getByText('RUN run-a111').closest('[role="button"]')!);
		expect(await screen.findByText('RUN EVIDENCE')).toBeInTheDocument();
	});
});
