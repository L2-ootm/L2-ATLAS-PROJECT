import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConsoleSessionProvider } from '../context/ConsoleSessionProvider';
import type { SurfaceEvent } from '../lib/surfaceContracts';
import Console from '../routes/Console';

// Regression coverage for the streaming-duplication bug: 'llm_delta' audit
// rows and the turn's final 'llm_call' reconcile both project to
// SurfaceEventKind 'text' (surface_events.py's _KIND_MAP has no distinct
// delta kind) — AgentTurn used to render every event in message.events as
// its own block, so each delta chunk PLUS the final reconcile would each
// show up as a separate line: the response appearing to repeat itself.
// consoleEvents.ts now tags delta-only payloads (`{delta: ...}`, no
// `text`/`summary`) as a synthetic 'text_delta' type, and Console.tsx's
// AgentTurn collapses a streaming run's deltas + its final reconcile into
// ONE rendered block instead of one per event.

const surface = vi.hoisted(() => ({
	value: {
		events: [] as SurfaceEvent[],
		submitPrompt: vi.fn()
	}
}));

const api = vi.hoisted(() => ({
	listProjects: vi.fn(),
	getRun: vi.fn()
}));

vi.mock('../context/AgentSurfaceContext', () => ({
	useAgentSurface: () => surface.value
}));

vi.mock('../lib/api', async importOriginal => ({
	...(await importOriginal<typeof import('../lib/api')>()),
	...api
}));

function surfaceEvent(
	seq: number,
	kind: SurfaceEvent['kind'],
	payload: Record<string, unknown>
): SurfaceEvent {
	return {
		session_id: 'surface-1',
		seq,
		kind,
		run_id: 'run-1',
		occurred_at: '2026-07-15T12:00:00Z',
		payload_json: JSON.stringify(payload)
	};
}

// Console reads `useAgentSurface()` (mocked above as a plain mutable object,
// not React state) — mutating `surface.value.events` alone doesn't trigger a
// re-render. A tick counter forces a plain re-render (no remount — Console's
// own local state, e.g. the composer, must survive) so it re-reads the
// mutated object, the same way the original consoleContinuation.test.tsx
// forces a re-read via an unrelated state change (there, a route toggle).
function RouteHarness() {
	const [, setTick] = useState(0);
	return (
		<>
			<button type="button" onClick={() => setTick((t) => t + 1)}>
				tick
			</button>
			<Console />
		</>
	);
}

function renderConsole() {
	return render(
		<MemoryRouter>
			<ConsoleSessionProvider>
				<RouteHarness />
			</ConsoleSessionProvider>
		</MemoryRouter>
	);
}

describe('Console streaming (delta + reconcile merge)', () => {
	beforeEach(() => {
		globalThis.ResizeObserver = class {
			observe() {}
			unobserve() {}
			disconnect() {}
		};
		surface.value.events = [];
		surface.value.submitPrompt.mockReset();
		api.listProjects.mockReset().mockResolvedValue({ projects: [] });
		api.getRun.mockReset();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders a streamed run once, not duplicated by the final reconcile', async () => {
		surface.value.submitPrompt.mockResolvedValue('run-1');
		renderConsole();

		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), {
			target: { value: 'stream this' }
		});
		fireEvent.click(screen.getByTitle('Send'));
		await act(async () => {});

		// Three coalesced llm_delta chunks (payload has only `delta`, matching
		// native.py's _DeltaBuffer — no `text`/`summary` key).
		surface.value.events = [
			surfaceEvent(1, 'text', { delta: 'Good question. ' }),
			surfaceEvent(2, 'text', { delta: 'Let me check where ' }),
			surfaceEvent(3, 'text', { delta: 'we actually stand.' })
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));

		const chatPane = screen.getByTestId('chat-pane-chat-1');
		expect(within(chatPane).getByText('Good question. Let me check where we actually stand.')).toBeInTheDocument();

		// The final llm_call reconcile: authoritative full text, same run.
		surface.value.events = [
			...surface.value.events,
			surfaceEvent(4, 'text', { text: 'Good question. Let me check where we actually stand.' })
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));

		// Scoped to the chat pane specifically: the separate Audit pane
		// legitimately shows every raw event (including each delta) as its own
		// debug row — that's a different view, not the duplication bug.
		const matches = within(chatPane).getAllByText('Good question. Let me check where we actually stand.');
		expect(matches).toHaveLength(1);
	});
});
