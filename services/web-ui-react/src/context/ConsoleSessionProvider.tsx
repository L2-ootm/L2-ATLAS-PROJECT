import { useState, type ReactNode } from 'react';
import {
	ConsoleSessionContext,
	type ActiveConsoleTurn,
	type ConsoleMessage,
	type ConsoleWindow,
	type LayoutMode
} from './ConsoleSessionContext';
import type { ConsoleChatEvent } from '../lib/api';

const INITIAL_WINDOWS: ConsoleWindow[] = [
	{ id: 'chat-1', kind: 'chat', title: 'atlas.chat', agent: 'native', x: 260, y: 54, w: 540, h: 430 },
	{ id: 'audit-1', kind: 'audit', title: 'audit.stream', x: 840, y: 54, w: 300, h: 210 },
	{ id: 'context-1', kind: 'context', title: 'context.graph', x: 840, y: 282, w: 300, h: 202 },
	{ id: 'tools-1', kind: 'tools', title: 'tool.dock', x: 20, y: 54, w: 220, h: 430 }
];

export function ConsoleSessionProvider({ children }: { children: ReactNode }) {
	const [windows, setWindows] = useState<ConsoleWindow[]>(INITIAL_WINDOWS);
	const [activeWindow, setActiveWindow] = useState('chat-1');
	const [messagesByWindow, setMessagesByWindow] = useState<Record<string, ConsoleMessage[]>>({});
	const [auditEvents, setAuditEvents] = useState<ConsoleChatEvent[]>([]);
	const [draftByWindow, setDraftByWindow] = useState<Record<string, string>>({ 'chat-1': '' });
	const [layout, setLayout] = useState<LayoutMode>('tile');
	const [activeTurn, setActiveTurn] = useState<ActiveConsoleTurn | null>(null);

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
				setActiveTurn
			}}
		>
			{children}
		</ConsoleSessionContext.Provider>
	);
}
