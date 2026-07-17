// ATLAS slash commands — prompt commands are kept in lockstep with the TUI
// command catalog (services/atlas-terminal/src/adapter/commands.ts). Each
// prompt command expands to a prompt executed through the existing
// chat/mission/run pipeline; no dedicated gateway endpoint.
//
// Action commands (kind: 'action') are WebUI-local operator controls — they
// run client-side (session, runtime, binding, navigation) and never become
// model prompts. The TUI has its own local command set; only the prompt
// commands are the cross-surface lockstep contract.

export type AtlasCommandAction =
	| 'help'
	| 'new'
	| 'clear'
	| 'agent'
	| 'bind'
	| 'unbind'
	| 'go';

export interface AtlasCommand {
	name: string;
	description: string;
	template: string;
	kind?: 'prompt' | 'action';
	action?: AtlasCommandAction;
	source?: 'atlas' | 'module';
	module?: string;
	argumentHint?: string;
}

export const ATLAS_COMMANDS: AtlasCommand[] = [
	{
		name: 'init',
		description: 'guided AGENTS.md setup',
		template:
			'Inspect this repository and draft or update AGENTS.md with a guided setup: project overview, ' +
			'build/test/lint commands, coding conventions, and any constraints contributors must follow. ' +
			'Ask only if something is genuinely ambiguous; otherwise write the file directly.'
	},
	{
		name: 'review',
		description: 'review changes [commit|branch|pr], defaults to uncommitted',
		argumentHint: '[commit | branch | PR]',
		template:
			'Review the following change: $ARGUMENTS\n' +
			'If no target was given, review the current uncommitted diff instead. For each affected file, ' +
			'summarize the change, flag defects/risks, and state whether it needs revision before merge.'
	},
	{
		name: 'dream',
		description: 'manually consolidate project memory from memory files and raw trajectory',
		template:
			'Consolidate project memory: read the persisted memory/handoff files and the raw trajectory of ' +
			'this session, then produce or update a compact, deduplicated summary of durable facts, decisions, ' +
			'and open threads. Do not restate ephemeral task details that are already resolved.'
	},
	{
		name: 'distill',
		description: 'find repeated workflows in recent work and package them into skills, subagents, or commands',
		template:
			'Scan recent work in this session and repo history for multi-step workflows that recur. For each ' +
			'pattern used two or more times, propose packaging it as a reusable skill, subagent, or slash ' +
			'command: name it, describe when to invoke it, and draft the initial implementation.'
	},
	{
		name: 'goal',
		description: "start or inspect a stop-condition mission that runs until its judge says it's met",
		argumentHint: '<goal>',
		template: '$ARGUMENTS'
	},
	{
		name: 'mission',
		description: 'alias of /goal for a judged long-horizon mission',
		argumentHint: '<goal>',
		template: '$ARGUMENTS'
	},
	{
		name: 'deep-research',
		description: 'deep multi-source, fact-checked research report (runs the deep-research workflow)',
		argumentHint: '<topic>',
		template:
			'Produce a deep, multi-source, fact-checked research report on: $ARGUMENTS\n' +
			'Cross-reference at least three independent sources for each major claim, note any disagreement ' +
			'or uncertainty explicitly, and cite sources inline.'
	},
	// ── WebUI-local action commands ─────────────────────────────────────────
	{
		name: 'help',
		description: 'list every available command and what it does',
		template: '',
		kind: 'action',
		action: 'help'
	},
	{
		name: 'new',
		description: 'start a new chat session — /new unbound also clears the workspace binding',
		argumentHint: '[unbound]',
		template: '',
		kind: 'action',
		action: 'new'
	},
	{
		name: 'clear',
		description: 'start a fresh session with the same binding (alias of /new)',
		template: '',
		kind: 'action',
		action: 'clear'
	},
	{
		name: 'agent',
		description: 'switch the active runtime for the next turn',
		argumentHint: '<atlas | claude | codex>',
		template: '',
		kind: 'action',
		action: 'agent'
	},
	{
		name: 'bind',
		description: 'open the workspace binding picker (project or folder)',
		template: '',
		kind: 'action',
		action: 'bind'
	},
	{
		name: 'unbind',
		description: 'clear the workspace binding for this session',
		template: '',
		kind: 'action',
		action: 'unbind'
	},
	{
		name: 'go',
		description: 'jump to a cockpit page',
		argumentHint: '<page>',
		template: '',
		kind: 'action',
		action: 'go'
	}
];

for (const command of ATLAS_COMMANDS) {
	command.source = 'atlas';
	if (!command.kind) command.kind = 'prompt';
}

/** Runtime aliases accepted by `/agent`. */
export function parseAgentArgument(raw: string): 'native' | 'claude_code' | 'codex' | null {
	const needle = raw.trim().toLowerCase();
	if (['atlas', 'native'].includes(needle)) return 'native';
	if (['claude', 'claude_code', 'claude-code', 'claudecode'].includes(needle)) return 'claude_code';
	if (needle === 'codex') return 'codex';
	return null;
}

/** Pages reachable through `/go`. Keys are what the operator types. */
export const GO_PAGES: Record<string, string> = {
	dashboard: '/',
	chat: '/chat',
	console: '/console',
	command: '/command',
	missions: '/missions',
	runs: '/runs',
	ledger: '/ledger',
	graph: '/graph',
	codex: '/codex',
	models: '/models',
	integrations: '/integrations',
	projects: '/projects',
	settings: '/settings',
	control: '/control'
};

/** Markdown command index rendered by `/help` into the transcript. */
export function renderCommandHelp(catalog: AtlasCommand[]): string {
	const prompt = catalog.filter((c) => c.kind !== 'action' && c.source !== 'module');
	const action = catalog.filter((c) => c.kind === 'action');
	const module = catalog.filter((c) => c.source === 'module');
	const line = (c: AtlasCommand) =>
		`- \`/${c.name}${c.argumentHint ? ` ${c.argumentHint}` : ''}\` — ${c.description}`;
	const sections = [
		'**Prompt commands** (expand into an agent run)',
		...prompt.map(line),
		'',
		'**Local commands** (act on this cockpit, never sent to the model)',
		...action.map(line)
	];
	if (module.length > 0) {
		sections.push('', '**Module commands**', ...module.map(line));
	}
	sections.push('', `Pages for \`/go\`: ${Object.keys(GO_PAGES).join(', ')}`);
	return sections.join('\n');
}

export function findAtlasCommand(name: string): AtlasCommand | undefined {
	return ATLAS_COMMANDS.find((c) => c.name === name);
}

export function expandCommandTemplate(template: string, args: string): string {
	const trimmed = args.trim();
	if (template.includes('$ARGUMENTS')) return template.replaceAll('$ARGUMENTS', trimmed);
	return trimmed ? `${template}\n\n${trimmed}` : template;
}

export function matchAtlasCommands(catalog: AtlasCommand[], input: string, limit = 8): AtlasCommand[] {
	const needle = input.replace(/^\//, '').split(/\s/, 1)[0].toLowerCase();
	if (!needle) return catalog.slice(0, limit);
	return catalog
		.map((command) => {
			const name = command.name.toLowerCase();
			const description = command.description.toLowerCase();
			const score = name === needle ? 4 : name.startsWith(needle) ? 3 : name.includes(needle) ? 2 : description.includes(needle) ? 1 : 0;
			return { command, score };
		})
		.filter((item) => item.score > 0)
		.sort((a, b) => b.score - a.score || a.command.name.localeCompare(b.command.name))
		.slice(0, limit)
		.map((item) => item.command);
}
