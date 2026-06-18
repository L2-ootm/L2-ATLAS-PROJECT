<script lang="ts">
	import { page } from '$app/stores';
	import { ChevronLeft, ChevronRight } from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';
	import { cockpitModules } from '$lib/modules.js';
	import { checkHealth } from '$lib/api.js';
	import { sidebar, SIDEBAR_WIDTH_COLLAPSED, SIDEBAR_WIDTH_EXPANDED } from '$lib/ui-state.svelte.js';
	import AtlasMark from '$lib/brand/AtlasMark.svelte';

	// ── Collapse state (shared with +layout so main content shifts) ──────────
	onMount(() => {
		const saved = localStorage.getItem('atlas-sidebar-expanded');
		if (saved !== null) sidebar.expanded = saved === 'true';
	});

	function toggleExpanded(): void {
		sidebar.expanded = !sidebar.expanded;
		localStorage.setItem('atlas-sidebar-expanded', String(sidebar.expanded));
	}

	const expanded = $derived(sidebar.expanded);
	const width = $derived(expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED);

	// ── Gateway health ────────────────────────────────────────────────────────
	let gatewayOnline = $state<boolean | null>(null);

	async function pollHealth(): Promise<void> {
		try {
			await checkHealth();
			gatewayOnline = true;
		} catch {
			gatewayOnline = false;
		}
	}

	let healthInterval: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		void pollHealth();
		healthInterval = setInterval(() => void pollHealth(), 30_000);
	});

	onDestroy(() => {
		if (healthInterval !== null) clearInterval(healthInterval);
	});

	// ── Active route detection ────────────────────────────────────────────────
	function isActive(route: string): boolean {
		return $page.url.pathname.startsWith(route);
	}

	const statusColor = $derived(
		gatewayOnline === true ? 'var(--l2-success)' : gatewayOnline === false ? 'var(--l2-error)' : 'var(--l2-fg-3)'
	);
	const statusTopo = $derived(gatewayOnline === true ? 'good' : gatewayOnline === false ? 'bad' : 'atlas');
</script>

<nav
	aria-label="Main navigation"
	data-topo="atlas"
	style="
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		width: {width}px;
		background: linear-gradient(180deg, rgba(10,10,12,0.82), rgba(5,5,7,0.92));
		backdrop-filter: blur(14px) saturate(1.3);
		display: flex;
		flex-direction: column;
		border-right: 1px solid var(--l2-glass-border-lo);
		box-shadow: 1px 0 0 rgba(0,0,0,0.6), 8px 0 32px rgba(0,0,0,0.45);
		transition: width var(--l2-duration-sm) var(--l2-ease);
		z-index: 100;
		overflow: hidden;
	"
