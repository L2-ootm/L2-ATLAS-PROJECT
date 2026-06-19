import { useEffect, useMemo, useRef, useState } from 'react';
import type * as React from 'react';
import { useSearchParams } from 'react-router-dom';
import {
	AlertTriangle,
	Bot,
	BoxSelect,
	Check,
	ChevronDown,
	ChevronRight,
	Circle,
	Columns3,
	CopyPlus,
	FilePen,
	FilePlus2,
	FileText,
	Folder,
	FolderOpen,
	FolderSearch,
	GitBranch,
	Grip,
	GripVertical,
	LayoutGrid,
	ListTree,
	MessageSquare,
	MousePointer2,
	Search,
	SendHorizontal,
	SquareTerminal,
	Waypoints,
	Wrench,
	X
} from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { TopoScroll } from '../components/TopoScroll';
import {
	agentRuntimeLabel,
	consoleChatStream,
	listProjects,
	type AgentRuntime,
	type ConsoleChatEvent,
	type Project
} from '../lib/api';
import { selectFolder } from '../lib/host';

type Load = { s: 'loading' } | { s: 'ready'; projects: Project[] } | { s: 'error' };
type LayoutMode = 'tile' | 'free' | 'tabs';
type BindingMode = 'project' | 'folder';
type WindowKind = 'chat' | 'audit' | 'tools' | 'context';
type DragState = { id: string; pointerId?: number; startX: number; startY: number; x: number; y: number } | null;
type ResizeState = { id: string; pointerId?: number; startX: number; startY: number; w: number; h: number } | null;

type ConsoleWindow = {
	id: string;
	kind: WindowKind;
	title: string;
	agent?: AgentRuntime;
	x: number;
	y: number;
	w: number;
	h: number;
};

type ConsoleMessage = {
	id: string;
	role: 'system' | 'operator' | 'agent';
	label: string;
	body: string;
	time: string;
	status?: 'pending' | 'failed' | 'succeeded';
	/** Ordered SDK events for an agent turn — text blocks + tool calls rendered inline. */
	events?: ConsoleChatEvent[];
};

const INITIAL_WINDOWS: ConsoleWindow[] = [
	{ id: 'chat-1', kind: 'chat', title: 'atlas.chat', agent: 'native', x: 260, y: 54, w: 540, h: 430 },
	{ id: 'audit-1', kind: 'audit', title: 'audit.stream', x: 840, y: 54, w: 300, h: 210 },
	{ id: 'context-1', kind: 'context', title: 'context.graph', x: 840, y: 282, w: 300, h: 202 },
	{ id: 'tools-1', kind: 'tools', title: 'tool.dock', x: 20, y: 54, w: 220, h: 430 }
];

const KIND_ICON: Record<WindowKind, React.ElementType> = {
	chat: MessageSquare,
	audit: SquareTerminal,
	tools: Bot,
	context: Waypoints
};

function nowLabel(): string {
	return new Intl.DateTimeFormat(undefined, {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit'
	}).format(new Date());
}

function shortPath(path: string): string {
	if (path.length <= 64) return path;
	return `...${path.slice(-61)}`;
}

function bootMessage(project: Project | null, cwd: string | null): ConsoleMessage {
	const body = project
		? `Console bound to ${project.name}. Workspace root: ${project.root_path}`
		: cwd
			? `Console bound to folder: ${cwd}`
			: 'Console opened without a folder binding.';
	return { id: `boot-${Date.now()}`, role: 'system', label: 'ATLAS', body, time: nowLabel() };
}

