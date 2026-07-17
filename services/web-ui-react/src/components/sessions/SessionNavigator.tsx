import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
	ChevronDown,
	Folder,
	FolderPlus,
	MessageSquare,
	PanelLeftOpen,
	Plus,
	Search,
	SquareTerminal,
	Unlink,
	X
} from 'lucide-react';
import {
	loadSessionCatalog,
	setActiveSessionId,
	subscribeSessionCatalog,
	type SessionCatalogEntry,
	type SessionSurface
} from '../../lib/sessionCatalog';

interface SessionNavigatorProps {
	activeSessionId: string;
	surface: SessionSurface;
	bound: boolean;
	disabled?: boolean;
	onNewSession: (unbound: boolean) => void;
	onSelectSession: (id: string) => void;
	onChooseFolder: () => void;
	onUnbind: () => void;
}

function relativeTime(value: string): string {
	const elapsed = Date.now() - new Date(value).getTime();
	if (!Number.isFinite(elapsed) || elapsed < 60_000) return 'NOW';
	if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}M`;
	if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}H`;
	return `${Math.floor(elapsed / 86_400_000)}D`;
}

function groupKey(entry: SessionCatalogEntry): string {
	if (entry.binding.kind === 'unbound') return 'unbound';
	return entry.binding.root || entry.binding.projectId || entry.binding.label;
}

export function SessionNavigator(props: SessionNavigatorProps) {
	const navigate = useNavigate();
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState('');
	const [catalog, setCatalog] = useState(loadSessionCatalog);
	const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

	useEffect(() => subscribeSessionCatalog(() => setCatalog(loadSessionCatalog())), []);
	useEffect(() => {
		if (!open) return;
		const close = (event: KeyboardEvent) => {
			if (event.key === 'Escape') setOpen(false);
		};
		window.addEventListener('keydown', close);
		return () => window.removeEventListener('keydown', close);
	}, [open]);

	const filtered = useMemo(() => {
		const needle = query.trim().toLowerCase();
		if (!needle) return catalog;
		return catalog.filter((entry) =>
			[entry.title, entry.binding.label, entry.binding.root, entry.surface]
				.filter(Boolean)
				.some((value) => String(value).toLowerCase().includes(needle))
		);
	}, [catalog, query]);
	const unbound = filtered.filter((entry) => entry.binding.kind === 'unbound');
	const boundGroups = useMemo(() => {
		const map = new Map<string, SessionCatalogEntry[]>();
		for (const entry of filtered.filter((item) => item.binding.kind !== 'unbound')) {
			const key = groupKey(entry);
			map.set(key, [...(map.get(key) ?? []), entry]);
		}
		return [...map.entries()].sort(([, a], [, b]) => b[0]!.updatedAt.localeCompare(a[0]!.updatedAt));
	}, [filtered]);

	function select(entry: SessionCatalogEntry) {
		setActiveSessionId(entry.surface, entry.id);
		setOpen(false);
		if (entry.surface === props.surface) {
			props.onSelectSession(entry.id);
			return;
		}
		navigate(entry.surface === 'chat' ? '/chat' : '/console');
	}

	return (
		<>
			<button
				type="button"
				className="atlas-session-nav-trigger"
				onClick={() => setOpen(true)}
				title="Sessions and functions"
			>
				<PanelLeftOpen size={15} strokeWidth={1.6} />
				<span>SESSIONS</span>
			</button>
			{open && (
				<div className="atlas-session-nav-layer" role="presentation">
					<button
						type="button"
						className="atlas-session-nav-backdrop"
						onClick={() => setOpen(false)}
						aria-label="Close session navigator"
					/>
					<aside className="atlas-session-nav" aria-label="Session navigator" data-topo="atlas">
						<header className="atlas-session-nav-head">
							<div>
								<div className="atlas-session-nav-kicker">ATLAS // SESSION INDEX</div>
								<div className="atlas-session-nav-title">Operational memory</div>
							</div>
							<button type="button" className="atlas-session-nav-icon" onClick={() => setOpen(false)} aria-label="Close">
								<X size={16} />
							</button>
						</header>

						<div className="atlas-session-nav-actions">
							<button type="button" disabled={props.disabled} onClick={() => { setOpen(false); props.onNewSession(false); }}>
								<Plus size={14} />
								<span>NEW SESSION</span>
								<kbd>⌘N</kbd>
							</button>
							<button type="button" disabled={props.disabled} onClick={() => { setOpen(false); props.onChooseFolder(); }}>
								<FolderPlus size={14} />
								<span>BIND FOLDER</span>
							</button>
							<button type="button" disabled={props.disabled || !props.bound} onClick={() => { setOpen(false); props.onUnbind(); }}>
								<Unlink size={14} />
								<span>UNBIND CURRENT</span>
							</button>
							<button type="button" disabled={props.disabled} onClick={() => { setOpen(false); props.onNewSession(true); }}>
								<MessageSquare size={14} />
								<span>NEW UNBOUND</span>
							</button>
						</div>

						<label className="atlas-session-nav-search">
							<Search size={13} />
							<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter sessions" />
						</label>

						<div className="atlas-session-nav-scroll">
							<SessionGroup
								label="UNBOUND"
								count={unbound.length}
								entries={unbound}
								activeId={props.activeSessionId}
								onSelect={select}
							/>
							{boundGroups.map(([key, entries]) => {
								const first = entries[0]!;
								const isCollapsed = collapsed[key] === true;
								return (
									<section className="atlas-session-group" key={key}>
										<button
											type="button"
											className="atlas-session-group-head"
											onClick={() => setCollapsed((value) => ({ ...value, [key]: !isCollapsed }))}
											title={first.binding.root ?? first.binding.label}
										>
											<Folder size={14} />
											<span className="atlas-session-group-name">{first.binding.label}</span>
											<span className="atlas-session-group-count">{entries.length}</span>
											<ChevronDown size={13} className={isCollapsed ? 'is-collapsed' : ''} />
										</button>
										{!isCollapsed && (
											<div className="atlas-session-group-items">
												{entries.map((entry) => (
													<SessionRow
														key={entry.id}
														entry={entry}
														active={entry.id === props.activeSessionId}
														onSelect={select}
													/>
												))}
											</div>
										)}
									</section>
								);
							})}
							{filtered.length === 0 && (
								<div className="atlas-session-nav-empty">NO SESSIONS MATCH THE CURRENT FILTER.</div>
							)}
						</div>
					</aside>
				</div>
			)}
		</>
	);
}

