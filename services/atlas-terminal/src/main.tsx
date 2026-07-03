/**
 * atlas-terminal STAGE 0 entry — proves the Solid+OpenTUI stack boots under
 * Bun on this machine and that the ATLAS fetch adapter reaches the gateway.
 * The donor TUI tree replaces this shell in STAGE 2 (see the refactor plan).
 *
 * `--smoke` runs headless: adapter probe only, no renderer, exit 0/1.
 */
import { createAtlasFetch } from './adapter/atlasFetch';

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
	console.log(`ATLAS TERMINAL STAGE0 OK — ${status}`);
	process.exit(0);
}

const { render } = await import('@opentui/solid');
const { createSignal, onMount } = await import('solid-js');

function App() {
	const [status, setStatus] = createSignal('probing gateway…');
	onMount(() => {
		void probe().then(setStatus);
	});
	return (
		<box style={{ flexDirection: 'column', padding: 2 }}>
			<text style={{ fg: '#4F8BFF' }}>A T L A S — terminal (stage 0)</text>
			<text style={{ fg: '#9BA0AD' }}>donor seam: MiMo-Code presentation ▸ ATLAS gateway adapter</text>
			<text>{status()}</text>
			<text style={{ fg: '#565C6B' }}>ctrl+c to exit</text>
		</box>
	);
}

await render(() => <App />);
