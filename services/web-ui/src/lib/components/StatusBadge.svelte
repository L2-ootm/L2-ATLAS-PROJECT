<script lang="ts">
	interface Props {
		status: string;
	}

	let { status }: Props = $props();

	interface BadgeStyle {
		background: string;
		border: string;
		color: string;
	}

	function getBadgeStyle(s: string): BadgeStyle {
		const upper = s.toUpperCase();
		switch (upper) {
			case 'PENDING':
				return {
					background: 'rgba(127,0,255,0.35)',
					border: 'rgba(127,0,255,0.35)',
					color: '#7F00FF'
				};
			case 'RUNNING':
				return {
					background: 'rgba(0,240,255,0.12)',
					border: 'rgba(0,240,255,0.35)',
					color: '#00F0FF'
				};
			case 'SUCCEEDED':
				return {
					background: 'rgba(0,255,148,0.12)',
					border: 'rgba(0,255,148,0.30)',
					color: '#00FF94'
				};
			case 'FAILED':
				return {
					background: 'rgba(255,0,85,0.12)',
					border: 'rgba(255,0,85,0.30)',
					color: '#FF0055'
				};
			case 'PARTIAL':
				return {
					background: 'rgba(255,214,0,0.12)',
					border: 'rgba(255,214,0,0.30)',
					color: '#FFD600'
				};
			default:
				return {
					background: 'rgba(255,255,255,0.05)',
					border: 'rgba(255,255,255,0.08)',
					color: '#A0A0A0'
				};
		}
	}

	const style = $derived(getBadgeStyle(status));
</script>

<span
	style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; padding: 4px 8px; border-radius: 4px; border: 1px solid {style.border}; background: {style.background}; color: {style.color};"
>
	{status.toUpperCase()}
</span>
