import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/hud';
import TopoInput from '../components/TopoInput';
import { listRuns, getRunEvents, type AuditEvent } from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import { projectAuditEvents, type AuditLogItem } from '../lib/logProjection';
import sealMark from '../brand/assets/seal.webp';

// ── Ledger — /audit — the cross-run forensic explorer ────────────────────────
// "Every action accounted for." A unified, filterable view across recent runs'
// audit events. INTERIM data source (HARNESS-WIRING §5): the gateway has no
// GET /v1/audit/events yet, so this fans out listRuns → getRunEvents and flattens,
// bounded by RUN_FANOUT × EVENTS_PER_RUN. Replace with the real endpoint when it
// ships — the table/drawer/filter UI is endpoint-agnostic.

const RUN_FANOUT = 40; // recent runs to scan
const EVENTS_PER_RUN = 80; // cap per run so a hot run can't dominate

/** An audit event joined to the run + mission it belongs to (ledger row shape). */
interface LedgerEvent extends AuditEvent {
	mission_title: string;
}

type Load =
	| { s: 'loading' }
	| { s: 'ready'; events: LedgerEvent[] }
	| { s: 'error' };

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

// Semantic tone per event_type / policy_result (UX-VISUAL-SPEC Law 4).
function eventTone(ev: AuditEvent): string {
	const p = (ev.policy_result ?? '').toLowerCase();
	if (p === 'deny' || p === 'denied' || p === 'blocked') return 'var(--l2-error)';
	const t = ev.event_type.toLowerCase();
	if (t.includes('fail') || t.includes('error')) return 'var(--l2-error)';
	if (t.includes('tool')) return 'var(--atlas-celestial)';
	if (t.includes('model') || t.includes('llm')) return '#A17BFF';
	if (t.includes('complete') || t.includes('succeed')) return 'var(--atlas-cyan)';
	return 'var(--l2-fg-3)';
}

