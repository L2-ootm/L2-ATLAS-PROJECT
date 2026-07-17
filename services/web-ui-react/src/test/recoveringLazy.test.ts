import { describe, expect, it, vi } from 'vitest';
import { isStaleChunkError, loadWithChunkRecovery } from '../lib/recoveringLazy';

function environment(initial: Record<string, string> = {}) {
	const values = new Map(Object.entries(initial));
	return {
		values,
		reload: vi.fn(),
		api: {
			get: (key: string) => values.get(key) ?? null,
			set: (key: string, value: string) => values.set(key, value),
			remove: (key: string) => values.delete(key),
			reload: vi.fn()
		}
	};
}

describe('lazy chunk recovery', () => {
	it('recognizes the browser dynamic-import failure', () => {
		expect(isStaleChunkError(new TypeError('Failed to fetch dynamically imported module: /assets/Graph-old.js'))).toBe(true);
		expect(isStaleChunkError(new Error('Graph query failed'))).toBe(false);
	});

	it('reloads once for a stale hashed chunk and then leaves the promise pending', async () => {
		const env = environment();
		const pending = loadWithChunkRecovery(
			'graph',
			() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: /assets/Graph-old.js')),
			env.api
		);
		await Promise.resolve();
		await Promise.resolve();
		expect(env.api.reload).toHaveBeenCalledOnce();
		expect(env.values.get('atlas.chunk-recovery.graph')).toBe('1');
		void pending;
	});

	it('does not enter a reload loop when the replacement chunk also fails', async () => {
		const env = environment({ 'atlas.chunk-recovery.graph': '1' });
		await expect(loadWithChunkRecovery(
			'graph',
			() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: /assets/Graph-old.js')),
			env.api
		)).rejects.toThrow('Failed to fetch');
		expect(env.api.reload).not.toHaveBeenCalled();
	});
});
