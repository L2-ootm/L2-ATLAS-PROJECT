import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Archive, Play, Ban, X } from 'lucide-react';
import { Page } from '../components/Page';
import { AgentBadge, GlassPanel, HudLabel, StatusBadge } from '../components/hud';
import RunTimeline from '../components/RunTimeline';
import LiveBadge from '../components/LiveBadge';
import BorderGlow from '../components/BorderGlow';
import GlassTopo from '../components/GlassTopo';
import { archiveMission, getMission, startRun, cancelRun, type AgentRuntime, type Mission, type Run } from '../lib/api';
import sealMark from '../brand/assets/seal.webp';

type Load =
	| { s: 'loading' }
	| { s: 'ready'; mission: Mission; runs: Run[] }
	| { s: 'error'; offline: boolean };

const RUN_GRID = '120px 110px 180px 180px 56px';

function isRunActive(status: string): boolean {
	const s = status.toUpperCase();
	return s === 'RUNNING' || s === 'PENDING';
}

function fmt(iso: string | null): string {
	if (!iso) return '—';
	const d = new Date(iso);
	return Number.isNaN(d.getTime())
		? iso
		: d.toLocaleString('en-GB', { hour12: false, dateStyle: 'short', timeStyle: 'medium' });
}

export default function MissionDetail() {
	const { id = '' } = useParams();
	const nav = useNavigate();
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [agent, setAgent] = useState<AgentRuntime>('native');
	const [launching, setLaunching] = useState(false);
	const [launchError, setLaunchError] = useState<string | null>(null);
	const [confirmCancel, setConfirmCancel] = useState(false);
	const [cancelError, setCancelError] = useState<string | null>(null);
	const [archiveOpen, setArchiveOpen] = useState(false);
	const [archiveDays, setArchiveDays] = useState(30);
	const [archiveError, setArchiveError] = useState<string | null>(null);
	const [archiving, setArchiving] = useState(false);

	const refresh = useCallback(async () => {
		try {
			const { mission, runs } = await getMission(id);
			setLoad({ s: 'ready', mission, runs });
		} catch (e) {
			setLoad({ s: 'error', offline: e instanceof TypeError });
		}
	}, [id]);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	async function launch() {
		if (launching || load.s !== 'ready') return;
		setLaunching(true);
		setLaunchError(null);
		try {
			const { run } = await startRun(load.mission.id, agent);
			nav(`/runs/${run.id}`);
		} catch (e) {
			setLaunchError(`RUN LAUNCH FAILED — ${e instanceof Error ? e.message : String(e)}. Mission status reverted.`);
			setLaunching(false);
		}
	}

	async function doCancel() {
		if (load.s !== 'ready') return;
		setCancelError(null);
		try {
			await cancelRun(load.mission.id);
			setConfirmCancel(false);
			await refresh();
		} catch (e) {
			setCancelError(`CANCEL FAILED — ${e instanceof Error ? e.message : String(e)}`);
		}
	}

	async function doArchive() {
		if (load.s !== 'ready') return;
		setArchiving(true);
		setArchiveError(null);
		try {
			await archiveMission(load.mission.id, archiveDays);
			setArchiveOpen(false);
			await refresh();
		} catch (e) {
			setArchiveError(`ARCHIVE FAILED — ${e instanceof Error ? e.message : String(e)}`);
		} finally {
			setArchiving(false);
		}
	}

	const mission = load.s === 'ready' ? load.mission : null;
	const runs = load.s === 'ready' ? load.runs : [];
	const hasActive = runs.some((r) => isRunActive(r.status));
	const missionStatus = mission?.status.toUpperCase() ?? '';
	const canLaunch = missionStatus === 'PENDING';
	const canArchive = missionStatus === 'SUCCEEDED' || missionStatus === 'COMPLETED';
	const archived = missionStatus === 'ARCHIVED';

	return (
		<Page
			eyebrow="MISSION · DETAIL"
			title={mission ? mission.title : 'Mission'}
			actions={
				load.s === 'ready' ? (
					<>
						{canLaunch && <AgentSelect value={agent} onChange={setAgent} disabled={launching} />}
						{canArchive && (
							<GhostButton icon={<Archive size={15} strokeWidth={1.5} />} onClick={() => setArchiveOpen(true)}>
								Archive
							</GhostButton>
						)}
						{hasActive && (
							<GhostButton icon={<Ban size={15} strokeWidth={1.5} />} onClick={() => setConfirmCancel(true)} danger>
								Cancel
							</GhostButton>
						)}
						{canLaunch && (
							<PrimaryButton icon={<Play size={15} strokeWidth={2} />} onClick={launch} disabled={launching}>
								{launching ? 'Launching…' : 'Launch run'}
							</PrimaryButton>
						)}
					</>
				) : null
			}
		>
			{load.s === 'loading' && (
				<GlassPanel style={{ padding: 48, display: 'grid', placeItems: 'center' }}>
					<HudLabel>LOADING…</HudLabel>
				</GlassPanel>
			)}

			{load.s === 'error' && (
				<GlassPanel glow="bad" style={{ padding: 24 }}>
					<HudLabel style={{ color: 'var(--l2-error)' }}>
						{load.offline ? 'GATEWAY OFFLINE — 127.0.0.1:8484 NOT RESPONDING' : 'FAILED TO LOAD MISSION'}
					</HudLabel>
				</GlassPanel>
			)}

			{load.s === 'ready' && mission && (
				<>
					{/* metadata — cursor-reactive hero panel */}
					<BorderGlow
						glowColor="220 100 70"
						colors={['#4F8BFF', '#A17BFF', '#46F0E0']}
						cardBg="#10131B"
						glowIntensity={0.85}
						edgeSensitivity={26}
						style={{ marginBottom: 16 }}
					>
						<GlassTopo tone="info" radius={2} accent padding={24}>
							<div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
								<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
									{mission.id}
								</span>
							</div>
							<div style={{ marginBottom: 18 }}>
								<RunTimeline status={mission.status} />
							</div>
							{mission.intent && (
								<p style={{ margin: '0 0 18px', color: 'var(--l2-fg-2)', fontSize: 15, lineHeight: 1.6 }}>
									{mission.intent}
								</p>
							)}
							<div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
								<Meta label="CREATED" value={fmt(mission.created_at)} />
								<Meta label="UPDATED" value={fmt(mission.updated_at)} />
								{mission.project && <Meta label="PROJECT" value={mission.project} />}
								{archived && mission.archived_at && <Meta label="ARCHIVED" value={fmt(mission.archived_at)} />}
								{archived && mission.delete_after && <Meta label="DELETE AFTER" value={fmt(mission.delete_after)} />}
							</div>
						</GlassTopo>
					</BorderGlow>

					{archiveOpen && (
						<ArchivePanel
							days={archiveDays}
							busy={archiving}
							error={archiveError}
							onDays={setArchiveDays}
							onClose={() => {
								setArchiveOpen(false);
								setArchiveError(null);
							}}
							onConfirm={doArchive}
						/>
					)}

					{/* runs */}
					<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
						<HudLabel>RUNS</HudLabel>
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
							{runs.length} TOTAL
						</span>
					</div>

					{confirmCancel && (
						<GlassPanel glow="bad" style={{ padding: 16, marginBottom: 12 }}>
							<p style={{ margin: '0 0 12px', color: 'var(--l2-fg-1)', fontSize: 14, lineHeight: 1.5 }}>
								CONFIRM CANCEL: this halts ALL active runs of this mission (not just one). Irreversible.
							</p>
							{cancelError && (
								<p style={{ margin: '0 0 10px', fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-error)' }}>
									{cancelError}
								</p>
							)}
							<div style={{ display: 'flex', gap: 10 }}>
								<GhostButton danger onClick={doCancel}>Confirm cancel</GhostButton>
								<GhostButton onClick={() => { setConfirmCancel(false); setCancelError(null); }}>Keep run</GhostButton>
							</div>
						</GlassPanel>
					)}

					{launchError && (
						<GlassPanel glow="bad" style={{ padding: '12px 16px', marginBottom: 12 }}>
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-error)' }}>{launchError}</span>
						</GlassPanel>
					)}

					{runs.length === 0 ? (
						<GlassPanel style={{ padding: '40px 24px', textAlign: 'center' }}>
							<img src={sealMark} alt="" aria-hidden="true" style={{ width: 96, opacity: 0.82, marginBottom: 14 }} />
							<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 19, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
								No runs initiated
							</div>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, marginBottom: 18 }}>
								Launch a run to put the titan to work on this mission.
							</div>
							<div style={{ display: 'inline-flex' }}>
								<PrimaryButton icon={<Play size={15} strokeWidth={2} />} onClick={launch} disabled={launching}>
									{launching ? 'Launching…' : 'Launch run'}
								</PrimaryButton>
							</div>
						</GlassPanel>
					) : (
						<GlassPanel
							glow="info"
							style={{
								overflow: 'hidden',
								background:
									'linear-gradient(135deg, rgba(237,234,224,0.08), rgba(18,22,31,0.36) 34%, rgba(79,139,255,0.07))',
								backdropFilter: 'blur(11px) saturate(1.55) brightness(1.04)',
								WebkitBackdropFilter: 'blur(11px) saturate(1.55) brightness(1.04)',
								boxShadow:
									'inset 0 1px 0 rgba(237,234,224,0.10), inset 0 0 30px rgba(79,139,255,0.05), 0 18px 60px rgba(0,0,0,0.28)'
							}}
						>
							<RunHeader />
							{runs.map((r, i) => (
								<RunRow key={r.id} r={r} first={i === 0} onClick={() => nav(`/runs/${r.id}`)} />
							))}
						</GlassPanel>
					)}
				</>
			)}
		</Page>
	);
}

