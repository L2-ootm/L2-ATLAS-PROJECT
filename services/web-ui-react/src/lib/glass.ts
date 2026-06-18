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
		// Translucent pane so the living TopoField reads THROUGH the frost; a faint
		// diagonal specular sheen sells the glass without making it opaque.
		background:
			'linear-gradient(125deg, rgba(237,234,224,0.05) 0%, transparent 28%, transparent 75%, rgba(237,234,224,0.022) 100%), linear-gradient(180deg, rgba(20,24,33,0.18), rgba(10,13,18,0.24))',
		backdropFilter: `blur(8px) url(#${GLASS_DISPLACE_ID}) saturate(1.45) brightness(1.03)`,
		WebkitBackdropFilter: 'blur(8px) saturate(1.45) brightness(1.03)',
		// No heavy inner shadow — that was reading as "solid". Top specular + soft lift.
		boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.07), 0 8px 30px rgba(0,0,0,0.28)',
		...extra
	};
}
