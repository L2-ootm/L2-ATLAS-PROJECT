import type { AgentRuntime } from './api';

export const AGENT_RUNTIME_OPTIONS: Array<{
	value: AgentRuntime;
	description: string;
}> = [
	{ value: 'native', description: 'ATLAS native runtime — audited, policy-bound' },
	{ value: 'claude_code', description: 'Local Claude Code session — no API key' },
	{ value: 'codex', description: 'Official Codex SDK · local login and runtime' }
];
