<script lang="ts">
	import type { ProvenanceRecord } from '$lib/api';
	import GlassPanel from './GlassPanel.svelte';
	import HudLabel from './HudLabel.svelte';

	interface Props {
		provenance: ProvenanceRecord | null;
	}

	let { provenance }: Props = $props();

	const rows = $derived.by(() => {
		if (provenance === null) return [];
		return [
			{ label: 'RUN ID', value: provenance.run_id ?? '—' },
			{ label: 'OPERATOR', value: provenance.operator_id ?? '—' },
			{ label: 'SOURCE', value: provenance.source_id ?? '—' },
			{ label: 'SENSITIVITY', value: provenance.sensitivity.toUpperCase() },
			{ label: 'WRITTEN', value: provenance.written_at }
		];
	});
</script>

<!-- ProvenancePanel: expands below wiki page viewer content (max-height CSS transition) -->
<div
	style="overflow: hidden; transition: max-height 200ms ease; max-height: 300px;"
	aria-label="Provenance details"
>
	<GlassPanel style="padding: 16px; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06);">
		<div style="margin-bottom: 8px;">
			<HudLabel>PROVENANCE</HudLabel>
		</div>
		{#if provenance === null}
			<HudLabel>NO PROVENANCE DATA</HudLabel>
		{:else}
			<div style="display: flex; flex-direction: column; gap: 8px;">
				{#each rows as row (row.label)}
					<div style="display: flex; align-items: flex-start; gap: 12px;">
						<span
							style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-2); text-transform: uppercase; letter-spacing: 0.2em; min-width: 96px; flex-shrink: 0;"
						>{row.label}</span>
						<span
							style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-1); word-break: break-all; font-variant-numeric: tabular-nums;"
						>{row.value}</span>
					</div>
				{/each}
			</div>
		{/if}
	</GlassPanel>
</div>
