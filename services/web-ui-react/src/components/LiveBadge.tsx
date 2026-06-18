// LiveBadge — a pulsing celestial dot signalling an active connection / live run.
// Brightness = liveness (UX-VISUAL-SPEC Law 3); cools to a static dim dot when
// disconnected so stillness reads as "nothing is happening".

export default function LiveBadge({ connected }: { connected: boolean }) {
	const color = connected ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)';
	return (
		<span
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 7,
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				letterSpacing: '0.22em',
				textTransform: 'uppercase',
				color
			}}
		>
			<span
				aria-hidden="true"
				style={{
					width: 7,
					height: 7,
					borderRadius: '50%',
					background: color,
					boxShadow: connected ? '0 0 9px var(--atlas-celestial-glow)' : 'none',
					animation: connected ? 'atlas-pulse-soft 1.4s var(--l2-ease) infinite' : 'none'
				}}
			/>
			{connected ? 'LIVE' : 'IDLE'}
		</span>
	);
}
