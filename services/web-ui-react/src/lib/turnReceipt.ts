import type { ConsoleMessage } from '../context/ConsoleSessionContext';

/** Stable signature of a turn's run-boundary receipt (run started · runtime ·
 * privacy notice). The information is session-level, so matching consecutive
 * receipts can be collapsed without hiding turn content. */
export function turnReceiptSignature(message: ConsoleMessage): string | null {
	const statuses = (message.events ?? []).filter((event) => event.type === 'status');
	if (statuses.length === 0) return null;
	return statuses.map((event) => event.text ?? '').join(' · ');
}
