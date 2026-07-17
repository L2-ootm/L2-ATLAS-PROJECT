// ── Console persistence — localStorage snapshot for reload continuity ───────
// Persists the Console's chat/workspace shape (windows, transcripts, drafts,
// layout, folder/project binding) so a page refresh doesn't discard an
// in-progress operator session. Deliberately excludes `auditEvents` (a
// derived/live projection) and `activeTurn` (a run in flight has no run to
// reconnect to after a reload — see `normalizeMessages` below).

import type { ConsoleMessage, ConsoleWindow, LayoutMode } from '../context/ConsoleSessionContext';
import {
	activeSessionId,
	createSessionId,
	setActiveSessionId
} from './sessionCatalog';

export type ConsoleBindingMode = 'project' | 'folder';

export type ConsoleBindingSnapshot = {
	bindingMode: ConsoleBindingMode;
	folderPath: string;
	/** The `?project=` search-param id, captured only so a bare `/console`
	 * reload can restore project binding even if the URL didn't carry it. */
	projectId: string;
};

export type ConsoleSnapshot = {
	windows: ConsoleWindow[];
	messagesByWindow: Record<string, ConsoleMessage[]>;
	draftByWindow: Record<string, string>;
	layout: LayoutMode;
	binding: ConsoleBindingSnapshot;
};

type StoredConsoleSnapshot = ConsoleSnapshot & { version: number };

const LEGACY_STORAGE_KEY = 'atlas.console.v1';
const SESSIONS_KEY = 'atlas.console.sessions.v2';
const SNAPSHOT_VERSION = 1;
const SAVE_DEBOUNCE_MS = 400;

const RECENT_FOLDERS_KEY = 'atlas.console.recent-folders.v1';
const RECENT_FOLDERS_LIMIT = 8;

const saveTimers = new Map<string, ReturnType<typeof setTimeout>>();

/** A `pending` turn has no run left to reconnect to after a reload — drop the
 * status (and the LIVE badge it drives) but leave whatever text streamed in. */
function stripPendingStatus(message: ConsoleMessage): ConsoleMessage {
	if (message.status !== 'pending') return message;
	const normalized: ConsoleMessage = { ...message };
	delete normalized.status;
	return normalized;
}

function normalizeMessages(
	messagesByWindow: Record<string, ConsoleMessage[]>
): Record<string, ConsoleMessage[]> {
	const next: Record<string, ConsoleMessage[]> = {};
	for (const [windowId, messages] of Object.entries(messagesByWindow)) {
		next[windowId] = Array.isArray(messages) ? messages.map(stripPendingStatus) : [];
	}
	return next;
}

/** Debounced (trailing) write of the console snapshot. Best-effort: storage
 * quota/availability failures are swallowed since persistence is a nicety,
 * not a correctness requirement. */
function loadStoredSessions(): Record<string, StoredConsoleSnapshot> {
	if (typeof window === 'undefined') return {};
	try {
		const parsed = JSON.parse(localStorage.getItem(SESSIONS_KEY) ?? '{}') as unknown;
		return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
			? (parsed as Record<string, StoredConsoleSnapshot>)
			: {};
	} catch {
		return {};
	}
}

export function saveConsoleSnapshot(snapshot: ConsoleSnapshot, sessionId?: string): void {
	if (typeof window === 'undefined') return;
	const id = sessionId ?? activeSessionId('console') ?? createSessionId('console');
	if (!activeSessionId('console')) setActiveSessionId('console', id);
	const priorTimer = saveTimers.get(id);
	if (priorTimer) clearTimeout(priorTimer);
	const timer = setTimeout(() => {
		saveTimers.delete(id);
		try {
			const payload: StoredConsoleSnapshot = { version: SNAPSHOT_VERSION, ...snapshot };
			const sessions = loadStoredSessions();
			sessions[id] = payload;
			window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
		} catch {
			// Storage unavailable, full, or disabled — persistence is best-effort.
		}
	}, SAVE_DEBOUNCE_MS);
	saveTimers.set(id, timer);
}

/** Reads + parses the persisted snapshot. Returns `null` on missing, corrupt,
 * or version-mismatched data so callers fall back to fresh state cleanly. */
