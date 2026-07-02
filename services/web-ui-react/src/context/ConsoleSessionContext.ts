import {
	createContext,
	useContext,
	type Dispatch,
	type SetStateAction
} from 'react';
import type { AgentRuntime, ConsoleChatEvent } from '../lib/api';

export type LayoutMode = 'tile' | 'free' | 'tabs' | 'bsp';
export type WindowKind = 'chat' | 'audit' | 'tools' | 'context';

export type ConsoleWindow = {
	id: string;
	kind: WindowKind;
	title: string;
	agent?: AgentRuntime;
	x: number;
	y: number;
	w: number;
	h: number;
};

export type ConsoleMessage = {
	id: string;
	role: 'system' | 'operator' | 'agent';
	label: string;
	body: string;
	time: string;
	status?: 'pending' | 'failed' | 'succeeded';
	events?: ConsoleChatEvent[];
};

export type ActiveConsoleTurn = {
	windowId: string;
	turnId: string;
	runId: string | null;
	afterSeq: number;
};

export type ConsoleSessionContextValue = {
	windows: ConsoleWindow[];
	setWindows: Dispatch<SetStateAction<ConsoleWindow[]>>;
	activeWindow: string;
	setActiveWindow: Dispatch<SetStateAction<string>>;
	messagesByWindow: Record<string, ConsoleMessage[]>;
	setMessagesByWindow: Dispatch<SetStateAction<Record<string, ConsoleMessage[]>>>;
	auditEvents: ConsoleChatEvent[];
	setAuditEvents: Dispatch<SetStateAction<ConsoleChatEvent[]>>;
	draftByWindow: Record<string, string>;
	setDraftByWindow: Dispatch<SetStateAction<Record<string, string>>>;
	layout: LayoutMode;
	setLayout: Dispatch<SetStateAction<LayoutMode>>;
	activeTurn: ActiveConsoleTurn | null;
	setActiveTurn: Dispatch<SetStateAction<ActiveConsoleTurn | null>>;
};

export const ConsoleSessionContext = createContext<ConsoleSessionContextValue | null>(null);

export function useConsoleSession(): ConsoleSessionContextValue {
	const value = useContext(ConsoleSessionContext);
	if (!value) throw new Error('useConsoleSession must be used inside ConsoleSessionProvider');
	return value;
}
