<script lang="ts">
	interface Props {
		connected: boolean;
	}

	let { connected }: Props = $props();
</script>

{#if connected}
	<span
		class="live-badge"
		role="status"
		aria-label="Live stream connected"
		style="
			font-family: var(--l2-font-mono);
			font-size: 12px;
			font-weight: 400;
			letter-spacing: 0.1em;
			text-transform: uppercase;
			color: #00F0FF;
			background: rgba(0,240,255,0.12);
			border: 1px solid rgba(0,240,255,0.35);
			border-radius: 4px;
			padding: 4px 8px;
			display: inline-block;
		"
	>
		LIVE
	</span>
{/if}

<style>
	.live-badge {
		animation: live-pulse 1.5s infinite;
	}

	@keyframes live-pulse {
		0% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
		100% {
			opacity: 1;
		}
	}
</style>
