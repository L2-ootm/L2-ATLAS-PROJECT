import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type * as React from 'react';
import {
	AlertTriangle,
	Bot,
	ChevronDown,
	Folder,
	FolderSearch,
	MessagesSquare,
	Unlink
} from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { TopoScroll } from '../components/TopoScroll';
import { ChatMarkdown } from '../components/ChatMarkdown';
import { StreamReveal } from '../components/chat/StreamReveal';
import { ChatActorWorkspace } from '../components/chat/ChatActorWorkspace';
import { OrchestrationCallCard } from '../components/chat/OrchestrationCallCard';
import { QueuedChatComposer } from '../components/chat/QueuedChatComposer';
import { SubagentRail } from '../components/agent/SubagentActivity';
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
import { displayConsoleEvents, isOrchestrationTool } from '../lib/consoleEventGroups';
import { useAgentSurface } from '../context/AgentSurfaceContext';
import type { ConsoleMessage } from '../context/ConsoleSessionContext';
import { selectFolder } from '../lib/host';
import {
	createChatSession,
	emptyChatSnapshot,
	loadActiveChatSession,
	loadChatSession,
	saveChatSession,
	type ChatSnapshot,
	type QueuedChatPrompt
} from '../lib/chatPersistence';
import {
	sessionBinding,
	sessionTitleFromText,
	setActiveSessionId,
	upsertSessionCatalog
} from '../lib/sessionCatalog';
import { useVisualSettings } from '../lib/visualSettings';
import { isNearBottom } from '../lib/scrollFollow';
import { subagentsFromConsoleEvents } from '../lib/subagents';
import { turnReceiptSignature } from '../lib/turnReceipt';
import { GOAL_STATUS_MESSAGE, parseMissionSlashIntent } from '../lib/missionSlash';
import { ReasoningBlock, ToolCallCard } from './Console';

/**
 * Dedicated operator chat — a single, full-page conversation with the agent.
 *
 * The multi-window Console stays the workbench; this surface is the polished
 * dialogue: one transcript, paced streaming reveal with a scan edge,
 * stick-to-bottom follow (only when the operator is already at the bottom),
 * run receipts shown once per session instead of on every turn, and a
 * grace-drained watchdog so answers can never freeze mid-chunk.
 */

type BindingMode = 'project' | 'folder';

type ActiveChatTurn = {
	turnId: string;
	runId: string | null;
	afterSeq: number;
	goalMode: boolean;
};

function nowLabel(): string {
	return new Intl.DateTimeFormat(undefined, {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit'
	}).format(new Date());
}

function pathTail(path: string): string {
	const tail = path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? path;
	return tail.length > 28 ? `${tail.slice(0, 27)}…` : tail;
}

