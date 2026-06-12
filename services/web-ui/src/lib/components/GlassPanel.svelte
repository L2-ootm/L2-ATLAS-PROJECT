<script lang="ts">
	interface Props {
		class?: string;
		style?: string;
		children?: import('svelte').Snippet;
	}

	let { class: className = '', style: extraStyle = '', children }: Props = $props();
</script>

<div
	class={className}
	style="background: rgba(20,20,20,0.60); border: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(12px) saturate(1.4); border-radius: 2px; {extraStyle}"
>
	{@render children?.()}
</div>
