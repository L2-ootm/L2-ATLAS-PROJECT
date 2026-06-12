<script lang="ts">
	import type { WikiPageDetail } from '$lib/api';
	import { createWikiPage, updateWikiPage } from '$lib/api';
	import { untrack } from 'svelte';
	import GlassPanel from './GlassPanel.svelte';
	import HudLabel from './HudLabel.svelte';

	interface Props {
		mode: 'create' | 'edit';
		initialSlug?: string;
		initialTitle?: string;
		initialBody?: string;
		initialLayer?: number;
		onSaved: (page: WikiPageDetail) => void;
		onDiscard: () => void;
	}

	let {
		mode,
		initialSlug = '',
		initialTitle = '',
		initialBody = '',
		initialLayer = 4,
		onSaved,
		onDiscard
	}: Props = $props();

	// Layer options per AGENT_MEMORY_FRAMEWORK_STRATEGY
	const layerOptions = [
		{ value: 1, label: '1 — PERCEPTION' },
		{ value: 2, label: '2 — WORKING' },
		{ value: 3, label: '3 — EPISODIC' },
		{ value: 4, label: '4 — SEMANTIC' },
		{ value: 5, label: '5 — PROCEDURAL' },
		{ value: 6, label: '6 — META' }
	];

	// Form fields: initialized from props once (editable by user thereafter).
	// untrack() prevents Svelte from tracking the prop reference in $state initialization,
	// avoiding the state_referenced_locally warning (prop is read once at mount, not reactive).
	let slug = $state(untrack(() => initialSlug));
	let title = $state(untrack(() => initialTitle));
	let body = $state(untrack(() => initialBody));
	let layer = $state(untrack(() => initialLayer));

	let saving = $state(false);
	let apiError = $state('');
	let fieldErrors = $state<Record<string, string>>({});

	function validate(): boolean {
		const errors: Record<string, string> = {};
		if (mode === 'create' && !slug.trim()) errors.slug = 'Slug is required';
		if (!title.trim()) errors.title = 'Title is required';
		if (!body.trim()) errors.body = 'Content is required';
		fieldErrors = errors;
		return Object.keys(errors).length === 0;
	}

	async function handleSave() {
		if (!validate()) return;
		saving = true;
		apiError = '';
		try {
			let result: { page: WikiPageDetail };
			if (mode === 'create') {
				result = await createWikiPage(slug.trim(), title.trim(), body, layer);
			} else {
				result = await updateWikiPage(initialSlug, { title: title.trim(), body, layer });
			}
			onSaved(result.page);
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			apiError = `PAGE SAVE FAILED — ${msg}. Content preserved in form. Retry.`;
		} finally {
			saving = false;
		}
	}

	function handleDiscard() {
		slug = initialSlug;
		title = initialTitle;
		body = initialBody;
		layer = initialLayer;
		fieldErrors = {};
		apiError = '';
		onDiscard();
	}

	// Shared input styles per L2 design system
	const inputStyle =
		'width: 100%; box-sizing: border-box; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 2px; color: var(--l2-fg-1); font-family: var(--l2-font-sans); font-size: 14px; padding: 8px 12px; outline: none; transition: border-color 150ms ease, box-shadow 150ms ease;';
	const inputFocusStyle =
		'border-color: #7F00FF !important; box-shadow: 0 0 0 2px rgba(127,0,255,0.20) !important;';
	const inputErrorStyle =
		'border-color: #FF0055 !important; box-shadow: 0 0 0 2px rgba(255,0,85,0.20) !important;';
</script>