export default function Console() {
	const [params, setParams] = useSearchParams();
	const projectId = params.get('project') ?? '';
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [layout, setLayout] = useState<LayoutMode>('tile');
	const [bindingMode, setBindingMode] = useState<BindingMode>(projectId ? 'project' : 'folder');
	const [folderPath, setFolderPath] = useState('');
	const [folderErr, setFolderErr] = useState<string | null>(null);
	const [windows, setWindows] = useState<ConsoleWindow[]>(INITIAL_WINDOWS);
	const [activeWindow, setActiveWindow] = useState('chat-1');
	const [messagesByWindow, setMessagesByWindow] = useState<Record<string, ConsoleMessage[]>>({});
	const [auditEvents, setAuditEvents] = useState<ConsoleChatEvent[]>([]);
	const [draftByWindow, setDraftByWindow] = useState<Record<string, string>>({ 'chat-1': '' });
	const [busyWindow, setBusyWindow] = useState<string | null>(null);
	const [drag, setDrag] = useState<DragState>(null);
	const [resize, setResize] = useState<ResizeState>(null);
	const [tileDragId, setTileDragId] = useState<string | null>(null);
	// Live drag bookkeeping: tracks the reserved "home" slot the dragged window
	// will land in, so other windows can swap into the vacated slot in real time.
	const dragRef = useRef<
		{ id: string; pointerId?: number; startX: number; startY: number; x: number; y: number; homeX: number; homeY: number; didSwap: boolean } | null
	>(null);
	const windowsRef = useRef(windows);
	windowsRef.current = windows;

	useEffect(() => {
		let alive = true;
		async function run() {
			try {
				const { projects } = await listProjects(100);
				if (alive) setLoad({ s: 'ready', projects });
			} catch {
				if (alive) setLoad({ s: 'error' });
			}
		}
		void run();
		return () => {
			alive = false;
		};
	}, []);

	const projects = load.s === 'ready' ? load.projects : [];
	const activeProject = useMemo(() => {
		if (load.s !== 'ready' || !projectId) return null;
		return load.projects.find((p) => p.id === projectId) ?? null;
	}, [load, projectId]);
	const boundCwd = bindingMode === 'project' ? activeProject?.root_path ?? null : folderPath.trim() || null;
	const activeConsoleWindow = windows.find((win) => win.id === activeWindow) ?? windows[0];
	const activeChatAgent = activeConsoleWindow?.kind === 'chat' ? activeConsoleWindow.agent ?? 'native' : 'native';
	const visibleWindows = layout === 'tabs' ? windows.filter((win) => win.id === activeWindow) : windows;
	const projectState = useMemo(() => {
		if (bindingMode === 'folder') {
			return boundCwd
				? { label: 'FOLDER', detail: shortPath(boundCwd), tone: 'info' as const }
				: { label: 'UNBOUND', detail: 'Choose folder', tone: 'muted' as const };
		}
		if (!projectId) return { label: 'UNBOUND', detail: 'No project context', tone: 'muted' as const };
		if (load.s === 'loading') return { label: 'RESOLVING', detail: projectId, tone: 'info' as const };
		if (load.s === 'error') return { label: 'OFFLINE', detail: 'Projects unavailable', tone: 'bad' as const };
		if (!activeProject) return { label: 'MISSING', detail: projectId, tone: 'warn' as const };
		return { label: 'BOUND', detail: activeProject.name, tone: 'good' as const };
	}, [activeProject, bindingMode, boundCwd, load.s, projectId]);

	useEffect(() => {
		setMessagesByWindow((prev) => {
			const next = { ...prev };
			for (const win of windows.filter((w) => w.kind === 'chat')) {
				const current = next[win.id] ?? [];
				const onlyBootReceipt = current.length === 1 && current[0].id.startsWith('boot-');
				if (current.length === 0 || onlyBootReceipt) {
					next[win.id] = [bootMessage(activeProject, boundCwd)];
				}
			}
			return next;
		});
	}, [activeProject, boundCwd, windows]);

	function pickProject(project: Project) {
		setBindingMode('project');
		setParams({ project: project.id });
	}

	async function chooseFolder() {
		setBindingMode('folder');
		setFolderErr(null);
		try {
			const picked = await selectFolder('Choose console working folder');
			if (picked) setFolderPath(picked);
		} catch {
			setFolderErr('Could not open the local folder picker. Confirm the gateway is running.');
		}
	}

	function addWindow(kind: WindowKind = 'chat', windowAgent: AgentRuntime = 'native') {
		const count = windows.filter((w) => w.kind === kind).length + 1;
		const agentCount = windows.filter((w) => w.kind === 'chat' && (w.agent ?? 'native') === windowAgent).length + 1;
		const id = `${kind}-${windowAgent}-${Date.now()}`;
		const title =
			kind === 'chat'
				? windowAgent === 'claude_code'
					? agentCount === 1
						? 'claude.code'
						: `claude.code.${agentCount}`
					: agentCount === 1
						? 'atlas.chat'
						: `atlas.chat.${agentCount}`
				: `${kind}.${count}`;
		const next = {
			id,
			kind,
			title,
			agent: kind === 'chat' ? windowAgent : undefined,
			x: 300 + count * 24,
			y: 92 + count * 18,
			w: kind === 'chat' ? 610 : 330,
			h: kind === 'chat' ? 500 : 300
		};
		setWindows((prev) => [...prev, next]);
		setActiveWindow(id);
		if (kind === 'chat') {
			setMessagesByWindow((prev) => ({ ...prev, [id]: [bootMessage(activeProject, boundCwd)] }));
			setDraftByWindow((prev) => ({ ...prev, [id]: '' }));
		}
	}

	function closeWindow(id: string) {
		if (windows.length <= 1) return;
		setWindows((prev) => prev.filter((w) => w.id !== id));
		if (activeWindow === id) {
			const fallback = windows.find((w) => w.id !== id)?.id ?? '';
			setActiveWindow(fallback);
		}
	}

	function resizeWindow(id: string, w: number, h: number) {
		setWindows((prev) =>
			prev.map((win) =>
				win.id === id
					? {
							...win,
							w: Math.max(260, w),
							h: Math.max(220, h)
						}
					: win
			)
		);
	}

	function reorderWindow(sourceId: string, targetId: string) {
		if (sourceId === targetId) return;
		setWindows((prev) => {
			const source = prev.find((w) => w.id === sourceId);
			if (!source) return prev;
			const rest = prev.filter((w) => w.id !== sourceId);
			const idx = rest.findIndex((w) => w.id === targetId);
			if (idx < 0) return prev;
			return [...rest.slice(0, idx), source, ...rest.slice(idx)];
		});
	}

	async function send(windowId: string) {
		const draft = (draftByWindow[windowId] ?? '').trim();
		if (!draft || busyWindow) return;
		const win = windows.find((item) => item.id === windowId);
		const windowAgent = win?.kind === 'chat' ? win.agent ?? 'native' : 'native';
		const operator: ConsoleMessage = {
			id: `${Date.now()}-operator`,
			role: 'operator',
			label: 'OPERATOR',
			body: draft,
			time: nowLabel()
		};
		// Live agent turn — events stream in and render as tool-cards in real time.
		const turnId = `${Date.now()}-agent`;
		const liveTurn: ConsoleMessage = {
			id: turnId,
			role: 'agent',
			label: agentRuntimeLabel(windowAgent),
			body: '',
			time: nowLabel(),
			status: 'pending',
			events: []
		};
		setDraftByWindow((prev) => ({ ...prev, [windowId]: '' }));
		setMessagesByWindow((prev) => ({
			...prev,
			[windowId]: [...(prev[windowId] ?? []), operator, liveTurn]
		}));
		setBusyWindow(windowId);

		const appendEvent = (event: ConsoleChatEvent) => {
			setMessagesByWindow((prev) => ({
				...prev,
				[windowId]: (prev[windowId] ?? []).map((m) =>
					m.id === turnId
						? {
								...m,
								events: [...(m.events ?? []), event],
								body: event.type === 'text' ? `${m.body}${event.text ?? ''}` : m.body,
								status:
									event.type === 'failure'
										? 'failed'
										: event.type === 'result'
											? event.is_error
												? 'failed'
												: 'succeeded'
											: m.status
							}
						: m
				)
			}));
			setAuditEvents((prev) => [event, ...prev].slice(0, 80));
		};

		try {
			await consoleChatStream({ prompt: draft, agent: windowAgent, cwd: boundCwd }, appendEvent);
			// If the stream ended without a terminal result event, settle the turn.
			setMessagesByWindow((prev) => ({
				...prev,
				[windowId]: (prev[windowId] ?? []).map((m) =>
					m.id === turnId && m.status === 'pending' ? { ...m, status: 'succeeded' } : m
				)
			}));
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			setMessagesByWindow((prev) => ({
				...prev,
				[windowId]: (prev[windowId] ?? []).map((m) =>
					m.id === turnId
						? {
								...m,
								status: 'failed',
								body: m.body || msg,
								events: [...(m.events ?? []), { type: 'failure', error: msg }]
							}
						: m
				)
			}));
		} finally {
			setBusyWindow(null);
		}
	}

	// Move the dragged window to follow the cursor, and if its center crosses
	// another window, swap that window into the dragged window's reserved slot —
	// live, while dragging. The dragged window keeps tracking the cursor 1:1.
	function dragMoveAndSwap(clientX: number, clientY: number) {
		const d = dragRef.current;
		if (!d) return;
		const nx = Math.max(0, d.x + clientX - d.startX);
		const ny = Math.max(0, d.y + clientY - d.startY);
		const wins = windowsRef.current;
		const dragged = wins.find((w) => w.id === d.id);
		if (!dragged) return;
		const cx = nx + dragged.w / 2;
		const cy = ny + dragged.h / 2;
		const target = wins.find(
			(w) => w.id !== d.id && cx >= w.x && cx <= w.x + w.w && cy >= w.y && cy <= w.y + w.h
		);
		if (target) {
			const homeX = d.homeX;
			const homeY = d.homeY;
			d.homeX = target.x;
			d.homeY = target.y;
			d.didSwap = true;
			setWindows((prev) =>
				prev.map((w) =>
					w.id === d.id
						? { ...w, x: nx, y: ny }
						: w.id === target.id
							? { ...w, x: homeX, y: homeY }
							: w
				)
			);
		} else {
			setWindows((prev) => prev.map((w) => (w.id === d.id ? { ...w, x: nx, y: ny } : w)));
		}
	}

	// On release, if any swap happened, snap the dragged window into its reserved
	// slot for a clean reorder. If nothing was swapped, it stays where it was dropped.
	function finishFreeDrag() {
		const d = dragRef.current;
		if (d && d.didSwap) {
			const { id, homeX, homeY } = d;
			setWindows((prev) => prev.map((w) => (w.id === id ? { ...w, x: homeX, y: homeY } : w)));
		}
		dragRef.current = null;
	}

	function resizeTo(clientX: number, clientY: number) {
		if (!resize) return;
		resizeWindow(resize.id, resize.w + clientX - resize.startX, resize.h + clientY - resize.startY);
	}

	function onFreePointerMove(e: React.PointerEvent<HTMLDivElement>) {
		if (!drag || drag.pointerId === undefined || e.pointerId !== drag.pointerId) return;
		dragMoveAndSwap(e.clientX, e.clientY);
	}

	function startFreeDrag(e: React.PointerEvent<HTMLDivElement>, win: ConsoleWindow) {
		if (layout !== 'free') return;
		try {
			(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
		} catch {
			// The document-level fallback still tracks movement.
		}
		setActiveWindow(win.id);
		dragRef.current = { id: win.id, pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, x: win.x, y: win.y, homeX: win.x, homeY: win.y, didSwap: false };
		setDrag({ id: win.id, pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, x: win.x, y: win.y });
	}

	function startFreeMouseDrag(e: React.MouseEvent<HTMLDivElement>, win: ConsoleWindow) {
		if (layout !== 'free' || e.button !== 0) return;
		setActiveWindow(win.id);
		dragRef.current = { id: win.id, startX: e.clientX, startY: e.clientY, x: win.x, y: win.y, homeX: win.x, homeY: win.y, didSwap: false };
		setDrag({ id: win.id, startX: e.clientX, startY: e.clientY, x: win.x, y: win.y });
	}

	function stopFreeDrag(e?: React.PointerEvent<HTMLDivElement>) {
		if (e && drag?.pointerId === e.pointerId) {
			try {
				(e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId);
			} catch {
				// Pointer capture may already be released by the browser.
			}
		}
		finishFreeDrag();
		setDrag(null);
	}

	function startResize(e: React.PointerEvent<HTMLDivElement>, win: ConsoleWindow) {
		if (layout !== 'free') return;
		e.stopPropagation();
		try {
			(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
		} catch {
			// The document-level fallback still tracks movement.
		}
		setActiveWindow(win.id);
		setResize({ id: win.id, pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, w: win.w, h: win.h });
	}

	function startResizeMouse(e: React.MouseEvent<HTMLDivElement>, win: ConsoleWindow) {
		if (layout !== 'free' || e.button !== 0) return;
		e.stopPropagation();
		setActiveWindow(win.id);
		setResize({ id: win.id, startX: e.clientX, startY: e.clientY, w: win.w, h: win.h });
	}

	function onResizePointerMove(e: React.PointerEvent<HTMLDivElement>) {
		if (!resize || resize.pointerId === undefined || e.pointerId !== resize.pointerId) return;
		resizeTo(e.clientX, e.clientY);
	}

	function stopResize(e?: React.PointerEvent<HTMLDivElement>) {
		if (e && resize?.pointerId === e.pointerId) {
			try {
				(e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId);
			} catch {
				// Pointer capture may already be released by the browser.
			}
		}
		setResize(null);
	}

	useEffect(() => {
		if (!drag && !resize) return;
		function onPointerMove(e: PointerEvent) {
			if (drag?.pointerId !== undefined && e.pointerId === drag.pointerId) {
				dragMoveAndSwap(e.clientX, e.clientY);
			}
			if (resize?.pointerId !== undefined && e.pointerId === resize.pointerId) {
				resizeWindow(resize.id, resize.w + e.clientX - resize.startX, resize.h + e.clientY - resize.startY);
			}
		}
		function onPointerEnd(e: PointerEvent) {
			if (drag?.pointerId !== undefined && e.pointerId === drag.pointerId) {
				finishFreeDrag();
				setDrag(null);
			}
			if (resize?.pointerId !== undefined && e.pointerId === resize.pointerId) setResize(null);
		}
		function onMouseMove(e: MouseEvent) {
			if (drag && drag.pointerId === undefined) {
				dragMoveAndSwap(e.clientX, e.clientY);
			}
			if (resize && resize.pointerId === undefined) {
				resizeWindow(resize.id, resize.w + e.clientX - resize.startX, resize.h + e.clientY - resize.startY);
			}
		}
		function onMouseEnd() {
			if (drag?.pointerId === undefined) {
				finishFreeDrag();
				setDrag(null);
			}
			if (resize?.pointerId === undefined) setResize(null);
		}
		window.addEventListener('pointermove', onPointerMove);
		window.addEventListener('pointerup', onPointerEnd);
		window.addEventListener('pointercancel', onPointerEnd);
		window.addEventListener('mousemove', onMouseMove);
		window.addEventListener('mouseup', onMouseEnd);
		return () => {
			window.removeEventListener('pointermove', onPointerMove);
			window.removeEventListener('pointerup', onPointerEnd);
			window.removeEventListener('pointercancel', onPointerEnd);
			window.removeEventListener('mousemove', onMouseMove);
			window.removeEventListener('mouseup', onMouseEnd);
		};
	}, [drag, resize]);

	function cycleLayout() {
		setLayout((current) => (current === 'tile' ? 'free' : current === 'free' ? 'tabs' : 'tile'));
	}

	return (
		<Page
			eyebrow="MISSION · CONSOLE"
			title="Console"
			max={null}
			actions={
				<>
					<SessionLaunchers onSpawn={(sessionAgent) => addWindow('chat', sessionAgent)} disabled={!!busyWindow} />
					<StatePill tone={projectState.tone}>{projectState.label}</StatePill>
					<IconAction title="Spawn native chat" onClick={() => addWindow('chat', 'native')}>
						<CopyPlus size={15} strokeWidth={1.7} />
					</IconAction>
					<IconAction title={layout === 'tile' ? 'Free window layout' : layout === 'free' ? 'Exclusive tab layout' : 'Tile windows'} onClick={cycleLayout}>
						{layout === 'tile' ? <MousePointer2 size={15} strokeWidth={1.7} /> : layout === 'free' ? <BoxSelect size={15} strokeWidth={1.7} /> : <LayoutGrid size={15} strokeWidth={1.7} />}
					</IconAction>
				</>
			}
		>
			<GlassPanel
				data-topo={activeChatAgent === 'claude_code' ? 'ai' : 'atlas'}
				style={{
					height: 'calc(100vh - 142px)',
					minHeight: 620,
					display: 'grid',
					gridTemplateRows: '42px minmax(0,1fr)',
					overflow: 'hidden'
				}}
			>
				<WorkbenchBar
					layout={layout}
					windows={windows}
					activeWindow={activeWindow}
					onActivate={setActiveWindow}
					onAddWindow={addWindow}
				/>
				<div
					className={
						layout === 'tile'
							? 'atlas-workbench-tile'
							: layout === 'free'
								? 'atlas-workbench-free'
								: 'atlas-workbench-tabs'
					}
				>
					{visibleWindows.map((win) => (
						<WorkbenchWindow
							key={win.id}
							win={win}
							layout={layout}
							active={win.id === activeWindow}
							busy={busyWindow === win.id}
							dragging={drag?.id === win.id || tileDragId === win.id}
							resizing={resize?.id === win.id}
							tileDragId={tileDragId}
							onActivate={() => setActiveWindow(win.id)}
							onClose={() => closeWindow(win.id)}
							onStartFreeDrag={startFreeDrag}
							onStartFreeMouseDrag={startFreeMouseDrag}
							onMoveFreeDrag={onFreePointerMove}
							onStopFreeDrag={stopFreeDrag}
							onStartResize={startResize}
							onStartResizeMouse={startResizeMouse}
							onMoveResize={onResizePointerMove}
							onStopResize={stopResize}
							onTileDragStart={setTileDragId}
							onTileDragEnd={() => setTileDragId(null)}
							onReorder={reorderWindow}
						>
							{win.kind === 'chat' && (
								<ChatPane
									windowId={win.id}
									agent={win.agent ?? 'native'}
									boundCwd={boundCwd}
									projectName={activeProject?.name ?? projectState.detail}
									messages={messagesByWindow[win.id] ?? []}
									draft={draftByWindow[win.id] ?? ''}
									busy={busyWindow === win.id}
									onDraft={(value) => setDraftByWindow((prev) => ({ ...prev, [win.id]: value }))}
									onSend={() => void send(win.id)}
								/>
							)}
							{win.kind === 'tools' && (
								<ToolsPane
									layout={layout}
									bindingMode={bindingMode}
									boundCwd={boundCwd}
									folderPath={folderPath}
									folderErr={folderErr}
									onSpawnAgent={(sessionAgent) => addWindow('chat', sessionAgent)}
									onLayout={setLayout}
									onBindingMode={setBindingMode}
									onFolderPath={setFolderPath}
									onChooseFolder={() => void chooseFolder()}
								/>
							)}
							{win.kind === 'context' && (
								<ContextPane
									load={load}
									activeProject={activeProject}
									projects={projects}
									projectState={projectState}
									bindingMode={bindingMode}
									boundCwd={boundCwd}
									onPickProject={pickProject}
									onUseFolder={() => setBindingMode('folder')}
									onSpawnBrain={() => addWindow('context')}
								/>
							)}
							{win.kind === 'audit' && <AuditPane events={auditEvents} />}
						</WorkbenchWindow>
					))}
				</div>
			</GlassPanel>
		</Page>
	);
}

function WorkbenchBar({
	layout,
	windows,
	activeWindow,
	onActivate,
	onAddWindow
}: {
	layout: LayoutMode;
	windows: ConsoleWindow[];
	activeWindow: string;
	onActivate: (id: string) => void;
	onAddWindow: (kind: WindowKind, agent?: AgentRuntime) => void;
}) {
	return (
		<div style={barStyle}>
			{windows.map((win) => {
				const Icon = KIND_ICON[win.kind];
				const active = win.id === activeWindow;
				return (
					<button
						key={win.id}
						type="button"
						onClick={() => onActivate(win.id)}
						data-topo={active ? 'info' : 'atlas'}
						style={{
							...tabStyle,
							background: active ? 'rgba(13,16,24,0.96)' : 'rgba(237,234,224,0.025)',
							borderTopColor: active ? 'rgba(79,139,255,0.58)' : 'transparent',
							color: active ? 'var(--l2-fg-1)' : 'var(--l2-fg-3)'
						}}
					>
						<Icon size={14} strokeWidth={1.6} />
						<span>{win.title}</span>
					</button>
				);
			})}
			<div style={{ flex: 1 }} />
			<MiniMenu onPick={onAddWindow} />
			<WorkbenchBadge
				icon={layout === 'tile' ? <Columns3 size={13} /> : layout === 'free' ? <BoxSelect size={13} /> : <LayoutGrid size={13} />}
				label={layout === 'tile' ? 'TILE MODE' : layout === 'free' ? 'FREE MODE' : 'EXCLUSIVE TABS'}
			/>
		</div>
	);
}

function WorkbenchWindow({
	win,
	layout,
	active,
	busy,
	dragging,
	resizing,
	tileDragId,
	children,
	onActivate,
	onClose,
	onStartFreeDrag,
	onStartFreeMouseDrag,
	onMoveFreeDrag,
	onStopFreeDrag,
	onStartResize,
	onStartResizeMouse,
	onMoveResize,
	onStopResize,
	onTileDragStart,
	onTileDragEnd,
	onReorder
}: {
	win: ConsoleWindow;
	layout: LayoutMode;
	active: boolean;
	busy: boolean;
	dragging: boolean;
	resizing: boolean;
	tileDragId: string | null;
	children: React.ReactNode;
	onActivate: () => void;
	onClose: () => void;
	onStartFreeDrag: (e: React.PointerEvent<HTMLDivElement>, win: ConsoleWindow) => void;
	onStartFreeMouseDrag: (e: React.MouseEvent<HTMLDivElement>, win: ConsoleWindow) => void;
	onMoveFreeDrag: (e: React.PointerEvent<HTMLDivElement>) => void;
	onStopFreeDrag: (e?: React.PointerEvent<HTMLDivElement>) => void;
	onStartResize: (e: React.PointerEvent<HTMLDivElement>, win: ConsoleWindow) => void;
	onStartResizeMouse: (e: React.MouseEvent<HTMLDivElement>, win: ConsoleWindow) => void;
	onMoveResize: (e: React.PointerEvent<HTMLDivElement>) => void;
	onStopResize: (e?: React.PointerEvent<HTMLDivElement>) => void;
	onTileDragStart: (id: string) => void;
	onTileDragEnd: () => void;
	onReorder: (sourceId: string, targetId: string) => void;
}) {
	const Icon = KIND_ICON[win.kind];
	const windowAgent = win.kind === 'chat' ? win.agent ?? 'native' : undefined;
	const freeStyle =
		layout === 'free'
			? {
					position: 'absolute' as const,
					left: win.x,
					top: win.y,
					width: win.w,
					height: win.h,
					zIndex: dragging ? 40 : active ? 30 : 10,
					// Dragged window tracks the cursor 1:1; displaced windows glide to their new slot.
					transition: dragging
						? 'none'
						: 'left 180ms var(--l2-ease), top 180ms var(--l2-ease), box-shadow 180ms var(--l2-ease), border-color 180ms var(--l2-ease)'
				}
			: {};
	return (
		<section
			className={`atlas-workbench-window${dragging ? ' is-dragging' : ''}${resizing ? ' is-resizing' : ''}`}
			data-topo={win.kind === 'chat' ? 'info' : win.kind === 'tools' ? 'ai' : win.kind === 'audit' ? 'good' : 'atlas'}
			data-agent={windowAgent}
			draggable={layout === 'tile'}
			onDragStart={(e) => {
				e.dataTransfer.effectAllowed = 'move';
				e.dataTransfer.setData('text/plain', win.id);
				onTileDragStart(win.id);
			}}
			onDragEnd={onTileDragEnd}
			onDragOver={(e) => {
				e.preventDefault();
				const sourceId = tileDragId || e.dataTransfer.getData('text/plain');
				if (sourceId && sourceId !== win.id) onReorder(sourceId, win.id);
			}}
			onDrop={(e) => {
				e.preventDefault();
				const sourceId = tileDragId || e.dataTransfer.getData('text/plain');
				if (sourceId) onReorder(sourceId, win.id);
				onTileDragEnd();
			}}
			onClick={onActivate}
			style={{
				...windowStyle,
				...freeStyle,
				borderColor: active ? 'rgba(79,139,255,0.42)' : 'var(--l2-hairline)',
				boxShadow: active ? '0 0 0 1px rgba(79,139,255,0.10), 0 18px 52px rgba(0,0,0,0.45)' : 'inset 0 1px 0 rgba(237,234,224,0.05)'
			}}
		>
			<div
				className="atlas-window-drag"
				onPointerDown={(e) => onStartFreeDrag(e, win)}
				onMouseDown={(e) => onStartFreeMouseDrag(e, win)}
				onPointerMove={onMoveFreeDrag}
				onPointerUp={onStopFreeDrag}
				onPointerCancel={onStopFreeDrag}
				style={windowHeaderStyle}
			>
				<span style={{ display: 'flex', color: 'var(--atlas-bronze)' }}>
					{layout === 'free' ? <Grip size={14} /> : <GripVertical size={14} />}
				</span>
				<Icon size={14} strokeWidth={1.6} style={{ color: 'var(--atlas-celestial)' }} />
				<span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{win.title}</span>
				<span style={busy ? liveBadgeStyle : tinyBadgeStyle}>{busy ? 'LIVE' : win.kind.toUpperCase()}</span>
				<button type="button" onClick={(e) => { e.stopPropagation(); onClose(); }} style={miniIconButtonStyle} title="Close window">
					<X size={13} strokeWidth={1.7} />
				</button>
			</div>
			<div style={{ minHeight: 0, overflow: 'hidden', height: '100%' }}>{children}</div>
			{layout === 'free' && (
				<div
					className="atlas-window-resize"
					onPointerDown={(e) => onStartResize(e, win)}
					onMouseDown={(e) => onStartResizeMouse(e, win)}
					onPointerMove={onMoveResize}
					onPointerUp={onStopResize}
					onPointerCancel={onStopResize}
					title="Resize window"
				/>
			)}
		</section>
	);
}

function ChatPane({
	windowId,
	agent,
	boundCwd,
	projectName,
	messages,
	draft,
	busy,
	onDraft,
	onSend
}: {
	windowId: string;
	agent: AgentRuntime;
	boundCwd: string | null;
	projectName: string;
	messages: ConsoleMessage[];
	draft: string;
	busy: boolean;
	onDraft: (value: string) => void;
	onSend: () => void;
}) {
	return (
		<div style={chatPaneStyle}>
			<div style={chatTopStyle}>
				<div style={{ minWidth: 0 }}>
					<div style={monoLabelStyle}>{agentRuntimeLabel(agent)} · {windowId.toUpperCase()}</div>
					<div style={titleTextStyle}>{projectName}</div>
				</div>
				<WorkbenchBadge icon={<GitBranch size={13} />} label={boundCwd ? 'BOUND' : 'UNBOUND'} />
			</div>
			<TopoScroll tone={agent === 'claude_code' ? 'atlas' : 'info'} style={{ minHeight: 0 }} viewportStyle={messageListStyle}>
				{messages.map((message) =>
					message.role === 'agent' && (message.events?.length || message.status === 'pending') ? (
						<AgentTurn key={message.id} message={message} />
					) : (
						<MessageBubble key={message.id} message={message} />
					)
				)}
			</TopoScroll>
			<div style={composerWrapStyle}>
				<textarea
					value={draft}
					onChange={(e) => onDraft(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === 'Enter' && !e.shiftKey) {
							e.preventDefault();
							onSend();
						}
					}}
					placeholder={agent === 'claude_code' ? 'Ask Claude Code in this folder' : 'Message ATLAS'}
					rows={3}
					style={composerStyle}
				/>
				<button type="button" onClick={onSend} disabled={!draft.trim() || busy} style={sendButtonStyle} title="Send">
					<SendHorizontal size={16} strokeWidth={1.8} />
				</button>
			</div>
		</div>
	);
}

function ToolsPane({
	layout,
	bindingMode,
	boundCwd,
	folderPath,
	folderErr,
	onSpawnAgent,
	onLayout,
	onBindingMode,
	onFolderPath,
	onChooseFolder
}: {
	layout: LayoutMode;
	bindingMode: BindingMode;
	boundCwd: string | null;
	folderPath: string;
	folderErr: string | null;
	onSpawnAgent: (agent: AgentRuntime) => void;
	onLayout: (layout: LayoutMode) => void;
	onBindingMode: (mode: BindingMode) => void;
	onFolderPath: (path: string) => void;
	onChooseFolder: () => void;
}) {
	return (
		<div style={paneBodyStyle}>
			<SectionTitle>Launch Session</SectionTitle>
			<SessionLaunchers onSpawn={onSpawnAgent} />
			<SectionTitle>Binding</SectionTitle>
			<div style={segStyle}>
				<SegmentButton active={bindingMode === 'project'} onClick={() => onBindingMode('project')}>Project</SegmentButton>
				<SegmentButton active={bindingMode === 'folder'} onClick={() => onBindingMode('folder')}>Folder</SegmentButton>
			</div>
			{bindingMode === 'folder' && (
				<div style={{ display: 'grid', gap: 8 }}>
					<div style={pathInputWrapStyle}>
						<input
							value={folderPath}
							onChange={(e) => onFolderPath(e.target.value)}
							placeholder="C:\\path\\to\\workspace"
							style={pathInputStyle}
						/>
						<button type="button" onClick={onChooseFolder} style={miniBrowseStyle} title="Choose folder">
							<FolderOpen size={14} />
						</button>
					</div>
					{folderErr && <div style={{ ...pathTextStyle, color: 'var(--l2-error)' }}>{folderErr}</div>}
				</div>
			)}
			<Metric label="CWD" value={boundCwd ? shortPath(boundCwd) : 'Not bound'} />
			<SectionTitle>Layout</SectionTitle>
			<div style={segStyle}>
				<SegmentButton active={layout === 'tile'} onClick={() => onLayout('tile')}>Tile</SegmentButton>
				<SegmentButton active={layout === 'free'} onClick={() => onLayout('free')}>Free</SegmentButton>
				<SegmentButton active={layout === 'tabs'} onClick={() => onLayout('tabs')}>Tabs</SegmentButton>
			</div>
			<ToolRow icon={<SquareTerminal size={14} />} name="shell" state={boundCwd ? 'READY' : 'UNBOUND'} />
			<ToolRow icon={<Waypoints size={14} />} name="topo.context" state="LIVE" />
			<ToolRow icon={<Bot size={14} />} name="claude.code" state="SPAWN" />
		</div>
	);
}

function ContextPane({
	load,
	activeProject,
	projects,
	projectState,
	bindingMode,
	boundCwd,
	onPickProject,
	onUseFolder,
	onSpawnBrain
}: {
	load: Load;
	activeProject: Project | null;
	projects: Project[];
	projectState: { label: string; detail: string; tone: 'muted' | 'info' | 'good' | 'warn' | 'bad' };
	bindingMode: BindingMode;
	boundCwd: string | null;
	onPickProject: (project: Project) => void;
	onUseFolder: () => void;
	onSpawnBrain: () => void;
}) {
	return (
		<div style={paneBodyStyle}>
			<SectionTitle>Current Scope</SectionTitle>
			<div style={projectCardStyle}>
				<div style={monoLabelStyle}>{projectState.label}</div>
				<div style={titleTextStyle}>{projectState.detail}</div>
				<div style={{ ...pathTextStyle, marginTop: 9 }}>{boundCwd ? shortPath(boundCwd) : 'No root path attached'}</div>
			</div>
			<SectionTitle>Hermes Brain</SectionTitle>
			<GraphBrainSurface activeProject={activeProject} boundCwd={boundCwd} onSpawnBrain={onSpawnBrain} />
			<SectionTitle>Projects</SectionTitle>
			{load.s === 'error' && <div style={emptyTinyStyle}>Project registry unavailable</div>}
			<div style={{ display: 'grid', gap: 7 }}>
				{projects.map((project) => (
					<button
						key={project.id}
						type="button"
						onClick={() => onPickProject(project)}
						style={{
							...projectRowStyle,
							borderColor: activeProject?.id === project.id && bindingMode === 'project' ? 'rgba(70,240,160,0.38)' : 'rgba(237,234,224,0.06)',
							background: activeProject?.id === project.id && bindingMode === 'project' ? 'rgba(70,240,160,0.07)' : 'rgba(237,234,224,0.025)'
						}}
					>
						<Circle size={8} fill={activeProject?.id === project.id && bindingMode === 'project' ? 'var(--atlas-emerald)' : 'transparent'} />
						<span>{project.name}</span>
						<Check size={14} style={{ color: activeProject?.id === project.id && bindingMode === 'project' ? 'var(--atlas-emerald)' : 'transparent' }} />
					</button>
				))}
				{projects.length === 0 && <div style={emptyTinyStyle}>No projects loaded</div>}
			</div>
			<button type="button" onClick={onUseFolder} style={folderModeButtonStyle}>
				<Folder size={14} />
				Use folder binding
			</button>
		</div>
	);
}

function GraphBrainSurface({ activeProject, boundCwd, onSpawnBrain }: { activeProject: Project | null; boundCwd: string | null; onSpawnBrain: () => void }) {
	const nodes = [
		{ id: 'memory', label: 'MEMORY', x: 48, y: 22, z: 1.18, tone: 'good' },
		{ id: 'skills', label: 'SKILLS', x: 25, y: 50, z: 0.86, tone: 'info' },
		{ id: 'runs', label: 'RUNS', x: 72, y: 52, z: 0.96, tone: 'warn' },
		{ id: 'audit', label: 'AUDIT', x: 42, y: 75, z: 0.74, tone: 'bad' },
		{ id: 'graph', label: 'GRAPHIFY', x: 58, y: 47, z: 1.34, tone: 'ai' }
	];
	return (
		<div className="atlas-brainfield" data-topo="ai">
			<svg className="atlas-brainfield-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
				<path d="M48 22 C38 34, 31 40, 25 50" />
				<path d="M48 22 C55 33, 65 42, 72 52" />
				<path d="M58 47 C52 56, 48 66, 42 75" />
				<path d="M25 50 C38 45, 48 44, 58 47" />
				<path d="M72 52 C64 48, 61 47, 58 47" />
			</svg>
			{nodes.map((node) => (
				<span
					key={node.id}
					className="atlas-brain-node"
					data-tone={node.tone}
					style={{ left: `${node.x}%`, top: `${node.y}%`, '--z': String(node.z) } as React.CSSProperties}
				>
					{node.label}
				</span>
			))}
			<div className="atlas-brainfield-readout">
				<span>{activeProject ? activeProject.name : boundCwd ? 'FOLDER BRAIN' : 'UNBOUND BRAIN'}</span>
				<span>GRAPHIFY: DISABLED</span>
				<span>HERMES: CORTEX CONTRACT</span>
			</div>
			<button type="button" onClick={onSpawnBrain} className="atlas-brainfield-button">
				SPAWN BRAIN VIEW
			</button>
		</div>
	);
}
function AuditPane({ events }: { events: ConsoleChatEvent[] }) {
	return (
		<TopoScroll tone="good" style={{ height: '100%' }} viewportStyle={auditBodyStyle}>
			{events.length === 0 ? (
				<div style={emptyAuditStyle}>No console events recorded.</div>
			) : (
				events.map((event, idx) => (
					<div key={`${idx}-${event.type}`} style={auditRowStyle}>
						<span style={monoLabelStyle}>{event.type}</span>
						<span style={{ ...pathTextStyle, color: 'var(--l2-fg-2)' }}>
							{event.text ?? event.tool_name ?? event.error ?? event.subtype ?? 'event'}
						</span>
					</div>
				))
			)}
		</TopoScroll>
	);
}

// ── Tool-calling inline rendering (Claude-Code-style cards) ─────────────────

const TOOL_ICON: Record<string, React.ElementType> = {
	read: FileText,
	grep: Search,
	glob: FolderSearch,
	ls: ListTree,
	edit: FilePen,
	multiedit: FilePen,
	write: FilePlus2,
	bash: SquareTerminal
};

function toolIcon(name: string | null | undefined): React.ElementType {
	if (!name) return Wrench;
	return TOOL_ICON[name.toLowerCase()] ?? Wrench;
}

function asRecord(value: unknown): Record<string, unknown> {
	return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function summarizeToolInput(name: string | null | undefined, input: unknown): string {
	const o = asRecord(input);
	const n = (name ?? '').toLowerCase();
	const str = (k: string) => (typeof o[k] === 'string' ? (o[k] as string) : undefined);
	if (n === 'read') return str('file_path') ?? str('path') ?? '';
	if (n === 'grep') {
		const pat = str('pattern') ?? '';
		const path = str('path') ?? str('glob');
		return path ? `${pat}  ·  ${path}` : pat;
	}
	if (n === 'glob') return str('pattern') ?? '';
	if (n === 'ls') return str('path') ?? '';
	if (n === 'edit' || n === 'multiedit' || n === 'write') return str('file_path') ?? str('path') ?? '';
	if (n === 'bash') return str('command') ?? '';
	const keys = Object.keys(o);
	if (keys.length === 0) return '';
	const first = o[keys[0]];
	return typeof first === 'string' ? first : JSON.stringify(o).slice(0, 120);
}

function resultToText(content: unknown): string {
	if (content == null) return '';
	if (typeof content === 'string') return content;
	if (Array.isArray(content)) {
		return content
			.map((b) => {
				const r = asRecord(b);
				if (typeof r.text === 'string') return r.text;
				return typeof b === 'string' ? b : JSON.stringify(b);
			})
			.join('\n');
	}
	const r = asRecord(content);
	if (typeof r.text === 'string') return r.text;
	return JSON.stringify(content, null, 2);
}

function clip(text: string, max = 4000): string {
	return text.length > max ? `${text.slice(0, max)}\n… (${text.length - max} more chars)` : text;
}

function DiffView({ oldStr, newStr }: { oldStr: string; newStr: string }) {
	const oldLines = oldStr ? oldStr.split('\n') : [];
	const newLines = newStr ? newStr.split('\n') : [];
	return (
		<div style={diffWrapStyle}>
			{oldLines.map((line, i) => (
				<div key={`o-${i}`} style={{ ...diffLineStyle, background: 'rgba(255,77,125,0.10)', color: '#ffb3c6' }}>
					<span style={diffSignStyle}>-</span>
					{line || ' '}
				</div>
			))}
			{newLines.map((line, i) => (
				<div key={`n-${i}`} style={{ ...diffLineStyle, background: 'rgba(70,240,160,0.10)', color: '#9bf3c9' }}>
					<span style={diffSignStyle}>+</span>
					{line || ' '}
				</div>
			))}
		</div>
	);
}

function ToolCallCard({ event, result }: { event: ConsoleChatEvent; result?: ConsoleChatEvent }) {
	const [open, setOpen] = useState(false);
	const Icon = toolIcon(event.tool_name);
	const name = (event.tool_name ?? 'tool').toUpperCase();
	const summary = summarizeToolInput(event.tool_name, event.input);
	const done = !!result;
	const isEdit = ['edit', 'multiedit', 'write'].includes((event.tool_name ?? '').toLowerCase());
	const editInput = asRecord(event.input);
	const oldStr = typeof editInput.old_string === 'string' ? editInput.old_string : '';
	const newStr =
		typeof editInput.new_string === 'string'
			? editInput.new_string
			: typeof editInput.content === 'string'
				? editInput.content
				: '';
	const resultText = result ? clip(resultToText(result.content)) : '';
	const Chevron = open ? ChevronDown : ChevronRight;
	return (
		<div style={toolCardStyle} data-topo="ai">
			<button type="button" style={toolCardHeaderStyle} onClick={() => setOpen((v) => !v)}>
				<Chevron size={13} strokeWidth={1.8} style={{ color: 'var(--l2-fg-3)', flex: '0 0 auto' }} />
				<Icon size={14} strokeWidth={1.7} style={{ color: 'var(--atlas-celestial)', flex: '0 0 auto' }} />
				<span style={toolNameStyle}>{name}</span>
				<span style={toolSummaryStyle}>{summary}</span>
				<span style={{ flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
					<Circle size={7} fill={done ? 'rgba(70,240,160,0.95)' : 'rgba(255,214,0,0.95)'} stroke="none" />
					<span style={monoMicroStyle}>{done ? 'DONE' : 'RUNNING'}</span>
				</span>
			</button>
			{open && (
				<div style={toolCardBodyStyle}>
					{isEdit && (oldStr || newStr) ? (
						<DiffView oldStr={oldStr} newStr={newStr} />
					) : (
						<>
							<div style={toolFieldLabelStyle}>INPUT</div>
							<pre style={toolPreStyle}>{JSON.stringify(event.input ?? {}, null, 2)}</pre>
						</>
					)}
					{resultText && (
						<>
							<div style={toolFieldLabelStyle}>OUTPUT</div>
							<pre style={toolPreStyle}>{resultText}</pre>
						</>
					)}
				</div>
			)}
		</div>
	);
}

function AgentTurn({ message }: { message: ConsoleMessage }) {
	const events = message.events ?? [];
	const resultsByCall = useMemo(() => {
		const map: Record<string, ConsoleChatEvent> = {};
		for (const e of events) {
			if (e.type === 'tool_result' && e.tool_call_id) map[e.tool_call_id] = e;
		}
		return map;
	}, [events]);
	const summary = events.find((e) => e.type === 'result');
	return (
		<div style={agentTurnStyle} data-topo={message.status === 'failed' ? 'bad' : 'good'}>
			<div style={agentTurnHeaderStyle}>
				<Bot size={13} strokeWidth={1.7} style={{ color: 'rgba(70,240,160,0.95)' }} />
				<span style={monoLabelStyle}>{message.label}</span>
				<span style={{ ...pathTextStyle, fontSize: 10 }}>{message.time}</span>
				{message.status === 'pending' && <span style={liveBadgeStyle}>LIVE</span>}
			</div>
			{events.length === 0 && message.status === 'pending' && (
				<div style={{ ...agentTextStyle, opacity: 0.6 }}>Working…</div>
			)}
			{events.map((event, idx) => {
				if (event.type === 'text') {
					return event.text ? (
						<div key={idx} style={agentTextStyle}>
							{event.text}
						</div>
					) : null;
				}
				if (event.type === 'tool_call') {
					return (
						<ToolCallCard
							key={idx}
							event={event}
							result={event.tool_call_id ? resultsByCall[event.tool_call_id] : undefined}
						/>
					);
				}
				if (event.type === 'failure') {
					return (
						<div key={idx} style={turnErrorStyle}>
							<AlertTriangle size={13} strokeWidth={1.8} />
							<span>{event.error ?? 'Agent failure'}</span>
						</div>
					);
				}
				return null;
			})}
			{summary && (summary.num_turns != null || summary.total_cost_usd != null) && (
				<div style={turnFooterStyle}>
					{summary.num_turns != null && <span>{summary.num_turns} turns</span>}
					{summary.total_cost_usd != null && <span>${summary.total_cost_usd.toFixed(4)}</span>}
				</div>
			)}
		</div>
	);
}

function MessageBubble({ message }: { message: ConsoleMessage }) {
	const operator = message.role === 'operator';
	const failed = message.status === 'failed';
	const pending = message.status === 'pending';
	return (
		<div style={{ display: 'flex', justifyContent: operator ? 'flex-end' : 'flex-start' }}>
			<div
				data-topo={failed ? 'bad' : operator ? 'info' : pending ? 'ai' : 'good'}
				style={{
					maxWidth: 'min(760px, 90%)',
					borderRadius: 2,
					border: failed
						? '1px solid rgba(255,77,125,0.32)'
						: operator
							? '1px solid rgba(79,139,255,0.32)'
							: '1px solid rgba(70,240,160,0.22)',
					background: failed
						? 'rgba(255,77,125,0.06)'
						: operator
							? 'rgba(79,139,255,0.10)'
							: 'rgba(70,240,160,0.055)',
					padding: '12px 13px',
					animation: 'atlas-window-in 260ms var(--l2-ease)'
				}}
			>
				<div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
					<span style={monoLabelStyle}>{message.label}</span>
					<span style={{ ...pathTextStyle, fontSize: 10 }}>{message.time}</span>
					{pending && <span style={liveBadgeStyle}>LIVE</span>}
				</div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 13.5, lineHeight: 1.55, overflowWrap: 'anywhere' }}>{message.body}</div>
			</div>
		</div>
	);
}

function SessionLaunchers({ onSpawn, disabled }: { onSpawn: (agent: AgentRuntime) => void; disabled?: boolean }) {
	return (
		<div style={agentToggleStyle}>
			<SegmentButton active={false} disabled={disabled} onClick={() => onSpawn('native')}>+ Native</SegmentButton>
			<SegmentButton active={false} disabled={disabled} onClick={() => onSpawn('claude_code')} tone="orange">+ Claude Code</SegmentButton>
		</div>
	);
}

function SegmentButton({ children, active, onClick, disabled, tone = 'blue' }: { children: React.ReactNode; active: boolean; onClick: () => void; disabled?: boolean; tone?: 'blue' | 'orange' }) {
	const color = tone === 'orange' ? 'var(--atlas-bronze)' : 'var(--atlas-celestial)';
	return (
		<button
			type="button"
			disabled={disabled}
			onClick={onClick}
			style={{
				height: 30,
				padding: '0 10px',
				borderRadius: 2,
				border: `1px solid ${active ? color : 'rgba(237,234,224,0.08)'}`,
				background: active ? (tone === 'orange' ? 'rgba(224,169,78,0.12)' : 'rgba(79,139,255,0.12)') : 'rgba(237,234,224,0.025)',
				color: active ? color : 'var(--l2-fg-3)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				letterSpacing: '0.13em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1
			}}
		>
			{children}
		</button>
	);
}

function MiniMenu({ onPick }: { onPick: (kind: WindowKind, agent?: AgentRuntime) => void }) {
	const [open, setOpen] = useState(false);
	const items: Array<{ label: string; kind: WindowKind; agent?: AgentRuntime }> = [
		{ label: 'native chat', kind: 'chat', agent: 'native' },
		{ label: 'claude code', kind: 'chat', agent: 'claude_code' },
		{ label: 'audit', kind: 'audit' },
		{ label: 'tools', kind: 'tools' },
		{ label: 'context', kind: 'context' }
	];
	return (
		<div style={{ position: 'relative' }}>
			<button type="button" onClick={() => setOpen((v) => !v)} style={miniMenuButtonStyle} title="Create window">
				<CopyPlus size={14} />
				<ChevronDown size={13} />
			</button>
			{open && (
				<div style={miniMenuStyle}>
					{items.map(({ label, kind, agent }) => {
						const Icon = KIND_ICON[kind];
						return (
							<button
								key={`${kind}-${agent ?? label}`}
								type="button"
								onClick={() => {
									onPick(kind, agent);
									setOpen(false);
								}}
								style={miniMenuItemStyle}
							>
								<Icon size={13} />
								{label}
							</button>
						);
					})}
				</div>
			)}
		</div>
	);
}

function Metric({ label, value }: { label: string; value: string }) {
	return (
		<div style={metricStyle}>
			<span style={monoLabelStyle}>{label}</span>
			<span style={{ ...pathTextStyle, color: 'var(--l2-fg-2)' }}>{value}</span>
		</div>
	);
}

function ToolRow({ icon, name, state }: { icon: React.ReactNode; name: string; state: string }) {
	return (
		<div style={toolRowStyle}>
			<span style={{ display: 'flex', color: 'var(--atlas-celestial)' }}>{icon}</span>
			<span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
			<span style={tinyBadgeStyle}>{state}</span>
		</div>
	);
}

function StatePill({ children, tone }: { children: React.ReactNode; tone: 'muted' | 'info' | 'good' | 'warn' | 'bad' }) {
	const dot =
		tone === 'good'
			? 'var(--atlas-emerald)'
			: tone === 'info'
				? 'var(--atlas-celestial)'
				: tone === 'warn'
					? '#FFD600'
					: tone === 'bad'
						? 'var(--l2-error)'
						: 'var(--l2-fg-3)';
	return (
		<span style={statePillStyle}>
			<span style={{ width: 7, height: 7, borderRadius: '50%', background: dot, boxShadow: `0 0 10px ${dot}` }} />
			{children}
		</span>
	);
}

function WorkbenchBadge({ icon, label }: { icon: React.ReactNode; label: string }) {
	return (
		<span style={workbenchBadgeStyle}>
			{icon}
			{label}
		</span>
	);
}

function IconAction({ children, title, onClick }: { children: React.ReactNode; title: string; onClick: () => void }) {
	return (
		<button type="button" onClick={onClick} style={iconButtonStyle} title={title}>
			{children}
		</button>
	);
}

function SectionTitle({ children }: { children: React.ReactNode }) {
	return <div style={sectionTitleStyle}>{children}</div>;
}

const iconButtonStyle: React.CSSProperties = {
	width: 34,
	height: 34,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(237,234,224,0.025)',
	color: 'var(--l2-fg-2)',
	cursor: 'pointer'
};

const barStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'stretch',
	borderBottom: '1px solid var(--l2-hairline)',
	background: 'rgba(5,6,10,0.44)',
	overflowX: 'auto',
	overflowY: 'hidden'
};

const tabStyle: React.CSSProperties = {
	height: 42,
	minWidth: 150,
	display: 'inline-flex',
	alignItems: 'center',
	gap: 8,
	padding: '0 13px',
	border: 'none',
	borderRight: '1px solid var(--l2-hairline)',
	borderTop: '2px solid transparent',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.04em',
	cursor: 'pointer',
	flex: '0 0 auto'
};

const windowStyle: React.CSSProperties = {
	minWidth: 0,
	minHeight: 0,
	display: 'grid',
	gridTemplateRows: '34px minmax(0,1fr)',
	border: '1px solid var(--l2-hairline)',
	borderRadius: 2,
	background: 'linear-gradient(180deg, rgba(16,19,27,0.72), rgba(7,8,12,0.72))',
	backdropFilter: 'blur(16px) saturate(1.35)',
	WebkitBackdropFilter: 'blur(16px) saturate(1.35)',
	overflow: 'hidden',
	animation: 'atlas-window-in 260ms var(--l2-ease)',
	transition: 'box-shadow 180ms var(--l2-ease), border-color 180ms var(--l2-ease), transform 260ms var(--l2-ease)'
};

const windowHeaderStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: '16px 16px minmax(0,1fr) auto 24px',
	alignItems: 'center',
	gap: 8,
	padding: '0 8px',
	borderBottom: '1px solid rgba(237,234,224,0.06)',
	background: 'rgba(5,6,10,0.44)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.13em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-2)',
	cursor: 'grab'
};

