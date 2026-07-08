import { describe, expect, it } from 'bun:test';
import { formatSessionCreateError } from '../src/tui/util/sessionError';

describe('session create error diagnostics', () => {
	it('formats SDK errors as stable JSON for terminal logs', () => {
		const formatted = formatSessionCreateError({
			status: 500,
			statusText: 'Internal Server Error',
			error: { code: 'gateway_failed', message: 'boom' },
			request: { method: 'POST', url: '/session?workspace=abc' }
		});

		expect(formatted).toContain('"status":500');
		expect(formatted).toContain('"code":"gateway_failed"');
		expect(formatted).toContain('"url":"/session?workspace=abc"');
	});

	it('formats Error instances and circular objects without throwing', () => {
		const err: Record<string, unknown> = { cause: new Error('network down') };
		err.self = err;

		const formatted = formatSessionCreateError(err);

		expect(formatted).toContain('network down');
		expect(formatted).toContain('[Circular]');
	});
});
