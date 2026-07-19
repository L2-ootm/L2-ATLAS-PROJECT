import { useEffect, useState } from 'react';
import { Page } from '../components/Page';
import { HudLabel, StatusBadge } from '../components/hud';
import GlowBorder from '../components/GlowBorder';
import { GlassPanel } from '../components/GlassFx';
import { listSurfaceSessionsDashboard } from '../lib/api';
import type {
	ActorBrief,
	HealthStatus,
	SessionDashboardEntry,
	SessionDashboardPage
} from '../lib/surfaceContracts';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import sealMark from '../brand/assets/seal.webp';

// SessionsPage (F11 — Phase 3 Track B): the cross-session operational view
// ChatActorWorkspace can't provide (it only ever shows the *current* session's
// actors). One row per surface session — health, mission brief, agent/model,
// age, actor counts — with a compact indented tree of that session's top-level
// actors. Live states first, then most-recently-active first (server-sorted).
//
// Deliberately scoped to top-level actors only (parent_actor_id IS NULL): the
// list endpoint batches actor aggregation to avoid N+1 queries across a page
// of sessions, so it does not carry full nested subtrees. A `/sessions/:id`
// detail page with the full actor tree + event stream is a deferred follow-up
// (see HANDOFF.md Part 0.6 Track B).

const LIVE_STATES = new Set(['starting', 'active', 'suspended', 'resuming', 'cancelling']);
const PAGE_SIZE = 25;

const HEALTH_COLOR: Record<HealthStatus, string> = {
	healthy: 'var(--l2-success)',
	stale: 'var(--atlas-bronze)',
	orphaned: 'var(--l2-error)',
	unknown: 'var(--l2-fg-3)'
};

type Load =
	| { s: 'loading' }
	| { s: 'ready'; page: SessionDashboardPage }
	| { s: 'error' };

function ageLabel(seconds: number | null): string {
	if (seconds === null) return '—';
	const s = Math.max(0, seconds);
	if (s < 60) return `${Math.floor(s)}s`;
	if (s < 3600) return `${Math.floor(s / 60)}m`;
	if (s < 86400) return `${Math.floor(s / 3600)}h`;
	return `${Math.floor(s / 86400)}d`;
}

function HealthDot({ health, title }: { health: HealthStatus; title?: string }) {
	return (
		<span
			data-health={health}
			title={title ?? `heartbeat: ${health}`}
			aria-label={`heartbeat ${health}`}
			style={{
				display: 'inline-block',
				width: 7,
				height: 7,
				borderRadius: '50%',
				flex: 'none',
				background: HEALTH_COLOR[health],
				boxShadow:
					health === 'healthy'
						? `0 0 6px ${HEALTH_COLOR.healthy}`
						: health === 'orphaned'
							? `0 0 6px ${HEALTH_COLOR.orphaned}`
							: 'none'
			}}
		/>
	);
}

export default function SessionsPage() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [activeOnly, setActiveOnly] = useState(false);
	const [offset, setOffset] = useState(0);
	const { epoch } = useGatewayHealth();

	useEffect(() => {
		let alive = true;
		setLoad({ s: 'loading' });
		listSurfaceSessionsDashboard({ activeOnly, limit: PAGE_SIZE, offset })
			.then((page) => alive && setLoad({ s: 'ready', page }))
			.catch(() => alive && setLoad({ s: 'error' }));
		return () => {
			alive = false;
		};
	}, [epoch, activeOnly, offset]);

	const total = load.s === 'ready' ? load.page.total : null;

	return (
		<Page
			eyebrow="MISSION · OPERATIONAL VIEW"
			title="Sessions"
			actions={
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{total === null ? '—' : `${total} SESSION${total === 1 ? '' : 'S'}`}
				</span>
			}
		>
			<div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
				<HudLabel style={{ fontSize: 9.5, color: 'var(--l2-fg-3)' }}>
					ALL SURFACES · ACTOR HEALTH PER SESSION
				</HudLabel>
				<div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
					{(['ALL', 'LIVE ONLY'] as const).map((label) => {
						const selected = label === 'LIVE ONLY' ? activeOnly : !activeOnly;
						return (
							<button
								key={label}
								onClick={() => {
									setOffset(0);
									setActiveOnly(label === 'LIVE ONLY');
								}}
								style={{
									padding: '7px 12px',
									borderRadius: 2,
									border: `1px solid ${selected ? 'rgba(79,139,255,0.4)' : 'var(--l2-hairline)'}`,
									background: selected ? 'rgba(79,139,255,0.1)' : 'transparent',
									color: selected ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 10,
									letterSpacing: '0.14em',
									cursor: 'pointer'
								}}
							>
								{label}
							</button>
						);
					})}
				</div>
			</div>

			<GlassPanel style={{ overflow: 'hidden' }}>
				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' &&
					(load.page.sessions.length === 0 ? (
						<Empty hasAny={load.page.total > 0} />
					) : (
						load.page.sessions.map((entry, i) => (
							<SessionRow key={entry.id} entry={entry} first={i === 0} />
						))
					))}
			</GlassPanel>

			{load.s === 'ready' && load.page.total > PAGE_SIZE && (
				<Pager
					offset={offset}
					limit={PAGE_SIZE}
					total={load.page.total}
					onPrev={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
					onNext={() => setOffset((o) => o + PAGE_SIZE)}
				/>
			)}
		</Page>
	);
}

