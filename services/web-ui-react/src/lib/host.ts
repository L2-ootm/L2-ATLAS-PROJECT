import { GATEWAY } from './api';

// Tauri desktop-shell bridge. Uses the injected `window.__TAURI__` global
// (enabled via withGlobalTauri) so the plain browser build needs NO @tauri-apps
// npm dependency. Outside the shell, folder selection falls back to the local
// loopback gateway so browser-mode ATLAS can still open a native folder dialog.

interface TauriCore {
	invoke: <T = unknown>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
}
interface TauriGlobal {
	core?: TauriCore;
}

function tauri(): TauriGlobal | undefined {
	if (typeof window === 'undefined') return undefined;
	return (window as unknown as { __TAURI__?: TauriGlobal }).__TAURI__;
}

/** True only when running inside the ATLAS Tauri desktop shell. */
export function isTauri(): boolean {
	return !!tauri()?.core?.invoke;
}

async function invoke<T = string>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	const core = tauri()?.core;
	if (!core?.invoke) throw new Error('not running in the ATLAS desktop shell');
	return core.invoke<T>(cmd, args);
}

export const startGatewayViaShell = (): Promise<string> => invoke<string>('start_gateway');
export const gatewayStatusViaShell = (): Promise<string> => invoke<string>('gateway_status');
export const stopGatewayViaShell = (): Promise<string> => invoke<string>('stop_gateway');
export const selectFolderViaShell = (title: string): Promise<string | null> =>
	invoke<string | null>('select_folder', { title });

export async function selectFolder(title: string): Promise<string | null> {
	if (isTauri()) return selectFolderViaShell(title);
	const response = await fetch(`${GATEWAY}/v1/host/select-folder`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ title })
	});
	if (!response.ok) throw new Error(`folder picker failed: ${response.status}`);
	const data = (await response.json()) as { path?: string | null };
	return data.path ?? null;
}

/** Open a folder in the local OS file manager (Explorer/Finder/xdg-open). */
export async function revealFolder(path: string): Promise<void> {
	const response = await fetch(`${GATEWAY}/v1/host/reveal`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ path })
	});
	if (!response.ok) throw new Error(`reveal failed: ${response.status}`);
}