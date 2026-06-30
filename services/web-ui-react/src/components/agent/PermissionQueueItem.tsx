import { AlertTriangle, ChevronDown, Clock3, ShieldAlert } from 'lucide-react';
import { useState } from 'react';
import { useAgentSurface } from '../../context/AgentSurfaceContext';
import type { ToolApproval } from '../../lib/api';
import { parsePolicyReceipt } from '../../lib/surfaceContracts';

function safeArgs(approval: ToolApproval): string {
	return approval.args_normalized || approval.args || '{}';
}

function isHardline(approval: ToolApproval): boolean {
	try {
		return parsePolicyReceipt(approval.policy_receipt)?.hardline === true;
	} catch {
		return true;
	}
}

export default function PermissionQueueItem({ approval }: { approval: ToolApproval }) {
	const surface = useAgentSurface();
	const [expanded, setExpanded] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const working = approval.status === 'executing';
	const hardline = isHardline(approval);

	async function decide(decision: 'deny' | 'once' | 'session' | 'durable') {
		if (
			decision === 'durable' &&
			!window.confirm('Always allow this exact bounded action in the current policy scope?')
		) {
			return;
		}
		setError(null);
		try {
			await surface.decide(approval, decision);
		} catch {
			setError('DECISION NOT APPLIED · STATE CHANGED. REFRESHED FROM AUTHORITY.');
		}
	}

	return (
		<article className="permission-item" data-risk={approval.risk_level}>
			<div className="permission-item__summary">
				<span className="permission-risk">
					{hardline ? <ShieldAlert size={14} aria-hidden="true" /> : <AlertTriangle size={14} aria-hidden="true" />}
					{approval.risk_level}
				</span>
				<strong>{approval.summary || approval.tool_name}</strong>
				<span className="permission-expiry">
					<Clock3 size={12} aria-hidden="true" />
					{approval.expiry_at ? new Date(approval.expiry_at).toLocaleTimeString() : 'NO TTL'}
				</span>
			</div>
			<dl className="permission-evidence">
				<div><dt>TOOL</dt><dd>{approval.tool_name}</dd></div>
				<div><dt>WORKSPACE</dt><dd>{approval.workspace_root || 'GLOBAL'}</dd></div>
				<div><dt>REQUESTER</dt><dd>{approval.surface_kind || 'agent'} · {approval.run_id}</dd></div>
				<div><dt>SCOPE</dt><dd>{approval.surface_session_id?.slice(0, 8) ?? 'UNOWNED'}</dd></div>
			</dl>
			<button
				type="button"
				className="permission-expand"
				aria-expanded={expanded}
				onClick={() => setExpanded(value => !value)}
			>
				<ChevronDown size={13} aria-hidden="true" />
				{expanded ? 'HIDE EVIDENCE' : 'SHOW EVIDENCE'}
			</button>
			{expanded && <pre className="permission-args">{safeArgs(approval)}</pre>}
			{error && <div className="permission-error" role="alert" tabIndex={-1}>{error}</div>}
			<div className="permission-actions" aria-label={`Decision for ${approval.tool_name}`}>
				<button type="button" onClick={() => void decide('deny')} disabled={working || Boolean(surface.error)}>DENY</button>
				{!hardline && (
					<>
						<button type="button" onClick={() => void decide('once')} disabled={working || Boolean(surface.error)}>ALLOW ONCE</button>
						<button type="button" onClick={() => void decide('session')} disabled={working || Boolean(surface.error)}>ALLOW SESSION</button>
						<button type="button" onClick={() => void decide('durable')} disabled={working || Boolean(surface.error)}>ALLOW SCOPED</button>
					</>
				)}
			</div>
		</article>
	);
}
