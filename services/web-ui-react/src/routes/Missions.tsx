import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, X } from 'lucide-react';
import { Page } from '../components/Page';
import { StatusBadge } from '../components/hud';
import TopoInput from '../components/TopoInput';
import BorderGlow from '../components/BorderGlow';
import { GlassPanel } from '../components/GlassFx';
import { listMissions, createMission, listProjects, type Mission, type Project } from '../lib/api';
import sealMark from '../brand/assets/seal.webp';

type Load = { s: 'loading' } | { s: 'ready'; missions: Mission[]; count: number } | { s: 'error' };

const STATUSES = ['ALL', 'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED'];

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

export default function Missions() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [query, setQuery] = useState('');
	const [status, setStatus] = useState('ALL');
	const [creating, setCreating] = useState(false);
	const nav = useNavigate();

	async function refresh() {
		try {
			const { missions, count } = await listMissions(50);
			setLoad({ s: 'ready', missions, count });
		} catch {
			setLoad({ s: 'error' });
		}
	}
	useEffect(() => {
		void refresh();
	}, []);

	const filtered = useMemo(() => {
		if (load.s !== 'ready') return [];
		const q = query.trim().toLowerCase();
		return load.missions.filter(
			(m) =>
				(status === 'ALL' || m.status?.toUpperCase() === status) &&
				(q === '' || m.title.toLowerCase().includes(q) || m.intent?.toLowerCase().includes(q))
		);
	}, [load, query, status]);

	const count = load.s === 'ready' ? load.count : null;

	return (
		<Page
			eyebrow="MISSION"
			title="Missions"
			actions={
				<>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
						{count === null ? '—' : `${count} TOTAL`}
					</span>
					<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={() => setCreating(true)}>
						New Mission
					</PrimaryButton>
				</>
			}
		>
			{/* filter rail */}
			<div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
				<div style={{ flex: 1, minWidth: 240 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Filter missions…"
						ariaLabel="Filter missions"
						tone="info"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
				</div>
				<div style={{ display: 'flex', gap: 6 }}>
					{STATUSES.map((s) => (
						<Chip key={s} active={s === status} onClick={() => setStatus(s)}>
							{s}
						</Chip>
					))}
				</div>
			</div>

			{/* table */}
			<GlassPanel style={{ overflow: 'hidden' }}>
				<Header />
				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' &&
					(filtered.length === 0 ? (
						<Empty hasAny={load.missions.length > 0} onCreate={() => setCreating(true)} />
					) : (
						filtered.map((m, i) => (
							<Row key={m.id} m={m} i={i} onClick={() => nav(`/missions/${m.id}`)} />
						))
					))}
			</GlassPanel>

			{creating && (
				<CreateModal
					onClose={() => setCreating(false)}
					onCreated={(id) => {
						setCreating(false);
						void refresh();
						nav(`/missions/${id}`);
					}}
				/>
			)}
		</Page>
	);
}

// ── table pieces ─────────────────────────────────────────────────────────────
const GRID = '28px 1fr 120px 110px';
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
			<span>#</span>
			<span>Mission</span>
			<span>Status</span>
			<span style={{ textAlign: 'right' }}>Updated</span>
		</div>
	);
}

function Row({ m, i, onClick }: { m: Mission; i: number; onClick: () => void }) {
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
				padding: '14px 18px',
				borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
				cursor: 'pointer',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
				{String(i + 1).padStart(2, '0')}
			</span>
			<span style={{ minWidth: 0 }}>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
					{m.title}
				</div>
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
					{m.intent}
				</div>
			</span>
			<span><StatusBadge status={m.status} /></span>
			<span style={{ textAlign: 'right', fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)' }}>
				{rel(m.updated_at)}
			</span>
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 6 }).map((_, i) => (
				<div key={i} style={{ display: 'grid', gridTemplateColumns: GRID, gap: 14, padding: '16px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(16)} />
					<div style={sk(`${50 + ((i * 11) % 35)}%`)} />
					<div style={sk(70)} />
					<div style={sk(48, true)} />
				</div>
			))}
		</div>
	);
}
const sk = (w: number | string, right = false): CSSPropsLite => ({
	height: 12,
	width: w,
	justifySelf: right ? 'end' : 'start',
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});
type CSSPropsLite = React.CSSProperties;

