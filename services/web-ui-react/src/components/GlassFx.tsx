import type { CSSProperties, ReactNode } from 'react';
import { GLASS_DISPLACE_ID, glassPanel } from '../lib/glass';

// GlassFx — a real refractive glass treatment (not just blur). An SVG
// feDisplacementMap warps the backdrop behind a panel, so the page's living
// TopoField bends through the glass like a thick lens — subtle but luxurious.
// Mount <GlassFilter /> once near the app root; surfaces opt in via the
// <GlassPanel> wrapper (or the glassPanel() style helper for fine control).

/**
 * Reusable glass surface. Drop-in container — its children render crisp on top
 * of the refractive frost. `style` is merged over the glass defaults (so callers
 * can add overflow/grid/margins); pass-through props cover clicks and a11y.
 */
export function GlassPanel({
	children,
	style,
	className,
	...rest
}: {
	children?: ReactNode;
	style?: CSSProperties;
	className?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div className={className} style={glassPanel(style)} {...rest}>
			{children}
		</div>
	);
}

/** Mount once near the app root. Renders the zero-size SVG filter defs. */
export function GlassFilter() {
	return (
		<svg
			aria-hidden="true"
			width="0"
			height="0"
			style={{ position: 'absolute', width: 0, height: 0, pointerEvents: 'none' }}
		>
			<defs>
				<filter
					id={GLASS_DISPLACE_ID}
					x="-25%"
					y="-25%"
					width="150%"
					height="150%"
					colorInterpolationFilters="sRGB"
				>
					{/* Low-frequency fractal noise = long, liquid undulations (not grain). */}
					<feTurbulence
						type="fractalNoise"
						baseFrequency="0.009 0.013"
						numOctaves={2}
						seed={42}
						result="noise"
					/>
					{/* Soften the map so the refraction reads as smooth glass, not ripples. */}
					<feGaussianBlur in="noise" stdDeviation="1.4" result="softMap" />
					{/* Warp the backdrop by the map. Low scale = a gentle, premium bend. */}
					<feDisplacementMap
						in="SourceGraphic"
						in2="softMap"
						scale={26}
						xChannelSelector="R"
						yChannelSelector="G"
					/>
				</filter>
			</defs>
		</svg>
	);
}
