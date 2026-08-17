import type { AuditEvent } from './api';

/**
 * The run's verification verdict, read off its own `verification_verdict` audit
 * event — the same durable record the CLI and the actor projection read, rather
 * than a second derivation that could disagree with them. Returns null for
 * `no_mutations` and for a run that has none, so the badge stays absent unless
 * there is something to answer for.
 */
export function verdictOf(events: AuditEvent[]): string | null {
	for (let i = events.length - 1; i >= 0; i--) {
		if (events[i].event_type !== 'verification_verdict') continue;
		const data = events[i].data;
		const state =
			typeof data === 'string'
				? (JSON.parse(data) as { state?: unknown }).state
				: (data as { state?: unknown } | null)?.state;
		// `no_mutations` and `exempt` are both "nothing to answer for" — a
		// read-only run and a documentation edit. Badging them would train the
		// eye to skip the verdicts that matter.
		return typeof state === 'string' && state !== 'no_mutations' && state !== 'exempt'
			? state
			: null;
	}
	return null;
}
