import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SessionsPage from '../routes/SessionsPage';
import * as api from '../lib/api';
import type { SessionDashboardEntry, SessionDashboardPage } from '../lib/surfaceContracts';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return { ...actual, listSurfaceSessionsDashboard: vi.fn() };
});

vi.mock('../lib/useGatewayHealth', () => ({
	useGatewayHealth: () => ({ online: true, epoch: 1 })
}));

function makeSession(overrides: Partial<SessionDashboardEntry> = {}): SessionDashboardEntry {
	return {
		id: 'surf-aaaaaaaa-1111',
		surface: { kind: 'webui', session_id: 'tab-1' },
		workspace: { kind: 'global', root: '/atlas', project_id: null },
		agent: 'atlas',
		model: { provider: 'anthropic', model_id: 'claude-opus-4' },
		permission_mode: 'ask',
		state: 'active',
		mission_id: 'mission-x',
		mission_title: 'Analyze codebase architecture',
		mission_intent: 'Investigate the sessions dashboard data model.',
		run_id: 'run-1',
		heartbeat_at: '2026-07-19T00:00:00+00:00',
		heartbeat_age_seconds: 12,
		health: 'healthy',
		actor_count: 2,
		active_actor_count: 1,
		actors: [
			{
				id: 'actor-1',
				parent_id: null,
				goal: 'Search for API patterns across the codebase',
				status: 'running',
				model: 'claude-opus-4',
				mode: 'joined',
				depth: 1,
				heartbeat_age_seconds: 5,
				health: 'healthy',
				created_at: '2026-07-19T00:00:00+00:00'
			}
		],
		created_at: '2026-07-19T00:00:00+00:00',
		updated_at: '2026-07-19T00:00:00+00:00',
		...overrides
	};
}

function page(sessions: SessionDashboardEntry[], overrides: Partial<SessionDashboardPage> = {}): SessionDashboardPage {
	return { sessions, total: sessions.length, limit: 25, offset: 0, ...overrides };
}

beforeEach(() => {
	vi.mocked(api.listSurfaceSessionsDashboard).mockReset();
});

function renderPage() {
	render(
		<MemoryRouter initialEntries={['/sessions']}>
			<Routes>
				<Route path="/sessions" element={<SessionsPage />} />
			</Routes>
		</MemoryRouter>
	);
}

describe('SessionsPage', () => {
	it('renders a session row with mission title, agent/model, state, and actor counts', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(page([makeSession()]));

		renderPage();

		expect(await screen.findByText('Analyze codebase architecture')).toBeInTheDocument();
		expect(screen.getByText('atlas')).toBeInTheDocument();
		expect(screen.getByText('claude-opus-4')).toBeInTheDocument();
		expect(screen.getByText('ACTIVE')).toBeInTheDocument();
		expect(screen.getByText(/2 ACTORS/)).toBeInTheDocument();
		expect(screen.getByText(/1 ACTIVE/)).toBeInTheDocument();
	});

	it('renders the top-level actor tree row under its session', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(page([makeSession()]));

		renderPage();

		expect(await screen.findByText('Search for API patterns across the codebase')).toBeInTheDocument();
		expect(screen.getByText('running')).toBeInTheDocument();
	});

	it('falls back to surface kind + short id when no mission is attached', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(
			page([makeSession({ mission_id: null, mission_title: null, mission_intent: null })])
		);

		renderPage();

		expect(await screen.findByText('WEBUI · surf-aaa')).toBeInTheDocument();
	});

	it('shows an empty state when there are zero sessions', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(page([]));

		renderPage();

		expect(await screen.findByText('No sessions yet')).toBeInTheDocument();
	});

	it('shows an offline state when the fetch rejects', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockRejectedValue(new Error('network down'));

		renderPage();

		expect(await screen.findByText('Gateway unavailable')).toBeInTheDocument();
	});

	it('toggling LIVE ONLY refetches with activeOnly=true and resets pagination', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(page([makeSession()]));

		renderPage();
		await screen.findByText('Analyze codebase architecture');

		await userEvent.click(screen.getByText('LIVE ONLY'));

		await waitFor(() => {
			expect(api.listSurfaceSessionsDashboard).toHaveBeenLastCalledWith(
				expect.objectContaining({ activeOnly: true, offset: 0 })
			);
		});
	});

	it('renders a distinct health dot per health status', async () => {
		vi.mocked(api.listSurfaceSessionsDashboard).mockResolvedValue(
			page([
				makeSession({ id: 's-healthy', health: 'healthy' }),
				makeSession({ id: 's-stale', health: 'stale', mission_title: 'Stale mission' }),
				makeSession({ id: 's-orphaned', health: 'orphaned', mission_title: 'Orphaned mission', state: 'reclaimed' }),
				makeSession({ id: 's-unknown', health: 'unknown', mission_title: 'Unknown mission', state: 'completed' })
			])
		);

		renderPage();
		await screen.findByText('Analyze codebase architecture');

		const dots = document.querySelectorAll('[data-health]');
		const healths = Array.from(dots).map((el) => el.getAttribute('data-health'));
		expect(healths).toEqual(expect.arrayContaining(['healthy', 'stale', 'orphaned', 'unknown']));
	});
});
