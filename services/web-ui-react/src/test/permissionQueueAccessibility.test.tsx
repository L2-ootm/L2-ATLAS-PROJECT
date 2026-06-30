import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Chrome, approval, session, value } from './agentChrome.test';

describe('permission queue accessibility', () => {
	beforeEach(() => {
		Object.defineProperty(window, 'matchMedia', {
			configurable: true,
			value: vi.fn().mockImplementation(() => ({
				matches: true,
				addEventListener: vi.fn(),
				removeEventListener: vi.fn()
			}))
		});
	});

	it('uses modal semantics, focuses its heading, and closes safely with Escape', () => {
		const setQueueOpen = vi.fn();
		render(
			<Chrome
				state={value({
					session: session(),
					approvals: [approval()],
					queueOpen: true,
					setQueueOpen
				})}
			/>
		);
		const dialog = screen.getByRole('dialog', { name: 'PERMISSION QUEUE' });
		expect(dialog).toHaveAttribute('aria-modal', 'true');
		expect(screen.getByRole('heading', { name: 'PERMISSION QUEUE' })).toHaveFocus();
		fireEvent.keyDown(dialog, { key: 'Escape' });
		expect(setQueueOpen).toHaveBeenCalledWith(false);
	});

	it('exposes named keyboard-operable decisions and a polite outcome region', async () => {
		const decide = vi.fn().mockResolvedValue(undefined);
		const user = userEvent.setup();
		render(
			<Chrome
				state={value({
					session: session(),
					approvals: [approval()],
					outcomes: [approval({ status: 'executed', decided_at: '2026-06-29T00:01:00Z' })],
					queueOpen: true,
					decide
				})}
			/>
		);
		const deny = screen.getByRole('button', { name: 'DENY' });
		deny.focus();
		await user.keyboard('{Enter}');
		expect(decide).toHaveBeenCalledWith(expect.any(Object), 'deny');
		expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent('terminal executed');
	});
});
