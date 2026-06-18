import { Page } from '../components/Page';
import { GlassPanel } from '../components/hud';
import sealMark from '../brand/assets/seal.webp';

// Console — the conversational operator surface. Reserved in the IA now so the
// navigation is forward-compatible; the interactive surface arrives in v1.1
// (outside the 10.0.3 launch wedge). Branded seal empty-state, not a stub.
export default function Console() {
	return (
		<Page eyebrow="MISSION · CONSOLE" title="Console">
			<GlassPanel accent topo="atlas" glow="ai" style={{ padding: '48px 36px', textAlign: 'center' }}>
				<img src={sealMark} alt="" aria-hidden="true" style={{ width: 112, opacity: 0.82, marginBottom: 16 }} />
				<h2 style={{ fontFamily: 'var(--l2-font-serif)', fontWeight: 600, fontSize: 24, margin: '0 0 10px', color: 'var(--l2-fg-1)' }}>
					Conversational operator surface
				</h2>
				<p style={{ color: 'var(--l2-fg-3)', fontSize: 14, lineHeight: 1.6, margin: '0 auto', maxWidth: 460 }}>
					Drive missions in natural language — author intent, steer runs, and interrogate the audit
					trail in a single thread. Arriving in v1.1.
				</p>
			</GlassPanel>
		</Page>
	);
}
