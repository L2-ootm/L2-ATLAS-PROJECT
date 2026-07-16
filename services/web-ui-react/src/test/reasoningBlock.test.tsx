import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReasoningBlock } from '../routes/Console';

describe('ReasoningBlock', () => {
	it('renders collapsed by default — label visible, reasoning text hidden', () => {
		render(<ReasoningBlock text="I should check the config file first." />);
		expect(screen.getByText('THINKING')).toBeInTheDocument();
		expect(screen.queryByText(/check the config file/)).not.toBeInTheDocument();
	});

	it('expands on click to reveal the reasoning text, and collapses again', () => {
		render(<ReasoningBlock text="I should check the config file first." />);
		const toggle = screen.getByRole('button');

		fireEvent.click(toggle);
		expect(screen.getByText(/check the config file/)).toBeInTheDocument();

		fireEvent.click(toggle);
		expect(screen.queryByText(/check the config file/)).not.toBeInTheDocument();
	});

	it('renders reasoning content as markdown when expanded', () => {
		render(<ReasoningBlock text="Weighing **two options** here." />);
		fireEvent.click(screen.getByRole('button'));
		expect(screen.getByText('two options').tagName).toBe('STRONG');
	});
});
