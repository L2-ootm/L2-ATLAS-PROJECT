<script lang="ts">
	// Surface 3: Wiki Browser — COCKPIT-04
	// Two-column layout: 280px scrollable page list + flex-1 page viewer
	// FTS search debounced 300ms, GitBranch provenance toggle, create/edit form
	import { onMount } from 'svelte';
	import type { WikiPage, WikiPageDetail, WikiSearchResult } from '$lib/api';
	import { listWikiPages, searchWiki, getWikiPage } from '$lib/api';
	import { Search } from '@lucide/svelte';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import WikiPageList from '$lib/components/WikiPageList.svelte';
	import WikiPageViewer from '$lib/components/WikiPageViewer.svelte';
	import WikiPageForm from '$lib/components/WikiPageForm.svelte';

	// ── State ────────────────────────────────────────────────────────────────────
	let pages = $state<WikiPage[]>([]);
	let searchQuery = $state('');
	let searchResults = $state<WikiSearchResult[] | null>(null);
	let activePage = $state<WikiPageDetail | null>(null);
	let showForm = $state(false);
	let formMode = $state<'create' | 'edit'>('create');
	let loadError = $state('');

	// Debounce timer handle (300ms — per spec: wiki FTS search debounce).
	// Plain variable, NOT $state: the $effect below both reads and writes it,
	// and a $state read+write inside the same effect re-triggers the effect
	// until Svelte aborts with effect_update_depth_exceeded.
	let debounceTimer: ReturnType<typeof setTimeout> | undefined;

	// ── Lifecycle ────────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			const res = await listWikiPages();
			pages = res.pages;
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			loadError = msg;
		}
	});

	// ── Debounced FTS search ($effect watches searchQuery) ───────────────────────
	$effect(() => {
		// Capture value in closure for async use
		const q = searchQuery;

		// Cancel previous debounce timer (300ms debounce)
		clearTimeout(debounceTimer);

		if (!q.trim()) {
			searchResults = null;
			return;
		}

		// Set new 300ms debounce timer
		debounceTimer = setTimeout(async () => {
			try {
				const res = await searchWiki(q);
				searchResults = res.results;
			} catch {
				searchResults = [];
			}
		}, 300);

		return () => clearTimeout(debounceTimer);
	});

	// ── Handlers ─────────────────────────────────────────────────────────────────
	async function handleSelectPage(page: { slug: string }) {
		try {
			const res = await getWikiPage(page.slug);
			activePage = res.page;
			searchQuery = '';
			searchResults = null;
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			loadError = msg;
		}
	}

	function handleEditPage() {
		formMode = 'edit';
		showForm = true;
	}

	function handleCreatePage() {
		formMode = 'create';
		showForm = true;
	}

	function handleFormSaved(page: WikiPageDetail) {
		// Dedupe regardless of mode: the gateway POST is an upsert, so "create"
		// with an existing slug succeeds — prepending unconditionally would put
		// duplicate slugs in the keyed each and crash the list.
		const exists = pages.some((p) => p.slug === page.slug);
		pages = exists ? pages.map((p) => (p.slug === page.slug ? page : p)) : [page, ...pages];
		activePage = page;
		showForm = false;
	}

	function handleFormDiscard() {
		showForm = false;
	}
</script>

<svelte:head>
	<title>WIKI — ATLAS COCKPIT</title>
</svelte:head>

<section
	aria-labelledby="wiki-heading"
	style="display: flex; flex-direction: column; height: 100%;"
	onmouseenter={() => document.documentElement.setAttribute('data-topo-glow', 'brand')}
	onmouseleave={() => document.documentElement.removeAttribute('data-topo-glow')}
