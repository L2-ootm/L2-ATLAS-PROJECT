import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'bun:test';

describe('cross-surface reference missions', () => {
	it('keeps atlas-terminal on the shared gateway event contract', () => {
		const fixture = JSON.parse(
			readFileSync(resolve(process.cwd(), '../agent-runtime/tests/fixtures/reference_missions.json'), 'utf8')
		) as { missions: Array<{ id: string; surface_projections: Record<string, Array<{ event_index: number; kind: string }>> }> };

		expect(fixture.missions).toHaveLength(8);
		for (const mission of fixture.missions) {
			const events = mission.surface_projections.atlas_terminal;
			expect(events.length, `${mission.id}: terminal projection`).toBeGreaterThan(0);
			expect(events.map((event) => event.event_index), `${mission.id}: ordered events`).toEqual(events.map((_, index) => index));
		}
	});
});
