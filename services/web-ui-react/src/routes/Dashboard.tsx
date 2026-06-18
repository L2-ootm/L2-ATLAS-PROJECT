import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Boxes, BookOpen, Activity, Map, type LucideIcon } from 'lucide-react';
import { Starfield, CompassStar } from '../brand/filigree';
import { Wordmark } from '../brand/Wordmark';
import { StatusBadge } from '../components/hud';
import { glassPanel } from '../lib/glass';
import { listMissions, listModels, listWikiPages, checkHealth, type Mission } from '../lib/api';
import emblemFigure from '../brand/assets/emblem-figure.webp';
import sealMark from '../brand/assets/seal.webp';

// ── Dashboard — the operator observatory. ────────────────────────────────────
// A bounded celestial stage (starfield + slow astrolabe) bearing the engraved
// wordmark, then live telemetry as hairline-framed rails — not floating cards.
// Every region resolves to a real skeleton / empty / offline state.

interface TelemetryData {
	missions: Mission[];
	missionCount: number;
	runningCount: number;
	modelCount: number;
	wikiCount: number;
	health: { status: string; db: string } | null;
	online: boolean;
}
type Load = { state: 'loading' } | { state: 'ready'; data: TelemetryData } | { state: 'error' };

export default function Dashboard() {
	const [load, setLoad] = useState<Load>({ state: 'loading' });

	useEffect(() => {
		let alive = true;
		(async () => {
			const [m, models, wiki, health] = await Promise.allSettled([
				listMissions(50),
				listModels(),
				listWikiPages(50),
				checkHealth()
			]);
			if (!alive) return;
			if ([m, models, wiki, health].every((r) => r.status === 'rejected')) {
				setLoad({ state: 'error' });
				return;
			}
			const missions = m.status === 'fulfilled' ? m.value.missions : [];
			setLoad({
				state: 'ready',
				data: {
					missions,
					missionCount: m.status === 'fulfilled' ? m.value.count : 0,
					runningCount: missions.filter((mi) => mi.status?.toLowerCase() === 'running').length,
					modelCount: models.status === 'fulfilled' ? models.value.count : 0,
					wikiCount: wiki.status === 'fulfilled' ? wiki.value.count : 0,
					health: health.status === 'fulfilled' ? health.value : null,
					online: health.status === 'fulfilled'
				}
			});
		})();
		return () => {
			alive = false;
		};
	}, []);

	return (
		<div style={{ maxWidth: 1200, margin: '0 auto' }}>
			<Hero />
			<StatRail load={load} />
			<div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 16, marginTop: 16 }}>
				<RecentMissions load={load} />
				<SystemStatus load={load} />
			</div>
		</div>
	);
}

// ── Hero — bounded celestial stage ───────────────────────────────────────────
function Hero() {
	return (
		<section
			data-topo="atlas"
			style={{
				position: 'relative',
				overflow: 'hidden',
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				background:
					'radial-gradient(120% 90% at 74% -10%, rgba(79,139,255,0.18), transparent 56%), linear-gradient(180deg, #0E1118 0%, #0B0D12 100%)',
				minHeight: 392
			}}
		>
			{/* starfield substrate */}
			<Starfield style={{ position: 'absolute', inset: 0 }} />
			{/* focal — the Operator Atlas bearing the world, bleeding off the right edge */}
			<img
				src={emblemFigure}
				alt=""
				aria-hidden="true"
				style={{
					position: 'absolute',
					right: -28,
					top: '50%',
					transform: 'translateY(-50%)',
					height: '128%',
					width: 'auto',
					opacity: 0.92,
					pointerEvents: 'none',
					WebkitMaskImage:
						'radial-gradient(130% 100% at 78% 50%, #000 42%, transparent 82%), linear-gradient(90deg, transparent 0%, #000 34%)',
					maskImage:
						'radial-gradient(130% 100% at 78% 50%, #000 42%, transparent 82%), linear-gradient(90deg, transparent 0%, #000 34%)',
					WebkitMaskComposite: 'source-in',
					maskComposite: 'intersect'
				}}
			/>
			{/* horizon hairline + bronze accent */}
			<span
				aria-hidden="true"
				style={{
					position: 'absolute',
					left: 0,
					right: 0,
					bottom: 0,
					height: 1,
					background: 'linear-gradient(90deg, transparent, var(--atlas-bronze-soft) 30%, var(--atlas-bronze) 50%, var(--atlas-bronze-soft) 70%, transparent)',
					opacity: 0.5
				}}
			/>

			<div style={{ position: 'relative', padding: '52px 48px 46px', maxWidth: 640 }}>
				<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
					<CompassStar size={12} />
					<span
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							letterSpacing: '0.36em',
							textTransform: 'uppercase',
							color: 'var(--atlas-bronze)'
						}}
					>
						Operator Cockpit · Mission · Audit · Structure
					</span>
				</div>

				<Wordmark fontSize={84} tracking="0.18em" style={{ alignItems: 'flex-start' }} />

				<p
					style={{
						fontFamily: 'var(--l2-font-serif)',
						fontSize: 21,
						lineHeight: 1.5,
						color: 'var(--l2-fg-2)',
						margin: '20px 0 0',
						maxWidth: 30 + 'ch',
						minWidth: 480
					}}
				>
					The titan bears the operational weight — missions, audit, autonomy — so you don't.
					<span style={{ color: 'var(--l2-fg-3)' }}> Complex inputs in. Clean outputs out.</span>
				</p>
			</div>
		</section>
	);
}

