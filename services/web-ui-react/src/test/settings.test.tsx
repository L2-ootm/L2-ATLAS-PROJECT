import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Settings from '../routes/Settings';
import {
	ApiError,
	freellmapiStatus,
	getConfig,
	getProviderModes,
	getProviderStatus,
	listModels,
	patchConfig,
	storeProviderKey,
	type AtlasConfigView,
	type ProviderModeView,
	type ProviderStatusView
} from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		getConfig: vi.fn(),
		getProviderStatus: vi.fn(),
		getProviderModes: vi.fn(),
		listModels: vi.fn(),
		patchConfig: vi.fn(),
		storeProviderKey: vi.fn(),
		importCodex: vi.fn(),
		freellmapiStatus: vi.fn(),
		freellmapiStart: vi.fn(),
		freellmapiStop: vi.fn()
	};
});

function configView(overrides: Partial<AtlasConfigView['provider']> = {}): AtlasConfigView {
	return {
		revision: 7,
		provider: {
			name: 'openai-codex',
			model: 'gpt-5.4-codex',
			api_key: '',
			base_url: null,
			auth_mode: 'oauth_import',
			reasoning_effort: '',
			...overrides
		},
		functions: { autoconfig: true, curator_model: '', auxiliary_model: '' },
		runtime: { default_agent: 'native', iteration_budget: 25, compression: 'auto' },
		gateway: { rust_port: 4780, messaging_enabled: false, messaging_port: 4781 },
		cockpit: { port: 5173, branding: 'atlas' },
		modules: {}
	};
}

function statusView(overrides: Partial<ProviderStatusView> = {}): ProviderStatusView {
	return {
		provider: 'openai-codex',
		model: 'gpt-5.4-codex',
		auth_mode: 'oauth_import',
		auth_mode_label: 'Codex OAuth import',
		base_url: null,
		credentials_present: true,
		mock_mode: false,
		remediation: null,
		reasoning_effort: null,
		privacy_warning: null,
		...overrides
	};
}

const modeBoard: ProviderModeView[] = [
	{ mode: 'api_key', label: 'API KEY', active: false, available: false, detail: 'no credential', remediation: null },
	{ mode: 'oauth_import', label: 'CODEX OAUTH', active: true, available: true, detail: 'imported', remediation: null },
	{ mode: 'claude_code', label: 'CLAUDE CODE', active: false, available: true, detail: 'session found', remediation: null },
	{ mode: 'freellmapi', label: 'FREE LLM API', active: false, available: false, detail: 'needs base URL', remediation: null }
];

function arm(config = configView(), status = statusView()) {
	vi.mocked(getConfig).mockResolvedValue(config);
	vi.mocked(getProviderStatus).mockResolvedValue(status);
	vi.mocked(getProviderModes).mockResolvedValue(modeBoard);
	vi.mocked(listModels).mockResolvedValue({ models: [], count: 0 });
	vi.mocked(patchConfig).mockResolvedValue(config);
	vi.mocked(storeProviderKey).mockResolvedValue({
		provider: 'openai-codex',
		status: 'stored',
		redacted_hint: 'sk-***'
	});
	// Sidecar absent by default so freellmapi mode does not auto-fill base URL/key.
	vi.mocked(freellmapiStatus).mockResolvedValue({
		running: false,
		base_url: '',
		dir: null,
		installed: false,
		api_key: null,
		remediation: null
	});
}

beforeEach(() => {
	vi.clearAllMocks();
});

