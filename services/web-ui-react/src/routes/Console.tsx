import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type * as React from 'react';
import { useSearchParams } from 'react-router-dom';
import {
	AlertTriangle,
	Bot,
	BoxSelect,
	Brain,
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
	Unlink,
	Waypoints,
	Wrench,
	X
} from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import CommandPalette from '../components/CommandPalette';
import { TopoScroll } from '../components/TopoScroll';
import { OrchestrationCallCard } from '../components/chat/OrchestrationCallCard';
import { ChatMarkdown } from '../components/ChatMarkdown';
import { StreamReveal } from '../components/chat/StreamReveal';
import { AgentConstellation, SubagentRail } from '../components/agent/SubagentActivity';
import { displayConsoleEvents, isOrchestrationTool } from '../lib/consoleEventGroups';
import { subagentsFromConsoleEvents } from '../lib/subagents';
import { SessionNavigator } from '../components/sessions/SessionNavigator';
import {
	agentRuntimeLabel,
	getRun,
	listProjects,
	registerProject,
	type AgentRuntime,
	type ConsoleChatEvent,
	type Project
} from '../lib/api';
import {
	finalGoalJudgementState,
	isRunTerminalEvent,
	surfaceConsoleEvent,
	surfaceEventsForTurn
} from '../lib/consoleEvents';
import { useAgentSurface } from '../context/AgentSurfaceContext';
import {
	type BindingMode,
	type ConsoleMessage,
	type ConsoleWindow,
	type LayoutMode,
	type WindowKind,
	useConsoleSession
} from '../context/ConsoleSessionContext';
import { selectFolder } from '../lib/host';
import { computeDwindle, type Rect } from '../lib/bspLayout';
import {
	addRecentFolder,
	createConsoleSession,
	ensureActiveConsoleSession,
	loadConsoleSession,
	loadConsoleSnapshot,
	saveConsoleSnapshot,
	type ConsoleSnapshot
} from '../lib/consolePersistence';
import {
	activeSessionId,
	sessionBinding,
	sessionTitleFromText,
	setActiveSessionId,
	upsertSessionCatalog
} from '../lib/sessionCatalog';
import { useVisualSettings } from '../lib/visualSettings';
import { distanceFromBottom, isNearBottom } from '../lib/scrollFollow';
import { turnReceiptSignature } from '../lib/turnReceipt';
import { subagentsFromSurfaceEvents } from '../lib/subagents';
import { GOAL_STATUS_MESSAGE, parseMissionSlashIntent } from '../lib/missionSlash';
import { projectConsoleEvents } from '../lib/logProjection';

type Load = { s: 'loading' } | { s: 'ready'; projects: Project[] } | { s: 'error' };
type DragState = { id: string; pointerId?: number; startX: number; startY: number; x: number; y: number } | null;
type ResizeState = { id: string; pointerId?: number; startX: number; startY: number; w: number; h: number } | null;

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

/** Last segment of a filesystem path — the binding truth an operator scans
 * for ("which repo is this chat in"), shown where a generic BOUND badge
 * would carry no information. */
