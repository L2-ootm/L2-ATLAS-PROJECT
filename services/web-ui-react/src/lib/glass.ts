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
		border: '1px solid var(--l2-glass-border)',
		borderRadius: 2,
		// Frosted REFRACTIVE glass (not flat translucency). A heavy blur turns the
		// living TopoField behind into a soft glow rather than a raw contour wash;
		// the url() feDisplacementMap warps that glow fluidically (the "liquid" bend);
		// a bright diagonal specular sweep + an inner celestial glow + a lit top edge
		// give the wet, glowing, glassmorphic read the flat tint was missing.
		background:
			'linear-gradient(135deg, rgba(237,234,224,0.10) 0%, transparent 26%, transparent 70%, rgba(237,234,224,0.045) 100%), linear-gradient(180deg, rgba(20,24,33,0.42), rgba(10,13,18,0.50))',
		// Lighter frost (blur 10, was 18) so the living TopoField stays VISIBLE through
		// the glass — just gently warped by the url() displacement (scale 18) + a soft
		// specular sweep + inner glow. Glassmorphic, but you can read the terrain.
		backdropFilter: `blur(10px) url(#${GLASS_DISPLACE_ID}) saturate(1.5) brightness(1.04)`,
		WebkitBackdropFilter: 'blur(10px) saturate(1.5) brightness(1.04)',
		// Lit top edge + faint inner celestial glow + soft lift = depth without going solid.
		boxShadow:
			'inset 0 1px 0 rgba(237,234,224,0.10), inset 0 0 26px rgba(79,139,255,0.05), 0 10px 38px rgba(0,0,0,0.32)',
		...extra
	};
}
