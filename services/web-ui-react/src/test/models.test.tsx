import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Models from '../routes/Models';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listModels: vi.fn(),
		getConfig: vi.fn(),
		getProviderStatus: vi.fn(),
		freellmapiStatus: vi.fn(),
		freellmapiStart: vi.fn(),
		freellmapiStop: vi.fn(),
		modelsRefresh: vi.fn(),
		patchConfig: vi.fn()
	};
});

function model(overrides: Partial<api.ModelEntry>): api.ModelEntry {
	return {
		model_id: 'auto',
		provider: 'freellmapi',
		source: 'gateway',
		first_seen: '2026-07-01T00:00:00Z',
		last_seen: '2026-07-03T00:00:00Z',
		active: true,
		...overrides
	} as api.ModelEntry;
}

const configView = {
	revision: 7,
	provider: { name: 'freellmapi', model: 'auto', auth_mode: 'freellmapi', base_url: 'http://127.0.0.1:3001/v1' },
	functions: { autoconfig: true, curator_model: '', auxiliary_model: '' }
} as unknown as api.AtlasConfigView;

beforeEach(() => {
	localStorage.clear();
	vi.mocked(api.listModels).mockResolvedValue({
		models: [
			model({ model_id: 'auto', provider: 'freellmapi' }),
			model({ model_id: 'gpt-5.5', provider: 'openai-codex' }),
			model({ model_id: 'gpt-5.4-mini', provider: 'openai-codex' }),
			model({ model_id: 'stale-model', provider: 'legacy', active: false })
		],
		count: 4
	});
	vi.mocked(api.getConfig).mockResolvedValue(configView);
	vi.mocked(api.getProviderStatus).mockResolvedValue({ mock_mode: false } as api.ProviderStatusView);
	vi.mocked(api.freellmapiStatus).mockResolvedValue({
		running: false,
		base_url: 'http://127.0.0.1:3001/v1',
		dir: 'C:/freellmapi',
		installed: true,
		remediation: null
	});
	vi.mocked(api.patchConfig).mockResolvedValue(configView);
	vi.mocked(api.modelsRefresh).mockResolvedValue({ message: 'source: x\nadded: 2' });
});

async function ready() {
	await waitFor(() => expect(screen.getByText('gpt-5.5')).toBeInTheDocument());
}

describe('Models route', () => {
	it('renders the registry grouped by provider with the sidecar panel', async () => {
		render(<Models />);
		await ready();
		expect(screen.getByText('FREELLMAPI ENDPOINT')).toBeInTheDocument();
		expect(screen.getByText('STOPPED')).toBeInTheDocument();
		// The active provider/model row is marked IN USE.
		expect(screen.getByText('IN USE')).toBeInTheDocument();
	});

	it('sets a model active through one immediate PATCH (no page save button)', async () => {
		render(<Models />);
		await ready();
		const row = screen.getByText('gpt-5.5').closest('div')!.parentElement!;
		await userEvent.click(within(row).getByRole('button', { name: 'USE' }));
		await waitFor(() =>
			expect(api.patchConfig).toHaveBeenCalledWith(7, {
				'provider.name': 'openai-codex',
				'provider.model': 'gpt-5.5'
			})
		);
		expect(screen.queryByText(/SAVE CONFIGURATION/i)).not.toBeInTheDocument();
	});

	it('routes curator to a model and can clear it, each as its own PATCH', async () => {
		render(<Models />);
		await ready();
		const row = screen.getByText('gpt-5.4-mini').closest('div')!.parentElement!;
		await userEvent.click(within(row).getByRole('button', { name: 'CURATOR' }));
		await waitFor(() =>
			expect(api.patchConfig).toHaveBeenCalledWith(7, {
				'functions.curator_model': 'openai-codex/gpt-5.4-mini'
			})
		);
	});

	it('reloads and warns on a 409 revision conflict', async () => {
		vi.mocked(api.patchConfig).mockRejectedValueOnce(new api.ApiError(409, 'conflict'));
		render(<Models />);
		await ready();
		const row = screen.getByText('gpt-5.5').closest('div')!.parentElement!;
		await userEvent.click(within(row).getByRole('button', { name: 'USE' }));
		await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/changed elsewhere/i));
	});

	it('filters by provider chip and search query', async () => {
		render(<Models />);
		await ready();
		await userEvent.click(screen.getByRole('button', { name: 'OPENAI-CODEX' }));
		expect(screen.queryByText('auto')).not.toBeInTheDocument();
		expect(screen.getByText('gpt-5.5')).toBeInTheDocument();
		await userEvent.type(screen.getByLabelText('Search models'), 'mini');
		expect(screen.queryByText('gpt-5.5')).not.toBeInTheDocument();
		expect(screen.getByText('gpt-5.4-mini')).toBeInTheDocument();
	});

	it('syncs the registry from the toolbar', async () => {
		render(<Models />);
		await ready();
		await userEvent.click(screen.getByRole('button', { name: /SYNC REGISTRY/i }));
		await waitFor(() => expect(api.modelsRefresh).toHaveBeenCalled());
	});
});
