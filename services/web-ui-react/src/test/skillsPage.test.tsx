import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SkillsPage from '../routes/SkillsPage';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		peekSkillCatalog: vi.fn(),
		listSkills: vi.fn(),
		setSkillTier: vi.fn()
	};
});

function skill(index: number): api.SkillInfo {
	return {
		id: `skills/atlas/skill-${index}`,
		name: `Skill ${index}`,
		description: `Description ${index}`,
		version: '1.0.0',
		author: 'ATLAS',
		license: 'MIT',
		category: index % 2 === 0 ? 'atlas' : 'operations',
		tags: [`tag-${index}`],
		provenance: { tier: 'original', source: 'bundled' },
		loading_tier: 'full',
		platforms: ['windows'],
		enabled: true,
		pinned: false,
		state: 'active',
		usage: { use_count: 0, view_count: 0, last_used_at: null },
		path: `C:/atlas/skills/skill-${index}/SKILL.md`
	};
}

const catalog: api.SkillCatalogResponse = {
	skills: Array.from({ length: 50 }, (_, index) => skill(index)),
	total: 50,
	catalog_generated_at: Date.now(),
	cache_status: 'fresh',
	cache_ttl_seconds: 30
};

function receipt(overrides: Partial<api.ControlReceipt> = {}): api.ControlReceipt {
	return {
		receipt_id: 'receipt-1',
		resource_type: 'skill',
		resource_id: 'skills/atlas/skill-0',
		resource_name: 'Skill 0',
		action: 'set_loading_tier',
		before: 'full',
		after: 'name-only',
		actor: 'cockpit.skills',
		reason: 'Operator changed Skill 0 loading tier from the Skills page',
		timestamp: '2026-07-30T12:00:00Z',
		status: 'committed',
		...overrides
	};
}

beforeEach(() => {
	vi.mocked(api.peekSkillCatalog).mockReturnValue(null);
	vi.mocked(api.listSkills).mockResolvedValue(catalog);
	vi.mocked(api.setSkillTier).mockResolvedValue(receipt());
});

describe('Skills control plane', () => {
	it('bounds the initial card DOM and reveals more on demand', async () => {
		render(<SkillsPage />);
		await screen.findByText('Skill 0');

		expect(screen.getAllByTitle('Loading tier: FULL')).toHaveLength(36);
		expect(screen.queryByText('Skill 49')).not.toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: /SHOW 14 MORE/i }));
		expect(screen.getAllByTitle('Loading tier: FULL')).toHaveLength(50);
		expect(screen.getByText('Skill 49')).toBeInTheDocument();
	});

	it('shows source/effective state and a durable receipt after mutation', async () => {
		render(<SkillsPage />);
		await screen.findByText('Skill 0');

		expect(screen.getAllByText('DISCOVERED · bundled')[0]).toBeInTheDocument();
		expect(screen.getAllByText('EFFECTIVE · enabled')[0]).toBeInTheDocument();
		await userEvent.click(screen.getAllByTitle('Loading tier: FULL')[0]);
		await userEvent.click(screen.getByRole('button', { name: 'NAME ONLY' }));

		await waitFor(() =>
			expect(api.setSkillTier).toHaveBeenCalledWith(
				'skills/atlas/skill-0',
				'name-only',
				'full',
				expect.stringContaining('Skills page')
			)
		);
		expect(await screen.findByText('CHANGE COMMITTED')).toBeInTheDocument();
		expect(screen.getByText(/receipt-1/)).toBeInTheDocument();
		expect(screen.getByText('ACTOR · cockpit.skills')).toBeInTheDocument();
	});

	it('rolls back through the same expected-state mutation path', async () => {
		vi.mocked(api.setSkillTier)
			.mockResolvedValueOnce(receipt())
			.mockResolvedValueOnce(receipt({
				receipt_id: 'receipt-2',
				before: 'name-only',
				after: 'full',
				reason: 'Rollback receipt receipt-1'
			}));
		render(<SkillsPage />);
		await screen.findByText('Skill 0');
		await userEvent.click(screen.getAllByTitle('Loading tier: FULL')[0]);
		await userEvent.click(screen.getByRole('button', { name: 'NAME ONLY' }));
		await userEvent.click(await screen.findByRole('button', { name: 'UNDO' }));

		await waitFor(() =>
			expect(api.setSkillTier).toHaveBeenLastCalledWith(
				'skills/atlas/skill-0',
				'full',
				'name-only',
				'Rollback receipt receipt-1'
			)
		);
		expect(await screen.findByText(/receipt-2/)).toBeInTheDocument();
	});

	it('never renders a success receipt when the mutation fails', async () => {
		vi.mocked(api.setSkillTier).mockRejectedValueOnce(new api.ApiError(409, 'stale tier'));
		render(<SkillsPage />);
		await screen.findByText('Skill 0');
		await userEvent.click(screen.getAllByTitle('Loading tier: FULL')[0]);
		await userEvent.click(screen.getByRole('button', { name: 'NAME ONLY' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('TIER UNCHANGED');
		expect(screen.queryByText('CHANGE COMMITTED')).not.toBeInTheDocument();
	});
});