const chatPaneStyle: React.CSSProperties = {
	height: '100%',
	minHeight: 0,
	display: 'grid',
	gridTemplateRows: '58px minmax(0,1fr) auto',
	background: 'rgba(6,7,11,0.20)'
};

const chatTopStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	gap: 12,
	padding: '0 14px',
	borderBottom: '1px solid rgba(237,234,224,0.06)'
};

const messageListStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	gap: 12,
	padding: 14
};

const composerWrapStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: 'minmax(0,1fr) 42px',
	gap: 10,
	padding: 12,
	borderTop: '1px solid rgba(237,234,224,0.06)',
	background: 'rgba(5,6,10,0.52)'
};

const composerStyle: React.CSSProperties = {
	width: '100%',
	resize: 'none',
	borderRadius: 2,
	border: '1px solid rgba(79,139,255,0.34)',
	background: 'rgba(9,11,16,0.76)',
	color: 'var(--l2-fg-1)',
	fontFamily: 'var(--l2-font-sans)',
	fontSize: 13.5,
	lineHeight: 1.45,
	padding: '11px 12px',
	outline: 'none',
	boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.05)'
};

const sendButtonStyle: React.CSSProperties = {
	width: 42,
	height: 42,
	alignSelf: 'end',
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid rgba(79,139,255,0.45)',
	background: 'rgba(79,139,255,0.14)',
	color: 'var(--atlas-celestial)',
	cursor: 'pointer'
};

