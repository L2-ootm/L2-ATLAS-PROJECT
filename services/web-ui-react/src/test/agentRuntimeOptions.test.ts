import { describe, expect, it } from 'vitest';
import { AGENT_RUNTIME_OPTIONS, filterAgentOptions } from '../lib/agentRuntimes';
import type { ComponentStatus } from '../lib/api';

function component(partial: Partial<ComponentStatus>): ComponentStatus {
	return {
		name: 'claude',
		description: '',
		agent_runtime: 'claude_code',
		pip_requirement: '',
		installed: true,
		cli_present: true,
		...partial
	};
}

describe('filterAgentOptions', () => {
	it('shows everything when the availability report is empty (old gateway)', () => {
		expect(filterAgentOptions([])).toEqual(AGENT_RUNTIME_OPTIONS);
	});

	it('hides runtimes whose component is uninstalled', () => {
		const filtered = filterAgentOptions([
			component({ name: 'claude', agent_runtime: 'claude_code', installed: false }),
			component({ name: 'codex', agent_runtime: 'codex', installed: true })
		]);
		expect(filtered.map((o) => o.value)).toEqual(['native', 'codex']);
	});

	it('never hides the native runtime', () => {
		const filtered = filterAgentOptions([
			component({ name: 'claude', agent_runtime: 'claude_code', installed: false }),
			component({ name: 'codex', agent_runtime: 'codex', installed: false })
		]);
		expect(filtered.map((o) => o.value)).toEqual(['native']);
	});
});
