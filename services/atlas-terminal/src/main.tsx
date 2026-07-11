/**
 * atlas-terminal entry — boots the vendored donor TUI over the ATLAS gateway
 * through the fetch-adapter seam (no second backend, no donor worker thread).
 *
 * `--smoke` runs headless: adapter probe only, no renderer, exit 0/1.
 */
import { createAtlasFetch, createAtlasFetchHandle } from './adapter/atlasFetch';
import { toGlobalEvent } from './adapter/events';

const GATEWAY = process.env['ATLAS_GATEWAY_URL'] ?? 'http://127.0.0.1:8484';

async function probe(): Promise<string> {
	const f = createAtlasFetch({ gateway: GATEWAY });
	try {
		const res = await f('http://donor.local/config');
		if (!res.ok) return `gateway unreachable (${res.status})`;
		const body = (await res.json()) as { model?: string };
		return body.model ? `LIVE ${body.model}` : 'gateway up (no model configured)';
	} catch {
		return 'gateway offline';
	}
}

if (process.argv.includes('--smoke')) {
	const status = await probe();
	console.log(`ATLAS TERMINAL OK — ${status}`);
	process.exit(0);
}

const { tui } = await import('@tui/app');
const handle = createAtlasFetchHandle({ gateway: GATEWAY });

const promptFlag = process.argv.indexOf('--prompt');
await tui({
	// The adapter intercepts every request; the URL is a routing origin only.
	url: 'http://atlas.local',
	args: {
		prompt: promptFlag >= 0 ? process.argv[promptFlag + 1] : undefined,
		continue: process.argv.includes('--continue'),
		neverAsk: false
	},
	config: {} as never,
	directory: process.cwd(),
	fetch: handle.fetch,
	events: {
		// The TUI consumes GlobalEvent {directory, payload}; bare DonorEvents
		// crash useEvent() on `event.payload.type`.
		subscribe: async (handler) => handle.bus.subscribe((event) => handler(toGlobalEvent(event) as never))
	}
});
await handle.chat.dispose();
process.exit(0);
