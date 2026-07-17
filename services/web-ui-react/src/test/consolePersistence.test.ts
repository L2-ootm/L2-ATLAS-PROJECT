import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConsoleMessage, ConsoleWindow } from '../context/ConsoleSessionContext';
import {
	addRecentFolder,
	loadConsoleSnapshot,
	loadRecentFolders,
	saveConsoleSnapshot,
	type ConsoleSnapshot
} from '../lib/consolePersistence';
import { setActiveSessionId } from '../lib/sessionCatalog';

const STORAGE_KEY = 'atlas.console.sessions.v2';
const SESSION_ID = 'console-test';

function snapshot(overrides: Partial<ConsoleSnapshot> = {}): ConsoleSnapshot {
	const windows: ConsoleWindow[] = [
		{ id: 'chat-1', kind: 'chat', title: 'atlas.chat', agent: 'native', x: 260, y: 54, w: 540, h: 430 }
	];
	const messages: ConsoleMessage[] = [
		{ id: 'boot-1', role: 'system', label: 'ATLAS', body: 'Console bound to folder: C:\\ws', time: '12:00' },
		{ id: 'turn-1', role: 'agent', label: 'NATIVE', body: 'done', time: '12:01', status: 'succeeded' }
	];
	return {
		windows,
		messagesByWindow: { 'chat-1': messages },
		draftByWindow: { 'chat-1': 'half-typed prompt' },
		layout: 'tile',
		binding: { bindingMode: 'folder', folderPath: 'C:\\ws', projectId: '' },
		...overrides
	};
}

describe('consolePersistence snapshot', () => {
	beforeEach(() => {
		localStorage.clear();
		setActiveSessionId('console', SESSION_ID);
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.runOnlyPendingTimers();
		vi.useRealTimers();
	});

	it('roundtrips a snapshot through the debounced save', () => {
		const source = snapshot();
		saveConsoleSnapshot(source);
		// Trailing debounce: nothing written until the window elapses.
		expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
		vi.advanceTimersByTime(400);

		const restored = loadConsoleSnapshot();
		expect(restored).toEqual(source);
	});

	it('collapses rapid successive saves into one trailing write', () => {
		const setItem = vi.spyOn(Storage.prototype, 'setItem');
		saveConsoleSnapshot(snapshot({ layout: 'tile' }));
		vi.advanceTimersByTime(200);
		saveConsoleSnapshot(snapshot({ layout: 'bsp' }));
		vi.advanceTimersByTime(400);

		expect(setItem).toHaveBeenCalledTimes(1);
		expect(loadConsoleSnapshot()?.layout).toBe('bsp');
	});

	it('returns null on missing data', () => {
		expect(loadConsoleSnapshot()).toBeNull();
	});

	it('returns null on corrupt JSON', () => {
		localStorage.setItem(STORAGE_KEY, '{broken');
		expect(loadConsoleSnapshot()).toBeNull();
	});

	it('returns null on a version mismatch', () => {
		saveConsoleSnapshot(snapshot());
		vi.advanceTimersByTime(400);
		const raw = localStorage.getItem(STORAGE_KEY);
		localStorage.setItem(STORAGE_KEY, String(raw).replace('"version":1', '"version":99'));
		expect(loadConsoleSnapshot()).toBeNull();
	});

	it('returns null when required slices are missing', () => {
		localStorage.setItem(STORAGE_KEY, JSON.stringify({ [SESSION_ID]: { version: 1, windows: [] } }));
		expect(loadConsoleSnapshot()).toBeNull();
	});

	it('normalizes pending messages to a neutral non-pending state on hydrate', () => {
		const pending: ConsoleMessage = {
			id: 'turn-2',
			role: 'agent',
			label: 'NATIVE',
			body: 'streamed halfway',
			time: '12:02',
			status: 'pending',
			events: [{ type: 'text', text: 'streamed halfway' }]
		};
		saveConsoleSnapshot(snapshot({ messagesByWindow: { 'chat-1': [pending] } }));
		vi.advanceTimersByTime(400);

		const restored = loadConsoleSnapshot();
		const message = restored?.messagesByWindow['chat-1']?.[0];
		expect(message).toBeDefined();
		expect(message?.status).toBeUndefined();
		expect(message?.body).toBe('streamed halfway');
		// Non-pending statuses survive untouched.
		saveConsoleSnapshot(snapshot());
		vi.advanceTimersByTime(400);
		expect(loadConsoleSnapshot()?.messagesByWindow['chat-1']?.[1]?.status).toBe('succeeded');
	});
});

describe('consolePersistence recent folders', () => {
	beforeEach(() => {
		localStorage.clear();
	});

	it('keeps a deduped most-recent-first MRU list', () => {
		addRecentFolder('C:\\alpha');
		addRecentFolder('C:\\beta');
		const result = addRecentFolder('C:\\alpha');
		expect(result).toEqual(['C:\\alpha', 'C:\\beta']);
		expect(loadRecentFolders()).toEqual(['C:\\alpha', 'C:\\beta']);
	});

	it('caps the list at eight entries', () => {
		for (let i = 0; i < 10; i += 1) addRecentFolder(`C:\\ws-${i}`);
		const folders = loadRecentFolders();
		expect(folders).toHaveLength(8);
		expect(folders[0]).toBe('C:\\ws-9');
		expect(folders).not.toContain('C:\\ws-0');
		expect(folders).not.toContain('C:\\ws-1');
	});

	it('ignores empty paths and survives corrupt stored data', () => {
		expect(addRecentFolder('   ')).toEqual([]);
		localStorage.setItem('atlas.console.recent-folders.v1', 'not json');
		expect(loadRecentFolders()).toEqual([]);
		expect(addRecentFolder('C:\\fresh')).toEqual(['C:\\fresh']);
	});
});
