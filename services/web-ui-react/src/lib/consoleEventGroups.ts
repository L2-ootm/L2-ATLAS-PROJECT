import type { ConsoleChatEvent } from './api';

export type DisplayConsoleEvent = ConsoleChatEvent & {
	_open?: boolean;
	_key: string;
};

export function isOrchestrationTool(name: string | null | undefined): boolean {
	return ['delegate_task', 'atlas_actor'].includes((name ?? '').toLowerCase());
}

/**
 * Turn the immutable event log into readable display blocks.
 *
 * Deltas remain open across metadata telemetry, reconcile into their final
 * text, and close at a real tool call. This preserves the semantic narration
 * boundary without allowing provider bookkeeping to become visible content.
 */
export function displayConsoleEvents(events: ConsoleChatEvent[]): DisplayConsoleEvent[] {
	const out: DisplayConsoleEvent[] = [];
	let openTextIndex: number | null = null;

	for (let sourceIndex = 0; sourceIndex < events.length; sourceIndex += 1) {
		const event = events[sourceIndex];
		if (event.type === 'telemetry') continue;

		if (event.type === 'text_delta') {
			if (openTextIndex !== null) {
				out[openTextIndex].text = `${out[openTextIndex].text ?? ''}${event.text ?? ''}`;
				continue;
			}
			out.push({ type: 'text', text: event.text ?? '', _open: true, _key: `text-${sourceIndex}` });
			openTextIndex = out.length - 1;
			continue;
		}

		if (event.type === 'text') {
			if (openTextIndex !== null) {
				out[openTextIndex].text = event.text;
				out[openTextIndex]._open = false;
				openTextIndex = null;
				continue;
			}
			out.push({ ...event, _open: false, _key: `text-${sourceIndex}` });
			continue;
		}

		if (event.type === 'tool_call' && openTextIndex !== null) {
			out[openTextIndex]._open = false;
			openTextIndex = null;
		}

		if (event.type === 'status') {
			if (!event.text) continue;
			const last = out[out.length - 1];
			if (last?.type === 'status') {
				last.text = `${last.text ?? ''} · ${event.text}`;
				continue;
			}
		}

		out.push({
			...event,
			_key: event.tool_call_id ? `call-${event.tool_call_id}-${event.type}` : `event-${sourceIndex}`
		});
	}

	return out;
}