>
	<!-- ── Brand header — ATLAS-forward ────────────────────────────────────── -->
	<a
		href="/"
		aria-label="ATLAS home"
		style="
			display: flex;
			align-items: center;
			gap: 12px;
			height: 72px;
			padding: 0 {expanded ? '18px' : '0'};
			justify-content: {expanded ? 'flex-start' : 'center'};
			text-decoration: none;
			border-bottom: 1px solid var(--l2-glass-border-lo);
			flex: none;
		"
	>
		<AtlasMark variant="borne" tone="color" size={30} />
		{#if expanded}
			<div style="display:flex; flex-direction:column; gap:3px; min-width:0;">
				<span
					style="
						font-family: var(--l2-font-display);
						font-weight: 700;
						font-size: 18px;
						letter-spacing: 0.26em;
						line-height: 1;
						color: var(--l2-fg-1);
						white-space: nowrap;
					"
				>ATL<span style="color: var(--atlas-bronze);">A</span>S</span>
				<span
					style="
						font-family: var(--l2-font-mono);
						font-size: 8px;
						letter-spacing: 0.28em;
						text-transform: uppercase;
						color: var(--l2-fg-3);
						white-space: nowrap;
					"
				>OPERATOR COCKPIT</span>
			</div>
		{/if}
	</a>

	<!-- ── Collapse toggle ─────────────────────────────────────────────────── -->
	<button
		onclick={toggleExpanded}
		aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
		style="
			display: flex;
			align-items: center;
			justify-content: {expanded ? 'flex-end' : 'center'};
			width: 100%;
			height: 34px;
			padding: {expanded ? '0 18px' : '0'};
			background: none;
			border: none;
			border-bottom: 1px solid var(--l2-glass-border-lo);
			cursor: pointer;
			color: var(--l2-fg-3);
			transition: color var(--l2-duration-xs) var(--l2-ease);
		"
		onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--l2-cyber-blue)'; }}
		onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--l2-fg-3)'; }}
	>
		{#if expanded}
			<ChevronLeft size={15} strokeWidth={1.5} />
		{:else}
			<ChevronRight size={15} strokeWidth={1.5} />
		{/if}
	</button>

	<!-- ── Navigation ──────────────────────────────────────────────────────── -->
	<ul role="list" style="flex: 1; list-style: none; margin: 0; padding: 10px 0;">
		{#each cockpitModules as mod (mod.id)}
			{@const active = isActive(mod.route)}
			<li>
				<a
					href={mod.route}
					data-topo={active ? 'info' : 'atlas'}
					aria-label={expanded ? undefined : mod.ariaLabel}
					aria-current={active ? 'page' : undefined}
					style="
						position: relative;
						display: flex;
						align-items: center;
						gap: {expanded ? '14px' : '0'};
						justify-content: {expanded ? 'flex-start' : 'center'};
						height: 46px;
						margin: 2px 8px;
						padding: {expanded ? '0 12px' : '0'};
						border-radius: var(--l2-radius);
						text-decoration: none;
						background: {active ? 'rgba(0,240,255,0.07)' : 'transparent'};
						color: {active ? 'var(--l2-cyber-blue)' : 'var(--l2-fg-3)'};
						box-shadow: {active ? 'inset 0 0 0 1px rgba(0,240,255,0.18)' : 'none'};
						transition: background var(--l2-duration-xs) var(--l2-ease), color var(--l2-duration-xs) var(--l2-ease);
					"
					onmouseenter={(e) => {
						if (!active) {
							const el = e.currentTarget as HTMLAnchorElement;
							el.style.background = 'var(--l2-glass-bg-lo)';
							el.style.color = 'var(--l2-fg-1)';
						}
					}}
					onmouseleave={(e) => {
						if (!active) {
							const el = e.currentTarget as HTMLAnchorElement;
							el.style.background = 'transparent';
							el.style.color = 'var(--l2-fg-3)';
						}
					}}
				>
					{#if active}
						<span
							aria-hidden="true"
							style="position:absolute; left:-8px; top:50%; transform:translateY(-50%); width:3px; height:22px; border-radius:0 2px 2px 0; background:var(--l2-cyber-blue); box-shadow:0 0 12px var(--l2-cyber-blue-glow);"
						></span>
					{/if}
					<mod.icon size={expanded ? 17 : 20} strokeWidth={1.5} color="currentColor" />
					{#if expanded}
						<span
							style="
								font-family: var(--l2-font-mono);
								font-size: 12px;
								font-weight: 500;
								text-transform: uppercase;
								letter-spacing: 0.16em;
								white-space: nowrap;
							"
						>{mod.label}</span>
					{/if}
				</a>
			</li>
		{/each}
	</ul>

	<!-- ── Footer — gateway status + L2 endorsement ────────────────────────── -->
	<div
		style="
			padding: {expanded ? '14px 18px' : '14px 0'};
			border-top: 1px solid var(--l2-glass-border-lo);
			display: flex;
			flex-direction: column;
			gap: 10px;
			align-items: {expanded ? 'stretch' : 'center'};
			flex: none;
		"
		data-topo={statusTopo}
	>
		<!-- Gateway status -->
		<div style="display:flex; align-items:center; gap:8px; justify-content:{expanded ? 'flex-start' : 'center'};">
			<span
				aria-hidden="true"
				style="width:7px; height:7px; border-radius:50%; background:{statusColor}; box-shadow:0 0 8px {statusColor}; flex:none;"
			></span>
			{#if expanded}
				<span
					style="font-family:var(--l2-font-mono); font-size:10px; text-transform:uppercase; letter-spacing:0.16em; color:{statusColor};"
				>
					{#if gatewayOnline === true}GATEWAY · ONLINE{:else if gatewayOnline === false}GATEWAY · OFFLINE{:else}GATEWAY · CHECKING{/if}
				</span>
			{/if}
		</div>

		{#if expanded}
			<!-- L2 endorsement (ATLAS-forward, L2-endorsed) -->
			<div style="display:flex; align-items:center; gap:6px; color:var(--l2-fg-3);">
				<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--l2-fg-2)" stroke-width="3" stroke-linecap="square" aria-hidden="true">
					<path d="M5 5 V19 H13 M15 5 H19 V11 H15 V19 H19" />
				</svg>
				<span style="font-family:var(--l2-font-mono); font-size:9px; letter-spacing:0.22em; text-transform:uppercase;">BY L2 SYSTEMS</span>
			</div>
		{/if}
	</div>
</nav>
