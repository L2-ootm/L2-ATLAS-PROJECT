import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Ledger from '../routes/Ledger';
import * as api from '../lib/api';
import type { EvidenceAuditEvent } from '../lib/api';

const surface = vi.hoisted(() => ({
	session: null as null | { id: string; owner_token: string }
}));

vi.mock('../context/AgentSurfaceContext', () => ({
	useAgentSurface: () => ({ session: surface.session })
}));

vi.mock('../lib/useGatewayHealth', () => ({
	useGatewayHealth: () => ({ online: true, epoch: 1 })
}));

vi.mock('../lib/api', async () => {
	const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
	return { ...actual, listAuditEvidence: vi.fn() };
});

function event(id: string, sessionId: string): EvidenceAuditEvent {
	return {
		id,
		cursor: `cursor-${id}`,
		run_id: `run-${id}`,
		event_type: `event_${id}`,
		data: {},
		timestamp: '2026-08-05T12:00:00Z',
		session_id: sessionId,
		task_id: null,
		tool_call_id: null,
		tool_name: null,
		duration_ms: null,
		policy_result: null
	};
}

function renderLedger() {
	return render(
		<MemoryRouter>
			<Ledger />
		</MemoryRouter>
	);
}

describe('Ledger owner-scoped states', () => {
	beforeEach(() => {
		surface.session = null;
		vi.mocked(api.listAuditEvidence).mockReset().mockResolvedValue({
			events: [],
			next_cursor: null
		});
	});

	it('shows a truthful missing-session state without creating or reading a session', async () => {
		renderLedger();

		expect(screen.getByRole('status')).toHaveTextContent('No owning session yet');
		expect(screen.getByRole('status')).toHaveTextContent('Ledger will not create one automatically');
		await act(async () => {});
		expect(api.listAuditEvidence).not.toHaveBeenCalled();
		expect(screen.queryByText('Gateway unavailable')).not.toBeInTheDocument();
	});

	it('distinguishes a restored session that has no owner token', async () => {
		surface.session = { id: 'surface-no-token', owner_token: '' };
		renderLedger();

		expect(screen.getByRole('status')).toHaveTextContent('Session ownership unavailable');
		expect(screen.getByRole('status')).toHaveTextContent('has no owner token');
		await act(async () => {});
		expect(api.listAuditEvidence).not.toHaveBeenCalled();
	});

	it('keeps an owned API failure in the offline request state', async () => {
		surface.session = { id: 'surface-owned', owner_token: 'owner-token' };
		vi.mocked(api.listAuditEvidence).mockRejectedValueOnce(new Error('offline'));
		renderLedger();

		expect(await screen.findByRole('alert')).toHaveTextContent('Gateway unavailable');
		expect(screen.getByRole('alert')).toHaveTextContent(/owned audit request failed/i);
		expect(api.listAuditEvidence).toHaveBeenCalledWith(
			'surface-owned',
			'owner-token',
			expect.objectContaining({ limit: 200 })
		);
	});

	it('renders an owned empty ledger as evidence-empty, not offline', async () => {
		surface.session = { id: 'surface-owned', owner_token: 'owner-token' };
		renderLedger();

		expect(await screen.findByText('No audit events yet')).toBeInTheDocument();
		expect(screen.getByText('This owned session has not recorded any audit evidence yet.')).toBeInTheDocument();
		expect(screen.queryByText('Gateway unavailable')).not.toBeInTheDocument();
	});

	it('fetches after ownership appears and ignores a stale response from the previous owner', async () => {
		let resolveFirst!: (page: { events: EvidenceAuditEvent[]; next_cursor: null }) => void;
		vi.mocked(api.listAuditEvidence)
			.mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
			.mockResolvedValueOnce({ events: [event('new-owner', 'surface-b')], next_cursor: null });
		const view = renderLedger();

		expect(api.listAuditEvidence).not.toHaveBeenCalled();
		surface.session = { id: 'surface-a', owner_token: 'token-a' };
		view.rerender(<MemoryRouter><Ledger /></MemoryRouter>);
		await waitFor(() => expect(api.listAuditEvidence).toHaveBeenCalledTimes(1));

		surface.session = { id: 'surface-b', owner_token: 'token-b' };
		view.rerender(<MemoryRouter><Ledger /></MemoryRouter>);
		expect(await screen.findByText('event_new-owner')).toBeInTheDocument();

		await act(async () => {
			resolveFirst({ events: [event('stale-owner', 'surface-a')], next_cursor: null });
		});
		expect(screen.queryByText('event_stale-owner')).not.toBeInTheDocument();
		expect(screen.getByText('event_new-owner')).toBeInTheDocument();
	});
});
