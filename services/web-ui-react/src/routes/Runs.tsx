import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Page } from '../components/Page';
import { AgentBadge, HudLabel, StatusBadge } from '../components/hud';
import LiveBadge from '../components/LiveBadge';
import GlowBorder from '../components/GlowBorder';
import { GlassPanel } from '../components/GlassFx';
import { listRuns, type RunWithMission } from '../lib/api';
import sealMark from '../brand/assets/seal.webp';

type Load = { s: 'loading' } | { s: 'ready'; runs: RunWithMission[] } | { s: 'error' };

// STATUS track is wide enough for a running row's two badges (RUNNING + ● LIVE)
// so they never overflow into the STARTED column.
const GRID = '104px 1fr 184px 150px 92px';
const STATUSES = ['ALL', 'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'PARTIAL'];

function isActive(status: string): boolean {
	const s = status.toUpperCase();
	return s === 'RUNNING' || s === 'PENDING';
}

function fmt(iso: string): string {
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('en-GB', { hour12: false, dateStyle: 'short', timeStyle: 'short' });
}

function duration(r: RunWithMission): string {
	const start = Date.parse(r.started_at);
	if (Number.isNaN(start)) return '—';
	const end = r.finished_at ? Date.parse(r.finished_at) : Date.now();
	const sec = Math.max(0, (end - start) / 1000);
	if (sec < 60) return `${sec.toFixed(1)}s`;
	return `${Math.floor(sec / 60)}m ${Math.floor(sec % 60)}s`;
}

export default function Runs() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [status, setStatus] = useState('ALL');
	const nav = useNavigate();

	useEffect(() => {
		let alive = true;
		listRuns(100)
			.then(({ runs }) => alive && setLoad({ s: 'ready', runs }))
			.catch(() => alive && setLoad({ s: 'error' }));
		return () => {
			alive = false;
		};
	}, []);

	const filtered = useMemo(() => {
		if (load.s !== 'ready') return [];
		return status === 'ALL' ? load.runs : load.runs.filter((r) => r.status.toUpperCase() === status);
	}, [load, status]);

	const count = load.s === 'ready' ? load.runs.length : null;

	return (
		<Page
			eyebrow="MISSION · ACTIVITY"
			title="Runs"
			actions={
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{count === null ? '—' : `${count} TOTAL`}
				</span>
			}
		>
			{/* interim-source note + filters */}
			<div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
				<HudLabel style={{ fontSize: 9.5, color: 'var(--l2-fg-3)' }}>
					AGGREGATED FROM MISSIONS — INTERIM UNTIL /v1/runs SHIPS
				</HudLabel>
				<div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
					{STATUSES.map((s) => (
						<button
							key={s}
							onClick={() => setStatus(s)}
							style={{
								padding: '7px 12px',
								borderRadius: 2,
								border: `1px solid ${s === status ? 'rgba(79,139,255,0.4)' : 'var(--l2-hairline)'}`,
								background: s === status ? 'rgba(79,139,255,0.1)' : 'transparent',
								color: s === status ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10,
								letterSpacing: '0.14em',
								cursor: 'pointer'
							}}
						>
							{s}
						</button>
					))}
				</div>
			</div>

			<GlassPanel style={{ overflow: 'hidden' }}>
				<Header />
				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' &&
					(filtered.length === 0 ? (
						<Empty hasAny={load.runs.length > 0} />
					) : (
						filtered.map((r, i) => <Row key={r.id} r={r} first={i === 0} onClick={() => nav(`/runs/${r.id}`)} />)
					))}
			</GlassPanel>
		</Page>
	);
}

function Header() {
	return (
		<div
			style={{
				display: 'grid',
				gridTemplateColumns: GRID,
				gap: 14,
				padding: '11px 18px',
				borderBottom: '1px solid var(--l2-hairline)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 9.5,
				letterSpacing: '0.2em',
				color: 'var(--l2-fg-3)',
				textTransform: 'uppercase'
			}}
		>
			<span>Run</span>
			<span>Mission</span>
			<span>Status</span>
			<span>Started</span>
			<span style={{ textAlign: 'right' }}>Duration</span>
		</div>
	);
}

function Row({ r, first, onClick }: { r: RunWithMission; first: boolean; onClick: () => void }) {
	const active = isActive(r.status);
	const inner = (
		<div
			role="button"
			tabIndex={0}
			data-topo={active ? 'info' : 'atlas'}
			onClick={onClick}
			onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
			style={{
				display: 'grid',
				gridTemplateColumns: GRID,
				gap: 14,
				alignItems: 'center',
				padding: '13px 18px',
				borderTop: first ? 'none' : '1px solid var(--l2-hairline)',
				cursor: 'pointer',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums' }}>
				{r.id.slice(0, 8)}
			</span>
			<span style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
				<span style={{ color: 'var(--l2-fg-1)', fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
					{r.mission_title}
				</span>
				{r.agent_runtime && (
					<span>
						<AgentBadge agent={r.agent_runtime} />
					</span>
				)}
			</span>
			<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
				<StatusBadge status={r.status} />
				{active && <LiveBadge connected />}
			</span>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
				{fmt(r.started_at)}
			</span>
			<span style={{ textAlign: 'right', fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums' }}>
				{duration(r)}
			</span>
		</div>
	);
	// Running rows get the electric border treatment.
	return active ? <GlowBorder active>{inner}</GlowBorder> : inner;
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 6 }).map((_, i) => (
				<div key={i} style={{ display: 'grid', gridTemplateColumns: GRID, gap: 14, padding: '15px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					{Array.from({ length: 5 }).map((__, j) => (
						<div
							key={j}
							style={{
								height: 12,
								width: j === 1 ? '60%' : 64,
								justifySelf: j === 4 ? 'end' : 'start',
								borderRadius: 2,
								background: 'var(--l2-fg-ghost)',
								animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
							}}
						/>
					))}
				</div>
			))}
		</div>
	);
}

function Empty({ hasAny }: { hasAny: boolean }) {
	return (
		<div style={{ padding: '40px 24px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 96, opacity: 0.82, marginBottom: 14 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 19, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				{hasAny ? 'No runs match this filter' : 'No runs yet'}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13 }}>
				{hasAny ? 'Adjust the status filter above.' : 'Launch a run from a mission to populate the activity stream.'}
			</div>
		</div>
	);
}

function Offline() {
	return (
		<div style={{ padding: '24px 18px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
			<span style={{ width: 7, height: 7, marginTop: 4, borderRadius: '50%', background: 'var(--l2-error)', boxShadow: '0 0 9px rgba(255,0,85,0.55)', flex: 'none' }} />
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 4 }}>Gateway unavailable</div>
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, fontFamily: 'var(--l2-font-mono)', letterSpacing: '0.04em' }}>
					NO RESPONSE FROM 127.0.0.1:8484 — START THE GATEWAY
				</div>
			</div>
		</div>
	);
}