export default function Chat() {
	const agentSurface = useAgentSurface();
	const visualSettings = useVisualSettings();
	const [initial] = useState(loadActiveChatSession);
	const [catalogSessionId, setCatalogSessionId] = useState(initial.id);
	const [messages, setMessages] = useState<ConsoleMessage[]>(initial.snapshot.messages);
	const [draft, setDraft] = useState(initial.snapshot.draft);
	const [queuedPrompts, setQueuedPrompts] = useState<QueuedChatPrompt[]>(initial.snapshot.queuedPrompts ?? []);
	const [queueError, setQueueError] = useState<string | null>(null);
	// One-shot composer seed (?draft=/hello) — module page actions and deep
	// links land here; the param is consumed so reloads don't re-seed.
	const [searchParams, setSearchParams] = useSearchParams();
	useEffect(() => {
		const seeded = searchParams.get('draft');
		if (seeded) {
			setDraft(seeded);
			const next = new URLSearchParams(searchParams);
			next.delete('draft');
			setSearchParams(next, { replace: true });
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);
	const [agent, setAgent] = useState<AgentRuntime>(initial.snapshot.agent);
	const [bindingMode, setBindingMode] = useState<BindingMode>(initial.snapshot.bindingMode);
	const [folderPath, setFolderPath] = useState(initial.snapshot.folderPath);
	const [projectId, setProjectId] = useState(initial.snapshot.projectId);
	const [projects, setProjects] = useState<Project[]>([]);
	const [activeTurn, setActiveTurn] = useState<ActiveChatTurn | null>(null);
	const [bindOpen, setBindOpen] = useState(false);
	const dispatchPromptRef = useRef<(prompt: string) => Promise<void>>(async () => undefined);

	useEffect(() => {
		let alive = true;
		void listProjects(100)
			.then(({ projects: loaded }) => {
				if (alive) setProjects(loaded);
			})
			.catch(() => undefined);
		return () => {
			alive = false;
		};
	}, []);

	const activeProject = useMemo(
		() => (bindingMode === 'project' && projectId ? projects.find((p) => p.id === projectId) ?? null : null),
		[bindingMode, projectId, projects]
	);
	const boundCwd = bindingMode === 'project' ? activeProject?.root_path ?? null : folderPath.trim() || null;

	useEffect(() => {
		const payload: ChatSnapshot = { messages, draft, agent, bindingMode, folderPath, projectId, queuedPrompts };
		saveChatSession(catalogSessionId, payload);
		const firstOperator = messages.find((message) => message.role === 'operator');
		upsertSessionCatalog({
			id: catalogSessionId,
			surface: 'chat',
			title: sessionTitleFromText(firstOperator?.body, 'New chat session'),
			agent,
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
		messages,
		draft,
		agent,
		bindingMode,
		folderPath,
		projectId,
		queuedPrompts,
		activeProject
	]);

	// ── event merge (same contract as Console's, single transcript) ─────────
	useEffect(() => {
		const pending = surfaceEventsForTurn(agentSurface.events, activeTurn);
		if (!activeTurn || pending.length === 0) return;
		const projected = pending.map((surfaceEvent): ConsoleChatEvent => {
			try {
				return surfaceConsoleEvent(surfaceEvent);
			} catch (cause) {
				return { type: 'failure', error: cause instanceof Error ? cause.message : String(cause) };
			}
		});
		const finalGoalState = finalGoalJudgementState(pending);
		const terminal = activeTurn.goalMode
			? finalGoalState !== null
			: projected.some(isRunTerminalEvent);
		const afterSeq = Math.max(...pending.map((event) => event.seq));
		const { turnId, runId } = activeTurn;

		setMessages((prev) =>
			prev.map((message) => {
				if (message.id !== turnId) return message;
				let body = message.body;
				let streamDeltaStart = message.streamDeltaStart;
				let next = message;
				for (const event of projected) {
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
					next = {
						...next,
						events: [...(next.events ?? []), event],
						body,
						streamDeltaStart,
						status:
							event.type === 'failure' && !event.tool_call_id
								? 'failed'
								: event.type === 'result'
									? event.is_error
										? 'failed'
										: 'succeeded'
									: next.status
					};
				}
				if (activeTurn.goalMode) {
					next = {
						...next,
						status: finalGoalState
							? finalGoalState === 'failed' ? 'failed' : 'succeeded'
							: 'pending'
					};
				}
				return next;
			})
		);
		setActiveTurn((current) => {
			if (!current || current.turnId !== turnId || current.runId !== runId) return current;
			return terminal ? null : { ...current, afterSeq };
		});
	}, [activeTurn, agentSurface.events]);

	// ── stuck-turn watchdog with grace drain (see Console.tsx) ──────────────
	const watchedRunId = activeTurn?.runId ?? null;
	const watchedTurnId = activeTurn?.turnId ?? null;
	const watchedGoalMode = activeTurn?.goalMode ?? false;
	const terminalSeenRef = useRef<string | null>(null);
	const refreshSurfaceEvents = agentSurface.refresh;
	useEffect(() => {
		if (!watchedRunId || !watchedTurnId) return;
		terminalSeenRef.current = null;
		const timer = window.setInterval(async () => {
			try {
				const { run } = await getRun(watchedRunId);
				if (!['succeeded', 'failed', 'cancelled'].includes(run.status)) return;
				if (watchedGoalMode) {
					void refreshSurfaceEvents().catch(() => undefined);
					return;
				}
				// First terminal sighting: the tail surface events (last deltas +
				// final reconcile) may not be polled yet — force a refresh and give
				// them one more tick before finalizing, or the answer truncates.
				if (terminalSeenRef.current !== watchedRunId) {
					terminalSeenRef.current = watchedRunId;
					void refreshSurfaceEvents().catch(() => undefined);
					return;
				}
				const failed = run.status !== 'succeeded';
				setMessages((prev) =>
					prev.map((message) =>
						message.id === watchedTurnId && message.status === 'pending'
							? {
									...message,
									status: failed ? 'failed' : 'succeeded',
									body: message.body || run.summary || (failed ? 'Run failed.' : 'Run completed.')
								}
							: message
					)
				);
				setActiveTurn((current) => (current?.runId === watchedRunId ? null : current));
			} catch {
				// Gateway blip — the next tick retries.
			}
		}, 8000);
		return () => window.clearInterval(timer);
	}, [watchedRunId, watchedTurnId, watchedGoalMode, refreshSurfaceEvents]);

	// ── workspace binding → registered project resolution ───────────────────
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
				setProjects((prev) => [...prev, project]);
				return project.id;
			} catch {
				return null;
			}
		},
		[projects]
	);

	// Rebinding releases the held surface session (it is workspace-bound).
	const bindingKey = `${bindingMode}|${projectId}|${boundCwd ?? ''}`;
	const releaseSession = agentSurface.releaseSession;
	useEffect(() => {
		if (activeTurn) return;
		void releaseSession();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [bindingKey]);

	// ── dispatch ─────────────────────────────────────────────────────────────
	async function dispatchPrompt(prompt: string) {
		const goalMode = parseMissionSlashIntent(prompt)?.kind === 'goal-launch';
		const operator: ConsoleMessage = {
			id: `${Date.now()}-operator`,
			role: 'operator',
			label: 'OPERATOR',
			body: prompt,
			time: nowLabel()
		};
		const turnId = `${Date.now()}-agent`;
		const liveTurn: ConsoleMessage = {
			id: turnId,
			role: 'agent',
			label: agentRuntimeLabel(agent),
			body: '',
			time: nowLabel(),
			status: 'pending',
			events: []
		};
		setMessages((prev) => [...prev, operator, liveTurn]);
		const afterSeq = agentSurface.events.reduce((highest, event) => Math.max(highest, event.seq), -1);
		setActiveTurn({ turnId, runId: null, afterSeq, goalMode });
		try {
			let workspace: { kind: 'global' } | { kind: 'project'; projectId: string } = { kind: 'global' };
			if (bindingMode === 'project' && projectId) {
				workspace = { kind: 'project', projectId };
			} else if (bindingMode === 'folder' && boundCwd) {
				const pid = folderProjectId ?? (await ensureFolderProject(boundCwd));
				if (pid) {
					setFolderProjectId(pid);
					workspace = { kind: 'project', projectId: pid };
				}
			}
			const runId = await agentSurface.submitPrompt(prompt, agent, workspace);
			if (runId === null) {
				setMessages((prev) =>
					prev.map((m) =>
						m.id === turnId ? { ...m, status: 'succeeded', body: GOAL_STATUS_MESSAGE } : m
					)
				);
				setActiveTurn((current) => (current?.turnId === turnId ? null : current));
				return;
			}
			setActiveTurn((current) => (current?.turnId === turnId ? { ...current, runId } : current));
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			setMessages((prev) =>
				prev.map((m) =>
					m.id === turnId
						? { ...m, status: 'failed', body: m.body || msg, events: [...(m.events ?? []), { type: 'failure', error: msg }] }
						: m
				)
			);
			setActiveTurn((current) => (current?.turnId === turnId ? null : current));
		}
	}
	dispatchPromptRef.current = dispatchPrompt;

	function submitDraft() {
		const prompt = draft.trim();
		if (!prompt) return;
		setQueueError(null);
		if (activeTurn) {
			if (queuedPrompts.length >= 4) {
				setQueueError('The four-message queue is full. Remove or edit an item before adding another.');
				return;
			}
			const id = globalThis.crypto?.randomUUID?.() ?? `queued-${Date.now()}`;
			setQueuedPrompts((current) => [...current, { id, text: prompt }]);
			setDraft('');
			return;
		}
		setDraft('');
		void dispatchPrompt(prompt);
	}

	async function cancelRun() {
		try {
			await agentSurface.cancel();
		} catch {
			// The watchdog settles the turn either way.
		}
	}

	function applySnapshot(id: string, snapshot: ChatSnapshot) {
		setCatalogSessionId(id);
		setActiveSessionId('chat', id);
		setMessages(snapshot.messages);
		setDraft(snapshot.draft);
		setAgent(snapshot.agent);
		setBindingMode(snapshot.bindingMode);
		setFolderPath(snapshot.folderPath);
		setProjectId(snapshot.projectId);
		setQueuedPrompts(snapshot.queuedPrompts ?? []);
		setQueueError(null);
		setActiveTurn(null);
		setBindOpen(false);
		void agentSurface.releaseSession();
	}

	function selectCatalogSession(id: string) {
		if (activeTurn) return;
		const snapshot = loadChatSession(id);
		if (snapshot) applySnapshot(id, snapshot);
	}

	function newSession(unbound = false) {
		if (activeTurn) return;
		const snapshot = emptyChatSnapshot({
			agent,
			bindingMode: unbound ? 'folder' : bindingMode,
			folderPath: unbound ? '' : folderPath,
			projectId: unbound ? '' : projectId
		});
		const id = createChatSession(snapshot);
		applySnapshot(id, snapshot);
	}

	async function chooseFolder() {
		setBindingMode('folder');
		try {
			const picked = await selectFolder('Choose chat working folder');
			if (picked) setFolderPath(picked);
		} catch {
			// Gateway offline — the binding chip keeps showing UNBOUND.
		}
	}

	function unbind() {
		setBindingMode('folder');
		setFolderPath('');
		setProjectId('');
		setFolderProjectId(null);
	}

	// ── stick-to-bottom follow ───────────────────────────────────────────────
	const viewportRef = useRef<HTMLDivElement | null>(null);
	const pinnedRef = useRef(true);
	const [unpinned, setUnpinned] = useState(false);
	const busy = !!activeTurn;
	const wasBusyRef = useRef(false);
	const drainingQueueRef = useRef(false);
	useEffect(() => {
		if (busy) {
			wasBusyRef.current = true;
			return;
		}
		if (!wasBusyRef.current || drainingQueueRef.current || queuedPrompts.length === 0) return;
		const next = queuedPrompts[0];
		wasBusyRef.current = false;
		drainingQueueRef.current = true;
		setQueuedPrompts((current) => current.filter((item) => item.id !== next.id));
		void dispatchPromptRef.current(next.text).finally(() => {
			drainingQueueRef.current = false;
		});
	}, [busy, queuedPrompts]);

	function promoteQueuedPrompt(id: string) {
		setQueuedPrompts((current) => {
			const selected = current.find((item) => item.id === id);
			return selected ? [selected, ...current.filter((item) => item.id !== id)] : current;
		});
	}

	function editQueuedPrompt(item: QueuedChatPrompt) {
		if (draft.trim()) {
			setQueueError('The composer already has a draft. Send or clear it before editing a queued prompt.');
			return;
		}
		setQueuedPrompts((current) => current.filter((queued) => queued.id !== item.id));
		setDraft(item.text);
		setQueueError(null);
	}
	const onViewportScroll = useCallback((el: HTMLDivElement) => {
		const pinned =
			visualSettings.autoFollow &&
			isNearBottom(el);
		pinnedRef.current = pinned;
		setUnpinned(!pinned);
	}, [visualSettings.autoFollow]);
	const onViewportUserIntent = useCallback(() => {
		pinnedRef.current = false;
		setUnpinned(true);
	}, []);
	useEffect(() => {
		const el = viewportRef.current;
		if (el && visualSettings.autoFollow && pinnedRef.current) el.scrollTop = el.scrollHeight;
	}, [messages, visualSettings.autoFollow]);
	const jumpToLatest = useCallback(() => {
		const el = viewportRef.current;
		if (!el) return;
		pinnedRef.current = true;
		setUnpinned(false);
		el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
	}, []);

	// Receipts repeat identically per session — show only when changed.
	let lastReceipt: string | null = null;

	const bindingLabel = activeProject
		? activeProject.name
		: boundCwd
			? pathTail(boundCwd)
			: 'UNBOUND';

	return (
		<Page
			eyebrow="MISSION · CHAT"
			title="Chat"
			max={null}
			actions={
				<>
					<SessionNavigator
						activeSessionId={catalogSessionId}
						surface="chat"
						bound={!!(boundCwd || projectId)}
						disabled={busy}
						onNewSession={newSession}
						onSelectSession={selectCatalogSession}
						onChooseFolder={() => {
							setBindOpen(false);
							void chooseFolder();
						}}
						onUnbind={unbind}
					/>
					<div style={{ position: 'relative' }}>
						<button
							type="button"
							style={bindingChipStyle}
							onClick={() => setBindOpen((v) => !v)}
							title={boundCwd ?? 'No workspace bound'}
						>
							<Folder size={13} strokeWidth={1.7} />
							{bindingLabel}
							<ChevronDown size={12} strokeWidth={1.8} />
						</button>
						{bindOpen && (
							<div style={bindMenuStyle} data-topo="atlas">
								<div style={bindMenuTitleStyle}>PROJECTS</div>
								{projects.map((project) => (
									<button
										key={project.id}
										type="button"
										style={bindMenuItemStyle}
										onClick={() => {
											setBindingMode('project');
											setProjectId(project.id);
											setBindOpen(false);
										}}
									>
										{project.name}
									</button>
								))}
								{projects.length === 0 && <div style={bindMenuEmptyStyle}>No registered projects</div>}
								<div style={bindMenuDividerStyle} />
								<button
									type="button"
									style={bindMenuItemStyle}
									onClick={() => {
										setBindOpen(false);
										void chooseFolder();
									}}
								>
									<FolderSearch size={13} strokeWidth={1.7} style={{ marginRight: 6 }} />
									Choose folder…
								</button>
							</div>
						)}
					</div>
					{(boundCwd || projectId) && (
						<IconAction title="Unbind workspace" onClick={unbind}>
							<Unlink size={14} strokeWidth={1.7} />
						</IconAction>
					)}
				</>
			}
		>
			<GlassPanel
				data-topo={agent === 'claude_code' ? 'ai' : 'atlas'}
				style={{
					height: 'calc(100vh - 142px)',
					minHeight: 560,
					overflow: 'hidden'
				}}
			>
				<div className="chat-workspace-grid">
					<div className="chat-context-reserve" aria-hidden="true" />
					<div className="chat-transcript-column">
						<div className="chat-transcript-viewport">
							<TopoScroll
								className="chat-transcript-scroll"
								tone={agent === 'claude_code' ? 'atlas' : 'info'}
								style={{ minHeight: 0, height: '100%' }}
								viewportStyle={transcriptStyle}
								viewportRef={viewportRef}
								onViewportScroll={onViewportScroll}
								onViewportUserIntent={onViewportUserIntent}
							>
								{messages.length === 0 && (
									<div style={emptyStateStyle}>
										<MessagesSquare size={26} strokeWidth={1.2} style={{ color: 'var(--atlas-celestial)', opacity: 0.7 }} />
										<div style={{ ...monoLabelStyle, fontSize: 11 }}>OPERATOR CHANNEL</div>
										<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, maxWidth: 420, textAlign: 'center', lineHeight: 1.6 }}>
											Direct line to {agentRuntimeLabel(agent)}.{' '}
											{boundCwd ? `Bound to ${pathTail(boundCwd)}.` : 'Bind a project or folder to scope execution.'}
										</div>
									</div>
								)}
								{messages.map((message) => {
									if (message.role === 'agent' && (message.events?.length || message.status === 'pending')) {
										const receipt = turnReceiptSignature(message);
										const hideStatus = receipt !== null && receipt === lastReceipt;
										if (receipt !== null) lastReceipt = receipt;
										return <ChatAgentTurn key={message.id} message={message} hideStatus={hideStatus} />;
									}
									return <ChatBubble key={message.id} message={message} />;
								})}
							</TopoScroll>
							{unpinned && (
								<button type="button" onClick={jumpToLatest} className="atlas-jump-latest" title="Follow the live response">
									<ChevronDown size={13} strokeWidth={2} />
									LATEST
								</button>
							)}
						</div>
						<QueuedChatComposer
							draft={draft}
							onDraftChange={(value) => {
								setDraft(value);
								if (queueError) setQueueError(null);
							}}
							queue={queuedPrompts}
							busy={busy}
							agent={agent}
							error={queueError}
							onSubmit={submitDraft}
							onCancel={() => void cancelRun()}
							onPromote={promoteQueuedPrompt}
							onEdit={editQueuedPrompt}
							onRemove={(id) => setQueuedPrompts((current) => current.filter((item) => item.id !== id))}
						/>
					</div>
					<ChatActorWorkspace
						events={agentSurface.events}
						busy={busy}
						provider={agentSurface.session?.model.provider}
						modelId={agentSurface.session?.model.model_id}
					/>
				</div>
			</GlassPanel>
		</Page>
	);
}

