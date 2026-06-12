<script lang="ts">
	import type { AuditEvent } from '$lib/api';

	interface Props {
		event: AuditEvent;
		isNew: boolean;
	}

	let { event, isNew }: Props = $props();

	let expanded = $state(false);

	function getEventTypeColor(eventType: string): string {
		const upper = eventType.toUpperCase();
		if (upper === 'TOOL_CALL' || upper === 'TOOL_RESULT') return '#00E5C8';
		if (upper === 'LLM_CALL' || upper === 'LLM_RESPONSE') return '#7F00FF';
		if (upper === 'ERROR' || upper === 'EXCEPTION') return '#FF0055';
		if (upper === 'RUN_START' || upper === 'RUN_END' || upper === 'CHECKPOINT') return '#00F0FF';
		return '#A0A0A0';
	}

	function isErrorEvent(eventType: string): boolean {
		const upper = eventType.toUpperCase();
		return upper === 'ERROR' || upper === 'EXCEPTION';
	}

	function formatTimestamp(iso: string): string {
		const d = new Date(iso);
		const hh = String(d.getHours()).padStart(2, '0');
		const mm = String(d.getMinutes()).padStart(2, '0');
		const ss = String(d.getSeconds()).padStart(2, '0');
		const ms = String(d.getMilliseconds()).padStart(3, '0');
		return `${hh}:${mm}:${ss}.${ms}`;
	}

	function truncate(text: string, max: number): string {
		if (text.length <= max) return text;
		return text.slice(0, max) + '…';
	}

	let animating = $state(false);

	$effect(() => {
		if (isNew) {
			animating = true;
			const timer = setTimeout(() => {
				animating = false;
			}, 200);
			return () => clearTimeout(timer);
		}
	});

	const typeColor = $derived(getEventTypeColor(event.event_type));
	const rowBg = $derived(isErrorEvent(event.event_type) ? 'rgba(255,0,85,0.04)' : 'transparent');
	const timestamp = $derived(formatTimestamp(event.created_at));
	const displayPayload = $derived(
		expanded ? event.payload : truncate(event.payload, 120)
	);
</script>

<div
	class="sse-row"
	class:sse-row--new={animating}
	style="
		display: grid;
		grid-template-columns: 90px 100px 1fr;
		gap: 12px;
		padding: 4px 12px;
		font-family: var(--l2-font-mono);
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		border-bottom: 1px solid rgba(255,255,255,0.03);
		background: {rowBg};
		cursor: pointer;
	"
	onclick={() => (expanded = !expanded)}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expanded = !expanded; } }}
	role="button"
	tabindex="0"
	aria-expanded={expanded}
	aria-label="Audit event: {event.event_type} at {timestamp}"
>
	<span style="color: rgba(0,240,255,0.5); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
		{timestamp}
	</span>
	<span style="color: {typeColor}; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
		{event.event_type}
	</span>
	<span
		style="
			color: {expanded ? '#E0E0E0' : '#A0A0A0'};
			{expanded ? 'white-space: pre-wrap; word-break: break-all;' : 'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'}
		"
	>
		{displayPayload}
	</span>
</div>

<style>
	.sse-row--new {
		animation: row-enter 150ms cubic-bezier(0.22, 1, 0.36, 1) both;
	}

	@keyframes row-enter {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
