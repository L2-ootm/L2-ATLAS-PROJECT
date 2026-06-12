<script lang="ts">
	// WikiPageViewer — renders wiki page content with markdown and provenance toggle
	// Inter 400 16px body, line-height 1.5. XSS-safe markdown via sanitizeHtml() before {@html}.
	import type { WikiPageDetail } from '$lib/api';
	import { GitBranch, Edit } from '@lucide/svelte';
	import GlassPanel from './GlassPanel.svelte';
	import HudLabel from './HudLabel.svelte';
	import ProvenancePanel from './ProvenancePanel.svelte';

	interface Props {
		page: WikiPageDetail | null;
		onEdit: () => void;
	}

	let { page, onEdit }: Props = $props();

	let showProvenance = $state(false);

	// ── Minimal markdown renderer (Inter 400 16px body, line-height 1.5) ─────────
	// Converts: **bold**, *italic*, `code`, # Heading → h3, - list items, blank lines → paragraphs
	// XSS-safe: sanitizeHtml strips script/iframe/on* before injecting into DOM (T-08-16)

	function sanitizeHtml(raw: string): string {
		return raw
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;')
			.replace(/'/g, '&#39;');
	}

	function renderMarkdown(text: string): string {
		// 1. Sanitize all HTML special chars first to prevent XSS
		const safe = sanitizeHtml(text);

		// 2. Process block elements line-by-line
		const lines = safe.split('\n');
		const result: string[] = [];
		let inList = false;

		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];

			// Headings (# → h3, since cockpit has no h1/h2)
			const headingMatch = /^#{1,6}\s+(.+)$/.exec(line);
			if (headingMatch) {
				if (inList) {
					result.push('</ul>');
					inList = false;
				}
				result.push(
					`<h3 style="font-family:var(--l2-font-sans);font-size:14px;font-weight:600;color:var(--l2-fg-1);margin:12px 0 4px 0;">${applyInline(headingMatch[1])}</h3>`
				);
				continue;
			}

			// Unordered list items
			const listMatch = /^[-*+]\s+(.+)$/.exec(line);
			if (listMatch) {
				if (!inList) {
					result.push(
						'<ul style="margin:8px 0;padding-left:20px;font-family:var(--l2-font-sans);font-size:16px;color:var(--l2-fg-1);">'
					);
					inList = true;
				}
				result.push(`<li style="margin:2px 0;line-height:1.5;">${applyInline(listMatch[1])}</li>`);
				continue;
			}

			// Close list if we hit a non-list line
			if (inList) {
				result.push('</ul>');
				inList = false;
			}

			// Blank line → paragraph separator
			if (line.trim() === '') {
				result.push('<br>');
				continue;
			}

			// Normal paragraph line
			result.push(
				`<p style="margin:0 0 8px 0;font-family:var(--l2-font-sans);font-size:16px;color:var(--l2-fg-1);line-height:1.5;">${applyInline(line)}</p>`
			);
		}

		if (inList) result.push('</ul>');

		return result.join('');
	}

	function applyInline(text: string): string {
		return text
			// Bold: **text** → <strong>
			.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600;">$1</strong>')
			// Italic: *text* → <em>
			.replace(/\*(.+?)\*/g, '<em style="font-style:italic;">$1</em>')
			// Inline code: `code` → <code>
			.replace(
				/`(.+?)`/g,
				'<code style="font-family:var(--l2-font-mono);font-size:12px;background:rgba(255,255,255,0.06);padding:1px 4px;border-radius:2px;">$1</code>'
			);
	}

	const renderedBody = $derived(page ? renderMarkdown(page.body) : '');
</script>

{#if page === null}
	<GlassPanel style="padding: 24px; display: flex; align-items: center; justify-content: center; height: 100%;">
		<HudLabel>SELECT A PAGE</HudLabel>
	</GlassPanel>
{:else}
	<GlassPanel style="padding: 24px; display: flex; flex-direction: column; height: 100%; overflow-y: auto;">
		<!-- Page title (Inter 600 16px #E0E0E0) -->
		<div
			style="font-family: var(--l2-font-sans); font-size: 16px; font-weight: 600; color: var(--l2-fg-1); margin-bottom: 12px; line-height: 1.2;"
		>
			{page.title}
		</div>

		<!-- Controls row: UPDATED timestamp left, GitBranch + Edit icons right -->
		<div
			style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);"
		>
			<span style="font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); font-variant-numeric: tabular-nums;">
				<HudLabel>UPDATED</HudLabel>
				&nbsp;{page.updated_at}
			</span>
			<div style="display: flex; gap: 8px; align-items: center;">
				<button
					aria-label="View provenance"
					onclick={() => { showProvenance = !showProvenance; }}
					style="background: none; border: none; cursor: pointer; color: {showProvenance ? '#7F00FF' : '#505050'}; padding: 4px; display: flex; align-items: center; transition: color 80ms ease;"
					onmouseenter={(e) => { if (!showProvenance) (e.currentTarget as HTMLButtonElement).style.color = '#A0A0A0'; }}
					onmouseleave={(e) => { if (!showProvenance) (e.currentTarget as HTMLButtonElement).style.color = '#505050'; }}
				>
					<GitBranch size={16} strokeWidth={1.5} />
				</button>
				<button
					aria-label="Edit page"
					onclick={onEdit}
					style="background: none; border: none; cursor: pointer; color: #505050; padding: 4px; display: flex; align-items: center; transition: color 80ms ease;"
					onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#A0A0A0'; }}
					onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#505050'; }}
				>
					<Edit size={16} strokeWidth={1.5} />
				</button>
			</div>
		</div>

		<!-- Markdown content: Inter 400 16px body, line-height 1.5, XSS-safe rendered HTML (T-08-16) -->
		<div
			style="flex: 1; overflow-y: auto; font-family: var(--l2-font-sans); font-size: 16px; color: var(--l2-fg-1); line-height: 1.5;"
		>
			{@html renderedBody}
		</div>

		<!-- Provenance row (always visible below content) -->
		<div
			style="margin-top: 16px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); display: flex; align-items: center; gap: 8px;"
		>
			<HudLabel>SOURCE:</HudLabel>
			<span style="font-family: var(--l2-font-mono); font-size: 12px; color: #505050; font-variant-numeric: tabular-nums;">
				{#if page.provenance}
					{page.provenance.sha256.slice(0, 16)}
				{:else}
					—
				{/if}
			</span>
		</div>

		<!-- ProvenancePanel: expands on GitBranch toggle -->
		{#if showProvenance}
			<ProvenancePanel provenance={page.provenance} />
		{/if}
	</GlassPanel>
{/if}
