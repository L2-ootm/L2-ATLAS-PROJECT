import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RunEvidenceReceipts } from '../routes/RunDetail';
import * as api from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listRunChangeSets: vi.fn(),
		listChangeSetFiles: vi.fn()
	};
});

describe('Run Detail evidence receipts', () => {
	it('uses the shared semantic receipt and opens the selected file for inspection', async () => {
		vi.mocked(api.listRunChangeSets).mockResolvedValue({
			change_sets: [
				{
					id: 'change-1',
					provenance: {
						run_id: 'run-1',
						session_id: 'surface-1',
						actor_id: 'actor-1',
						parent_actor_id: null,
						team_run_id: null,
						turn_id: 'turn-1',
						tool_call_id: 'call-1'
					},
					coverage: 'complete',
					status: 'captured',
					redaction_count: 0,
					created_at: '2026-07-29T12:00:00Z',
					file_count: 1,
					additions: 7,
					deletions: 2
				}
			],
			next_cursor: null
		});
		vi.mocked(api.listChangeSetFiles).mockResolvedValue({
			files: [
				{
					id: 'file-1',
					change_set_id: 'change-1',
					path: 'src/app.ts',
					old_path: null,
					operation: 'edit',
					availability: 'available',
					before_sha256: null,
					after_sha256: 'a'.repeat(64),
					before_bytes: 10,
					after_bytes: 20,
					additions: 7,
					deletions: 2,
					binary: false,
					generated: false,
					mode_before: null,
					mode_after: null,
					redaction_count: 0
				}
			],
			next_cursor: null
		});
		const inspect = vi.fn();

		render(
			<RunEvidenceReceipts
				runId="run-1"
				ownerToken="owner-1"
				onInspect={inspect}
			/>
		);

		expect(await screen.findByText('src/app.ts')).toBeInTheDocument();
		expect(screen.getByText('+7')).toBeInTheDocument();
		expect(screen.getByText('−2')).toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: /inspect src\/app.ts/i }));
		await waitFor(() => expect(inspect).toHaveBeenCalledWith(expect.objectContaining({ id: 'file-1' })));
	});
});
