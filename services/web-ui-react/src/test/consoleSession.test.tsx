import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { surfaceConsoleEvent } from '../routes/Console';
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