export default function Ledger() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [query, setQuery] = useState('');
	const [typeFilter, setTypeFilter] = useState('ALL');
	const [policyOnly, setPolicyOnly] = useState(false);
	const [selected, setSelected] = useState<AuditLogItem<LedgerEvent> | null>(null);
	const { epoch } = useGatewayHealth();
	const nav = useNavigate();

	const refresh = useCallback(async () => {
		try {
			const { runs } = await listRuns(RUN_FANOUT);
			const settled = await Promise.allSettled(
				runs.map((r) => getRunEvents(r.id, 0, EVENTS_PER_RUN))
			);
			const events: LedgerEvent[] = [];
			settled.forEach((res, i) => {
				if (res.status !== 'fulfilled') return;
				for (const ev of res.value.events) {
					events.push({ ...ev, mission_title: runs[i].mission_title });
				}
			});
			events.sort((a, b) => b.cursor - a.cursor);
			setLoad({ s: 'ready', events });
		} catch {
			setLoad({ s: 'error' });
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh, epoch]);

	const eventTypes = useMemo(() => {
		if (load.s !== 'ready') return ['ALL'];
		const set = new Set<string>();
		for (const ev of load.events) set.add(ev.event_type);
		return ['ALL', ...[...set].sort()];
	}, [load]);
	const projected = useMemo(
		() => (load.s === 'ready' ? projectAuditEvents(load.events) : []),
		[load]
	);

	const filtered = useMemo(() => {
		const q = query.trim().toLowerCase();
		return projected.filter((item) => {
			const ev = item.event;
			if (typeFilter !== 'ALL' && ev.event_type !== typeFilter) return false;
			if (policyOnly && !ev.policy_result) return false;
			if (q === '') return true;
			return (
				ev.event_type.toLowerCase().includes(q) ||
				(ev.tool_name ?? '').toLowerCase().includes(q) ||
				ev.run_id.toLowerCase().includes(q) ||
				ev.mission_title.toLowerCase().includes(q) ||
				item.text.toLowerCase().includes(q) ||
				(ev.policy_result ?? '').toLowerCase().includes(q)
			);
		});
	}, [policyOnly, projected, query, typeFilter]);

	const total = load.s === 'ready' ? load.events.length : null;

	return (
		<Page
			eyebrow="AUDIT"
			title="Ledger"
			actions={
				<span style={mono(11, 'var(--l2-fg-3)')}>
					{total === null ? '—' : `${filtered.length} ROWS · ${total} EVENTS`}
				</span>
			}
		>
			{/* filter rail */}
			<div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
				<div style={{ flex: 1, minWidth: 240 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Filter events — type, tool, run, mission…"
						ariaLabel="Filter audit events"
						tone="info"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
				</div>
				<Chip active={policyOnly} onClick={() => setPolicyOnly((v) => !v)}>
					POLICY ONLY
				</Chip>
			</div>

			<div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
				{eventTypes.slice(0, 12).map((t) => (
					<Chip key={t} active={t === typeFilter} onClick={() => setTypeFilter(t)}>
						{t.toUpperCase()}
					</Chip>
				))}
			</div>

			{/* ledger table */}
			<GlassPanel style={{ overflow: 'hidden' }}>
				<Header />
				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' &&
					(filtered.length === 0 ? (
						<Empty hasAny={load.events.length > 0} onClear={() => { setQuery(''); setTypeFilter('ALL'); setPolicyOnly(false); }} />
					) : (
						<div style={{ maxHeight: '64vh', overflowY: 'auto' }}>
							{filtered.slice(0, 400).map((item, i) => (
								<Row key={item.id} item={item} i={i} onClick={() => setSelected(item)} />
							))}
							{filtered.length > 400 && (
								<div style={{ padding: '12px 18px', textAlign: 'center', ...mono(10.5, 'var(--l2-fg-3)') }}>
									SHOWING FIRST 400 — REFINE FILTERS TO NARROW
								</div>
							)}
						</div>
					))}
			</GlassPanel>

			{selected && (
				<Drawer item={selected} onClose={() => setSelected(null)} onOpenRun={(id) => nav(`/runs/${id}`)} />
			)}
		</Page>
	);
}

// ── table pieces ─────────────────────────────────────────────────────────────
const GRID = '64px 1fr 150px 90px 84px';

function Header() {
	return (
		<div
			style={{
				display: 'grid',
				gridTemplateColumns: GRID,
				gap: 14,
				padding: '11px 18px',
				borderBottom: '1px solid var(--l2-hairline)',
				...mono(9.5, 'var(--l2-fg-3)'),
				letterSpacing: '0.2em',
				textTransform: 'uppercase'
			}}
		>
			<span>Cursor</span>
			<span>Event · Run</span>
			<span>Tool</span>
			<span style={{ textAlign: 'right' }}>Policy</span>
			<span style={{ textAlign: 'right' }}>When</span>
		</div>
	);
}

function Row({ item, i, onClick }: { item: AuditLogItem<LedgerEvent>; i: number; onClick: () => void }) {
	const ev = item.event;
	const tone = eventTone(ev);
	return (
		<div
			role="button"
			tabIndex={0}
			data-topo="info"
			onClick={onClick}
			onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
			style={{
				display: 'grid',
				gridTemplateColumns: GRID,
				gap: 14,
				alignItems: 'center',
				padding: '12px 18px',
				borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
				cursor: 'pointer',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<span style={{ ...mono(11, 'var(--l2-fg-3)'), fontVariantNumeric: 'tabular-nums' }}>
				#{ev.cursor}
			</span>
			<span style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 9 }}>
				<span style={{ width: 6, height: 6, borderRadius: '50%', background: tone, boxShadow: `0 0 7px ${tone}`, flexShrink: 0 }} />
				<span style={{ minWidth: 0 }}>
					<div style={{ ...mono(12.5, 'var(--l2-fg-1)'), letterSpacing: '0.04em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
						{ev.event_type}{item.count > 1 ? ` ×${item.count}` : ''}
					</div>
					<div style={{ fontSize: 11.5, color: 'var(--l2-fg-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
						{ev.mission_title} · {ev.run_id.slice(0, 8)}{item.count > 1 ? ` · ${item.charCount.toLocaleString()} chars` : ''}
					</div>
				</span>
			</span>
			<span style={{ ...mono(11.5, 'var(--l2-fg-2)'), overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
				{ev.tool_name ?? '—'}
			</span>
			<span style={{ textAlign: 'right' }}>
				{ev.policy_result ? (
					<span style={{ ...mono(9.5, tone), border: `1px solid ${tone}`, borderRadius: 2, padding: '1px 6px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
						{ev.policy_result}
					</span>
				) : (
					<span style={mono(11, 'var(--l2-fg-3)')}>—</span>
				)}
			</span>
			<span style={{ textAlign: 'right', ...mono(11, 'var(--l2-fg-3)') }}>{rel(ev.timestamp)}</span>
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 8 }).map((_, i) => (
				<div key={i} style={{ display: 'grid', gridTemplateColumns: GRID, gap: 14, padding: '14px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(40)} />
					<div style={sk(`${50 + ((i * 13) % 35)}%`)} />
					<div style={sk(72)} />
					<div style={sk(48, true)} />
					<div style={sk(40, true)} />
				</div>
			))}
		</div>
	);
}

function Empty({ hasAny, onClear }: { hasAny: boolean; onClear: () => void }) {
	return (
		<div style={{ padding: '40px 24px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 100, opacity: 0.82, marginBottom: 14 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 20, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				{hasAny ? 'No events match these filters' : 'No audit events yet'}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, marginBottom: hasAny ? 14 : 0 }}>
				{hasAny ? 'Loosen the filters to see the full ledger.' : 'Launch a run — every action it takes is accounted for here.'}
			</div>
			{hasAny && (
				<button onClick={onClear} style={ghostBtn}>CLEAR FILTERS</button>
			)}
		</div>
	);
}

function Offline() {
	return (
		<div style={{ padding: '24px 18px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
			<span style={{ width: 7, height: 7, marginTop: 4, borderRadius: '50%', background: 'var(--l2-error)', boxShadow: '0 0 9px rgba(255,0,85,0.55)', flex: 'none' }} />
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 4 }}>Gateway unavailable</div>
				<div style={mono(11.5, 'var(--l2-fg-3)')}>NO RESPONSE FROM 127.0.0.1:8484 — START THE GATEWAY</div>
			</div>
		</div>
	);
}

// ── detail drawer ─────────────────────────────────────────────────────────────
function Drawer({ item, onClose, onOpenRun }: { item: AuditLogItem<LedgerEvent>; onClose: () => void; onOpenRun: (id: string) => void }) {
	const ev = item.event;
	const pretty = (() => {
		try {
			return item.count > 1
				? JSON.stringify({
					group: 'consecutive_llm_delta',
					count: item.count,
					cursor_range: [item.firstCursor, item.lastCursor],
					char_count: item.charCount,
					text: item.text,
					member_event_ids: item.members.map((member) => member.id)
				}, null, 2)
				: JSON.stringify(ev.data, null, 2);
		} catch {
			return String(ev.data);
		}
	})();
	const rows: Array<[string, string]> = [
		['Event type', item.count > 1 ? `${ev.event_type} ×${item.count}` : ev.event_type],
		['Cursor', `#${ev.cursor}`],
		...(item.count > 1 ? [['Cursor range', `#${item.firstCursor}–#${item.lastCursor}`] as [string, string]] : []),
		['Run', ev.run_id],
		['Mission', ev.mission_title],
		['Tool', ev.tool_name ?? '—'],
		['Policy', ev.policy_result ?? '—'],
		['Duration', ev.duration_ms != null ? `${ev.duration_ms} ms` : '—'],
		['Timestamp', ev.timestamp]
	];
	return (
		<div
			onClick={onClose}
			style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', justifyContent: 'flex-end', background: 'rgba(5,6,10,0.6)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				style={{
					width: 'min(560px, 94vw)',
					height: '100%',
					overflowY: 'auto',
					background: 'linear-gradient(180deg, rgba(17,20,27,0.98), rgba(10,12,17,0.98))',
					borderLeft: '1px solid var(--l2-hairline)',
					boxShadow: '-24px 0 80px rgba(0,0,0,0.55)'
				}}
			>
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--l2-hairline)', position: 'sticky', top: 0, background: 'rgba(13,16,22,0.96)', zIndex: 1 }}>
					<span style={{ ...mono(11, 'var(--atlas-bronze)'), letterSpacing: '0.22em' }}>AUDIT EVENT</span>
					<button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', display: 'flex' }}>
						<X size={16} />
					</button>
				</div>
				<div style={{ padding: 20, display: 'grid', gap: 0 }}>
					{rows.map(([k, v], i) => (
						<div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
							<span style={{ color: 'var(--l2-fg-3)', fontSize: 12.5 }}>{k}</span>
							<span style={{ ...mono(12, 'var(--l2-fg-1)'), textAlign: 'right', wordBreak: 'break-all' }}>{v}</span>
						</div>
					))}
				</div>
				<div style={{ padding: '0 20px 16px' }}>
					<button onClick={() => onOpenRun(ev.run_id)} style={{ ...ghostBtn, width: '100%' }}>
						OPEN RUN TIMELINE
					</button>
				</div>
				<div style={{ padding: '0 20px 24px' }}>
					<div style={{ ...mono(9.5, 'var(--l2-fg-3)'), letterSpacing: '0.2em', marginBottom: 8 }}>PAYLOAD</div>
					<pre
						style={{
							margin: 0,
							padding: '14px 16px',
							background: 'rgba(9,11,16,0.7)',
							border: '1px solid var(--l2-hairline)',
							borderRadius: 2,
							...mono(11.5, 'var(--l2-fg-2)'),
							lineHeight: 1.6,
							whiteSpace: 'pre-wrap',
							wordBreak: 'break-word',
							maxHeight: 360,
							overflowY: 'auto'
						}}
					>
						{pretty}
					</pre>
				</div>
			</div>
		</div>
	);
}

// ── shared bits ───────────────────────────────────────────────────────────────
function Chip({ children, active, onClick }: { children: React.ReactNode; active: boolean; onClick: () => void }) {
	return (
		<button
			onClick={onClick}
			style={{
				padding: '7px 12px',
				borderRadius: 2,
				border: `1px solid ${active ? 'rgba(79,139,255,0.4)' : 'var(--l2-hairline)'}`,
				background: active ? 'rgba(79,139,255,0.1)' : 'transparent',
				color: active ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
				...mono(10),
				letterSpacing: '0.14em',
				cursor: 'pointer'
			}}
		>
			{children}
		</button>
	);
}

const ghostBtn: React.CSSProperties = {
	padding: '9px 16px',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'transparent',
	color: 'var(--l2-fg-2)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};

const sk = (w: number | string, right = false): React.CSSProperties => ({
	height: 12,
	width: w,
	justifySelf: right ? 'end' : 'start',
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});

function mono(size: number, color?: string): React.CSSProperties {
	return { fontFamily: 'var(--l2-font-mono)', fontSize: size, ...(color ? { color } : {}) };
}
