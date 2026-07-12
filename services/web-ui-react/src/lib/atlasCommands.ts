// ATLAS slash commands — the same six prompt templates the TUI ships
// (services/atlas-terminal/src/adapter/commands.ts). Each command expands to a
// prompt executed through the existing chat/mission/run pipeline; no dedicated
// gateway endpoint. Keep the two files in lockstep: one command set, every
// surface (multi-surface, one runtime).

export interface AtlasCommand {
	name: string;
	description: string;
	template: string;
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
		description: "set a stop-condition goal; runs until a judge says it's met. /goal clear to abort",
		template:
			'Set an explicit stop-condition goal: $ARGUMENTS\n' +
			"Work toward this goal, re-checking after each meaningful step whether it has been met. Stop and " +
			"report as soon as the goal is genuinely satisfied, or if truly blocked."
	},
	{
		name: 'deep-research',
		description: 'deep multi-source, fact-checked research report (runs the deep-research workflow)',
		template:
			'Produce a deep, multi-source, fact-checked research report on: $ARGUMENTS\n' +
			'Cross-reference at least three independent sources for each major claim, note any disagreement ' +
			'or uncertainty explicitly, and cite sources inline.'
	}
];

export function findAtlasCommand(name: string): AtlasCommand | undefined {
	return ATLAS_COMMANDS.find((c) => c.name === name);
}

export function expandCommandTemplate(template: string, args: string): string {
	const trimmed = args.trim();
	if (template.includes('$ARGUMENTS')) return template.replaceAll('$ARGUMENTS', trimmed);
	return trimmed ? `${template}\n\n${trimmed}` : template;
}
