<script lang="ts">
	// ATLAS horizontal lockup — ATLAS-forward, L2-endorsed.
	// Mark + wordmark + subtle "BY L2 SYSTEMS" endorsement (with the L2 glyph).

	import AtlasMark from './AtlasMark.svelte';

	type Variant = 'borne' | 'axis' | 'bracket';

	let {
		variant = 'borne' as Variant,
		markSize = 30,
		endorse = true,
		tone = 'color' as 'color' | 'currentColor'
	}: { variant?: Variant; markSize?: number; endorse?: boolean; tone?: 'color' | 'currentColor' } = $props();
</script>

<div style="display:flex;align-items:center;gap:12px;">
	<AtlasMark {variant} {tone} size={markSize} />
	<div style="display:flex;flex-direction:column;gap:3px;">
		<span
			style="
				font-family:var(--l2-font-display);
				font-weight:700;
				font-size:{markSize * 0.6}px;
				letter-spacing:0.26em;
				line-height:1;
				color:var(--l2-fg-1);
			"
		>ATL<span style="color:var(--atlas-bronze);">A</span>S</span>
		{#if endorse}
			<span
				style="
					font-family:var(--l2-font-mono);
					font-size:9px;
					letter-spacing:0.24em;
					text-transform:uppercase;
					color:var(--l2-fg-3);
					display:flex;align-items:center;gap:6px;
				"
			>
				<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--l2-fg-2)" stroke-width="3" stroke-linecap="square" aria-hidden="true">
					<path d="M5 5 V19 H13 M15 5 H19 V11 H15 V19 H19" />
				</svg>
				BY L2 SYSTEMS
			</span>
		{/if}
	</div>
</div>
