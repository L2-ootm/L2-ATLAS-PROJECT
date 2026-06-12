<script lang="ts">
	import { page } from '$app/stores';
	import { ChevronLeft, ChevronRight } from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';
	import { cockpitModules } from '$lib/modules.js';
	import { checkHealth } from '$lib/api.js';
	import { sidebar } from '$lib/ui-state.svelte.js';

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
</script>

<nav
	aria-label="Main navigation"
	style="
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		width: {expanded ? '200px' : '56px'};
		background: #050505;
		display: flex;
		flex-direction: column;
		border-right: 1px solid rgba(255,255,255,0.05);
		transition: width 150ms var(--l2-ease);
		z-index: 100;
		overflow: hidden;
	"
>
	<!-- ASCII ATLAS wordmark (brand accent) -->
	{#if expanded}
		<div
			style="
				padding: 16px 12px 4px;
				border-bottom: 1px solid rgba(255,255,255,0.04);
			"
			aria-hidden="true"
		>
			<pre
				style="
					font-family: var(--l2-font-mono);
					font-size: 7px;
					line-height: 1.1;
					color: var(--l2-fg-3);
					margin: 0;
					padding: 0;
					user-select: none;
					letter-spacing: 0.05em;
				"
			>
  ___  _____ __    ___  ___
 / _ \|_   _| |  / _ \/ __|
| (_) | | | | |_| (_) \__ \
 \___/  |_| |____\___/|___/
			</pre>
		</div>
	{:else}
		<div style="height: 48px;"></div>
	{/if}

	<!-- Toggle button -->
	<button
		onclick={toggleExpanded}
		aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
		style="
			display: flex;
			align-items: center;
			justify-content: center;
			width: 100%;
			height: 40px;
			background: none;
			border: none;
			border-bottom: 1px solid rgba(255,255,255,0.04);
			cursor: pointer;
			color: var(--l2-fg-3);
			padding: 0;
			transition: color var(--l2-duration-xs) var(--l2-ease);
		"
		onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--l2-fg-2)'; }}
		onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--l2-fg-3)'; }}
	>
		{#if expanded}
			<ChevronLeft size={16} strokeWidth={1.5} />
		{:else}
			<ChevronRight size={16} strokeWidth={1.5} />
		{/if}
	</button>

	<!-- Navigation items -->
	<ul role="list" style="flex: 1; list-style: none; margin: 0; padding: 8px 0;">
		{#each cockpitModules as mod (mod.id)}
			{@const active = isActive(mod.route)}
			<li>
				<a
					href={mod.route}
					aria-label={expanded ? undefined : mod.ariaLabel}
					aria-current={active ? 'page' : undefined}
					style="
						display: flex;
						align-items: center;
						gap: {expanded ? '12px' : '0'};
						justify-content: {expanded ? 'flex-start' : 'center'};
						height: 48px;
						padding: {expanded ? '0 16px' : '0'};
						text-decoration: none;
						border-left: 2px solid {active ? '#00F0FF' : 'transparent'};
						background: {active ? 'rgba(0,240,255,0.06)' : 'transparent'};
						color: {active ? '#00F0FF' : '#505050'};
						transition: background var(--l2-duration-xs) var(--l2-ease), color var(--l2-duration-xs) var(--l2-ease);
					"
					onmouseenter={(e) => {
						if (!active) {
							const el = e.currentTarget as HTMLAnchorElement;
							el.style.background = 'rgba(255,255,255,0.02)';
							el.style.color = '#A0A0A0';
						}
					}}
					onmouseleave={(e) => {
						if (!active) {
							const el = e.currentTarget as HTMLAnchorElement;
							el.style.background = 'transparent';
							el.style.color = '#505050';
						}
					}}
				>
					<mod.icon
						size={expanded ? 16 : 20}
						strokeWidth={1.5}
						color={active ? '#00F0FF' : '#505050'}
					/>
					{#if expanded}
						<span
							style="
								font-family: var(--l2-font-sans);
								font-size: 14px;
								font-weight: 600;
								text-transform: uppercase;
								letter-spacing: 0.1em;
								white-space: nowrap;
							"
						>
							{mod.label}
						</span>
					{/if}
				</a>
			</li>
		{/each}
	</ul>

	<!-- Bottom: wordmark + gateway status -->
	{#if expanded}
		<div
			style="
				padding: 12px 16px;
				border-top: 1px solid rgba(255,255,255,0.04);
			"
		>
			<!-- Wordmark -->
			<div
				style="
					font-family: var(--l2-font-display);
					font-size: 12px;
					text-transform: uppercase;
					letter-spacing: 0.3em;
					color: #E0E0E0;
					margin-bottom: 8px;
				"
			>
				L2 // SYSTEMS
			</div>

			<!-- Gateway status -->
			<div
				style="
					font-family: var(--l2-font-mono);
					font-size: 11px;
					text-transform: uppercase;
					letter-spacing: 0.1em;
					color: {gatewayOnline === true ? '#00FF94' : gatewayOnline === false ? '#FF0055' : '#505050'};
				"
			>
				{#if gatewayOnline === true}
					GATEWAY: ONLINE
				{:else if gatewayOnline === false}
					GATEWAY: OFFLINE
				{:else}
					GATEWAY: CHECKING
				{/if}
			</div>
		</div>
	{/if}
</nav>
