import type { ReactNode } from 'react';
import { CompassStar } from '../brand/filigree';

// Page scaffold — the shared layout primitive for every route. Consistent header
// rhythm (eyebrow · engraved title · actions), max-width, and content slot, so
// surfaces stay modular and uniform as the cockpit scales. Lightweight: pure
// layout, no state.

interface PageProps {
	/** mono bronze eyebrow (the pillar / context line) */
	eyebrow?: string;
	/** engraved page title */
	title: string;
	/** right-aligned header actions (buttons, counts) */
	actions?: ReactNode;
	/** content max width; surfaces that need full bleed pass max={null} */
	max?: number | null;
	children?: ReactNode;
}

export function Page({ eyebrow, title, actions, max = 1200, children }: PageProps) {
	return (
		<div style={{ maxWidth: max ?? undefined, margin: max ? '0 auto' : undefined }}>
			<header
				className="atlas-page-header"
				style={{
					display: 'flex',
					alignItems: 'flex-end',
					justifyContent: 'space-between',
					gap: 16,
					padding: '2px 2px 16px',
					marginBottom: 18,
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<div style={{ minWidth: 0 }}>
					{eyebrow && (
						<div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
							<CompassStar size={11} />
							<span
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 10,
									letterSpacing: '0.34em',
									textTransform: 'uppercase',
									color: 'var(--atlas-bronze)'
								}}
							>
								{eyebrow}
							</span>
						</div>
					)}
					<h1
						style={{
							fontFamily: 'var(--l2-font-display)',
							fontWeight: 600,
							fontSize: 27,
							letterSpacing: '0.08em',
							lineHeight: 1.05,
							margin: 0,
							color: 'var(--l2-fg-1)',
							whiteSpace: 'nowrap',
							overflow: 'hidden',
							textOverflow: 'ellipsis'
						}}
					>
						{title}
					</h1>
				</div>
				{actions && (
					<div
						className="atlas-page-actions"
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'flex-end',
							gap: 10,
							flex: '0 1 auto',
							flexWrap: 'wrap',
							minWidth: 0
						}}
					>
						{actions}
					</div>
				)}
			</header>
			{children}
		</div>
	);
}
