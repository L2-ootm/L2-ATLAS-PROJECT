import { describe, expect, it } from 'vitest';
import { displayConsoleEvents } from '../lib/consoleEventGroups';
import type { ConsoleChatEvent } from '../lib/api';

const status = (text: string): ConsoleChatEvent => ({ type: 'status', text });

describe('status coalescing', () => {
	it('joins consecutive status lines into one row', () => {
		const out = displayConsoleEvents([status('run started'), status('runtime native')]);
		expect(out).toHaveLength(1);
		expect(out[0].text).toBe('run started · runtime native');
	});

	it('drops a repeated segment instead of printing it twice', () => {
		// surfaceConsoleEvent falls back to `runtime <name>` for any
		// tool_call-kind payload carrying no transition or privacy warning, so
		// two unrelated run events legitimately project to the same words.
		const out = displayConsoleEvents([
			status('run started'),
			status('runtime native'),
			status('runtime native'),
			status('free models may log prompts')
		]);
		expect(out).toHaveLength(1);
		expect(out[0].text).toBe('run started · runtime native · free models may log prompts');
	});

	it('keeps a later distinct status even after a duplicate is dropped', () => {
		const out = displayConsoleEvents([status('runtime native'), status('runtime native'), status('run succeeded')]);
		expect(out[0].text).toBe('runtime native · run succeeded');
	});

	it('ignores empty status text entirely', () => {
		const out = displayConsoleEvents([status('run started'), status('')]);
		expect(out[0].text).toBe('run started');
	});

	it('does not merge statuses separated by another event kind', () => {
		const out = displayConsoleEvents([
			status('run started'),
			{ type: 'text', text: 'answer' },
			status('run succeeded')
		]);
		const statuses = out.filter((event) => event.type === 'status');
		expect(statuses.map((event) => event.text)).toEqual(['run started', 'run succeeded']);
	});
});