describe('Settings route', () => {
	it('renders the mode board, live status, and current revision', async () => {
		arm();
		render(<Settings />);
		expect(await screen.findByText('CODEX OAUTH')).toBeInTheDocument();
		expect(screen.getByText('LIVE')).toBeInTheDocument();
		expect(screen.getByText('ACTIVE NOW')).toBeInTheDocument();
		expect(screen.getByText('revision 7')).toBeInTheDocument();
		// api_key inactive → no API KEY field in oauth_import mode
		expect(screen.queryByLabelText('API key')).not.toBeInTheDocument();
	});

	it('saves effort and function routing through one optimistic PATCH', async () => {
		arm();
		const user = userEvent.setup();
		render(<Settings />);
		await screen.findByText('CODEX OAUTH');
		await user.click(screen.getByRole('button', { name: 'HIGH' }));
		const curator = screen.getByLabelText('Curator model override');
		await user.type(curator, 'openai-codex/gpt-5.4-mini');
		await user.click(screen.getByRole('button', { name: 'SAVE CONFIGURATION' }));
		await waitFor(() => expect(patchConfig).toHaveBeenCalledTimes(1));
		expect(patchConfig).toHaveBeenCalledWith(7, {
			'provider.name': 'openai-codex',
			'provider.model': 'gpt-5.4-codex',
			'provider.auth_mode': 'oauth_import',
			'provider.base_url': null,
			'provider.reasoning_effort': 'high',
			'functions.autoconfig': true,
			'functions.curator_model': 'openai-codex/gpt-5.4-mini',
			'functions.auxiliary_model': ''
		});
		expect(storeProviderKey).not.toHaveBeenCalled();
		expect(await screen.findByText('Provider configuration saved.')).toBeInTheDocument();
	});

	it('routes secrets through the auth store before patching in api_key mode', async () => {
		arm(configView({ auth_mode: 'api_key', name: 'openrouter', model: 'x/y' }));
		const user = userEvent.setup();
		render(<Settings />);
		await screen.findByText('CODEX OAUTH');
		await user.type(screen.getByLabelText('API key'), 'sk-test-123');
		await user.click(screen.getByRole('button', { name: 'SAVE CONFIGURATION' }));
		await waitFor(() => expect(patchConfig).toHaveBeenCalledTimes(1));
		expect(storeProviderKey).toHaveBeenCalledWith('openrouter', 'sk-test-123', undefined);
		// key field cleared after the secret crossed once
		expect(screen.getByLabelText('API key')).toHaveValue('');
	});

	it('shows the privacy warning and requires a base URL for freellmapi', async () => {
		arm();
		const user = userEvent.setup();
		render(<Settings />);
		await screen.findByText('CODEX OAUTH');
		await user.click(screen.getByRole('button', { name: /FREE LLM API/ }));
		expect(screen.getByRole('alert')).toHaveTextContent(/Privacy warning/);
		await user.click(screen.getByRole('button', { name: 'SAVE CONFIGURATION' }));
		expect(patchConfig).not.toHaveBeenCalled();
		expect(screen.getByText('FreeLLMAPI mode requires a base URL.')).toBeInTheDocument();
	});

	it('surfaces a 409 revision conflict as a warn banner and refetches', async () => {
		arm();
		vi.mocked(patchConfig).mockRejectedValue(new ApiError(409, 'revision conflict', 'conflict', undefined, 9));
		const user = userEvent.setup();
		render(<Settings />);
		await screen.findByText('CODEX OAUTH');
		await user.click(screen.getByRole('button', { name: 'SAVE CONFIGURATION' }));
		expect(await screen.findByText(/Config changed elsewhere/)).toBeInTheDocument();
		// initial load + post-conflict refresh
		expect(getConfig).toHaveBeenCalledTimes(2);
	});

	it('shows the offline banner when the gateway is unreachable', async () => {
		vi.mocked(getConfig).mockRejectedValue(new Error('fetch failed'));
		vi.mocked(getProviderStatus).mockRejectedValue(new Error('fetch failed'));
		vi.mocked(getProviderModes).mockRejectedValue(new Error('fetch failed'));
		vi.mocked(listModels).mockResolvedValue({ models: [], count: 0 });
		render(<Settings />);
		expect(await screen.findByText(/GATEWAY OFFLINE/)).toBeInTheDocument();
	});
});
