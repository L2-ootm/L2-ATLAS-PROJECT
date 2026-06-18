import type { CSSProperties } from 'react';
import { CompassStar } from './filigree';

// Engraved ATLAS wordmark — Cinzel caps with an ivory-metal gradient fill and a
// bronze hairline rule, flanked by compass-stars on the lockup. Heraldic, not techno.

const engraved: CSSProperties = {
	fontFamily: 'var(--l2-font-display)',
	fontWeight: 600,
	background: 'linear-gradient(180deg, #FFFFFF 0%, #EDEAE0 46%, #C9BCA6 100%)',
	WebkitBackgroundClip: 'text',
	backgroundClip: 'text',
	color: 'transparent',
	WebkitTextFillColor: 'transparent'
};

export function Wordmark({
	fontSize = 22,
	tracking = '0.32em',
	subtitle,
	stars = false,
	style
}: {
	fontSize?: number;
	tracking?: string;
	subtitle?: string;
	stars?: boolean;
	style?: CSSProperties;
}) {
	return (
		<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, ...style }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.5 }}>
				{stars && <CompassStar size={fontSize * 0.42} />}
				<span
					style={{
						...engraved,
						fontSize,
						letterSpacing: tracking,
						lineHeight: 1,
						paddingLeft: tracking // optical: compensate trailing track
					}}
				>
					ATLAS
				</span>
				{stars && <CompassStar size={fontSize * 0.42} />}
			</div>
			{subtitle && (
				<div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
					<span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, var(--atlas-bronze-soft) 40%, var(--atlas-bronze) 50%, var(--atlas-bronze-soft) 60%, transparent)' }} />
					<span
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: Math.max(7, fontSize * 0.3),
							letterSpacing: '0.34em',
							textTransform: 'uppercase',
							color: 'var(--atlas-bronze)',
							whiteSpace: 'nowrap'
						}}
					>
						{subtitle}
					</span>
					<span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, var(--atlas-bronze-soft) 40%, var(--atlas-bronze) 50%, var(--atlas-bronze-soft) 60%, transparent)' }} />
				</div>
			)}
		</div>
	);
}
