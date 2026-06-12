<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { ChevronLeft, ExternalLink } from '@lucide/svelte';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { getMission, startRun } from '$lib/api';
	import type { Mission, Run } from '$lib/api';

	const mission_id = $derived($page.params.id ?? '');

	let mission: Mission | null = $state(null);
	let runs: Run[] = $state([]);
	let loading = $state(true);
	let error: string | null = $state(null);
	let launching = $state(false);
	let launchError: string | null = $state(null);

	onMount(async () => {
		await loadMission();
	});

	async function loadMission() {
		loading = true;
		error = null;
		try {
			const result = await getMission(mission_id);
			mission = result.mission;
			runs = result.runs;
		} catch (err) {
			if (err instanceof TypeError) {
				error =
					'GATEWAY OFFLINE — 127.0.0.1:8484 not responding. Start the atlas-gateway process.';
			} else if (err instanceof Error) {
				error = err.message;
			} else {
				error = 'Failed to load mission.';
			}
		} finally {
			loading = false;
		}
	}

	async function handleLaunchRun() {
		if (launching || !mission) return;
		launching = true;
		launchError = null;
		try {
			const result = await startRun(mission.id);
			window.location.href = `/runs/${result.run.id}`;
		} catch (err) {
			if (err instanceof Error) {
				launchError = `RUN LAUNCH FAILED — ${err.message}. Mission status reverted.`;
			} else {
				launchError = 'RUN LAUNCH FAILED — Unknown error. Mission status reverted.';
			}
			launching = false;
		}
	}

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

<svelte:head>
	<title>
		{mission ? `MISSION ${mission.id.slice(0, 8)} — ATLAS COCKPIT` : 'MISSION DETAIL — ATLAS COCKPIT'}
	</title>
</svelte:head>

