import { Activity, Bot, Clock3, Radio, Waypoints, X } from 'lucide-react';
import { shortActorId, type SubagentActivity, type SubagentStreamItem } from '../../lib/subagents';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'orphaned']);

function eventTime(value: string): string {
	const date = new Date(value);
	return Number.isNaN(date.valueOf())
		? value
		: new Intl.DateTimeFormat(undefined, {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			}).format(date);
}

/**
 * Shared subagent detail dialog — one implementation for every surface
 * (Chat's ChatActorWorkspace, Console's SubagentRail) instead of each
 * inventing its own modal. `stream` is optional: pass an array (even empty)
 * when the surface has a per-step telemetry log to show (Chat); omit it
 * entirely when the surface only has static facts (Console's ConsoleChatEvent
 * carries no seq/timestamp for a step-by-step replay) — the stream section
 * is hidden rather than shown permanently "waiting" for data that will never
 * arrive.
 */
export function SubagentDetailModal({
	actor,
	stream,
	onClose
}: {
	actor: SubagentActivity;
	stream?: SubagentStreamItem[];
	onClose: () => void;
}) {
	return (
		<div className="chat-actor-detail-layer" role="presentation">
			<button
				type="button"
				className="chat-actor-detail-backdrop"
				onClick={onClose}
				aria-label="Close actor details"
			/>
			<section className="chat-actor-detail" role="dialog" aria-modal="true" aria-labelledby="subagent-detail-title">
				<header className="chat-actor-detail__header">
					<div>
						<span>AGENT {shortActorId(actor.id)}</span>
						<h2 id="subagent-detail-title">Live activity</h2>
					</div>
					<button type="button" onClick={onClose} aria-label="Close actor details" autoFocus>
						<X size={15} />
					</button>
				</header>
				<div className="chat-actor-detail__goal">{actor.goal || 'Delegated task'}</div>
				<div className="chat-actor-detail__facts">
					<span><Bot size={12} /> {actor.model || 'inherited model'}</span>
					<span><Waypoints size={12} /> depth {actor.depth} · {actor.background ? 'detached' : 'joined'}</span>
					<span><Activity size={12} /> {actor.toolCount} tool calls</span>
					{actor.durationSeconds != null && <span><Clock3 size={12} /> {actor.durationSeconds.toFixed(1)}s</span>}
				</div>
				<div className="chat-actor-detail__signal" data-phase={actor.phase}>
					<span className="chat-actor-detail__signal-core"><Radio size={16} /></span>
					<div>
						<small>LIVE SIGNAL</small>
						<strong>{actor.tool || (TERMINAL.has(actor.phase) ? 'Actor settled' : 'Awaiting first heartbeat')}</strong>
					</div>
					<em>{actor.phase}</em>
				</div>
				{stream && (
					<div className="chat-actor-stream" aria-live="polite">
						{stream.length === 0 && (
							<div className="chat-actor-stream__empty">Waiting for the first actor telemetry pulse…</div>
						)}
						{stream.map((step) => (
							<div key={step.seq} className="chat-actor-stream__step" data-phase={step.phase} data-kind={step.kind}>
								<span className="chat-actor-stream__signal"><Radio size={12} /></span>
								<div>
									<strong>{step.phase}</strong>
									<span>{step.detail}</span>
								</div>
								<time>{eventTime(step.occurredAt)}</time>
							</div>
						))}
					</div>
				)}
			</section>
		</div>
	);
}
