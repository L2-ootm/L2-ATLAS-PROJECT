import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ConsoleSessionProvider } from '../context/ConsoleSessionProvider';
import type { ConsoleSnapshot } from '../lib/consolePersistence';
import { createConsoleSession } from '../lib/consolePersistence';
import {
	setActiveSessionId,
	upsertSessionCatalog
} from '../lib/sessionCatalog';
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

	it('opens the shared session drawer with functions and an unbound group', async () => {
		renderConsole();
		await act(async () => {});

		fireEvent.click(screen.getByTitle('Sessions and functions'));
		expect(screen.getByText('Operational memory')).toBeInTheDocument();
		expect(screen.getByText('NEW SESSION')).toBeInTheDocument();
		expect(screen.getByText('NEW UNBOUND')).toBeInTheDocument();
		expect(screen.getAllByText('UNBOUND').length).toBeGreaterThan(0);
	});

	it('groups bound sessions under their folder and restores the selected snapshot', async () => {
		const baseWindow = {
			id: 'chat-1',
			kind: 'chat' as const,
			title: 'atlas.chat',
			agent: 'native' as const,
			x: 260,
			y: 54,
			w: 540,
			h: 430
		};
		const folderSnapshot: ConsoleSnapshot = {
			windows: [baseWindow],
			messagesByWindow: {
				'chat-1': [{
					id: 'boot-folder',
					role: 'system',
					label: 'ATLAS',
					body: 'Console bound to folder: C:\\ws\\recent',
					time: '12:00'
				}]
			},
			draftByWindow: { 'chat-1': '' },
			layout: 'tile',
			binding: { bindingMode: 'folder', folderPath: 'C:\\ws\\recent', projectId: '' }
		};
		const folderId = createConsoleSession(folderSnapshot);
		upsertSessionCatalog({
			id: folderId,
			surface: 'console',
			title: 'Review recent workspace',
			agent: 'native',
			binding: { kind: 'folder', label: 'recent', root: 'C:\\ws\\recent', projectId: null }
		});
		const unboundSnapshot: ConsoleSnapshot = {
			...folderSnapshot,
			messagesByWindow: { 'chat-1': [] },
			binding: { bindingMode: 'folder', folderPath: '', projectId: '' }
		};
		const unboundId = createConsoleSession(unboundSnapshot);
		upsertSessionCatalog({
			id: unboundId,
			surface: 'console',
			title: 'Unbound scratch',
			agent: 'native',
			binding: { kind: 'unbound', label: 'UNBOUND', root: null, projectId: null }
		});
		setActiveSessionId('console', unboundId);

		renderConsole();
		await act(async () => {});

		fireEvent.click(screen.getByTitle('Sessions and functions'));
		expect(screen.getByText('recent')).toBeInTheDocument();
		fireEvent.click(screen.getByTitle('Review recent workspace'));

		await waitFor(() =>
			expect(
				screen.getByText('Console bound to folder: C:\\ws\\recent')
			).toBeInTheDocument()
		);
	});

	it('exposes a persistent change-folder action outside the popover', async () => {
		renderConsole();
		await act(async () => {});
		expect(screen.getByTitle('Change bound folder')).toBeInTheDocument();
	});
});