<GlassPanel style="padding: 24px;">
	<!-- Header -->
	<div style="margin-bottom: 16px;">
		<HudLabel>{mode === 'create' ? 'CREATE PAGE' : 'EDIT PAGE'}</HudLabel>
	</div>

	<div style="display: flex; flex-direction: column; gap: 16px;">
		<!-- SLUG field (create mode only) -->
		{#if mode === 'create'}
			<div>
				<label
					for="wiki-slug"
					style="display: block; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); margin-bottom: 4px;"
				>
					SLUG
				</label>
				<input
					id="wiki-slug"
					type="text"
					bind:value={slug}
					placeholder="e.g. agent-overview"
					style="{inputStyle}{fieldErrors.slug ? inputErrorStyle : ''}"
					onfocus={(e) => { (e.currentTarget as HTMLInputElement).style.cssText += inputFocusStyle; }}
					onblur={(e) => { (e.currentTarget as HTMLInputElement).style.cssText = inputStyle + (fieldErrors.slug ? inputErrorStyle : ''); }}
				/>
				{#if fieldErrors.slug}
					<p
						style="margin: 4px 0 0 0; font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055;"
					>
						{fieldErrors.slug}
					</p>
				{/if}
			</div>
		{:else}
			<div>
				<!-- Readonly slug display in edit mode — use span+output (not label) since there is no associated form control -->
				<span
					id="wiki-slug-label"
					style="display: block; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); margin-bottom: 4px;"
				>
					SLUG
				</span>
				<output
					aria-labelledby="wiki-slug-label"
					style="display: block; font-family: var(--l2-font-mono); font-size: 12px; color: var(--l2-fg-3); padding: 8px 12px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 2px;"
				>
					{initialSlug}
					<span style="margin-left: 8px; color: var(--l2-fg-3); font-size: 11px;">(slug is immutable)</span>
				</output>
			</div>
		{/if}

		<!-- TITLE field -->
		<div>
			<label
				for="wiki-title"
				style="display: block; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); margin-bottom: 4px;"
			>
				TITLE
			</label>
			<input
				id="wiki-title"
				type="text"
				bind:value={title}
				placeholder="Page title"
				required
				style="{inputStyle}{fieldErrors.title ? inputErrorStyle : ''}"
				onfocus={(e) => { (e.currentTarget as HTMLInputElement).style.cssText += inputFocusStyle; }}
				onblur={(e) => { (e.currentTarget as HTMLInputElement).style.cssText = inputStyle + (fieldErrors.title ? inputErrorStyle : ''); }}
			/>
			{#if fieldErrors.title}
				<p
					style="margin: 4px 0 0 0; font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055;"
				>
					{fieldErrors.title}
				</p>
			{/if}
		</div>

		<!-- CONTENT textarea (Inter 400, min-height 240px) -->
		<div>
			<label
				for="wiki-content"
				style="display: block; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); margin-bottom: 4px;"
			>
				CONTENT
			</label>
			<textarea
				id="wiki-content"
				bind:value={body}
				placeholder="Write page content in markdown..."
				style="{inputStyle} min-height: 240px; resize: vertical; line-height: 1.5;{fieldErrors.body ? inputErrorStyle : ''}"
				onfocus={(e) => { (e.currentTarget as HTMLTextAreaElement).style.cssText += inputFocusStyle; }}
				onblur={(e) => { (e.currentTarget as HTMLTextAreaElement).style.cssText = inputStyle + ' min-height: 240px; resize: vertical; line-height: 1.5;' + (fieldErrors.body ? inputErrorStyle : ''); }}
			></textarea>
			{#if fieldErrors.body}
				<p
					style="margin: 4px 0 0 0; font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055;"
				>
					{fieldErrors.body}
				</p>
			{/if}
		</div>

		<!-- LAYER select -->
		<div>
			<label
				for="wiki-layer"
				style="display: block; font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--l2-fg-2); margin-bottom: 4px;"
			>
				LAYER
			</label>
			<select
				id="wiki-layer"
				bind:value={layer}
				style="{inputStyle} cursor: pointer;"
				onfocus={(e) => { (e.currentTarget as HTMLSelectElement).style.cssText += inputFocusStyle; }}
				onblur={(e) => { (e.currentTarget as HTMLSelectElement).style.cssText = inputStyle + ' cursor: pointer;'; }}
			>
				{#each layerOptions as opt (opt.value)}
					<option value={opt.value}>{opt.label}</option>
				{/each}
			</select>
		</div>

		<!-- API error -->
		{#if apiError}
			<p
				style="margin: 0; font-family: var(--l2-font-mono); font-size: 12px; color: #FF0055; padding: 8px 12px; background: rgba(255,0,85,0.08); border: 1px solid rgba(255,0,85,0.20); border-radius: 2px;"
			>
				{apiError}
			</p>
		{/if}

		<!-- Actions row: SAVE PAGE (primary) + DISCARD CHANGES (secondary) -->
		<div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
			<button
				onclick={handleSave}
				disabled={saving}
				style="background: #7F00FF; border: 1px solid rgba(127,0,255,0.6); box-shadow: 0 0 24px rgba(127,0,255,0.35); font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #FFFFFF; border-radius: 2px; padding: 8px 16px; cursor: pointer; transition: background 80ms ease; opacity: {saving ? 0.4 : 1};"
				onmouseenter={(e) => { if (!saving) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(127,0,255,0.85)'; }}
				onmouseleave={(e) => { if (!saving) (e.currentTarget as HTMLButtonElement).style.background = '#7F00FF'; }}
			>
				{saving ? 'SAVING…' : 'SAVE PAGE'}
			</button>
			<button
				onclick={handleDiscard}
				style="background: rgba(20,20,20,0.60); border: 1px solid rgba(255,255,255,0.08); font-family: var(--l2-font-sans); font-size: 14px; font-weight: 600; letter-spacing: 0.05em; color: var(--l2-fg-2); border-radius: 2px; padding: 8px 16px; cursor: pointer; transition: background 80ms ease, color 80ms ease;"
				onmouseenter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)'; (e.currentTarget as HTMLButtonElement).style.color = '#E0E0E0'; }}
				onmouseleave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(20,20,20,0.60)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--l2-fg-2)'; }}
			>
				DISCARD CHANGES
			</button>
		</div>
	</div>
</GlassPanel>