const paneBodyStyle: React.CSSProperties = {
	height: '100%',
	minHeight: 0,
	overflow: 'auto',
	padding: 12
};

const auditBodyStyle: React.CSSProperties = {
	padding: 12,
	display: 'flex',
	flexDirection: 'column',
	gap: 7
};

const monoLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.17em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)'
};

const titleTextStyle: React.CSSProperties = {
	marginTop: 3,
	color: 'var(--l2-fg-1)',
	fontSize: 14,
	fontWeight: 700,
	whiteSpace: 'nowrap',
	overflow: 'hidden',
	textOverflow: 'ellipsis'
};

const pathTextStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	lineHeight: 1.45,
	color: 'var(--l2-fg-3)',
	whiteSpace: 'nowrap',
	overflow: 'hidden',
	textOverflow: 'ellipsis'
};

const sectionTitleStyle: React.CSSProperties = {
	margin: '14px 0 8px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.22em',
	textTransform: 'uppercase',
	color: 'var(--atlas-bronze)'
};

const tinyBadgeStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.12em',
	color: 'var(--atlas-celestial)',
	border: '1px solid rgba(79,139,255,0.24)',
	background: 'rgba(79,139,255,0.07)',
	borderRadius: 2,
	padding: '2px 5px'
};

const liveBadgeStyle: React.CSSProperties = {
	...tinyBadgeStyle,
	color: 'var(--atlas-emerald)',
	border: '1px solid rgba(70,240,160,0.32)',
	background: 'rgba(70,240,160,0.08)'
};

