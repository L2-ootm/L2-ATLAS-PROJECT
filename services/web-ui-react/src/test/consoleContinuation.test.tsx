import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useConsoleSession } from '../context/ConsoleSessionContext';
import { ConsoleSessionProvider } from '../context/ConsoleSessionProvider';
import type { SurfaceEvent } from '../lib/surfaceContracts';
import Console from '../routes/Console';

const surface = vi.hoisted(() => ({
	value: {
		events: [] as SurfaceEvent[],
		submitPrompt: vi.fn(),
		releaseSession: vi.fn().mockResolvedValue(undefined),
		refresh: vi.fn().mockResolvedValue(undefined)
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
	payload: Record<string, unknown>,
	runId = 'run-1'
): SurfaceEvent {
	return {
		session_id: 'surface-1',
		seq,
		kind,
		run_id: runId,
		occurred_at: '2026-07-02T12:00:00Z',
		payload_json: JSON.stringify(payload)
	};
}

function RouteHarness() {
	const [consoleRoute, setConsoleRoute] = useState(true);
	const [, setTick] = useState(0);
	return (
		<>
			<button type="button" onClick={() => setTick((current) => current + 1)}>
				tick events
			</button>
			<button type="button" onClick={() => setConsoleRoute((current) => !current)}>
				navigate
			</button>
			{consoleRoute ? <Console /> : <div>another route</div>}
		</>
	);
}

function SessionStateProbe() {
	const { activeTurn, messagesByWindow } = useConsoleSession();
	const turn = messagesByWindow['chat-1']?.find((message) => message.role === 'agent');
	return (
		<>
			<div data-testid="active-run">
				{activeTurn ? activeTurn.runId ?? 'resolving' : 'idle'}
			</div>
			<div data-testid="turn-status">{turn?.status ?? 'missing'}</div>
		</>
	);
}

function renderConsole() {
	return render(
		<MemoryRouter>
			<ConsoleSessionProvider>
				<SessionStateProbe />
				<RouteHarness />
			</ConsoleSessionProvider>
		</MemoryRouter>
	);
}

describe('Console route continuation', () => {
	beforeEach(() => {
		globalThis.ResizeObserver = class {
			observe() {}
			unobserve() {}
			disconnect() {}
		};
		surface.value.events = [];
		surface.value.submitPrompt.mockReset();
		surface.value.refresh.mockClear();
		api.listProjects.mockReset().mockResolvedValue({ projects: [] });
		api.getRun.mockReset();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('consumes pre-resolution events and completes after route remount', async () => {
		let resolveRun!: (runId: string) => void;
		surface.value.submitPrompt.mockImplementation(
			() => new Promise<string>((resolve) => { resolveRun = resolve; })
		);
		renderConsole();

		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), {
			target: { value: 'continue through navigation' }
		});
		fireEvent.click(screen.getByTitle('Send'));
		expect(screen.getByTestId('active-run')).toHaveTextContent('resolving');
		expect(screen.getByTestId('turn-status')).toHaveTextContent('pending');
		// While a turn is in flight the composer is disabled and speaks the
		// system voice instead of the idle prompt.
		expect(screen.getByPlaceholderText('Turn in progress — streaming')).toBeDisabled();
		expect(
			screen.getByTitle('Cannot close the window owning the active run')
		).toBeDisabled();

		surface.value.events = [
			surfaceEvent(1, 'text', { text: 'buffered while submission resolved' })
		];
		await act(async () => resolveRun('run-1'));
		expect((await screen.findAllByText('buffered while submission resolved')).length).toBeGreaterThan(0);

		fireEvent.click(screen.getByText('navigate'));
		expect(screen.getByText('another route')).toBeInTheDocument();
		surface.value.events = [
			...surface.value.events,
			surfaceEvent(2, 'completion', { status: 'succeeded' })
		];
		fireEvent.click(screen.getByText('navigate'));

		await waitFor(() => expect(screen.getByTestId('active-run')).toHaveTextContent('idle'));
		expect(screen.getByTestId('turn-status')).toHaveTextContent('succeeded');
		expect(screen.getByPlaceholderText('Message ATLAS')).toBeEnabled();
		expect(screen.getAllByText('buffered while submission resolved').length).toBeGreaterThan(0);
	});

	it('lets the watchdog release a turn whose terminal event was dropped', async () => {
		vi.useFakeTimers();
		surface.value.submitPrompt.mockResolvedValue('run-1');
		api.getRun.mockResolvedValue({
			run: { status: 'succeeded', summary: 'Recovered from run record.' }
		});
		renderConsole();

		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), {
			target: { value: 'watch this run' }
		});
		fireEvent.click(screen.getByTitle('Send'));
		await act(async () => {});
		expect(screen.getByTestId('turn-status')).toHaveTextContent('pending');
		expect(screen.getByPlaceholderText('Turn in progress — streaming')).toBeDisabled();

		// First terminal sighting is a grace pass: the watchdog forces a surface
		// event refresh instead of finalizing, so late tail events (final deltas
		// + reconcile) can still land — see the "Bril" truncation bug. The turn
		// must still be held open after this tick.
		await act(async () => {
			await vi.advanceTimersByTimeAsync(8_000);
		});
		expect(api.getRun).toHaveBeenCalledWith('run-1');
		expect(surface.value.refresh).toHaveBeenCalled();
		expect(screen.getByTestId('active-run')).toHaveTextContent('run-1');

		// Second sighting with the terminal event still missing: finalize from
		// the run record.
		await act(async () => {
			await vi.advanceTimersByTimeAsync(8_000);
		});
		expect(screen.getByTestId('active-run')).toHaveTextContent('idle');
		expect(screen.getByTestId('turn-status')).toHaveTextContent('succeeded');
		expect(screen.getByPlaceholderText('Message ATLAS')).toBeEnabled();
		expect(screen.getByText('Recovered from run record.')).toBeInTheDocument();
	});

	it('does not let the initial run watchdog finalize a goal continuation', async () => {
		vi.useFakeTimers();
		surface.value.submitPrompt.mockResolvedValue('run-1');
		api.getRun.mockResolvedValue({
			run: { status: 'succeeded', summary: 'Initial run completed.' }
		});
		renderConsole();

		fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), {
			target: { value: '/mission finish all phases' }
		});
		fireEvent.click(screen.getByTitle('Send'));
		await act(async () => {});

		await act(async () => {
			await vi.advanceTimersByTimeAsync(16_000);
		});
		expect(screen.getByTestId('active-run')).toHaveTextContent('run-1');
		expect(screen.getByTestId('turn-status')).toHaveTextContent('pending');
		expect(surface.value.refresh).toHaveBeenCalled();

		surface.value.events = [
			surfaceEvent(1, 'completion', { status: 'succeeded' }),
			surfaceEvent(2, 'task', { state: 'active', verdict: 'continue' }),
			surfaceEvent(3, 'text', { text: 'Continuation completed.' }, 'run-2'),
			surfaceEvent(4, 'completion', { state: 'exhausted', verdict: 'continue' }, 'run-2')
		];
		await act(async () => fireEvent.click(screen.getByText('tick events')));

		expect(screen.getByTestId('active-run')).toHaveTextContent('idle');
		expect(screen.getByTestId('turn-status')).toHaveTextContent('succeeded');
		expect(screen.getAllByText('Continuation completed.').length).toBeGreaterThan(0);
	});
});
