// Scroll edge-limit pulse — when a scrollable container is at its vertical limit
// and the operator wheels further, emit a small light pulse at that edge in the
// new-mission hover tones (emerald → celestial). Purely cosmetic, fail-soft.
//
// JS rather than CSS because scroll containers clip overflow, so an edge glow
// painted inside them would be cut off; we draw a fixed-position overlay sized
// to the container's rect instead. One capture-phase wheel listener, throttled.

const COOLDOWN_MS = 340;
const EDGE_EPSILON = 1.5;
let lastPulseAt = 0;

function scrollableAncestor(start: Element | null): HTMLElement | null {
	let node: Element | null = start;
	while (node && node !== document.body && node !== document.documentElement) {
		if (node instanceof HTMLElement) {
			const oy = getComputedStyle(node).overflowY;
			if ((oy === 'auto' || oy === 'scroll') && node.scrollHeight > node.clientHeight + EDGE_EPSILON) {
				return node;
			}
		}
		node = node.parentElement;
	}
	return null;
}

function isFixedAncestor(start: Element | null): boolean {
	let node: Element | null = start;
	while (node && node !== document.body && node !== document.documentElement) {
		if (node instanceof HTMLElement) {
			if (getComputedStyle(node).position === 'fixed') return true;
		}
		node = node.parentElement;
	}
	return false;
}

function spawnPulse(rect: DOMRect, edge: 'top' | 'bottom', fixedMode: boolean): void {
	const bar = document.createElement('div');
	bar.className = 'atlas-scroll-pulse';
	if (fixedMode) {
		bar.style.position = 'fixed';
		bar.style.left = `${Math.round(rect.left)}px`;
		bar.style.top = edge === 'top' ? `${Math.round(rect.top)}px` : `${Math.round(rect.bottom - 2)}px`;
	} else {
		bar.style.position = 'absolute';
		bar.style.left = `${Math.round(rect.left + window.scrollX)}px`;
		bar.style.top = edge === 'top' ? `${Math.round(rect.top + window.scrollY)}px` : `${Math.round(rect.bottom + window.scrollY - 2)}px`;
	}
	bar.style.width = `${Math.round(rect.width)}px`;
	document.body.appendChild(bar);
	window.setTimeout(() => bar.remove(), 600);
}

function onWheel(e: WheelEvent): void {
	if (e.deltaY === 0) return;
	const el = scrollableAncestor(e.target as Element);
	if (!el) return;
	const now = performance.now();
	if (now - lastPulseAt < COOLDOWN_MS) return;

	const atTop = el.scrollTop <= EDGE_EPSILON;
	const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - EDGE_EPSILON;
	const fixedMode = isFixedAncestor(el);
	
	if (e.deltaY > 0 && atBottom) {
		lastPulseAt = now;
		spawnPulse(el.getBoundingClientRect(), 'bottom', fixedMode);
	} else if (e.deltaY < 0 && atTop) {
		lastPulseAt = now;
		spawnPulse(el.getBoundingClientRect(), 'top', fixedMode);
	}
}

/** Install the global scroll edge-pulse once. Idempotent. */
export function initScrollEdgePulse(): void {
	const w = window as unknown as { __atlasEdgePulse?: boolean };
	if (w.__atlasEdgePulse) return;
	if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
	w.__atlasEdgePulse = true;
	window.addEventListener('wheel', onWheel, { capture: true, passive: true });
}
