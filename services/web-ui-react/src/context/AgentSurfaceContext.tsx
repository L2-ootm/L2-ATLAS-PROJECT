import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
	type ReactNode
} from 'react';
import {
	approveToolCall,
	cancelSurfaceSession,
	createMission,
	createSurfaceSession,
	getSurfaceEvents,
	getSurfaceSession,
	heartbeatSurfaceSession,
	listOwnedToolApprovals,
	rejectToolCall,
	resumeSurfaceSession,
	startRun,
	type AgentRuntime,
	type ToolApproval
} from '../lib/api';
import {
	parseSurfaceReplay,
	type SurfaceEvent,
	type SurfaceSession
} from '../lib/surfaceContracts';

const RECONNECT_KEY = 'atlas.agent-surface.reconnect.v1';

type WorkspaceRequest =
	| { kind: 'global' }
	| { kind: 'project'; projectId: string };

interface ReconnectIdentity {
	id: string;
	ownerToken: string;
}

export interface AgentSurfaceValue {
	session: SurfaceSession | null;
	events: SurfaceEvent[];
	approvals: ToolApproval[];
	outcomes: ToolApproval[];
	error: string | null;
	busy: boolean;
	pinned: boolean;
	queueOpen: boolean;
	openSurface: (workspace: WorkspaceRequest) => Promise<SurfaceSession>;
	submitPrompt: (
		prompt: string,
		agent: AgentRuntime,
		workspace: WorkspaceRequest
	) => Promise<string>;
	cancel: () => Promise<void>;
	refresh: () => Promise<void>;
	decide: (
		approval: ToolApproval,
		decision: 'deny' | 'once' | 'session' | 'durable'
	) => Promise<void>;
	setPinned: (pinned: boolean) => void;
}

const AgentSurfaceContext = createContext<AgentSurfaceValue | null>(null);

