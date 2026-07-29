import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
	filterTranscriptItems,
	resolveToolPresentation,
	type ToolPresentationItem
} from '../lib/toolPresentation';

const items: ToolPresentationItem[] = [
	{ id: 'read', kind: 'file.read', state: 'done' },
	{ id: 'edit', kind: 'file.change', state: 'done' },
	{ id: 'shell', kind: 'shell', state: 'running' },
	{ id: 'failed', kind: 'generic', state: 'failed' }
];

describe('semantic tool presentation registry', () => {
	it('selects semantics from manifest ui.kind and safely falls back for unknown kinds', () => {
		const change = resolveToolPresentation({
			toolName: 'opaque-adapter-name',
			manifest: { ui: { kind: 'file.change' } },
			input: { path: 'src/app.ts' }
		});
		expect(change.kind).toBe('file.change');
		expect(change.summary).toBe('src/app.ts');

		const unknown = resolveToolPresentation({
			toolName: 'future-tool',
			manifest: { ui: { kind: 'future.widget' } },
			input: { value: 42 }
		});
		expect(unknown.kind).toBe('generic');
		render(unknown.renderDetail({ value: 42 }));
		expect(screen.getByText(/"value": 42/)).toBeInTheDocument();
	});

	it('treats Summary, Normal, and Verbose as filters over one registry', () => {
		expect(filterTranscriptItems(items, 'summary').map((item) => item.id)).toEqual([
			'edit',
			'failed'
		]);
		expect(filterTranscriptItems(items, 'normal').map((item) => item.id)).toEqual([
			'edit',
			'shell',
			'failed'
		]);
		expect(filterTranscriptItems(items, 'verbose')).toEqual(items);
	});
});

