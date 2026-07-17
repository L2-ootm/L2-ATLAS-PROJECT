import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AgentPicker, AGENT_RUNTIME_OPTIONS } from '../components/agent/AgentPicker';

describe('AgentPicker', () => {
	it('lists all three runtimes and reports a selection', () => {
		const onChange = vi.fn();
		render(<AgentPicker value="native" onChange={onChange} />);

		fireEvent.click(screen.getByRole('button', { name: /ATLAS/i }));
		const options = screen.getAllByRole('option');
		expect(options).toHaveLength(3);
		expect(AGENT_RUNTIME_OPTIONS.map((o) => o.value)).toEqual(['native', 'claude_code', 'codex']);

		fireEvent.click(screen.getByRole('option', { name: /CODEX/i }));
		expect(onChange).toHaveBeenCalledWith('codex');
		expect(screen.queryAllByRole('option')).toHaveLength(0);
	});

	it('does not open while disabled', () => {
		render(<AgentPicker value="native" onChange={() => {}} disabled />);
		const trigger = screen.getByRole('button', { name: /ATLAS/i });
		expect(trigger).toBeDisabled();
		fireEvent.click(trigger);
		expect(screen.queryAllByRole('option')).toHaveLength(0);
	});
});
