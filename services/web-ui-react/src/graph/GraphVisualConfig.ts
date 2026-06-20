// Centralized visual config for the Graphify knowledge graph.
//
// Category coloring is SEMANTIC and STABLE — never heat-map, never hue-shift by
// activity. Activity (brightness/glow/scale/fog) is layered on top of these base
// hues elsewhere; this file owns the base hues, sizes, link/particle colors, and
// the force/bloom constants so the renderer stays config-driven.

import type { GraphNode } from '../lib/api';

// ── Category colors (canonical ATLAS categories — exact spec hues) ───────────
export const CATEGORY_COLOR: Record<string, string> = {
	// structural hubs
	root: '#B08A57', // bronze
	group: '#B08A57', // folder = bronze/amber
	// canonical content categories
	phase: '#4F8BFF', // blue/indigo
	roadmap: '#46F0E0', // cyan
	state: '#46F0E0', // cyan
	research: '#00CED1', // teal
	prep: '#A17BFF', // violet
	report: '#FFD700', // gold
	// secondary ATLAS kinds (brand-aligned, distinct)
	milestone: '#6FA8FF',
	project: '#B08A57',
	requirements: '#4F8BFF',
	risks: '#FF6F91',
	retro: '#46F0A0',
	intel: '#46F0E0',
	doc: '#9BA0AD' // note/fallback neutral accent
};

// Deterministic palette for unknown kinds (folder-slug communities in the
// global / obsidian / projects scopes) — stable per kind, not heat-based.
export const PALETTE = [
	'#00CED1', '#46F0E0', '#4F8BFF', '#A17BFF', '#C58CF0', '#FF6F91',
	'#FFD700', '#46F0A0', '#B08A57', '#5BC8FF', '#9A8CFF', '#FF9F4A', '#3DD6A8'
];

export function paletteFor(kind: string): string {
	let h = 0;
	for (let i = 0; i < kind.length; i++) h = (h * 31 + kind.charCodeAt(i)) | 0;
	return PALETTE[Math.abs(h) % PALETTE.length];
}

export const colorFor = (kind: string): string => CATEGORY_COLOR[kind] ?? paletteFor(kind);

// ── Link + particle colors ──────────────────────────────────────────────────
export const LINK_COLOR: Record<string, string> = {
	contains: 'rgba(176,138,87,0.16)',
	link: 'rgba(70,240,224,0.5)',
	wikilink: 'rgba(0,206,209,0.5)',
	decision: 'rgba(161,123,255,0.45)',
	phase: 'rgba(79,139,255,0.45)'
};
export const linkColorFor = (kind: string): string => LINK_COLOR[kind] ?? 'rgba(155,160,173,0.16)';

// Bright, opaque particle colors so the "electricity" glows through bloom.
export const PARTICLE_COLOR: Record<string, string> = {
	link: '#7CF6EC',
	wikilink: '#5DEBEE',
	decision: '#C7A8FF',
	phase: '#8FB4FF'
};
export const particleColorFor = (kind: string): string => PARTICLE_COLOR[kind] ?? '#8FE9FF';

// ── Node sizing (activity can scale on top of this; base is content size) ────
export function nodeSize(node: GraphNode): number {
	if (node.id === 'root') return 8;
	if (node.kind === 'group') return 4.5;
	return Math.max(1, Math.min(4.5, node.size / 3400));
}

// ── Bloom (gentle — bright cores/particles glow, hubs don't melt) ────────────
export const BLOOM = { strength: 0.72, radius: 0.5, threshold: 0.3 } as const;

// ── Force / interaction physics ──────────────────────────────────────────────
// Smoothed cooling + weighted damping so drag/orbit don't fight or spring back.
export const FORCE = {
	velocityDecay: 0.4,
	alphaDecay: 0.02,
	warmupTicks: 0,
	cooldownTime: 12000,
	orbitDamping: 0.12,
	// Slow ambient orbit around the fitted center (OrbitControls.autoRotateSpeed
	// ≈ rotations/min at 60fps). Subtle — the graph drifts, the user can grab it.
	autoRotateSpeed: 0.32
} as const;

// ── Text tokens (contrast-audited) ───────────────────────────────────────────
export const TEXT = {
	primary: '#EDEAE0', // ivory — labels, values
	secondary: '#9BA0AD', // muted — captions
	ghost: '#5B6170', // disabled
	bronze: '#C79A52' // section eyebrows
} as const;