export function loadConsoleSession(id: string): ConsoleSnapshot | null {
	if (typeof window === 'undefined') return null;
	try {
		const parsed = loadStoredSessions()[id] as Partial<StoredConsoleSnapshot> | undefined;
		if (!parsed || parsed.version !== SNAPSHOT_VERSION) return null;
		if (
			!Array.isArray(parsed.windows) ||
			typeof parsed.messagesByWindow !== 'object' || parsed.messagesByWindow === null ||
			typeof parsed.draftByWindow !== 'object' || parsed.draftByWindow === null ||
			typeof parsed.layout !== 'string' ||
			typeof parsed.binding !== 'object' || parsed.binding === null
		) {
			return null;
		}
		const binding = parsed.binding;
		return {
			windows: parsed.windows,
			messagesByWindow: normalizeMessages(parsed.messagesByWindow),
			draftByWindow: parsed.draftByWindow,
			layout: parsed.layout as LayoutMode,
			binding: {
				bindingMode: binding.bindingMode === 'project' ? 'project' : 'folder',
				folderPath: typeof binding.folderPath === 'string' ? binding.folderPath : '',
				projectId: typeof binding.projectId === 'string' ? binding.projectId : ''
			}
		};
	} catch {
		return null;
	}
}

export function loadConsoleSnapshot(): ConsoleSnapshot | null {
	const active = activeSessionId('console');
	if (active) {
		const snapshot = loadConsoleSession(active);
		if (snapshot) return snapshot;
	}
	if (typeof window === 'undefined') return null;
	try {
		const raw = window.localStorage.getItem(LEGACY_STORAGE_KEY);
		if (!raw) return null;
		const parsed = JSON.parse(raw) as Partial<StoredConsoleSnapshot> | null;
		if (!parsed || parsed.version !== SNAPSHOT_VERSION) return null;
		if (
			!Array.isArray(parsed.windows) ||
			typeof parsed.messagesByWindow !== 'object' || parsed.messagesByWindow === null ||
			typeof parsed.draftByWindow !== 'object' || parsed.draftByWindow === null ||
			typeof parsed.layout !== 'string' ||
			typeof parsed.binding !== 'object' || parsed.binding === null
		) return null;
		const snapshot: ConsoleSnapshot = {
			windows: parsed.windows,
			messagesByWindow: normalizeMessages(parsed.messagesByWindow),
			draftByWindow: parsed.draftByWindow,
			layout: parsed.layout as LayoutMode,
			binding: {
				bindingMode: parsed.binding.bindingMode === 'project' ? 'project' : 'folder',
				folderPath: typeof parsed.binding.folderPath === 'string' ? parsed.binding.folderPath : '',
				projectId: typeof parsed.binding.projectId === 'string' ? parsed.binding.projectId : ''
			}
		};
		createConsoleSession(snapshot);
		localStorage.removeItem(LEGACY_STORAGE_KEY);
		return snapshot;
	} catch {
		return null;
	}
}

export function createConsoleSession(snapshot: ConsoleSnapshot): string {
	const id = createSessionId('console');
	const sessions = loadStoredSessions();
	sessions[id] = { version: SNAPSHOT_VERSION, ...snapshot };
	try {
		localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
	} catch {
		// Best-effort persistence.
	}
	setActiveSessionId('console', id);
	return id;
}

export function ensureActiveConsoleSession(snapshot: ConsoleSnapshot): string {
	const active = activeSessionId('console');
	if (active && loadConsoleSession(active)) return active;
	return createConsoleSession(snapshot);
}

/** MRU list of bound folder paths (most-recent-first, deduped, capped). Kept
 * in a separate key from the main snapshot since it accumulates across many
 * sessions rather than reflecting only the current one. */
export function loadRecentFolders(): string[] {
	if (typeof window === 'undefined') return [];
	try {
		const raw = window.localStorage.getItem(RECENT_FOLDERS_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw) as unknown;
		if (!Array.isArray(parsed)) return [];
		return parsed.filter((entry): entry is string => typeof entry === 'string').slice(0, RECENT_FOLDERS_LIMIT);
	} catch {
		return [];
	}
}

/** Appends `path` to the MRU list (moving it to the front if already present)
 * and persists the result. Returns the updated list so callers can update
 * their own render state without a second read. */
export function addRecentFolder(path: string): string[] {
	const trimmed = path.trim();
	if (!trimmed) return loadRecentFolders();
	const existing = loadRecentFolders().filter((entry) => entry !== trimmed);
	const next = [trimmed, ...existing].slice(0, RECENT_FOLDERS_LIMIT);
	if (typeof window !== 'undefined') {
		try {
			window.localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(next));
		} catch {
			// Storage unavailable, full, or disabled — persistence is best-effort.
		}
	}
	return next;
}
