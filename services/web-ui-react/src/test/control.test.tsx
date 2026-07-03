import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom';
import Control from '../routes/Control';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		checkHealth: vi.fn(),
		listModules: vi.fn(),
		getConfig: vi.fn(),
		listChannels: vi.fn(),
		messagingGatewayStatus: vi.fn(),
		getToolManifests: vi.fn(),
		listToolApprovals: vi.fn(),
		getProviderStatus: vi.fn(),
		getProviderModes: vi.fn(),
		listModels: vi.fn()
	};
});

// restoreMocks:true wipes implementations between tests — re-arm per test.
beforeEach(() => {
	vi.mocked(api.checkHealth).mockResolvedValue({ status: 'ok', db: 'ok' });
	vi.mocked(api.listModules).mockResolvedValue({ modules: [], count: 0 });
	vi.mocked(api.getConfig).mockRejectedValue(new Error('offline'));
	vi.mocked(api.listChannels).mockResolvedValue({ channels: [] });
	vi.mocked(api.messagingGatewayStatus).mockResolvedValue({ running: false, pid: null });
	vi.mocked(api.getToolManifests).mockResolvedValue([]);
	vi.mocked(api.listToolApprovals).mockResolvedValue([
		{ id: 1, tool_name: 'workspace_write', status: 'pending', summary: 'write file' } as unknown as api.ToolApproval
	]);
	vi.mocked(api.getProviderStatus).mockResolvedValue(null as unknown as api.ProviderStatusView);
	vi.mocked(api.getProviderModes).mockResolvedValue([]);
	vi.mocked(api.listModels).mockResolvedValue({ models: [], count: 0 });
});

function renderAt(path: string) {
	return render(
		<MemoryRouter initialEntries={[path]}>
			<Routes>
				<Route path="/control" element={<Control />} />
				<Route path="/system" element={<Navigate to="/control" replace />} />
				<Route path="/settings" element={<Navigate to="/control?tab=provider" replace />} />
			</Routes>
		</MemoryRouter>
	);
}

describe('Control route', () => {
	it('renders the tablist with all sections and shows STATUS by default', async () => {
		renderAt('/control');
		const tablist = screen.getByRole('tablist', { name: /system control sections/i });
		expect(tablist).toBeInTheDocument();
		for (const label of ['STATUS', 'PROVIDER', 'TOOLS & POLICY', 'CHANNELS', 'MODULES', 'ABOUT']) {
			expect(screen.getByRole('tab', { name: new RegExp(label.replace(/[&]/g, '&'), 'i') })).toBeInTheDocument();
		}
		await waitFor(() => expect(screen.getByText('GATEWAY')).toBeInTheDocument());
		expect(screen.getByRole('tab', { name: /status/i })).toHaveAttribute('aria-selected', 'true');
	});

	it('shows the pending-approvals badge on the TOOLS & POLICY tab', async () => {
		renderAt('/control');
		await waitFor(() => {
			const toolsTab = screen.getByRole('tab', { name: /tools & policy/i });
			expect(toolsTab).toHaveTextContent('1');
		});
	});

	it('switches tabs on click and reaches the ABOUT band', async () => {
		renderAt('/control');
		await userEvent.click(screen.getByRole('tab', { name: /about/i }));
		expect(await screen.findByText(/Bearing Complexity Through Structure/i)).toBeInTheDocument();
	});

	it('opens the PROVIDER tab from the /settings redirect shim', async () => {
		renderAt('/settings');
		await waitFor(() =>
			expect(screen.getByRole('tab', { name: /provider/i })).toHaveAttribute('aria-selected', 'true')
		);
	});

	it('opens STATUS from the /system redirect shim', async () => {
		renderAt('/system');
		await waitFor(() =>
			expect(screen.getByRole('tab', { name: /status/i })).toHaveAttribute('aria-selected', 'true')
		);
	});
});