function pathTail(path: string): string {
	const tail = path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? path;
	return tail.length > 24 ? `${tail.slice(0, 23)}…` : tail;
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
	const agentSurface = useAgentSurface();
	const {
		windows,
		setWindows,
		activeWindow,
		setActiveWindow,
		messagesByWindow,
		setMessagesByWindow,
		auditEvents,
		setAuditEvents,
		draftByWindow,
		setDraftByWindow,
		layout,
		setLayout,
		activeTurn,
		setActiveTurn,
		bindingMode,
		setBindingMode,
		folderPath,
		setFolderPath
	} = useConsoleSession();
	const [params, setParams] = useSearchParams();
	const projectId = params.get('project') ?? '';
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [folderErr, setFolderErr] = useState<string | null>(null);
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
	const busyWindow = activeTurn?.windowId ?? null;
	const [catalogSessionId, setCatalogSessionId] = useState(() =>
		activeSessionId('console') ??
		ensureActiveConsoleSession({
			windows,
			messagesByWindow,
			draftByWindow,
			layout,
			binding: { bindingMode, folderPath, projectId }
		})
	);

	// ── Cmd+K / Ctrl+K slash-command palette (TUI parity) ────────────────────
	const [paletteOpen, setPaletteOpen] = useState(false);
	useEffect(() => {
		function onKey(e: KeyboardEvent) {
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
				e.preventDefault();
				setPaletteOpen((open) => !open);
			}
		}
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, []);

	/** Palette runs land on the active chat window, else the first chat window. */
	function paletteTargetWindow(): string | null {
		const wins = windowsRef.current;
		const active = wins.find((w) => w.id === activeWindow && w.kind === 'chat');
		return (active ?? wins.find((w) => w.kind === 'chat'))?.id ?? null;
	}

	// BSP auto-tiling needs the live canvas size to compute window rects.
	const canvasRef = useRef<HTMLDivElement>(null);
	const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
	useEffect(() => {
		const el = canvasRef.current;
		if (!el || typeof ResizeObserver === 'undefined') return;
		const ro = new ResizeObserver((entries) => {
			const r = entries[0]?.contentRect;
			if (r) setCanvasSize({ w: r.width, h: r.height });
		});
		ro.observe(el);
		return () => ro.disconnect();
	}, []);

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

	// One-time (mount-only) binding reconciliation: an explicit `?project=` in
	// the URL always wins (matches a fresh "open in console" link). Otherwise,
	// if we landed on a bare /console and the persisted snapshot remembers a
	// project binding, restore its id into the URL — the Provider already
	// hydrated `bindingMode` from the same snapshot, so this just brings the
	// URL back in sync with it.
	useEffect(() => {
		if (projectId) {
			setBindingMode('project');
			return;
		}
		const restored = loadConsoleSnapshot()?.binding;
		if (restored?.bindingMode === 'project' && restored.projectId) {
			setParams({ project: restored.projectId }, { replace: true });
		}
		// Mount-only: re-checking on every projectId change would fight the
		// operator's own later folder/project switches.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const projects = useMemo(() => (load.s === 'ready' ? load.projects : []), [load]);
	const activeProject = useMemo(() => {
		if (load.s !== 'ready' || !projectId) return null;
		return load.projects.find((p) => p.id === projectId) ?? null;
	}, [load, projectId]);
	const boundCwd = bindingMode === 'project' ? activeProject?.root_path ?? null : folderPath.trim() || null;
	const activeConsoleWindow = windows.find((win) => win.id === activeWindow) ?? windows[0];
	const activeChatAgent = activeConsoleWindow?.kind === 'chat' ? activeConsoleWindow.agent ?? 'native' : 'native';
	const visibleWindows = layout === 'tabs' ? windows.filter((win) => win.id === activeWindow) : windows;
	const bspRects: Map<string, Rect> | null =
		layout === 'bsp' && canvasSize.w > 0 && canvasSize.h > 0
			? computeDwindle(
					visibleWindows.map((w) => w.id),
					{ x: 0, y: 0, w: canvasSize.w, h: canvasSize.h },
					8,
					activeWindow
				)
			: null;
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

	// The provider outlives route navigation. When the shared drawer routes
	// from Chat to a specific Console session, reload the newly-active console
	// snapshot instead of reusing whichever workbench state the provider held.
	const initialCatalogRestore = useRef(false);
	useEffect(() => {
		if (initialCatalogRestore.current) return;
		initialCatalogRestore.current = true;
		// A provider-held active turn is newer than any debounced localStorage
		// snapshot. Preserve it across route remounts so buffered completion
		// events can reconcile the live message instead of restoring stale data.
		if (activeTurn) return;
		const snapshot = loadConsoleSession(catalogSessionId);
		if (!snapshot) return;
		setWindows(snapshot.windows);
		setActiveWindow(snapshot.windows[0]?.id ?? '');
		setMessagesByWindow(snapshot.messagesByWindow);
		setDraftByWindow(snapshot.draftByWindow);
		setLayout(snapshot.layout);
		setBindingMode(snapshot.binding.bindingMode);
		setFolderPath(snapshot.binding.folderPath);
		setParams(snapshot.binding.projectId ? { project: snapshot.binding.projectId } : {}, { replace: true });
		setAuditEvents([]);
		setActiveTurn(null);
		// Mount-only: catalogSessionId is fixed from the active key for this
		// route instance; in-page switches call applyConsoleSnapshot directly.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

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
	}, [activeProject, boundCwd, setMessagesByWindow, windows]);

	// MRU of bound folder paths — tracks any successful binding (project roots
	// included, since they're still a filesystem path worth resurfacing), not
	// just explicit "Change folder…" picks.
	useEffect(() => {
		if (!boundCwd) return;
		addRecentFolder(boundCwd);
	}, [boundCwd]);

	// The gateway workspace model is global|project (registered roots with
	// containment checks) — a raw folder binding must resolve to a registered
	// project id before a run can actually execute inside it. Cached per
	// folderPath; resolved lazily at dispatch so a persisted binding survives
	// reloads without an eager registration on every hydrate.
	const [folderProjectId, setFolderProjectId] = useState<string | null>(null);
	useEffect(() => {
		setFolderProjectId(null);
	}, [folderPath]);

	const ensureFolderProject = useCallback(
		async (path: string): Promise<string | null> => {
			const norm = (p: string) => p.replace(/[\\/]+$/, '').replace(/\//g, '\\').toLowerCase();
			const existing = projects.find((p) => norm(p.root_path) === norm(path));
			if (existing) return existing.id;
			try {
				const { project } = await registerProject(pathTail(path), path);
				setLoad((prev) =>
					prev.s === 'ready' ? { s: 'ready', projects: [...prev.projects, project] } : prev
				);
				return project.id;
			} catch {
				return null;
			}
		},
		[projects]
	);

	// A surface session is bound to the workspace it was opened with; when the
	// operator rebinds, the held session would keep scoping runs to the OLD
	// workspace. Release it (idle turns only — dispatch is blocked mid-turn
	// anyway) so the next prompt re-surfaces against the new binding.
	const bindingKey = `${projectId ?? ''}|${boundCwd ?? ''}`;
	useEffect(() => {
		if (activeTurn) return;
		void agentSurface.releaseSession();
		// Keyed on the binding identity only — releasing on every render or
		// turn change would churn sessions for no reason.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [bindingKey]);

	// Single debounced writer for the whole console snapshot. `auditEvents` and
	// `activeTurn` are intentionally excluded — see consolePersistence.ts.
	useEffect(() => {
		const snapshot: ConsoleSnapshot = {
			windows,
			messagesByWindow,
			draftByWindow,
			layout,
			binding: { bindingMode, folderPath, projectId }
		};
		saveConsoleSnapshot(snapshot, catalogSessionId);
		const firstOperator = Object.values(messagesByWindow)
			.flat()
			.find((message) => message.role === 'operator');
		upsertSessionCatalog({
			id: catalogSessionId,
			surface: 'console',
			title: sessionTitleFromText(firstOperator?.body, 'New console session'),
			agent: activeChatAgent,
			binding: sessionBinding(
				bindingMode,
				folderPath,
				projectId,
				activeProject?.name,
				activeProject?.root_path
			)
		});
	}, [
		catalogSessionId,
		windows,
		messagesByWindow,
		draftByWindow,
		layout,
		bindingMode,
		folderPath,
		projectId,
		activeChatAgent,
		activeProject
	]);

	useEffect(() => {
		const pendingSurfaceEvents = surfaceEventsForTurn(agentSurface.events, activeTurn);
		if (!activeTurn || pendingSurfaceEvents.length === 0) return;

		const projectedEvents = pendingSurfaceEvents.map((surfaceEvent): ConsoleChatEvent => {
			try {
				return surfaceConsoleEvent(surfaceEvent);
			} catch (cause) {
				return {
					type: 'failure',
					error: cause instanceof Error ? cause.message : String(cause)
				};
			}
		});
		const finalGoalState = finalGoalJudgementState(pendingSurfaceEvents);
		const terminal = activeTurn.goalMode
			? finalGoalState !== null
			: projectedEvents.some(isRunTerminalEvent);
		const afterSeq = Math.max(...pendingSurfaceEvents.map((event) => event.seq));
		const { windowId, turnId, runId } = activeTurn;

		setMessagesByWindow((prev) => {
			let messages = prev[windowId] ?? [];
			for (const event of projectedEvents) {
				messages = messages.map((message) => {
					if (message.id !== turnId) return message;
					// 'text_delta' (streamed chunk) and 'text' (the turn's final
					// authoritative reconcile) can both arrive for the same run —
					// appending both would duplicate the response. Append deltas
					// while a run streams; when the reconcile lands, replace just
					// that run's provisional text (tracked via streamDeltaStart)
					// with the authoritative value instead of appending after it.
					let body = message.body;
					let streamDeltaStart = message.streamDeltaStart;
					if (event.type === 'text_delta') {
						if (streamDeltaStart === undefined) streamDeltaStart = body.length;
						body = `${body}${event.text ?? ''}`;
					} else if (event.type === 'text') {
						body =
							streamDeltaStart !== undefined
								? `${body.slice(0, streamDeltaStart)}${event.text ?? ''}`
								: `${body}${event.text ?? ''}`;
						streamDeltaStart = undefined;
					} else if (event.type === 'tool_call') {
						streamDeltaStart = undefined;
					}
					return {
						...message,
						events: [...(message.events ?? []), event],
						body,
						streamDeltaStart,
						status:
							event.type === 'failure' && !event.tool_call_id
								? 'failed'
								: event.type === 'result'
									? event.is_error
										? 'failed'
										: 'succeeded'
									: message.status
					};
				});
			}
			if (activeTurn.goalMode) {
				messages = messages.map((message) =>
					message.id === turnId
						? {
								...message,
								status: finalGoalState
									? finalGoalState === 'failed' ? 'failed' : 'succeeded'
									: 'pending'
							}
						: message
				);
			}
			return { ...prev, [windowId]: messages };
		});
		setAuditEvents((prior) => [...projectedEvents].reverse().concat(prior).slice(0, 80));
		setActiveTurn((current) => {
			if (!current || current.turnId !== turnId || current.runId !== runId) return current;
			return terminal ? null : { ...current, afterSeq };
		});
	}, [activeTurn, agentSurface.events, setActiveTurn, setAuditEvents, setMessagesByWindow]);

	// Stuck-turn watchdog: if the surface event stream never delivers the
	// terminal frame (reconnect gap, dropped poll), the run record is still the
	// truth. Poll it while a turn is pending so the composer can never stay
	// locked on a finished run.
	const watchedRunId = activeTurn?.runId ?? null;
	const watchedTurnId = activeTurn?.turnId ?? null;
	const watchedWindowId = activeTurn?.windowId ?? null;
	const watchedGoalMode = activeTurn?.goalMode ?? false;
	// Grace pass: the run record goes terminal BEFORE the tail surface events
	// (last deltas + the final text reconcile) have been polled and applied.
	// Finalizing on the first terminal observation froze answers mid-chunk
	// (observed live: a response cut at "Bril" while the audit ledger held the
	// full text). First terminal sighting only marks the run and forces an
	// event refresh; the turn finalizes on the NEXT tick if the terminal
	// surface event still hasn't landed by then.
	const terminalSeenRef = useRef<string | null>(null);
	const refreshSurfaceEvents = agentSurface.refresh;
	useEffect(() => {
		if (!watchedRunId || !watchedTurnId || !watchedWindowId) return;
		terminalSeenRef.current = null;
		const timer = window.setInterval(async () => {
			try {
				const { run } = await getRun(watchedRunId);
				if (!['succeeded', 'failed', 'cancelled'].includes(run.status)) return;
				if (watchedGoalMode) {
					void refreshSurfaceEvents().catch(() => undefined);
					return;
				}
				if (terminalSeenRef.current !== watchedRunId) {
					terminalSeenRef.current = watchedRunId;
					void refreshSurfaceEvents().catch(() => undefined);
					return;
				}
				const failed = run.status !== 'succeeded';
				setMessagesByWindow((prev) => ({
					...prev,
					[watchedWindowId]: (prev[watchedWindowId] ?? []).map((message) =>
						message.id === watchedTurnId && message.status === 'pending'
							? {
									...message,
									status: failed ? 'failed' : 'succeeded',
									body: message.body || run.summary || (failed ? 'Run failed.' : 'Run completed.')
								}
						: message
					)
				}));
				setActiveTurn((current) =>
					current?.runId === watchedRunId ? null : current
				);
			} catch {
				// Gateway blip — keep waiting; the next tick retries.
			}
		}, 8000);
		return () => window.clearInterval(timer);
	}, [
		watchedRunId,
		watchedTurnId,
		watchedWindowId,
		watchedGoalMode,
		refreshSurfaceEvents,
		setActiveTurn,
		setMessagesByWindow
	]);

	// Selecting a project/folder from the session switcher (or the pre-existing
	// project list) starts a fresh session: chat transcripts and drafts reset
	// to a plain boot receipt for the new binding, window/pane layout is left
	// untouched. Clearing to `[]` (rather than hand-building the boot message
	// here) lets the boot-reset effect above regenerate it once `activeProject`
	// / `boundCwd` actually settle to the new values — same content, no fight.
	function resetChatSessions() {
		setMessagesByWindow((prev) => {
			const next = { ...prev };
			for (const win of windows) {
				if (win.kind === 'chat') next[win.id] = [];
			}
			return next;
		});
		setDraftByWindow((prev) => {
			const next = { ...prev };
			for (const win of windows) {
				if (win.kind === 'chat') next[win.id] = '';
			}
			return next;
		});
	}

	function pickProject(project: Project) {
		setBindingMode('project');
		setParams({ project: project.id });
		resetChatSessions();
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

	function unbindWorkspace() {
		setBindingMode('folder');
		setFolderPath('');
		setFolderProjectId(null);
		if (projectId) setParams({});
		resetChatSessions();
	}

	function applyConsoleSnapshot(id: string, snapshot: ConsoleSnapshot) {
		setCatalogSessionId(id);
		setActiveSessionId('console', id);
		setWindows(snapshot.windows);
		setActiveWindow(snapshot.windows[0]?.id ?? '');
		setMessagesByWindow(snapshot.messagesByWindow);
		setDraftByWindow(snapshot.draftByWindow);
		setLayout(snapshot.layout);
		setBindingMode(snapshot.binding.bindingMode);
		setFolderPath(snapshot.binding.folderPath);
		setParams(snapshot.binding.projectId ? { project: snapshot.binding.projectId } : {});
		setAuditEvents([]);
		setActiveTurn(null);
		void agentSurface.releaseSession();
	}

	function selectCatalogSession(id: string) {
		if (activeTurn) return;
		const snapshot = loadConsoleSession(id);
		if (snapshot) applyConsoleSnapshot(id, snapshot);
	}

	function newCatalogSession(unbound = false) {
		if (activeTurn) return;
		const nextMessages: Record<string, ConsoleMessage[]> = {};
		const nextDrafts: Record<string, string> = {};
		for (const win of windows) {
			if (win.kind === 'chat') {
				nextMessages[win.id] = [];
				nextDrafts[win.id] = '';
			}
		}
		const snapshot: ConsoleSnapshot = {
			windows,
			messagesByWindow: nextMessages,
			draftByWindow: nextDrafts,
			layout,
			binding: {
				bindingMode: unbound ? 'folder' : bindingMode,
				folderPath: unbound ? '' : folderPath,
				projectId: unbound ? '' : projectId
			}
		};
		const id = createConsoleSession(snapshot);
		applyConsoleSnapshot(id, snapshot);
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
					: windowAgent === 'codex'
						? agentCount === 1
							? 'codex'
							: `codex.${agentCount}`
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
		if (windows.length <= 1 || activeTurn?.windowId === id) return;
		setWindows((prev) => prev.filter((w) => w.id !== id));
		if (activeWindow === id) {
			const fallback = windows.find((w) => w.id !== id)?.id ?? '';
			setActiveWindow(fallback);
		}
	}

	const resizeWindow = useCallback((id: string, w: number, h: number) => {
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
	}, [setWindows]);

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
		if (!draft || activeTurn) return;
		setDraftByWindow((prev) => ({ ...prev, [windowId]: '' }));
		await dispatchPrompt(windowId, draft, draft);
	}

	/** Submit a prompt on a chat window. `display` is what the transcript shows
	 * as the operator message (e.g. `/review HEAD~1` for palette runs), `prompt`
	 * is the text actually sent to the agent (the expanded command template). */
	async function dispatchPrompt(windowId: string, display: string, prompt: string) {
		if (activeTurn) return;
		const goalMode = parseMissionSlashIntent(display)?.kind === 'goal-launch';
		const win = windows.find((item) => item.id === windowId);
		const windowAgent = win?.kind === 'chat' ? win.agent ?? 'native' : 'native';
		const operator: ConsoleMessage = {
			id: `${Date.now()}-operator`,
			role: 'operator',
			label: 'OPERATOR',
			body: display,
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
		setMessagesByWindow((prev) => ({
			...prev,
			[windowId]: [...(prev[windowId] ?? []), operator, liveTurn]
		}));
		const afterSeq = agentSurface.events.reduce(
			(highest, event) => Math.max(highest, event.seq),
			-1
		);
		setActiveTurn({ windowId, turnId, runId: null, afterSeq, goalMode });

		try {
			let workspace: { kind: 'global' } | { kind: 'project'; projectId: string } = {
				kind: 'global'
			};
			if (bindingMode === 'project' && projectId) {
				workspace = { kind: 'project', projectId };
			} else if (bindingMode === 'folder' && boundCwd) {
				// Folder bindings execute as registered projects — resolve (or
				// register) the project for this folder so the run's cwd is real.
				const pid = folderProjectId ?? (await ensureFolderProject(boundCwd));
				if (pid) {
					setFolderProjectId(pid);
					workspace = { kind: 'project', projectId: pid };
				}
			}
			const runId = display === prompt
				? await agentSurface.submitPrompt(prompt, windowAgent, workspace)
				: await agentSurface.submitPrompt(prompt, windowAgent, workspace, display);
			if (runId === null) {
				setMessagesByWindow((prev) => ({
					...prev,
					[windowId]: (prev[windowId] ?? []).map((m) =>
						m.id === turnId ? { ...m, status: 'succeeded', body: GOAL_STATUS_MESSAGE } : m
					)
				}));
				setActiveTurn((current) => (current?.turnId === turnId ? null : current));
				return;
			}
			setActiveTurn((current) =>
				current?.turnId === turnId ? { ...current, runId } : current
			);
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
			setActiveTurn((current) => (current?.turnId === turnId ? null : current));
		}
	}

	// Move the dragged window to follow the cursor, and if its center crosses
	// another window, swap that window into the dragged window's reserved slot —
	// live, while dragging. The dragged window keeps tracking the cursor 1:1.
	const dragMoveAndSwap = useCallback((clientX: number, clientY: number) => {
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
	}, [setWindows]);

	// On release, if any swap happened, snap the dragged window into its reserved
	// slot for a clean reorder. If nothing was swapped, it stays where it was dropped.
	const finishFreeDrag = useCallback(() => {
		const d = dragRef.current;
		if (d && d.didSwap) {
			const { id, homeX, homeY } = d;
			setWindows((prev) => prev.map((w) => (w.id === id ? { ...w, x: homeX, y: homeY } : w)));
		}
		dragRef.current = null;
	}, [setWindows]);

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
	}, [drag, dragMoveAndSwap, finishFreeDrag, resize, resizeWindow]);

	function cycleLayout() {
		setLayout((current) =>
			current === 'tile' ? 'bsp' : current === 'bsp' ? 'free' : current === 'free' ? 'tabs' : 'tile'
		);
	}

	return (
		<Page
			eyebrow="MISSION · CONSOLE"
			title="Console"
			max={null}
			actions={
				<>
					<SessionNavigator
						activeSessionId={catalogSessionId}
						surface="console"
						bound={!!(boundCwd || projectId)}
						disabled={!!busyWindow}
						onNewSession={newCatalogSession}
						onSelectSession={selectCatalogSession}
						onChooseFolder={() => void chooseFolder()}
						onUnbind={unbindWorkspace}
					/>
					<SessionLaunchers onSpawn={(sessionAgent) => addWindow('chat', sessionAgent)} disabled={!!busyWindow} />
					<StatePill tone={projectState.tone}>{projectState.label}</StatePill>
					<IconAction title="Change bound folder" onClick={() => void chooseFolder()}>
						<FolderSearch size={15} strokeWidth={1.7} />
					</IconAction>
					{(boundCwd || projectId) && (
						<IconAction title="Unbind workspace" onClick={unbindWorkspace}>
							<Unlink size={15} strokeWidth={1.7} />
						</IconAction>
					)}
					<IconAction title="Spawn native chat" onClick={() => addWindow('chat', 'native')}>
						<CopyPlus size={15} strokeWidth={1.7} />
					</IconAction>
					<IconAction
						title={
							layout === 'tile'
								? 'BSP auto-tile layout'
								: layout === 'bsp'
									? 'Free window layout'
									: layout === 'free'
										? 'Exclusive tab layout'
										: 'Tile windows'
						}
						onClick={cycleLayout}
					>
						{layout === 'tile' ? (
							<LayoutGrid size={15} strokeWidth={1.7} />
						) : layout === 'bsp' ? (
							<Columns3 size={15} strokeWidth={1.7} />
						) : layout === 'free' ? (
							<BoxSelect size={15} strokeWidth={1.7} />
						) : (
							<MousePointer2 size={15} strokeWidth={1.7} />
						)}
					</IconAction>
				</>
			}
		>
			<GlassPanel
				data-topo={activeChatAgent !== 'native' ? 'ai' : 'atlas'}
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
					busyWindowId={activeTurn?.windowId ?? null}
					onActivate={setActiveWindow}
					onAddWindow={addWindow}
					onClose={closeWindow}
				/>
				<div
					ref={canvasRef}
					className={
						layout === 'tile'
							? 'atlas-workbench-tile'
							: layout === 'free'
								? 'atlas-workbench-free'
								: layout === 'bsp'
									? 'atlas-workbench-bsp'
									: 'atlas-workbench-tabs'
					}
				>
					{visibleWindows.map((win) => (
						<WorkbenchWindow
							key={win.id}
							win={win}
							layout={layout}
							rect={bspRects?.get(win.id)}
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
									busy={!!activeTurn}
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
			<CommandPalette
				open={paletteOpen}
				onClose={() => setPaletteOpen(false)}
				busy={!!activeTurn}
				onRun={(display, prompt) => {
					const target = paletteTargetWindow();
					if (target) void dispatchPrompt(target, display, prompt);
				}}
			/>
		</Page>
	);
}

function WorkbenchBar({
	layout,
	windows,
	activeWindow,
	busyWindowId,
	onActivate,
	onAddWindow,
	onClose
}: {
	layout: LayoutMode;
	windows: ConsoleWindow[];
	activeWindow: string;
	busyWindowId: string | null;
	onActivate: (id: string) => void;
	onAddWindow: (kind: WindowKind, agent?: AgentRuntime) => void;
	onClose: (id: string) => void;
}) {
	return (
		<div style={barStyle}>
			{windows.map((win) => {
				const Icon = KIND_ICON[win.kind];
				const active = win.id === activeWindow;
				const closable = windows.length > 1 && busyWindowId !== win.id;
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
						{closable && (
							/* span, not button — tabs are already buttons and nesting is invalid HTML */
							<span
								role="button"
								tabIndex={0}
								aria-label={`Close ${win.title}`}
								title={`Close ${win.title}`}
								className="atlas-tab-close"
								onClick={(e) => {
									e.stopPropagation();
									onClose(win.id);
								}}
								onKeyDown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										e.preventDefault();
										e.stopPropagation();
										onClose(win.id);
									}
								}}
							>
								<X size={11} strokeWidth={1.8} />
							</span>
						)}
					</button>
				);
			})}
			<div style={{ flex: 1 }} />
			<MiniMenu onPick={onAddWindow} />
			<WorkbenchBadge
				icon={layout === 'tile' ? <Columns3 size={13} /> : layout === 'bsp' ? <LayoutGrid size={13} /> : layout === 'free' ? <BoxSelect size={13} /> : <LayoutGrid size={13} />}
				label={layout === 'tile' ? 'TILE MODE' : layout === 'bsp' ? 'BSP AUTO-TILE' : layout === 'free' ? 'FREE MODE' : 'EXCLUSIVE TABS'}
			/>
		</div>
	);
}

function WorkbenchWindow({
	win,
	layout,
	rect,
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
	rect?: Rect;
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
	const agentSurface = useAgentSurface();
	const windowActors = useMemo(
		() => win.kind === 'chat' ? subagentsFromSurfaceEvents(agentSurface.events) : [],
		[agentSurface.events, win.kind]
	);
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
	// BSP auto-tile: absolutely position from the computed rect (no manual drag).
	const bspStyle =
		layout === 'bsp' && rect
			? {
					position: 'absolute' as const,
					left: rect.x,
					top: rect.y,
					width: rect.w,
					height: rect.h,
					zIndex: active ? 30 : 10,
					transition:
						'left 200ms var(--l2-ease), top 200ms var(--l2-ease), width 200ms var(--l2-ease), height 200ms var(--l2-ease), box-shadow 180ms var(--l2-ease), border-color 180ms var(--l2-ease)'
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
				...bspStyle,
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
				<AgentConstellation actors={windowActors} compact />
				<span style={busy ? liveBadgeStyle : tinyBadgeStyle}>{busy ? 'LIVE' : win.kind.toUpperCase()}</span>
				<button
					type="button"
					disabled={busy}
					// Stop pointer/mouse-down from reaching the header drag handler:
					// in free mode it calls setPointerCapture, which redirects the
					// pointerup and suppresses this button's click (window wouldn't close).
					onPointerDown={(e) => e.stopPropagation()}
					onMouseDown={(e) => e.stopPropagation()}
					onClick={(e) => { e.stopPropagation(); onClose(); }}
					style={{
						...miniIconButtonStyle,
						cursor: busy ? 'not-allowed' : miniIconButtonStyle.cursor,
						opacity: busy ? 0.45 : 1
					}}
					title={busy ? 'Cannot close the window owning the active run' : 'Close window'}
				>
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
	// Stick-to-bottom follow: track whether the operator is pinned at the
	// bottom of the transcript; only then does new streamed content auto-follow.
	// Scrolling up detaches (reading history must never be yanked away); the
	// jump pill re-pins.
	const visualSettings = useVisualSettings();
	const viewportRef = useRef<HTMLDivElement | null>(null);
	const pinnedRef = useRef(true);
	const [unpinned, setUnpinned] = useState(false);
	const onViewportScroll = useCallback((el: HTMLDivElement) => {
		const pinned =
			visualSettings.autoFollow &&
			isNearBottom(el);
		pinnedRef.current = pinned;
		setUnpinned(!pinned);
	}, [visualSettings.autoFollow]);
	useEffect(() => {
		const el = viewportRef.current;
		if (el && visualSettings.autoFollow && pinnedRef.current) el.scrollTop = el.scrollHeight;
	}, [messages, visualSettings.autoFollow]);
	// While a turn streams, content height also grows between message-state
	// updates (paced reveal) — keep following via rAF as long as we're pinned.
	useEffect(() => {
		if (!busy || !visualSettings.autoFollow) return;
		let raf = 0;
		const follow = () => {
			const el = viewportRef.current;
			if (el && pinnedRef.current && distanceFromBottom(el) > 1) {
				el.scrollTop = el.scrollHeight;
			}
			raf = requestAnimationFrame(follow);
		};
		raf = requestAnimationFrame(follow);
		return () => cancelAnimationFrame(raf);
	}, [busy, visualSettings.autoFollow]);
	const jumpToLatest = useCallback(() => {
		const el = viewportRef.current;
		if (!el) return;
		pinnedRef.current = true;
		setUnpinned(false);
		el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
	}, []);
	// Run receipts (run started · runtime · privacy notice) repeat identically
	// on every turn of a session — show a receipt only when it differs from the
	// previous agent turn's (first turn, or the runtime/privacy line changed).
	let lastReceipt: string | null = null;
	return (
		<div style={chatPaneStyle} data-testid={`chat-pane-${windowId}`}>
			<div style={chatTopStyle}>
				<div style={{ minWidth: 0 }}>
					<div style={monoLabelStyle}>{agentRuntimeLabel(agent)} · {windowId.toUpperCase()}</div>
					<div style={titleTextStyle}>{projectName}</div>
				</div>
				<WorkbenchBadge
					icon={<GitBranch size={13} />}
					label={boundCwd ? pathTail(boundCwd) : 'UNBOUND'}
					title={boundCwd ?? undefined}
				/>
			</div>
			<div style={{ position: 'relative', minHeight: 0, display: 'grid' }}>
				<TopoScroll
					tone={agent !== 'native' ? 'atlas' : 'info'}
					style={{ minHeight: 0 }}
					viewportStyle={messageListStyle}
					viewportRef={viewportRef}
					onViewportScroll={onViewportScroll}
				>
					{messages.map((message) => {
						if (message.role === 'agent' && (message.events?.length || message.status === 'pending')) {
							const receipt = turnReceiptSignature(message);
							const hideStatus = receipt !== null && receipt === lastReceipt;
							if (receipt !== null) lastReceipt = receipt;
							return <AgentTurn key={message.id} message={message} hideStatus={hideStatus} />;
						}
						return <MessageBubble key={message.id} message={message} />;
					})}
				</TopoScroll>
				{unpinned && (
					<button type="button" onClick={jumpToLatest} className="atlas-jump-latest" title="Follow the live response">
						<ChevronDown size={13} strokeWidth={2} />
						LATEST
					</button>
				)}
			</div>
			<div style={composerWrapStyle}>
				<textarea
					className="atlas-console-composer"
					value={draft}
					disabled={busy}
					onChange={(e) => onDraft(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === 'Enter' && !e.shiftKey) {
							e.preventDefault();
							onSend();
						}
					}}
					placeholder={
						busy
							? 'Turn in progress — streaming'
							: agent === 'claude_code'
								? 'Ask Claude Code in this folder'
								: agent === 'codex'
									? 'Ask Codex in this folder'
									: 'Message ATLAS'
					}
					rows={3}
					style={composerStyle}
				/>
				<button
					type="button"
					className="atlas-console-send"
					onClick={onSend}
					disabled={!draft.trim() || busy}
					style={sendButtonStyle}
					title="Send"
				>
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
				<SegmentButton active={layout === 'bsp'} onClick={() => onLayout('bsp')}>BSP</SegmentButton>
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
	const projected = useMemo(() => projectConsoleEvents(events), [events]);
	return (
		<TopoScroll tone="good" style={{ height: '100%' }} viewportStyle={auditBodyStyle}>
			{events.length === 0 ? (
				<div style={emptyAuditStyle}>No console events recorded.</div>
			) : (
				projected.map((item) =>
					item.count > 1 ? (
						<details key={item.id} style={{ borderBottom: '1px solid var(--l2-hairline)' }}>
							<summary style={{ ...auditRowStyle, cursor: 'pointer', listStyle: 'none' }}>
								<span style={monoLabelStyle}>text_delta ×{item.count}</span>
								<span style={{ ...pathTextStyle, color: 'var(--l2-fg-2)' }}>
									{item.charCount.toLocaleString()} chars · expand burst
								</span>
							</summary>
							<pre style={{ margin: 0, padding: '8px 12px 12px', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflowY: 'auto', background: 'rgba(4,7,12,0.58)' }}>
								{item.text}
							</pre>
						</details>
					) : (
						<div key={item.id} style={auditRowStyle}>
							<span style={monoLabelStyle}>{item.event.type}</span>
							<span style={{ ...pathTextStyle, color: 'var(--l2-fg-2)' }}>
								{item.event.text ?? item.event.tool_name ?? item.event.error ?? item.event.subtype ?? 'event'}
							</span>
						</div>
					)
				)
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

/** Tool output is markdown-rendered only when it reads as prose: not JSON,
 * and carrying at least one visible markdown structure (heading, fence, list,
 * emphasis, table). Raw command output / file dumps stay in the mono <pre>. */
function looksLikeProse(text: string): boolean {
	const trimmed = text.trim();
	if (!trimmed) return false;
	if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
		try {
			JSON.parse(trimmed);
			return false;
		} catch {
			// not JSON — fall through to the markdown-signal check
		}
	}
	return /(^|\n)#{1,6} |(^|\n)```|(^|\n)[-*] |(^|\n)\d+\. |\*\*[^*\n]+\*\*|(^|\n)\|.+\|/.test(trimmed);
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

export function ToolCallCard({ event, result }: { event: ConsoleChatEvent; result?: ConsoleChatEvent }) {
	const [open, setOpen] = useState(false);
	const Icon = toolIcon(event.tool_name);
	const name = (event.tool_name ?? 'tool').toUpperCase();
	const summary = summarizeToolInput(event.tool_name, event.input);
	const failed = result?.type === 'failure' || result?.is_error === true;
	const done = !!result && !failed;
	const isEdit = ['edit', 'multiedit', 'write'].includes((event.tool_name ?? '').toLowerCase());
	const editInput = asRecord(event.input);
	const oldStr = typeof editInput.old_string === 'string' ? editInput.old_string : '';
	const newStr =
		typeof editInput.new_string === 'string'
			? editInput.new_string
			: typeof editInput.content === 'string'
				? editInput.content
				: '';
	const resultText = result ? clip(result.error ?? resultToText(result.content)) : '';
	const Chevron = open ? ChevronDown : ChevronRight;
	return (
		<div style={toolCardStyle} data-topo={failed ? 'bad' : 'ai'}>
			<button type="button" style={toolCardHeaderStyle} onClick={() => setOpen((v) => !v)}>
				<Chevron size={13} strokeWidth={1.8} style={{ color: 'var(--l2-fg-3)', flex: '0 0 auto' }} />
				<Icon size={14} strokeWidth={1.7} style={{ color: 'var(--atlas-celestial)', flex: '0 0 auto' }} />
				<span style={toolNameStyle}>{name}</span>
				<span style={toolSummaryStyle}>{summary}</span>
				<span style={{ flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
					<Circle
						size={7}
						fill={failed ? 'rgba(255,77,125,0.95)' : done ? 'rgba(70,240,160,0.95)' : 'rgba(255,214,0,0.95)'}
						stroke="none"
					/>
					<span style={monoMicroStyle}>{failed ? 'FAILED' : done ? 'DONE' : 'RUNNING'}</span>
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
							{!isEdit && looksLikeProse(resultText) ? (
								<div style={toolOutputProseStyle}>
									<ChatMarkdown text={resultText} style={{ fontSize: 12 }} />
								</div>
							) : (
								<pre style={toolPreStyle}>{resultText}</pre>
							)}
						</>
					)}
				</div>
			)}
		</div>
	);
}

/** Collapsed-by-default reasoning ("thinking") block. Deliberately dimmer and
 * quieter than the final answer — same chevron/expand pattern as ToolCallCard. */
export function ReasoningBlock({ text }: { text: string }) {
	const [open, setOpen] = useState(false);
	const Chevron = open ? ChevronDown : ChevronRight;
	return (
		<div style={reasoningBlockStyle} data-topo="muted">
			<button type="button" style={toolCardHeaderStyle} onClick={() => setOpen((v) => !v)}>
				<Chevron size={13} strokeWidth={1.8} style={{ color: 'var(--l2-fg-3)', flex: '0 0 auto' }} />
				<Brain size={13} strokeWidth={1.7} style={{ color: 'var(--l2-fg-3)', flex: '0 0 auto' }} />
				<span style={reasoningLabelStyle}>THINKING</span>
			</button>
			{open && (
				<div style={reasoningBodyStyle}>
					<ChatMarkdown text={text} style={{ color: 'var(--l2-fg-2)', fontSize: 12.5 }} />
				</div>
			)}
		</div>
	);
}

function AgentTurn({ message, hideStatus = false }: { message: ConsoleMessage; hideStatus?: boolean }) {
	const events = useMemo(() => message.events ?? [], [message.events]);
	// 'text_delta' (streamed chunk) and 'text' (the run's final authoritative
	// reconcile) both need to land in ONE rendered block per streaming run,
	// not one div each — otherwise every delta plus the final reconcile shows
	// up as its own stacked line, which reads as the response being repeated.
	// Collapse: deltas extend the currently-open run in place; the reconcile
	// replaces that open run's (provisional) text instead of appending a new
	// block. `_open` marks a run that's still streaming so an unrelated later
	// 'text' event (a fresh, non-streamed round) doesn't overwrite it.
	const displayEvents = useMemo(() => displayConsoleEvents(events), [events]);
	const actors = useMemo(() => subagentsFromConsoleEvents(events), [events]);
	const resultsByCall = useMemo(() => {
		const map: Record<string, ConsoleChatEvent> = {};
		for (const e of events) {
			if ((e.type === 'tool_result' || e.type === 'failure') && e.tool_call_id) map[e.tool_call_id] = e;
		}
		return map;
	}, [events]);
	const summary = events.find((e) => e.type === 'result');
	return (
		<div
			style={agentTurnStyle}
			className={message.status === 'pending' ? 'atlas-inference-wake' : undefined}
			data-topo={message.status === 'failed' ? 'bad' : 'good'}
		>
			<div style={agentTurnHeaderStyle}>
				<Bot size={13} strokeWidth={1.7} style={{ color: 'rgba(70,240,160,0.95)' }} />
				<span style={monoLabelStyle}>{message.label}</span>
				<span style={{ ...pathTextStyle, fontSize: 10 }}>{message.time}</span>
				{message.status === 'pending' && <span style={liveBadgeStyle}>LIVE</span>}
			</div>
			{events.length === 0 && message.status === 'pending' && (
				<div style={{ ...agentTextStyle, opacity: 0.6 }}>Working…</div>
			)}
			<SubagentRail events={events} />
			{displayEvents.map((event) => {
				if (event.type === 'task') return null;
				if (event.type === 'text') {
					// Chat and Console share the same live-Markdown reveal and
					// chunk scan protocol; settings apply to both surfaces.
					if (event._open && message.status === 'pending') {
						return <StreamReveal key={event._key} text={event.text ?? ''} />;
					}
					return event.text ? <ChatMarkdown key={event._key} text={event.text} /> : null;
				}
				if (event.type === 'reasoning') {
					return event.text ? <ReasoningBlock key={event._key} text={event.text} /> : null;
				}
				if (event.type === 'tool_call') {
					if (isOrchestrationTool(event.tool_name)) {
						return (
							<OrchestrationCallCard
								key={event._key}
								event={event}
								result={event.tool_call_id ? resultsByCall[event.tool_call_id] : undefined}
								actors={actors}
							/>
						);
					}
					return (
						<ToolCallCard
							key={event._key}
							event={event}
							result={event.tool_call_id ? resultsByCall[event.tool_call_id] : undefined}
						/>
					);
				}
				if (event.type === 'failure') {
					if (event.tool_call_id) return null;
					return (
						<div key={event._key} style={turnErrorStyle}>
							<AlertTriangle size={13} strokeWidth={1.8} />
							<span>{event.error ?? 'Agent failure'}</span>
						</div>
					);
				}
				if (event.type === 'result' || event.type === 'tool_result') return null;
				if (event.type === 'status') {
					if (hideStatus) return null;
					return (
						<div key={event._key} style={statusLineStyle}>
							{event.text}
						</div>
					);
				}
				return (
					<div key={event._key} style={activityEventStyle} data-event-kind={event.type}>
						<span style={monoLabelStyle}>{event.type.replaceAll('_', ' ')}</span>
						<span>{event.text ?? clip(resultToText(event.content), 600)}</span>
					</div>
				);
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
	// The system states; it does not chat. Binding receipts and boot notices
	// render as flat mono ledger lines, not conversation bubbles — they are
	// records of what the system did, and must not compete with the dialogue.
	if (message.role === 'system') {
		return (
			<div style={systemReceiptStyle} data-topo="muted">
				<span style={{ ...monoLabelStyle, color: 'var(--atlas-bronze)' }}>▸ {message.label}</span>
				<span style={systemReceiptBodyStyle}>{message.body}</span>
				<span style={{ ...pathTextStyle, fontSize: 10, flex: '0 0 auto' }}>{message.time}</span>
			</div>
		);
	}
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
				{message.role === 'agent' ? (
					<ChatMarkdown text={message.body} />
				) : (
					<div style={{ color: 'var(--l2-fg-1)', fontSize: 13.5, lineHeight: 1.55, overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}>
						{message.body}
					</div>
				)}
			</div>
		</div>
	);
}

function SessionLaunchers({ onSpawn, disabled }: { onSpawn: (agent: AgentRuntime) => void; disabled?: boolean }) {
	return (
		<div style={agentToggleStyle}>
			<SegmentButton active={false} disabled={disabled} onClick={() => onSpawn('native')}>+ Native</SegmentButton>
			<SegmentButton active={false} disabled={disabled} onClick={() => onSpawn('claude_code')} tone="orange">+ Claude Code</SegmentButton>
			<SegmentButton active={false} disabled={disabled} onClick={() => onSpawn('codex')} tone="orange">+ Codex</SegmentButton>
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

const statusLineStyle: React.CSSProperties = {
	padding: '2px 0',
	color: 'var(--l2-fg-3)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.1em',
	textTransform: 'uppercase',
	opacity: 0.55,
	overflowWrap: 'anywhere'
};

const activityEventStyle: React.CSSProperties = {
	display: 'grid',
	gridTemplateColumns: '112px minmax(0, 1fr)',
	gap: 10,
	padding: '8px 0',
	borderTop: '1px solid rgba(237,234,224,0.06)',
	color: 'var(--l2-fg-2)',
	fontSize: 12,
	lineHeight: 1.45,
	overflowWrap: 'anywhere'
};

function MiniMenu({ onPick }: { onPick: (kind: WindowKind, agent?: AgentRuntime) => void }) {
	const [open, setOpen] = useState(false);
	const items: Array<{ label: string; kind: WindowKind; agent?: AgentRuntime }> = [
		{ label: 'native chat', kind: 'chat', agent: 'native' },
		{ label: 'claude code', kind: 'chat', agent: 'claude_code' },
		{ label: 'codex', kind: 'chat', agent: 'codex' },
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

function WorkbenchBadge({ icon, label, title }: { icon: React.ReactNode; label: string; title?: string }) {
	return (
		<span style={workbenchBadgeStyle} title={title}>
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
	background: 'rgba(70,240,160,0.08)',
	animation: 'atlas-pulse-soft 1.8s var(--l2-ease) infinite'
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

const systemReceiptStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'baseline',
	gap: 10,
	padding: '6px 10px',
	borderLeft: '2px solid rgba(176,138,87,0.4)',
	background: 'rgba(237,234,224,0.02)',
	animation: 'atlas-window-in 240ms var(--l2-ease)'
};

const systemReceiptBodyStyle: React.CSSProperties = {
	flex: '1 1 auto',
	minWidth: 0,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	lineHeight: 1.5,
	color: 'var(--l2-fg-2)',
	overflowWrap: 'anywhere'
};

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

/** Prose-shaped tool OUTPUT rendered as markdown — same framed box as
 * toolPreStyle, minus the mono/pre treatment (ChatMarkdown supplies type). */
const toolOutputProseStyle: React.CSSProperties = {
	maxHeight: 280,
	overflow: 'auto',
	background: 'rgba(5,6,10,0.5)',
	border: '1px solid rgba(237,234,224,0.06)',
	borderRadius: 2,
	padding: '8px 9px'
};

/** Reasoning ("thinking") block: dashed hairline + reduced opacity keep it
 * visually subordinate to the answer text and tool cards. */
const reasoningBlockStyle: React.CSSProperties = {
	border: '1px dashed rgba(237,234,224,0.14)',
	borderRadius: 2,
	background: 'rgba(13,16,24,0.35)',
	overflow: 'hidden',
	opacity: 0.85
};

const reasoningLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.14em',
	color: 'var(--l2-fg-3)'
};

const reasoningBodyStyle: React.CSSProperties = {
	borderTop: '1px dashed rgba(237,234,224,0.10)',
	padding: '9px 10px',
	maxHeight: 320,
	overflow: 'auto'
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
