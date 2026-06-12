<script lang="ts">
	// Surface 4: Model Registry — COCKPIT-06 (read-only)
	// Sections: model registry table, routing policy block, audit visibility block
	// D-017: read-only in v1.0 — no mutation controls rendered.
	import { onMount } from 'svelte';
	import type { ModelEntry, Run } from '$lib/api';
	import { listModels, listMissions, getMission, ApiError } from '$lib/api';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
	import ModelRow from '$lib/components/ModelRow.svelte';

	// ── State ────────────────────────────────────────────────────────────────────
	let models = $state<ModelEntry[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Audit visibility: up to 10 recent runs across up to 3 missions
	let auditRuns = $state<Run[]>([]);
	let auditLoading = $state(true);

	// ── Lifecycle ────────────────────────────────────────────────────────────────
	onMount(async () => {
		// Load model registry
		try {
			const res = await listModels();
			models = res.models;
		} catch (err_) {
			const msg = err_ instanceof Error ? err_.message : String(err_);
			// listModels already degrades 404/503 to an empty list — anything
			// reaching here is a real gateway error (5xx) or a network failure.
			error =
				err_ instanceof ApiError
					? `GATEWAY ERROR ${err_.status} — model registry request failed.`
					: 'GATEWAY OFFLINE — 127.0.0.1:8484 not responding. Start the atlas-gateway process.';
			console.error('[models] listModels error:', msg);
		} finally {
			loading = false;
		}

		// Load audit visibility: last 10 runs across up to 3 missions (T-08-22: cap at 3)
		try {
			const missionsRes = await listMissions(3);
			const missions = missionsRes.missions.slice(0, 3);

			const runArrays = await Promise.all(
				missions.map(async (m) => {
					try {
						const detail = await getMission(m.id);
						return detail.runs;
					} catch {
						return [] as Run[];
					}
				})
			);

			// Flatten, sort by started_at desc, take first 10
			const allRuns: Run[] = runArrays.flat();
			allRuns.sort((a, b) => {
				const ta = a.started_at ?? '';
				const tb = b.started_at ?? '';
				return tb.localeCompare(ta);
			});
			auditRuns = allRuns.slice(0, 10);
		} catch {
			// Non-fatal: audit section shows NO AUDIT DATA
			auditRuns = [];
		} finally {
			auditLoading = false;
		}
	});

	// ── Derived: routing policy ──────────────────────────────────────────────────
	// Group by tier, collect PREFERRED model per tier.
	// Falls back to source field when tier is absent.
	function deriveRoutingPolicy(entries: ModelEntry[]): Array<{ key: string; value: string }> {
		if (entries.length === 0) return [];
		const preferred = new Map<string, string>();
		for (const m of entries) {
			const tier = (m.tier ?? m.source ?? '').trim();
			const policy = (m.policy ?? (m.active ? 'PREFERRED' : 'DISABLED')).toUpperCase();
			if (policy === 'PREFERRED' && tier) {
				const key = `TASK_CLASS_${tier.toUpperCase().replace(/[^A-Z0-9_]/g, '_')}`;
				if (!preferred.has(key)) {
					preferred.set(key, m.model_id);
				}
			}
		}
		return Array.from(preferred.entries()).map(([key, value]) => ({ key, value }));
	}

	const routingPolicy = $derived(deriveRoutingPolicy(models));
</script>

<svelte:head>
	<title>MODEL REGISTRY — ATLAS COCKPIT</title>
</svelte:head>

<section
	aria-labelledby="models-heading"
	style="display: flex; flex-direction: column;"
>
	<!-- Section header: HUD label MODEL REGISTRY + grayed "(MUTATION CONTROLS: PHASE 10)" -->
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
		<h1 id="models-heading" style="margin: 0; padding: 0;">
			<HudLabel>MODEL REGISTRY</HudLabel>
		</h1>
		<span
			style="
				font-family: var(--l2-font-sans);
				font-size: 12px;
				font-weight: 400;
				color: rgba(255,255,255,0.20);
				letter-spacing: 0.05em;
			"
		>
			(MUTATION CONTROLS: PHASE 10)
		</span>
	</header>

	<!-- Load error banner (gateway offline) -->
	{#if error}
		<p
			style="
				font-family: var(--l2-font-mono);
				font-size: 12px;
				color: #FF0055;
				margin: 0 0 16px 0;
				padding: 8px 12px;
				background: rgba(255,0,85,0.08);
				border: 1px solid rgba(255,0,85,0.20);
				border-radius: 2px;
				letter-spacing: 0.05em;
			"
		>
			{error}
		</p>
	{/if}

	<!-- Model Registry Table in GlassPanel with topo glow on hover -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		onmouseenter={() => document.documentElement.setAttribute('data-topo-glow', 'info')}
		onmouseleave={() => document.documentElement.removeAttribute('data-topo-glow')}
	>
		<GlassPanel style="overflow: hidden;">
			{#if loading}
				<p
					style="
						font-family: var(--l2-font-mono);
						font-size: 12px;
						text-transform: uppercase;
						letter-spacing: 0.1em;
						color: var(--l2-fg-3);
						margin: 0;
						padding: 16px 12px;
					"
				>
					LOADING...
				</p>
			{:else if models.length === 0}
				<!-- Empty state per spec -->
				<div style="padding: 16px 12px;">
					<HudLabel>MODEL REGISTRY EMPTY.</HudLabel>
					<p
						style="
							font-family: var(--l2-font-sans);
							font-size: 16px;
							font-weight: 400;
							color: var(--l2-fg-2);
							margin: 8px 0 0 0;
						"
					>
						Ensure the Phase 7 gateway is running on 127.0.0.1:8484.
					</p>
				</div>
			{:else}
				<!-- Data table: MODEL ID | PROVIDER | TIER | HEALTH | POLICY -->
				<table style="width: 100%; border-collapse: collapse;">
					<!-- Header row -->
					<thead>
						<tr style="background: #050505; border-bottom: 1px solid rgba(255,255,255,0.05);">
							<th
								style="text-align: left; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); padding: 4px 12px; font-weight: 400; width: 200px;"
							>MODEL ID</th>
							<th
								style="text-align: left; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); padding: 4px 12px; font-weight: 400; width: 140px;"
							>PROVIDER</th>
							<th
								style="text-align: left; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); padding: 4px 12px; font-weight: 400; width: 140px;"
							>TIER</th>
							<th
								style="text-align: left; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); padding: 4px 12px; font-weight: 400; width: 120px;"
							>HEALTH</th>
							<th
								style="text-align: left; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); padding: 4px 12px; font-weight: 400; width: 120px;"
							>POLICY</th>
						</tr>
					</thead>
					<tbody>
						{#each models as model (model.model_id)}
							<ModelRow {model} />
						{/each}
					</tbody>
				</table>
			{/if}
		</GlassPanel>
	</div>

	<!-- Routing Policy block -->
	<div style="margin-top: 24px;">
		<GlassPanel style="padding: 16px;">
			<div style="margin-bottom: 12px;">
				<HudLabel>ROUTING POLICY</HudLabel>
			</div>
			{#if routingPolicy.length === 0}
				<span
					style="
						font-family: var(--l2-font-mono);
						font-size: 12px;
						color: rgba(255,255,255,0.40);
					"
				>
					NO POLICY CONFIGURED
				</span>
			{:else}
				<div style="display: flex; flex-direction: column; gap: 6px;">
					{#each routingPolicy as entry (entry.key)}
						<span
							style="
								font-family: var(--l2-font-mono);
								font-size: 12px;
								color: #A0A0A0;
								font-variant-numeric: tabular-nums;
							"
						>
							{entry.key}: {entry.value}
						</span>
					{/each}
				</div>
			{/if}
		</GlassPanel>
	</div>

	<!-- Audit Visibility block -->
	<div style="margin-top: 24px;">
		<GlassPanel style="padding: 16px;">
			<div style="margin-bottom: 12px;">
				<HudLabel>AUDIT VISIBILITY</HudLabel>
			</div>

			{#if auditLoading}
				<span
					style="
						font-family: var(--l2-font-mono);
						font-size: 12px;
						color: var(--l2-fg-3);
					"
				>
					LOADING...
				</span>
			{:else if auditRuns.length === 0}
				<span
					style="
						font-family: var(--l2-font-mono);
						font-size: 12px;
						color: rgba(255,255,255,0.40);
					"
				>
					NO AUDIT DATA
				</span>
			{:else}
				<div style="display: flex; flex-direction: column; gap: 6px;">
					{#each auditRuns as run (run.id)}
						<div style="display: flex; align-items: center; gap: 6px;">
							<!-- RUN ID: linked to /runs/{id} -->
							<a
								href="/runs/{run.id}"
								style="
									font-family: var(--l2-font-mono);
									font-size: 12px;
									color: #A0A0A0;
									text-decoration: none;
									font-variant-numeric: tabular-nums;
								"
								onmouseenter={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = '#00F0FF'; }}
								onmouseleave={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = '#A0A0A0'; }}
							>
								{run.id}
							</a>
							<span
								style="
									font-family: var(--l2-font-mono);
									font-size: 12px;
									color: #505050;
								"
							>
								→
							</span>
							<!-- MODEL ID: session_id as model session proxy; "—" if absent -->
							<span
								style="
									font-family: var(--l2-font-mono);
									font-size: 12px;
									color: #505050;
									font-variant-numeric: tabular-nums;
								"
							>
								{run.session_id ?? '—'}
							</span>
						</div>
					{/each}
				</div>
			{/if}

			<!-- VIEW ALL IN RUNS ghost link -->
			<div style="margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
				<a
					href="/runs"
					style="
						font-family: var(--l2-font-mono);
						font-size: 12px;
						text-transform: uppercase;
						letter-spacing: 0.1em;
						color: #505050;
						text-decoration: none;
						background: transparent;
						border: 1px solid rgba(255,255,255,0.08);
						border-radius: 2px;
						padding: 6px 12px;
						transition: color 80ms ease, background 80ms ease, border-color 80ms ease;
						display: inline-block;
					"
					onmouseenter={(e) => {
						const el = e.currentTarget as HTMLAnchorElement;
						el.style.color = '#E0E0E0';
						el.style.background = 'rgba(255,255,255,0.08)';
						el.style.borderColor = 'rgba(255,255,255,0.30)';
					}}
					onmouseleave={(e) => {
						const el = e.currentTarget as HTMLAnchorElement;
						el.style.color = '#505050';
						el.style.background = 'transparent';
						el.style.borderColor = 'rgba(255,255,255,0.08)';
					}}
				>
					VIEW ALL IN RUNS
				</a>
			</div>
		</GlassPanel>
	</div>
</section>
