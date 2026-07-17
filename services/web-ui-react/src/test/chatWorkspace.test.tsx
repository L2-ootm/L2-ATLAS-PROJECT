import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatActorWorkspace } from '../components/chat/ChatActorWorkspace';
import { QueuedChatComposer } from '../components/chat/QueuedChatComposer';
import type { SurfaceEvent } from '../lib/surfaceContracts';

function event(seq: number, kind: SurfaceEvent['kind'], runId: string, payload: object): SurfaceEvent {
	return {
		session_id: 'surface-1',
		seq,
		kind,
		run_id: runId,
		occurred_at: '2026-07-17T01:02:03Z',
		payload_json: JSON.stringify(payload)
	};
}

describe('chat actor workspace', () => {
	it('opens a durable actor and shows its linked child tool stream', () => {
		const events = [
			event(1, 'task', 'parent-run', {
				orchestration: 'subagent',
				actor: true,
				subagent_id: 'actor-12345678',
				phase: 'working',
				goal: 'Inspect the runtime',
				child_run_id: 'child-run'
			}),
			event(2, 'tool_call', 'child-run', {
				tool: 'read_file',
				arguments: { path: 'actor_worker.py' }
			})
		];
		render(
			<ChatActorWorkspace
				events={events}
				busy={false}
				provider="anthropic"
				modelId="claude-opus"
			/>
		);
		fireEvent.click(screen.getByText('Inspect the runtime'));
		expect(screen.getByRole('heading', { name: 'Live activity stream' })).toBeInTheDocument();
		expect(screen.getByText('read_file')).toBeInTheDocument();
		expect(screen.getByText(/actor_worker\.py/)).toBeInTheDocument();
	});

	it('warns above ten active actors without hiding or refusing any', () => {
		const events = Array.from({ length: 11 }, (_, index) => event(index + 1, 'task', 'parent-run', {
			orchestration: 'subagent',
			subagent_id: `actor-${index}`,
			phase: 'working',
			goal: `Actor ${index}`
		}));
		render(<ChatActorWorkspace events={events} busy={false} provider="openrouter" modelId="primary" />);
		expect(screen.getByText(/11 actors are parallel/)).toBeInTheDocument();
		expect(screen.getAllByRole('button', { name: /Actor \d/ })).toHaveLength(11);
	});
});

describe('queued chat composer', () => {
	it('keeps the composer active during a run and exposes queue controls', () => {
		const submit = vi.fn();
		const promote = vi.fn();
		render(
			<QueuedChatComposer
				draft="follow up"
				onDraftChange={vi.fn()}
				queue={[{ id: 'one', text: 'first' }, { id: 'two', text: 'second' }]}
				busy
				agent="native"
				error={null}
				onSubmit={submit}
				onCancel={vi.fn()}
				onPromote={promote}
				onEdit={vi.fn()}
				onRemove={vi.fn()}
			/>
		);
		expect(screen.getByPlaceholderText('Write the next request for ATLAS')).toBeEnabled();
		fireEvent.click(screen.getByRole('button', { name: 'Queue this prompt' }));
		expect(submit).toHaveBeenCalledOnce();
		fireEvent.click(screen.getByRole('button', { name: 'Run this prompt next' }));
		expect(promote).toHaveBeenCalledWith('two');
	});
});
