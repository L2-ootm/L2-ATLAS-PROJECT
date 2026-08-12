import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OrchestrationCallCard } from '../components/chat/OrchestrationCallCard';
import { AgentSurfaceContext, type AgentSurfaceValue } from '../context/AgentSurfaceContext';
import * as api from '../lib/api';
import type { SurfaceSession } from '../lib/surfaceContracts';
import type { SubagentActivity } from '../lib/subagents';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listChangeSetFiles: vi.fn(),
		listFileChangeHunks: vi.fn(),
		getFileChangePatch: vi.fn()
	};
});

const restoredActor: SubagentActivity = {
	id: 'actor-parent',
	parentId: null,
	phase: 'completed',
	goal: 'Inspect runtime',
	model: 'test',
	role: 'worker',
	tool: 'read_file',
	toolCount: 4,
	depth: 1,
	background: false,
	durationSeconds: 2,
	childRunId: 'child-run'
};

const surface = {
	session: {
		id: 'surface-1',
		owner_token: 'owner-1'
	} as SurfaceSession
} as AgentSurfaceValue;

function renderCard(evidence: Record<string, unknown>, actor = restoredActor) {
	return render(
		<AgentSurfaceContext.Provider value={surface}>
			<OrchestrationCallCard
				event={{
					type: 'tool_call',
					tool_name: 'delegate_task',
					tool_call_id: 'delegate-1',
					input: { tasks: [{ goal: actor.goal }] }
				}}
				result={{ type: 'tool_result', tool_call_id: 'delegate-1', content: { evidence } }}
				actors={[actor]}
			/>
		</AgentSurfaceContext.Provider>
	);
}

describe('orchestration Evidence Plane receipts', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('deduplicates referenced sets, preserves totals, and opens the shared inspector', async () => {
		vi.mocked(api.listChangeSetFiles)
			.mockResolvedValueOnce({
				files: [{
					id: 'file-1',
					change_set_id: 'aggregate-parent',
					path: 'services/runtime/worker.py',
					old_path: null,
					operation: 'edit',
					availability: 'available',
					before_sha256: null,
					after_sha256: 'a'.repeat(64),
					before_bytes: 10,
					after_bytes: 20,
					additions: 7,
					deletions: 2,
					binary: false,
					generated: false,
					mode_before: null,
					mode_after: null,
					redaction_count: 0
				}],
				next_cursor: null
			})
			.mockResolvedValueOnce({ files: [], next_cursor: null });
		vi.mocked(api.listFileChangeHunks).mockResolvedValue({
			hunks: [],
			next_cursor: null,
			context: 3,
			ignore_whitespace: false
		});
		vi.mocked(api.getFileChangePatch).mockResolvedValue({
			availability: 'available',
			media_type: 'text/x-diff',
			sha256: 'a'.repeat(64),
			range: { start: 0, end: 12, total_bytes: 12 },
			content: '@@ -1 +1 @@'
		});

		const { container } = renderCard({
			evidence_ids: ['aggregate-parent', 'leaf-a', 'aggregate-parent'],
			file_count: 2,
			additions: 11,
			deletions: 4,
			coverage: 'complete',
			availability: 'available',
			redaction_count: 0,
			ancestry: {
				actor_id: 'actor-parent',
				parent_actor_id: null,
				team_run_id: null,
				goal_id: 'goal-1'
			},
			incident: null
		});

		expect(container.querySelector('.chat-orchestration-card')).toHaveAttribute('data-state', 'done');
		expect(screen.getByText('2 EVIDENCE SETS')).toBeInTheDocument();
		expect(screen.getByText('+11')).toBeInTheDocument();
		expect(screen.getByText('−4')).toBeInTheDocument();
		expect(screen.getByText('COMPLETE')).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /delegate_task/i }));
		expect(await screen.findByText('services/runtime/worker.py')).toBeInTheDocument();
		expect(api.listChangeSetFiles).toHaveBeenNthCalledWith(
			1,
			'aggregate-parent',
			'owner-1',
			expect.objectContaining({ limit: 100 })
		);
		expect(api.listChangeSetFiles).toHaveBeenNthCalledWith(
			2,
			'leaf-a',
			'owner-1',
			expect.objectContaining({ limit: 100 })
		);
		await userEvent.click(screen.getByRole('button', { name: /inspect services\/runtime\/worker.py/i }));
		expect(await screen.findByRole('dialog', { name: /evidence inspector/i })).toBeInTheDocument();
		expect(screen.getByText('ACTOR actor-parent')).toBeInTheDocument();
	});

	it.each([
		['partial capture', { coverage: 'partial', availability: 'partial' }, 'PARTIAL'],
		['unavailable evidence', { coverage: 'unavailable', availability: 'unavailable' }, 'UNAVAILABLE'],
		['cleanup failure', { coverage: 'complete', availability: 'available', cleanup: { status: 'failed', error: 'worker alive' } }, 'CLEANUP FAILED'],
		['read-only incident', { coverage: 'complete', availability: 'available', incident: { kind: 'read_only_mutation', status: 'denied', reason: 'actor produced file changes' } }, 'READ ONLY MUTATION']
	])('renders %s as non-success', (_name, state, warning) => {
		const { container } = renderCard({
			evidence_ids: ['change-1'],
			file_count: 1,
			additions: 1,
			deletions: 0,
			redaction_count: 0,
			ancestry: { actor_id: 'actor-parent' },
			incident: null,
			...state
		});
		expect(container.querySelector('.chat-orchestration-card')).toHaveAttribute('data-state', 'failed');
		expect(screen.getByText('ATTENTION')).toBeInTheDocument();
		expect(screen.getByText(warning)).toBeInTheDocument();
	});

	it('keeps a cancelled restored actor non-success even when a tool result exists', async () => {
		const cancelled = { ...restoredActor, phase: 'cancelled' as const };
		const { container } = renderCard({
			evidence_ids: ['change-1'],
			file_count: 1,
			additions: 1,
			deletions: 0,
			coverage: 'complete',
			availability: 'available',
			redaction_count: 0,
			cleanup: { status: 'complete', error: null },
			incident: null
		}, cancelled);
		expect(container.querySelector('.chat-orchestration-card')).toHaveAttribute('data-state', 'failed');
		expect(screen.getByText('ATTENTION')).toBeInTheDocument();
		await waitFor(() => expect(api.listChangeSetFiles).not.toHaveBeenCalled());
	});
});
