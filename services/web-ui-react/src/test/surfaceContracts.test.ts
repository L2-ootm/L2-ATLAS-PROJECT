import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
	parseSurfaceEvent,
	parseSurfaceReplay,
	SURFACE_EVENT_KINDS
} from '../lib/surfaceContracts';

const fixturePath = resolve(
	process.cwd(),
	'../agent-runtime/tests/fixtures/surface_event_parity.json'
);

describe('frozen surface contracts', () => {
	it('matches the runtime fixture hash and preserves terminal order', () => {
		const raw = readFileSync(fixturePath);
		expect(createHash('sha256').update(raw).digest('hex').toUpperCase()).toBe(
			'D539F5E0E93877BD4061CA27F767FA578445285FC0F62DCFF850DE1F731F6283'
		);
		const fixture = JSON.parse(raw.toString()) as {
			session_id: string;
			terminal_outcome: string;
			events: unknown[];
		};
		const replay = parseSurfaceReplay({
			session_id: fixture.session_id,
			after_seq: -1,
			events: fixture.events
		});
		expect(replay.events.map((event) => event.kind)).toEqual([...SURFACE_EVENT_KINDS]);
		expect(replay.events.map((event) => event.seq)).toEqual(
			replay.events.map((_, index) => index)
		);
		const terminal = JSON.parse(replay.events.at(-1)!.payload_json) as { status: string };
		expect(terminal.status).toBe(fixture.terminal_outcome);
	});

	it('fails visibly on unknown or malformed events', () => {
		expect(() =>
			parseSurfaceEvent({
				session_id: 'surface-1',
				seq: 0,
				kind: 'silently_drop_me',
				run_id: null,
				occurred_at: 'now',
				payload_json: '{}'
			})
		).toThrow(/unknown surface event kind/);
		expect(() => parseSurfaceReplay({ session_id: 'surface-1', events: [{ seq: 0 }] })).toThrow();
	});
});
