/**
 * ATLAS's own implementations of the donor's "built-in" slash commands
 * (client-side names hardcoded in src/tui/i18n/slash-command.ts's BUILTIN
 * set: init, review, dream, distill, goal, deep-research). The donor's
 * `GET /command` previously returned an empty BOOTSTRAP_STUB, so none of
 * these were actually invocable — the client already ships descriptions
 * and autocomplete entries for them, but nothing backed `/command.name`.
 *
 * Prompt commands use templates through the existing chat pipeline. The
 * goal/mission aliases are classified separately and re-enter ChatAdapter as
 * raw command input so its exact command grammar remains the only parser.
 */

import {
	type EvidenceAvailability,
	type EvidenceReceipt,
	GatewayClient,
	type SurfaceSession
} from './gateway';

export interface AtlasCommand {
	name: string;
	description: string;
	template: string;
	kind?: 'prompt' | 'mission';
}

export const MISSION_COMMAND_ALIASES = ['goal', 'mission'] as const;
export type MissionCommandAlias = (typeof MISSION_COMMAND_ALIASES)[number];

export type MissionCommand =
	| { alias: MissionCommandAlias; action: 'status' }
	| { alias: MissionCommandAlias; action: 'start'; objective: string };

/** Parse only the two exact long-horizon command aliases. */
export function parseMissionCommand(input: string): MissionCommand | null {
	const match = /^\/(goal|mission)(?:\s+([\s\S]*))?$/.exec(input.trim());
	if (!match) return null;
	const alias = match[1] as MissionCommandAlias;
	const args = (match[2] ?? '').trim();
	if (!args || args === 'status') return { alias, action: 'status' };
	return { alias, action: 'start', objective: args };
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
		description: "start or inspect a stop-condition mission that runs until a judge says it's met",
		template: '$ARGUMENTS',
		kind: 'mission'
	},
	{
		name: 'mission',
		description: 'start or inspect a long-horizon mission with a judged stop condition',
		template: '$ARGUMENTS',
		kind: 'mission'
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

/**
 * Module-contributed commands (module framework): refreshed from the gateway's
 * /v1/commands by handleCommandList, merged after the built-ins. Built-in
 * names can never be shadowed (the gateway filters too — defense in depth).
 */
let MODULE_COMMANDS: AtlasCommand[] = [];

export function setModuleCommands(commands: AtlasCommand[]): void {
	const taken = new Set(ATLAS_COMMANDS.map((c) => c.name));
	MODULE_COMMANDS = commands.filter((c) => !!c.name && !!c.template && !taken.has(c.name));
}

export function allAtlasCommands(): AtlasCommand[] {
	return [...ATLAS_COMMANDS, ...MODULE_COMMANDS];
}

export function findAtlasCommand(name: string): AtlasCommand | undefined {
	return allAtlasCommands().find((c) => c.name === name);
}

export function expandCommandTemplate(template: string, args: string): string {
	const trimmed = args.trim();
	if (template.includes('$ARGUMENTS')) return template.replaceAll('$ARGUMENTS', trimmed);
	return trimmed ? `${template}\n\n${trimmed}` : template;
}

export type EvidenceCommandAction = 'inspect' | 'fetch' | 'export';
export type EvidenceCommandTarget = 'run' | 'change-set' | 'patch' | 'result';

export interface EvidenceCommand {
	action: EvidenceCommandAction;
	target: EvidenceCommandTarget;
	id: string;
}

export interface EvidenceCommandResult {
	availability: EvidenceAvailability;
	evidence_ids: string[];
	next_cursor: string | null;
}

export type TranscriptMode = 'summary' | 'normal' | 'verbose';

export function parseEvidenceCommand(input: string): EvidenceCommand | null {
	const match = /^\/evidence\s+(inspect|fetch|export)\s+(run|change-set|patch|result)\s+(\S+)$/.exec(
		input.trim()
	);
	if (!match) return null;
	return {
		action: match[1] as EvidenceCommandAction,
		target: match[2] as EvidenceCommandTarget,
		id: match[3]!
	};
}

function evidenceOperationLabel(receipt: EvidenceReceipt): string {
	if (receipt.ui_kind !== 'file.change') return 'EVIDENCE';
	switch (receipt.operation.toLowerCase()) {
		case 'create':
			return 'CREATED';
		case 'edit':
			return 'EDITED';
		case 'delete':
			return 'DELETED';
		case 'rename':
			return 'RENAMED';
		default:
			return 'CHANGED';
	}
}

export function formatEvidenceReceipt(
	receipt: EvidenceReceipt,
	mode: TranscriptMode = 'normal'
): string {
	const parts = [
		evidenceOperationLabel(receipt),
		receipt.path || '-',
		`+${receipt.additions}`,
		`-${receipt.deletions}`
	];
	if (mode !== 'summary') {
		parts.push(receipt.actor || '-', `${receipt.duration_ms} ms`);
	}
	parts.push(receipt.evidence_id || '-', receipt.availability);
	if (mode === 'verbose') parts.push(`ui.kind=${receipt.ui_kind || '-'}`);
	return parts.join(' · ');
}

const EVIDENCE_INSPECT_PAGE_SIZE = 100;
const EVIDENCE_FETCH_PREVIEW_BYTES = 16 * 1024;
const EVIDENCE_EXPORT_MAX_BYTES = 256 * 1024 * 1024;

/**
 * Execute an Evidence Plane command without computing diffs in TypeScript.
 * Metadata is cursor-paged by the Rust gateway; content is delivered to the
 * caller chunk-by-chunk so fetch/export never builds an unbounded string.
 */
export async function executeEvidenceCommand(
	gateway: GatewayClient,
	session: SurfaceSession,
	command: EvidenceCommand,
	onChunk: (chunk: string) => void
): Promise<EvidenceCommandResult> {
	if (command.action === 'inspect') {
		if (command.target === 'run') {
			const page = await gateway.runChangeSets(session, command.id, {
				limit: EVIDENCE_INSPECT_PAGE_SIZE
			});
			return {
				availability: page.change_sets.some((item) => item.status !== 'captured')
					? 'partial'
					: 'available',
				evidence_ids: page.change_sets.map((item) => item.id),
				next_cursor: page.next_cursor
			};
		}
		if (command.target === 'change-set') {
			const page = await gateway.changeSetFiles(session, command.id, {
				limit: EVIDENCE_INSPECT_PAGE_SIZE
			});
			const availability =
				page.files.find((item) => item.availability !== 'available')?.availability ?? 'available';
			return {
				availability,
				evidence_ids: page.files.map((item) => item.id),
				next_cursor: page.next_cursor
			};
		}
		throw new Error(`inspect requires run or change-set, got ${command.target}`);
	}

	const maxBytes =
		command.action === 'fetch' ? EVIDENCE_FETCH_PREVIEW_BYTES : EVIDENCE_EXPORT_MAX_BYTES;
	let availability: EvidenceAvailability;
	if (command.target === 'patch') {
		availability = await gateway.streamFileChangePatch(
			session,
			command.id,
			onChunk,
			maxBytes
		);
	} else if (command.target === 'result') {
		availability = await gateway.streamEvidenceResult(
			session,
			command.id,
			onChunk,
			maxBytes
		);
	} else {
		throw new Error(`${command.action} requires patch or result, got ${command.target}`);
	}
	return { availability, evidence_ids: [command.id], next_cursor: null };
}
