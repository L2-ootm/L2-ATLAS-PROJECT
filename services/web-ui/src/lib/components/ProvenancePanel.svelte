<script lang="ts">
	import type { ProvenanceRecord } from '$lib/api';
	import GlassPanel from './GlassPanel.svelte';
	import HudLabel from './HudLabel.svelte';
	import StatusBadge from './StatusBadge.svelte';

	interface Props {
		provenance: ProvenanceRecord | null;
	}

	let { provenance }: Props = $props();

	function lintStatusVariant(lint: string): string {
		const upper = lint.toUpperCase();
		if (upper === 'PASS' || upper === 'PASSED' || upper === 'OK') return 'SUCCEEDED';
		if (upper === 'FAIL' || upper === 'FAILED' || upper === 'ERROR') return 'FAILED';
		return 'PARTIAL';
	}
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
				<div style="display: flex; align-items: flex-start; gap: 12px;">
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-2); text-transform: uppercase; letter-spacing: 0.2em; min-width: 96px; flex-shrink: 0;"
					>SHA256</span>
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-1); word-break: break-all; font-variant-numeric: tabular-nums;"
					>{provenance.sha256}</span>
				</div>
				<div style="display: flex; align-items: center; gap: 12px;">
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-2); text-transform: uppercase; letter-spacing: 0.2em; min-width: 96px; flex-shrink: 0;"
					>INGESTED</span>
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); font-variant-numeric: tabular-nums;"
					>{provenance.ingested_at}</span>
				</div>
				<div style="display: flex; align-items: center; gap: 12px;">
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-2); text-transform: uppercase; letter-spacing: 0.2em; min-width: 96px; flex-shrink: 0;"
					>LAYER</span>
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-1); font-variant-numeric: tabular-nums;"
					>{provenance.layer}</span>
				</div>
				<div style="display: flex; align-items: center; gap: 12px;">
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-2); text-transform: uppercase; letter-spacing: 0.2em; min-width: 96px; flex-shrink: 0;"
					>LINT STATUS</span>
					<StatusBadge status={lintStatusVariant(provenance.lint_status)} />
				</div>
			</div>
		{/if}
	</GlassPanel>
</div>
