import { useEffect, useMemo, useState } from 'react';
import { listComponents, type AgentRuntime, type ComponentStatus } from './api';

/** Runtime catalog driving the agent picker. Order = display order.
 * Lives outside the component file so fast-refresh stays component-only. */
export const AGENT_RUNTIME_OPTIONS: Array<{
	value: AgentRuntime;
	description: string;
}> = [
	{ value: 'native', description: 'ATLAS native runtime — audited, policy-bound' },
	{ value: 'claude_code', description: 'Local Claude Code session — no API key' },
	{ value: 'codex', description: 'Local OpenAI Codex CLI session' }
];

/** Hide runtimes whose SDK component is reported uninstalled. An empty report
 * (old gateway, offline probe) hides nothing — availability is advisory. */
export function filterAgentOptions(
	components: ComponentStatus[]
): typeof AGENT_RUNTIME_OPTIONS {
	const unavailable = new Set(
		components.filter((c) => !c.installed).map((c) => c.agent_runtime)
	);
	return AGENT_RUNTIME_OPTIONS.filter((o) => !unavailable.has(o.value));
}

// Module-level cache: component availability changes only when the operator
// installs/uninstalls an SDK, so one probe per page load is enough.
let componentsCache: ComponentStatus[] | null = null;

/** Invalidate the availability cache (after install/uninstall actions). */
export function invalidateComponentsCache(): void {
	componentsCache = null;
}

/** The agent runtime options currently available on this install. */
export function useAgentRuntimeOptions(): typeof AGENT_RUNTIME_OPTIONS {
	const [components, setComponents] = useState<ComponentStatus[] | null>(componentsCache);
	useEffect(() => {
		if (componentsCache !== null) return;
		let cancelled = false;
		void listComponents().then((c) => {
			componentsCache = c;
			if (!cancelled) setComponents(c);
		});
		return () => {
			cancelled = true;
		};
	}, []);
	return useMemo(() => filterAgentOptions(components ?? []), [components]);
}
