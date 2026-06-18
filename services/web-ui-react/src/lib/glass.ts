import type { CSSProperties } from 'react';

// Shared glass-refraction constants + style helper. Kept separate from the
// GlassFilter component so Fast Refresh stays happy (components-only modules).

export const GLASS_DISPLACE_ID = 'atlas-glass-displace';

/**
 * Glass panel style: translucent tinted pane + frost + refractive displacement +
 * specular edge. Spread onto any container; its children render crisp on top
 * (backdrop-filter only affects what is BEHIND the element). The url() filter is
 * honoured by Chromium / WebView2; the Webkit fallback keeps the frost on Safari.
 */
export function glassPanel(extra?: CSSProperties): CSSProperties {
	return {
		border: '1px solid var(--l2-hairline)',
		borderRadius: 2,
		// Tinted pane that sits CLEARLY above the living TopoField — the terrain only
		// faintly refracts through, it no longer washes across the surface. A faint
		// diagonal specular sheen still sells the glass; the url() displacement + frost
		// keep the refraction. Opacity raised (was 0.18/0.24) per the "panels too
		// transparent" direction so data reads on a real surface, not raw terrain.
		background:
			'linear-gradient(125deg, rgba(237,234,224,0.06) 0%, transparent 30%, transparent 74%, rgba(237,234,224,0.025) 100%), linear-gradient(180deg, rgba(20,24,33,0.74), rgba(10,13,18,0.82))',
		backdropFilter: `blur(11px) url(#${GLASS_DISPLACE_ID}) saturate(1.4) brightness(1.02)`,
		WebkitBackdropFilter: 'blur(11px) saturate(1.4) brightness(1.02)',
		// No heavy inner shadow — that was reading as "solid". Top specular + soft lift.
		boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.07), 0 8px 30px rgba(0,0,0,0.28)',
		...extra
	};
}
