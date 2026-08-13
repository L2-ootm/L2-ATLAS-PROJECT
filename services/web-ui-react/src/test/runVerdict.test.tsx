import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { verdictOf } from '../routes/RunDetail';
import { VerificationBadge } from '../components/hud';
import type { AuditEvent } from '../lib/api';

function event(partial: Partial<AuditEvent>): AuditEvent {
	return {
		id: 'e1',
		cursor: 1,
		run_id: 'r1',
		event_type: 'llm_call',
		data: {},
		timestamp: '2026-08-13T00:00:00Z',
		session_id: null,
		task_id: null,
		tool_call_id: null,
		tool_name: null,
		...partial
	} as AuditEvent;
}

describe('verdictOf', () => {
	it('reads the state off the durable verification event', () => {
		expect(
			verdictOf([
				event({}),
				event({ event_type: 'verification_verdict', data: { state: 'unverified' } })
			])
		).toBe('unverified');
	});

	it('accepts the payload as a JSON string', () => {
		// The gateway hands `data` through as the raw audit column in some
		// projections; parsing only objects would silently drop every verdict.
		expect(
			verdictOf([
				event({ event_type: 'verification_verdict', data: JSON.stringify({ state: 'verified' }) })
			])
		).toBe('verified');
	});

	it('says nothing about a read-only run', () => {
		expect(
			verdictOf([event({ event_type: 'verification_verdict', data: { state: 'no_mutations' } })])
		).toBeNull();
	});

	it('is null when the run has no verdict at all', () => {
		expect(verdictOf([event({})])).toBeNull();
	});

	it('takes the last verdict when a run was re-classified', () => {
		expect(
			verdictOf([
				event({ event_type: 'verification_verdict', data: { state: 'unverified' } }),
				event({ event_type: 'verification_verdict', data: { state: 'verified' } })
			])
		).toBe('verified');
	});
});

describe('VerificationBadge', () => {
	it('renders nothing when there is nothing to answer for', () => {
		const { container } = render(<VerificationBadge verdict={null} />);
		expect(container).toBeEmptyDOMElement();
	});

	it('names a failed verification in plain words, not a status code', () => {
		render(<VerificationBadge verdict="contradicted" />);
		expect(screen.getByText('VERIFICATION FAILED')).toBeTruthy();
	});

	it('ignores an unknown state rather than rendering a blank chip', () => {
		const { container } = render(<VerificationBadge verdict="something-new" />);
		expect(container).toBeEmptyDOMElement();
	});
});
