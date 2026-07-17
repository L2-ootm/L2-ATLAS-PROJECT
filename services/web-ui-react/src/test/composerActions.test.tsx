import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { QueuedChatComposer } from '../components/chat/QueuedChatComposer';
import { ATLAS_COMMANDS } from '../lib/atlasCommands';

vi.mock('../lib/commandCatalog', () => ({
	loadAtlasCommandCatalog: () => Promise.resolve(ATLAS_COMMANDS)
}));

function mount(overrides: Partial<Parameters<typeof QueuedChatComposer>[0]> = {}) {
	const onSubmit = vi.fn().mockReturnValue(true);
	const onAction = vi.fn().mockReturnValue(true);
	render(
		<QueuedChatComposer
			draft=""
			onDraftPersist={() => undefined}
			queue={[]}
			busy={false}
			agent="native"
			error={null}
			onSubmit={onSubmit}
			onAction={onAction}
			onCancel={() => undefined}
			onPromote={() => undefined}
			onEdit={() => undefined}
			onRemove={() => undefined}
			{...overrides}
		/>
	);
	return { onSubmit, onAction };
}

describe('QueuedChatComposer action commands', () => {
	it('routes /agent codex to onAction instead of submitting a prompt', async () => {
		const { onSubmit, onAction } = mount();
		await userEvent.type(screen.getByRole('textbox'), '/agent codex{Enter}');
		expect(onAction).toHaveBeenCalledTimes(1);
		const [command, args] = onAction.mock.calls[0];
		expect(command.name).toBe('agent');
		expect(args).toBe('codex');
		expect(onSubmit).not.toHaveBeenCalled();
	});

	it('keeps the draft when the action reports failure', async () => {
		const onAction = vi.fn().mockReturnValue(false);
		mount({ onAction });
		const input = screen.getByRole('textbox');
		await userEvent.type(input, '/agent nope{Enter}');
		expect(onAction).toHaveBeenCalled();
		expect(input).toHaveValue('/agent nope');
	});

	it('suggests action commands while typing a slash', async () => {
		mount();
		await userEvent.type(screen.getByRole('textbox'), '/hel');
		expect(await screen.findByText('/help')).toBeInTheDocument();
	});

	it('hides action commands when no onAction handler is provided', async () => {
		const { onSubmit } = mount({ onAction: undefined });
		const input = screen.getByRole('textbox');
		await userEvent.type(input, '/help{Enter}');
		// No action layer: `/help` is not a known command, so it submits as text.
		expect(onSubmit).toHaveBeenCalledWith('/help', '/help');
	});
});
