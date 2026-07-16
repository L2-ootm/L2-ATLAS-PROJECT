import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ConsoleSessionProvider } from '../context/ConsoleSessionProvider';
import type { SurfaceEvent } from '../lib/surfaceContracts';
import Console from '../routes/Console';

const surface = vi.hoisted(() => ({
	value: {
		events: [] as SurfaceEvent[],
		submitPrompt: vi.fn(),
		releaseSession: vi.fn().mockResolvedValue(undefined)
	}
}));

const api = vi.hoisted(() => ({
	listProjects: vi.fn(),
	getRun: vi.fn()
}));

vi.mock('../context/AgentSurfaceContext', () => ({
	useAgentSurface: () => surface.value
}));

vi.mock('../lib/api', async importOriginal => ({
	...(await importOriginal<typeof import('../lib/api')>()),
	...api
}));

const PROJECT = {
	id: 'p-1',
	name: 'Atlas Gateway',
	root_path: 'C:\\proj\\gateway',
	created_at: '2026-07-01T00:00:00Z',
	updated_at: '2026-07-01T00:00:00Z'
};

function renderConsole() {
	return render(
		<MemoryRouter>
			<ConsoleSessionProvider>
				<Console />
			</ConsoleSessionProvider>
		</MemoryRouter>
	);
}

describe('Console session switcher', () => {
	beforeEach(() => {
		localStorage.clear();
		surface.value.events = [];
		surface.value.submitPrompt.mockReset();
		api.listProjects.mockReset().mockResolvedValue({ projects: [PROJECT] });
		api.getRun.mockReset();
	});

	it('lists recent folders and projects, and rebinding starts a fresh session', async () => {
		localStorage.setItem('atlas.console.recent-folders.v1', JSON.stringify(['C:\\ws\\recent']));
		renderConsole();
		await act(async () => {});

		fireEvent.click(screen.getByTitle('Switch session'));
		expect(screen.getByText('Recent folders')).toBeInTheDocument();
		expect(screen.getByTitle('C:\\ws\\recent')).toBeInTheDocument();
		// The switcher's project entry carries the root path as its title
		// (the bare name also renders in the ContextPane project list).
		expect(screen.getByTitle('C:\\proj\\gateway')).toBeInTheDocument();

		fireEvent.click(screen.getByTitle('C:\\ws\\recent'));
		await waitFor(() =>
			expect(
				screen.getByText('Console bound to folder: C:\\ws\\recent')
			).toBeInTheDocument()
		);
		// The popover closes after a selection.
		expect(screen.queryByText('Recent folders')).not.toBeInTheDocument();
	});

	it('binding to a project resets the transcript to a project boot receipt', async () => {
		renderConsole();
		await act(async () => {});

		fireEvent.click(screen.getByTitle('Switch session'));
		fireEvent.click(screen.getByTitle('C:\\proj\\gateway'));

		await waitFor(() =>
			expect(
				screen.getByText('Console bound to Atlas Gateway. Workspace root: C:\\proj\\gateway')
			).toBeInTheDocument()
		);
	});

	it('exposes a persistent change-folder action outside the popover', async () => {
		renderConsole();
		await act(async () => {});
		expect(screen.getByTitle('Change bound folder')).toBeInTheDocument();
	});
});
