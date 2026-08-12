import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ModuleHost from '../routes/ModuleHost';
import * as api from '../lib/api';

vi.mock('../components/ChatMarkdown', () => ({
	ChatMarkdown: ({ text }: { text: string }) => <div>{text}</div>
}));

const demoModule: api.Module = {
	id: 'demo-mod',
	name: 'Demo Mod',
	description: 'demo',
	status: 'active',
	activated_at: null,
	version: '1.0.0',
	missing: false,
	manifest: {
		id: 'demo-mod',
		name: 'Demo Mod',
		version: '1.0.0',
		description: 'demo',
		capabilities: {
			commands: [],
			pages: [
				{
					id: 'main',
					title: 'Demo',
					icon: '',
					blocks: [
						{ kind: 'heading', text: 'Demo Page' },
						{ kind: 'markdown', text: 'Rendered from the manifest.' },
						{ kind: 'metrics', items: [{ label: 'Version', value: 'v1' }] },
						{ kind: 'actions', items: [{ label: 'Run demo', command: '/demo' }] },
						{ kind: 'hologram', text: 'future kind' }
					]
				}
			]
		}
	}
};

function renderHost(moduleId: string) {
	return render(
		<MemoryRouter initialEntries={[`/m/${moduleId}`]}>
			<Routes>
				<Route path="/m/:moduleId" element={<ModuleHost />} />
			</Routes>
		</MemoryRouter>
	);
}

beforeEach(() => {
	vi.restoreAllMocks();
});

describe('ModuleHost', () => {
	it('renders manifest blocks, degrading unknown kinds to placeholders', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [demoModule], count: 1 });
		renderHost('demo-mod');
		await waitFor(() => expect(screen.getByText('Demo Page')).toBeInTheDocument());
		expect(screen.getByText('Rendered from the manifest.')).toBeInTheDocument();
		expect(screen.getByText('Version')).toBeInTheDocument();
		expect(screen.getByText('Run demo')).toBeInTheDocument();
		expect(screen.getByText(/unsupported block kind: hologram/)).toBeInTheDocument();
	});

	it('explains unknown and deactivated modules instead of erroring', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({
			modules: [{ ...demoModule, status: 'inactive' }],
			count: 1
		});
		renderHost('demo-mod');
		await waitFor(() =>
			expect(screen.getByText(/deactivated/)).toBeInTheDocument()
		);

		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [], count: 0 });
		renderHost('ghost-mod');
		await waitFor(() =>
			expect(screen.getByText(/No module registered/)).toBeInTheDocument()
		);
	});
});

// --- capability v2 blocks ---------------------------------------------------

const crmModule: api.Module = {
	...demoModule,
	id: 'crm-mod',
	manifest: {
		id: 'crm-mod',
		name: 'CRM Mod',
		version: '2.0.0',
		description: 'crm',
		capabilities: {
			commands: [],
			collections: [
				{
					id: 'prospects',
					title: 'Prospects',
					label_field: 'name',
					fields: [{ name: 'name', type: 'text' }]
				}
			],
			pages: [
				{
					id: 'main',
					title: 'CRM',
					icon: '',
					blocks: [
						{
							kind: 'stat_row',
							items: [
								{ label: 'All', collection: 'prospects' },
								{ label: 'Ready', collection: 'prospects', where: { stage: 'ready' } }
							]
						},
						{
							kind: 'tabs',
							tabs: [
								{ id: 'one', label: 'First', blocks: [{ kind: 'markdown', text: 'first tab body' }] },
								{
									id: 'two',
									label: 'Second',
									blocks: [
										{ kind: 'records', collection: 'prospects', columns: ['name', 'stage'] }
									]
								}
							]
						}
					]
				}
			]
		}
	}
};

const records: api.ModuleRecord[] = [
	{
		id: 'acme',
		data: { name: 'Acme', stage: 'ready' },
		status: 'active',
		created_at: '2026-08-12T00:00:00Z',
		updated_at: '2026-08-12T00:00:00Z'
	},
	{
		id: 'globex',
		data: { name: 'Globex', stage: 'research' },
		status: 'active',
		created_at: '2026-08-12T00:00:00Z',
		updated_at: '2026-08-12T00:00:00Z'
	}
];

describe('ModuleHost capability v2 blocks', () => {
	it('shows only the active tab and switches on click', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [crmModule], count: 1 });
		vi.spyOn(api, 'listModuleRecords').mockResolvedValue(records);
		renderHost('crm-mod');

		await waitFor(() => expect(screen.getByText('first tab body')).toBeInTheDocument());
		expect(screen.queryByText('Globex')).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole('tab', { name: 'Second' }));
		await waitFor(() => expect(screen.getByText('Globex')).toBeInTheDocument());
		expect(screen.queryByText('first tab body')).not.toBeInTheDocument();
	});

	it('counts records per stat, honoring the where filter', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [crmModule], count: 1 });
		vi.spyOn(api, 'listModuleRecords').mockResolvedValue(records);
		renderHost('crm-mod');

		await waitFor(() => expect(screen.getByText('All')).toBeInTheDocument());
		// 2 records total, 1 matching {stage: ready}.
		await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument());
		expect(screen.getByText('1')).toBeInTheDocument();
	});

	it('filters the records table', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [crmModule], count: 1 });
		vi.spyOn(api, 'listModuleRecords').mockResolvedValue(records);
		renderHost('crm-mod');
		fireEvent.click(await screen.findByRole('tab', { name: 'Second' }));
		await waitFor(() => expect(screen.getByText('Acme')).toBeInTheDocument());

		fireEvent.change(screen.getByLabelText('Filter prospects'), { target: { value: 'globe' } });
		await waitFor(() => expect(screen.queryByText('Acme')).not.toBeInTheDocument());
		expect(screen.getByText('Globex')).toBeInTheDocument();
	});

	it('says an empty collection is empty rather than rendering nothing', async () => {
		vi.spyOn(api, 'listModules').mockResolvedValue({ modules: [crmModule], count: 1 });
		vi.spyOn(api, 'listModuleRecords').mockResolvedValue([]);
		renderHost('crm-mod');
		fireEvent.click(await screen.findByRole('tab', { name: 'Second' }));
		await waitFor(() => expect(screen.getByText(/No records yet/)).toBeInTheDocument());
	});
});
