import type { ConsoleChatEvent } from './api';
import type { SurfaceEvent } from './surfaceContracts';

export type GoalJudgementState = 'active' | 'done' | 'paused' | 'exhausted' | 'failed';

const GOAL_JUDGEMENT_STATES = new Set<GoalJudgementState>([
	'active',
	'done',
	'paused',
	'exhausted',
	'failed'
]);

export function goalJudgementState(event: SurfaceEvent): GoalJudgementState | null {
	try {
		const payload = JSON.parse(event.payload_json) as { state?: unknown };
		if (typeof payload.state !== 'string' || !GOAL_JUDGEMENT_STATES.has(payload.state as GoalJudgementState)) {
			return null;
		}
		const state = payload.state as GoalJudgementState;
		if (state === 'active') return event.kind === 'task' ? state : null;
		return event.kind === 'completion' ? state : null;
	} catch {
		return null;
	}
}

export function finalGoalJudgementState(events: SurfaceEvent[]): GoalJudgementState | null {
	let finalState: GoalJudgementState | null = null;
	for (const event of events) {
		const state = goalJudgementState(event);
		if (state && state !== 'active') finalState = state;
	}
	return finalState;
}

function stringField(
	payload: Record<string, unknown>,
	...keys: string[]
): string | undefined {
	for (const key of keys) {
		const value = payload[key];
		if (typeof value === 'string') return value;
	}
	return undefined;
}

export function surfaceConsoleEvent(event: SurfaceEvent): ConsoleChatEvent {
	let payload: Record<string, unknown>;
	try {
		const parsed = JSON.parse(event.payload_json) as unknown;
		payload =
			typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
				? (parsed as Record<string, unknown>)
				: { value: parsed };
	} catch {
		throw new Error(`Malformed ${event.kind} event at sequence ${event.seq}`);
	}

	const text = stringField(payload, 'text', 'summary');
	const toolName = stringField(payload, 'tool', 'tool_name') ?? null;
	const toolCallId = stringField(payload, 'call_id', 'tool_call_id') ?? null;
	const isError = payload.is_error === true;

	// `llm_delta` audit rows (native.py's _DeltaBuffer, ~150ms/48-char coalesced
	// chunks) and the turn's final `llm_call` reconcile both project to
	// SurfaceEventKind 'text' (surface_events.py's _KIND_MAP) — the kind alone
	// can't tell them apart. The raw payload can: a delta chunk carries only
	// `delta`, never `text`/`summary`. Surface it as a distinct synthetic
	// 'text_delta' type so the caller can APPEND deltas while a turn streams,
	// then REPLACE with the authoritative final text on the real 'text' event
	// — appending both would duplicate the response (the same bug class fixed
	// in atlas-terminal's chat.ts reconcile guard).
	if (event.kind === 'text' && text === undefined && typeof payload.delta === 'string') {
		return { type: 'text_delta', text: payload.delta, content: payload };
	}
	// Provider-call metadata shares the `text` surface kind with actual model
	// output. It is telemetry, not an authoritative empty reconcile. Treating it
	// as text used to close the open delta group and produced fragments such as
	// "ator/mass_calculator files" after every metadata checkpoint.
	if (event.kind === 'text' && text === undefined) {
		return { type: 'telemetry', content: payload };
	}

	if (event.kind === 'error') {
		return {
			type: 'failure',
			error: stringField(payload, 'error', 'message') ?? text ?? 'Agent error',
			tool_name: toolName,
			tool_call_id: toolCallId,
			is_error: true,
			content: payload
		};
	}
	if (event.kind === 'completion') {
		const terminalStatus = payload.status ?? payload.transition ?? payload.state;
		const succeeded = ['succeeded', 'done', 'paused', 'exhausted'].includes(String(terminalStatus));
		return {
			type: 'result',
			content: payload,
			is_error: !succeeded
		};
	}
	if (event.kind === 'tool_call' && !toolName) {
		const statusText =
			typeof payload.transition === 'string'
				? `run ${payload.transition}`
				: typeof payload.privacy_warning === 'string'
					? payload.privacy_warning
					: payload.mock_mode === true
						? 'MOCK MODE run (deterministic, no provider)'
						: typeof payload.runtime === 'string'
							? `runtime ${payload.runtime}`
							: null;
		return statusText
			? { type: 'status', text: statusText, content: payload }
			: { type: 'telemetry', content: payload };
	}
	return {
		type: event.kind,
		text,
		tool_name: toolName,
		tool_call_id: toolCallId,
		input: payload.arguments ?? payload.input ?? payload,
		content: payload,
		is_error: isError
	};
}

export function isRunTerminalEvent(event: ConsoleChatEvent): boolean {
	return event.type === 'result' || (event.type === 'failure' && !event.tool_call_id);
}

export function surfaceEventsForTurn(
	events: SurfaceEvent[],
	turn: { runId: string | null; afterSeq: number; goalMode?: boolean } | null
): SurfaceEvent[] {
	if (!turn?.runId) return [];
	return events.filter(
		(event) => event.seq > turn.afterSeq && (turn.goalMode || event.run_id === turn.runId)
	);
}
