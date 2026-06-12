<script lang="ts">
	interface Props {
		status: string;
		progress?: number;
	}

	let { status, progress = 50 }: Props = $props();

	function getFillColor(s: string): string {
		const upper = s.toUpperCase();
		switch (upper) {
			case 'RUNNING':
				return '#00F0FF';
			case 'SUCCEEDED':
				return '#00FF94';
			case 'FAILED':
				return '#FF0055';
			default:
				return 'rgba(255,255,255,0.3)';
		}
	}

	const fillColor = $derived(getFillColor(status));
	const isRunning = $derived(status.toUpperCase() === 'RUNNING');
</script>

<div
	style="
		height: 2px;
		background: rgba(255,255,255,0.08);
		border-radius: 1px;
		overflow: hidden;
		width: 100%;
	"
	role="progressbar"
	aria-valuenow={progress}
	aria-valuemin={0}
	aria-valuemax={100}
	aria-label="Run progress"
>
	<div
		class:timeline-shimmer={isRunning}
		style="
			width: {progress}%;
			height: 100%;
			background: {fillColor};
			border-radius: 1px;
			position: relative;
		"
	></div>
</div>

<style>
	.timeline-shimmer::after {
		content: '';
		position: absolute;
		top: 0;
		right: 0;
		width: 40px;
		height: 100%;
		background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.4), transparent);
		animation: shimmer 2s ease-in-out infinite;
	}

	@keyframes shimmer {
		0% {
			transform: translateX(-40px);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translateX(40px);
			opacity: 0;
		}
	}
</style>