>
	<!-- Section header: HudLabel WIKI + CREATE PAGE primary button -->
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
		<h1 id="wiki-heading" style="margin: 0; padding: 0;">
			<HudLabel>WIKI</HudLabel>
		</h1>
		<button
			onclick={handleCreatePage}
			style="background: #7F00FF; border: 1px solid rgba(127,0,255,0.6); box-shadow: 0 0 24px rgba(127,0,255,0.35); font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #FFFFFF; border-radius: 2px; padding: 8px 16px; cursor: pointer; transition: background 80ms ease;"
			onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(127,0,255,0.85)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = '#7F00FF'; }}
		>
			CREATE PAGE
		</button>
	</header>

	<!-- Load error banner -->
	{#if loadError}
		<p
			style="font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055; margin: 0 0 12px 0; padding: 8px 12px; background: rgba(255,0,85,0.08); border: 1px solid rgba(255,0,85,0.20); border-radius: 2px;"
		>
			{loadError}
		</p>
	{/if}

	<!-- FTS search bar: full-width, Search icon left-inset, debounce 300ms -->
	<div style="position: relative; margin-bottom: 16px;">
		<span
			style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #505050; display: flex; align-items: center; pointer-events: none;"
			aria-hidden="true"
		>
			<Search size={16} strokeWidth={1.5} />
		</span>
		<input
			type="text"
			bind:value={searchQuery}
			placeholder="SEARCH WIKI — full-text search"
			aria-label="Search wiki pages"
			style="
				width: 100%;
				box-sizing: border-box;
				background: rgba(255,255,255,0.05);
				border: 1px solid rgba(255,255,255,0.08);
				border-radius: 2px;
				color: var(--l2-fg-1);
				font-family: var(--l2-font-sans);
				font-size: 16px;
				font-weight: 400;
				padding: 10px 12px 10px 36px;
				outline: none;
				transition: border-color 150ms ease, box-shadow 150ms ease;
			"
			onfocus={(e) => {
				const el = e.currentTarget as HTMLInputElement;
				el.style.borderColor = '#7F00FF';
				el.style.boxShadow = '0 0 0 2px rgba(127,0,255,0.20)';
			}}
			onblur={(e) => {
				const el = e.currentTarget as HTMLInputElement;
				el.style.borderColor = 'rgba(255,255,255,0.08)';
				el.style.boxShadow = 'none';
			}}
		/>
	</div>

	<!-- FTS results table (shown only when searchResults is not null) -->
	{#if searchResults !== null}
		<div style="flex: 1; overflow-y: auto;">
			{#if searchResults.length === 0}
				<div
					style="padding: 16px; background: rgba(20,20,20,0.60); border: 1px solid rgba(255,255,255,0.08); border-radius: 2px;"
				>
					<HudLabel>NO RESULTS — query: "{searchQuery}". Refine search terms or browse all pages.</HudLabel>
				</div>
			{:else}
				<!-- Data Table: TITLE flex-1, UPDATED 160px mono, RELEVANCE SCORE 80px mono -->
				<div style="background: rgba(20,20,20,0.60); border: 1px solid rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden;">
					<!-- Header row -->
					<div
						style="display: grid; grid-template-columns: 1fr 160px 80px; gap: 12px; padding: 4px 12px; background: #050505; border-bottom: 1px solid rgba(255,255,255,0.05);"
					>
						<span style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2);">TITLE</span>
						<span style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2);">UPDATED</span>
						<span style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2);">SCORE</span>
					</div>
					<!-- Result rows -->
					{#each searchResults as result (result.slug)}
						<div
							role="button"
							tabindex="0"
							aria-label="Open wiki page: {result.title}"
							onclick={() => handleSelectPage(result)}
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									handleSelectPage(result);
								}
							}}
							style="display: grid; grid-template-columns: 1fr 160px 80px; gap: 12px; padding: 4px 12px; height: 48px; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: background 80ms ease;"
							onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.03)'; }}
							onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
						>
							<span style="font-family: var(--l2-font-sans); font-size: 16px; color: var(--l2-fg-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{result.title}</span>
							<span style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); font-variant-numeric: tabular-nums;">{result.updated_at}</span>
							<!-- bm25 rank: more negative = better match; show magnitude -->
							<span style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); font-variant-numeric: tabular-nums;">{Math.abs(result.score).toFixed(2)}</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<!-- Two-column layout: 280px list + flex-1 viewer/form -->
		<div style="display: flex; flex: 1; gap: 16px; min-height: 0; overflow: hidden;">
			<!-- Left: wiki page list (280px) -->
			<div
				style="width: 280px; flex-shrink: 0; background: rgba(20,20,20,0.60); border: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(12px) saturate(1.4); border-radius: 2px; overflow: hidden; display: flex; flex-direction: column;"
			>
				<WikiPageList
					{pages}
					activeslug={activePage?.slug ?? null}
					onSelect={handleSelectPage}
				/>
			</div>

			<!-- Right: viewer or form (flex-1) -->
			<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden;">
				{#if showForm}
					<WikiPageForm
						mode={formMode}
						initialSlug={formMode === 'edit' ? (activePage?.slug ?? '') : ''}
						initialTitle={formMode === 'edit' ? (activePage?.title ?? '') : ''}
						initialBody={formMode === 'edit' ? (activePage?.body ?? '') : ''}
						onSaved={handleFormSaved}
						onDiscard={handleFormDiscard}
					/>
				{:else}
					<WikiPageViewer page={activePage} onEdit={handleEditPage} />
				{/if}
			</div>
		</div>
	{/if}
</section>
