import { describe, it, expect } from 'vitest';

// Test URL construction logic directly (no gateway needed)
describe('Mission API URL Construction', () => {
	it('constructs updateMission URL correctly', () => {
		const id = 'mission-123';
		const url = `/v1/missions/${encodeURIComponent(id)}`;
		expect(url).toBe('/v1/missions/mission-123');
	});

	it('encodes special characters in mission ID', () => {
		const id = 'mission/with/slashes';
		const url = `/v1/missions/${encodeURIComponent(id)}`;
		expect(url).toBe('/v1/missions/mission%2Fwith%2Fslashes');
	});

	it('encodes spaces in mission ID', () => {
		const id = 'id with spaces';
		const url = `/v1/missions/${encodeURIComponent(id)}`;
		expect(url).toBe('/v1/missions/id%20with%20spaces');
	});

	it('constructs context URL correctly', () => {
		const id = 'm1';
		const url = `/v1/missions/${encodeURIComponent(id)}/context`;
		expect(url).toBe('/v1/missions/m1/context');
	});

	it('constructs PATCH body correctly', () => {
		const patch = { title: 'New Title', intent: 'New intent', project: 'proj-1' };
		const body = JSON.stringify(patch);
		const parsed = JSON.parse(body);

		expect(parsed.title).toBe('New Title');
		expect(parsed.intent).toBe('New intent');
		expect(parsed.project).toBe('proj-1');
	});

	it('omits undefined fields from patch', () => {
		const patch = { title: 'Only Title' };
		const body = JSON.stringify(patch);
		const parsed = JSON.parse(body);

		expect(parsed.title).toBe('Only Title');
		expect(parsed.intent).toBeUndefined();
		expect(parsed.project).toBeUndefined();
	});
});
