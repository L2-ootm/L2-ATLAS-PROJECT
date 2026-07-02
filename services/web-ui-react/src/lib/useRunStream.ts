import { useCallback, useEffect, useRef, useState } from 'react';
import { getRun, getRunEvents, openRunStream, type AuditEvent, type Run } from './api';

// useRunStream — the Run-detail data engine. Live runs consume the SSE stream;
// finished runs page their full audit history. Guarantees:
//   - lastCursor dedupe: a reconnect/replay never produces duplicate cursors
//   - single transport retry per disconnection, resuming from lastCursor
//   - 500-row DOM cap
//   - newCursors set (cleared after 300ms) so the view can blur-in + sonar-ping

const DOM_CAP = 500;
const HISTORY_PAGE = 1000;
const HISTORY_MAX_PAGES = 20; // up to 20k events on terminal-run backfill

function isActive(status: string): boolean {
	const s = status.toUpperCase();
	return s === 'RUNNING' || s === 'PENDING';
}

export interface RunStreamState {
	status: string;
	finishedAt: string | null;
	events: AuditEvent[];
	connected: boolean;
	streamError: string | null;
	newCursors: Set<number>;
	loading: boolean;
}

export function useRunStream(runId: string, initialRun: Run | null): RunStreamState {
	const [status, setStatus] = useState(initialRun?.status ?? 'PENDING');
	const [finishedAt, setFinishedAt] = useState<string | null>(initialRun?.finished_at ?? null);
	const [events, setEvents] = useState<AuditEvent[]>([]);
	const [connected, setConnected] = useState(false);
	const [streamError, setStreamError] = useState<string | null>(null);
	const [newCursors, setNewCursors] = useState<Set<number>>(new Set());
	const [loading, setLoading] = useState(true);

	// Mutable refs survive re-renders without re-triggering the effect.
	const lastCursor = useRef(0);
	const sourceRef = useRef<EventSource | null>(null);
	const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
	const retried = useRef(false);

	const appendEvent = useCallback((evt: AuditEvent) => {
		// Dedupe guard: a reconnect must continue, never replay.
		if (evt.cursor <= lastCursor.current) return;
		lastCursor.current = evt.cursor;
		setEvents((prev) => {
			const next = [...prev, evt];
			return next.length > DOM_CAP ? next.slice(next.length - DOM_CAP) : next;
		});
		setNewCursors((prev) => new Set(prev).add(evt.cursor));
		setTimeout(() => {
			setNewCursors((prev) => {
				const n = new Set(prev);
				n.delete(evt.cursor);
				return n;
			});
		}, 300);
	}, []);

	useEffect(() => {
		let alive = true;

		function closeSource() {
			if (retryTimer.current !== null) {
				clearTimeout(retryTimer.current);
				retryTimer.current = null;
			}
			sourceRef.current?.close();
			sourceRef.current = null;
			setConnected(false);
		}

		function connect(id: string) {
			const source = openRunStream(id, lastCursor.current);
			sourceRef.current = source;

			source.onopen = () => {
				if (!alive) return;
				setConnected(true);
				setStreamError(null);
				retried.current = false; // re-arm the single-retry budget on a clean open
			};

			source.addEventListener('audit', (e) => {
				try {
					appendEvent(JSON.parse((e as MessageEvent).data) as AuditEvent);
				} catch {
					/* ignore malformed event */
				}
			});

			source.addEventListener('end', (e) => {
				if (!alive) return;
				setConnected(false);
				source.close();
				sourceRef.current = null;
				try {
					const endData = JSON.parse((e as MessageEvent).data) as { status?: string };
					if (endData.status) {
						setStatus(endData.status);
						setFinishedAt((prev) => prev ?? new Date().toISOString());
					}
				} catch {
					// status unknown — re-fetch the authoritative run record
					getRun(id)
						.then((r) => {
							if (!alive) return;
							setStatus(r.run.status);
							setFinishedAt(r.run.finished_at);
						})
						.catch(() => {});
				}
			});

			// Gateway-level failure (named so it can't collide with transport errors).
			source.addEventListener('stream_error', (e) => {
				if (!alive) return;
				try {
					const err = JSON.parse((e as MessageEvent).data) as { error?: string };
					setStreamError(err.error ?? 'STREAM ERROR');
				} catch {
					setStreamError('STREAM ERROR — unknown gateway error');
				}
				setConnected(false);
				source.close();
				sourceRef.current = null;
			});

			// Transport error: retry once per disconnection, resuming from lastCursor.
			source.onerror = () => {
				if (!alive) return;
				setConnected(false);
				source.close();
				sourceRef.current = null;
				if (!retried.current) {
					retried.current = true;
					setStreamError('STREAM INTERRUPTED — reconnecting in 2s. If this persists, check gateway health.');
					retryTimer.current = setTimeout(() => alive && connect(id), 2000);
				} else {
					setStreamError('STREAM DISCONNECTED — refresh the page to reconnect.');
				}
			};
		}

		async function loadFullTrail(id: string) {
			let cursor: number | undefined;
			let all: AuditEvent[] = [];
			for (let i = 0; i < HISTORY_MAX_PAGES; i++) {
				const res = await getRunEvents(id, cursor, HISTORY_PAGE);
				all = [...all, ...res.events];
				if (!res.next_cursor || res.events.length === 0) break;
				cursor = res.next_cursor;
			}
			if (!alive) return;
			const capped = all.slice(-DOM_CAP);
			if (capped.length > 0) lastCursor.current = capped[capped.length - 1].cursor;
			setEvents(capped);
		}

		async function init() {
			if (!runId) {
				setStreamError('INVALID RUN ID — missing parameter');
				setLoading(false);
				return;
			}
			// Reset for a fresh run id.
			lastCursor.current = 0;
			retried.current = false;
			setEvents([]);
			try {
				const { run } = initialRun && initialRun.id === runId ? { run: initialRun } : await getRun(runId);
				if (!alive) return;
				setStatus(run.status);
				setFinishedAt(run.finished_at);
				if (isActive(run.status)) {
					connect(runId);
				} else {
					await loadFullTrail(runId);
				}
			} catch (e) {
				if (alive) setStreamError(e instanceof Error ? e.message : String(e));
			} finally {
				if (alive) setLoading(false);
			}
		}

		void init();

		return () => {
			alive = false;
			closeSource();
		};
		// initialRun is a stable snapshot for this run id; re-run only on id change.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [runId, appendEvent]);

	return { status, finishedAt, events, connected, streamError, newCursors, loading };
}