// ── turn rendering ──────────────────────────────────────────────────────────

/** Streamed answer text: paced scan-edge reveal while the run is open, then a
 * swap to full markdown only AFTER the reveal has played out to the end. */
function TurnText({ text, streaming }: { text: string; streaming: boolean }) {
	const [settled, setSettled] = useState(!streaming);
	const everStreamed = useRef(streaming);
	if (streaming) everStreamed.current = true;
	if (!everStreamed.current || (settled && !streaming)) {
		return text ? <ChatMarkdown text={text} /> : null;
	}
	return <StreamReveal text={text} done={!streaming} onSettled={() => setSettled(true)} />;
}

function ChatAgentTurn({ message, hideStatus }: { message: ConsoleMessage; hideStatus: boolean }) {
	const events = useMemo(() => message.events ?? [], [message.events]);
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
	const pending = message.status === 'pending';
	return (
		<div
			style={turnStyle}
			className={pending ? 'atlas-inference-wake' : undefined}
			data-topo={message.status === 'failed' ? 'bad' : 'good'}
		>
			<div style={turnHeaderStyle}>
				<Bot size={13} strokeWidth={1.7} style={{ color: 'rgba(70,240,160,0.95)' }} />
				<span style={monoLabelStyle}>{message.label}</span>
				<span style={{ ...timeTextStyle }}>{message.time}</span>
				{pending && <span style={liveBadgeStyle}>LIVE</span>}
			</div>
			{events.length === 0 && pending && <div style={{ color: 'var(--l2-fg-3)', fontSize: 13 }}>Working…</div>}
			<SubagentRail events={events} />
			{displayEvents.map((event) => {
				if (event.type === 'task') return null;
				if (event.type === 'text') {
					return <TurnText key={event._key} text={event.text ?? ''} streaming={!!event._open && pending} />;
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

function ChatBubble({ message }: { message: ConsoleMessage }) {
	const operator = message.role === 'operator';
	const failed = message.status === 'failed';
	if (message.role === 'system') {
		return (
			<div style={systemReceiptStyle} data-topo="muted">
				<span style={{ ...monoLabelStyle, color: 'var(--atlas-bronze)' }}>▸ {message.label}</span>
				<span style={{ color: 'var(--l2-fg-3)', fontSize: 12, minWidth: 0 }}>{message.body}</span>
				<span style={{ ...timeTextStyle, flex: '0 0 auto' }}>{message.time}</span>
			</div>
		);
	}
	return (
		<div style={{ display: 'flex', justifyContent: operator ? 'flex-end' : 'flex-start' }}>
			<div
				data-topo={failed ? 'bad' : operator ? 'info' : 'good'}
				style={{
					maxWidth: 'min(720px, 88%)',
					borderRadius: 2,
					border: failed
						? '1px solid rgba(255,77,125,0.32)'
						: operator
							? '1px solid rgba(79,139,255,0.32)'
							: '1px solid rgba(70,240,160,0.22)',
					background: failed ? 'rgba(255,77,125,0.06)' : operator ? 'rgba(79,139,255,0.10)' : 'rgba(70,240,160,0.055)',
					padding: '12px 13px',
					animation: 'atlas-window-in 260ms var(--l2-ease)'
				}}
			>
				<div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
					<span style={monoLabelStyle}>{message.label}</span>
					<span style={timeTextStyle}>{message.time}</span>
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

// ── small chrome ────────────────────────────────────────────────────────────

function IconAction({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
	return (
		<button type="button" title={title} onClick={onClick} style={iconActionStyle}>
			{children}
		</button>
	);
}

// ── styles ──────────────────────────────────────────────────────────────────

const monoLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	color: 'var(--l2-fg-2)',
	textTransform: 'uppercase'
};

const timeTextStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-mono)',
	fontSize: 10,
	color: 'var(--l2-fg-3)'
};

const liveBadgeStyle: React.CSSProperties = {
	marginLeft: 'auto',
	fontFamily: 'var(--l2-mono)',
	fontSize: 9,
	letterSpacing: '0.16em',
	color: 'var(--atlas-emerald)',
	border: '1px solid rgba(70,240,160,0.35)',
	borderRadius: 1,
	padding: '2px 6px',
	animation: 'atlas-pulse-soft 1.4s var(--l2-ease) infinite'
};

const transcriptStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	gap: 14,
	padding: '22px clamp(16px, 6vw, 96px) 26px',
	maxWidth: 1040,
	width: '100%',
	margin: '0 auto'
};

const emptyStateStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	alignItems: 'center',
	gap: 10,
	margin: 'auto',
	padding: '80px 0'
};

const turnStyle: React.CSSProperties = {
	display: 'grid',
	gap: 10,
	border: '1px solid rgba(70,240,160,0.16)',
	background: 'rgba(70,240,160,0.035)',
	borderRadius: 2,
	padding: '12px 14px'
};

const turnHeaderStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8
};

const turnErrorStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 7,
	color: 'var(--l2-error, #ff4d7d)',
	fontSize: 12.5
};

const statusLineStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-mono)',
	fontSize: 10,
	letterSpacing: '0.1em',
	color: 'var(--l2-fg-3)',
	textTransform: 'uppercase'
};

