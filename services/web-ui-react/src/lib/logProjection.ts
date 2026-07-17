import type { AuditEvent, ConsoleChatEvent } from './api';

export type AuditLogItem<T extends AuditEvent = AuditEvent> = {
	id: string;
	event: T;
	members: T[];
	count: number;
	charCount: number;
	text: string;
	firstCursor: number;
	lastCursor: number;
};

export type ConsoleLogItem = {
	id: string;
	event: ConsoleChatEvent;
	members: ConsoleChatEvent[];
	count: number;
	charCount: number;
	text: string;
};

function auditDelta(event: AuditEvent): string {
	if (event.event_type !== 'llm_delta' || !event.data || typeof event.data !== 'object') return '';
	const delta = (event.data as Record<string, unknown>).delta;
	return typeof delta === 'string' ? delta : '';
}

function makeAuditItem<T extends AuditEvent>(members: T[]): AuditLogItem<T> {
	const ordered = [...members].sort((a, b) => a.cursor - b.cursor);
	const text = ordered.map(auditDelta).join('');
	return {
		id: members.length === 1
			? `event-${members[0].cursor}`
			: `delta-${ordered[0].cursor}-${ordered[ordered.length - 1].cursor}`,
		event: members[0],
		members,
		count: members.length,
		charCount: text.length,
		text,
		firstCursor: ordered[0].cursor,
		lastCursor: ordered[ordered.length - 1].cursor
	};
}

/** Collapse only adjacent delta rows from the same run. Tool calls, results,
 * status transitions, and deltas from another run always terminate a burst. */
export function projectAuditEvents<T extends AuditEvent>(events: T[]): AuditLogItem<T>[] {
	const projected: AuditLogItem<T>[] = [];
	let deltaBurst: T[] = [];

	const flush = () => {
		if (deltaBurst.length > 0) projected.push(makeAuditItem(deltaBurst));
		deltaBurst = [];
	};

	for (const event of events) {
		if (event.event_type === 'llm_delta') {
			const sameRun = deltaBurst.length === 0 || deltaBurst[0].run_id === event.run_id;
			if (!sameRun) flush();
			deltaBurst.push(event);
			continue;
		}
		flush();
		projected.push(makeAuditItem([event]));
	}
	flush();
	return projected;
}

function makeConsoleItem(members: ConsoleChatEvent[], index: number): ConsoleLogItem {
	const text = members.map((event) => event.text ?? '').join('');
	return {
		id: members.length === 1 ? `event-${index}` : `delta-${index}-${members.length}`,
		event: members[0],
		members,
		count: members.length,
		charCount: text.length,
		text
	};
}

export function projectConsoleEvents(events: ConsoleChatEvent[]): ConsoleLogItem[] {
	const projected: ConsoleLogItem[] = [];
	let deltaBurst: ConsoleChatEvent[] = [];
	let index = 0;
	const flush = () => {
		if (deltaBurst.length > 0) projected.push(makeConsoleItem(deltaBurst, index++));
		deltaBurst = [];
	};
	for (const event of events) {
		if (event.type === 'text_delta') {
			deltaBurst.push(event);
			continue;
		}
		flush();
		projected.push(makeConsoleItem([event], index++));
	}
	flush();
	return projected;
}
