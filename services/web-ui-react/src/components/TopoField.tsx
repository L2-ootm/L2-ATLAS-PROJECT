import { useEffect, useRef } from 'react';
import { createTopoField, type TopoFieldAPI } from '../topo/topoEngine';

// Ambient topographic background — the "living terrain" beneath the whole cockpit.
// The world ATLAS bears. Faint at rest; bulges + glows by the SEMANTIC context of
// whatever the cursor touches (elements tag themselves with data-topo="brand|info|
// good|warn|bad|atlas"); drifts in parallax on scroll. Recedes behind content.

// Bright glow inks (mix-blend screen) keyed by semantic context.
const GLOW: Record<string, string> = {
	brand: 'rgba(127,0,255,0.85)',
	info: 'rgba(0,240,255,0.80)',
	good: 'rgba(0,255,148,0.80)',
	warn: 'rgba(255,214,0,0.80)',
	bad: 'rgba(255,0,85,0.85)',
	atlas: 'rgba(224,169,78,0.85)'
};

function semanticAt(x: number, y: number): string {
	const el = document.elementFromPoint(x, y) as HTMLElement | null;
	const tagged = el?.closest<HTMLElement>('[data-topo]');
	const key = tagged?.dataset.topo || 'atlas';
	return GLOW[key] || GLOW.atlas;
}

export default function TopoField() {
	const hostRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const host = hostRef.current;
		if (!host) return;

		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		let field: TopoFieldAPI | null = null;
		let raf = 0;

		function build() {
			field?.destroy();
			const W = window.innerWidth;
			const H = window.innerHeight;
			field = createTopoField({
				host: host!,
				viewW: W,
				viewH: H,
				cellSize: 18,
				color: 'rgba(170,190,220,1)',
				glowColor: GLOW.atlas,
				restingOpacity: 0.1,
				glowOpacity: 0.32, // ambient — recedes behind content
				restingWidth: 0.7,
				glowWidth: 1.0,
				bulgeStrength: 0.42,
				hoverRadius: Math.min(W, H) * 0.32,
				freq: 0.005
			});
		}

		build();

		let px = -9999,
			py = -9999,
			queued = false;
		function onMove(e: PointerEvent) {
			px = e.clientX;
			py = e.clientY;
			if (queued || reduce || !field) return;
			queued = true;
			raf = requestAnimationFrame(() => {
				queued = false;
				field?.setHover(px, py, semanticAt(px, py));
			});
		}
		function onLeave() {
			field?.endHover();
		}

		// Parallax drift: the terrain is never frozen; it eases under scroll.
		function onScroll() {
			const drift = -(window.scrollY % window.innerHeight) * 0.06;
			host!.style.transform = `translate3d(0, ${drift}px, 0)`;
		}

		let rt = 0;
		function onResize() {
			clearTimeout(rt);
			rt = window.setTimeout(build, 200) as unknown as number;
		}

		if (!reduce) {
			window.addEventListener('pointermove', onMove, { passive: true });
			window.addEventListener('pointerleave', onLeave, { passive: true });
			window.addEventListener('scroll', onScroll, { passive: true });
		}
		window.addEventListener('resize', onResize);

		return () => {
			cancelAnimationFrame(raf);
			clearTimeout(rt);
			window.removeEventListener('pointermove', onMove);
			window.removeEventListener('pointerleave', onLeave);
			window.removeEventListener('scroll', onScroll);
			window.removeEventListener('resize', onResize);
			field?.destroy();
		};
	}, []);

	return (
		<div
			ref={hostRef}
			aria-hidden="true"
			style={{
				position: 'fixed',
				inset: '-10vh 0 0 0',
				height: '120vh',
				zIndex: 0,
				pointerEvents: 'none',
				opacity: 0.5,
				willChange: 'transform'
			}}
		/>
	);
}
