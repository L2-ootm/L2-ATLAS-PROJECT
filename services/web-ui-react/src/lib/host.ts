// Tauri desktop-shell bridge. Uses the injected `window.__TAURI__` global
// (enabled via withGlobalTauri) so the plain browser build needs NO @tauri-apps
// npm dependency. Outside the shell isTauri() is false and the cockpit falls back
// to the copy-command flow.

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

async function invoke<T = string>(cmd: string): Promise<T> {
	const core = tauri()?.core;
	if (!core?.invoke) throw new Error('not running in the ATLAS desktop shell');
	return core.invoke<T>(cmd);
}

export const startGatewayViaShell = (): Promise<string> => invoke<string>('start_gateway');
export const gatewayStatusViaShell = (): Promise<string> => invoke<string>('gateway_status');
export const stopGatewayViaShell = (): Promise<string> => invoke<string>('stop_gateway');
