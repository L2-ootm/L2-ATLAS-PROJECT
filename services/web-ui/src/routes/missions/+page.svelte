<script lang="ts">
	import { onMount } from 'svelte';
	import { Plus } from '@lucide/svelte';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import GlassPanel from '$lib/components/GlassPanel.svelte';
	import MissionRow from '$lib/components/MissionRow.svelte';
	import { listMissions } from '$lib/api';
	import type { Mission } from '$lib/api';

	let missions: Mission[] = $state([]);
	let loading = $state(true);
	let error: string | null = $state(null);
	let showModal = $state(false);
	let flashId: string | null = $state(null);

	onMount(async () => {
		await loadMissions();
	});

	async function loadMissions() {
		loading = true;
		error = null;
		try {
			const result = await listMissions();
			missions = result.missions;
		} catch (err) {
			if (err instanceof TypeError) {
				error =
					'GATEWAY OFFLINE — 127.0.0.1:8484 not responding. Start the atlas-gateway process.';
			} else if (err instanceof Error) {
				const match = err.message.match(/^GATEWAY ERROR (\d+)/);
				if (match) {
					error = `GATEWAY ERROR ${match[1]} — /v1/missions. Inspect logs at services/atlas-gateway.`;
				} else {
					error =
						'GATEWAY OFFLINE — 127.0.0.1:8484 not responding. Start the atlas-gateway process.';
				}
			} else {
				error =
					'GATEWAY OFFLINE — 127.0.0.1:8484 not responding. Start the atlas-gateway process.';
			}
		} finally {
			loading = false;
		}
	}

	function handleCreated(mission: Mission) {
		missions = [mission, ...missions];
		flashId = mission.id;
		setTimeout(() => {
			flashId = null;
		}, 500);
	}
</script>

<svelte:head>
	<title>MISSIONS — ATLAS COCKPIT</title>
</svelte:head>

<section aria-labelledby="missions-heading">
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
		<h1 id="missions-heading" style="margin: 0;">
			<HudLabel>MISSIONS</HudLabel>
		</h1>

		<button
			onclick={() => (showModal = true)}
			class="btn-primary"
			aria-label="Create mission"
		>
			<Plus size={20} strokeWidth={1.5} />
			CREATE MISSION
		</button>
	</header>

	{#if loading}
		<GlassPanel
			style="padding: 48px; display: flex; justify-content: center; align-items: center;"
		>
			<HudLabel>LOADING...</HudLabel>
		</GlassPanel>
	{:else if error}
		<GlassPanel style="padding: 24px;">
			<span class="error-text">{error}</span>
		</GlassPanel>
	{:else if missions.length === 0}
		<GlassPanel
			style="padding: 64px 24px; display: flex; flex-direction: column; align-items: center; gap: 16px; text-align: center;"
		>
			<HudLabel>NO MISSIONS RECORDED</HudLabel>
			<p class="body-text">Operation window closed. Create a mission to begin.</p>
			<button
				onclick={() => (showModal = true)}
				class="btn-primary"
				style="margin-top: 8px;"
				aria-label="Create mission"
			>
				<Plus size={20} strokeWidth={1.5} />
				CREATE MISSION
			</button>
		</GlassPanel>
	{:else}
		<div
			role="region"
			aria-label="Mission list panel"
			onmouseenter={(e) => {
				(e.currentTarget as HTMLElement).dataset.topoActive = 'true';
			}}
			onmouseleave={(e) => {
				delete (e.currentTarget as HTMLElement).dataset.topoActive;
			}}
		>
			<GlassPanel>
				<table
					style="width: 100%; border-collapse: collapse; table-layout: fixed;"
					role="grid"
					aria-label="Mission list"
				>
					<colgroup>
						<col style="width: 90px;" />
						<col />
						<col style="width: 120px;" />
						<col style="width: 160px;" />
						<col style="width: 80px;" />
					</colgroup>
					<thead>
						<tr style="background: #050505; border-bottom: 1px solid rgba(255,255,255,0.05);">
							<th scope="col" style="padding: 12px; text-align: left;"><HudLabel>ID</HudLabel></th>
							<th scope="col" style="padding: 12px; text-align: left;"
								><HudLabel>TITLE</HudLabel></th
							>
							<th scope="col" style="padding: 12px; text-align: center;"
								><HudLabel>STATUS</HudLabel></th
							>
							<th scope="col" style="padding: 12px; text-align: left;"
								><HudLabel>CREATED</HudLabel></th
							>
							<th scope="col" style="padding: 12px; text-align: right;"
								><HudLabel>ACTIONS</HudLabel></th
							>
						</tr>
					</thead>
					<tbody>
						{#each missions as mission (mission.id)}
							<MissionRow {mission} flash={flashId === mission.id} />
						{/each}
					</tbody>
				</table>
			</GlassPanel>
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

	.btn-primary:hover {
		background: rgba(127, 0, 255, 0.85);
		border-color: rgba(127, 0, 255, 1);
	}

	.btn-primary:focus {
		outline: 2px solid rgba(127, 0, 255, 0.6);
	}

	.btn-primary:disabled {
		opacity: 0.4;
		pointer-events: none;
	}

	.error-text {
		font-family: var(--l2-font-mono);
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		color: #ff0055;
	}

	.body-text {
		font-family: var(--l2-font-sans);
		font-size: 16px;
		font-weight: 400;
		color: #a0a0a0;
		margin: 0;
		line-height: 1.5;
	}
</style>
