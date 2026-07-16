import { useEffect, useRef, useState } from 'react';
import type * as React from 'react';

/**
 * Paced streaming reveal with a luminous scan edge.
 *
 * Incoming text arrives in coarse poll batches (~200ms–2s), which reads as
 * jumpy sentence-at-a-time paints. This buffers the target text and reveals
 * it character-by-character at an adaptive rate: the backlog drains over
 * ~420ms so the reveal never falls behind the live stream, but never
 * teleports either. The reveal runs all the way to the end of the answer —
 * when the final reconcile lands the remaining buffer still plays out, then
 * `onSettled` fires so the parent can swap to full markdown rendering.
 *
 * The visual: settled text cools to the normal foreground; the trailing ~24
 * revealed characters glow (the "hot edge"), and a scan bar pulses at the
 * frontier. Honors prefers-reduced-motion (instant paint, no effects).
 */
export function StreamReveal({
	text,
	done = false,
	onSettled,
	style
}: {
	/** Target text — may grow while streaming. */
	text: string;
	/** True once the authoritative final text has landed (stream closed). */
	done?: boolean;
	/** Fires once, when `done` and the reveal has caught up with `text`. */
	onSettled?: () => void;
	style?: React.CSSProperties;
}) {
	// Text present at mount is history — paint it whole; only growth animates.
	const [shown, setShown] = useState(() => text.length);
	const shownRef = useRef(text.length);
	const textRef = useRef(text);
	textRef.current = text;
	const doneRef = useRef(done);
	doneRef.current = done;
	const settledRef = useRef(false);
	const onSettledRef = useRef(onSettled);
	onSettledRef.current = onSettled;
	const [reduced] = useState(
		() =>
			typeof window.matchMedia === 'function' &&
			window.matchMedia('(prefers-reduced-motion: reduce)').matches
	);

	useEffect(() => {
		if (reduced) {
			shownRef.current = textRef.current.length;
			setShown(shownRef.current);
			if (doneRef.current && !settledRef.current) {
				settledRef.current = true;
				onSettledRef.current?.();
			}
			return;
		}
		let raf = 0;
		let last = performance.now();
		const step = (now: number) => {
			const target = textRef.current.length;
			const current = shownRef.current;
			if (current < target) {
				const backlog = target - current;
				// chars/sec: drain the backlog in ~420ms, never slower than 55 cps.
				const rate = Math.max(55, backlog / 0.42);
				const advance = Math.max(1, Math.round(((now - last) / 1000) * rate));
				shownRef.current = Math.min(target, current + advance);
				setShown(shownRef.current);
			} else if (doneRef.current && !settledRef.current) {
				settledRef.current = true;
				onSettledRef.current?.();
			}
			last = now;
			raf = requestAnimationFrame(step);
		};
		raf = requestAnimationFrame(step);
		return () => cancelAnimationFrame(raf);
	}, [reduced]);

	// `done` can flip while the rAF loop is between frames with zero backlog —
	// make settling deterministic rather than waiting for the next text change.
	useEffect(() => {
		if (done && shown >= text.length && !settledRef.current) {
			settledRef.current = true;
			onSettledRef.current?.();
		}
	}, [done, shown, text.length]);

	const revealed = text.slice(0, shown);
	const HOT_EDGE = 24;
	const cut = reduced || (done && shown >= text.length) ? revealed.length : Math.max(0, revealed.length - HOT_EDGE);
	const settledText = revealed.slice(0, cut);
	const hotText = revealed.slice(cut);
	const streamingNow = !reduced && !(done && shown >= text.length);

	return (
		<div className="atlas-stream-reveal" style={style}>
			{settledText}
			{hotText && <span className="atlas-stream-hot">{hotText}</span>}
			{streamingNow && <span className="atlas-scan-bar" aria-hidden />}
		</div>
	);
}
