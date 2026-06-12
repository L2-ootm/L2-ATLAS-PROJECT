<script lang="ts">
	import HudLabel from '$lib/components/HudLabel.svelte';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
</script>

<svelte:head>
	<title>RUNS — ATLAS COCKPIT</title>
</svelte:head>

<section aria-labelledby="runs-heading">
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
			id="runs-heading"
			style="margin: 0;"
		>
			<HudLabel>RUNS</HudLabel>
		</h1>
	</header>

	<GlassPanel style="padding: 24px;">
		<p style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 12px 0;">
			NO RUNS INITIATED. Launch a mission to generate a run.
		</p>
		<p style="font-family: var(--l2-font-sans); font-size: 14px; color: #505050; margin: 0;">
			Select a run from a mission detail page.
			<a
				href="/missions"
				style="color: #7F00FF; text-decoration: none;"
				onmouseenter={(e) => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'underline'; }}
				onmouseleave={(e) => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'none'; }}
			>
				VIEW MISSIONS
			</a>
		</p>
	</GlassPanel>
</section>
