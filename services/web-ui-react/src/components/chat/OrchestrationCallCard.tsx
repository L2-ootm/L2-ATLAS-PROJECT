import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Circle, Network, RadioTower } from 'lucide-react';
import type { ConsoleChatEvent } from '../../lib/api';
import type { SubagentActivity } from '../../lib/subagents';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'orphaned']);

function record(value: unknown): Record<string, unknown> {
	if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
		return value as Record<string, unknown>;
	}
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

function goals(input: unknown): string[] {
	const value = record(input);
	const tasks = Array.isArray(value.tasks) ? value.tasks : [];
	const fromTasks = tasks
		.map((task) => record(task).goal)
		.filter((goal): goal is string => typeof goal === 'string' && goal.trim().length > 0);
	if (fromTasks.length > 0) return fromTasks;
	const direct = value.goal ?? value.task ?? value.prompt;
	return typeof direct === 'string' && direct.trim() ? [direct] : [];
}

function normalized(value: string): string {
	return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

export function OrchestrationCallCard({
	event,
	result,
	actors
}: {
	event: ConsoleChatEvent;
	result?: ConsoleChatEvent;
	actors: SubagentActivity[];
}) {
	const [open, setOpen] = useState(false);
	const plannedGoals = useMemo(() => goals(event.input), [event.input]);
	const relevantActors = useMemo(() => {
		if (plannedGoals.length === 0) return actors;
		const wanted = new Set(plannedGoals.map(normalized));
		return actors.filter((actor) => wanted.has(normalized(actor.goal)));
	}, [actors, plannedGoals]);
	const failed = result?.type === 'failure' || result?.is_error === true || relevantActors.some((actor) => actor.phase === 'failed' || actor.phase === 'orphaned');
	const allActorsTerminal = relevantActors.length > 0 && relevantActors.every((actor) => TERMINAL.has(actor.phase));
	const done = (!!result && !failed) || allActorsTerminal;
	const label = (event.tool_name ?? 'orchestration').toUpperCase();
	const headline = plannedGoals[0] ?? ((event.tool_name ?? '').toLowerCase() === 'atlas_actor' ? 'Durable actor operation' : 'Parallel delegation');
	const Chevron = open ? ChevronDown : ChevronRight;

	return (
		<section className="chat-orchestration-card" data-state={failed ? 'failed' : done ? 'done' : 'running'}>
			<button type="button" className="chat-orchestration-card__header" onClick={() => setOpen((value) => !value)}>
				<span className="chat-orchestration-card__glyph"><Network size={15} /></span>
				<span className="chat-orchestration-card__copy">
					<small>{label} · ACTOR PLANE</small>
					<strong>{headline}</strong>
				</span>
				<span className="chat-orchestration-card__state">
					<Circle size={7} fill="currentColor" stroke="none" />
					{failed ? 'ATTENTION' : done ? 'SETTLED' : 'DISPATCHING'}
				</span>
				<Chevron size={14} />
			</button>
			{open && (
				<div className="chat-orchestration-card__body">
					{plannedGoals.map((goal, index) => (
						<div key={`${goal}-${index}`} className="chat-orchestration-card__goal">
							<RadioTower size={13} />
							<span><small>ACTOR {String(index + 1).padStart(2, '0')}</small>{goal}</span>
						</div>
					))}
					{relevantActors.length > 0 && (
						<div className="chat-orchestration-card__actors">
							{relevantActors.map((actor) => <span key={actor.id} data-phase={actor.phase}>{actor.phase} · {actor.tool || actor.model || actor.id}</span>)}
						</div>
					)}
				</div>
			)}
		</section>
	);
}
