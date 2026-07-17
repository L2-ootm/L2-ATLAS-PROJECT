import { describe, expect, it } from 'vitest';
import type { AuditEvent, ConsoleChatEvent } from '../lib/api';
import { projectAuditEvents, projectConsoleEvents } from '../lib/logProjection';

function audit(cursor: number, event_type: string, data: unknown = {}, run_id = 'run-1'): AuditEvent {
	return {
		id: `event-${cursor}`,
		cursor,
		run_id,
		event_type,
		data,
		timestamp: `2026-07-16T12:00:${String(cursor).padStart(2, '0')}Z`,
		session_id: null,
		task_id: null,
		tool_call_id: null,
		tool_name: null,
		duration_ms: null,
		policy_result: null
	};
}

describe('log projection', () => {
	it('groups adjacent deltas and preserves the full text in cursor order', () => {
		const projected = projectAuditEvents([
			audit(3, 'llm_delta', { delta: 'world' }),
			audit(2, 'llm_delta', { delta: 'hello ' }),
			audit(1, 'tool_call')
		]);
		expect(projected).toHaveLength(2);
		expect(projected[0]).toMatchObject({ count: 2, charCount: 11, text: 'hello world' });
		expect(projected[0].members).toHaveLength(2);
	});

	it('does not group across tool boundaries or different runs', () => {
		const projected = projectAuditEvents([
			audit(1, 'llm_delta', { delta: 'a' }),
			audit(2, 'tool_call'),
			audit(3, 'llm_delta', { delta: 'b' }),
			audit(4, 'llm_delta', { delta: 'c' }, 'run-2')
		]);
		expect(projected.map((item) => item.count)).toEqual([1, 1, 1, 1]);
	});

	it('groups normalized console text deltas without dropping raw members', () => {
		const events: ConsoleChatEvent[] = [
			{ type: 'text_delta', text: 'alpha ' },
			{ type: 'text_delta', text: 'beta' },
			{ type: 'tool_call', tool_name: 'read_file' }
		];
		const projected = projectConsoleEvents(events);
		expect(projected[0]).toMatchObject({ count: 2, text: 'alpha beta', charCount: 10 });
		expect(projected[0].members).toEqual(events.slice(0, 2));
	});
});
