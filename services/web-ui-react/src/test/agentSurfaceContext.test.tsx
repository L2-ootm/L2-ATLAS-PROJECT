import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	RECONNECT_KEY,
	useAgentSurface
} from '../context/AgentSurfaceContext';
import { AgentSurfaceProvider } from '../context/AgentSurfaceProvider';
import type { SurfaceSession } from '../lib/surfaceContracts';

const api = vi.hoisted(() => ({
	createSurfaceSession: vi.fn(),
	getSurfaceSession: vi.fn(),
	resumeSurfaceSession: vi.fn(),
	heartbeatSurfaceSession: vi.fn(),
	cancelSurfaceSession: vi.fn(),
	getSurfaceEvents: vi.fn(),
	listOwnedToolApprovals: vi.fn(),
	createMission: vi.fn(),
	startRun: vi.fn(),
	approveToolCall: vi.fn(),
	rejectToolCall: vi.fn()
}));

vi.mock('../lib/api', async importOriginal => ({
	...(await importOriginal<typeof import('../lib/api')>()),
	...api
}));

function session(overrides: Partial<SurfaceSession> = {}): SurfaceSession {
	return {
		id: 'surface-1',
		surface: { kind: 'webui', session_id: 'tab-1' },
		workspace: { kind: 'global', root: 'C:/atlas', project_id: null },
		agent: 'native',
		model: { provider: 'openrouter', model_id: 'test' },
		permission_mode: 'ask',
		state: 'active',
		owner_token: 'owner-1',
		mission_id: null,
		run_id: null,
		...overrides
	};
}

function Probe() {
	const surface = useAgentSurface();
	return (
		<div>
			<span data-testid="session">{surface.session?.id ?? 'none'}</span>
			<span data-testid="approvals">{surface.approvals.length}</span>
			<button onClick={() => void surface.openSurface({ kind: 'global' })}>global</button>
			<button
				onClick={() =>
					void surface.openSurface({ kind: 'project', projectId: 'project-1' })
				}
			>
				project
			</button>
			<button
				onClick={() =>
					void surface.submitPrompt('Ship it', 'native', {
						kind: 'project',
						projectId: 'project-1'
					})
				}
			>
				submit
			</button>
			<button onClick={() => void surface.submitPrompt('/goal Ship it', 'native', { kind: 'global' })}>
				goal
			</button>
			<button onClick={() => void surface.submitPrompt('/mission status', 'native', { kind: 'global' })}>
				goal status
			</button>
			<button
				onClick={() =>
					void surface.submitPrompt(
						'Expanded command template',
						'native',
						{ kind: 'global' },
						'/mission Ship from palette'
					)
				}
			>
				palette goal
			</button>
		</div>
	);
}

describe('AgentSurfaceProvider', () => {
	beforeEach(() => {
		api.createSurfaceSession.mockReset();
		api.getSurfaceSession.mockReset();
		api.resumeSurfaceSession.mockReset();
		api.heartbeatSurfaceSession.mockReset();
		api.cancelSurfaceSession.mockReset();
		api.getSurfaceEvents.mockReset().mockResolvedValue({
			session_id: 'surface-1',
			after_seq: -1,
			events: []
		});
		api.listOwnedToolApprovals.mockReset().mockResolvedValue([]);
		api.createMission.mockReset().mockResolvedValue({ mission: { id: 'mission-1' } });
		api.startRun.mockReset().mockResolvedValue({ run: { id: 'run-1' } });
		api.heartbeatSurfaceSession.mockResolvedValue(session());
	});

	it('creates global/project sessions and binds submitted runs to the session', async () => {
		api.createSurfaceSession.mockResolvedValue(session());
		const user = userEvent.setup();
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);
		await user.click(screen.getByRole('button', { name: 'project' }));
		await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent('surface-1'));
		expect(api.createSurfaceSession).toHaveBeenCalledWith(
			expect.objectContaining({
				surface_kind: 'webui',
				workspace_kind: 'project',
				project_id: 'project-1'
			})
		);

		await user.click(screen.getByRole('button', { name: 'submit' }));
		await waitFor(() =>
			expect(api.startRun).toHaveBeenCalledWith(
				'mission-1',
				'native',
				true,
				'surface-1'
			)
		);
	});

	it('creates one mission and starts goal mode for a long-horizon alias', async () => {
		api.createSurfaceSession.mockResolvedValue(session());
		const user = userEvent.setup();
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);

		await user.click(screen.getByRole('button', { name: 'goal' }));
		await waitFor(() => expect(api.startRun).toHaveBeenCalledTimes(1));
		expect(api.createMission).toHaveBeenCalledTimes(1);
		expect(api.createMission).toHaveBeenCalledWith('Ship it', 'Ship it', undefined);
		expect(api.startRun).toHaveBeenCalledWith(
			'mission-1',
			'native',
			true,
			'surface-1',
			{ goalMode: true }
		);
	});

	it('does not send bare or status aliases as agent prompts', async () => {
		const user = userEvent.setup();
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);

		await user.click(screen.getByRole('button', { name: 'goal status' }));
		expect(api.createSurfaceSession).not.toHaveBeenCalled();
		expect(api.createMission).not.toHaveBeenCalled();
		expect(api.startRun).not.toHaveBeenCalled();
	});

	it('uses Console command text instead of its expanded prompt for goal launch', async () => {
		api.createSurfaceSession.mockResolvedValue(session());
		const user = userEvent.setup();
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);

		await user.click(screen.getByRole('button', { name: 'palette goal' }));
		await waitFor(() => expect(api.createMission).toHaveBeenCalledTimes(1));
		expect(api.createMission).toHaveBeenCalledWith(
			'Ship from palette',
			'Ship from palette',
			undefined
		);
		expect(api.startRun).toHaveBeenCalledWith(
			'mission-1',
			'native',
			true,
			'surface-1',
			{ goalMode: true }
		);
	});

	it('restores reconnect identity and filters foreign approvals', async () => {
		localStorage.setItem(
			RECONNECT_KEY,
			JSON.stringify({ id: 'surface-1', ownerToken: 'owner-1' })
		);
		api.getSurfaceSession.mockResolvedValue(session({ owner_token: '' }));
		api.listOwnedToolApprovals.mockResolvedValue([
			{
				id: 'owned',
				status: 'pending',
				surface_session_id: 'surface-1'
			},
			{
				id: 'foreign',
				status: 'pending',
				surface_session_id: 'surface-2'
			}
		]);
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);
		await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent('surface-1'));
		await waitFor(() => expect(screen.getByTestId('approvals')).toHaveTextContent('1'));
		expect(api.getSurfaceSession).toHaveBeenCalledWith('surface-1', 'owner-1');
		expect(api.getSurfaceEvents).toHaveBeenCalledWith(
			expect.objectContaining({ id: 'surface-1', owner_token: 'owner-1' }),
			-1
		);
	});

	it('resumes suspended sessions and preserves the rotated owner token', async () => {
		localStorage.setItem(
			RECONNECT_KEY,
			JSON.stringify({ id: 'surface-1', ownerToken: 'owner-old' })
		);
		api.getSurfaceSession.mockResolvedValue(
			session({ state: 'suspended', owner_token: '' })
		);
		api.resumeSurfaceSession.mockResolvedValue(
			session({ owner_token: 'owner-new' })
		);
		render(
			<AgentSurfaceProvider>
				<Probe />
			</AgentSurfaceProvider>
		);
		await waitFor(() => expect(api.resumeSurfaceSession).toHaveBeenCalled());
		await act(async () => {});
		expect(localStorage.getItem(RECONNECT_KEY)).toContain('owner-new');
	});
});
