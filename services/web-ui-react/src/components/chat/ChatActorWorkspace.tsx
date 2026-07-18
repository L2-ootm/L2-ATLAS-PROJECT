import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, PanelRightOpen, Radio, Waypoints, X } from 'lucide-react';
import { surfaceConsoleEvent } from '../../lib/consoleEvents';
import type { SurfaceEvent } from '../../lib/surfaceContracts';
import {
	shortActorId,
	subagentLifecycleFromSurfaceEvents,
	subagentsFromSurfaceEvents,
	type SubagentActivity,
	type SubagentStreamItem
} from '../../lib/subagents';
import { ChatModelRouter } from './ChatModelRouter';
import { SubagentDetailModal } from '../agent/SubagentDetailModal';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'orphaned']);

type ActorStreamItem = SubagentStreamItem;

interface DispatchRecord {
	callId: string;
	goals: string[];
	done: boolean;
	failed: boolean;
}

function compact(value: unknown, max = 160): string {
	const text = typeof value === 'string' ? value : JSON.stringify(value ?? '');
	return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function record(value: unknown): Record<string, unknown> {
	if (typeof value === 'object' && value !== null && !Array.isArray(value)) return value as Record<string, unknown>;
	if (typeof value === 'string') {
		try {
			const parsed = JSON.parse(value) as unknown;
			return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
				? parsed as Record<string, unknown>
				: {};
		} catch {
			return {};
		}
	}
	return {};
}

function dispatchGoals(input: unknown): string[] {
	const data = record(input);
	const taskGoals = (Array.isArray(data.tasks) ? data.tasks : [])
		.map((task) => record(task).goal)
		.filter((goal): goal is string => typeof goal === 'string' && goal.trim().length > 0);
	if (taskGoals.length > 0) return taskGoals;
	const direct = data.goal ?? data.task ?? data.prompt;
	return typeof direct === 'string' && direct.trim() ? [direct] : [];
}

function normalizedGoal(value: string): string {
	return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

/**
 * A dispatch exists before the first child heartbeat. Synthesize that short
 * allocation phase so the workspace never says "No actors" while the
 * transcript already shows a running delegate_task/atlas_actor call.
 */
function provisionalActors(events: SurfaceEvent[], durable: SubagentActivity[]): SubagentActivity[] {
	const calls = new Map<string, DispatchRecord>();
	for (const event of events) {
		try {
			const projected = surfaceConsoleEvent(event);
			const callId = projected.tool_call_id;
			if (projected.type === 'tool_call' && callId && ['delegate_task', 'atlas_actor'].includes((projected.tool_name ?? '').toLowerCase())) {
				const goals = dispatchGoals(projected.input);
				if (goals.length > 0) calls.set(callId, {
					callId,
					goals,
					done: false,
					failed: false
				});
			} else if ((projected.type === 'tool_result' || projected.type === 'failure') && callId) {
				const call = calls.get(callId);
				if (call) {
					call.done = true;
					call.failed = projected.type === 'failure' || projected.is_error === true;
				}
			}
		} catch {
			// Malformed telemetry must not make the workspace disappear.
		}
	}

	const durableGoals = new Set(durable.map((actor) => normalizedGoal(actor.goal)).filter(Boolean));
	return [...calls.values()].flatMap((call) => call.goals.flatMap((goal, index) => {
		if (durableGoals.has(normalizedGoal(goal))) return [];
		return [{
			id: `dispatch:${call.callId}:${index}`,
			parentId: null,
			phase: call.failed ? 'failed' : call.done ? 'completed' : 'queued',
			goal,
			model: '',
			tool: call.done ? 'Dispatch receipt settled' : 'Allocating actor context',
			toolCount: 0,
			depth: 1,
			background: false,
			durationSeconds: null,
			childRunId: null
		} satisfies SubagentActivity];
	}));
}

function actorStream(events: SurfaceEvent[], actor: SubagentActivity): ActorStreamItem[] {
	const items: ActorStreamItem[] = [];
	const provisionalCallId = actor.id.startsWith('dispatch:') ? actor.id.split(':')[1] : null;
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
		if (provisionalCallId) {
			try {
				const projected = surfaceConsoleEvent(event);
				if (projected.tool_call_id === provisionalCallId && ['tool_call', 'tool_result', 'failure'].includes(projected.type)) {
					items.push({
						seq: event.seq,
						occurredAt: event.occurred_at,
						phase: projected.type === 'tool_call' ? 'dispatching' : projected.type === 'failure' ? 'failed' : 'settled',
						detail: projected.type === 'tool_call' ? actor.goal : compact(projected.error || projected.content),
						kind: projected.type
					});
				}
			} catch {
				// Ignore malformed provisional dispatch telemetry.
			}
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
	const actors = useMemo(() => {
		const durable = subagentsFromSurfaceEvents(events);
		return [...durable, ...provisionalActors(events, durable)];
	}, [events]);
	const active = actors.filter((actor) => !TERMINAL.has(actor.phase));
	const completed = actors.filter((actor) => TERMINAL.has(actor.phase));
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [mobileOpen, setMobileOpen] = useState(false);
	const selected = actors.find((actor) => actor.id === selectedId) ?? null;
	const stream = useMemo(
		() => (selected ? actorStream(events, selected) : []),
		[events, selected]
	);
	const signalActors = active.length > 0 ? active : completed.slice(-8).reverse();

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
					{actors.length > 0 && <ActorSignalField actors={signalActors} events={events} onSelect={setSelectedId} />}
					<ActorGroup label="ACTIVE" actors={active} events={events} onSelect={setSelectedId} />
					<ActorGroup label="RECENT" actors={completed.slice().reverse()} events={events} onSelect={setSelectedId} />
				</div>

				<footer className="chat-actor-runtime">
					<ChatModelRouter provider={provider} modelId={modelId} busy={busy} />
				</footer>
			</aside>

			{selected && (
				<SubagentDetailModal actor={selected} stream={stream} onClose={() => setSelectedId(null)} />
			)}
		</>
	);
}

function latestSignal(events: SurfaceEvent[], actor: SubagentActivity): ActorStreamItem | null {
	const stream = actorStream(events, actor);
	return stream.at(-1) ?? null;
}

function ActorSignalField({
	actors,
	events,
	onSelect
}: {
	actors: SubagentActivity[];
	events: SurfaceEvent[];
	onSelect: (id: string) => void;
}) {
	return (
		<section className="chat-actor-signal-field" aria-label="Actor live signal field">
			<div className="chat-actor-signal-field__head"><span>LIVE SIGNAL FIELD</span><span>{actors.length} NODES</span></div>
			<div className="chat-actor-signal-field__plane">
				<span className="chat-actor-signal-field__orbit" />
				{actors.slice(0, 16).map((actor, index) => {
					const signal = latestSignal(events, actor);
					return (
						<button
							key={`${actor.id}-${signal?.seq ?? actor.phase}`}
							type="button"
							className="chat-actor-signal-node"
							data-phase={actor.phase}
							onClick={() => onSelect(actor.id)}
							title={`${actor.goal || actor.id} · ${signal?.phase || actor.phase}`}
							aria-label={`Inspect signal node ${index + 1}`}
						>
							<span /><small>{String(index + 1).padStart(2, '0')}</small>
						</button>
					);
				})}
			</div>
		</section>
	);
}

function ActorGroup({
	label,
	actors,
	events,
	onSelect
}: {
	label: string;
	actors: SubagentActivity[];
	events: SurfaceEvent[];
	onSelect: (id: string) => void;
}) {
	if (actors.length === 0) return null;
	return (
		<section className="chat-actor-group">
			<div className="chat-actor-group__label"><span>{label}</span><span>{actors.length}</span></div>
			{actors.map((actor) => {
				const signal = latestSignal(events, actor);
				return (
				<button
					key={`${actor.id}-${signal?.seq ?? actor.phase}`}
					type="button"
					className="chat-actor-row"
					data-phase={actor.phase}
					onClick={() => onSelect(actor.id)}
				>
					<span className="chat-actor-row__signal"><Radio size={13} /><i /></span>
					<span className="chat-actor-row__copy">
						<strong>{actor.goal || `Actor ${shortActorId(actor.id)}`}</strong>
						<small>{signal?.phase || actor.tool || actor.model || 'Allocating context'} · {actor.toolCount} calls</small>
					</span>
					<span className="chat-actor-row__phase">{actor.phase}</span>
				</button>
				);
			})}
		</section>
	);
}