function ArchivePanel({
	days,
	busy,
	error,
	onDays,
	onClose,
	onConfirm
}: {
	days: number;
	busy: boolean;
	error: string | null;
	onDays: (days: number) => void;
	onClose: () => void;
	onConfirm: () => void;
}) {
	const options = [7, 30, 90, 365];
	return (
		<GlassPanel glow="atlas" style={{ padding: 16, marginBottom: 12 }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
				<span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
					<Archive size={15} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<HudLabel style={{ color: 'var(--atlas-bronze)' }}>ARCHIVE RETENTION</HudLabel>
				</span>
				<button onClick={onClose} aria-label="Close archive panel" style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', display: 'flex' }}>
					<X size={16} />
				</button>
			</div>
			<p style={{ margin: '0 0 12px', color: 'var(--l2-fg-2)', fontSize: 13, lineHeight: 1.5 }}>
				Archive this succeeded mission. ATLAS keeps the run and audit trail until the retention deadline, then the purge sweep deletes it.
			</p>
			<div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
				{options.map((opt) => (
					<button
						key={opt}
						onClick={() => onDays(opt)}
						style={{
							padding: '7px 11px',
							borderRadius: 2,
							border: `1px solid ${days === opt ? 'rgba(176,138,87,0.5)' : 'var(--l2-hairline)'}`,
							background: days === opt ? 'rgba(176,138,87,0.14)' : 'transparent',
							color: days === opt ? 'var(--atlas-bronze)' : 'var(--l2-fg-3)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							letterSpacing: '0.12em',
							cursor: 'pointer'
						}}
					>
						{opt}D
					</button>
				))}
				<input
					type="number"
					min={1}
					max={3650}
					value={days}
					onChange={(e) => onDays(Math.max(1, Math.min(3650, Number(e.target.value) || 1)))}
					aria-label="Archive retention days"
					style={{
						width: 88,
						padding: '7px 10px',
						borderRadius: 2,
						border: '1px solid var(--l2-hairline)',
						background: 'rgba(9,11,16,0.58)',
						color: 'var(--l2-fg-1)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 11
					}}
				/>
			</div>
			{error && <div style={{ marginBottom: 10, color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{error}</div>}
			<div style={{ display: 'flex', gap: 10 }}>
				<PrimaryButton icon={<Archive size={15} strokeWidth={1.5} />} onClick={onConfirm} disabled={busy}>
					{busy ? 'ARCHIVING…' : 'ARCHIVE'}
				</PrimaryButton>
				<GhostButton onClick={onClose}>Keep Visible</GhostButton>
			</div>
		</GlassPanel>
	);
}

function Meta({ label, value }: { label: string; value: string }) {
	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
			<HudLabel style={{ fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)' }}>{label}</HudLabel>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums' }}>
				{value}
			</span>
		</div>
	);
}

function RunHeader() {
	return (
		<div
			style={{
				display: 'grid',
				gridTemplateColumns: RUN_GRID,
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
			<span>Status</span>
			<span>Started</span>
			<span>Finished</span>
			<span style={{ textAlign: 'right' }}>View</span>
		</div>
	);
}

function RunRow({ r, first, onClick }: { r: Run; first: boolean; onClick: () => void }) {
	const active = isRunActive(r.status);
	return (
		<div
			role="button"
			tabIndex={0}
			data-topo={active ? 'info' : 'atlas'}
			onClick={onClick}
			onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
			style={{
				display: 'grid',
				gridTemplateColumns: RUN_GRID,
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
			<span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 5, minWidth: 0 }}>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-2)', fontVariantNumeric: 'tabular-nums' }}>
					{r.id.slice(0, 8)}
				</span>
				{r.agent_runtime && <AgentBadge agent={r.agent_runtime} />}
			</span>
			<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
				<StatusBadge status={r.status} />
				{active && <LiveBadge connected />}
			</span>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
				{fmt(r.started_at)}
			</span>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
				{fmt(r.finished_at)}
			</span>
			<span style={{ textAlign: 'right', fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--atlas-celestial)' }}>→</span>
		</div>
	);
}

function PrimaryButton({ children, icon, onClick, disabled }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void; disabled?: boolean }) {
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '9px 16px',
				borderRadius: 2,
				border: '1px solid rgba(79,139,255,0.4)',
				background: 'rgba(79,139,255,0.12)',
				color: 'var(--atlas-celestial)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1,
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => !disabled && (e.currentTarget.style.background = 'rgba(79,139,255,0.2)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.12)')}
		>
			{icon}
			{children}
		</button>
	);
}