function SessionRow({ entry, first }: { entry: SessionDashboardEntry; first: boolean }) {
	const live = LIVE_STATES.has(entry.state);
	const row = (
		<div
			data-topo={live ? 'info' : 'atlas'}
			style={{
				padding: '14px 18px',
				borderTop: first ? 'none' : '1px solid var(--l2-hairline)'
			}}
		>
			<div style={{ display: 'grid', gridTemplateColumns: '18px minmax(0,1.6fr) 200px 70px 150px', gap: 14, alignItems: 'center' }}>
				<HealthDot health={entry.health} />
				<span style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
					<span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
						<span
							style={{
								color: 'var(--l2-fg-1)',
								fontSize: 14,
								overflow: 'hidden',
								textOverflow: 'ellipsis',
								whiteSpace: 'nowrap'
							}}
						>
							{entry.mission_title ?? `${entry.surface.kind.toUpperCase()} · ${entry.id.slice(0, 8)}`}
						</span>
						<StatusBadge status={entry.state} />
					</span>
					{entry.mission_intent && (
						<span
							style={{
								color: 'var(--l2-fg-3)',
								fontSize: 11,
								overflow: 'hidden',
								textOverflow: 'ellipsis',
								whiteSpace: 'nowrap'
							}}
						>
							{entry.mission_intent}
						</span>
					)}
				</span>
				<span style={{ display: 'flex', flexDirection: 'column', gap: 3, fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)' }}>
					<span>{entry.agent}</span>
					<span style={{ color: 'var(--l2-fg-3)', opacity: 0.8 }}>{entry.model.model_id}</span>
				</span>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
					{ageLabel(entry.heartbeat_age_seconds)}
				</span>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)', letterSpacing: '0.06em', textAlign: 'right' }}>
					{entry.actor_count} ACTOR{entry.actor_count === 1 ? '' : 'S'}
					{entry.active_actor_count > 0 && ` · ${entry.active_actor_count} ACTIVE`}
				</span>
			</div>
			{entry.actors.length > 0 && (
				<div style={{ marginTop: 10, paddingLeft: 32, display: 'grid', gap: 6 }}>
					{entry.actors.map((actor) => (
						<ActorTreeRow key={actor.id} actor={actor} />
					))}
				</div>
			)}
		</div>
	);
	return live ? <GlowBorder active color="rgba(79,139,255,0.3)">{row}</GlowBorder> : row;
}

function ActorTreeRow({ actor }: { actor: ActorBrief }) {
	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
			<span style={{ color: 'var(--l2-fg-3)', fontFamily: 'var(--l2-font-mono)', fontSize: 10 }}>├─</span>
			<HealthDot health={actor.health} />
			<span
				style={{
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 9.5,
					letterSpacing: '0.08em',
					textTransform: 'uppercase',
					color: 'var(--l2-fg-3)',
					flex: 'none'
				}}
			>
				{actor.status}
			</span>
			<span
				style={{
					color: 'var(--l2-fg-2)',
					fontSize: 12,
					overflow: 'hidden',
					textOverflow: 'ellipsis',
					whiteSpace: 'nowrap',
					minWidth: 0
				}}
			>
				{actor.goal}
			</span>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9, color: 'var(--l2-fg-3)', flex: 'none', marginLeft: 'auto' }}>
				{actor.mode.toUpperCase()} · {ageLabel(actor.heartbeat_age_seconds)}
			</span>
		</div>
	);
}

function Pager({
	offset,
	limit,
	total,
	onPrev,
	onNext
}: {
	offset: number;
	limit: number;
	total: number;
	onPrev: () => void;
	onNext: () => void;
}) {
	const start = total === 0 ? 0 : offset + 1;
	const end = Math.min(offset + limit, total);
	return (
		<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12, marginTop: 14 }}>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)' }}>
				{start}–{end} OF {total}
			</span>
			<button
				onClick={onPrev}
				disabled={offset === 0}
				style={pagerButtonStyle(offset === 0)}
			>
				PREV
			</button>
			<button
				onClick={onNext}
				disabled={end >= total}
				style={pagerButtonStyle(end >= total)}
			>
				NEXT
			</button>
		</div>
	);
}

function pagerButtonStyle(disabled: boolean) {
	return {
		padding: '6px 12px',
		borderRadius: 2,
		border: '1px solid var(--l2-hairline)',
		background: 'transparent',
		color: disabled ? 'var(--l2-fg-3)' : 'var(--l2-fg-2)',
		fontFamily: 'var(--l2-font-mono)',
		fontSize: 10,
		letterSpacing: '0.14em',
		cursor: disabled ? 'default' : 'pointer',
		opacity: disabled ? 0.4 : 1
	} as const;
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 5 }).map((_, i) => (
				<div key={i} style={{ display: 'grid', gridTemplateColumns: '18px minmax(0,1.6fr) 200px 70px 150px', gap: 14, padding: '14px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					{Array.from({ length: 5 }).map((__, j) => (
						<div
							key={j}
							style={{
								height: 12,
								width: j === 1 ? '60%' : 48,
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
				{hasAny ? 'No sessions match this filter' : 'No sessions yet'}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13 }}>
				{hasAny ? 'Switch to "ALL" to see completed and reclaimed sessions.' : 'Open Chat, Console, or the TUI to start a surface session.'}
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