function surfaceId(): string {
	return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}`;
}

function withOwnerToken(next: SurfaceSession, prior: SurfaceSession): SurfaceSession {
	return next.owner_token ? next : { ...next, owner_token: prior.owner_token };
}

export function AgentSurfaceProvider({ children }: { children: ReactNode }) {
	const [session, setSession] = useState<SurfaceSession | null>(null);
	const [events, setEvents] = useState<SurfaceEvent[]>([]);
	const [approvals, setApprovals] = useState<ToolApproval[]>([]);
	const [outcomes, setOutcomes] = useState<ToolApproval[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [pinned, setPinned] = useState(false);
	const cursor = useRef(-1);
	const sessionRef = useRef<SurfaceSession | null>(null);

	const retainSession = useCallback((next: SurfaceSession | null) => {
		sessionRef.current = next;
		setSession(next);
		if (next?.owner_token) {
			const reconnect: ReconnectIdentity = {
				id: next.id,
				ownerToken: next.owner_token
			};
			localStorage.setItem(RECONNECT_KEY, JSON.stringify(reconnect));
		} else if (!next) {
			localStorage.removeItem(RECONNECT_KEY);
		}
	}, []);

	const refresh = useCallback(async () => {
		const current = sessionRef.current;
		if (!current) return;
		const [replayValue, owned] = await Promise.all([
			getSurfaceEvents(current.id, cursor.current),
			listOwnedToolApprovals(current.id)
		]);
		const replay = parseSurfaceReplay(replayValue);
		if (replay.events.length > 0) {
			cursor.current = replay.events.at(-1)!.seq;
			setEvents((prior) => [...prior, ...replay.events]);
		}
		setApprovals(
			owned.filter(
				approval =>
					approval.surface_session_id === current.id && approval.status === 'pending'
			)
		);
	}, []);

	const openSurface = useCallback(
		async (workspace: WorkspaceRequest) => {
			setBusy(true);
			setError(null);
			try {
				const created = await createSurfaceSession({
					surface_kind: 'webui',
					surface_id: surfaceId(),
					workspace_kind: workspace.kind,
					...(workspace.kind === 'project' ? { project_id: workspace.projectId } : {})
				});
				cursor.current = -1;
				setEvents([]);
				setApprovals([]);
				retainSession(created);
				return created;
			} catch (cause) {
				const message = cause instanceof Error ? cause.message : String(cause);
				setError(message);
				throw cause;
			} finally {
				setBusy(false);
			}
		},
		[retainSession]
	);

	const submitPrompt = useCallback(
		async (prompt: string, agent: AgentRuntime, workspace: WorkspaceRequest) => {
			setBusy(true);
			setError(null);
			try {
				const current = sessionRef.current ?? (await openSurface(workspace));
				const created = await createMission(
					prompt.split(/\r?\n/, 1)[0].slice(0, 120) || 'Agent request',
					prompt,
					workspace.kind === 'project' ? workspace.projectId : undefined
				);
				const started = await startRun(created.mission.id, agent, true, current.id);
				return started.run.id;
			} catch (cause) {
				const message = cause instanceof Error ? cause.message : String(cause);
				setError(message);
				throw cause;
			} finally {
				setBusy(false);
			}
		},
		[openSurface]
	);

	const cancel = useCallback(async () => {
		const current = sessionRef.current;
		if (!current) return;
		const next = withOwnerToken(await cancelSurfaceSession(current), current);
		retainSession(next);
	}, [retainSession]);

	const decide = useCallback(
		async (
			approval: ToolApproval,
			decision: 'deny' | 'once' | 'session' | 'durable'
		) => {
			if (
				!sessionRef.current ||
				approval.surface_session_id !== sessionRef.current.id ||
				!approval.nonce
			) {
				throw new Error('approval is not actionable by this surface');
			}
			setApprovals((prior) =>
				prior.map((item) =>
					item.id === approval.id ? { ...item, status: 'executing' } : item
				)
			);
			try {
				const outcome =
					decision === 'deny'
						? await rejectToolCall(approval, 'rejected from WebUI')
						: await approveToolCall(approval, decision);
				setApprovals((prior) => prior.filter((item) => item.id !== approval.id));
				setOutcomes((prior) => [outcome, ...prior].slice(0, 20));
			} catch (cause) {
				await refresh();
				throw cause;
			}
		},
		[refresh]
	);

	useEffect(() => {
		const raw = localStorage.getItem(RECONNECT_KEY);
		if (!raw) return;
		let identity: ReconnectIdentity;
		try {
			identity = JSON.parse(raw) as ReconnectIdentity;
		} catch {
			localStorage.removeItem(RECONNECT_KEY);
			return;
		}
		void getSurfaceSession(identity.id)
			.then(async projected => {
				let restored = { ...projected, owner_token: identity.ownerToken };
				if (projected.state === 'suspended') {
					restored = withOwnerToken(await resumeSurfaceSession(restored), restored);
				}
				if (['completed', 'failed', 'reclaimed'].includes(restored.state)) {
					retainSession(null);
					return;
				}
				retainSession(restored);
			})
			.catch(() => retainSession(null));
	}, [retainSession]);

	useEffect(() => {
		if (!session || !['active', 'suspended', 'resuming', 'cancelling'].includes(session.state)) {
			return;
		}
		void refresh().catch(cause => setError(cause instanceof Error ? cause.message : String(cause)));
		const timer = window.setInterval(() => {
			const current = sessionRef.current;
			if (!current) return;
			void Promise.all([heartbeatSurfaceSession(current), refresh()])
				.then(([next]) => retainSession(withOwnerToken(next, current)))
				.catch(cause => setError(cause instanceof Error ? cause.message : String(cause)));
		}, 2000);
		return () => window.clearInterval(timer);
	}, [refresh, retainSession, session?.id, session?.state]);

	const value = useMemo<AgentSurfaceValue>(
		() => ({
			session,
			events,
			approvals,
			outcomes,
			error,
			busy,
			pinned,
			queueOpen: approvals.length > 0 || pinned,
			openSurface,
			submitPrompt,
			cancel,
			refresh,
			decide,
			setPinned
		}),
		[
			session,
			events,
			approvals,
			outcomes,
			error,
			busy,
			pinned,
			openSurface,
			submitPrompt,
			cancel,
			refresh,
			decide
		]
	);

	return (
		<AgentSurfaceContext.Provider value={value}>
			{children}
		</AgentSurfaceContext.Provider>
	);
}

export function useAgentSurface(): AgentSurfaceValue {
	const value = useContext(AgentSurfaceContext);
	if (!value) throw new Error('useAgentSurface must be used inside AgentSurfaceProvider');
	return value;
}

export { RECONNECT_KEY };
