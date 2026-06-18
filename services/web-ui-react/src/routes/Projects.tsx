import { useEffect, useMemo, useState } from 'react';
import { Search, Plus, FolderPlus, X } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import BorderGlow from '../components/BorderGlow';
import { GlassPanel } from '../components/GlassFx';
import { listProjects, createProject, registerProject, type Project } from '../lib/api';
import sealMark from '../brand/assets/seal.webp';

type Load = { s: 'loading' } | { s: 'ready'; projects: Project[]; count: number } | { s: 'error' };
type Mode = 'create' | 'register';

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

export default function Projects() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [query, setQuery] = useState('');
	const [modal, setModal] = useState<Mode | null>(null);

	async function refresh() {
		try {
			const { projects, count } = await listProjects(100);
			setLoad({ s: 'ready', projects, count });
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
		return load.projects.filter(
			(p) =>
				q === '' ||
				p.name.toLowerCase().includes(q) ||
				p.root_path.toLowerCase().includes(q)
		);
	}, [load, query]);

	const count = load.s === 'ready' ? load.count : null;

	return (
		<Page
			eyebrow="STRUCTURE"
			title="Projects"
			actions={
				<>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
						{count === null ? '—' : `${count} TOTAL`}
					</span>
					<GhostButton icon={<FolderPlus size={15} strokeWidth={2} />} onClick={() => setModal('register')}>
						Register Folder
					</GhostButton>
					<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={() => setModal('create')}>
						New Project
					</PrimaryButton>
				</>
			}
		>
			<div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
				<div style={{ flex: 1, minWidth: 240 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Filter projects…"
						ariaLabel="Filter projects"
						tone="good"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
				</div>
			</div>

			<GlassPanel style={{ overflow: 'hidden' }}>
				<Header />
				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' &&
					(filtered.length === 0 ? (
						<Empty hasAny={load.projects.length > 0} onCreate={() => setModal('create')} />
					) : (
						filtered.map((p, i) => <Row key={p.id} p={p} i={i} />)
					))}
			</GlassPanel>

			{modal && (
				<ProjectModal
					mode={modal}
					onClose={() => setModal(null)}
					onCreated={() => {
						setModal(null);
						void refresh();
					}}
				/>
			)}
		</Page>
	);
}

// ── table pieces ─────────────────────────────────────────────────────────────
const GRID = '28px 1fr 110px';
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
			<span>Project</span>
			<span style={{ textAlign: 'right' }}>Created</span>
		</div>
	);
}

function Row({ p, i }: { p: Project; i: number }) {
	return (
		<div
			data-topo="good"
			style={{
				display: 'grid',
				gridTemplateColumns: GRID,
				gap: 14,
				alignItems: 'center',
				padding: '14px 18px',
				borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(70,240,160,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums' }}>
				{String(i + 1).padStart(2, '0')}
			</span>
			<span style={{ minWidth: 0 }}>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
					{p.name}
				</div>
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 12, fontFamily: 'var(--l2-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
					{p.root_path}
				</div>
			</span>
			<span style={{ textAlign: 'right', fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)' }}>
				{rel(p.created_at)}
			</span>
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 4 }).map((_, i) => (
				<div key={i} style={{ display: 'grid', gridTemplateColumns: GRID, gap: 14, padding: '16px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(16)} />
					<div style={sk(`${50 + ((i * 11) % 35)}%`)} />
					<div style={sk(48, true)} />
				</div>
			))}
		</div>
	);
}
const sk = (w: number | string, right = false): React.CSSProperties => ({
	height: 12,
	width: w,
	justifySelf: right ? 'end' : 'start',
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});

function Empty({ hasAny, onCreate }: { hasAny: boolean; onCreate: () => void }) {
	return (
		<div style={{ padding: '40px 24px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 104, opacity: 0.82, marginBottom: 14 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 20, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				{hasAny ? 'No projects match this filter' : 'No projects yet'}
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, marginBottom: hasAny ? 0 : 18 }}>
				{hasAny
					? 'Adjust the filter above.'
					: 'Create a project folder or register an existing one — missions run in its working directory.'}
			</div>
			{!hasAny && (
				<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={onCreate}>
					New Project
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
				border: '1px solid rgba(70,240,160,0.4)',
				background: 'rgba(70,240,160,0.12)',
				color: 'var(--atlas-emerald, #46f0a0)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1,
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => !disabled && (e.currentTarget.style.background = 'rgba(70,240,160,0.2)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(70,240,160,0.12)')}
		>
			{icon}
			{children}
		</button>
	);
}

function GhostButton({ children, icon, onClick }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void }) {
	return (
		<button
			onClick={onClick}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '9px 16px',
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				background: 'transparent',
				color: 'var(--l2-fg-2)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: 'pointer',
				transition: 'border-color var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(70,240,160,0.4)')}
			onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--l2-hairline)')}
		>
			{icon}
			{children}
		</button>
	);
}

// ── create / register modal ──────────────────────────────────────────────────
function ProjectModal({ mode, onClose, onCreated }: { mode: Mode; onClose: () => void; onCreated: () => void }) {
	const [name, setName] = useState('');
	const [path, setPath] = useState('');
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	const isCreate = mode === 'create';

	async function submit() {
		if (!name.trim() || !path.trim()) {
			setErr('Name and folder path are required.');
			return;
		}
		setBusy(true);
		setErr(null);
		try {
			if (isCreate) await createProject(name.trim(), path.trim());
			else await registerProject(name.trim(), path.trim());
			onCreated();
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			setErr(
				isCreate
					? 'Could not create the project folder — is the gateway running and the path writable?'
					: `Could not register folder — ${msg.includes('does not exist') ? 'the folder does not exist.' : 'is the gateway running?'}`
			);
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
					glowColor="158 90 62"
					colors={['#46F0A0', '#46F0E0', '#4F8BFF']}
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
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
								{isCreate ? 'NEW PROJECT' : 'REGISTER FOLDER'}
							</span>
							<button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', display: 'flex' }}>
								<X size={16} />
							</button>
						</div>
						<div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
							<Field label="NAME">
								<TopoInput value={name} onChange={setName} placeholder="Project name" tone="good" ariaLabel="Project name" autoFocus />
							</Field>
							<Field label={isCreate ? 'FOLDER TO CREATE' : 'EXISTING FOLDER PATH'}>
								<TopoInput
									value={path}
									onChange={setPath}
									placeholder={isCreate ? 'C:\\path\\to\\new-project' : 'C:\\path\\to\\existing\\folder'}
									tone="info"
									ariaLabel="Folder path"
								/>
							</Field>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, lineHeight: 1.5 }}>
								{isCreate
									? 'The folder is created if it does not exist. Missions assigned to this project run in this directory.'
									: 'The folder must already exist on this machine. It becomes the working directory for assigned missions.'}
							</div>
							{err && <div style={{ color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{err}</div>}
						</div>
						<div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 20px', borderTop: '1px solid var(--l2-hairline)' }}>
							<button onClick={onClose} style={{ padding: '9px 16px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', cursor: 'pointer' }}>
								CANCEL
							</button>
							<PrimaryButton onClick={submit} disabled={busy}>
								{busy ? (isCreate ? 'CREATING…' : 'REGISTERING…') : isCreate ? 'CREATE' : 'REGISTER'}
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
