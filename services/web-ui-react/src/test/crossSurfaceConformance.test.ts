import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
	parsePolicyReceipt,
	parseSurfaceReplay,
	SURFACE_EVENT_KINDS
} from '../lib/surfaceContracts';

const runtimeFixtures = resolve(process.cwd(), '../agent-runtime/tests/fixtures');

describe('cross-surface conformance', () => {
	it('preserves session/run identity, sequence, kinds, and terminal outcome', () => {
		const fixture = JSON.parse(
			readFileSync(resolve(runtimeFixtures, 'surface_event_parity.json'), 'utf8')
		) as {
			session_id: string;
			terminal_outcome: string;
			events: Array<{ run_id: string; payload_json: string }>;
		};
		const replay = parseSurfaceReplay({
			session_id: fixture.session_id,
			after_seq: -1,
			events: fixture.events
		});

		expect(new Set(replay.events.map((event) => event.session_id))).toEqual(
			new Set([fixture.session_id])
		);
		expect(new Set(replay.events.map((event) => event.run_id))).toEqual(
			new Set(['fixture-run'])
		);
		expect(replay.events.map((event) => event.kind)).toEqual(SURFACE_EVENT_KINDS);
		expect(replay.events.map((event) => event.seq)).toEqual(
			replay.events.map((_, index) => index)
		);
		expect(JSON.parse(replay.events.at(-1)!.payload_json).status).toBe(
			fixture.terminal_outcome
		);
	});

	it('consumes server receipt field names without reclassifying policy', () => {
		const receipt = parsePolicyReceipt(
			JSON.stringify({
				decision: 'deny',
				reason_code: 'hardline_block_device',
				source_layer: 'hardline',
				matched_rule_id: 'hardline-block-device',
				effective_preset: 'full_autonomy',
				maintenance_scope_used: false
			})
		);
		expect(receipt).toMatchObject({
			decision: 'deny',
			source_layer: 'hardline',
			reason_code: 'hardline_block_device'
		});
		expect(receipt).not.toHaveProperty('source');
	});

	it('keeps the global approval endpoint read-only and actions session-owned', () => {
		const api = readFileSync(resolve(process.cwd(), 'src/lib/api.ts'), 'utf8');
		expect(api).toContain("'/v1/tools/approvals?status=all'");
		expect(api).toContain('/v1/surface-sessions/${encodeURIComponent(session.id)}/approvals');
		expect(api).toContain("'X-Atlas-Surface-Owner': ownerToken");
		expect(api).not.toContain('/v1/tools/approvals/${encodeURIComponent(approval.id)}');
	});
});
