<script lang="ts">
	import '../app.css';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import TopoField from '$lib/components/TopoField.svelte';
	import {
		sidebar,
		SIDEBAR_WIDTH_COLLAPSED,
		SIDEBAR_WIDTH_EXPANDED
	} from '$lib/ui-state.svelte.js';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const offset = $derived(sidebar.expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED);
</script>

<!-- Living terrain — the world ATLAS bears, beneath everything -->
<TopoField />

<div style="display: flex; min-height: 100vh; position: relative; z-index: 1;">
	<Sidebar />

	<!-- Main content — offset tracks the fixed sidebar width -->
	<main
		style="flex: 1; margin-left: {offset}px; overflow-y: auto; padding: 24px 32px; min-height: 100vh; transition: margin-left 150ms var(--l2-ease);"
		id="main-content"
	>
		{@render children?.()}
	</main>
</div>
