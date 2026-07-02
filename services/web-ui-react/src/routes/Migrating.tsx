import { Page } from '../components/Page';
import { GlassPanel } from '../components/hud';
import sealMark from '../brand/assets/seal.webp';

// Branded fallback for routes that do not yet have a dedicated cockpit surface.
export default function Migrating({ name, pillar }: { name: string; pillar?: string }) {
	return (
		<Page eyebrow={pillar ?? 'ATLAS'} title={name}>
			<GlassPanel accent topo="atlas" style={{ padding: '48px 36px', textAlign: 'center' }}>
				<img
					src={sealMark}
					alt=""
					aria-hidden="true"
					style={{ width: 112, height: 'auto', opacity: 0.82, marginBottom: 16 }}
				/>
				<h2
					style={{
						fontFamily: 'var(--l2-font-serif)',
						fontWeight: 600,
						fontSize: 24,
						margin: '0 0 10px',
						color: 'var(--l2-fg-1)'
					}}
				>
					This surface is being built
				</h2>
				<p
					style={{
						color: 'var(--l2-fg-3)',
						fontSize: 14,
						lineHeight: 1.6,
						margin: '0 auto',
						maxWidth: 420
					}}
				>
					Ported into the new celestial cockpit, route by route, per the page spec. The Observatory
					is live; this pillar is next in the build wave.
				</p>
			</GlassPanel>
		</Page>
	);
}
