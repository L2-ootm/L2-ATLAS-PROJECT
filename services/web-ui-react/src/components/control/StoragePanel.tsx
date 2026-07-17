import { useState } from 'react';
import { ArchiveX, CalendarClock, Database, ShieldCheck } from 'lucide-react';
import { purgeArchivedMissions } from '../../lib/api';
import { glassPanel } from '../../lib/glass';

type PurgeState =
	| { kind: 'idle' }
	| { kind: 'confirm' }
	| { kind: 'running' }
	| { kind: 'done'; deleted: number }
	| { kind: 'error' };

export function StoragePanel() {
	const [purge, setPurge] = useState<PurgeState>({ kind: 'idle' });

	async function runPurge() {
		setPurge({ kind: 'running' });
		try {
			const result = await purgeArchivedMissions();
			setPurge({ kind: 'done', deleted: result.deleted });
		} catch {
			setPurge({ kind: 'error' });
		}
	}

	return (
		<div style={{ display: 'grid', gap: 16 }}>
			<section style={{ ...glassPanel(), padding: 20 }}>
				<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
					<Database size={15} strokeWidth={1.5} color="var(--atlas-bronze)" />
					<span style={label}>RUN HISTORY RETENTION</span>
				</div>
				<p style={copy}>
					ATLAS keeps session runs and their audit evidence until the owning mission is archived and its retention deadline passes.
					Compiled observations remain available, with deleted run links detached cleanly.
				</p>

				<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, marginTop: 18 }}>
					<PolicyCard icon={<CalendarClock size={14} />} title="MISSION DEADLINE" value="PER ARCHIVE" tone="var(--atlas-celestial)" />
					<PolicyCard icon={<ShieldCheck size={14} />} title="ACTIVE SESSIONS" value="PROTECTED" tone="var(--atlas-cyan)" />
					<PolicyCard icon={<ArchiveX size={14} />} title="AUTO / DATE FILTERS" value="PLANNED" tone="var(--l2-fg-3)" />
				</div>
			</section>

			<section style={{ ...glassPanel(), padding: 20 }}>
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 20 }}>
					<div>
						<div style={{ ...label, marginBottom: 7 }}>PURGE DUE ARCHIVES</div>
						<p style={{ ...copy, maxWidth: 650 }}>
							Deletes only archived missions whose configured deadline is already due, including their raw run events, tool records,
							artifacts, approvals, and contract snapshots. This action cannot be undone.
						</p>
					</div>
					{purge.kind !== 'confirm' && (
						<button type="button" onClick={() => setPurge({ kind: 'confirm' })} disabled={purge.kind === 'running'} style={button(false)}>
							REVIEW PURGE
						</button>
					)}
				</div>

				{purge.kind === 'confirm' && (
					<div style={{ marginTop: 16, padding: 14, border: '1px solid rgba(255,183,77,0.35)', background: 'rgba(255,183,77,0.055)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
						<span style={{ ...copy, color: 'var(--l2-fg-2)' }}>Confirm deletion of every archive whose retention deadline has passed.</span>
						<span style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
							<button type="button" onClick={() => setPurge({ kind: 'idle' })} style={button(false)}>CANCEL</button>
							<button type="button" onClick={() => void runPurge()} style={button(true)}>PURGE DUE NOW</button>
						</span>
					</div>
				)}

				{purge.kind === 'running' && <Notice>Running the retention transaction…</Notice>}
				{purge.kind === 'done' && <Notice>{purge.deleted} archived mission{purge.deleted === 1 ? '' : 's'} purged.</Notice>}
				{purge.kind === 'error' && <Notice error>Retention purge failed. No partial deletion was committed.</Notice>}
			</section>
		</div>
	);
}

function PolicyCard({ icon, title, value, tone }: { icon: React.ReactNode; title: string; value: string; tone: string }) {
	return (
		<div style={{ border: '1px solid var(--l2-hairline)', background: 'rgba(4,7,12,0.34)', padding: 13 }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--l2-fg-3)', marginBottom: 8 }}>{icon}<span style={{ ...label, color: 'var(--l2-fg-3)', fontSize: 9 }}>{title}</span></div>
			<div style={{ ...label, color: tone, fontSize: 11 }}>{value}</div>
		</div>
	);
}

function Notice({ children, error = false }: { children: React.ReactNode; error?: boolean }) {
	return <div style={{ marginTop: 14, ...label, color: error ? 'var(--l2-error)' : 'var(--atlas-cyan)' }}>{children}</div>;
}

const label: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.16em',
	color: 'var(--atlas-bronze)'
};

const copy: React.CSSProperties = {
	margin: 0,
	fontSize: 12.5,
	lineHeight: 1.65,
	color: 'var(--l2-fg-3)'
};

function button(danger: boolean): React.CSSProperties {
	return {
		border: `1px solid ${danger ? 'rgba(255,183,77,0.5)' : 'var(--l2-hairline)'}`,
		background: danger ? 'rgba(255,183,77,0.1)' : 'rgba(79,139,255,0.06)',
		color: danger ? 'var(--l2-warning)' : 'var(--atlas-celestial)',
		fontFamily: 'var(--l2-font-mono)',
		fontSize: 9.5,
		letterSpacing: '0.13em',
		padding: '8px 11px',
		cursor: 'pointer',
		whiteSpace: 'nowrap'
	};
}