const miniIconButtonStyle: React.CSSProperties = {
	width: 22,
	height: 22,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	border: '1px solid transparent',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer'
};

const statePillStyle: React.CSSProperties = {
	height: 34,
	display: 'inline-flex',
	alignItems: 'center',
	gap: 8,
	padding: '0 11px',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(237,234,224,0.025)',
	color: 'var(--l2-fg-2)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.16em',
	textTransform: 'uppercase'
};

const workbenchBadgeStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	margin: '0 10px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.16em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)',
	whiteSpace: 'nowrap'
};

const agentToggleStyle: React.CSSProperties = {
	display: 'inline-flex',
	gap: 4,
	padding: 2,
	border: '1px solid var(--l2-hairline)',
	borderRadius: 2,
	background: 'rgba(237,234,224,0.02)'
};

const segStyle: React.CSSProperties = {
	display: 'inline-flex',
	gap: 4,
	padding: 2,
	border: '1px solid rgba(237,234,224,0.07)',
	borderRadius: 2,
	background: 'rgba(237,234,224,0.02)'
};

const metricStyle: React.CSSProperties = {
	display: 'grid',
	gap: 5,
	padding: '10px 0',
	borderBottom: '1px solid rgba(237,234,224,0.06)'
};

const toolRowStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: '18px minmax(0,1fr) auto',
	alignItems: 'center',
	gap: 8,
	padding: '9px 0',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	color: 'var(--l2-fg-2)',
	borderBottom: '1px solid rgba(237,234,224,0.055)'
};