// ── StatRail — one band, hairline-divided cells (not floating cards) ─────────
const STATS: { icon: LucideIcon; label: string; key: keyof TelemetryData; to: string }[] = [
	{ icon: Map, label: 'MISSIONS', key: 'missionCount', to: '/missions' },
	{ icon: Activity, label: 'RUNNING', key: 'runningCount', to: '/missions' },
	{ icon: Boxes, label: 'MODELS', key: 'modelCount', to: '/models' },
	{ icon: BookOpen, label: 'WIKI PAGES', key: 'wikiCount', to: '/wiki' }
];

function StatRail({ load }: { load: Load }) {
	return (
		<div
			style={glassPanel({
				marginTop: 16,
				display: 'grid',
				gridTemplateColumns: 'repeat(4, 1fr)',
				overflow: 'hidden'
			})}
		>
			{STATS.map((s, i) => {
				const Icon = s.icon;
				const value = load.state === 'ready' ? (load.data[s.key] as number) : null;
				const isError = load.state === 'error';
				return (
					<Link
						key={s.label}
						to={s.to}
						style={{
							position: 'relative',
							display: 'block',
							padding: '20px 22px 18px',
							textDecoration: 'none',
							borderLeft: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
							transition: 'background var(--l2-duration-sm) var(--l2-ease)'
						}}
						onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
						onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
					>
						<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
							<Icon size={15} strokeWidth={1.5} color="var(--atlas-celestial)" />
							<ArrowUpRight size={13} strokeWidth={1.5} color="var(--l2-fg-3)" />
						</div>
						{isError ? (
							<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 36, fontWeight: 400, lineHeight: 1, color: 'var(--l2-fg-3)' }}>
								—
							</div>
						) : value === null ? (
							<div style={{ height: 34, width: 56, borderRadius: 2, background: 'var(--l2-fg-ghost)', animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite' }} />
						) : (
							<div
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 36,
									fontWeight: 500,
									lineHeight: 1,
									color: 'var(--l2-fg-1)',
									fontVariantNumeric: 'tabular-nums'
								}}
							>
								{String(value).padStart(2, '0')}
							</div>
						)}
						<div
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 9.5,
								letterSpacing: '0.24em',
								textTransform: 'uppercase',
								color: 'var(--l2-fg-3)',
								marginTop: 12
							}}
						>
							{s.label}
						</div>
					</Link>
				);
			})}
		</div>
	);
}

// ── Framed band with engraved header ─────────────────────────────────────────
function Band({
	title,
	topo,
	children,
	right
}: {
	title: string;
	topo?: string;
	children: React.ReactNode;
	right?: React.ReactNode;
}) {
	return (
		<section data-topo={topo} style={glassPanel({ overflow: 'hidden' })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					gap: 10,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
					<CompassStar size={11} />
					<span
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 11,
							letterSpacing: '0.22em',
							textTransform: 'uppercase',
							color: 'var(--atlas-bronze)'
						}}
					>
						{title}
					</span>
				</div>
				{right}
			</header>
			{children}
		</section>
	);
}

