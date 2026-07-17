import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
	finalGoalJudgementState,
	isRunTerminalEvent,
	surfaceConsoleEvent,
	surfaceEventsForTurn
} from '../lib/consoleEvents';
import { displayConsoleEvents } from '../lib/consoleEventGroups';
import { ToolCallCard } from '../routes/Console';
import {
	SURFACE_EVENT_KINDS,
	type SurfaceEvent,
	type SurfaceEventKind
} from '../lib/surfaceContracts';

function event(kind: SurfaceEventKind, payload: Record<string, unknown> = {}): SurfaceEvent {
	return {
		session_id: 'surface-1',
		seq: SURFACE_EVENT_KINDS.indexOf(kind),
		kind,
		run_id: 'run-1',
		occurred_at: '2026-06-29T00:00:00+00:00',
		payload_json: JSON.stringify(payload)
	};
}

describe('Console shared session transport', () => {
	it('projects every normalized event kind without silent drops', () => {
		const projected = SURFACE_EVENT_KINDS.map(kind =>
			surfaceConsoleEvent(
				event(kind, {
					text: `${kind} detail`,
					status: 'succeeded',
					tool: 'read_file',
					call_id: 'call-1'
				})
			)
		);
		expect(projected).toHaveLength(SURFACE_EVENT_KINDS.length);
		expect(projected.map(item => item.type)).toEqual([
			'text',
			'reasoning',
			'tool_call',
			'tool_result',
			'task',
			'retry',
			'retrieval',
			'approval',
			'failure',
			'result'
		]);
	});

	it('turns malformed payloads into a visible failure boundary', () => {
		expect(() =>
			surfaceConsoleEvent({ ...event('text'), payload_json: '{broken' })
		).toThrow(/Malformed text event/);
	});

	it('keeps streamed narration open across provider-call metadata', () => {
		const projected = [
			surfaceConsoleEvent(event('text', { delta: 'Let me read the remaining ' })),
			surfaceConsoleEvent(event('text', { provider: 'openai', model: 'gpt-5' })),
			surfaceConsoleEvent(event('text', { delta: 'core physics files.' }))
		];
		expect(projected[1].type).toBe('telemetry');
		expect(displayConsoleEvents(projected)).toEqual([
			expect.objectContaining({ type: 'text', text: 'Let me read the remaining core physics files.', _open: true })
		]);
	});

	it('preserves tool identity on tool-scoped failures', () => {
		const projected = surfaceConsoleEvent(
			event('error', {
				error: 'permission denied',
				tool_name: 'terminal',
				tool_call_id: 'call-1',
				is_error: true
			})
		);

		expect(projected).toMatchObject({
			type: 'failure',
			error: 'permission denied',
			tool_name: 'terminal',
			tool_call_id: 'call-1',
			is_error: true
		});
	});

	it('renders a failed tool result without treating it as a terminal run event', () => {
		const failure = {
			type: 'failure',
			error: 'permission denied',
			tool_name: 'terminal',
			tool_call_id: 'call-1',
			is_error: true
		};
		render(
			<ToolCallCard
				event={{
					type: 'tool_call',
					tool_name: 'terminal',
					tool_call_id: 'call-1',
					input: { cmd: 'go build' }
				}}
				result={failure}
			/>
		);

		expect(screen.getByText('FAILED')).toBeInTheDocument();
		expect(screen.queryByText('DONE')).not.toBeInTheDocument();
		expect(isRunTerminalEvent(failure)).toBe(false);
		expect(isRunTerminalEvent({ type: 'failure', error: 'provider unavailable' })).toBe(true);
	});

	it('consumes buffered events after the active turn receives its run ID', () => {
		const buffered = [
			{ ...event('text', { text: 'before submit resolved' }), seq: 13, run_id: 'run-2' }
		];
		const unresolved = {
			windowId: 'chat-1',
			turnId: 'turn-1',
			runId: null,
			afterSeq: 12
		};

		expect(surfaceEventsForTurn(buffered, unresolved)).toEqual([]);
		expect(surfaceEventsForTurn(buffered, { ...unresolved, runId: 'run-2' })).toEqual(buffered);
	});

	it('keeps following shared session events across goal continuation run IDs', () => {
		const events = [
			{ ...event('completion', { status: 'succeeded' }), seq: 13, run_id: 'run-1' },
			{ ...event('task', { state: 'active', verdict: 'continue' }), seq: 14, run_id: 'run-1' },
			{ ...event('text', { text: 'continued work' }), seq: 15, run_id: 'run-2' },
			{ ...event('completion', { state: 'done', verdict: 'done' }), seq: 16, run_id: 'run-2' }
		];
		const turn = {
			windowId: 'chat-1',
			turnId: 'turn-1',
			runId: 'run-1',
			afterSeq: 12,
			goalMode: true
		};

		expect(surfaceEventsForTurn(events, turn)).toEqual(events);
		expect(finalGoalJudgementState(events.slice(0, 2))).toBeNull();
		expect(finalGoalJudgementState(events)).toBe('done');
		expect(surfaceConsoleEvent(events.at(-1)!).is_error).toBe(false);
	});

	it.each([
		['done', false],
		['paused', false],
		['exhausted', false],
		['failed', true]
	] as const)('projects final goal state %s as a terminal result', (state, isError) => {
		const judgement = event('completion', { state });
		expect(finalGoalJudgementState([judgement])).toBe(state);
		expect(surfaceConsoleEvent(judgement)).toEqual(
			expect.objectContaining({ type: 'result', is_error: isError })
		);
	});

	it('contains no production dependency on the legacy console stream', () => {
		const consoleSource = readFileSync(
			resolve(process.cwd(), 'src/routes/Console.tsx'),
			'utf8'
		);
		const apiSource = readFileSync(resolve(process.cwd(), 'src/lib/api.ts'), 'utf8');
		expect(consoleSource).not.toContain('consoleChatStream');
		expect(apiSource).not.toContain('/v1/console/stream');
	});
});