const turnFooterStyle: React.CSSProperties = {
	display: 'flex',
	gap: 14,
	fontFamily: 'var(--l2-mono)',
	fontSize: 10,
	color: 'var(--l2-fg-3)',
	borderTop: '1px solid rgba(237,234,224,0.06)',
	paddingTop: 8
};

const systemReceiptStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'baseline',
	gap: 10,
	padding: '4px 2px'
};

const iconActionStyle: React.CSSProperties = {
	border: '1px solid rgba(237,234,224,0.10)',
	background: 'rgba(237,234,224,0.03)',
	color: 'var(--l2-fg-2)',
	borderRadius: 2,
	width: 30,
	height: 30,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	cursor: 'pointer'
};

const bindingChipStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	border: '1px solid rgba(237,234,224,0.12)',
	background: 'rgba(237,234,224,0.03)',
	color: 'var(--l2-fg-2)',
	borderRadius: 2,
	padding: '6px 10px',
	fontFamily: 'var(--l2-mono)',
	fontSize: 10,
	letterSpacing: '0.1em',
	cursor: 'pointer',
	maxWidth: 240,
	whiteSpace: 'nowrap',
	overflow: 'hidden',
	textOverflow: 'ellipsis'
};

const bindMenuStyle: React.CSSProperties = {
	position: 'absolute',
	top: 'calc(100% + 6px)',
	right: 0,
	zIndex: 60,
	minWidth: 240,
	maxHeight: 320,
	overflowY: 'auto',
	border: '1px solid rgba(237,234,224,0.12)',
	background: 'rgba(10,13,20,0.98)',
	borderRadius: 2,
	padding: 6,
	boxShadow: '0 18px 52px rgba(0,0,0,0.55)'
};

const bindMenuTitleStyle: React.CSSProperties = {
	...monoLabelStyle,
	padding: '6px 8px 4px'
};

const bindMenuItemStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	width: '100%',
	border: 'none',
	background: 'transparent',
	color: 'var(--l2-fg-1)',
	fontSize: 12.5,
	textAlign: 'left',
	padding: '7px 8px',
	borderRadius: 1,
	cursor: 'pointer'
};

const bindMenuEmptyStyle: React.CSSProperties = {
	color: 'var(--l2-fg-3)',
	fontSize: 12,
	padding: '6px 8px'
};

const bindMenuDividerStyle: React.CSSProperties = {
	height: 1,
	background: 'rgba(237,234,224,0.08)',
	margin: '6px 0'
};
