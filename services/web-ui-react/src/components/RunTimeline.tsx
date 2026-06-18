import { StatusBadge } from './hud';

// RunTimeline — the lifecycle rail (pending → running → terminal). A thin track
// whose fill + glow track the run status: celestial while running, cyan on
// success, red on failure, amber on partial. Pure presentation of status.

function fillFor(status: string): { pct: number; color: string; glow: boolean } {
	switch (status.toUpperCase()) {
		case 'PENDING':
			return { pct: 12, color: '#A17BFF', glow: false };
		case 'RUNNING':
			return { pct: 55, color: 'var(--atlas-celestial)', glow: true };
		case 'SUCCEEDED':
		case 'COMPLETED':
			return { pct: 100, color: '#46F0E0', glow: false };
		case 'FAILED':
			return { pct: 100, color: '#FF4D7D', glow: false };
		case 'CANCELLED':
		case 'CANCELED':
			return { pct: 100, color: '#C77', glow: false };
		case 'PARTIAL':
			return { pct: 100, color: '#FFD600', glow: false };
		default:
			return { pct: 0, color: 'var(--l2-fg-3)', glow: false };
	}
}

export default function RunTimeline({ status }: { status: string }) {
	const f = fillFor(status);
	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
			<div
				style={{
					position: 'relative',
					flex: 1,
					height: 3,
					borderRadius: 2,
					background: 'var(--l2-fg-ghost)',
					overflow: 'hidden'
				}}
			>
				<div
					style={{
						position: 'absolute',
						inset: 0,
						width: `${f.pct}%`,
						background: f.color,
						boxShadow: f.glow ? `0 0 10px ${f.color}` : 'none',
						transition: 'width var(--l2-duration-md, 250ms) var(--l2-ease)',
						animation: f.glow ? 'atlas-pulse-soft 1.8s var(--l2-ease) infinite' : 'none'
					}}
				/>
			</div>
			<StatusBadge status={status} />
		</div>
	);
}
