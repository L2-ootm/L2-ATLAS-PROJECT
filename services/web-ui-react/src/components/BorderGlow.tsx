import { useCallback, useRef, type CSSProperties, type ReactNode } from 'react';

// BorderGlow — cursor-reactive border + edge halo, adapted from reactbits
// BorderGlow (.planning/research/ui-effects/border-glow.md). Pointer position
// drives two CSS vars (--cursor-angle, --edge-proximity); the wedge-masked mesh
// border + box-shadow halo (in app.css, .abg-* classes) light the edge nearest
// the cursor. ATLAS-toned: 2px radius, celestial/violet palette, restrained.

// HSL triplet "h s l" → layered glow vars (decreasing opacity rings).
function buildGlowVars(glow: string, intensity: number): Record<string, string> {
	const m = glow.match(/([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
	const [h, s, l] = m ? [m[1], m[2], m[3]] : ['220', '100', '70'];
	const base = `${h}deg ${s}% ${l}%`;
	const ramp: Array<[string, number]> = [
		['', 100],
		['-60', 60],
		['-50', 50],
		['-40', 40],
		['-30', 30],
		['-20', 20],
		['-10', 10]
	];
	const vars: Record<string, string> = {};
	for (const [suffix, op] of ramp) {
		vars[`--glow-color${suffix}`] = `hsl(${base} / ${Math.min(op * intensity, 100)}%)`;
	}
	return vars;
}

// Seven radial mesh stops mapped across the supplied accent colors.
const POSITIONS = ['80% 55%', '69% 34%', '8% 6%', '41% 38%', '86% 85%', '82% 18%', '51% 4%'];
const COLOR_MAP = [0, 1, 2, 0, 1, 2, 1];
const KEYS = ['--gradient-one', '--gradient-two', '--gradient-three', '--gradient-four', '--gradient-five', '--gradient-six', '--gradient-seven'];

function buildGradientVars(colors: string[]): Record<string, string> {
	const vars: Record<string, string> = {};
	for (let i = 0; i < 7; i++) {
		const c = colors[Math.min(COLOR_MAP[i], colors.length - 1)];
		vars[KEYS[i]] = `radial-gradient(at ${POSITIONS[i]}, ${c} 0px, transparent 50%)`;
	}
	vars['--gradient-base'] = `linear-gradient(${colors[0]} 0 100%)`;
	return vars;
}

interface BorderGlowProps {
	children?: ReactNode;
	className?: string;
	style?: CSSProperties;
	/** HSL triplet "h s l" for the halo color */
	glowColor?: string;
	/** accent colors for the mesh border */
	colors?: string[];
	cardBg?: string;
	borderRadius?: number;
	glowIntensity?: number;
	/** 0 center → 100 edge: how near the cursor must be before the glow shows */
	edgeSensitivity?: number;
}

export default function BorderGlow({
	children,
	className,
	style,
	glowColor = '220 100 70',
	colors = ['#4F8BFF', '#A17BFF', '#46F0E0'],
	cardBg = '#0E1118',
	borderRadius = 2,
	glowIntensity = 0.9,
	edgeSensitivity = 25
}: BorderGlowProps) {
	const ref = useRef<HTMLDivElement>(null);

	const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
		const card = ref.current;
		if (!card) return;
		const rect = card.getBoundingClientRect();
		const x = e.clientX - rect.left;
		const y = e.clientY - rect.top;
		const cx = rect.width / 2;
		const cy = rect.height / 2;
		const dx = x - cx;
		const dy = y - cy;
		// edge proximity: 0 at center, 1 at the nearest edge
		let kx = Infinity;
		let ky = Infinity;
		if (dx !== 0) kx = cx / Math.abs(dx);
		if (dy !== 0) ky = cy / Math.abs(dy);
		const edge = Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
		// bearing center → pointer, +90deg so 0deg points up
		let deg = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
		if (deg < 0) deg += 360;
		card.style.setProperty('--edge-proximity', (edge * 100).toFixed(3));
		card.style.setProperty('--cursor-angle', `${deg.toFixed(3)}deg`);
	}, []);

	const vars = {
		'--card-bg': cardBg,
		'--border-radius': `${borderRadius}px`,
		'--edge-sensitivity': edgeSensitivity,
		...buildGlowVars(glowColor, glowIntensity),
		...buildGradientVars(colors)
	} as CSSProperties;

	return (
		<div
			ref={ref}
			onPointerMove={onPointerMove}
			className={`abg-card ${className ?? ''}`}
			style={{ ...vars, ...style }}
		>
			<span className="abg-edge" aria-hidden="true" />
			<div className="abg-inner">{children}</div>
		</div>
	);
}
