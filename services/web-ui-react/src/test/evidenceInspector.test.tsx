import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { FileChangeReceipt } from '../components/evidence/FileChangeReceipt';
import * as api from '../lib/api';
import type { EvidenceFileChange } from '../lib/api';

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return {
		...actual,
		listFileChangeHunks: vi.fn(),
		getFileChangePatch: vi.fn()
	};
});

const file: EvidenceFileChange = {
	id: 'file-1',
	change_set_id: 'change-1',
	path: 'src/app.ts',
	old_path: null,
	operation: 'edit',
	availability: 'available',
	before_sha256: 'a'.repeat(64),
	after_sha256: 'b'.repeat(64),
	before_bytes: 100,
	after_bytes: 140,
	additions: 7,
	deletions: 2,
	binary: false,
	generated: false,
	mode_before: null,
	mode_after: null,
	redaction_count: 0
};

beforeEach(() => {
	vi.mocked(api.listFileChangeHunks).mockResolvedValue({
		hunks: Array.from({ length: 100 }, (_, hunk_index) => ({
			id: `hunk-${hunk_index}`,
			file_change_id: file.id,
			hunk_index,
			old_start: hunk_index * 10 + 1,
			old_lines: 5,
			new_start: hunk_index * 10 + 1,
			new_lines: 6,
			patch_start_byte: hunk_index * 100,
			patch_bytes: 100,
			redacted: false
		})),
		next_cursor: 'next-hunks',
		context: 3,
		ignore_whitespace: false
	});
	vi.mocked(api.getFileChangePatch).mockResolvedValue({
		availability: 'partial',
		media_type: 'text/x-diff',
		sha256: 'c'.repeat(64),
		range: { start: 0, end: 16_384, total_bytes: 8_000_000 },
		content: Array.from({ length: 1_000 }, (_, index) =>
			index % 3 === 0 ? `+added ${index}` : index % 3 === 1 ? `-removed ${index}` : ` context ${index}`
		).join('\n')
	});
});

describe('Evidence inspector receipts', () => {
	it('renders semantic receipt fields and opens the selected file', async () => {
		const inspect = vi.fn();
		render(
			<FileChangeReceipt
				file={file}
				actorId="actor-1"
				durationMs={42}
				onInspect={inspect}
			/>
		);
		expect(screen.getByText('EDIT')).toBeInTheDocument();
		expect(screen.getByText('src/app.ts')).toBeInTheDocument();
		expect(screen.getByText('+7')).toBeInTheDocument();
		expect(screen.getByText('−2')).toBeInTheDocument();
		expect(screen.getByText('actor-1')).toBeInTheDocument();
		expect(screen.getByText('42 ms')).toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: /inspect src\/app.ts/i }));
		expect(inspect).toHaveBeenCalledWith(file);
	});
});

describe('Evidence inspector 100k scale and accessibility', () => {
	it('pages Rust hunks, requests at most 16 KiB initially, and renders <=250 rows', async () => {
		render(
			<EvidenceInspector
				file={file}
				ownerToken="owner-1"
				provenance={{ actorId: 'actor-1', runId: 'run-1', toolCallId: 'call-1' }}
				onClose={() => {}}
			/>
		);

		expect(await screen.findByRole('dialog', { name: /evidence inspector/i })).toBeInTheDocument();
		await waitFor(() => expect(api.getFileChangePatch).toHaveBeenCalled());
		expect(vi.mocked(api.getFileChangePatch).mock.calls[0][2]).toMatchObject({
			offset: 0,
			limit: 16_384
		});
		expect(document.querySelectorAll('[data-evidence-row]').length).toBeLessThanOrEqual(250);
		expect(screen.getByText(/PARTIAL EVIDENCE/i)).toBeInTheDocument();
	});

	it('traps focus, resizes by keyboard, announces status, and restores focus on Escape', async () => {
		const before = document.createElement('button');
		before.textContent = 'Before';
		document.body.append(before);
		before.focus();
		const close = vi.fn();
		render(
			<EvidenceInspector
				file={file}
				ownerToken="owner-1"
				provenance={{ actorId: null, runId: 'run-1', toolCallId: null }}
				onClose={close}
			/>
		);
		const dialog = await screen.findByRole('dialog', { name: /evidence inspector/i });
		expect(dialog).toHaveFocus();
		expect(screen.getByRole('status')).toBeInTheDocument();

		const separator = screen.getByRole('separator', { name: /resize evidence inspector/i });
		const width = separator.getAttribute('aria-valuenow');
		separator.focus();
		await userEvent.keyboard('{ArrowLeft}');
		expect(separator.getAttribute('aria-valuenow')).not.toBe(width);

		await userEvent.keyboard('{Escape}');
		expect(close).toHaveBeenCalled();
		await waitFor(() => expect(before).toHaveFocus());
		before.remove();
	});
});
