import {
	createContext,
	useContext,
	type Dispatch,
	type SetStateAction
} from 'react';
import type { AgentRuntime, ConsoleChatEvent } from '../lib/api';

export type LayoutMode = 'tile' | 'free' | 'tabs' | 'bsp';
export type WindowKind = 'chat' | 'audit' | 'tools' | 'context';
export type BindingMode = 'project' | 'folder';

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
	/** Index into `body` where the current open `text_delta` streaming run
	 * started (undefined when no run is open). Lets the eventual `text`
	 * reconcile REPLACE just that run's provisional content with the
	 * authoritative final text instead of appending after it, which would
	 * duplicate the response — see Console.tsx's message-merge effect. */
	streamDeltaStart?: number;
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
	/** Folder/project binding — lifted here (not just page-local state) so it
	 * survives navigating away from and back to Console, and so it can hydrate
	 * from the persisted snapshot the same way windows/messages do. */
	bindingMode: BindingMode;
	setBindingMode: Dispatch<SetStateAction<BindingMode>>;
	folderPath: string;
	setFolderPath: Dispatch<SetStateAction<string>>;
};

export const ConsoleSessionContext = createContext<ConsoleSessionContextValue | null>(null);

export function useConsoleSession(): ConsoleSessionContextValue {
	const value = useContext(ConsoleSessionContext);
	if (!value) throw new Error('useConsoleSession must be used inside ConsoleSessionProvider');
	return value;
}
