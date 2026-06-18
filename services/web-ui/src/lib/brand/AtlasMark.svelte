<script lang="ts">
	// ATLAS logo glyph — "the titan bears the world".
	// A wireframe contour globe (the world, drawn in the same topographic language
	// as the cockpit's living terrain) borne by a load-bearing figure.
	//
	// Three art-directed variants (a full set for any environment):
	//   borne   — globe cradled by a bronze yoke + arms (most figurative; best favicon read)
	//   axis    — globe on a shoulder-bar descending into a single load-bearing axis (monument)
	//   bracket — globe held in an angular obsidian-cut bracket (most HUD, least figurative)
	//
	// Tone:
	//   color        — celestial globe + bronze bearer (full brand)
	//   currentColor — single-ink, inherits text color + any semantic glow (sidebar/inline)

	type Variant = 'borne' | 'axis' | 'bracket';
	type Tone = 'color' | 'currentColor';

	let {
		variant = 'borne' as Variant,
		tone = 'color' as Tone,
		size = 32,
		title = 'ATLAS'
	}: { variant?: Variant; tone?: Tone; size?: number; title?: string } = $props();

	const globe = $derived(tone === 'color' ? 'var(--atlas-celestial)' : 'currentColor');
	const bearer = $derived(tone === 'color' ? 'var(--atlas-bronze)' : 'currentColor');
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 64 64"
	fill="none"
	role="img"
	aria-label={title}
	style="display:block;overflow:visible;"
>
	<title>{title}</title>

	{#if variant === 'borne'}
		<!-- wireframe world -->
		<g stroke={globe} stroke-width="2" stroke-linecap="round">
			<circle cx="32" cy="25" r="14" />
			<ellipse cx="32" cy="25" rx="14" ry="4.6" />
			<ellipse cx="32" cy="25" rx="4.6" ry="14" />
		</g>
		<!-- bronze yoke + arms taking the load -->
		<path d="M11 40 Q32 60 53 40" stroke={bearer} stroke-width="3" stroke-linecap="round" />
		<path d="M18 44 L23 38 M46 44 L41 38" stroke={bearer} stroke-width="2.4" stroke-linecap="round" />
	{:else if variant === 'axis'}
		<g stroke={globe} stroke-width="2" stroke-linecap="round">
			<circle cx="32" cy="22" r="13" />
			<ellipse cx="32" cy="22" rx="13" ry="4.2" />
			<ellipse cx="32" cy="22" rx="4.2" ry="13" />
		</g>
		<path d="M16 40 L32 35 L48 40" stroke={bearer} stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
		<path d="M32 35 L32 56 M24 56 L40 56" stroke={bearer} stroke-width="2.6" stroke-linecap="round" />
	{:else}
		<g stroke={globe} stroke-width="2" stroke-linecap="round">
			<circle cx="32" cy="24" r="13" />
			<ellipse cx="32" cy="24" rx="13" ry="4.3" />
			<ellipse cx="32" cy="24" rx="4.3" ry="13" />
		</g>
		<path d="M14 41 L22 49 L42 49 L50 41" stroke={bearer} stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
		<path d="M22 49 L22 56 M42 49 L42 56" stroke={bearer} stroke-width="2.4" stroke-linecap="round" />
	{/if}
</svg>
