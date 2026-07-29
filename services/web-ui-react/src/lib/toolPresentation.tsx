import type { ReactNode } from 'react';
import type { ToolManifest } from './api';

export type ToolUiKind =
	| 'file.read'
	| 'file.change'
	| 'search'
	| 'shell'
	| 'generic';
export type TranscriptMode = 'summary' | 'normal' | 'verbose';
export type PresentationState = 'running' | 'done' | 'failed';

export interface ToolPresentationItem {
	id: string;
	kind: ToolUiKind;
	state: PresentationState;
}

interface PresentationSpec {
	kind: ToolUiKind;
	level: Exclude<TranscriptMode, 'verbose'> | 'verbose';
	summary: (input: Record<string, unknown>) => string;
	renderDetail: (input: unknown) => ReactNode;
}

export interface ResolvedToolPresentation extends Omit<PresentationSpec, 'summary'> {
	label: string;
	summary: string;
}

const asRecord = (value: unknown): Record<string, unknown> =>
	value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const text = (input: Record<string, unknown>, ...keys: string[]): string => {
	for (const key of keys) {
		if (typeof input[key] === 'string') return input[key] as string;
	}
	return '';
};

const detail = (input: unknown) => (
	<pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
		{JSON.stringify(input ?? {}, null, 2)}
	</pre>
);

export const TOOL_PRESENTATION_REGISTRY: Record<ToolUiKind, PresentationSpec> = {
	'file.read': {
		kind: 'file.read',
		level: 'verbose',
		summary: (input) => text(input, 'file_path', 'path'),
		renderDetail: detail
	},
	'file.change': {
		kind: 'file.change',
		level: 'summary',
		summary: (input) => text(input, 'file_path', 'path'),
		renderDetail: detail
	},
	search: {
		kind: 'search',
		level: 'normal',
		summary: (input) => {
			const query = text(input, 'pattern', 'query');
			const scope = text(input, 'path', 'glob');
			return scope ? `${query} · ${scope}` : query;
		},
		renderDetail: detail
	},
	shell: {
		kind: 'shell',
		level: 'normal',
		summary: (input) => text(input, 'command', 'cmd'),
		renderDetail: detail
	},
	generic: {
		kind: 'generic',
		level: 'normal',
		summary: (input) => {
			const first = Object.values(input)[0];
			return typeof first === 'string' ? first : '';
		},
		renderDetail: detail
	}
};

function knownKind(value: string | undefined): ToolUiKind {
	return value && value in TOOL_PRESENTATION_REGISTRY
		? (value as ToolUiKind)
		: 'generic';
}

export function resolveToolPresentation(input: {
	toolName?: string | null;
	manifest?: Pick<ToolManifest, 'ui' | 'renderer'>;
	input?: unknown;
}): ResolvedToolPresentation {
	const kind = knownKind(input.manifest?.ui?.kind ?? input.manifest?.renderer);
	const spec = TOOL_PRESENTATION_REGISTRY[kind];
	const args = asRecord(input.input);
	return {
		...spec,
		label: input.toolName?.trim() || 'tool',
		summary: spec.summary(args)
	};
}

const MODE_RANK: Record<TranscriptMode, number> = {
	summary: 0,
	normal: 1,
	verbose: 2
};

export function filterTranscriptItems(
	items: ToolPresentationItem[],
	mode: TranscriptMode
): ToolPresentationItem[] {
	return items.filter((item) => {
		if (item.state === 'failed') return true;
		const level = TOOL_PRESENTATION_REGISTRY[item.kind].level;
		return MODE_RANK[level] <= MODE_RANK[mode];
	});
}
