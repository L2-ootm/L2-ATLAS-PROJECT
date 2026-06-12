<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/stores';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import SseEventRow from '$lib/components/SseEventRow.svelte';
	import LiveBadge from '$lib/components/LiveBadge.svelte';
	import RunTimeline from '$lib/components/RunTimeline.svelte';
	import { getRun, getRunEvents } from '$lib/api';
	import type { Run, AuditEvent } from '$lib/api';

	const GATEWAY = 'http://127.0.0.1:8484';

	// ── URL param ─────────────────────────────────────────────────────────────
	let id = $derived($page.params.id ?? '');

	// ── State ─────────────────────────────────────────────────────────────────
	let run: Run | null = $state(null);
	let events: AuditEvent[] = $state([]);
	let loading = $state(true);
	let error: string | null = $state(null);
	let sseConnected = $state(false);
	let showCancelConfirm = $state(false);
	let cancelError: string | null = $state(null);
	let newEventIds = $state(new Set<number>());
	let streamError: string | null = $state(null);
	let filterType = $state('ALL');

	// ── DOM refs ──────────────────────────────────────────────────────────────
	let scrollContainer: HTMLDivElement | undefined = $state(undefined);

	// ── SSE ref ───────────────────────────────────────────────────────────────
	let sseSource: EventSource | null = null;
	let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	let reconnectAttempted = false;

	// ── Derived ───────────────────────────────────────────────────────────────
	function checkIsActive(r: Run | null): boolean {
		if (!r) return false;
		const s = r.status.toUpperCase();
		return s === 'RUNNING' || s === 'PENDING';
	}

	function checkIsTerminal(r: Run | null): boolean {
		if (!r) return false;
		const s = r.status.toUpperCase();
		return s === 'SUCCEEDED' || s === 'FAILED' || s === 'PARTIAL';
	}

	function getTimelineProgress(r: Run | null): number {
		if (!r) return 0;
		const s = r.status.toUpperCase();
		if (s === 'RUNNING' || s === 'PENDING') return 50;
		if (s === 'SUCCEEDED' || s === 'FAILED') return 100;
		return 0;
	}

	const isActive = $derived(checkIsActive(run));
	const isTerminal = $derived(checkIsTerminal(run));
	const elapsedText = $derived(getElapsedText());
	const timelineProgress = $derived(getTimelineProgress(run));

	const distinctEventTypes = $derived(
		['ALL', ...Array.from(new Set(events.map(e => e.event_type.toUpperCase())))]
	);

	const filteredEvents = $derived(
		filterType === 'ALL' ? events : events.filter(e => e.event_type.toUpperCase() === filterType)
	);

	// ── Helpers ───────────────────────────────────────────────────────────────
	function getElapsedText(): string {
		if (!run) return '';
		const start = new Date(run.started_at).getTime();
		const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
		const diffMs = end - start;
		if (diffMs < 0) return '0.0s';
		const diffSec = diffMs / 1000;
		if (diffSec < 60) return `${diffSec.toFixed(1)}s`;
		const m = Math.floor(diffSec / 60);
		const s = Math.floor(diffSec % 60);
		return `${m}m ${s}s`;
	}

	function formatTs(iso: string | null): string {
		if (!iso) return '—';
		const d = new Date(iso);
		return d.toLocaleString();
	}

	function isAtBottom(): boolean {
		if (!scrollContainer) return true;
		const { scrollHeight, scrollTop, clientHeight } = scrollContainer;
		return scrollHeight - scrollTop - clientHeight < 100;
	}

	function scrollToBottom(): void {
		if (!scrollContainer) return;
		requestAnimationFrame(() => {
			if (scrollContainer) {
				scrollContainer.scrollTop = scrollContainer.scrollHeight;
			}
		});
	}

	function addEvent(evt: AuditEvent): void {
		const wasAtBottom = isAtBottom();

		// Push new event
		events = [...events, evt];

		// DOM cap: hard limit at 500 rows
		if (events.length > 500) {
			events = events.slice(events.length - 500);
		}

		// Mark as new for animation
		newEventIds = new Set([...newEventIds, evt.rowid]);
		setTimeout(() => {
			newEventIds = new Set([...newEventIds].filter(id => id !== evt.rowid));
		}, 300);

		// Auto-scroll if at bottom
		if (wasAtBottom) {
			scrollToBottom();
		}
	}

	// ── SSE connection ────────────────────────────────────────────────────────
	function openSse(runId: string): void {
		closeSse();
		reconnectAttempted = false;
		streamError = null;

		const source = new EventSource(`${GATEWAY}/v1/runs/${encodeURIComponent(runId)}/stream`);
		sseSource = source;

		source.onopen = () => {
			sseConnected = true;
			streamError = null;
		};

		source.addEventListener('audit', (evt: MessageEvent) => {
			try {
				const data = JSON.parse(evt.data) as AuditEvent;
				addEvent(data);
			} catch {
				// ignore malformed events
			}
		});

		source.addEventListener('end', (evt: MessageEvent) => {
			sseConnected = false;
			source.close();
			sseSource = null;
			// Update run status from end event
			try {
				const endData = JSON.parse(evt.data) as { status: string };
				if (run && endData.status) {
					run = { ...run, status: endData.status, finished_at: run.finished_at ?? new Date().toISOString() };
				}
			} catch {
				// status unknown — re-fetch run
				getRun(runId).then(r => { run = r.run; }).catch(() => {});
			}
		});

		source.addEventListener('error', (evt: MessageEvent) => {
			// Gateway-level error event
			try {
				const errData = JSON.parse(evt.data) as { error: string };
				streamError = errData.error ?? 'STREAM ERROR';
			} catch {
				streamError = 'STREAM ERROR — unknown gateway error';
			}
		});

		source.onerror = () => {
			sseConnected = false;
			source.close();
			sseSource = null;

			if (!reconnectAttempted) {
				reconnectAttempted = true;
				streamError = 'STREAM INTERRUPTED — reconnecting in 2s. If this persists, check gateway health.';
				reconnectTimer = setTimeout(() => {
					// Single retry
					const retrySource = new EventSource(`${GATEWAY}/v1/runs/${encodeURIComponent(runId)}/stream`);
					sseSource = retrySource;

					retrySource.onopen = () => {
						sseConnected = true;
						streamError = null;
					};

					retrySource.addEventListener('audit', (e: MessageEvent) => {
						try {
							const data = JSON.parse(e.data) as AuditEvent;
							addEvent(data);
						} catch {
							// ignore
						}
					});

					retrySource.addEventListener('end', (e: MessageEvent) => {
						sseConnected = false;
						retrySource.close();
						sseSource = null;
						try {
							const endData = JSON.parse(e.data) as { status: string };
							if (run && endData.status) {
								run = { ...run, status: endData.status, finished_at: run.finished_at ?? new Date().toISOString() };
							}
						} catch {
							getRun(runId).then(r => { run = r.run; }).catch(() => {});
						}
					});

					retrySource.onerror = () => {
						sseConnected = false;
						retrySource.close();
						sseSource = null;
						streamError = 'STREAM INTERRUPTED — reconnecting in 2s. If this persists, check gateway health.';
					};
				}, 2000);
			}
		};
	}

	function closeSse(): void {
		if (reconnectTimer !== null) {
			clearTimeout(reconnectTimer);
			reconnectTimer = null;
		}
		if (sseSource) {
			sseSource.close();
			sseSource = null;
		}
		sseConnected = false;
	}

	// ── Load complete audit trail for finished runs ───────────────────────────
	async function loadFullTrail(runId: string): Promise<void> {
		let cursor: number | undefined = undefined;
		let allEvents: AuditEvent[] = [];
		let iterations = 0;
		const MAX_ITERATIONS = 20; // guard: up to 1000 * 20 = 20000 events

		while (iterations < MAX_ITERATIONS) {
			const result = await getRunEvents(runId, cursor);
			allEvents = [...allEvents, ...result.events];
			if (!result.next_cursor || result.events.length === 0) break;
			cursor = result.next_cursor;
			iterations++;
		}

		events = allEvents.slice(-500); // apply DOM cap on initial load too
		scrollToBottom();
	}

	// ── CANCEL RUN ────────────────────────────────────────────────────────────
	async function confirmCancel(): Promise<void> {
		if (!run) return;
		cancelError = null;
		try {
			const resp = await fetch(`${GATEWAY}/v1/missions/${encodeURIComponent(run.mission_id)}/cancel`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});
			if (!resp.ok) {
				const text = await resp.text().catch(() => resp.statusText);
				cancelError = `CANCEL FAILED — ${text}`;
				return;
			}
			showCancelConfirm = false;
			// Optimistically update run status; will be corrected by SSE end event
			if (run) {
				run = { ...run, status: 'PARTIAL' };
			}
			closeSse();
		} catch (e) {
			cancelError = `CANCEL FAILED — ${e instanceof Error ? e.message : String(e)}`;
		}
	}

	// ── EXPORT JSONL ──────────────────────────────────────────────────────────
	async function exportJsonl(): Promise<void> {
		if (!run) return;
		// Fetch all events via paginated API
		let cursor: number | undefined = undefined;
		let allEvents: AuditEvent[] = [];
		let iterations = 0;
		const MAX_ITERATIONS = 100;

		while (iterations < MAX_ITERATIONS) {
			const result = await getRunEvents(run.id, cursor);
			allEvents = [...allEvents, ...result.events];
			if (!result.next_cursor || result.events.length === 0) break;
			cursor = result.next_cursor;
			iterations++;
		}

		const jsonl = allEvents.map(e => JSON.stringify(e)).join('\n');
		const blob = new Blob([jsonl], { type: 'application/x-ndjson' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `run-${run.id}-audit.jsonl`;
		a.click();
		URL.revokeObjectURL(url);
	}

	// ── Mount / Destroy ───────────────────────────────────────────────────────
	onMount(async () => {
		const runId: string = $page.params.id ?? '';
		if (!runId) {
			error = 'INVALID RUN ID — missing parameter';
			loading = false;
			return;
		}
		try {
			const result = await getRun(runId);
			run = result.run;

			const status = run.status.toUpperCase();
			if (status === 'RUNNING' || status === 'PENDING') {
				openSse(runId);
			} else {
				await loadFullTrail(runId);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});

	onDestroy(() => {
		closeSse();
	});
</script>

<svelte:head>
	<title>RUN {id} — ATLAS COCKPIT</title>
</svelte:head>

{#if loading}
	<div style="padding: 24px;">
		<span style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); text-transform: uppercase; letter-spacing: 0.2em;">
			LOADING RUN...
		</span>
	</div>
{:else if error}
	<div style="padding: 24px;">
		<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055; text-transform: uppercase; letter-spacing: 0.1em;">
			{error}
		</span>
	</div>
{:else if run}
	<!-- Run header -->
	<div style="margin-bottom: 16px;">
		<!-- Section header -->
		<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px; margin-bottom: 16px;">
			<HudLabel>RUN DETAIL</HudLabel>
		</div>

		<!-- Header row: ID, mission link, status, timestamps, elapsed, LIVE badge -->
		<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 12px;">
			<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #A0A0A0; font-variant-numeric: tabular-nums;">
				{run.id}
			</span>

			<a
				href="/missions/{run.mission_id}"
				style="font-family: var(--l2-font-sans); font-size: 14px; font-weight: 400; color: #7F00FF; text-decoration: none;"
				onmouseenter={(e) => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'underline'; }}
				onmouseleave={(e) => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'none'; }}
			>
				{run.mission_id}
			</a>

			<StatusBadge status={run.status} />

			<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums;">
				STARTED {formatTs(run.started_at)}
			</span>

			{#if run.finished_at}
				<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums;">
					FINISHED {formatTs(run.finished_at)}
				</span>
			{/if}

			<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #E0E0E0; font-variant-numeric: tabular-nums;">
				{elapsedText}
			</span>

			<LiveBadge connected={sseConnected} />
		</div>

		<!-- Timeline -->
		<div style="margin-bottom: 16px;">
			<RunTimeline status={run.status} progress={timelineProgress} />
		</div>
	</div>

	<!-- Controls bar -->
	<div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap;">
		{#if isActive}
			<button
				style="
					background: rgba(255,0,85,0.15);
					border: 1px solid rgba(255,0,85,0.40);
					font-family: var(--l2-font-mono);
					font-size: 12px;
					text-transform: uppercase;
					color: #FF0055;
					padding: 6px 12px;
					border-radius: 2px;
					cursor: pointer;
					letter-spacing: 0.1em;
				"
				onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,0,85,0.25)'; }}
				onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,0,85,0.15)'; }}
				onclick={() => { showCancelConfirm = true; }}
			>
				CANCEL RUN
			</button>
		{/if}

		{#if isTerminal}
			<button
				style="
					background: rgba(20,20,20,0.60);
					border: 1px solid rgba(255,255,255,0.08);
					font-family: var(--l2-font-sans);
					font-size: 14px;
					font-weight: 600;
					letter-spacing: 0.05em;
					color: #A0A0A0;
					padding: 6px 12px;
					border-radius: 2px;
					cursor: pointer;
				"
				onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)'; (e.currentTarget as HTMLButtonElement).style.color = '#E0E0E0'; }}
				onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(20,20,20,0.60)'; (e.currentTarget as HTMLButtonElement).style.color = '#A0A0A0'; }}
				onclick={exportJsonl}
			>
				EXPORT JSONL
			</button>
		{/if}

		<!-- Filter select -->
		<select
			style="
				background: rgba(255,255,255,0.05);
				border: 1px solid rgba(255,255,255,0.08);
				font-family: var(--l2-font-sans);
				font-size: 14px;
				font-weight: 600;
				letter-spacing: 0.05em;
				color: #A0A0A0;
				padding: 5px 10px;
				border-radius: 2px;
				cursor: pointer;
				outline: none;
			"
			bind:value={filterType}
			onfocus={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = '#7F00FF'; (e.currentTarget as HTMLSelectElement).style.boxShadow = '0 0 0 2px rgba(127,0,255,0.20)'; }}
			onblur={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = 'rgba(255,255,255,0.08)'; (e.currentTarget as HTMLSelectElement).style.boxShadow = 'none'; }}
		>
			{#each distinctEventTypes as type}
				<option value={type} style="background: #0A0A0A; color: #E0E0E0;">{type}</option>
			{/each}
		</select>
	</div>

	<!-- Cancel confirmation banner -->
	{#if showCancelConfirm}
		<div
			style="
				background: rgba(255,0,85,0.08);
				border: 1px solid rgba(255,0,85,0.30);
				padding: 12px 16px;
				border-radius: 2px;
				margin-bottom: 8px;
			"
		>
			<p style="font-family: var(--l2-font-sans); font-size: 14px; font-weight: 400; color: #E0E0E0; margin: 0 0 12px 0;">
				CONFIRM CANCEL: This will halt the active run and mark it PARTIAL. Action is irreversible.
			</p>
			{#if cancelError}
				<p style="font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055; margin: 0 0 8px 0; text-transform: uppercase;">
					{cancelError}
				</p>
			{/if}
			<div style="display: flex; gap: 8px;">
				<button
					style="
						background: rgba(255,0,85,0.15);
						border: 1px solid rgba(255,0,85,0.40);
						font-family: var(--l2-font-mono);
						font-size: 12px;
						text-transform: uppercase;
						color: #FF0055;
						padding: 6px 12px;
						border-radius: 2px;
						cursor: pointer;
						letter-spacing: 0.1em;
					"
					onclick={confirmCancel}
				>
					CONFIRM CANCEL
				</button>
				<button
					style="
						background: rgba(20,20,20,0.60);
						border: 1px solid rgba(255,255,255,0.08);
						font-family: var(--l2-font-sans);
						font-size: 14px;
						font-weight: 600;
						letter-spacing: 0.05em;
						color: #A0A0A0;
						padding: 6px 12px;
						border-radius: 2px;
						cursor: pointer;
					"
					onclick={() => { showCancelConfirm = false; cancelError = null; }}
				>
					KEEP RUN
				</button>
			</div>
		</div>
	{/if}

	<!-- SSE stream container -->
	<div style="margin-bottom: 8px;">
		<HudLabel>AUDIT STREAM</HudLabel>
	</div>

	<div
		bind:this={scrollContainer}
		role="log"
		aria-live="polite"
		aria-label="Audit event stream"
		style="
			height: calc(100vh - 200px);
			overflow-y: auto;
			background: #0A0A0A;
			border: 1px solid rgba(255,255,255,0.08);
			{sseConnected ? 'border-left: 2px solid #00F0FF;' : ''}
			border-radius: 2px;
		"
	>
		{#if streamError}
			<div style="padding: 8px 12px; font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid rgba(255,0,85,0.20);">
				{streamError}
			</div>
		{/if}

		{#if filteredEvents.length === 0 && !sseConnected && !isActive}
			<div style="padding: 24px; text-align: center;">
				<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; text-transform: uppercase; letter-spacing: 0.2em;">
					STREAM INACTIVE. Run has not started.
				</span>
			</div>
		{/if}

		{#each filteredEvents as evt (evt.rowid)}
			<SseEventRow event={evt} isNew={newEventIds.has(evt.rowid)} />
		{/each}
	</div>
{/if}
