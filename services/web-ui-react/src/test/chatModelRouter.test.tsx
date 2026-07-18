import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatModelRouter } from '../components/chat/ChatModelRouter';

const api = vi.hoisted(() => ({
	listModels: vi.fn(),
	getConfig: vi.fn(),
	patchConfig: vi.fn()
}));

vi.mock('../lib/api', async (importOriginal) => ({
	...(await importOriginal<typeof import('../lib/api')>()),
	...api
}));

const config = {
	revision: 7,
	provider: { name: 'openrouter', model: 'primary', api_key: '', base_url: null },
	functions: {
		autoconfig: true,
		actor_model: '',
		curator_model: '',
		auxiliary_model: '',
		judge_model: ''
	},
	runtime: { default_agent: 'native', iteration_budget: 90, compression: 'auto' },
	gateway: { rust_port: 8484, messaging_enabled: true, messaging_port: 8485 },
	cockpit: { port: 5173, branding: 'atlas' },
	modules: {}
};

describe('ChatModelRouter', () => {
	beforeEach(() => {
		api.listModels.mockReset().mockResolvedValue({
			models: [{
				provider: 'openai-codex', model_id: 'gpt-5.4-mini', source: 'test',
				first_seen: '', last_seen: '', active: true
			}],
			count: 1
		});
		api.getConfig.mockReset().mockResolvedValue(config);
		api.patchConfig.mockReset().mockResolvedValue({
			...config,
			revision: 8,
			functions: { ...config.functions, actor_model: 'openai-codex/gpt-5.4-mini' }
		});
	});

	it('routes the durable actor role through the optimistic config plane', async () => {
		render(<ChatModelRouter provider="openrouter" modelId="primary" busy={false} />);
		fireEvent.click(screen.getByRole('button', { name: /MODEL MESH/i }));
		await screen.findByRole('heading', { name: 'Model routing' });
		fireEvent.click(screen.getByRole('button', { name: /ACTORS/i }));
		fireEvent.click(await screen.findByRole('button', { name: /gpt-5\.4-mini/i }));
		await waitFor(() => expect(api.patchConfig).toHaveBeenCalledWith(7, {
			'functions.actor_model': 'openai-codex/gpt-5.4-mini'
		}));
	});

	it('keeps routing readable but locked while a turn is live', async () => {
		render(<ChatModelRouter provider="openrouter" modelId="primary" busy />);
		fireEvent.click(screen.getByRole('button', { name: /MODEL MESH/i }));
		expect(await screen.findByText(/Routing unlocks when it settles/)).toBeInTheDocument();
		expect(await screen.findByRole('button', { name: /gpt-5\.4-mini/i })).toBeDisabled();
	});
});
