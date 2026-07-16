import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { SurfaceEvent } from '../lib/surfaceContracts';
import Chat from '../routes/Chat';

// Coverage for the dedicated Chat page: the delta+reconcile merge renders a
// streamed answer exactly once, and run receipts (run started / runtime /
// privacy notices) show once per session instead of repeating on every turn.

const surface = vi.hoisted(() => ({
	value: {
		events: [] as SurfaceEvent[],
		submitPrompt: vi.fn(),
		releaseSession: vi.fn().mockResolvedValue(undefined),
		refresh: vi.fn().mockResolvedValue(undefined),
		cancel: vi.fn().mockResolvedValue(undefined)
	}
}));

const api = vi.hoisted(() => ({
	listProjects: vi.fn(),
	getRun: vi.fn(),
	registerProject: vi.fn()
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
	payload: Record<string, unknown>,
	runId = 'run-1'
): SurfaceEvent {
	return {
		session_id: 'surface-1',
		seq,
		kind,
		run_id: runId,
		occurred_at: '2026-07-16T12:00:00Z',
		payload_json: JSON.stringify(payload)
	};
}

// The mocked surface is a plain mutable object — a tick re-render makes the
// page re-read `surface.value.events` (same pattern as consoleStreaming).
function Harness() {
	const [, setTick] = useState(0);
	return (
		<>
			<button type="button" onClick={() => setTick((t) => t + 1)}>
				tick
			</button>
			<Chat />
		</>
	);
}

function renderChat() {
	return render(
		<MemoryRouter>
			<Harness />
		</MemoryRouter>
	);
}

function countOccurrences(haystack: string, needle: string): number {
	return haystack.split(needle).length - 1;
}

describe('Chat page', () => {
	beforeEach(() => {
		globalThis.ResizeObserver = class {
			observe() {}
			unobserve() {}
			disconnect() {}
		};
		localStorage.clear();
		surface.value.events = [];
		surface.value.submitPrompt.mockReset();
		api.listProjects.mockReset().mockResolvedValue({ projects: [] });
		api.getRun.mockReset();
	});

	it('renders a streamed answer once — deltas merge and the reconcile replaces, never appends', async () => {
		surface.value.submitPrompt.mockResolvedValue('run-1');
		renderChat();

		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), {
			target: { value: 'stream this' }
		});
		fireEvent.keyDown(screen.getByPlaceholderText('Message ATLAS'), { key: 'Enter' });
		await act(async () => {});

		surface.value.events = [
			surfaceEvent(1, 'text', { delta: 'The answer is ' }),
			surfaceEvent(2, 'text', { delta: 'forty-two exactly.' })
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));
		expect(countOccurrences(document.body.textContent ?? '', 'forty-two exactly.')).toBe(1);

		// Final reconcile carries the SAME full text — must replace, not append.
		surface.value.events = [
			...surface.value.events,
			surfaceEvent(3, 'text', { text: 'The answer is forty-two exactly.' }),
			surfaceEvent(4, 'completion', { status: 'succeeded' })
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));

		expect(countOccurrences(document.body.textContent ?? '', 'forty-two exactly.')).toBe(1);
		// Turn settled: composer is live again.
		expect(screen.getByPlaceholderText('Message ATLAS')).toBeEnabled();
	});

	it('shows the run receipt once per session, not on every turn', async () => {
		surface.value.submitPrompt.mockResolvedValueOnce('run-1').mockResolvedValueOnce('run-2');
		renderChat();

		// Turn 1 — receipt + answer + terminal.
		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), { target: { value: 'first' } });
		fireEvent.keyDown(screen.getByPlaceholderText('Message ATLAS'), { key: 'Enter' });
		await act(async () => {});
		surface.value.events = [
			surfaceEvent(1, 'tool_call', { transition: 'started' }),
			surfaceEvent(2, 'tool_call', { runtime: 'native' }),
			surfaceEvent(3, 'text', { text: 'First answer.' }),
			surfaceEvent(4, 'completion', { status: 'succeeded' })
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));
		expect(screen.getByPlaceholderText('Message ATLAS')).toBeEnabled();

		// Turn 2 — identical receipt events on a new run.
		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), { target: { value: 'second' } });
		fireEvent.keyDown(screen.getByPlaceholderText('Message ATLAS'), { key: 'Enter' });
		await act(async () => {});
		surface.value.events = [
			...surface.value.events,
			surfaceEvent(5, 'tool_call', { transition: 'started' }, 'run-2'),
			surfaceEvent(6, 'tool_call', { runtime: 'native' }, 'run-2'),
			surfaceEvent(7, 'text', { text: 'Second answer.' }, 'run-2'),
			surfaceEvent(8, 'completion', { status: 'succeeded' }, 'run-2')
		];
		await act(async () => fireEvent.click(screen.getByText('tick')));

		expect(screen.getByText('First answer.')).toBeInTheDocument();
		expect(screen.getByText('Second answer.')).toBeInTheDocument();
		// The merged "run started · runtime native" receipt appears exactly once.
		expect(countOccurrences(document.body.textContent ?? '', 'run started')).toBe(1);
	});
});
