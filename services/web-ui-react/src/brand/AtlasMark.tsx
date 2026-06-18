// ATLAS celestial mark — "the titan bears the heavens".
// An astrolabe globe drawn in fine constellation linework (the world rendered as
// celestial cartography), cradled by a bronze bearer-arc. The mark is a fragment
// of the same star-field/topographic language that runs under the whole cockpit.
//
// Variants:
//   celestial — the astrolabe globe + bronze cradle (default; brand mark)
//   seal      — celestial globe inside a ticked bronze astrolabe ring (favicon/seal)
// Tone:
//   color — celestial-blue graticule, mythic-blue orbits, bronze cradle + star
//   mono  — single ink (currentColor), inherits text + semantic glow

type Variant = 'celestial' | 'seal';
type Tone = 'color' | 'mono';

interface AtlasMarkProps {
	variant?: Variant;
	tone?: Tone;
	size?: number;
	title?: string;
}

export default function AtlasMark({
	variant = 'celestial',
	tone = 'color',
	size = 32,
	title = 'ATLAS'
}: AtlasMarkProps) {
	const mono = tone === 'mono';
	const globe = mono ? 'currentColor' : 'var(--atlas-celestial)';
	const lines = mono ? 'currentColor' : 'var(--atlas-mythic)';
	const bronze = mono ? 'currentColor' : 'var(--atlas-bronze)';
	const node = mono ? 'currentColor' : 'var(--atlas-cyan)';

	// Globe sits high so the bronze cradle reads beneath it.
	const cx = 32;
	const cy = 27;
	const r = 16;

	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 64 64"
			fill="none"
			role="img"
			aria-label={title}
			style={{ display: 'block', overflow: 'visible' }}
		>
			<title>{title}</title>

			{variant === 'seal' && (
				// Astrolabe ring with compass ticks
				<g stroke={bronze} strokeWidth="1" opacity="0.9">
					<circle cx="32" cy="30" r="29" />
					<circle cx="32" cy="30" r="26" strokeOpacity="0.5" />
					{Array.from({ length: 24 }).map((_, i) => {
						const a = (i / 24) * Math.PI * 2;
						const long = i % 6 === 0 ? 3.4 : 1.8;
						const r0 = 29;
						const r1 = 29 - long;
						return (
							<line
								key={i}
								x1={32 + Math.cos(a) * r0}
								y1={30 + Math.sin(a) * r0}
								x2={32 + Math.cos(a) * r1}
								y2={30 + Math.sin(a) * r1}
								strokeWidth={i % 6 === 0 ? 1.1 : 0.7}
							/>
						);
					})}
				</g>
			)}

			{/* ── Celestial globe — graticule ─────────────────────────────────── */}
			<circle cx={cx} cy={cy} r={r} stroke={globe} strokeWidth="1.4" />
			<g stroke={lines} strokeWidth="0.85" opacity="0.92">
				{/* latitudes */}
				<ellipse cx={cx} cy={cy} rx={r} ry={r * 0.34} />
				<ellipse cx={cx} cy={cy} rx={r * 0.82} ry={r * 0.66} />
				{/* meridians */}
				<ellipse cx={cx} cy={cy} rx={r * 0.34} ry={r} />
				<ellipse cx={cx} cy={cy} rx={r * 0.66} ry={r} />
			</g>

			{/* ── Tilted orbit ring crossing the sphere ───────────────────────── */}
			<g transform={`rotate(-24 ${cx} ${cy})`}>
				<ellipse cx={cx} cy={cy} rx={r + 4.5} ry={r * 0.32} stroke={globe} strokeWidth="1" opacity="0.8" />
			</g>

			{/* ── Constellation nodes (stars) ─────────────────────────────────── */}
			<g fill={node}>
				<circle cx={cx} cy={cy - r} r="1.25" />
				<circle cx={cx + r * 0.7} cy={cy - r * 0.5} r="1" />
				<circle cx={cx - r * 0.78} cy={cy + r * 0.36} r="1" />
				<circle cx={cx + r * 0.5} cy={cy + r * 0.62} r="0.9" />
			</g>

			{/* ── Central compass-star ────────────────────────────────────────── */}
			<g stroke={bronze} strokeWidth="1" strokeLinecap="round">
				<path d={`M${cx} ${cy - 4} L${cx} ${cy + 4} M${cx - 4} ${cy} L${cx + 4} ${cy}`} />
				<path
					d={`M${cx - 2.4} ${cy - 2.4} L${cx + 2.4} ${cy + 2.4} M${cx + 2.4} ${cy - 2.4} L${cx - 2.4} ${cy + 2.4}`}
					strokeWidth="0.6"
					opacity="0.7"
				/>
			</g>
			<circle cx={cx} cy={cy} r="1.3" fill={bronze} />

			{/* ── Bronze bearer cradle — the titan takes the load ─────────────── */}
			<g stroke={bronze} strokeLinecap="round" fill="none">
				<path d={`M14 ${cy + r - 1} Q32 ${cy + r + 12} 50 ${cy + r - 1}`} strokeWidth="2" />
				<path d={`M19 ${cy + r + 2.5} L24 ${cy + r - 3} M45 ${cy + r + 2.5} L40 ${cy + r - 3}`} strokeWidth="1.6" opacity="0.85" />
			</g>
		</svg>
	);
}
