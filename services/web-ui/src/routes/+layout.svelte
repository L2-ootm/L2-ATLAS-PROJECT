<script lang="ts">
	import '../app.css';
	import Sidebar from '$lib/components/Sidebar.svelte';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

<div style="display: flex; min-height: 100vh;">
	<Sidebar />

	<!-- Main content — offset for sidebar (collapsed = 56px) -->
	<main
		style="flex: 1; margin-left: 56px; overflow-y: auto; padding: 24px; min-height: 100vh;"
		id="main-content"
	>
		{@render children?.()}
	</main>
</div>
