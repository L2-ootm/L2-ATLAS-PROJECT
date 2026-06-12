<script lang="ts">
	import HudLabel from '$lib/components/HudLabel.svelte';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
</script>

<svelte:head>
	<title>MISSIONS — ATLAS COCKPIT</title>
</svelte:head>

<section aria-labelledby="missions-heading">
	<header
		style="
			display: flex;
			justify-content: space-between;
			align-items: center;
			border-bottom: 1px solid rgba(255,255,255,0.05);
			padding-bottom: 8px;
			margin-bottom: 16px;
		"
	>
		<h1
			id="missions-heading"
			style="margin: 0; font-family: var(--l2-font-display); font-size: 32px; font-weight: 700; color: var(--l2-fg-1); line-height: 1.2;"
		>
			<HudLabel>MISSIONS</HudLabel>
		</h1>
	</header>

	<GlassPanel style="padding: 24px;">
		<p
			style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--l2-fg-3); margin: 0;"
		>
			Surface implemented in Phase 8 Plan 03.
		</p>
	</GlassPanel>
</section>
