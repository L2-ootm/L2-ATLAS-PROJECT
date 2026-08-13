import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DisposablesPanel } from '../components/control/DisposablesPanel';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listScratchpad: vi.fn(),
		setScratchpadPinned: vi.fn(),
		deleteScratchpadEntry: vi.fn(),
		sweepScratchpad: vi.fn()
	};
});

function entry(over: Partial<api.ScratchpadEntry> = {}): api.ScratchpadEntry {
	return {
		id: 'probe',
		scope: 'run',
		owner: 'run-1',
		run_id: 'run-1',
		session_id: 'sess-1',
		kind: 'tool',
		title: 'Probe the gateway',
		path: 'C:\\Users\\x\\.atlas\\scratch\\tools\\probe.py',
		ttl_policy: 'next_startup',
		expires_at: null,
		pinned: false,
		chars: 42,
		created_at: '2026-08-12T00:00:00Z',
		updated_at: '2026-08-12T00:00:00Z',
		rationale: 'searched atlas_module and the tool catalog; nothing reaches the gateway, one-off',
		...over
	};
}

beforeEach(() => {
	vi.mocked(api.listScratchpad).mockResolvedValue({
		entries: [
			entry(),
			entry({
				id: 'the-plan',
				kind: 'plan',
				title: 'The plan',
				path: '',
				ttl_policy: 'session',
				rationale: ''
			})
		],
		count: 2,
		pinned: 0,
		tools: 1
	});
	vi.mocked(api.setScratchpadPinned).mockResolvedValue(undefined);
	vi.mocked(api.deleteScratchpadEntry).mockResolvedValue(undefined);
	vi.mocked(api.sweepScratchpad).mockResolvedValue({ swept: true, detail: 'startup=1 total=1 files=1' });
});

describe('DisposablesPanel', () => {
	it('shows what is held, its expiry in plain words, and the file name', async () => {
		render(<DisposablesPanel />);
		expect(await screen.findByText('Probe the gateway')).toBeInTheDocument();
		expect(screen.getByText('2 ENTRIES · 1 TOOLS · 0 KEPT')).toBeInTheDocument();
		// A TTL is a risk of loss: say when it dies, not what the policy is named.
		expect(screen.getByText(/UNTIL RESTART · 42C/)).toBeInTheDocument();
		expect(screen.getByText(/WITH ITS SESSION/)).toBeInTheDocument();
		expect(screen.getByText('probe.py')).toBeInTheDocument();
	});

	it('shows why a disposable exists, so pin-or-expire is a decidable question', async () => {
		render(<DisposablesPanel />);
		expect(
			await screen.findByText(/searched atlas_module and the tool catalog/)
		).toBeInTheDocument();
		// An entry with no recorded decision renders no empty line for one.
		expect(screen.getAllByText(/searched atlas_module/)).toHaveLength(1);
	});

	it('pins an entry — the promotion out of disposability', async () => {
		render(<DisposablesPanel />);
		await userEvent.click(await screen.findByRole('button', { name: 'Pin probe' }));
		expect(api.setScratchpadPinned).toHaveBeenCalledWith('probe', true);
		await waitFor(() => expect(api.listScratchpad).toHaveBeenCalledTimes(2));
	});

	it('sweeps expired entries and reloads', async () => {
		render(<DisposablesPanel />);
		await userEvent.click(await screen.findByRole('button', { name: /SWEEP EXPIRED/ }));
		expect(api.sweepScratchpad).toHaveBeenCalled();
		await waitFor(() => expect(api.listScratchpad).toHaveBeenCalledTimes(2));
	});

	it('reports a gateway failure instead of silently doing nothing', async () => {
		vi.mocked(api.deleteScratchpadEntry).mockRejectedValue(new Error('offline'));
		render(<DisposablesPanel />);
		await userEvent.click(await screen.findByRole('button', { name: 'Delete probe' }));
		expect(await screen.findByText(/gateway rejected that/i)).toBeInTheDocument();
	});

	it('explains the empty state instead of rendering a blank panel', async () => {
		vi.mocked(api.listScratchpad).mockResolvedValue({ entries: [], count: 0, pinned: 0, tools: 0 });
		render(<DisposablesPanel />);
		expect(await screen.findByText(/Nothing held/i)).toBeInTheDocument();
	});
});
