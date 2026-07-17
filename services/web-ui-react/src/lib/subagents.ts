import type { ConsoleChatEvent } from './api';
import type { SurfaceEvent } from './surfaceContracts';

export type SubagentPhase = 'queued' | 'running' | 'working' | 'waiting' | 'completed' | 'failed' | 'cancelled' | 'orphaned';

export interface SubagentActivity {
	id: string;
	parentId: string | null;
	phase: SubagentPhase;
	goal: string;
	model: string;
	tool: string;
	toolCount: number;
	depth: number;
	background: boolean;
	durationSeconds: number | null;
}

function record(value: unknown): Record<string, unknown> | null {
	return typeof value === 'object' && value !== null && !Array.isArray(value)
		? value as Record<string, unknown>
		: null;
}

function activity(value: unknown): SubagentActivity | null {
	const data = record(value);
	if (data?.orchestration !== 'subagent' || typeof data.subagent_id !== 'string') return null;
	const rawPhase = String(data.phase ?? 'working');
	const phase: SubagentPhase = rawPhase === 'completed' && data.status === 'failed'
		? 'failed'
		: ['queued', 'running', 'working', 'waiting', 'completed', 'failed', 'cancelled', 'orphaned'].includes(rawPhase)
			? rawPhase as SubagentPhase
			: 'working';
	return {
		id: data.subagent_id,
		parentId: typeof data.parent_id === 'string' ? data.parent_id : null,
		phase,
		goal: typeof data.goal === 'string' ? data.goal : '',
		model: typeof data.model === 'string' ? data.model : '',
		tool: typeof data.tool === 'string' ? data.tool : '',
		toolCount: Number.isFinite(Number(data.tool_count)) ? Number(data.tool_count) : 0,
		depth: Number.isFinite(Number(data.depth)) ? Number(data.depth) : 1,
		background: data.background === true,
		durationSeconds: data.duration_seconds == null ? null : Number(data.duration_seconds)
	};
}

/** Last-write-wins fold: replaying the same immutable event list is idempotent. */
export function subagentsFromSurfaceEvents(events: SurfaceEvent[]): SubagentActivity[] {
	const latest = new Map<string, SubagentActivity>();
	for (const event of events) {
		if (event.kind !== 'task') continue;
		try {
			const next = activity(JSON.parse(event.payload_json));
			if (next) latest.set(next.id, next);
		} catch {
			// Other task producers own arbitrary payloads; ignore malformed actor data.
		}
	}
	return [...latest.values()];
}

export function subagentFromConsoleEvent(event: ConsoleChatEvent): SubagentActivity | null {
	return event.type === 'task' ? activity(event.content) : null;
}

