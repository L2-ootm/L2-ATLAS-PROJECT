import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AgentSessionHeader from '../components/agent/AgentSessionHeader';
import PermissionQueueSidebar from '../components/agent/PermissionQueueSidebar';
import { AgentSurfaceContext, type AgentSurfaceValue } from '../context/AgentSurfaceContext';
import type { ToolApproval } from '../lib/api';
import type { SurfaceSession } from '../lib/surfaceContracts';

function session(state: SurfaceSession['state'] = 'active'): SurfaceSession {
	return {
		id: 'surface-123456',
		surface: { kind: 'webui', session_id: 'tab-1' },
		workspace: { kind: 'project', root: 'C:/atlas', project_id: 'project-1' },
		agent: 'native',
		model: { provider: 'openrouter', model_id: 'test/model' },
		permission_mode: 'ask',
		state,
		owner_token: 'owner-1',
		mission_id: null,
		run_id: 'run-1'
	};
}

function approval(overrides: Partial<ToolApproval> = {}): ToolApproval {
	return {
		id: 'approval-1',
		tool_name: 'terminal',
		risk_level: 'high',
		args: '{"cmd":"go test ./..."}',
		args_normalized: '{"cmd":"go test ./..."}',
		summary: 'Run project tests',
		status: 'pending',
		reason: null,
		result: null,
		run_id: 'run-1',
		surface_session_id: 'surface-123456',
		surface_kind: 'webui',
		workspace_root: 'C:/atlas',
		expiry_at: '2026-06-29T23:59:00Z',
		decision: null,
		nonce: 'nonce-1',
		policy_receipt: '{"decision":"ask","source":"master"}',
		requested_at: '2026-06-29T00:00:00Z',
		decided_at: null,
		...overrides
	};
}

function value(overrides: Partial<AgentSurfaceValue> = {}): AgentSurfaceValue {
	return {
		session: null,
		events: [],
		approvals: [],
		outcomes: [],
		error: null,
		busy: false,
		pinned: false,
		queueOpen: false,
		openSurface: vi.fn(),
		submitPrompt: vi.fn(),
		cancel: vi.fn(),
		resume: vi.fn(),
		refresh: vi.fn(),
		decide: vi.fn(),
		setPinned: vi.fn(),
		setQueueOpen: vi.fn(),
		...overrides
	};
}

function Chrome({ state }: { state: AgentSurfaceValue }) {
	return (
		<AgentSurfaceContext.Provider value={state}>
			<AgentSessionHeader />
			<PermissionQueueSidebar />
		</AgentSurfaceContext.Provider>
	);
}

describe('agent chrome visibility matrix', () => {
	it('hides inactive and terminal empty chrome', () => {
		const { rerender } = render(<Chrome state={value()} />);
		expect(screen.queryByText('AGENT SESSION')).not.toBeInTheDocument();
		expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
		rerender(<Chrome state={value({ session: session('completed') })} />);
		expect(screen.queryByText('AGENT SESSION')).not.toBeInTheDocument();
	});

	it('shows active header and owned pending queue', () => {
		render(
			<Chrome
				state={value({
					session: session(),
					approvals: [approval()],
					queueOpen: true
				})}
			/>
		);
		expect(screen.getByText('AGENT SESSION')).toBeInTheDocument();
		expect(screen.getByRole('complementary', { name: 'PERMISSION QUEUE' })).toBeInTheDocument();
		expect(screen.getByText('Run project tests')).toBeInTheDocument();
	});

	it('keeps pinned empty queue useful and submits nonce-bound scopes', async () => {
		const decide = vi.fn().mockResolvedValue(undefined);
		const user = userEvent.setup();
		const { rerender } = render(
			<Chrome
				state={value({
					session: session(),
					pinned: true,
					queueOpen: true
				})}
			/>
		);
		expect(screen.getByText('NO ACTION REQUIRED')).toBeInTheDocument();
		rerender(
			<Chrome
				state={value({
					session: session(),
					approvals: [approval()],
					queueOpen: true,
					decide
				})}
			/>
		);
		await user.click(screen.getByRole('button', { name: 'ALLOW SESSION' }));
		expect(decide).toHaveBeenCalledWith(expect.objectContaining({
			id: 'approval-1',
			nonce: 'nonce-1',
			surface_session_id: 'surface-123456'
		}), 'session');
	});

	it('never offers allow controls for a hardline receipt', () => {
		render(
			<Chrome
				state={value({
					session: session(),
					approvals: [
						approval({
							policy_receipt: '{"decision":"deny","hardline":true,"source":"H-004"}'
						})
					],
					queueOpen: true
				})}
			/>
		);
		expect(screen.getByRole('button', { name: 'DENY' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /ALLOW/ })).not.toBeInTheDocument();
	});
});

export { approval, session, value, Chrome };
