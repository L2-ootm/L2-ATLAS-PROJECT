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
	childRunId: string | null;
}

export interface SubagentLifecycleStep {
	seq: number;
	occurredAt: string;
	activity: SubagentActivity;
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
	const terminalStatus = String(data.status ?? '');
	const phase: SubagentPhase = rawPhase === 'completed' && ['failed', 'timeout', 'timed_out'].includes(terminalStatus)
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
		durationSeconds: data.duration_seconds == null ? null : Number(data.duration_seconds),
		childRunId: typeof data.child_run_id === 'string' ? data.child_run_id : null
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

export function subagentFromSurfaceEvent(event: SurfaceEvent): SubagentActivity | null {
	if (event.kind !== 'task') return null;
	try {
		return activity(JSON.parse(event.payload_json));
	} catch {
		return null;
	}
}

export function subagentLifecycleFromSurfaceEvents(
	events: SurfaceEvent[],
	actorId: string
): SubagentLifecycleStep[] {
	const steps: SubagentLifecycleStep[] = [];
	for (const event of events) {
		const next = subagentFromSurfaceEvent(event);
		if (next?.id === actorId) {
			steps.push({ seq: event.seq, occurredAt: event.occurred_at, activity: next });
		}
	}
	return steps;
}

export function subagentFromConsoleEvent(event: ConsoleChatEvent): SubagentActivity | null {
	return event.type === 'task' ? activity(event.content) : null;
}

export function subagentsFromConsoleEvents(events: ConsoleChatEvent[]): SubagentActivity[] {
	const latest = new Map<string, SubagentActivity>();
	for (const event of events) {
		const next = subagentFromConsoleEvent(event);
		if (next) latest.set(next.id, next);
	}
	return [...latest.values()];
}

/** One per-step row in a subagent's live telemetry stream (Chat only —
 * Console's ConsoleChatEvent carries no seq/timestamp for a step replay). */
export interface SubagentStreamItem {
	seq: number;
	occurredAt: string;
	phase: string;
	detail: string;
	kind: string;
}

export function shortActorId(id: string): string {
	return id.replace(/^actor-/, '').slice(0, 8).toUpperCase();
}