// Segmented control selecting the agent runtime a launched run is recorded
// against (P4). NATIVE default; CLAUDE CODE routes the run to the operator's
// local Claude Code session. Matches the Chip/PrimaryButton mono-uppercase law.
const AGENT_OPTIONS: { value: AgentRuntime; label: string }[] = [
	{ value: 'native', label: 'NATIVE' },
	{ value: 'claude_code', label: 'CLAUDE CODE' }
];
function AgentSelect({ value, onChange, disabled }: { value: AgentRuntime; onChange: (a: AgentRuntime) => void; disabled?: boolean }) {
	return (
		<div
			role="radiogroup"
			aria-label="Agent runtime"
			style={{
				display: 'inline-flex',
				padding: 2,
				gap: 2,
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				background: 'rgba(9,11,16,0.5)',
				opacity: disabled ? 0.5 : 1
			}}
		>
			{AGENT_OPTIONS.map((opt) => {
				const on = opt.value === value;
				const claude = opt.value === 'claude_code';
				const activeColor = claude ? '#F08A4B' : 'var(--atlas-celestial)';
				const activeBg = claude ? 'rgba(240,138,75,0.15)' : 'rgba(79,139,255,0.14)';
				const activeBorder = claude ? 'rgba(240,138,75,0.42)' : 'rgba(79,139,255,0.34)';
				return (
					<button
						key={opt.value}
						role="radio"
						aria-checked={on}
						disabled={disabled}
						onClick={() => onChange(opt.value)}
						style={{
							padding: '7px 12px',
							borderRadius: 2,
							border: `1px solid ${on ? activeBorder : 'transparent'}`,
							background: on ? activeBg : 'transparent',
							color: on ? activeColor : 'var(--l2-fg-3)',
							boxShadow: on && claude ? '0 0 18px rgba(240,138,75,0.10)' : 'none',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							letterSpacing: '0.14em',
							textTransform: 'uppercase',
							cursor: disabled ? 'default' : 'pointer',
							transition: 'background var(--l2-duration-xs) var(--l2-ease), color var(--l2-duration-xs) var(--l2-ease)'
						}}
					>
						{opt.label}
					</button>
				);
			})}
		</div>
	);
}

function GhostButton({ children, icon, onClick, danger }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void; danger?: boolean }) {
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
				background: 'transparent',
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
