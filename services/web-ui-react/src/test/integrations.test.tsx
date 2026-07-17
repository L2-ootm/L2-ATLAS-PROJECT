import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Integrations from '../routes/Integrations';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		checkHealth: vi.fn(),
		getToolManifests: vi.fn(),
		listChannels: vi.fn(),
		listModules: vi.fn(),
		messagingGatewayStatus: vi.fn(),
		discordStatus: vi.fn(),
		cashflowStatus: vi.fn()
	};
});

beforeEach(() => {
	vi.mocked(api.checkHealth).mockResolvedValue({ status: 'ok', db: 'ok' });
	vi.mocked(api.getToolManifests).mockResolvedValue([]);
	vi.mocked(api.listChannels).mockResolvedValue({ channels: [] });
	vi.mocked(api.listModules).mockResolvedValue({ modules: [], count: 0 });
	vi.mocked(api.messagingGatewayStatus).mockResolvedValue({ running: false, pid: null });
	vi.mocked(api.discordStatus).mockResolvedValue({ running: false, ready: false, guild_count: 0, pid: null });
	vi.mocked(api.cashflowStatus).mockResolvedValue({ running: false, backend: 'local' });
});

function renderPage() {
	return render(
		<MemoryRouter>
			<Integrations />
		</MemoryRouter>
	);
}

describe('Integrations status integrity', () => {
	it('shows an unreachable status endpoint as unknown, not stopped', async () => {
		vi.mocked(api.discordStatus).mockRejectedValue(new Error('endpoint unavailable'));
		vi.mocked(api.cashflowStatus).mockRejectedValue(new Error('endpoint unavailable'));
		renderPage();

		const discordDetail = await screen.findByText('sidecar status unavailable');
		const cashflowDetail = await screen.findByText('module status unavailable');
		expect(discordDetail.closest('[role="button"]')).toHaveTextContent('UNKNOWN');
		expect(cashflowDetail.closest('[role="button"]')).toHaveTextContent('UNKNOWN');
		expect(screen.queryByText('sidecar stopped')).not.toBeInTheDocument();
	});

	it('uses offline only when a reachable adapter reports stopped', async () => {
		renderPage();

		const discordDetail = await screen.findByText('sidecar stopped');
		expect(discordDetail.closest('[role="button"]')).toHaveTextContent('OFFLINE');
	});
});
