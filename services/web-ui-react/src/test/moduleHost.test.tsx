import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
