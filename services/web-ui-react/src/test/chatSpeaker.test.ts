import { describe, expect, it } from 'vitest';
import { delegateAccent, resolveSpeaker, speakerContinues } from '../lib/chatSpeaker';
import type { ConsoleMessage } from '../context/ConsoleSessionContext';

const message = (role: ConsoleMessage['role'], label: string): ConsoleMessage => ({
	id: `${role}-${label}`,
	role,
	label,
	body: 'body',
	time: '10:00:00'
});

describe('chat speaker resolution', () => {
	it('marks the built-in runtimes as the primary agent, not as collaborators', () => {
		for (const label of ['ATLAS', 'CLAUDE CODE', 'CODEX']) {
			const speaker = resolveSpeaker(message('agent', label));
			expect(speaker.kind).toBe('atlas');
			expect(speaker.accent).toBe('var(--atlas-emerald)');
		}
	});

	it('treats any other agent label as a named collaborator', () => {
		const speaker = resolveSpeaker(message('agent', 'Precision Reviewer'));
		expect(speaker.kind).toBe('delegate');
		expect(speaker.name).toBe('Precision Reviewer');
		expect(speaker.initials).toBe('PR');
	});

	it('never gives a collaborator the primary or operator accent', () => {
		for (const name of ['Reviewer', 'Planner', 'Scout', 'Archivist', 'Auditor', 'Ops']) {
			const accent = delegateAccent(name);
			expect(accent).not.toBe('var(--atlas-emerald)');
			expect(accent).not.toBe('var(--atlas-celestial)');
		}
	});

	it('keeps a collaborator colour stable across turns and orderings', () => {
		expect(delegateAccent('Precision Reviewer')).toBe(delegateAccent('precision reviewer'));
		expect(delegateAccent('Planner')).toBe(delegateAccent('Planner'));
	});

	it('renders the operator as a fixed first-person identity', () => {
		const speaker = resolveSpeaker(message('operator', 'OPERATOR'));
		expect(speaker).toMatchObject({ name: 'You', kind: 'operator' });
	});

	it('groups only consecutive turns from the same agent', () => {
		const atlas = message('agent', 'ATLAS');
		const other = message('agent', 'Precision Reviewer');
		const operator = message('operator', 'OPERATOR');
		expect(speakerContinues(atlas, atlas)).toBe(true);
		expect(speakerContinues(atlas, other)).toBe(false);
		expect(speakerContinues(operator, atlas)).toBe(false);
		expect(speakerContinues(undefined, atlas)).toBe(false);
	});

	it('does not group operator turns — a bubble is already a distinct object', () => {
		const operator = message('operator', 'OPERATOR');
		expect(speakerContinues(operator, operator)).toBe(false);
	});
});
