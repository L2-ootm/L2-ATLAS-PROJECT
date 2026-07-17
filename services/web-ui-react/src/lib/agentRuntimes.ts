import type { AgentRuntime } from './api';

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
