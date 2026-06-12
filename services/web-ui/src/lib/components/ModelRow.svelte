<script lang="ts">
	// ModelRow — single row in the model registry table
	// Columns: MODEL ID | PROVIDER | TIER | HEALTH | POLICY
	// Read-only: no edit controls, no toggles.
	import type { ModelEntry } from '$lib/api';
	import StatusBadge from '$lib/components/StatusBadge.svelte';

	interface Props {
		model: ModelEntry;
	}

	let { model }: Props = $props();

	/**
	 * Map model_registry `health` field to StatusBadge status string.
	 * DB values: "healthy" | "degraded" | "down"
	 * StatusBadge variants: SUCCEEDED | PARTIAL | FAILED
	 * Falls back to SUCCEEDED when field absent (active=1 means healthy).
	 */
	function healthToStatus(health: string | undefined, active: number): string {
		if (!health) {
			// Derive from `active` flag when health field absent
			return active ? 'SUCCEEDED' : 'FAILED';
		}
		switch (health.toLowerCase()) {
			case 'healthy':
				return 'SUCCEEDED';
			case 'degraded':
				return 'PARTIAL';
			case 'down':
				return 'FAILED';
			default:
				return 'PARTIAL';
		}
	}

	/**
	 * Policy badge color per spec:
	 *   PREFERRED → #00FF94
	 *   FALLBACK  → #FFD600
	 *   DISABLED  → #505050
	 *   (default) → #A0A0A0
	 */
	function policyColor(policy: string | undefined): string {
		switch ((policy ?? '').toUpperCase()) {
			case 'PREFERRED':
				return '#00FF94';
			case 'FALLBACK':
				return '#FFD600';
			case 'DISABLED':
				return '#505050';
			default:
				return '#A0A0A0';
		}
	}

	const healthStatus = $derived(healthToStatus(model.health, model.active));
	const policyLabel = $derived((model.policy ?? (model.active ? 'PREFERRED' : 'DISABLED')).toUpperCase());
	const tierLabel = $derived((model.tier ?? model.source ?? '—').toUpperCase());
</script>

<tr
	style="
		min-height: 48px;
		border-bottom: 1px solid rgba(255,255,255,0.05);
		transition: background 80ms ease;
	"
	onmouseenter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'rgba(255,255,255,0.03)'; }}
	onmouseleave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'; }}
>
	<!-- MODEL ID -->
	<td
		style="
			font-family: var(--l2-font-mono);
			font-size: 12px;
			color: #A0A0A0;
			padding: 4px 12px;
			height: 48px;
			font-variant-numeric: tabular-nums;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
			max-width: 200px;
		"
	>
		{model.model_id}
	</td>

	<!-- PROVIDER -->
	<td
		style="
			font-family: var(--l2-font-mono);
			font-size: 12px;
			color: #A0A0A0;
			padding: 4px 12px;
			height: 48px;
		"
	>
		{model.provider}
	</td>

	<!-- TIER (derived from tier field or source) -->
	<td
		style="
			font-family: var(--l2-font-mono);
			font-size: 12px;
			color: #A0A0A0;
			padding: 4px 12px;
			height: 48px;
		"
	>
		{tierLabel}
	</td>

	<!-- HEALTH → StatusBadge -->
	<td style="padding: 4px 12px; height: 48px;">
		<StatusBadge status={healthStatus} />
	</td>

	<!-- POLICY: text badge, mono 12px, color per spec -->
	<td style="padding: 4px 12px; height: 48px;">
		<span
			style="
				font-family: var(--l2-font-mono);
				font-size: 12px;
				text-transform: uppercase;
				letter-spacing: 0.1em;
				color: {policyColor(model.policy ?? (model.active ? 'PREFERRED' : 'DISABLED'))};
			"
		>
			{policyLabel}
		</span>
	</td>
</tr>
