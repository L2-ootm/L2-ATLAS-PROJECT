import { useEffect, useMemo, useState } from 'react';
import type * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, FolderPlus, X, FolderOpen, SquareTerminal } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import BorderGlow from '../components/BorderGlow';
import { GlassPanel } from '../components/GlassFx';
import { GLASS_DISPLACE_ID } from '../lib/glass';
import { listProjects, createProject, registerProject, type Project } from '../lib/api';
import { selectFolder } from '../lib/host';
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
	const navigate = useNavigate();

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
						filtered.map((p, i) => (
							<Row
								key={p.id}
								p={p}
								i={i}
								onOpenConsole={() => navigate(`/console?project=${encodeURIComponent(p.id)}`)}
							/>
						))
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
function Header() {
	return (
		<div
			className="atlas-projects-grid"
			style={{
				display: 'grid',
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
			<span className="atlas-projects-created-col" style={{ textAlign: 'right' }}>Created</span>
			<span className="atlas-projects-console-col" style={{ textAlign: 'right' }}>Console</span>
		</div>
	);
}

function Row({ p, i, onOpenConsole }: { p: Project; i: number; onOpenConsole: () => void }) {
	return (
		<div
			className="atlas-projects-grid"
			data-topo="good"
			style={{
				display: 'grid',
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
			<span className="atlas-projects-created-col" style={{ textAlign: 'right', fontFamily: 'var(--l2-font-mono)', fontSize: 11, color: 'var(--l2-fg-3)' }}>
				{rel(p.created_at)}
			</span>
			<span className="atlas-projects-console-col" style={{ display: 'flex', justifyContent: 'flex-end' }}>
				<ConsoleButton onClick={onOpenConsole} />
			</span>
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 4 }).map((_, i) => (
				<div key={i} className="atlas-projects-grid" style={{ display: 'grid', gap: 14, padding: '16px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(16)} />
					<div style={sk(`${50 + ((i * 11) % 35)}%`)} />
					<div className="atlas-projects-created-col" style={sk(48, true)} />
					<div className="atlas-projects-console-col" style={sk(64, true)} />
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

function ConsoleButton({ onClick }: { onClick: () => void }) {
	return (
		<button
			type="button"
			className="atlas-project-console-button"
			onClick={onClick}
			title="Open project console"
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				justifyContent: 'center',
				gap: 7,
				height: 32,
				borderRadius: 2,
				border: '1px solid rgba(79,139,255,0.38)',
				background: 'linear-gradient(180deg, rgba(79,139,255,0.12), rgba(79,139,255,0.05))',
				color: 'var(--atlas-celestial)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				letterSpacing: '0.14em',
				textTransform: 'uppercase',
				cursor: 'pointer',
				boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.06)',
				transition: 'border-color 150ms var(--l2-ease), background 150ms var(--l2-ease), transform 150ms var(--l2-ease)'
			}}
			onMouseEnter={(e) => {
				e.currentTarget.style.borderColor = 'rgba(79,139,255,0.72)';
				e.currentTarget.style.background = 'linear-gradient(180deg, rgba(79,139,255,0.20), rgba(79,139,255,0.08))';
				e.currentTarget.style.transform = 'translateY(-1px)';
			}}
			onMouseLeave={(e) => {
				e.currentTarget.style.borderColor = 'rgba(79,139,255,0.38)';
				e.currentTarget.style.background = 'linear-gradient(180deg, rgba(79,139,255,0.12), rgba(79,139,255,0.05))';
				e.currentTarget.style.transform = 'none';
			}}
		>
			<SquareTerminal size={14} strokeWidth={1.7} />
			<span className="atlas-project-console-label">Open</span>
		</button>
	);
}

// ── create / register modal ──────────────────────────────────────────────────
function folderName(path: string): string {
	const clean = path.replace(/[\\/]+$/, '');
	return clean.split(/[\\/]/).filter(Boolean).pop() ?? clean;
}

function safeFolderSegment(name: string): string {
	const printable = Array.from(name.trim()).filter((ch) => {
		const code = ch.codePointAt(0) ?? 0;
		return code >= 32 && code !== 127;
	}).join('');
	const clean = printable
		.trim()
		.replace(/[<>:"/\\|?*]+/g, '-')
		.replace(/\s+/g, '-')
		.replace(/^-+|-+$/g, '');
	return clean || 'new-project';
}

function joinFolder(base: string, child: string): string {
	const clean = base.replace(/[\\/]+$/, '');
	if (!clean) return child;
	const sep = clean.includes('/') && !clean.includes('\\') ? '/' : '\\';
	return `${clean}${sep}${child}`;
}

function ProjectModal({ mode, onClose, onCreated }: { mode: Mode; onClose: () => void; onCreated: () => void }) {
	const [name, setName] = useState('');
	const [path, setPath] = useState('');
	const [basePath, setBasePath] = useState('');
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	const isCreate = mode === 'create';

	useEffect(() => {
		if (!isCreate || !basePath) return;
		setPath(joinFolder(basePath, safeFolderSegment(name)));
	}, [basePath, isCreate, name]);

	async function chooseFolder() {
		setErr(null);
		try {
			const picked = await selectFolder(isCreate ? 'Choose parent folder for the new project' : 'Choose project folder');
			if (!picked) return;
			if (isCreate) {
				setBasePath(picked);
				setPath(joinFolder(picked, safeFolderSegment(name)));
			} else {
				setPath(picked);
				if (!name.trim()) setName(folderName(picked));
			}
		} catch {
			setErr('Could not open the local folder picker. Confirm the gateway is running.');
		}
	}

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
			style={{
				position: 'fixed',
				inset: 0,
				zIndex: 200,
				display: 'grid',
				placeItems: 'center',
				background: 'rgba(5,6,10,0.76)',
				backdropFilter: `blur(6px) url(#${GLASS_DISPLACE_ID}) saturate(1.35)`,
				WebkitBackdropFilter: 'blur(6px) saturate(1.35)'
			}}
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
					<div
						style={{
							position: 'relative',
							borderRadius: 2,
							overflow: 'hidden',
							background:
								'linear-gradient(135deg, rgba(237,234,224,0.10), rgba(13,16,24,0.54) 38%, rgba(70,240,160,0.08))',
							backdropFilter: `blur(7px) url(#${GLASS_DISPLACE_ID}) saturate(1.55) brightness(1.05)`,
							WebkitBackdropFilter: 'blur(7px) saturate(1.55) brightness(1.05)',
							boxShadow:
								'inset 0 1px 0 rgba(237,234,224,0.10), inset 0 0 34px rgba(70,240,160,0.08), 0 28px 90px rgba(0,0,0,0.58)'
						}}
					>
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
								<TopoInput value={name} onChange={setName} placeholder="Project name" tone="good" ariaLabel="Project name" autoFocus quiet />
							</Field>
							<Field label={isCreate ? 'FOLDER TO CREATE' : 'EXISTING FOLDER PATH'}>
								<PathPicker
									value={path}
									onChange={setPath}
									onPick={chooseFolder}
									readOnly={false}
									actionLabel={isCreate ? 'Choose Parent' : 'Choose Folder'}
									placeholder={isCreate ? 'Choose a parent folder' : 'Choose an existing folder'}
								/>
							</Field>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, lineHeight: 1.5 }}>
								{isCreate
									? basePath
										? `ATLAS will create ${safeFolderSegment(name)} inside the selected parent. Missions assigned to this project run there.`
										: 'Pick a parent folder; ATLAS will create a project folder inside it.'
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

function PathPicker({
	value,
	onChange,
	onPick,
	readOnly,
	actionLabel,
	placeholder
}: {
	value: string;
	onChange: (value: string) => void;
	onPick: () => void;
	readOnly: boolean;
	actionLabel: string;
	placeholder: string;
}) {
	return (
		<div
			style={{
				display: 'grid',
				gridTemplateColumns: 'minmax(0,1fr) auto',
				gap: 8,
				alignItems: 'stretch'
			}}
		>
			<input
				value={value}
				readOnly={readOnly}
				onClick={() => readOnly && onPick()}
				onChange={(e) => onChange(e.target.value)}
				placeholder={placeholder}
				aria-label="Folder path"
				style={{
					width: '100%',
					minWidth: 0,
					height: 44,
					borderRadius: 2,
					border: '1px solid var(--l2-hairline)',
					background: 'rgba(9,11,16,0.72)',
					color: value ? 'var(--l2-fg-1)' : 'var(--l2-fg-3)',
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 12.5,
					padding: '0 12px',
					outline: 'none',
					cursor: readOnly ? 'pointer' : 'text',
					boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.04)'
				}}
			/>
			<button
				type="button"
				onClick={onPick}
				style={{
					display: 'inline-flex',
					alignItems: 'center',
					justifyContent: 'center',
					gap: 8,
					height: 44,
					padding: '0 13px',
					borderRadius: 2,
					border: '1px solid rgba(70,240,160,0.35)',
					background: 'rgba(70,240,160,0.10)',
					color: 'var(--atlas-emerald)',
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 10.5,
					letterSpacing: '0.14em',
					textTransform: 'uppercase',
					whiteSpace: 'nowrap',
					cursor: 'pointer',
					transition: 'border-color 150ms var(--l2-ease), background 150ms var(--l2-ease)'
				}}
				onMouseEnter={(e) => {
					e.currentTarget.style.borderColor = 'rgba(70,240,160,0.72)';
					e.currentTarget.style.background = 'rgba(70,240,160,0.18)';
				}}
				onMouseLeave={(e) => {
					e.currentTarget.style.borderColor = 'rgba(70,240,160,0.35)';
					e.currentTarget.style.background = 'rgba(70,240,160,0.10)';
				}}
			>
				<FolderOpen size={14} strokeWidth={1.7} />
				{actionLabel}
			</button>
		</div>
	);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div style={{ display: 'block' }}>
			<span style={{ display: 'block', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)', marginBottom: 7 }}>{label}</span>
			{children}
		</div>
	);
}
