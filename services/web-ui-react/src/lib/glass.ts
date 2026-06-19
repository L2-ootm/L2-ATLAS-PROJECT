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
			'linear-gradient(135deg, rgba(237,234,224,0.11) 0%, transparent 24%, transparent 67%, rgba(237,234,224,0.05) 100%), linear-gradient(180deg, rgba(22,26,36,0.56), rgba(10,13,18,0.64))',
		backdropFilter: `blur(18px) url(#${GLASS_DISPLACE_ID}) saturate(1.7) brightness(1.06)`,
		WebkitBackdropFilter: 'blur(18px) saturate(1.7) brightness(1.06)',
		// Lit top edge + faint inner celestial glow + soft lift = depth without going solid.
		boxShadow:
			'inset 0 1px 0 rgba(237,234,224,0.12), inset 0 0 30px rgba(79,139,255,0.06), 0 12px 44px rgba(0,0,0,0.36)',
		...extra
	};
}
