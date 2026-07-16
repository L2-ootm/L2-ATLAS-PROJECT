import { createContext, useContext } from 'react';
import type { AgentRuntime, ToolApproval } from '../lib/api';
import type { SurfaceEvent, SurfaceSession } from '../lib/surfaceContracts';

export const RECONNECT_KEY = 'atlas.agent-surface.reconnect.v1';

export type WorkspaceRequest =
	| { kind: 'global' }
	| { kind: 'project'; projectId: string };

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
	/** Drop the held surface session (workspace rebind/unbind) — local release
	 * first, then a best-effort close; the next prompt re-surfaces fresh. */
	releaseSession: () => Promise<void>;
	resume: () => Promise<void>;
	refresh: () => Promise<void>;
	decide: (
		approval: ToolApproval,
		decision: 'deny' | 'once' | 'session' | 'durable'
	) => Promise<void>;
	setPinned: (pinned: boolean) => void;
	setQueueOpen: (open: boolean) => void;
}

export const AgentSurfaceContext = createContext<AgentSurfaceValue | null>(null);

export function useAgentSurface(): AgentSurfaceValue {
	const value = useContext(AgentSurfaceContext);
	if (!value) throw new Error('useAgentSurface must be used inside AgentSurfaceProvider');
	return value;
}
