import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import CommandPalette from '../components/CommandPalette';
import { ATLAS_COMMANDS, expandCommandTemplate, findAtlasCommand } from '../lib/atlasCommands';

function mount(overrides: Partial<Parameters<typeof CommandPalette>[0]> = {}) {
	const onRun = vi.fn();
	const onClose = vi.fn();
	render(<CommandPalette open busy={false} onRun={onRun} onClose={onClose} {...overrides} />);
	return { onRun, onClose };
}

describe('CommandPalette', () => {
	it('lists all six ATLAS commands when the query is empty', () => {
		mount();
		for (const command of ATLAS_COMMANDS) {
			expect(screen.getByText(`/${command.name}`)).toBeInTheDocument();
		}
	});

	it('runs the matched command with $ARGUMENTS expanded on Enter', async () => {
		const { onRun, onClose } = mount();
		await userEvent.type(screen.getByLabelText('Slash command'), 'review HEAD~1{Enter}');
		const template = findAtlasCommand('review')!.template;
		expect(onRun).toHaveBeenCalledWith('/review HEAD~1', expandCommandTemplate(template, 'HEAD~1'));
		expect(onClose).toHaveBeenCalled();
	});

	it('does not execute while the agent is busy', async () => {
		const { onRun } = mount({ busy: true });
		await userEvent.type(screen.getByLabelText('Slash command'), 'init{Enter}');
		expect(onRun).not.toHaveBeenCalled();
		expect(screen.getByText(/AGENT BUSY/)).toBeInTheDocument();
	});

	it('closes on Escape without running anything', async () => {
		const { onRun, onClose } = mount();
		await userEvent.type(screen.getByLabelText('Slash command'), '{Escape}');
		expect(onClose).toHaveBeenCalled();
		expect(onRun).not.toHaveBeenCalled();
	});
});