const projectCardStyle: React.CSSProperties = {
	borderRadius: 2,
	border: '1px solid rgba(70,240,160,0.20)',
	background: 'rgba(70,240,160,0.045)',
	padding: 12,
	boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.05)'
};

const projectRowStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: '12px minmax(0,1fr) 18px',
	alignItems: 'center',
	gap: 8,
	minWidth: 0,
	border: '1px solid rgba(237,234,224,0.06)',
	background: 'rgba(237,234,224,0.025)',
	color: 'var(--l2-fg-2)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	textAlign: 'left',
	padding: '8px 9px',
	borderRadius: 2,
	cursor: 'pointer'
};

const emptyTinyStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	color: 'var(--l2-fg-3)'
};

const emptyAuditStyle: React.CSSProperties = {
	...emptyTinyStyle,
	padding: 18,
	textAlign: 'center'
};

const auditRowStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: '92px minmax(0,1fr)',
	gap: 10,
	padding: '8px 0',
	borderBottom: '1px solid rgba(237,234,224,0.055)'
};

// ── Tool-call card + agent-turn styles ──────────────────────────────────────

const agentTurnStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	gap: 8,
	alignItems: 'stretch',
	maxWidth: 'min(820px, 96%)',
	animation: 'atlas-window-in 240ms var(--l2-ease)'
};

const agentTurnHeaderStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8
};

const agentTextStyle: React.CSSProperties = {
	color: 'var(--l2-fg-1)',
	fontSize: 13.5,
	lineHeight: 1.58,
	overflowWrap: 'anywhere',
	whiteSpace: 'pre-wrap'
};

const toolCardStyle: React.CSSProperties = {
	border: '1px solid rgba(74,93,191,0.30)',
	borderRadius: 2,
	background: 'rgba(13,16,24,0.55)',
	overflow: 'hidden'
};

const toolCardHeaderStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	width: '100%',
	padding: '7px 10px',
	background: 'transparent',
	border: 'none',
	cursor: 'pointer',
	textAlign: 'left',
	color: 'var(--l2-fg-2)'
};

const toolNameStyle: React.CSSProperties = {
	flex: '0 0 auto',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.14em',
	color: 'var(--atlas-celestial)'
};

const toolSummaryStyle: React.CSSProperties = {
	flex: '1 1 auto',
	minWidth: 0,
	overflow: 'hidden',
	textOverflow: 'ellipsis',
	whiteSpace: 'nowrap',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	color: 'var(--l2-fg-2)'
};

const monoMicroStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.14em',
	color: 'var(--l2-fg-3)'
};

const toolCardBodyStyle: React.CSSProperties = {
	borderTop: '1px solid rgba(237,234,224,0.07)',
	padding: '9px 10px',
	display: 'flex',
	flexDirection: 'column',
	gap: 6
};

const toolFieldLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.18em',
	color: 'var(--l2-fg-3)'
};

const toolPreStyle: React.CSSProperties = {
	margin: 0,
	maxHeight: 280,
	overflow: 'auto',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	lineHeight: 1.5,
	color: 'var(--l2-fg-1)',
	background: 'rgba(5,6,10,0.5)',
	border: '1px solid rgba(237,234,224,0.06)',
	borderRadius: 2,
	padding: '8px 9px',
	whiteSpace: 'pre-wrap',
	overflowWrap: 'anywhere'
};

const diffWrapStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	lineHeight: 1.5,
	maxHeight: 320,
	overflow: 'auto',
	border: '1px solid rgba(237,234,224,0.06)',
	borderRadius: 2,
	background: 'rgba(5,6,10,0.5)'
};

const diffLineStyle: React.CSSProperties = {
	display: 'flex',
	gap: 8,
	padding: '1px 9px',
	whiteSpace: 'pre-wrap',
	overflowWrap: 'anywhere'
};

const diffSignStyle: React.CSSProperties = {
	flex: '0 0 auto',
	opacity: 0.7,
	userSelect: 'none'
};

const turnErrorStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	padding: '8px 10px',
	border: '1px solid rgba(255,77,125,0.32)',
	borderRadius: 2,
	background: 'rgba(255,77,125,0.07)',
	color: '#ffb3c6',
	fontSize: 12.5
};

const turnFooterStyle: React.CSSProperties = {
	display: 'flex',
	gap: 14,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.12em',
	color: 'var(--l2-fg-3)',
	paddingTop: 2
};

const pathInputWrapStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: 'minmax(0,1fr) 34px',
	gap: 6
};

const pathInputStyle: React.CSSProperties = {
	width: '100%',
	minWidth: 0,
	height: 34,
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(9,11,16,0.72)',
	color: 'var(--l2-fg-1)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	padding: '0 9px',
	outline: 'none'
};

const miniBrowseStyle: React.CSSProperties = {
	width: 34,
	height: 34,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid rgba(70,240,160,0.35)',
	background: 'rgba(70,240,160,0.08)',
	color: 'var(--atlas-emerald)',
	cursor: 'pointer'
};

const folderModeButtonStyle: React.CSSProperties = {
	width: '100%',
	marginTop: 12,
	height: 34,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	gap: 8,
	borderRadius: 2,
	border: '1px solid rgba(79,139,255,0.28)',
	background: 'rgba(79,139,255,0.07)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.13em',
	textTransform: 'uppercase',
	cursor: 'pointer'
};

const miniMenuButtonStyle: React.CSSProperties = {
	height: 42,
	display: 'inline-flex',
	alignItems: 'center',
	gap: 5,
	padding: '0 10px',
	border: 'none',
	borderLeft: '1px solid var(--l2-hairline)',
	background: 'rgba(237,234,224,0.025)',
	color: 'var(--l2-fg-2)',
	cursor: 'pointer'
};

const miniMenuStyle: React.CSSProperties = {
	position: 'absolute',
	top: 42,
	right: 0,
	zIndex: 80,
	minWidth: 150,
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(8,10,15,0.98)',
	boxShadow: '0 18px 50px rgba(0,0,0,0.5)',
	overflow: 'hidden'
};

const miniMenuItemStyle: React.CSSProperties = {
	width: '100%',
	height: 34,
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	border: 'none',
	borderBottom: '1px solid rgba(237,234,224,0.05)',
	background: 'transparent',
	color: 'var(--l2-fg-2)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.12em',
	textTransform: 'uppercase',
	padding: '0 10px',
	cursor: 'pointer'
};
