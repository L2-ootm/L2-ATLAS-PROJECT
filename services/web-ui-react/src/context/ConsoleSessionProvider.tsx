import { useState, type ReactNode } from 'react';
import {
	ConsoleSessionContext,
	type ActiveConsoleTurn,
	type BindingMode,
	type ConsoleMessage,
	type ConsoleWindow,
	type LayoutMode
} from './ConsoleSessionContext';
import type { ConsoleChatEvent } from '../lib/api';
import { loadConsoleSnapshot } from '../lib/consolePersistence';

const INITIAL_WINDOWS: ConsoleWindow[] = [
	{ id: 'chat-1', kind: 'chat', title: 'atlas.chat', agent: 'native', x: 260, y: 54, w: 540, h: 430 },
	{ id: 'audit-1', kind: 'audit', title: 'audit.stream', x: 840, y: 54, w: 300, h: 210 },
	{ id: 'context-1', kind: 'context', title: 'context.graph', x: 840, y: 282, w: 300, h: 202 },
	{ id: 'tools-1', kind: 'tools', title: 'tool.dock', x: 20, y: 54, w: 220, h: 430 }
];

export function ConsoleSessionProvider({ children }: { children: ReactNode }) {
	// Read the persisted snapshot exactly once per mount (lazy `useState`
	// initializer — never re-invoked on re-render) and share it across every
	// slice's own lazy initializer below. Using lazy initializers rather than
	// a hydration `useEffect` avoids a first-paint flash of empty state.
	const [initialSnapshot] = useState(loadConsoleSnapshot);

	const [windows, setWindows] = useState<ConsoleWindow[]>(() =>
		initialSnapshot && initialSnapshot.windows.length > 0 ? initialSnapshot.windows : INITIAL_WINDOWS
	);
	const [activeWindow, setActiveWindow] = useState(() => windows[0]?.id ?? 'chat-1');
	const [messagesByWindow, setMessagesByWindow] = useState<Record<string, ConsoleMessage[]>>(
		() => initialSnapshot?.messagesByWindow ?? {}
	);
	// Live/derived — never persisted (see consolePersistence.ts).
	const [auditEvents, setAuditEvents] = useState<ConsoleChatEvent[]>([]);
	const [draftByWindow, setDraftByWindow] = useState<Record<string, string>>(
		() => initialSnapshot?.draftByWindow ?? { 'chat-1': '' }
	);
	const [layout, setLayout] = useState<LayoutMode>(() => initialSnapshot?.layout ?? 'tile');
	// A run in flight has no run to reconnect to after a reload — never persisted.
	const [activeTurn, setActiveTurn] = useState<ActiveConsoleTurn | null>(null);
	const [bindingMode, setBindingMode] = useState<BindingMode>(
		() => initialSnapshot?.binding.bindingMode ?? 'folder'
	);
	const [folderPath, setFolderPath] = useState<string>(() => initialSnapshot?.binding.folderPath ?? '');

	return (
		<ConsoleSessionContext.Provider
			value={{
				windows,
				setWindows,
				activeWindow,
				setActiveWindow,
				messagesByWindow,
				setMessagesByWindow,
				auditEvents,
				setAuditEvents,
				draftByWindow,
				setDraftByWindow,
				layout,
				setLayout,
				activeTurn,
				setActiveTurn,
				bindingMode,
				setBindingMode,
				folderPath,
				setFolderPath
			}}
		>
			{children}
		</ConsoleSessionContext.Provider>
	);
}
