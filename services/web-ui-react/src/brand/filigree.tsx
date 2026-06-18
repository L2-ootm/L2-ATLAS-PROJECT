import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';

// Heraldic signature elements — fine bronze/celestial linework that frames the
// cockpit like an engraved astronomical chart. Hairlines are expensive, not loud.

// ── CompassStar — four-point star corner/accent mark ────────────────────────
export function CompassStar({
	size = 14,
	color = 'var(--atlas-bronze)',
	style
}: {
	size?: number;
	color?: string;
	style?: CSSProperties;
}) {
	return (
		<svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={style}>
			<path d="M12 1 L13.4 10.6 L23 12 L13.4 13.4 L12 23 L10.6 13.4 L1 12 L10.6 10.6 Z" fill={color} opacity="0.9" />
			<path d="M12 5 L12 19 M5 12 L19 12" stroke={color} strokeWidth="0.5" opacity="0.5" />
		</svg>
	);
}

// ── AstrolabeRings — concentric celestial rings, slowly rotating ────────────
export function AstrolabeRings({
	size = 360,
	style
}: {
	size?: number;
	style?: CSSProperties;
}) {
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 200 200"
			fill="none"
			aria-hidden="true"
			style={style}
		>
			<g stroke="var(--atlas-bronze)" strokeWidth="0.4" opacity="0.5">
				<circle cx="100" cy="100" r="98" />
				<circle cx="100" cy="100" r="86" strokeOpacity="0.5" />
			</g>
			{/* ticked outer ring */}
			<g stroke="var(--atlas-bronze)" opacity="0.55" style={{ animation: 'atlas-spin-cw 220s linear infinite', transformOrigin: '100px 100px' }}>
				{Array.from({ length: 72 }).map((_, i) => {
					const a = (i / 72) * Math.PI * 2;
					const long = i % 9 === 0 ? 5 : 2.5;
					return (
						<line
							key={i}
							x1={100 + Math.cos(a) * 86}
							y1={100 + Math.sin(a) * 86}
							x2={100 + Math.cos(a) * (86 - long)}
							y2={100 + Math.sin(a) * (86 - long)}
							strokeWidth={i % 9 === 0 ? 0.7 : 0.35}
						/>
					);
				})}
			</g>
			{/* celestial graticule, counter-rotating */}
			<g stroke="var(--atlas-mythic)" strokeWidth="0.4" opacity="0.34" style={{ animation: 'atlas-spin-ccw 300s linear infinite', transformOrigin: '100px 100px' }}>
				<circle cx="100" cy="100" r="64" />
				<ellipse cx="100" cy="100" rx="64" ry="22" />
				<ellipse cx="100" cy="100" rx="64" ry="44" />
				<ellipse cx="100" cy="100" rx="22" ry="64" />
				<ellipse cx="100" cy="100" rx="44" ry="64" />
			</g>
			{/* tilted orbit */}
			<g style={{ animation: 'atlas-spin-cw 160s linear infinite', transformOrigin: '100px 100px' }}>
				<ellipse cx="100" cy="100" rx="78" ry="26" transform="rotate(-22 100 100)" stroke="var(--atlas-celestial)" strokeWidth="0.5" opacity="0.4" />
			</g>
		</svg>
	);
}

// ── HairlineFrame — bronze hairline border with compass-star corners ────────
export function HairlineFrame({ inset = 0 }: { inset?: number }) {
	const c = (pos: CSSProperties) => (
		<CompassStar size={11} style={{ position: 'absolute', ...pos }} />
	);
	return (
		<div aria-hidden="true" style={{ position: 'absolute', inset, pointerEvents: 'none' }}>
			<div
				style={{
					position: 'absolute',
					inset: 6,
					border: '1px solid var(--atlas-bronze-soft)',
					borderRadius: 2
				}}
			/>
			{c({ top: 0, left: 0 })}
			{c({ top: 0, right: 0 })}
			{c({ bottom: 0, left: 0 })}
			{c({ bottom: 0, right: 0 })}
		</div>
	);
}

// ── Starfield — slow-drifting points of light. Replaces gradient fog with a
//    controlled celestial field (dark-luxe: light hitting material, not haze). ─
export function Starfield({ density = 0.00016, style }: { density?: number; style?: CSSProperties }) {
	const ref = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = ref.current;
		if (!canvas) return;
		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		let w = 0,
			h = 0,
			raf = 0;
		const dpr = Math.min(window.devicePixelRatio || 1, 2);
		type Star = { x: number; y: number; r: number; tw: number; ph: number; c: string };
		let stars: Star[] = [];
		const inks = ['rgba(237,234,224,', 'rgba(79,139,255,', 'rgba(70,240,224,', 'rgba(161,123,255,'];

		function build() {
			const host = canvas!.parentElement;
			if (!host) return;
			w = host.clientWidth;
			h = host.clientHeight;
			canvas!.width = w * dpr;
			canvas!.height = h * dpr;
			canvas!.style.width = w + 'px';
			canvas!.style.height = h + 'px';
			ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
			const n = Math.max(24, Math.floor(w * h * density));
			stars = Array.from({ length: n }, () => ({
				x: Math.random() * w,
				y: Math.random() * h,
				r: Math.random() * 1.1 + 0.3,
				tw: Math.random() * 0.6 + 0.2,
				ph: Math.random() * Math.PI * 2,
				c: inks[(Math.random() * inks.length) | 0]
			}));
		}

		const t0 = performance.now();
		function frame(now: number) {
			const t = (now - t0) / 1000;
			ctx!.clearRect(0, 0, w, h);
			for (const s of stars) {
				const a = 0.25 + 0.55 * (0.5 + 0.5 * Math.sin(t * s.tw + s.ph));
				ctx!.beginPath();
				ctx!.fillStyle = s.c + a.toFixed(3) + ')';
				ctx!.arc(s.x, s.y, s.r, 0, Math.PI * 2);
				ctx!.fill();
			}
			if (!reduce) raf = requestAnimationFrame(frame);
		}

		build();
		if (reduce) frame(performance.now());
		else raf = requestAnimationFrame(frame);

		const onResize = () => {
			build();
		};
		window.addEventListener('resize', onResize);
		return () => {
			cancelAnimationFrame(raf);
			window.removeEventListener('resize', onResize);
		};
	}, [density]);

	return <canvas ref={ref} aria-hidden="true" style={{ display: 'block', ...style }} />;
}
