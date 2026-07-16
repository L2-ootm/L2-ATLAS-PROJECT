import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Missions from '../routes/Missions';
import * as api from '../lib/api';

// Regression coverage: useGatewayHealth's `epoch` only bumps on a
// reconnect transition, so a mission/session created elsewhere (another
// surface, the TUI, Discord) while the gateway stayed up never triggered a
// refetch — the list looked stuck until a manual page refresh. Missions.tsx
// now also polls on a steady interval (MISSIONS_POLL_MS).

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listMissions: vi.fn(),
		listProjects: vi.fn(),
		createMission: vi.fn(),
		checkHealth: vi.fn()
	};
});

function renderMissions() {
	return render(
		<MemoryRouter>
			<Missions />
		</MemoryRouter>
	);
}

describe('Missions live updates', () => {
	beforeEach(() => {
		vi.mocked(api.checkHealth).mockResolvedValue({ status: 'ok', db: 'ok' });
		vi.mocked(api.listProjects).mockResolvedValue({ projects: [], count: 0 });
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('refetches on a steady poll without a gateway reconnect', async () => {
		const emptyResult = { missions: [] as api.Mission[], count: 0 };
		const withNewSession = {
			missions: [
				{
					id: 'm-1',
					title: 'Session started elsewhere',
					intent: 'created from the TUI',
					status: 'PENDING',
					created_at: '2026-07-15T12:00:00Z'
				} as api.Mission
			],
			count: 1
		};
		// useGatewayHealth's module-level heartbeat can itself bump `epoch` on
		// its very first tick (online: null -> true reads as a "reconnect"),
		// so the exact initial call count isn't deterministic here — every
		// call before the steady poll fires returns the empty result; only
		// asserting the *delta* the steady poll itself causes is reliable.
		vi.mocked(api.listMissions).mockResolvedValue(emptyResult);

		vi.useFakeTimers();
		renderMissions();

		await act(async () => {});
		expect(screen.queryByText('Session started elsewhere')).not.toBeInTheDocument();
		const callsBeforePoll = vi.mocked(api.listMissions).mock.calls.length;
		vi.mocked(api.listMissions).mockResolvedValue(withNewSession);

		// No gateway reconnect (epoch unchanged) — just the steady poll firing.
		await act(async () => {
			await vi.advanceTimersByTimeAsync(8000);
		});

		expect(vi.mocked(api.listMissions).mock.calls.length).toBeGreaterThan(callsBeforePoll);
		expect(screen.getByText('Session started elsewhere')).toBeInTheDocument();
	});
});
