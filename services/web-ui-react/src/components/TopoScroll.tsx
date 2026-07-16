import { useCallback, useEffect, useRef, useState } from 'react';
import type * as React from 'react';

type ScrollTone = 'info' | 'good' | 'ai' | 'atlas';

type Props = {
	children: React.ReactNode;
	/** Outer wrapper style — use this for layout placement (flex, grid area, height). */
	style?: React.CSSProperties;
	/** Inner viewport style — use this for padding / inner flex / gap. */
	viewportStyle?: React.CSSProperties;
	className?: string;
	tone?: ScrollTone;
	/** Optional handle to the scrolling viewport element — lets chat surfaces
	 * implement stick-to-bottom follow without reaching into the DOM. */
	viewportRef?: React.MutableRefObject<HTMLDivElement | null>;
	/** Fires on viewport scroll (after the internal thumb bookkeeping). */
	onViewportScroll?: (el: HTMLDivElement) => void;
};

/**
 * Overlay scrollbar that fully replaces the native rail: the native bar is
 * hidden, and a thin gradient thumb (topographic tint + glow) is drawn on top.
 * It auto-hides when idle, brightens on hover, and is draggable. Vertical only —
 * the console scroll surfaces never scroll horizontally.
 */
export function TopoScroll({ children, style, viewportStyle, className, tone = 'info', viewportRef: externalViewportRef, onViewportScroll }: Props) {
	const viewportRef = useRef<HTMLDivElement>(null);
	const [thumb, setThumb] = useState({ height: 0, top: 0, visible: false });
	const [active, setActive] = useState(false);
	const hideTimer = useRef<number | null>(null);
	const dragRef = useRef<{ startY: number; startScroll: number } | null>(null);

	const recompute = useCallback(() => {
		const el = viewportRef.current;
		if (!el) return;
		const { scrollTop, scrollHeight, clientHeight } = el;
		const scrollable = scrollHeight - clientHeight;
		if (scrollable <= 1) {
			setThumb((t) => (t.visible ? { ...t, visible: false } : t));
			return;
		}
		const trackH = clientHeight;
		const height = Math.max(30, (clientHeight / scrollHeight) * trackH);
		const top = (scrollTop / scrollable) * (trackH - height);
		setThumb({ height, top, visible: true });
	}, []);

	const flashActive = useCallback(() => {
		setActive(true);
		if (hideTimer.current) window.clearTimeout(hideTimer.current);
		hideTimer.current = window.setTimeout(() => setActive(false), 900);
	}, []);

	useEffect(() => {
		recompute();
		const el = viewportRef.current;
		if (!el) return;
		const ro = new ResizeObserver(() => recompute());
		ro.observe(el);
		for (const child of Array.from(el.children)) ro.observe(child);
		return () => {
			ro.disconnect();
			if (hideTimer.current) window.clearTimeout(hideTimer.current);
		};
	}, [recompute, children]);

	function onScroll() {
		recompute();
		flashActive();
		if (viewportRef.current && onViewportScroll) onViewportScroll(viewportRef.current);
	}

	function onThumbDown(e: React.PointerEvent<HTMLDivElement>) {
		e.preventDefault();
		e.stopPropagation();
		const el = viewportRef.current;
		if (!el) return;
		try {
			(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
		} catch {
			// pointer capture is best-effort
		}
		dragRef.current = { startY: e.clientY, startScroll: el.scrollTop };
		setActive(true);
	}

	function onThumbMove(e: React.PointerEvent<HTMLDivElement>) {
		const d = dragRef.current;
		const el = viewportRef.current;
		if (!d || !el) return;
		const { scrollHeight, clientHeight } = el;
		const scrollable = scrollHeight - clientHeight;
		const travel = clientHeight - thumb.height;
		if (travel <= 0) return;
		el.scrollTop = d.startScroll + ((e.clientY - d.startY) * scrollable) / travel;
	}

	function onThumbUp(e: React.PointerEvent<HTMLDivElement>) {
		dragRef.current = null;
		try {
			(e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId);
		} catch {
			// already released
		}
		flashActive();
	}

	return (
		<div className={`atlas-topo-scroll${className ? ` ${className}` : ''}`} style={style} data-tone={tone}>
			<div
				ref={(el) => {
					viewportRef.current = el;
					if (externalViewportRef) externalViewportRef.current = el;
				}}
				className="atlas-topo-scroll-viewport"
				style={viewportStyle}
				onScroll={onScroll}
			>
				{children}
			</div>
			{thumb.visible && (
				<div className="atlas-topo-scroll-track" data-active={active ? 'true' : 'false'}>
					<div
						className="atlas-topo-scroll-thumb"
						style={{ height: thumb.height, transform: `translateY(${thumb.top}px)` }}
						onPointerDown={onThumbDown}
						onPointerMove={onThumbMove}
						onPointerUp={onThumbUp}
						onPointerCancel={onThumbUp}
					/>
				</div>
			)}
		</div>
	);
}
