export const SURFACE_EVENT_KINDS = [
	'text',
	'reasoning',
	'tool_call',
	'tool_result',
	'task',
	'retry',
	'retrieval',
	'approval',
	'error',
	'completion'
] as const;

export type SurfaceEventKind = (typeof SURFACE_EVENT_KINDS)[number];
export type SurfaceSessionState =
	| 'starting'
	| 'active'
	| 'suspended'
	| 'resuming'
	| 'cancelling'
	| 'completed'
	| 'failed'
	| 'reclaimed';

export interface SurfaceSession {
	id: string;
	surface: { kind: string; session_id: string };
	workspace: { kind: 'global' | 'project' | 'directory'; root: string; project_id: string | null };
	agent: string;
	model: { provider: string; model_id: string };
	permission_mode: 'allow' | 'ask' | 'deny';
	state: SurfaceSessionState;
	owner_token: string;
	mission_id: string | null;
	run_id: string | null;
	heartbeat_at?: string;
}

export interface SurfaceEvent {
	session_id: string;
	seq: number;
	kind: SurfaceEventKind;
	run_id: string | null;
	occurred_at: string;
	payload_json: string;
}

export interface SurfaceEventReplay {
	session_id: string;
	after_seq: number;
	events: SurfaceEvent[];
}

export interface PermissionPolicyReceipt {
	decision?: 'allow' | 'ask' | 'deny';
	source?: string;
	rule_id?: string | null;
	hardline?: boolean;
	[key: string]: unknown;
}

export interface SurfaceToolApproval {
	id: string;
	tool_name: string;
	risk_level: string;
	args: string;
	args_normalized: string | null;
	summary: string;
	status: string;
	reason: string | null;
	result: string | null;
	run_id: string;
	surface_session_id: string | null;
	surface_kind: string | null;
	workspace_root: string | null;
	expiry_at: string | null;
	decision: string | null;
	nonce: string | null;
	policy_receipt: string | null;
	requested_at: string;
	decided_at: string | null;
}

function record(value: unknown, label: string): Record<string, unknown> {
	if (typeof value !== 'object' || value === null || Array.isArray(value)) {
		throw new Error(`${label} must be an object`);
	}
	return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
	if (typeof value !== 'string') throw new Error(`${label} must be a string`);
	return value;
}

export function parseSurfaceEvent(value: unknown): SurfaceEvent {
	const item = record(value, 'surface event');
	const kind = text(item.kind, 'surface event kind');
	if (!SURFACE_EVENT_KINDS.includes(kind as SurfaceEventKind)) {
		throw new Error(`unknown surface event kind: ${kind}`);
	}
	if (!Number.isSafeInteger(item.seq) || Number(item.seq) < 0) {
		throw new Error('surface event seq must be a non-negative integer');
	}
	return {
		session_id: text(item.session_id, 'surface event session_id'),
		seq: Number(item.seq),
		kind: kind as SurfaceEventKind,
		run_id: item.run_id === null ? null : text(item.run_id, 'surface event run_id'),
		occurred_at: text(item.occurred_at, 'surface event occurred_at'),
		payload_json: text(item.payload_json, 'surface event payload_json')
	};
}

export function parseSurfaceReplay(value: unknown): SurfaceEventReplay {
	const replay = record(value, 'surface replay');
	if (!Array.isArray(replay.events)) throw new Error('surface replay events must be an array');
	const events = replay.events.map(parseSurfaceEvent);
	for (let index = 1; index < events.length; index += 1) {
		if (events[index].seq <= events[index - 1].seq) {
			throw new Error('surface replay events must be strictly ordered');
		}
	}
	return {
		session_id: text(replay.session_id, 'surface replay session_id'),
		after_seq: Number(replay.after_seq ?? -1),
		events
	};
}

export function parsePolicyReceipt(raw: string | null): PermissionPolicyReceipt | null {
	if (!raw) return null;
	const parsed = JSON.parse(raw) as unknown;
	return record(parsed, 'policy receipt') as PermissionPolicyReceipt;
}
