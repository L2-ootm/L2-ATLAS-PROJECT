// MockModeBanner — a small, unmissable strip telling the operator that the
// active provider has no configured credentials, so the run pipeline is
// using the deterministic mock provider (atlas_runtime/agents/mock.py). The
// banner renders nothing when a real provider is configured (UX-VISUAL-SPEC
// Law 5: nothing stays lit without cause).

interface MockModeBannerProps {
	mockMode: boolean;
}

export default function MockModeBanner({ mockMode }: MockModeBannerProps) {
	if (!mockMode) {
		return null;
	}
	return (
		<div
			role="status"
			style={{
				display: 'flex',
				alignItems: 'center',
				gap: 8,
				padding: '6px 14px',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				color: 'var(--l2-warning)',
				background: 'rgba(255, 214, 0, 0.08)',
				borderBottom: '1px solid rgba(255, 214, 0, 0.28)'
			}}
		>
			<span
				aria-hidden="true"
				style={{
					width: 6,
					height: 6,
					borderRadius: '50%',
					background: 'var(--l2-warning)'
				}}
			/>
			MOCK MODE — no live model
		</div>
	);
}
