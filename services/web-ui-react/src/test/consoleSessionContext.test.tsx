import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { useConsoleSession } from '../context/ConsoleSessionContext';
import { ConsoleSessionProvider } from '../context/ConsoleSessionProvider';

function SessionProbe() {
	const session = useConsoleSession();
	return (
		<>
			<button
				type="button"
				onClick={() => {
					session.setActiveTurn({
						windowId: 'chat-1',
						turnId: 'turn-1',
						runId: 'run-1',
						afterSeq: 12,
						goalMode: false
					});
					session.setMessagesByWindow({
						'chat-1': [
							{
								id: 'turn-1',
								role: 'agent',
								label: 'ATLAS',
								body: 'still running',
								time: '12:00',
								status: 'pending'
							}
						]
					});
				}}
			>
				start turn
			</button>
			<div>{session.activeTurn?.runId ?? 'idle'}</div>
			<div>{session.messagesByWindow['chat-1']?.[0]?.body ?? 'empty'}</div>
		</>
	);
}

function RouteHarness() {
	const [onConsoleRoute, setOnConsoleRoute] = useState(true);
	return (
		<ConsoleSessionProvider>
			<button type="button" onClick={() => setOnConsoleRoute((current) => !current)}>
				navigate
			</button>
			{onConsoleRoute ? <SessionProbe /> : <div>another route</div>}
		</ConsoleSessionProvider>
	);
}

describe('ConsoleSessionProvider', () => {
	it('preserves the live turn and transcript across child-route remounts', () => {
		render(<RouteHarness />);

		fireEvent.click(screen.getByText('start turn'));
		expect(screen.getByText('run-1')).toBeInTheDocument();
		expect(screen.getByText('still running')).toBeInTheDocument();

		fireEvent.click(screen.getByText('navigate'));
		expect(screen.getByText('another route')).toBeInTheDocument();
		fireEvent.click(screen.getByText('navigate'));

		expect(screen.getByText('run-1')).toBeInTheDocument();
		expect(screen.getByText('still running')).toBeInTheDocument();
	});
});