<section aria-labelledby="mission-detail-heading">
	<!-- Section header -->
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
		<div style="display: flex; align-items: center; gap: 12px;">
			<a
				href="/missions"
				style="
					display: inline-flex;
					align-items: center;
					gap: 4px;
					color: #A0A0A0;
					font-family: var(--l2-font-sans);
					font-size: 14px;
					font-weight: 600;
					text-decoration: none;
					transition: color 80ms ease;
					outline-offset: 2px;
				"
				onmouseenter={(e) => {
					(e.currentTarget as HTMLElement).style.color = '#E0E0E0';
				}}
				onmouseleave={(e) => {
					(e.currentTarget as HTMLElement).style.color = '#A0A0A0';
				}}
				onfocus={(e) => {
					(e.currentTarget as HTMLElement).style.outline = '2px solid rgba(127,0,255,0.6)';
				}}
				onblur={(e) => {
					(e.currentTarget as HTMLElement).style.outline = 'none';
				}}
			>
				<ChevronLeft size={16} strokeWidth={1.5} />
				MISSIONS
			</a>
			<span style="color: rgba(255,255,255,0.2);">/</span>
			<h1 id="mission-detail-heading" style="margin: 0;">
				<HudLabel>MISSION DETAIL</HudLabel>
			</h1>
		</div>
	</header>

	{#if loading}
		<GlassPanel style="padding: 48px; display: flex; justify-content: center; align-items: center;">
			<HudLabel>LOADING...</HudLabel>
		</GlassPanel>
	{:else if error}
		<GlassPanel style="padding: 24px;">
			<span
				style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: #FF0055;"
			>
				{error}
			</span>
		</GlassPanel>
	{:else if mission}
		<!-- Mission metadata panel -->
		<GlassPanel style="padding: 24px; margin-bottom: 16px;">
			<div style="display: flex; flex-direction: column; gap: 16px;">
				<!-- ID row -->
				<div style="display: flex; align-items: center; gap: 12px;">
					<span
						style="font-family: var(--l2-font-mono); font-size: 12px; color: #A0A0A0; font-variant-numeric: tabular-nums;"
					>
						{mission.id}
					</span>
					<StatusBadge status={mission.status} />
				</div>

				<!-- Title -->
				<h2
					style="margin: 0; font-family: var(--l2-font-sans); font-size: 16px; font-weight: 600; color: #E0E0E0; line-height: 1.4;"
				>
					{mission.title}
				</h2>

				<!-- Intent body -->
				{#if mission.intent}
					<p
						style="margin: 0; font-family: var(--l2-font-sans); font-size: 16px; font-weight: 400; color: #A0A0A0; line-height: 1.5;"
					>
						{mission.intent}
					</p>
				{/if}

				<!-- Timestamps -->
				<div style="display: flex; gap: 24px; flex-wrap: wrap;">
					<div style="display: flex; flex-direction: column; gap: 2px;">
						<HudLabel>CREATED</HudLabel>
						<span
							style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums;"
						>
							{formatDate(mission.created_at)}
						</span>
					</div>
					<div style="display: flex; flex-direction: column; gap: 2px;">
						<HudLabel>UPDATED</HudLabel>
						<span
							style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums;"
						>
							{formatDate(mission.updated_at)}
						</span>
					</div>
					{#if mission.project}
						<div style="display: flex; flex-direction: column; gap: 2px;">
							<HudLabel>PROJECT</HudLabel>
							<span
								style="font-family: var(--l2-font-mono); font-size: 12px; color: #A0A0A0; font-variant-numeric: tabular-nums;"
							>
								{mission.project}
							</span>
						</div>
					{/if}
				</div>
			</div>
		</GlassPanel>

		<!-- Runs section -->
		<div style="margin-top: 24px;">
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
				<h2 style="margin: 0;">
					<HudLabel>RUNS</HudLabel>
				</h2>
				<button
					onclick={handleLaunchRun}
					class="btn-primary"
					disabled={launching}
					aria-label="Launch new run for mission {mission.id}"
				>
					LAUNCH NEW RUN
				</button>
			</header>

			{#if launchError}
				<div
					style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #FF0055; padding: 8px; background: rgba(255,0,85,0.08); border: 1px solid rgba(255,0,85,0.20); border-radius: 2px; margin-bottom: 16px;"
					role="alert"
				>
					{launchError}
				</div>
			{/if}

			{#if runs.length === 0}
				<GlassPanel
					style="padding: 48px 24px; display: flex; flex-direction: column; align-items: center; gap: 16px; text-align: center;"
				>
					<HudLabel>NO RUNS INITIATED</HudLabel>
					<p
						style="font-family: var(--l2-font-sans); font-size: 16px; font-weight: 400; color: #A0A0A0; margin: 0; line-height: 1.5;"
					>
						Launch a mission to generate a run.
					</p>
					<button
						onclick={handleLaunchRun}
						class="btn-primary"
						disabled={launching}
						style="margin-top: 8px;"
					>
						LAUNCH NEW RUN
					</button>
				</GlassPanel>
			{:else}
				<GlassPanel>
					<table
						style="width: 100%; border-collapse: collapse; table-layout: fixed;"
						aria-label="Mission runs"
					>
						<colgroup>
							<col style="width: 120px;" />
							<col style="width: 120px;" />
							<col style="width: 180px;" />
							<col style="width: 180px;" />
							<col style="width: 60px;" />
						</colgroup>
						<thead>
							<tr style="background: #050505; border-bottom: 1px solid rgba(255,255,255,0.05);">
								<th scope="col" style="padding: 12px; text-align: left;"
									><HudLabel>RUN ID</HudLabel></th
								>
								<th scope="col" style="padding: 12px; text-align: center;"
									><HudLabel>STATUS</HudLabel></th
								>
								<th scope="col" style="padding: 12px; text-align: left;"
									><HudLabel>STARTED</HudLabel></th
								>
								<th scope="col" style="padding: 12px; text-align: left;"
									><HudLabel>FINISHED</HudLabel></th
								>
								<th scope="col" style="padding: 12px; text-align: right;"
									><HudLabel>VIEW</HudLabel></th
								>
							</tr>
						</thead>
						<tbody>
							{#each runs as run (run.id)}
								<tr
									class="run-row"
									onclick={() => (window.location.href = `/runs/${run.id}`)}
									tabindex="0"
									aria-label="Run {run.id}"
									onkeydown={(e) => {
										if (e.key === 'Enter' || e.key === ' ') {
											e.preventDefault();
											window.location.href = `/runs/${run.id}`;
										}
									}}
									style="
										cursor: pointer;
										min-height: 48px;
										height: 48px;
										border-bottom: 1px solid rgba(255,255,255,0.05);
										transition: background 80ms ease;
									"
								>
									<td
										style="padding: 0 12px; font-family: var(--l2-font-mono); font-size: 12px; color: #A0A0A0; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
									>
										{run.id.slice(0, 8)}
									</td>
									<td style="padding: 0 12px; text-align: center;">
										<StatusBadge status={run.status} />
									</td>
									<td
										style="padding: 0 12px; font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums; white-space: nowrap;"
									>
										{formatDate(run.started_at)}
									</td>
									<td
										style="padding: 0 12px; font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums; white-space: nowrap;"
									>
										{run.finished_at ? formatDate(run.finished_at) : '—'}
									</td>
									<td style="padding: 0 12px; text-align: right;">
										<button
											onclick={(e) => {
												e.stopPropagation();
												window.location.href = `/runs/${run.id}`;
											}}
											aria-label="View run {run.id}"
											class="ghost-btn"
										>
											<ExternalLink size={16} strokeWidth={1.5} />
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</GlassPanel>
			{/if}
		</div>
	{/if}
</section>

<style>
	.btn-primary {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		background: #7f00ff;
		border: 1px solid rgba(127, 0, 255, 0.6);
		box-shadow: 0 0 24px rgba(127, 0, 255, 0.35);
		color: #ffffff;
		font-family: var(--l2-font-mono);
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		border-radius: 2px;
		padding: 8px 16px;
		cursor: pointer;
		transition:
			background 80ms ease,
			border-color 80ms ease;
		outline-offset: 2px;
	}

	.btn-primary:hover:not(:disabled) {
		background: rgba(127, 0, 255, 0.85);
		border-color: rgba(127, 0, 255, 1);
	}

	.btn-primary:focus {
		outline: 2px solid rgba(127, 0, 255, 0.6);
	}

	.btn-primary:disabled {
		opacity: 0.4;
		pointer-events: none;
		box-shadow: none;
	}

	.run-row:hover {
		background: rgba(255, 255, 255, 0.03);
	}

	.run-row:focus {
		outline: 2px solid rgba(127, 0, 255, 0.6);
		outline-offset: -2px;
	}

	.ghost-btn {
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
	}

	.ghost-btn:hover {
		color: #a0a0a0;
	}

	.ghost-btn:focus {
		outline: 2px solid rgba(127, 0, 255, 0.6);
	}
</style>
