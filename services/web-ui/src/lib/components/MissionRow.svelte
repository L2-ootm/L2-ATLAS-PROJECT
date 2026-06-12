<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import type { Mission } from '$lib/api';

	interface Props {
		mission: Mission;
		flash?: boolean;
	}

	let { mission, flash = false }: Props = $props();

	function formatDate(iso: string): string {
		try {
			return new Date(iso).toLocaleString('en-CA', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit',
				hour12: false
			});
		} catch {
			return iso;
		}
	}
</script>

<tr
	class="mission-row"
	class:flash
	onclick={() => (window.location.href = `/missions/${mission.id}`)}
	style="
		cursor: pointer;
		min-height: 48px;
		height: 48px;
		border-bottom: 1px solid rgba(255,255,255,0.05);
		transition: background 80ms ease;
	"
	tabindex="0"
	aria-label="Mission {mission.id}: {mission.title}"
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			window.location.href = `/missions/${mission.id}`;
		}
	}}
>
	<td
		style="
			padding: 0 12px;
			font-family: var(--l2-font-mono);
			font-size: 12px;
			color: #A0A0A0;
			font-variant-numeric: tabular-nums;
			width: 90px;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		"
	>
		{mission.id.slice(0, 8)}
	</td>
	<td
		style="
			padding: 0 12px;
			font-family: var(--l2-font-sans);
			font-size: 16px;
			font-weight: 400;
			color: #E0E0E0;
		"
	>
		{mission.title}
	</td>
	<td
		style="
			padding: 0 12px;
			width: 120px;
			text-align: center;
		"
	>
		<StatusBadge status={mission.status} />
	</td>
	<td
		style="
			padding: 0 12px;
			font-family: var(--l2-font-mono);
			font-size: 12px;
			color: #505050;
			font-variant-numeric: tabular-nums;
			width: 160px;
			white-space: nowrap;
		"
	>
		{formatDate(mission.created_at)}
	</td>
	<td
		style="
			padding: 0 12px;
			width: 80px;
			text-align: right;
		"
	>
		<button
			onclick={(e) => {
				e.stopPropagation();
				window.location.href = `/missions/${mission.id}`;
			}}
			aria-label="View mission {mission.id}"
			style="
				background: none;
				border: none;
				cursor: pointer;
				color: #505050;
				display: inline-flex;
				align-items: center;
				justify-content: center;
				padding: 4px;
				border-radius: 2px;
				transition: color 80ms ease;
				outline-offset: 2px;
			"
			onmouseenter={(e) => {
				(e.currentTarget as HTMLElement).style.color = '#A0A0A0';
			}}
			onmouseleave={(e) => {
				(e.currentTarget as HTMLElement).style.color = '#505050';
			}}
			onfocus={(e) => {
				(e.currentTarget as HTMLElement).style.outline = '2px solid rgba(127,0,255,0.6)';
			}}
			onblur={(e) => {
				(e.currentTarget as HTMLElement).style.outline = 'none';
			}}
		>
			<ExternalLink size={16} strokeWidth={1.5} />
		</button>
	</td>
</tr>

<style>
	.mission-row:hover {
		background: rgba(255,255,255,0.03);
	}

	.mission-row:focus {
		outline: 2px solid rgba(127, 0, 255, 0.6);
		outline-offset: -2px;
	}

	@keyframes flash-border {
		0% {
			box-shadow: inset 2px 0 0 #7f00ff;
		}
		100% {
			box-shadow: inset 2px 0 0 transparent;
		}
	}

	.mission-row.flash {
		animation: flash-border 400ms ease-out forwards;
	}
</style>
