import { describe, expect, it } from 'vitest';
import {
	ATLAS_COMMANDS,
	GO_PAGES,
	matchAtlasCommands,
	parseAgentArgument,
	renderCommandHelp
} from '../lib/atlasCommands';

describe('action command catalog', () => {
	it('classifies every command as prompt or action', () => {
		for (const command of ATLAS_COMMANDS) {
			expect(command.kind === 'prompt' || command.kind === 'action').toBe(true);
		}
	});

	it('ships the WebUI-local action set', () => {
		const actions = ATLAS_COMMANDS.filter((c) => c.kind === 'action').map((c) => c.name);
		expect(actions).toEqual(['help', 'new', 'clear', 'agent', 'bind', 'unbind', 'go', 'team', 'export']);
	});

	it('matches action commands through the shared matcher', () => {
		const matches = matchAtlasCommands(ATLAS_COMMANDS, '/age');
		expect(matches[0]?.name).toBe('agent');
	});
});

describe('parseAgentArgument', () => {
	it('maps operator aliases onto runtimes', () => {
		expect(parseAgentArgument('atlas')).toBe('native');
		expect(parseAgentArgument('native')).toBe('native');
		expect(parseAgentArgument('Claude')).toBe('claude_code');
		expect(parseAgentArgument('claude-code')).toBe('claude_code');
		expect(parseAgentArgument('codex')).toBe('codex');
	});

	it('rejects unknown runtimes', () => {
		expect(parseAgentArgument('gpt')).toBeNull();
		expect(parseAgentArgument('')).toBeNull();
	});
});

describe('renderCommandHelp', () => {
	it('lists prompt, local, and module sections with /go pages', () => {
		const help = renderCommandHelp([
			...ATLAS_COMMANDS,
			{ name: 'hello', description: 'module cmd', template: 'x', source: 'module', module: 'example' }
		]);
		expect(help).toContain('**Prompt commands**');
		expect(help).toContain('- `/review');
		expect(help).toContain('**Local commands**');
		expect(help).toContain('- `/agent <atlas | claude | codex>`');
		expect(help).toContain('**Module commands**');
		expect(help).toContain('- `/hello`');
		for (const page of Object.keys(GO_PAGES)) expect(help).toContain(page);
	});
});
