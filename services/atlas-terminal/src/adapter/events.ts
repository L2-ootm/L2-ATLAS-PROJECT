/**
 * Donor event bus — the in-process channel behind GET /event.
 *
 * The donor TUI consumes one global SSE stream of `{ type, properties }`
 * events (Event.message.part.updated, Event.session.status, ...). The chat
 * orchestrator emits onto this bus; every open /event response subscribes.
 */

export interface DonorEvent {
	type: string;
	properties: Record<string, unknown>;
}

/**
 * The donor SDK v2 consumes `GlobalEvent { directory, payload }` — the TUI's
 * useEvent() reads `event.payload.type` and filters on `event.directory`, so
 * bare DonorEvents crash it. Wrap at every boundary that feeds the SDK.
 */
export interface GlobalEventEnvelope {
	directory: string;
	payload: DonorEvent;
}

export function toGlobalEvent(event: DonorEvent, directory = process.cwd()): GlobalEventEnvelope {
	return { directory, payload: event };
}

export type DonorEventListener = (event: DonorEvent) => void;

export class EventBus {
	private listeners = new Set<DonorEventListener>();
	/** Ring of recent events so a stream opened just after boot still sees state. */
	private recent: DonorEvent[] = [];
	private static readonly RECENT_CAP = 256;

	subscribe(listener: DonorEventListener): () => void {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	}

	emit(type: string, properties: Record<string, unknown>): void {
		const event: DonorEvent = { type, properties };
		this.recent.push(event);
		if (this.recent.length > EventBus.RECENT_CAP) this.recent.shift();
		for (const listener of [...this.listeners]) listener(event);
	}

	replayRecent(listener: DonorEventListener): void {
		for (const event of this.recent) listener(event);
	}
}
