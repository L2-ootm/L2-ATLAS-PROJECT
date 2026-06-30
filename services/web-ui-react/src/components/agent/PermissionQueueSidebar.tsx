import { Pin, PinOff, X } from 'lucide-react';
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useAgentSurface } from '../../context/AgentSurfaceContext';
import PermissionQueueItem from './PermissionQueueItem';
import PolicyReceipt from './PolicyReceipt';

function useNarrow(): boolean {
	const [narrow, setNarrow] = useState(() => window.matchMedia?.('(max-width: 1023px)').matches ?? false);
	useEffect(() => {
		const query = window.matchMedia?.('(max-width: 1023px)');
		if (!query) return;
		const update = () => setNarrow(query.matches);
		query.addEventListener('change', update);
		return () => query.removeEventListener('change', update);
	}, []);
	return narrow;
}

export default function PermissionQueueSidebar() {
	const surface = useAgentSurface();
	const heading = useRef<HTMLHeadingElement>(null);
	const narrow = useNarrow();

	useEffect(() => {
		if (!surface.queueOpen) return;
		heading.current?.focus();
		if (narrow) document.getElementById('main-content')?.setAttribute('inert', '');
		return () => {
			document.getElementById('main-content')?.removeAttribute('inert');
			document.getElementById('permission-queue-trigger')?.focus();
		};
	}, [narrow, surface.queueOpen]);

	if (!surface.queueOpen) return null;

	function onKeyDown(event: KeyboardEvent<HTMLElement>) {
		if (event.key === 'Escape') {
			event.preventDefault();
			surface.setQueueOpen(false);
			return;
		}
		if (!narrow || event.key !== 'Tab') return;
		const controls = Array.from(
			event.currentTarget.querySelectorAll<HTMLElement>(
				'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
			)
		);
		if (controls.length === 0) return;
		const first = controls[0];
		const last = controls.at(-1)!;
		if (event.shiftKey && document.activeElement === first) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && document.activeElement === last) {
			event.preventDefault();
			first.focus();
		}
	}

	return (
		<>
			{narrow && <button className="permission-scrim" aria-label="Close permission queue" onClick={() => surface.setQueueOpen(false)} />}
			<aside
				id="permission-queue"
				className={narrow ? 'permission-queue permission-queue--sheet' : 'permission-queue'}
				aria-labelledby="permission-queue-title"
				role={narrow ? 'dialog' : undefined}
				aria-modal={narrow || undefined}
				onKeyDown={onKeyDown}
			>
				<header className="permission-queue__header">
					<div>
						<h2 id="permission-queue-title" ref={heading} tabIndex={-1}>PERMISSION QUEUE</h2>
						<span>{surface.approvals.length} OWNED PENDING</span>
					</div>
					<button type="button" aria-label={surface.pinned ? 'Unpin permission queue' : 'Pin permission queue'} onClick={() => surface.setPinned(!surface.pinned)}>
						{surface.pinned ? <PinOff size={15} /> : <Pin size={15} />}
					</button>
					{narrow && <button type="button" aria-label="Close permission queue" onClick={() => surface.setQueueOpen(false)}><X size={16} /></button>}
				</header>
				<div className="permission-queue__body">
					{surface.error && (
						<div className="permission-error" role="alert">
							GATEWAY UNAVAILABLE · DECISIONS REMAIN FAIL-CLOSED.
						</div>
					)}
					{surface.approvals.length > 0 ? (
						<section aria-labelledby="permission-action-title">
							<h3 id="permission-action-title">ACTION REQUIRED</h3>
							{surface.approvals.map(approval => <PermissionQueueItem key={approval.id} approval={approval} />)}
						</section>
					) : (
						<section className="permission-empty">
							<h3>NO ACTION REQUIRED</h3>
							<p>This Web session has no pending decisions.</p>
							<p>Effective policy · {surface.session?.permission_mode ?? 'ask'}</p>
						</section>
					)}
					{surface.outcomes.length > 0 && (
						<section aria-labelledby="permission-outcome-title">
							<h3 id="permission-outcome-title">RECENT OUTCOMES</h3>
							{surface.outcomes.map(outcome => <PolicyReceipt key={outcome.id} approval={outcome} />)}
						</section>
					)}
				</div>
				<div className="sr-only" aria-live="polite">
					{surface.outcomes[0] ? `${surface.outcomes[0].tool_name} ${surface.outcomes[0].status}` : ''}
				</div>
			</aside>
		</>
	);
}
