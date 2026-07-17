import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatActorWorkspace } from '../components/chat/ChatActorWorkspace';
import { OrchestrationCallCard } from '../components/chat/OrchestrationCallCard';
import { QueuedChatComposer } from '../components/chat/QueuedChatComposer';
import { TopoScroll } from '../components/TopoScroll';
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

	it('shows an allocating actor immediately from a delegate dispatch before its heartbeat', () => {
		render(<ChatActorWorkspace events={[
			event(1, 'tool_call', 'parent-run', {
				tool: 'delegate_task',
				call_id: 'delegate-1',
				arguments: { tasks: [{ goal: 'Review the precision model' }] }
			})
		]} busy provider="openrouter" modelId="primary" />);
		expect(screen.getByText('Review the precision model')).toBeInTheDocument();
		expect(screen.getByText('1 LIVE')).toBeInTheDocument();
		expect(screen.getByText(/dispatching · 0 calls/)).toBeInTheDocument();
	});

	it('settles an orchestration call from terminal actor lifecycle even before the join receipt arrives', () => {
		render(<OrchestrationCallCard
			event={{ type: 'tool_call', tool_name: 'delegate_task', tool_call_id: 'delegate-1', input: { tasks: [{ goal: 'Inspect runtime' }] } }}
			actors={[{
				id: 'actor-1', parentId: null, phase: 'completed', goal: 'Inspect runtime', model: 'test', tool: 'read_file',
				toolCount: 4, depth: 1, background: false, durationSeconds: 2, childRunId: 'child-run'
			}]}
		/>);
		expect(screen.getByText('SETTLED')).toBeInTheDocument();
	});
});

describe('topographic scroll ownership', () => {
	it('reports upward wheel intent before the scroll position changes', () => {
		const intent = vi.fn();
		render(<TopoScroll onViewportUserIntent={intent}><div>content</div></TopoScroll>);
		fireEvent.wheel(document.querySelector('.atlas-topo-scroll-viewport')!, { deltaY: -120 });
		expect(intent).toHaveBeenCalledWith('up');
	});
});

describe('queued chat composer', () => {
	it('keeps the composer active during a run and exposes queue controls', () => {
		const submit = vi.fn(() => true);
		const promote = vi.fn();
		render(
			<QueuedChatComposer
				draft="follow up"
				onDraftPersist={vi.fn()}
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

	it('discovers slash commands inline and completes a partial command before send', () => {
		const submit = vi.fn(() => true);
		render(
			<QueuedChatComposer
				draft=""
				onDraftPersist={vi.fn()}
				queue={[]}
				busy={false}
				agent="native"
				error={null}
				onSubmit={submit}
				onCancel={vi.fn()}
				onPromote={vi.fn()}
				onEdit={vi.fn()}
				onRemove={vi.fn()}
			/>
		);
		const composer = screen.getByPlaceholderText('Message ATLAS');
		fireEvent.change(composer, { target: { value: '/rev' } });
		const suggestions = screen.getByRole('listbox', { name: 'Slash command suggestions' });
		expect(screen.getByRole('option', { name: /\/review/ })).toBeInTheDocument();
		expect(suggestions.parentElement).toHaveClass('chat-composer-region');
		expect(suggestions.nextElementSibling).toHaveClass('chat-composer-shell');
		fireEvent.keyDown(composer, { key: 'Enter' });
		expect(composer).toHaveValue('/review ');
		expect(submit).not.toHaveBeenCalled();
		fireEvent.change(composer, { target: { value: '/review HEAD~1' } });
		fireEvent.keyDown(composer, { key: 'Enter' });
		expect(submit).toHaveBeenCalledWith('/review HEAD~1', expect.stringContaining('HEAD~1'));
	});

	it('cancels the pending persistence debounce after a successful send', () => {
		vi.useFakeTimers();
		const persist = vi.fn();
		render(
			<QueuedChatComposer
				draft=""
				onDraftPersist={persist}
				queue={[]}
				busy={false}
				agent="native"
				error={null}
				onSubmit={() => true}
				onCancel={vi.fn()}
				onPromote={vi.fn()}
				onEdit={vi.fn()}
				onRemove={vi.fn()}
			/>
		);
		const composer = screen.getByPlaceholderText('Message ATLAS');
		fireEvent.change(composer, { target: { value: 'send once' } });
		fireEvent.keyDown(composer, { key: 'Enter' });
		vi.runAllTimers();
		expect(persist).toHaveBeenLastCalledWith('');
		expect(persist).not.toHaveBeenCalledWith('send once');
		vi.useRealTimers();
	});
});
