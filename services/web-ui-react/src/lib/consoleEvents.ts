import type { ConsoleChatEvent } from './api';
import type { SurfaceEvent } from './surfaceContracts';

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
		const terminalStatus = payload.status ?? payload.transition;
		return {
			type: 'result',
			content: payload,
			is_error: terminalStatus !== 'succeeded'
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
							: 'runtime event';
		return { type: 'status', text: statusText, content: payload };
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
	turn: { runId: string | null; afterSeq: number } | null
): SurfaceEvent[] {
	if (!turn?.runId) return [];
	return events.filter((event) => event.run_id === turn.runId && event.seq > turn.afterSeq);
}
