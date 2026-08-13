import { useCallback, useEffect, useState } from 'react';
import { Notebook, Pin, PinOff, Trash2, Wind } from 'lucide-react';
import {
	deleteScratchpadEntry,
	listScratchpad,
	setScratchpadPinned,
	sweepScratchpad,
	type ScratchpadEntry,
	type ScratchpadView
} from '../../lib/api';
import { glassPanel } from '../../lib/glass';

// ── Disposables — what the agent is holding, and for how long ─────────────────
// The scratchpad is durable working memory plus generated one-off tools. Without
// this panel both are invisible to the operator: plans live only in the DB and a
// materialized script is a file under <ATLAS home>/scratch/tools that nothing
// surfaces. Pin promotes an entry out of disposability; sweep purges what has
// expired (pinned entries always survive, so sweep can never destroy a keeper).

const EMPTY: ScratchpadView = { entries: [], count: 0, pinned: 0, tools: 0 };

/** Bronze for durable, cyan for tools, dim for ordinary notes. */
function kindTone(kind: string): string {
	if (kind === 'tool') return 'var(--atlas-cyan)';
	if (kind === 'plan' || kind === 'finding') return 'var(--atlas-celestial)';
	return 'var(--l2-fg-3)';
}

/** A TTL reads as risk of loss, so name what it means, not what it is called. */
function ttlLabel(entry: ScratchpadEntry): string {
	if (entry.pinned) return 'KEPT';
	switch (entry.ttl_policy) {
		case 'permanent':
			return 'PERMANENT';
		case 'next_startup':
			return 'UNTIL RESTART';
		case 'hours':
			return entry.expires_at ? `UNTIL ${entry.expires_at.slice(0, 16).replace('T', ' ')}` : 'HOURS';
		case 'run':
			return 'WITH ITS RUN';
		default:
			return 'WITH ITS SESSION';
	}
}

export function DisposablesPanel() {
	const [view, setView] = useState<ScratchpadView>(EMPTY);
	const [busyId, setBusyId] = useState<string | null>(null);
	const [sweeping, setSweeping] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		setView(await listScratchpad());
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	async function act(id: string, run: () => Promise<unknown>) {
		setBusyId(id);
		setErr(null);
		try {
			await run();
			await refresh();
		} catch {
			setErr('The gateway rejected that. Is it running, and is this build current?');
		} finally {
			setBusyId(null);
		}
	}

	async function sweep() {
		setSweeping(true);
		setErr(null);
		try {
			await sweepScratchpad();
			await refresh();
		} catch {
			setErr('Sweep failed — the gateway could not reach the ATLAS CLI.');
		} finally {
			setSweeping(false);
		}
	}

	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Notebook size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={label}>SCRATCHPAD & DISPOSABLES</span>
				<span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
					<span style={{ ...label, color: 'var(--l2-fg-3)', fontSize: 10 }}>
						{view.count} ENTRIES · {view.tools} TOOLS · {view.pinned} KEPT
					</span>
					<button type="button" onClick={() => void sweep()} disabled={sweeping} style={sweepButton}>
						<Wind size={11} strokeWidth={1.6} />
						{sweeping ? 'SWEEPING…' : 'SWEEP EXPIRED'}
					</button>
				</span>
			</header>

			{view.entries.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6 }}>
					Nothing held. ATLAS writes plans and findings here during a run, and materializes one-off
					scripts under <code style={code}>&lt;ATLAS home&gt;/scratch/tools</code> when a missing
					capability blocks it. Both expire on their own unless pinned.
				</div>
			) : (
				view.entries.map((entry, i) => (
					<div
						key={entry.id}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '13px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
							<span
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 8.5,
									letterSpacing: '0.16em',
									color: kindTone(entry.kind),
									border: `1px solid ${kindTone(entry.kind)}`,
									borderRadius: 2,
									padding: '1px 6px',
									textTransform: 'uppercase',
									flexShrink: 0
								}}
							>
								{entry.kind}
							</span>
							<span style={{ color: 'var(--l2-fg-1)', fontSize: 13, wordBreak: 'break-word' }}>
								{entry.title || entry.id}
							</span>
							{entry.path && (
								<span
									style={{
										fontFamily: 'var(--l2-font-mono)',
										fontSize: 10,
										color: 'var(--l2-fg-3)',
										wordBreak: 'break-all'
									}}
									title={entry.path}
								>
									{entry.path.split(/[\\/]/).pop()}
								</span>
							)}
						</div>
						<div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
							<span style={{ ...label, fontSize: 9.5, color: entry.pinned ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)' }}>
								{ttlLabel(entry)} · {entry.chars}C
							</span>
							<button
								type="button"
								aria-label={entry.pinned ? `Unpin ${entry.id}` : `Pin ${entry.id}`}
								disabled={busyId === entry.id}
								onClick={() => void act(entry.id, () => setScratchpadPinned(entry.id, !entry.pinned))}
								style={iconButton(entry.pinned ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)')}
							>
								{entry.pinned ? <PinOff size={12} strokeWidth={1.6} /> : <Pin size={12} strokeWidth={1.6} />}
							</button>
							<button
								type="button"
								aria-label={`Delete ${entry.id}`}
								disabled={busyId === entry.id}
								onClick={() => void act(entry.id, () => deleteScratchpadEntry(entry.id))}
								style={iconButton('var(--l2-error)')}
							>
								<Trash2 size={12} strokeWidth={1.6} />
							</button>
						</div>
					</div>
				))
			)}

			{err && (
				<div style={{ padding: '10px 18px', ...label, fontSize: 10, color: 'var(--l2-error)' }}>{err}</div>
			)}
		</section>
	);
}

const label: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.22em',
	color: 'var(--atlas-bronze)'
};

const code: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	color: 'var(--atlas-celestial)'
};

const sweepButton: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 6,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(79,139,255,0.06)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.13em',
	padding: '6px 10px',
	cursor: 'pointer',
	whiteSpace: 'nowrap'
};

function iconButton(tone: string): React.CSSProperties {
	return {
		display: 'inline-flex',
		alignItems: 'center',
		justifyContent: 'center',
		border: '1px solid var(--l2-hairline)',
		background: 'transparent',
		color: tone,
		padding: '5px 7px',
		cursor: 'pointer'
	};
}
