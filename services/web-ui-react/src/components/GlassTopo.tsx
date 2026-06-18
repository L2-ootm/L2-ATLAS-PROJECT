import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { createTopoField, type TopoFieldAPI } from '../topo/topoEngine';

// GlassTopo — the signature surface: a vivid topographic field rendered behind a
// frosted-glass layer, so the terrain glows *through* the blur (fluidic feel).
// Ported settings from the L2 Systems Design System topo_patterns.html (.ti-shell:
// backdrop-filter blur(16px) saturate(1.3), translucent navy bg) + a vivid field.
// The field is the panel's OWN child (works inside modals over a scrim, where the
// page ambient field is occluded). Pointer drives a fluidic morph; a slow ambient
// orbit keeps it breathing at rest. prefers-reduced-motion → static lattice.

export type GlassTone = 'good' | 'ai' | 'info' | 'warn' | 'bad' | 'atlas';

const GLOW: Record<GlassTone, string> = {
	good: 'rgba(70,240,160,0.95)', // emerald
	ai: 'rgba(161,123,255,0.95)', // violet
	info: 'rgba(79,139,255,0.95)', // celestial
	warn: 'rgba(255,200,80,0.95)',
	bad: 'rgba(255,77,125,0.95)',
	atlas: 'rgba(224,169,78,0.95)' // bronze
};

// Resting lattice tinted toward the tone (dim) so the WHOLE field reads in the
// semantic color through the frost — not neutral grey. The orbit/pointer adds a
// brighter moving glow on top.
const RESTING: Record<GlassTone, string> = {
	good: 'rgba(70,240,160,0.55)',
	ai: 'rgba(161,123,255,0.55)',
	info: 'rgba(110,160,235,0.55)',
	warn: 'rgba(255,200,80,0.5)',
	bad: 'rgba(255,110,150,0.5)',
	atlas: 'rgba(224,180,110,0.5)'
};

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
				cellSize: 15,
				color: RESTING[tone],
				glowColor: glow,
				restingOpacity: 0.42,
				glowOpacity: 0.95,
				restingWidth: 0.8,
				glowWidth: 1.4,
				bulgeStrength: 0.5,
				hoverRadius: Math.max(W, H) * 0.85,
				freq: 0.012
			});
		};
		build();

		const ro = new ResizeObserver(build);
		ro.observe(host);

		// Ambient orbit + pointer reactivity. The engine interpolates toward the
		// hover target and keeps its rAF alive while the target drifts, so a slow
		// moving target = a perpetual gentle morph (one rAF, the engine's own).
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
				t += 0.16;
				const W = host.clientWidth || 400;
				const H = host.clientHeight || 200;
				const x = W * (0.5 + 0.38 * Math.cos(t));
				const y = H * (0.5 + 0.42 * Math.sin(t * 0.8));
				fieldRef.current?.setHover(x, y, glow);
			}, 120);
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
				...style
			}}
		>
			{/* topo field — painted behind the glass so the blur frosts it */}
			<div
				ref={fieldHostRef}
				aria-hidden="true"
				style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none' }}
			/>
			{/* frosted glass — backdrop-filter blurs the field behind it; content is crisp */}
			<div
				style={{
					position: 'relative',
					zIndex: 1,
					borderRadius: radius,
					padding,
					background:
						'linear-gradient(180deg, rgba(17,21,30,0.5), rgba(9,11,16,0.62))',
					backdropFilter: 'blur(11px) saturate(1.4)',
					WebkitBackdropFilter: 'blur(11px) saturate(1.4)',
					boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.06), 0 2px 0 rgba(0,0,0,0.28)'
				}}
			>
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
				{children}
			</div>
		</div>
	);
}
