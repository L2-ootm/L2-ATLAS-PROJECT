import type { AgentRuntime } from './api';

export type SessionSurface = 'chat' | 'console';
export type SessionBindingKind = 'unbound' | 'folder' | 'project';

export interface SessionBinding {
	kind: SessionBindingKind;
	label: string;
	root: string | null;
	projectId: string | null;
}

export interface SessionCatalogEntry {
	id: string;
	surface: SessionSurface;
	title: string;
	agent: AgentRuntime;
	binding: SessionBinding;
	createdAt: string;
	updatedAt: string;
}

const CATALOG_KEY = 'atlas.sessions.catalog.v1';
const ACTIVE_KEY_PREFIX = 'atlas.sessions.active.';
const CATALOG_EVENT = 'atlas-session-catalog-change';
const MAX_SESSIONS = 120;

function validEntry(value: unknown): value is SessionCatalogEntry {
	if (!value || typeof value !== 'object') return false;
	const entry = value as Partial<SessionCatalogEntry>;
	return (
		typeof entry.id === 'string' &&
		(entry.surface === 'chat' || entry.surface === 'console') &&
		typeof entry.title === 'string' &&
		typeof entry.createdAt === 'string' &&
		typeof entry.updatedAt === 'string' &&
		!!entry.binding &&
		typeof entry.binding === 'object'
	);
}

function notifyCatalog(): void {
	if (typeof window !== 'undefined') window.dispatchEvent(new Event(CATALOG_EVENT));
}

export function createSessionId(surface: SessionSurface): string {
	const token = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
	return `${surface}-${token}`;
}

export function loadSessionCatalog(): SessionCatalogEntry[] {
	if (typeof window === 'undefined') return [];
	try {
		const parsed = JSON.parse(localStorage.getItem(CATALOG_KEY) ?? '[]') as unknown;
		if (!Array.isArray(parsed)) return [];
		return parsed.filter(validEntry).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
	} catch {
		return [];
	}
}

export function saveSessionCatalog(entries: SessionCatalogEntry[]): void {
	if (typeof window === 'undefined') return;
	try {
		const ordered = [...entries]
			.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
			.slice(0, MAX_SESSIONS);
		localStorage.setItem(CATALOG_KEY, JSON.stringify(ordered));
		notifyCatalog();
	} catch {
		// Catalog persistence is best-effort; active conversations stay usable.
	}
}

export function upsertSessionCatalog(
	entry: Omit<SessionCatalogEntry, 'createdAt' | 'updatedAt'> &
		Partial<Pick<SessionCatalogEntry, 'createdAt' | 'updatedAt'>>
): SessionCatalogEntry {
	const now = new Date().toISOString();
	const entries = loadSessionCatalog();
	const prior = entries.find((item) => item.id === entry.id);
	const next: SessionCatalogEntry = {
		...entry,
		createdAt: entry.createdAt ?? prior?.createdAt ?? now,
		updatedAt: entry.updatedAt ?? now
	};
	saveSessionCatalog([next, ...entries.filter((item) => item.id !== entry.id)]);
	return next;
}

export function removeSessionCatalogEntry(id: string): void {
	saveSessionCatalog(loadSessionCatalog().filter((entry) => entry.id !== id));
}

export function activeSessionId(surface: SessionSurface): string | null {
	if (typeof window === 'undefined') return null;
	return localStorage.getItem(`${ACTIVE_KEY_PREFIX}${surface}`);
}

export function setActiveSessionId(surface: SessionSurface, id: string): void {
	if (typeof window === 'undefined') return;
	localStorage.setItem(`${ACTIVE_KEY_PREFIX}${surface}`, id);
	notifyCatalog();
}

export function subscribeSessionCatalog(listener: () => void): () => void {
	if (typeof window === 'undefined') return () => {};
	const onStorage = (event: StorageEvent) => {
		if (event.key === CATALOG_KEY || event.key?.startsWith(ACTIVE_KEY_PREFIX)) listener();
	};
	window.addEventListener(CATALOG_EVENT, listener);
	window.addEventListener('storage', onStorage);
	return () => {
		window.removeEventListener(CATALOG_EVENT, listener);
		window.removeEventListener('storage', onStorage);
	};
}

export function sessionBinding(
	mode: 'project' | 'folder',
	folderPath: string,
	projectId: string,
	projectName?: string | null,
	projectRoot?: string | null
): SessionBinding {
	if (mode === 'project' && projectId) {
		return {
			kind: 'project',
			label: projectName || projectRoot?.split(/[\\/]/).filter(Boolean).at(-1) || 'PROJECT',
			root: projectRoot || null,
			projectId
		};
	}
	const root = folderPath.trim();
	if (root) {
		return {
			kind: 'folder',
			label: root.split(/[\\/]/).filter(Boolean).at(-1) || root,
			root,
			projectId: null
		};
	}
	return { kind: 'unbound', label: 'UNBOUND', root: null, projectId: null };
}

export function sessionTitleFromText(text: string | undefined, fallback: string): string {
	const normalized = (text ?? '').replace(/\s+/g, ' ').trim();
	if (!normalized) return fallback;
	return normalized.length > 54 ? `${normalized.slice(0, 53)}…` : normalized;
}

