import { describe, expect, it } from 'vitest';
import { distanceFromBottom, isNearBottom } from '../lib/scrollFollow';

describe('scroll follow boundary', () => {
	it('follows while the viewport remains within the near-bottom threshold', () => {
		expect(
			isNearBottom({ scrollHeight: 1_000, scrollTop: 620, clientHeight: 200 })
		).toBe(true);
	});

	it('detaches once the operator scrolls beyond the threshold', () => {
		expect(
			isNearBottom({ scrollHeight: 1_000, scrollTop: 619, clientHeight: 200 })
		).toBe(false);
	});

	it('clamps transient over-scroll geometry to zero', () => {
		expect(
			distanceFromBottom({ scrollHeight: 1_000, scrollTop: 850, clientHeight: 200 })
		).toBe(0);
	});
});
