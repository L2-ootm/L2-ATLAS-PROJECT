import { useEffect, useRef, useState } from 'react';
import type * as React from 'react';
import { ChatMarkdown } from '../ChatMarkdown';
import {
	streamIntensityValue,
	streamSpeedMultiplier,
	useVisualSettings
} from '../../lib/visualSettings';

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
 * The visible prefix is parsed as Markdown on every paced paint, so headings,
 * lists, emphasis, links, and code become formatted while the answer is still
 * arriving. A restrained glow on the newest Markdown block plus a short scan
 * line marks the live frontier. Honors prefers-reduced-motion.
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
	const visuals = useVisualSettings();
	// Text present at mount is history — paint it whole; only growth animates.
	const [shown, setShown] = useState(() => text.length);
	const [chunkEpoch, setChunkEpoch] = useState(0);
	const shownRef = useRef(text.length);
	const carryRef = useRef(0);
	const lastPaintRef = useRef(0);
	const priorTargetRef = useRef(text.length);
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
	const animate = !reduced && visuals.streamingEffect;
	const speed = streamSpeedMultiplier(visuals.streamSpeed);
	const intensity = streamIntensityValue(visuals.streamIntensity);

	useEffect(() => {
		if (text.length > priorTargetRef.current && !done) setChunkEpoch((value) => value + 1);
		priorTargetRef.current = text.length;
	}, [done, text.length]);

	useEffect(() => {
		if (!animate) {
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
				// Drain coarse transport chunks smoothly instead of painting a
				// sentence at once. Fractional carry avoids one-character-per-rAF
				// jitter; the cap prevents large poll batches from teleporting.
				const rate = Math.min(340, Math.max(64, backlog / 0.52)) * speed;
				carryRef.current += ((now - last) / 1000) * rate;
				const advance = Math.floor(carryRef.current);
				if (advance > 0 && now - lastPaintRef.current >= 28) {
					carryRef.current -= advance;
					shownRef.current = Math.min(target, current + advance);
					lastPaintRef.current = now;
					setShown(shownRef.current);
				}
			} else if (doneRef.current && !settledRef.current) {
				settledRef.current = true;
				onSettledRef.current?.();
			}
			last = now;
			raf = requestAnimationFrame(step);
		};
		raf = requestAnimationFrame(step);
		return () => cancelAnimationFrame(raf);
	}, [animate, speed]);

	// `done` can flip while the rAF loop is between frames with zero backlog —
	// make settling deterministic rather than waiting for the next text change.
	useEffect(() => {
		if (done && shown >= text.length && !settledRef.current) {
			settledRef.current = true;
			onSettledRef.current?.();
		}
	}, [done, shown, text.length]);

	const revealed = text.slice(0, shown);
	const streamingNow = animate && !(done && shown >= text.length);
	const visualStyle = {
		...style,
		'--atlas-stream-glow-alpha': Math.min(0.5, 0.18 * intensity),
		'--atlas-stream-scan-alpha': Math.min(1, 0.72 * intensity),
		'--atlas-stream-scan-duration': `${Math.max(360, 760 / speed)}ms`
	} as React.CSSProperties;

	return (
		<div
			className={`atlas-stream-reveal${streamingNow ? ' is-streaming' : ''}`}
			style={visualStyle}
			aria-live="polite"
		>
			{revealed ? <ChatMarkdown text={revealed} /> : null}
			{streamingNow && <span className="atlas-stream-frontier" aria-hidden />}
			{streamingNow && (
				<span key={chunkEpoch} className="atlas-stream-chunk-scan" aria-hidden />
			)}
		</div>
	);
}
