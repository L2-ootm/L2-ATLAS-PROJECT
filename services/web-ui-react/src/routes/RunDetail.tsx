import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Ban, Download } from 'lucide-react';
import { Page } from '../components/Page';
import { AgentBadge, GlassPanel, HudLabel, StatusBadge } from '../components/hud';
import LiveBadge from '../components/LiveBadge';
import RunTimeline from '../components/RunTimeline';
import GlowBorder from '../components/GlowBorder';
import GlassTopo from '../components/GlassTopo';
import SseEventRow, { ROW_GRID } from '../components/SseEventRow';
import { useRunStream } from '../lib/useRunStream';
import { getRun, getRunEvents, cancelRun, type Run } from '../lib/api';
import { projectAuditEvents } from '../lib/logProjection';
import { createTopoField, type TopoFieldAPI } from '../topo/topoEngine';

function isActive(status: string): boolean {
	const s = status.toUpperCase();
	return s === 'RUNNING' || s === 'PENDING';
}

function fmt(iso: string | null): string {
	if (!iso) return '—';
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('en-GB', { hour12: false });
}

export default function RunDetail() {
	const { id = '' } = useParams();
	const [run, setRun] = useState<Run | null>(null);
	const [nowTick, setNowTick] = useState(Date.now());
	const [filter, setFilter] = useState('ALL');
	const [compactDeltas, setCompactDeltas] = useState(true);
	const [confirmCancel, setConfirmCancel] = useState(false);
	const [cancelError, setCancelError] = useState<string | null>(null);
	const [exportError, setExportError] = useState<string | null>(null);

	const stream = useRunStream(id, run);
	const active = isActive(stream.status);
	const [topoPhase, setTopoPhase] = useState<'idle' | 'live' | 'release'>('idle');
	const topoWasLive = useRef(false);
	const visualTopoPhase = active ? 'live' : topoPhase;

	useEffect(() => {
		if (active) {
			topoWasLive.current = true;
			setTopoPhase('live');
			return;
		}
		if (topoWasLive.current) {
			setTopoPhase('release');
			const t = setTimeout(() => {
				topoWasLive.current = false;
				setTopoPhase('idle');
			}, 1400);
			return () => clearTimeout(t);
		}
		setTopoPhase('idle');
	}, [active]);

	// Fetch the run record for header metadata (mission link, timestamps).
	useEffect(() => {
		let alive = true;
		getRun(id)
			.then((r) => alive && setRun(r.run))
			.catch(() => {});
		return () => {
			alive = false;
		};
	}, [id]);

	// 1s tick so live elapsed advances.
	useEffect(() => {
		if (!active) return;
		const t = setInterval(() => setNowTick(Date.now()), 1000);
		return () => clearInterval(t);
	}, [active]);

	// ── Dedicated topo field behind the audit stream (sonar-ping on events) ────
	const fieldHostRef = useRef<HTMLDivElement>(null);
	const fieldRef = useRef<TopoFieldAPI | null>(null);
	const reducedMotion = useRef(false);
	useEffect(() => {
		const host = fieldHostRef.current;
		if (!host) return;
		reducedMotion.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reducedMotion.current) return;
		const build = () => {
			fieldRef.current?.destroy();
			const W = host.clientWidth || 600;
			const H = host.clientHeight || 400;
			fieldRef.current = createTopoField({
				host,
				viewW: W,
				viewH: H,
				cellSize: 16,
				color: 'rgba(150,170,210,1)',
				glowColor: 'rgba(79,139,255,0.85)',
				restingOpacity: 0.08,
				glowOpacity: 0.58,
				glowWidth: 1.25,
				bulgeStrength: 0.62,
				freq: 0.012
			});
		};
		build();
		const ro = new ResizeObserver(build);
		ro.observe(host);
		return () => {
			ro.disconnect();
			fieldRef.current?.destroy();
			fieldRef.current = null;
		};
	}, []);

	// ── Auto-scroll: hold the head while pinned to the bottom ──────────────────
	const scrollRef = useRef<HTMLDivElement>(null);
	const pinned = useRef(true);
	const prevLen = useRef(0);

	useEffect(() => {
		const el = scrollRef.current;
		if (!el) return;
		// Sonar-ping at the bottom region where the new row lands.
		if (stream.events.length > prevLen.current && fieldRef.current && !reducedMotion.current) {
			const host = fieldHostRef.current;
			if (host) fieldRef.current.sonarPing(host.clientWidth * 0.22, host.clientHeight * 0.86, 'rgba(79,139,255,0.9)');
		}
		prevLen.current = stream.events.length;
		if (pinned.current) {
			requestAnimationFrame(() => {
				if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
			});
		}
	}, [stream.events, topoPhase]);

	function onScroll() {
		const el = scrollRef.current;
		if (!el) return;
		pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
	}

	const eventTypes = useMemo(
		() => ['ALL', ...Array.from(new Set(stream.events.map((e) => e.event_type.toUpperCase())))],
		[stream.events]
	);
	const projectedEvents = useMemo(() => projectAuditEvents(stream.events), [stream.events]);
	const visible = useMemo(() => {
		const source = compactDeltas
			? projectedEvents
			: stream.events.map((event) => projectAuditEvents([event])[0]);
		return filter === 'ALL'
			? source
			: source.filter((item) => item.event.event_type.toUpperCase() === filter);
	}, [compactDeltas, filter, projectedEvents, stream.events]);

	const elapsed = useMemo(() => {
		if (!run) return '—';
		const start = Date.parse(run.started_at);
		if (Number.isNaN(start)) return '—';
		const end = stream.finishedAt ? Date.parse(stream.finishedAt) : run.finished_at ? Date.parse(run.finished_at) : nowTick;
		const sec = Math.max(0, (end - start) / 1000);
		return sec < 60 ? `${sec.toFixed(1)}s` : `${Math.floor(sec / 60)}m ${Math.floor(sec % 60)}s`;
	}, [run, stream.finishedAt, nowTick]);

	async function doCancel() {
		if (!run) return;
		setCancelError(null);
		try {
			await cancelRun(run.mission_id);
			setConfirmCancel(false);
		} catch (e) {
			setCancelError(`CANCEL FAILED — ${e instanceof Error ? e.message : String(e)}`);
		}
	}

	async function exportJsonl() {
		if (!run) return;
		setExportError(null);
		try {
			let cursor: number | undefined;
			let all: typeof stream.events = [];
			let truncated = false;
			const MAX = 100; // 1000/page → cap at 100k events
			for (let i = 0; ; i++) {
				if (i >= MAX) {
					truncated = true;
					break;
				}
				const res = await getRunEvents(run.id, cursor, 1000);
				all = [...all, ...res.events];
				if (!res.next_cursor || res.events.length === 0) break;
				cursor = res.next_cursor;
			}
			const lines = all.map((e) => JSON.stringify(e));
			if (truncated) {
				lines.push(JSON.stringify({ _export_warning: `TRUNCATED — pagination cap reached after ${all.length} events` }));
				setExportError(`EXPORT TRUNCATED — pagination cap reached after ${all.length} events.`);
			}
			const blob = new Blob([lines.join('\n')], { type: 'application/x-ndjson' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `run-${run.id}-audit.jsonl`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			setExportError(`EXPORT FAILED — ${e instanceof Error ? e.message : String(e)}`);
		}
	}

	return (
		<Page
			eyebrow="MISSION · RUN"
			title={run ? run.id.slice(0, 8) : 'Run'}
			max={null}
			actions={
				<>
					{active && (
						<ActionBtn icon={<Ban size={15} strokeWidth={1.5} />} danger onClick={() => setConfirmCancel(true)}>
							Cancel run
						</ActionBtn>
					)}
					{!active && stream.status && (
						<ActionBtn icon={<Download size={15} strokeWidth={1.5} />} onClick={exportJsonl}>
							Export JSONL
						</ActionBtn>
					)}
				</>
			}
		>
			{/* header */}
			<GlassTopo tone={active ? 'good' : 'info'} accent padding="18px 22px" style={{ marginBottom: 14 }}>
				<div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', marginBottom: 14 }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums' }}>
						{run?.id ?? id}
					</span>
					{run && (
						<Link to={`/missions/${run.mission_id}`} style={{ color: 'var(--atlas-celestial)', fontSize: 13, textDecoration: 'none', fontFamily: 'var(--l2-font-mono)' }}>
							↳ {run.mission_id.slice(0, 8)}
						</Link>
					)}
					<StatusBadge status={stream.status} />
					{run?.agent_runtime && <AgentBadge agent={run.agent_runtime} />}
					{run && (
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
							STARTED {fmt(run.started_at)}
						</span>
					)}
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums', marginLeft: 'auto' }}>
						{elapsed}
					</span>
					<LiveBadge connected={stream.connected} />
				</div>
				<RunTimeline status={stream.status} />
			</GlassTopo>

			{confirmCancel && (
				<GlassPanel glow="bad" style={{ padding: 16, marginBottom: 12 }}>
					<p style={{ margin: '0 0 12px', color: 'var(--l2-fg-1)', fontSize: 14, lineHeight: 1.5 }}>
						CONFIRM CANCEL: this halts ALL active runs of this mission (not just this one). Irreversible.
					</p>
					{cancelError && (
						<p style={{ margin: '0 0 10px', fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-error)' }}>{cancelError}</p>
					)}
					<div style={{ display: 'flex', gap: 10 }}>
						<ActionBtn danger onClick={doCancel}>Confirm cancel</ActionBtn>
						<ActionBtn onClick={() => { setConfirmCancel(false); setCancelError(null); }}>Keep run</ActionBtn>
					</div>
				</GlassPanel>
			)}

			{exportError && (
				<GlassPanel glow="bad" style={{ padding: '10px 14px', marginBottom: 12 }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-error)' }}>{exportError}</span>
				</GlassPanel>
			)}

			{/* controls */}
			<div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
				<HudLabel>AUDIT STREAM</HudLabel>
				<button
					type="button"
					onClick={() => setCompactDeltas((value) => !value)}
					aria-pressed={compactDeltas}
					style={{
						marginLeft: 'auto',
						background: compactDeltas ? 'rgba(79,139,255,0.10)' : 'transparent',
						border: `1px solid ${compactDeltas ? 'rgba(79,139,255,0.38)' : 'var(--l2-hairline)'}`,
						color: compactDeltas ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10,
						letterSpacing: '0.12em',
						padding: '6px 10px',
						borderRadius: 2,
						cursor: 'pointer'
					}}
				>
					{compactDeltas ? 'DELTAS GROUPED' : 'RAW DELTAS'}
				</button>
				<select
					value={filter}
					onChange={(e) => setFilter(e.target.value)}
					aria-label="Filter by event type"
					style={{
						background: 'var(--l2-glass-bg-lo)',
						border: '1px solid var(--l2-hairline)',
						color: 'var(--l2-fg-2)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 11,
						letterSpacing: '0.1em',
						padding: '6px 10px',
						borderRadius: 2,
						cursor: 'pointer',
						outline: 'none'
					}}
				>
					{eventTypes.map((t) => (
						<option key={t} value={t} style={{ background: '#0A0A0A' }}>
							{t}
						</option>
					))}
				</select>
			</div>

			{/* stream */}
			<GlowBorder active={stream.connected}>
				<div
					style={{
						position: 'relative',
						borderRadius: 2,
						background:
							visualTopoPhase === 'idle'
								? 'linear-gradient(180deg, rgba(8,9,13,0.98), rgba(5,6,9,0.99))'
								: 'linear-gradient(180deg, rgba(8,9,13,0.92), rgba(5,6,9,0.96))',
						border: stream.connected ? 'none' : '1px solid var(--l2-hairline)',
						overflow: 'hidden'
					}}
				>
					{/* topo field host — behind the log */}
					<div
						ref={fieldHostRef}
						aria-hidden="true"
						className={`atlas-audit-topo ${visualTopoPhase}`}
						style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
					/>
					{/* CRT scanline texture */}
					<div
						aria-hidden="true"
						style={{
							position: 'absolute',
							inset: 0,
							pointerEvents: 'none',
							opacity: visualTopoPhase === 'idle' ? 0.08 : 0.35,
							transition: 'opacity 600ms var(--l2-ease)',
							background: 'repeating-linear-gradient(0deg, rgba(255,255,255,0.018) 0px, rgba(255,255,255,0.018) 1px, transparent 1px, transparent 3px)'
						}}
					/>
					<div
						ref={scrollRef}
						onScroll={onScroll}
						role="log"
						aria-live="polite"
						aria-label="Audit event stream"
						style={{ position: 'relative', height: 'calc(100vh - 320px)', minHeight: 280, overflowY: 'auto' }}
					>
						{stream.streamError && (
							<div style={{ padding: '8px 14px', fontFamily: 'var(--l2-font-mono)', fontSize: 11.5, color: 'var(--l2-error)', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid rgba(255,0,85,0.2)' }}>
								{stream.streamError}
							</div>
						)}
						{stream.loading && (
							<div style={{ padding: 24 }}>
								<HudLabel style={{ fontSize: 11, color: 'var(--l2-fg-3)' }}>LOADING RUN…</HudLabel>
							</div>
						)}
						{!stream.loading && visible.length === 0 && (
							<div style={{ padding: 28, textAlign: 'center' }}>
								<HudLabel style={{ fontSize: 11, color: 'var(--l2-fg-3)', letterSpacing: '0.2em' }}>
									{active ? 'AWAITING EVENTS…' : 'NO AUDIT EVENTS RECORDED'}
								</HudLabel>
							</div>
						)}
						{visible.map((item) => (
							<SseEventRow
								key={item.id}
								event={item.event}
								group={compactDeltas ? item : undefined}
								isNew={item.members.some((event) => stream.newCursors.has(event.cursor))}
							/>
						))}
					</div>
				</div>
			</GlowBorder>

			<div style={{ marginTop: 8, fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.18em', color: 'var(--l2-fg-3)', display: 'grid', gridTemplateColumns: ROW_GRID, gap: 12, padding: '0 14px' }}>
				<span>TIME</span>
				<span>EVENT</span>
				<span>TOOL</span>
				<span style={{ textAlign: 'right' }}>DUR</span>
				<span style={{ textAlign: 'right' }}>POLICY</span>
			</div>
		</Page>
	);
}

function ActionBtn({ children, icon, onClick, danger }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void; danger?: boolean }) {
	const color = danger ? 'var(--l2-error)' : 'var(--l2-fg-2)';
	const border = danger ? 'rgba(255,0,85,0.4)' : 'var(--l2-hairline)';
	return (
		<button
			onClick={onClick}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '9px 14px',
				borderRadius: 2,
				border: `1px solid ${border}`,
				background: danger ? 'rgba(255,0,85,0.08)' : 'transparent',
				color,
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.14em',
				textTransform: 'uppercase',
				cursor: 'pointer'
			}}
		>
			{icon}
			{children}
		</button>
	);
}