function SessionGroup({
	label,
	count,
	entries,
	activeId,
	onSelect
}: {
	label: string;
	count: number;
	entries: SessionCatalogEntry[];
	activeId: string;
	onSelect: (entry: SessionCatalogEntry) => void;
}) {
	if (entries.length === 0) return null;
	return (
		<section className="atlas-session-group">
			<div className="atlas-session-group-label">
				<span>{label}</span>
				<span>{count}</span>
			</div>
			<div className="atlas-session-group-items">
				{entries.map((entry) => (
					<SessionRow key={entry.id} entry={entry} active={entry.id === activeId} onSelect={onSelect} />
				))}
			</div>
		</section>
	);
}

function SessionRow({
	entry,
	active,
	onSelect
}: {
	entry: SessionCatalogEntry;
	active: boolean;
	onSelect: (entry: SessionCatalogEntry) => void;
}) {
	const SurfaceIcon = entry.surface === 'chat' ? MessageSquare : SquareTerminal;
	return (
		<button
			type="button"
			className={`atlas-session-row${active ? ' is-active' : ''}`}
			onClick={() => onSelect(entry)}
			title={entry.title}
		>
			<span className="atlas-session-row-signal" />
			<SurfaceIcon size={13} strokeWidth={1.6} />
			<span className="atlas-session-row-copy">
				<span className="atlas-session-row-title">{entry.title}</span>
				<span className="atlas-session-row-meta">
					{entry.surface.toUpperCase()} · {entry.agent === 'claude_code' ? 'CLAUDE CODE' : 'ATLAS'}
				</span>
			</span>
			<span className="atlas-session-row-time">{relativeTime(entry.updatedAt)}</span>
		</button>
	);
}