function RecentMissions({ load }: { load: Load }) {
	return (
		<Band title="Recent Missions">
			{load.state === 'loading' && <SkeletonRows n={5} />}
			{load.state === 'error' && <OfflineNote />}
			{load.state === 'ready' &&
				(load.data.missions.length === 0 ? (
					<EmptyNote
						head="No missions yet"
						body="The titan stands ready. Create a mission to put it to work."
					/>
				) : (
					<ul role="list" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
						{load.data.missions.slice(0, 6).map((m, i) => (
							<li key={m.id}>
								<Link
									to={`/missions/${m.id}`}
									style={{
										display: 'flex',
										alignItems: 'center',
										justifyContent: 'space-between',
										gap: 12,
										padding: '13px 18px',
										textDecoration: 'none',
										borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
										transition: 'background var(--l2-duration-xs) var(--l2-ease)'
									}}
									onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.04)')}
									onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
								>
									<span style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
										<span
											style={{
												fontFamily: 'var(--l2-font-mono)',
												fontSize: 11,
												color: 'var(--l2-fg-3)',
												fontVariantNumeric: 'tabular-nums'
											}}
										>
											{String(i + 1).padStart(2, '0')}
										</span>
										<span
											style={{
												color: 'var(--l2-fg-1)',
												fontSize: 14,
												overflow: 'hidden',
												textOverflow: 'ellipsis',
												whiteSpace: 'nowrap'
											}}
										>
											{m.title}
										</span>
									</span>
									<StatusBadge status={m.status} />
								</Link>
							</li>
						))}
					</ul>
				))}
		</Band>
	);
}

function SystemStatus({ load }: { load: Load }) {
	const online = load.state === 'ready' && load.data.online;
	const health = load.state === 'ready' ? load.data.health : null;
	const rows: [string, string, boolean][] =
		load.state === 'ready'
			? [
					['GATEWAY', online ? 'ONLINE' : 'OFFLINE', online],
					['DATABASE', health?.db?.toUpperCase() ?? 'UNKNOWN', (health?.db ?? '').toLowerCase() === 'ok'],
					['HEALTH', health?.status?.toUpperCase() ?? 'UNKNOWN', (health?.status ?? '').toLowerCase() === 'ok']
				]
			: [];
	return (
		<Band title="System Status" topo={online ? 'good' : load.state === 'ready' ? 'bad' : 'atlas'}>
			{load.state === 'loading' && <SkeletonRows n={3} />}
			{load.state === 'error' && <OfflineNote />}
			{load.state === 'ready' && (
				<div style={{ padding: '6px 0' }}>
					{rows.map(([k, v, ok]) => (
						<div
							key={k}
							style={{
								display: 'flex',
								alignItems: 'center',
								justifyContent: 'space-between',
								padding: '11px 18px'
							}}
						>
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.18em', color: 'var(--l2-fg-3)' }}>
								{k}
							</span>
							<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
								<span
									style={{
										width: 6,
										height: 6,
										borderRadius: '50%',
										background: ok ? 'var(--atlas-cyan)' : 'var(--l2-error)',
										boxShadow: `0 0 8px ${ok ? 'var(--atlas-cyan-glow)' : 'rgba(255,0,85,0.5)'}`
									}}
								/>
								<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.1em', color: ok ? 'var(--atlas-cyan)' : 'var(--l2-error)' }}>
									{v}
								</span>
							</span>
						</div>
					))}
				</div>
			)}
		</Band>
	);
}

// ── Shared states (no blank voids; loading preserves layout) ─────────────────
function SkeletonRows({ n }: { n: number }) {
	return (
		<div style={{ padding: '4px 0' }}>
			{Array.from({ length: n }).map((_, i) => (
				<div
					key={i}
					style={{
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'space-between',
						padding: '13px 18px',
						borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
					}}
				>
					<div style={{ height: 12, width: `${40 + ((i * 13) % 35)}%`, borderRadius: 2, background: 'var(--l2-fg-ghost)', animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite' }} />
					<div style={{ height: 12, width: 52, borderRadius: 2, background: 'var(--l2-fg-ghost)', animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite' }} />
				</div>
			))}
		</div>
	);
}

function EmptyNote({ head, body }: { head: string; body: string }) {
	return (
		<div style={{ padding: '30px 24px 34px', textAlign: 'center' }}>
			<img
				src={sealMark}
				alt=""
				aria-hidden="true"
				style={{ width: 104, height: 'auto', opacity: 0.82, marginBottom: 14 }}
			/>
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 19, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				{head}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6, maxWidth: 360, margin: '0 auto' }}>
				{body}
			</div>
		</div>
	);
}

function OfflineNote() {
	return (
		<div style={{ padding: '24px 22px', display: 'flex', gap: 13, alignItems: 'flex-start' }}>
			<span
				style={{
					width: 7,
					height: 7,
					marginTop: 4,
					borderRadius: '50%',
					background: 'var(--l2-error)',
					boxShadow: '0 0 9px rgba(255,0,85,0.55)',
					flex: 'none'
				}}
			/>
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 5 }}>
					Gateway telemetry unavailable
				</div>
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, fontFamily: 'var(--l2-font-mono)', lineHeight: 1.6, letterSpacing: '0.04em' }}>
					NO RESPONSE FROM 127.0.0.1:8484
					<br />
					START THE GATEWAY TO STREAM LIVE STATE
				</div>
			</div>
		</div>
	);
}
