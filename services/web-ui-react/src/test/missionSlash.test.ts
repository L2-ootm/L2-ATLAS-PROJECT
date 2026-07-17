import { describe, expect, it } from 'vitest';
import { parseMissionSlashIntent } from '../lib/missionSlash';

describe('parseMissionSlashIntent', () => {
	it.each(['/goal Ship the release', '/mission Ship the release'])(
		'parses %s as a goal launch',
		(input) => {
			expect(parseMissionSlashIntent(input)).toEqual({
				kind: 'goal-launch',
				objective: 'Ship the release'
			});
		}
	);

	it.each(['/goal', '/mission   ', '/goal status', '/mission status'])(
		'parses %s as status without an agent prompt',
		(input) => {
			expect(parseMissionSlashIntent(input)).toEqual({ kind: 'goal-status' });
		}
	);

	it.each(['Ship the release', '/goals Ship the release', '/Goal Ship the release', '/missionary'])(
		'leaves %s as an ordinary prompt',
		(input) => {
			expect(parseMissionSlashIntent(input)).toBeNull();
		}
	);
});
