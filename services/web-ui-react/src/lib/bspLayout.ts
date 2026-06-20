// Hyprland-style binary-space-partition (dwindle) layout — pure geometry.
//
// Given an ordered list of window ids and a container rect, recursively split
// the space: the first window takes half, the remaining windows recurse into the
// other half. Split direction is aspect-driven (wider rect → side-by-side; taller
// rect → stacked), which produces the dwindle spiral operators expect. Adding a
// window lengthens the list (it splits the deepest region); removing one shortens
// it (the layout reflows to fill). No manual placement, no overlap, no gaps.
//
// Pure and framework-agnostic so the trickiest logic stays out of React.

export type Rect = { x: number; y: number; w: number; h: number };

/** Minimum edge a window may shrink to before splitting stops subdividing. */
const MIN_EDGE = 80;

function partition(ids: string[], rect: Rect, gap: number, out: Map<string, Rect>): void {
	if (ids.length === 0) return;
	if (ids.length === 1) {
		out.set(ids[0], rect);
		return;
	}
	const [first, ...rest] = ids;
	// Aspect-driven: split along the longer axis (dwindle). Tie → horizontal.
	const horizontal = rect.w >= rect.h;
	if (horizontal) {
		const half = Math.max(MIN_EDGE, (rect.w - gap) / 2);
		const restW = rect.w - half - gap;
		out.set(first, { x: rect.x, y: rect.y, w: half, h: rect.h });
		if (restW <= 0) {
			// No room to split further — stack the remainder onto the first cell.
			for (const id of rest) out.set(id, { x: rect.x, y: rect.y, w: half, h: rect.h });
			return;
		}
		partition(rest, { x: rect.x + half + gap, y: rect.y, w: restW, h: rect.h }, gap, out);
	} else {
		const half = Math.max(MIN_EDGE, (rect.h - gap) / 2);
		const restH = rect.h - half - gap;
		out.set(first, { x: rect.x, y: rect.y, w: rect.w, h: half });
		if (restH <= 0) {
			for (const id of rest) out.set(id, { x: rect.x, y: rect.y, w: rect.w, h: half });
			return;
		}
		partition(rest, { x: rect.x, y: rect.y + half + gap, w: rect.w, h: restH }, gap, out);
	}
}

/**
 * Compute non-overlapping rects for `ids` filling `container`, dwindle-style.
 * `focusId`, if given and present, is placed first so it takes the largest cell.
 */
export function computeDwindle(
	ids: string[],
	container: Rect,
	gap = 8,
	focusId?: string
): Map<string, Rect> {
	const out = new Map<string, Rect>();
	const ordered =
		focusId && ids.includes(focusId) ? [focusId, ...ids.filter((id) => id !== focusId)] : ids;
	partition(ordered, container, gap, out);
	return out;
}
