import { useEffect, useMemo, useState } from 'react';
import {
	Activity,
	AlertTriangle,
	Bot,
	Clock3,
	PanelRightOpen,
	Radio,
	Waypoints,
	X
} from 'lucide-react';
import { surfaceConsoleEvent } from '../../lib/consoleEvents';
import type { SurfaceEvent } from '../../lib/surfaceContracts';
import {
	subagentLifecycleFromSurfaceEvents,
	subagentsFromSurfaceEvents,
	type SubagentActivity
} from '../../lib/subagents';
import { ChatModelRouter } from './ChatModelRouter';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'orphaned']);

function shortId(id: string): string {
	return id.replace(/^actor-/, '').slice(0, 8).toUpperCase();
}

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

interface ActorStreamItem {
	seq: number;
	occurredAt: string;
	phase: string;
	detail: string;
	kind: string;
}

function compact(value: unknown, max = 160): string {
	const text = typeof value === 'string' ? value : JSON.stringify(value ?? '');
	return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function actorStream(events: SurfaceEvent[], actor: SubagentActivity): ActorStreamItem[] {
	const items: ActorStreamItem[] = [];
	for (const event of events) {
		const lifecycle = event.kind === 'task' ? subagentLifecycleFromSurfaceEvents([event], actor.id)[0] : null;
		if (lifecycle) {
			items.push({
				seq: event.seq,
				occurredAt: event.occurred_at,
				phase: lifecycle.activity.phase,
				detail: lifecycle.activity.tool || (TERMINAL.has(lifecycle.activity.phase) ? 'Actor settled' : 'Supervisor lifecycle'),
				kind: 'lifecycle'
			});
			continue;
		}
		if (!actor.childRunId || event.run_id !== actor.childRunId) continue;
		try {
			const projected = surfaceConsoleEvent(event);
			if (projected.type === 'tool_call') {
				items.push({
					seq: event.seq,
					occurredAt: event.occurred_at,
					phase: projected.tool_name || 'tool',
					detail: compact(projected.input),
					kind: 'tool'
				});
			} else if (projected.type === 'reasoning' || projected.type === 'text' || projected.type === 'text_delta') {
				items.push({
					seq: event.seq,
					occurredAt: event.occurred_at,
					phase: projected.type === 'reasoning' ? 'thinking' : 'response',
					detail: compact(projected.text || ''),
					kind: projected.type
				});
			} else if (projected.type === 'failure' || projected.type === 'result') {
				items.push({
					seq: event.seq,
					occurredAt: event.occurred_at,
					phase: projected.type === 'failure' ? 'failed' : 'child complete',
					detail: compact(projected.error || projected.text || projected.content),
					kind: projected.type
				});
			}
		} catch {
			// A malformed child event should not break the actor workspace.
		}
	}
	return items.slice(-80);
}

export function ChatActorWorkspace({
	events,
	busy,
	provider,
	modelId
}: {
	events: SurfaceEvent[];
	busy: boolean;
	provider?: string | null;
	modelId?: string | null;
}) {
	const actors = useMemo(() => subagentsFromSurfaceEvents(events), [events]);
	const active = actors.filter((actor) => !TERMINAL.has(actor.phase));
	const completed = actors.filter((actor) => TERMINAL.has(actor.phase));
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [mobileOpen, setMobileOpen] = useState(false);
	const selected = actors.find((actor) => actor.id === selectedId) ?? null;
	const stream = useMemo(
		() => (selected ? actorStream(events, selected) : []),
		[events, selected]
	);

	useEffect(() => {
		if (!selectedId && !mobileOpen) return;
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				if (selectedId) setSelectedId(null);
				else setMobileOpen(false);
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [mobileOpen, selectedId]);

	return (
		<>
			<button
				type="button"
				className="chat-actor-trigger"
				onClick={() => setMobileOpen(true)}
				aria-label="Open actor workspace"
			>
				<PanelRightOpen size={14} />
				ACTORS {active.length}
			</button>
			{mobileOpen && (
				<button
					type="button"
					className="chat-actor-mobile-backdrop"
					onClick={() => setMobileOpen(false)}
					aria-label="Close actor workspace"
				/>
			)}
			<aside className={`chat-actor-workspace${mobileOpen ? ' is-mobile-open' : ''}`} aria-label="Actor workspace">
				<header className="chat-actor-workspace__header">
					<div>
						<span className="chat-actor-workspace__kicker">ORCHESTRATION</span>
						<strong>Actor workspace</strong>
					</div>
					<span className="chat-actor-workspace__count">{active.length} LIVE</span>
					<button
						type="button"
						className="chat-actor-workspace__mobile-close"
						onClick={() => setMobileOpen(false)}
						aria-label="Close actor workspace"
					>
						<X size={14} />
					</button>
				</header>

				{active.length > 10 && (
					<div className="chat-actor-warning" role="status">
						<AlertTriangle size={13} />
						<span>{active.length} actors are parallel. Under 10 usually keeps context and provider throughput sharper.</span>
					</div>
				)}

				<div className="chat-actor-workspace__scroll">
					{actors.length === 0 && (
						<div className="chat-actor-empty">
							<Waypoints size={20} />
							<strong>No actors in this session</strong>
							<span>Spawned and delegated work will appear here as a live topology.</span>
						</div>
					)}
					<ActorGroup label="ACTIVE" actors={active} onSelect={setSelectedId} />
					<ActorGroup label="RECENT" actors={completed.slice().reverse()} onSelect={setSelectedId} />
				</div>

				<footer className="chat-actor-runtime">
					<ChatModelRouter provider={provider} modelId={modelId} busy={busy} />
				</footer>
			</aside>

			{selected && (
				<div className="chat-actor-detail-layer" role="presentation">
					<button
						type="button"
						className="chat-actor-detail-backdrop"
						onClick={() => setSelectedId(null)}
						aria-label="Close actor details"
					/>
					<section className="chat-actor-detail" role="dialog" aria-modal="true" aria-labelledby="actor-detail-title">
						<header className="chat-actor-detail__header">
							<div>
								<span>ACTOR {shortId(selected.id)}</span>
								<h2 id="actor-detail-title">Live activity stream</h2>
							</div>
							<button type="button" onClick={() => setSelectedId(null)} aria-label="Close actor details" autoFocus>
								<X size={15} />
							</button>
						</header>
						<div className="chat-actor-detail__goal">{selected.goal || 'Delegated task'}</div>
						<div className="chat-actor-detail__facts">
							<span><Bot size={12} /> {selected.model || 'inherited model'}</span>
							<span><Waypoints size={12} /> depth {selected.depth} · {selected.background ? 'detached' : 'joined'}</span>
							<span><Activity size={12} /> {selected.toolCount} tool calls</span>
							{selected.durationSeconds != null && <span><Clock3 size={12} /> {selected.durationSeconds.toFixed(1)}s</span>}
						</div>
						<div className="chat-actor-stream" aria-live="polite">
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
					</section>
				</div>
			)}
		</>
	);
}

function ActorGroup({
	label,
	actors,
	onSelect
}: {
	label: string;
	actors: SubagentActivity[];
	onSelect: (id: string) => void;
}) {
	if (actors.length === 0) return null;
	return (
		<section className="chat-actor-group">
			<div className="chat-actor-group__label"><span>{label}</span><span>{actors.length}</span></div>
			{actors.map((actor) => (
				<button
					key={actor.id}
					type="button"
					className="chat-actor-row"
					data-phase={actor.phase}
					onClick={() => onSelect(actor.id)}
				>
					<span className="chat-actor-row__signal"><Radio size={13} /></span>
					<span className="chat-actor-row__copy">
						<strong>{actor.goal || `Actor ${shortId(actor.id)}`}</strong>
						<small>{actor.tool || actor.model || 'Allocating context'}</small>
					</span>
					<span className="chat-actor-row__phase">{actor.phase}</span>
				</button>
			))}
		</section>
	);
}
