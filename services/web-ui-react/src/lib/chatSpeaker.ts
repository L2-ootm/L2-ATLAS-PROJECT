import type { ConsoleMessage } from '../context/ConsoleSessionContext';

/**
 * Who is talking in a transcript line.
 *
 * The chat surface used to have exactly two voices — "the operator" and "the
 * agent" — so a message only needed a `label` string and a left/right
 * alignment. Team runs break that: several named collaborators speak into one
 * transcript, and an operator reading it has to be able to tell them apart at
 * a glance without reading the prose. A speaker is therefore a first-class
 * resolved value (name + kind + a stable accent), not a formatting detail of
 * whichever component happens to render the line.
 */

export type SpeakerKind = 'operator' | 'atlas' | 'delegate' | 'system';

export interface ChatSpeaker {
	/** What the transcript prints before the response. */
	name: string;
	kind: SpeakerKind;
	/** CSS color driving this speaker's glyph, rail and live pulse. */
	accent: string;
	/** Two-character glyph fallback when there is no avatar. */
	initials: string;
}

/** Runtime labels `agentRuntimeLabel` produces — these are ATLAS itself
 * speaking through a provider, not a separate collaborator. */
const PRIMARY_LABELS = new Set(['ATLAS', 'CLAUDE CODE', 'CODEX']);

/**
 * Delegates get a colour from the brand palette rather than a rotated hue, so
 * a five-member team still reads as ATLAS and not as a pie chart. Emerald is
 * reserved for the primary agent and celestial for the operator, so neither
 * appears here — a delegate must never be mistakable for either.
 */
const DELEGATE_ACCENTS = [
	'var(--atlas-violet)',
	'var(--atlas-cyan)',
	'var(--atlas-bronze)',
	'var(--atlas-mythic)'
];

/** FNV-1a — a small, stable, non-cryptographic hash. Stability is the point:
 * the same collaborator must keep the same colour across turns, reloads and
 * sessions, so the mapping cannot depend on arrival order or array index. */
function hash(value: string): number {
	let h = 0x811c9dc5;
	for (let i = 0; i < value.length; i += 1) {
		h ^= value.charCodeAt(i);
		h = Math.imul(h, 0x01000193) >>> 0;
	}
	return h >>> 0;
}

export function delegateAccent(name: string): string {
	return DELEGATE_ACCENTS[hash(name.toLowerCase()) % DELEGATE_ACCENTS.length];
}

function initialsOf(name: string): string {
	const words = name.trim().split(/[\s_\-—–]+/).filter(Boolean);
	if (words.length === 0) return '··';
	if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
	return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export function resolveSpeaker(message: ConsoleMessage): ChatSpeaker {
	if (message.role === 'operator') {
		return { name: 'You', kind: 'operator', accent: 'var(--atlas-celestial)', initials: 'YO' };
	}
	if (message.role === 'system') {
		return { name: message.label, kind: 'system', accent: 'var(--atlas-bronze)', initials: initialsOf(message.label) };
	}
	const name = message.label || 'ATLAS';
	if (PRIMARY_LABELS.has(name.toUpperCase())) {
		return { name, kind: 'atlas', accent: 'var(--atlas-emerald)', initials: initialsOf(name) };
	}
	return { name, kind: 'delegate', accent: delegateAccent(name), initials: initialsOf(name) };
}

/**
 * Consecutive turns from the same speaker print the name once.
 *
 * Repeating an identity that has not changed is noise, and noise is what makes
 * a multi-agent transcript unreadable. Only agent turns group: an operator
 * bubble is a visually distinct object already, and a system receipt is a
 * one-line record that carries its own label.
 */
export function speakerContinues(previous: ConsoleMessage | undefined, current: ConsoleMessage): boolean {
	if (!previous || current.role !== 'agent' || previous.role !== 'agent') return false;
	return previous.label === current.label;
}
