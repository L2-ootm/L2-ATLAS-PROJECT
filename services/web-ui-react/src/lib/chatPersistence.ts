import type { AgentRuntime } from './api';
import {
	activeSessionId,
	createSessionId,
	setActiveSessionId
} from './sessionCatalog';
import type { ConsoleMessage } from '../context/ConsoleSessionContext';

export type ChatBindingMode = 'project' | 'folder';

export interface QueuedChatPrompt {
	id: string;
	text: string;
}

export interface ChatSnapshot {
	messages: ConsoleMessage[];
	draft: string;
	agent: AgentRuntime;
	bindingMode: ChatBindingMode;
	folderPath: string;
	projectId: string;
	queuedPrompts?: QueuedChatPrompt[];
}

const LEGACY_KEY = 'atlas.chatpage.v1';
const SESSIONS_KEY = 'atlas.chat.sessions.v2';
const MAX_STORED_MESSAGES = 150;

function normalize(snapshot: ChatSnapshot): ChatSnapshot {
	return {
		...snapshot,
		queuedPrompts: Array.isArray(snapshot.queuedPrompts)
			? snapshot.queuedPrompts
					.filter((item) => item && typeof item.id === 'string' && typeof item.text === 'string')
					.slice(0, 4)
			: [],
		messages: (snapshot.messages ?? []).slice(-MAX_STORED_MESSAGES).map((message) =>
			message.status === 'pending'
				? {
						...message,
						status: 'failed',
						body: message.body || 'Interrupted — the session ended before this turn completed.'
					}
				: message
		)
	};
}

function loadMap(): Record<string, ChatSnapshot> {
	try {
		const parsed = JSON.parse(localStorage.getItem(SESSIONS_KEY) ?? '{}') as unknown;
		return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
			? (parsed as Record<string, ChatSnapshot>)
			: {};
	} catch {
		return {};
	}
}

function saveMap(map: Record<string, ChatSnapshot>): void {
	try {
		localStorage.setItem(SESSIONS_KEY, JSON.stringify(map));
	} catch {
		// Best-effort persistence.
	}
}

export function emptyChatSnapshot(binding?: Partial<ChatSnapshot>): ChatSnapshot {
	return {
		messages: [],
		draft: '',
		agent: binding?.agent ?? 'native',
		bindingMode: binding?.bindingMode ?? 'folder',
		folderPath: binding?.folderPath ?? '',
		projectId: binding?.projectId ?? '',
		queuedPrompts: binding?.queuedPrompts ?? []
	};
}

export function loadChatSession(id: string): ChatSnapshot | null {
	const snapshot = loadMap()[id];
	return snapshot ? normalize(snapshot) : null;
}

export function saveChatSession(id: string, snapshot: ChatSnapshot): void {
	const map = loadMap();
	map[id] = {
		...snapshot,
		messages: snapshot.messages.slice(-MAX_STORED_MESSAGES)
	};
	saveMap(map);
}

export function createChatSession(snapshot = emptyChatSnapshot()): string {
	const id = createSessionId('chat');
	saveChatSession(id, snapshot);
	setActiveSessionId('chat', id);
	return id;
}

export function loadActiveChatSession(): { id: string; snapshot: ChatSnapshot } {
	const active = activeSessionId('chat');
	if (active) {
		const snapshot = loadChatSession(active);
		if (snapshot) return { id: active, snapshot };
	}
	try {
		const legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) ?? 'null') as ChatSnapshot | null;
		if (legacy) {
			const id = createChatSession(normalize(legacy));
			localStorage.removeItem(LEGACY_KEY);
			return { id, snapshot: normalize(legacy) };
		}
	} catch {
		// Corrupt legacy state falls through to a fresh session.
	}
	const snapshot = emptyChatSnapshot();
	return { id: createChatSession(snapshot), snapshot };
}
