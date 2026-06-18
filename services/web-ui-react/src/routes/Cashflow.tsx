import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';

// ── Cashflow — vendored module surface (Decision 3b) ─────────────────────────
// First cut: the cashflow app runs as its own Next.js process (services/cashflow,
// `npm run dev` → :3000) and is embedded here. A deeper native re-skin to the
// glass design system is a later milestone. The nav entry only appears when the
// module is active (toggled in the System page).

const CASHFLOW_URL = 'http://localhost:3000';

export default function Cashflow() {
	return (
		<Page eyebrow="MODULE" title="Cashflow" max={null}>
			<div
				style={glassPanel({
					padding: '10px 14px',
					marginBottom: 12,
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					gap: 12,
					flexWrap: 'wrap'
				})}
			>
				<span style={{ color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.5 }}>
					Embedded L2-Cashflow module. Runs as its own process —
					<code
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 12,
							color: 'var(--atlas-celestial)',
							margin: '0 6px'
						}}
					>
						cd services/cashflow &amp;&amp; npm run dev
					</code>
					→ {CASHFLOW_URL}
				</span>
				<a
					href={CASHFLOW_URL}
					target="_blank"
					rel="noreferrer"
					style={{
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10.5,
						letterSpacing: '0.14em',
						textTransform: 'uppercase',
						color: 'var(--atlas-celestial)',
						textDecoration: 'none',
						border: '1px solid rgba(79,139,255,0.4)',
						borderRadius: 2,
						padding: '7px 13px'
					}}
				>
					Open in new tab ↗
				</a>
			</div>
			<iframe
				title="Cashflow"
				src={CASHFLOW_URL}
				style={{
					width: '100%',
					height: 'calc(100vh - 180px)',
					border: '1px solid var(--l2-hairline)',
					borderRadius: 2,
					background: '#0B0D12'
				}}
			/>
		</Page>
	);
}
