import { GitBranch, Radio } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import type { ConsoleChatEvent } from '../../lib/api';
import { subagentsFromConsoleEvents, type SubagentActivity } from '../../lib/subagents';
import { SubagentDetailModal } from './SubagentDetailModal';

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
	const actors = useMemo(() => subagentsFromConsoleEvents(events), [events]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const selected = actors.find((actor) => actor.id === selectedId) ?? null;
	if (actors.length === 0) return null;
	return (
		<div className="subagent-rail" data-topo="ai">
			<div className="subagent-rail__spine"><GitBranch size={12} /><span>ORCHESTRATION</span></div>
			{actors.map((actor) => (
				<SubagentRow key={actor.id} actor={actor} onSelect={() => setSelectedId(actor.id)} />
			))}
			{selected && <SubagentDetailModal actor={selected} onClose={() => setSelectedId(null)} />}
		</div>
	);
}

/**
 * Same row treatment ChatActorWorkspace's actor list uses (`.chat-actor-row`)
 * so Console's inline rail and Chat's session panel read as one visual
 * language instead of two — this replaced a bespoke expand/collapse
 * accordion card with no live-detail affordance.
 */
function SubagentRow({ actor, onSelect }: { actor: SubagentActivity; onSelect: () => void }) {
	const live = !terminal.has(actor.phase);
	return (
		<button type="button" className="chat-actor-row" data-phase={actor.phase} onClick={onSelect}>
			<span className="chat-actor-row__signal"><Radio size={13} />{live && <i />}</span>
			<span className="chat-actor-row__copy">
				<strong>{actor.goal || `Agent ${actor.id.slice(0, 8)}`}</strong>
				<small>{actor.tool || (live ? 'allocating context' : 'no active tool')} · {actor.toolCount} calls</small>
			</span>
			<span className="chat-actor-row__phase">{actor.phase}</span>
		</button>
	);
}
