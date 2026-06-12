<script lang="ts">
	import type { WikiPage } from '$lib/api';
	import HudLabel from './HudLabel.svelte';

	interface Props {
		pages: WikiPage[];
		activeslug: string | null;
		onSelect: (page: WikiPage) => void;
	}

	let { pages, activeslug, onSelect }: Props = $props();

	function formatDate(iso: string): string {
		try {
			const d = new Date(iso);
			const now = new Date();
			const diffMs = now.getTime() - d.getTime();
			const diffDays = Math.floor(diffMs / 86400000);
			if (diffDays === 0) return 'today';
			if (diffDays === 1) return '1d ago';
			if (diffDays < 30) return `${diffDays}d ago`;
			if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
			return `${Math.floor(diffDays / 365)}y ago`;
		} catch {
			return iso;
		}
	}
</script>

<div style="overflow-y: auto; height: 100%;">
	{#if pages.length === 0}
		<div style="padding: 24px 16px;">
			<HudLabel>
				WIKI EMPTY. No pages ingested. Create a page or ingest a source to populate the knowledge
				base.
			</HudLabel>
		</div>
	{:else}
		{#each pages as page (page.slug)}
			<!-- svelte-ignore a11y_interactive_supports_focus -->
			<div
				role="button"
				tabindex="0"
				aria-label="Open wiki page: {page.title}"
				onclick={() => onSelect(page)}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						onSelect(page);
					}
				}}
				style="
					padding: 12px 16px;
					cursor: pointer;
					border-left: 2px solid {page.slug === activeslug ? '#7F00FF' : 'transparent'};
					background: {page.slug === activeslug ? 'rgba(127,0,255,0.06)' : 'transparent'};
					transition: background 80ms ease;
					border-bottom: 1px solid rgba(255,255,255,0.03);
				"
				onmouseenter={(e) => {
					if (page.slug !== activeslug) {
						(e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.03)';
					}
				}}
				onmouseleave={(e) => {
					if (page.slug !== activeslug) {
						(e.currentTarget as HTMLElement).style.background = 'transparent';
					}
				}}
			>
				<div
					style="font-family: var(--l2-font-sans); font-size: 14px; font-weight: 400; color: var(--l2-fg-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
				>
					{page.title}
				</div>
				<div
					style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); margin-top: 2px; font-variant-numeric: tabular-nums;"
				>
					{formatDate(page.updated_at)}
				</div>
			</div>
		{/each}
	{/if}
</div>
