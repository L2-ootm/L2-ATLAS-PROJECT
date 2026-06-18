import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { createTopoField, type TopoFieldAPI } from '../topo/topoEngine';

// GlassTopo — the signature surface: a dense, uniformly-glowing topographic field
// rendered behind a frosted-glass layer, so the terrain glows *through* the blur.
// The reference look (L2 Systems Design System) is a fine green contour map that
// glows across the WHOLE panel — not a single moving highlight. So here the
// *resting* field is the star: bright, dense, bloomed, uniform. The pointer / slow
// ambient orbit only adds a gentle moving accent on top. prefers-reduced-motion →
// static field (still fully visible). cellSize/levels tuned for density.

export type GlassTone = 'good' | 'ai' | 'info' | 'warn' | 'bad' | 'atlas';

// Bright moving-accent colour (the local bulge glow that follows pointer/orbit).
const GLOW: Record<GlassTone, string> = {
	good: 'rgba(90,255,180,1)',
	ai: 'rgba(178,148,255,1)',
	info: 'rgba(110,165,255,1)',
	warn: 'rgba(255,205,90,1)',
	bad: 'rgba(255,100,140,1)',
	atlas: 'rgba(235,185,110,1)'
};

// Resting field colour — now the dominant layer, so it must read as a saturated
// glowing map (bright + opaque), not a dim grey lattice.
const RESTING: Record<GlassTone, string> = {
	good: 'rgba(74,235,158,0.92)',
	ai: 'rgba(168,138,255,0.92)',
	info: 'rgba(96,156,255,0.92)',
	warn: 'rgba(255,200,85,0.9)',
	bad: 'rgba(255,108,148,0.9)',
	atlas: 'rgba(230,180,110,0.9)'
};

// Soft bloom colour for the drop-shadow on the field (tight halo — keep lines crisp).
const BLOOM: Record<GlassTone, string> = {
	good: 'rgba(74,235,158,0.4)',
	ai: 'rgba(168,138,255,0.4)',
	info: 'rgba(96,156,255,0.4)',
	warn: 'rgba(255,200,85,0.38)',
	bad: 'rgba(255,108,148,0.38)',
	atlas: 'rgba(230,180,110,0.38)'
};

// Faint tone tint mixed into the glass so the frost itself carries the colour.
const TINT: Record<GlassTone, string> = {
	good: 'rgba(20,60,44,0.34)',
	ai: 'rgba(40,30,68,0.34)',
	info: 'rgba(22,38,72,0.34)',
	warn: 'rgba(56,46,18,0.32)',
	bad: 'rgba(60,24,38,0.32)',
	atlas: 'rgba(54,42,20,0.32)'
};

// More contour levels = more concentric lines = the dense reference map.
const LEVELS = [0.18, 0.28, 0.38, 0.48, 0.58, 0.68, 0.78, 0.88];

interface GlassTopoProps {
	children?: ReactNode;
	tone?: GlassTone;
	/** outer corner radius (px) */
	radius?: number;
	/** content padding (px or any CSS value) */
	padding?: number | string;
	/** bronze specular top edge (brand surface) */
	accent?: boolean;
	className?: string;
	/** style on the outer root (margins, width, boxShadow…) */
	style?: CSSProperties;
}

export default function GlassTopo({
	children,
	tone = 'info',
	radius = 2,
	padding = 0,
	accent = false,
	className,
	style
}: GlassTopoProps) {
	const fieldHostRef = useRef<HTMLDivElement>(null);
	const fieldRef = useRef<TopoFieldAPI | null>(null);

	useEffect(() => {
		const host = fieldHostRef.current;
		if (!host) return;
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		const glow = GLOW[tone];

		const build = () => {
			fieldRef.current?.destroy();
			const W = host.clientWidth || 400;
			const H = host.clientHeight || 200;
			fieldRef.current = createTopoField({
				host,
				viewW: W,
				viewH: H,
				cellSize: 9,
				levels: LEVELS,
				color: RESTING[tone],
				glowColor: glow,
				// resting field is the star: dense, bright, uniform, CRISP lines
				restingOpacity: 0.82,
				restingWidth: 0.7,
				// moving accent: a small localised bulge (NOT a panel-wide mask hole)
				glowOpacity: 0.95,
				glowWidth: 1.3,
				bulgeStrength: 0.55,
				hoverRadius: 150,
				freq: 0.015
			});
		};
		build();

		const ro = new ResizeObserver(build);
		ro.observe(host);

		// Ambient orbit + pointer reactivity — a gentle moving highlight over the
		// already-glowing field. Small hoverRadius keeps it a localised accent.
		let orbit: ReturnType<typeof setInterval> | null = null;
		let pointerUntil = 0;
		const onMove = (e: PointerEvent) => {
			const r = host.getBoundingClientRect();
			pointerUntil = Date.now() + 900;
			fieldRef.current?.setHover(e.clientX - r.left, e.clientY - r.top, glow);
		};
		if (!reduced) {
			let t = Math.random() * Math.PI * 2;
			orbit = setInterval(() => {
				if (Date.now() < pointerUntil) return; // cursor owns the field while moving
				t += 0.14;
				const W = host.clientWidth || 400;
				const H = host.clientHeight || 200;
				const x = W * (0.5 + 0.4 * Math.cos(t));
				const y = H * (0.5 + 0.44 * Math.sin(t * 0.8));
				fieldRef.current?.setHover(x, y, glow);
			}, 130);
			host.parentElement?.addEventListener('pointermove', onMove);
		}

		return () => {
			ro.disconnect();
			if (orbit) clearInterval(orbit);
			host.parentElement?.removeEventListener('pointermove', onMove);
			fieldRef.current?.destroy();
			fieldRef.current = null;
		};
	}, [tone]);

	return (
		<div
			className={className}
			style={{
				position: 'relative',
				borderRadius: radius,
				overflow: 'hidden',
				border: '1px solid var(--l2-hairline)',
				background: '#06080c',
				...style
			}}
		>
			{/* topo field — bloomed and painted behind the glass so the blur frosts it */}
			<div
				ref={fieldHostRef}
				aria-hidden="true"
				style={{
					position: 'absolute',
					inset: 0,
					zIndex: 0,
					pointerEvents: 'none',
					filter: `drop-shadow(0 0 2px ${BLOOM[tone]})`
				}}
			/>
			{/* frosted glass — light bg + low blur so the field reads through clearly */}
			<div
				style={{
					position: 'relative',
					zIndex: 1,
					borderRadius: radius,
					padding,
					background: `linear-gradient(180deg, ${TINT[tone]}, rgba(7,10,15,0.42))`,
					backdropFilter: 'blur(3px) saturate(1.6)',
					WebkitBackdropFilter: 'blur(3px) saturate(1.6)',
					boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.06), 0 2px 0 rgba(0,0,0,0.28)'
				}}
			>
				{/* vignette — darken edges so the glowing field feels centred (reference) */}
				<span
					aria-hidden="true"
					style={{
						position: 'absolute',
						inset: 0,
						borderRadius: radius,
						background:
							'radial-gradient(ellipse at center, transparent 42%, rgba(3,5,9,0.55) 100%)',
						pointerEvents: 'none',
						zIndex: 1
					}}
				/>
				{accent && (
					<span
						aria-hidden="true"
						style={{
							position: 'absolute',
							top: 0,
							left: 0,
							right: 0,
							height: 1,
							background:
								'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)',
							opacity: 0.55,
							zIndex: 2
						}}
					/>
				)}
				<div style={{ position: 'relative', zIndex: 2 }}>{children}</div>
			</div>
		</div>
	);
}
