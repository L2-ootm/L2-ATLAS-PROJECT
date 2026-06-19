import { useEffect, useState } from 'react';
import { checkHealth } from './api';

// Shared gateway heartbeat. A single module-level poller (not one per component)
// pings /health on a short interval; every subscriber re-renders when the status
// flips. `epoch` bumps on each (re)connect so data views can refetch automatically
// the moment the gateway comes up — no manual refresh. Paused while the tab is
// hidden to stay cheap.

const INTERVAL_MS = 5000;

let online: boolean | null = null;
let epoch = 0;
let timer: ReturnType<typeof setInterval> | null = null;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

async function tick(): Promise<void> {
	if (typeof document !== 'undefined' && document.hidden) return;
	let next: boolean;
	try {
		await checkHealth();
		next = true;
	} catch {
		next = false;
	}
	if (next === online) return;
	if (next && online !== true) epoch += 1; // offline/unknown → online = a (re)connect
	online = next;
	emit();
}

function ensureHeartbeat(): void {
	if (timer) return;
	void tick();
	timer = setInterval(() => void tick(), INTERVAL_MS);
}

/**
 * Subscribe to the shared gateway heartbeat.
 * - `online`: live gateway reachability (null until the first probe resolves).
 * - `epoch`: increments on every (re)connect — add it to a data-fetch effect's
 *   deps so the view refetches automatically when the gateway returns.
 */
export function useGatewayHealth(): { online: boolean | null; epoch: number } {
	const [, rerender] = useState(0);
	useEffect(() => {
		const cb = () => rerender((n) => n + 1);
		subscribers.add(cb);
		ensureHeartbeat();
		return () => {
			subscribers.delete(cb);
		};
	}, []);
	return { online, epoch };
}
