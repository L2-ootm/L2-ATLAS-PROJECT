import { beforeEach, describe, expect, it } from 'vitest';
import {
	activeSessionId,
	loadSessionCatalog,
	sessionBinding,
	setActiveSessionId,
	upsertSessionCatalog
} from '../lib/sessionCatalog';

describe('session catalog', () => {
	beforeEach(() => localStorage.clear());

	it('keeps unbound and folder-bound sessions in one surface-neutral catalog', () => {
		upsertSessionCatalog({
			id: 'chat-1',
			surface: 'chat',
			title: 'Unbound research',
			agent: 'native',
			binding: sessionBinding('folder', '', '')
		});
		upsertSessionCatalog({
			id: 'console-1',
			surface: 'console',
			title: 'Fix terminal stream',
			agent: 'native',
			binding: sessionBinding('folder', 'C:\\repo\\atlas', '')
		});

		const catalog = loadSessionCatalog();
		expect(catalog).toHaveLength(2);
		expect(catalog.find((entry) => entry.id === 'chat-1')?.binding.kind).toBe('unbound');
		expect(catalog.find((entry) => entry.id === 'console-1')?.binding).toMatchObject({
			kind: 'folder',
			label: 'atlas',
			root: 'C:\\repo\\atlas'
		});
	});

	it('tracks the active session independently per surface', () => {
		setActiveSessionId('chat', 'chat-1');
		setActiveSessionId('console', 'console-1');
		expect(activeSessionId('chat')).toBe('chat-1');
		expect(activeSessionId('console')).toBe('console-1');
	});
});

