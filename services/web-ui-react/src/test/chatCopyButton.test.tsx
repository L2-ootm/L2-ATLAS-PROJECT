import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { SurfaceEvent } from '../lib/surfaceContracts';
import Chat from '../routes/Chat';

// Coverage for the whole-message copy button on agent chat turns: it must
// copy the full `message.body` (never a partial streamed slice), stay
// hidden while there is nothing to copy yet, and swap Copy -> Check ->
// Copy on click, matching the CodeBlock copy-button contract in
// ChatMarkdown.tsx.

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
// page re-read `surface.value.events` (same pattern as chatPage.test.tsx).
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

function mockClipboard() {
	const writeText = vi.fn().mockResolvedValue(undefined);
	Object.defineProperty(navigator, 'clipboard', {
		value: { writeText },
		configurable: true
	});
	return writeText;
}

async function sendPrompt(text: string) {
	fireEvent.change(screen.getByPlaceholderText('Message ATLAS'), { target: { value: text } });
	fireEvent.keyDown(screen.getByPlaceholderText('Message ATLAS'), { key: 'Enter' });
	await act(async () => {});
}

async function tick() {
	await act(async () => fireEvent.click(screen.getByText('tick')));
}

describe('Chat agent turn — copy message button', () => {
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

	it('does not render a copy button while the turn has no body yet', async () => {
		surface.value.submitPrompt.mockResolvedValue('run-1');
		renderChat();

		await sendPrompt('hello');
		// Turn is pending with no events yet -> body is still empty.
		expect(screen.queryByRole('button', { name: /copy message/i })).toBeNull();
	});

	it('copies the full message body to the clipboard, including mid-stream', async () => {
		const writeText = mockClipboard();
		surface.value.submitPrompt.mockResolvedValue('run-1');
		renderChat();

		await sendPrompt('stream this');

		// Turn is still open (no completion event) — message.body is fed by the
		// text/text_delta merge in Chat.tsx regardless of what StreamReveal is
		// animating on screen, so it must already hold the full text.
		surface.value.events = [surfaceEvent(1, 'text', { text: 'Full accumulated answer.' })];
		await tick();

		const button = screen.getByRole('button', { name: /copy message/i });
		fireEvent.click(button);

		expect(writeText).toHaveBeenCalledWith('Full accumulated answer.');
	});

	it('swaps the icon to a "Copied" state on click and reverts after 1400ms', async () => {
		mockClipboard();
		surface.value.submitPrompt.mockResolvedValue('run-1');
		renderChat();

		await sendPrompt('hello');
		surface.value.events = [
			surfaceEvent(1, 'text', { text: 'Done.' }),
			surfaceEvent(2, 'completion', { status: 'succeeded' })
		];
		await tick();

		const button = screen.getByRole('button', { name: /copy message/i });

		vi.useFakeTimers();
		try {
			await act(async () => {
				fireEvent.click(button);
			});
			expect(screen.getByRole('button', { name: /^copied$/i })).toBeInTheDocument();

			act(() => {
				vi.advanceTimersByTime(1400);
			});
			expect(screen.getByRole('button', { name: /^copy message$/i })).toBeInTheDocument();
		} finally {
			vi.useRealTimers();
		}
	});
});
