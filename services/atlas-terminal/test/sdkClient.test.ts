import { describe, expect, it } from 'bun:test';
import { createOpencodeClient } from '@atlas/sdk/v2';
import { createAtlasFetchHandle } from '../src/adapter/atlasFetch';

/**
 * Regression guard for the generated SDK v2 client talking to the ATLAS
 * adapter — the exact path `src/tui/context/sdk.tsx` uses in the live app.
 * The chat-loop tests exercise `handle.fetch` directly; this exercises the
 * client the TUI actually calls, so a future request-shape mismatch (query
 * vs body params, header requirements, base URL handling) fails here instead
 * of only surfacing as "Creating a session failed" during manual UAT.
 */
describe('SDK v2 client over the ATLAS adapter', () => {
	it('creates and lists a session with no client-level error', async () => {
		const handle = createAtlasFetchHandle({ gateway: 'http://127.0.0.1:8484' });
		const sdk = createOpencodeClient({
			baseUrl: 'http://atlas.local',
			directory: process.cwd(),
			fetch: handle.fetch
		});

		const created = await sdk.session.create({ title: 'smoke session' });
		expect(created.error).toBeUndefined();
		expect(created.data?.id).toBeDefined();

		const listed = await sdk.session.list();
		expect(listed.error).toBeUndefined();
		expect(listed.data?.some((s) => s.id === created.data!.id)).toBe(true);
	});
});