function Empty({ hasAny, onCreate }: { hasAny: boolean; onCreate: () => void }) {
	return (
		<div style={{ padding: '40px 24px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 104, opacity: 0.82, marginBottom: 14 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 20, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				{hasAny ? 'No missions match this filter' : 'No missions yet'}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, marginBottom: hasAny ? 0 : 18 }}>
				{hasAny ? 'Adjust the filter or status above.' : 'Author the first mission to put the titan to work.'}
			</div>
			{!hasAny && (
				<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={onCreate}>
					New Mission
				</PrimaryButton>
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
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, fontFamily: 'var(--l2-font-mono)', letterSpacing: '0.04em' }}>
					NO RESPONSE FROM 127.0.0.1:8484 — START THE GATEWAY
				</div>
			</div>
		</div>
	);
}

// ── controls ─────────────────────────────────────────────────────────────────
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
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				letterSpacing: '0.14em',
				cursor: 'pointer'
			}}
		>
			{children}
		</button>
	);
}

// ── create modal ─────────────────────────────────────────────────────────────
function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
	const [title, setTitle] = useState('');
	const [intent, setIntent] = useState('');
	const [projectId, setProjectId] = useState('');
	const [projects, setProjects] = useState<Project[]>([]);
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	useEffect(() => {
		void listProjects(100)
			.then(({ projects }) => setProjects(projects))
			.catch(() => setProjects([]));
	}, []);

	async function submit() {
		if (!title.trim() || !intent.trim()) {
			setErr('Title and intent are required.');
			return;
		}
		setBusy(true);
		setErr(null);
		try {
			const { mission } = await createMission(title.trim(), intent.trim(), projectId || undefined);
			onCreated(mission.id);
		} catch {
			setErr('Could not create mission — is the gateway running?');
			setBusy(false);
		}
	}

	return (
		<div
			onClick={onClose}
			style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'grid', placeItems: 'center', background: 'rgba(4,5,9,0.86)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
		>
			<div onClick={(e) => e.stopPropagation()} style={{ width: 'min(560px, 92vw)' }}>
			<BorderGlow
				glowColor="258 100 76"
				colors={['#A17BFF', '#4F8BFF', '#46F0E0']}
				cardBg="#0E1118"
				glowIntensity={1.1}
				edgeSensitivity={16}
				style={{ boxShadow: '0 24px 80px rgba(0,0,0,0.6)' }}
			>
				<div style={{ position: 'relative', borderRadius: 2, overflow: 'hidden' }}>
					<span
						aria-hidden="true"
						style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)', opacity: 0.5, zIndex: 2 }}
					/>
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>NEW MISSION</span>
					<button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', display: 'flex' }}>
						<X size={16} />
					</button>
				</div>
				<div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
					<Field label="TITLE">
						<TopoInput value={title} onChange={setTitle} placeholder="Concise mission title" tone="info" ariaLabel="Mission title" autoFocus />
					</Field>
					<Field label="INTENT">
						<TopoInput value={intent} onChange={setIntent} placeholder="What should ATLAS accomplish, and why?" tone="ai" multiline rows={4} ariaLabel="Mission intent" />
					</Field>
					{projects.length > 0 && (
						<Field label="PROJECT (OPTIONAL — RUNS IN ITS FOLDER)">
							<select
								value={projectId}
								onChange={(e) => setProjectId(e.target.value)}
								aria-label="Project"
								style={{
									width: '100%',
									padding: '10px 12px',
									borderRadius: 2,
									border: '1px solid var(--l2-hairline)',
									background: 'rgba(9,11,16,0.6)',
									color: 'var(--l2-fg-1)',
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 12.5,
									cursor: 'pointer'
								}}
							>
								<option value="">No project (default working directory)</option>
								{projects.map((p) => (
									<option key={p.id} value={p.id}>
										{p.name} — {p.root_path}
									</option>
								))}
							</select>
						</Field>
					)}
					{err && <div style={{ color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{err}</div>}
				</div>
				<div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 20px', borderTop: '1px solid var(--l2-hairline)' }}>
					<button onClick={onClose} style={{ padding: '9px 16px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', cursor: 'pointer' }}>
						CANCEL
					</button>
					<PrimaryButton onClick={submit} disabled={busy}>
						{busy ? 'CREATING…' : 'CREATE'}
					</PrimaryButton>
				</div>
			</div>
			</BorderGlow>
			</div>
		</div>
	);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<label style={{ display: 'block' }}>
			<span style={{ display: 'block', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)', marginBottom: 7 }}>{label}</span>
			{children}
		</label>
	);
}
