import { ChevronDown, ChevronRight, Circle, GitBranch, Radio, Waypoints } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import type { ConsoleChatEvent } from '../../lib/api';
import { subagentFromConsoleEvent, type SubagentActivity } from '../../lib/subagents';

const terminal = new Set(['completed', 'failed', 'cancelled', 'orphaned']);

export function AgentConstellation({ actors, compact = false }: { actors: SubagentActivity[]; compact?: boolean }) {
	if (actors.length === 0) return null;
	const active = actors.filter((actor) => !terminal.has(actor.phase));
	const visible = actors.slice(-4);
	return (
		<div className={`agent-constellation${compact ? ' is-compact' : ''}`} aria-label={`${active.length} active subagents`}>
			<div className="agent-constellation__glyph" aria-hidden="true">
				<span className="agent-constellation__core" />
				{visible.map((actor, index) => (
					<span key={actor.id} className="agent-constellation__node" data-phase={actor.phase} style={{ '--node-index': index } as CSSProperties} />
				))}
			</div>
			<span className="agent-constellation__label">{active.length > 0 ? `${active.length} ACTIVE` : `${actors.length} COMPLETE`}</span>
		</div>
	);
}

export function SubagentRail({ events }: { events: ConsoleChatEvent[] }) {
	const actors = useMemo(() => {
		const latest = new Map<string, SubagentActivity>();
		for (const event of events) {
			const next = subagentFromConsoleEvent(event);
			if (next) latest.set(next.id, next);
		}
		return [...latest.values()];
	}, [events]);
	if (actors.length === 0) return null;
	return (
		<div className="subagent-rail" data-topo="ai">
			<div className="subagent-rail__spine"><GitBranch size={12} /><span>ORCHESTRATION</span></div>
			{actors.map((actor) => <SubagentCard key={actor.id} actor={actor} />)}
		</div>
	);
}

function SubagentCard({ actor }: { actor: SubagentActivity }) {
	const [open, setOpen] = useState(false);
	const Chevron = open ? ChevronDown : ChevronRight;
	const live = !terminal.has(actor.phase);
	return (
		<article className="subagent-card" data-phase={actor.phase}>
			<button type="button" className="subagent-card__header" onClick={() => setOpen((value) => !value)}>
				<Chevron size={12} />
				<span className="subagent-card__signal">{live ? <Radio size={13} /> : <Circle size={8} />}</span>
				<span className="subagent-card__identity">AGENT {actor.id.slice(0, 8)}</span>
				<span className="subagent-card__goal">{actor.goal || 'Delegated task'}</span>
				<span className="subagent-card__phase">{actor.phase}</span>
			</button>
			{open && (
				<div className="subagent-card__body">
					<span><Waypoints size={11} /> {actor.tool || (live ? 'allocating context' : 'no active tool')}</span>
					<span>{actor.toolCount} tool calls</span>
					<span>{actor.model || 'inherited model'}</span>
					<span>{actor.background ? 'detached' : 'joined'} · depth {actor.depth}</span>
					{actor.durationSeconds != null && <span>{actor.durationSeconds.toFixed(1)}s</span>}
				</div>
			)}
		</article>
	);
}
