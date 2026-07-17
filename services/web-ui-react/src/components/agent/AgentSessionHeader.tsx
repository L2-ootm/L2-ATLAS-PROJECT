import { Bot, Pause, ShieldCheck, Square, Wifi } from 'lucide-react';
import { useAgentSurface } from '../../context/AgentSurfaceContext';
import { subagentsFromSurfaceEvents } from '../../lib/subagents';
import { AgentConstellation } from './SubagentActivity';

const visibleStates = new Set(['starting', 'active', 'suspended', 'resuming', 'cancelling']);

export default function AgentSessionHeader() {
	const surface = useAgentSurface();
	const { session } = surface;
	if (!session || !visibleStates.has(session.state)) return null;
	const actors = subagentsFromSurfaceEvents(surface.events);

	return (
		<header className="agent-session-header" data-state={session.state}>
			<div className="agent-session-header__identity">
				<Bot size={15} aria-hidden="true" />
				<span className="agent-hud-label">AGENT SESSION</span>
				<span className="agent-state-pill">
					<Wifi size={11} aria-hidden="true" />
					{session.state}
				</span>
				<code>{session.id.slice(0, 8)}</code>
			</div>
			<div className="agent-session-header__context">
				<AgentConstellation actors={actors} />
				<span>{session.workspace.kind === 'project' ? session.workspace.project_id : 'GLOBAL'}</span>
				<span>{session.model.provider}/{session.model.model_id}</span>
				<span><ShieldCheck size={12} aria-hidden="true" /> {session.permission_mode}</span>
			</div>
			<div className="agent-session-header__actions">
				<button
					id="permission-queue-trigger"
					type="button"
					className={surface.approvals.length > 0 ? 'agent-queue-trigger is-pending' : 'agent-queue-trigger'}
					aria-expanded={surface.queueOpen}
					aria-controls="permission-queue"
					onClick={() => surface.setQueueOpen(!surface.queueOpen)}
				>
					PERMISSION QUEUE · {surface.approvals.length}
				</button>
				{session.state === 'suspended' ? (
					<button type="button" className="agent-icon-control" onClick={() => void surface.resume()}>
						<Pause size={14} aria-hidden="true" />
						RESUME
					</button>
				) : (
					<button
						type="button"
						className="agent-icon-control agent-icon-control--danger"
						onClick={() => void surface.cancel()}
						disabled={session.state === 'cancelling'}
					>
						<Square size={13} aria-hidden="true" />
						CANCEL
					</button>
				)}
			</div>
		</header>
	);
}
