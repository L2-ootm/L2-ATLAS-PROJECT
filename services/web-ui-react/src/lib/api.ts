// ATLAS Cockpit — API client targeting Phase 7 gateway
// Base: http://127.0.0.1:8484
import type {
	SurfaceEventReplay,
	SurfaceSession,
	SurfaceToolApproval
} from './surfaceContracts';

export const GATEWAY = 'http://127.0.0.1:8484';

// ── Type definitions (mirror db.rs mission_row / run_row) ─────────────────────

export interface Mission {
	id: string;
	title: string;
	intent: string;
	status: string;
	project: string;
	created_at: string;
	updated_at: string;
	archived_at?: string | null;
	delete_after?: string | null;
}

/** Folder-backed working directory (P3). Mirrors db.rs project_row. */
export interface Project {
	id: string;
	name: string;
	root_path: string;
	created_at: string;
	updated_at: string;
}

/**
 * The operator's current working focus (WP-2 — Command Center). A single row is
 * `active` at a time (the Current Focus). `priorities`/`drivers` are stored as
 * JSON-array strings in SQLite and parsed back to arrays by db.rs focus_row.
 * Mirrors atlas_core.schemas.Focus / db.rs FOCUS_COLS.
 */
export interface Focus {
	id: string;
	title: string;
	framework: string;
	priorities: string[];
	drivers: string[];
	project_id: string | null;
	status: string;
	created_at: string;
	updated_at: string;
}

/** Agent runtime that executes a run: native ATLAS in-process, the operator's
 * local Claude Code session, or the local OpenAI Codex CLI. Mirrors the
 * gateway's `agent` request field / `agent_runtime` response field (P4 —
 * modular agents). */
export type AgentRuntime = 'native' | 'claude_code' | 'codex';

/** Human display label for an agent runtime (e.g. "claude_code" → "CLAUDE CODE"). */
export function agentRuntimeLabel(agent: AgentRuntime): string {
	switch (agent) {
		case 'native':
			return 'ATLAS';
		case 'claude_code':
			return 'CLAUDE CODE';
		case 'codex':
			return 'CODEX';
		default:
			return String(agent).toUpperCase();
	}
}

export interface Run {
	id: string;
	mission_id: string;
	session_id: string | null;
	status: string;
	started_at: string;
	finished_at: string | null;
	summary: string;
	/** Which runtime this run was recorded against (P4). Older gateways omit it. */
	agent_runtime?: AgentRuntime;
}

export interface AuditEvent {
	id: string;
	/** Monotonic rowid cursor — pagination key and stable list identity. */
	cursor: number;
	run_id: string;
	event_type: string;
	/** Structured event payload (audit_events.data JSON column). */
	data: unknown;
	timestamp: string;
	session_id: string | null;
	task_id: string | null;
	tool_call_id: string | null;
	tool_name: string | null;
	duration_ms: number | null;
	policy_result: string | null;
}

export interface WikiPage {
	slug: string;
	title: string;
	/** Present on detail responses; list/search responses omit it. */
	body?: string;
	created_at: string;
	updated_at: string;
}

// ── Internal helpers ─────────────────────────────────────────────────────────

/** Non-2xx gateway response. `status` lets callers branch on specific codes. */
export class ApiError extends Error {
	constructor(
		public readonly status: number,
		message: string,
		public readonly code?: string,
		public readonly remediation?: string,
		public readonly currentRevision?: number
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
	// Only attach a content-type when there is a body — a JSON header on GETs
	// makes every request non-simple and forces a CORS preflight round-trip.
	const headers: HeadersInit = init?.body
		? { 'Content-Type': 'application/json', ...(init?.headers ?? {}) }
		: { ...(init?.headers ?? {}) };
	const response = await fetch(`${GATEWAY}${path}`, { ...init, headers });
	if (!response.ok) {
		const text = await response.text().catch(() => response.statusText);
		let detail:
			| {
					error?: { code?: string; message?: string; remediation?: string };
					current_revision?: number;
			  }
			| undefined;
		try {
			detail = JSON.parse(text) as typeof detail;
		} catch {
			detail = undefined;
		}
		throw new ApiError(
			response.status,
			detail?.error?.message ?? `GATEWAY ERROR ${response.status} — ${path}: ${text}`,
			detail?.error?.code,
			detail?.error?.remediation,
			detail?.current_revision
		);
	}
	return response.json() as Promise<T>;
}

// ── Mission endpoints ─────────────────────────────────────────────────────────

export async function listMissions(limit = 50): Promise<{ missions: Mission[]; count: number }> {
	return apiFetch(`/v1/missions?limit=${limit}`);
}

export async function getMission(id: string): Promise<{ mission: Mission; runs: Run[] }> {
	return apiFetch(`/v1/missions/${encodeURIComponent(id)}`);
}

export async function createMission(
	title: string,
	intent: string,
	project?: string
): Promise<{ mission: Mission; runs: Run[] }> {
	const body: { title: string; intent: string; project?: string } = { title, intent };
	if (project) body.project = project;
	return apiFetch('/v1/missions', {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

export async function archiveMission(
	id: string,
	deleteAfterDays = 30
): Promise<{ mission: Mission; runs: Run[] }> {
	return apiFetch(`/v1/missions/${encodeURIComponent(id)}/archive`, {
		method: 'POST',
		body: JSON.stringify({ delete_after_days: deleteAfterDays })
	});
}

export async function purgeArchivedMissions(): Promise<{ deleted: number }> {
	try {
		return await apiFetch('/v1/missions/purge-archived', { method: 'POST' });
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { deleted: 0 };
		}
		throw err;
	}
}

// ── Project endpoints (P3 — folder-backed working directories) ────────────────

export async function listProjects(limit = 100): Promise<{ projects: Project[]; count: number }> {
	try {
		return await apiFetch<{ projects: Project[]; count: number }>(`/v1/projects?limit=${limit}`);
	} catch (err) {
		// A pre-0005 gateway (no /v1/projects route) or absent DB renders empty.
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { projects: [], count: 0 };
		}
		throw err;
	}
}

// ── VCS context (/v1/vcs — dependency-free git reader in the gateway) ─────────

export interface VcsContext {
	/** False when the directory is not inside a git repository. */
	repo: boolean;
	/** Current branch name; null when detached or not a repo. */
	branch: string | null;
	detached?: boolean;
	/** Short commit sha, present only on a detached HEAD. */
	commit?: string;
}

export async function getVcsContext(path?: string): Promise<VcsContext> {
	const qs = path ? `?path=${encodeURIComponent(path)}` : '';
	return apiFetch<VcsContext>(`/v1/vcs${qs}`);
}

// ── Focus endpoints (WP-2 — Command Center Current Focus) ─────────────────────

export async function listFocus(limit = 50): Promise<{ focus: Focus[]; count: number }> {
	try {
		return await apiFetch<{ focus: Focus[]; count: number }>(`/v1/focus?limit=${limit}`);
	} catch (err) {
		// A pre-0009 gateway (no /v1/focus route) or absent DB renders empty.
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { focus: [], count: 0 };
		}
		throw err;
	}
}

/** The Current Focus, or `null` when none is set / the gateway predates WP-2. */
export async function getCurrentFocus(): Promise<{ focus: Focus | null }> {
	try {
		return await apiFetch<{ focus: Focus | null }>(`/v1/focus/current`);
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { focus: null };
		}
		throw err;
	}
}

export interface CreateFocusInput {
	title: string;
	framework?: string;
	priorities?: string[];
	drivers?: string[];
	project?: string;
}

/** Create the Current Focus (archives any prior active one on the backend). */
export async function createFocus(input: CreateFocusInput): Promise<{ focus: Focus }> {
	return apiFetch(`/v1/focus`, {
		method: 'POST',
		body: JSON.stringify(input)
	});
}

export async function archiveFocus(id: string): Promise<{ archived: boolean; id: string }> {
	return apiFetch(`/v1/focus/${encodeURIComponent(id)}/archive`, { method: 'POST' });
}

// ── Goal hierarchy (loop-engineering slice: goals → tasks + observations) ──────

/** A concrete objective under a Focus. Mirrors atlas_core.schemas.Goal. */
export interface Goal {
	id: string;
	focus_id: string | null;
	parent_goal_id: string | null;
	title: string;
	description: string;
	status: 'open' | 'active' | 'done' | 'archived';
	position: number;
	created_at: string;
	updated_at: string;
}

export interface Task {
	id: string;
	goal_id: string;
	title: string;
	status: 'todo' | 'doing' | 'done';
	position: number;
	created_at: string;
	updated_at: string;
}

export interface Observation {
	id: string;
	goal_id: string | null;
	run_id: string | null;
	body: string;
	source: string;
	created_at: string;
}

/** A goal tree node: a Goal plus its tasks, recent observations, and sub-goals. */
export interface GoalNode extends Goal {
	tasks: Task[];
	observations: Observation[];
	children: GoalNode[];
}

/** The nested goal forest for a focus (goals → children → tasks → observations). */
export async function getFocusTree(focusId: string): Promise<{ tree: GoalNode[] }> {
	try {
		return await apiFetch<{ tree: GoalNode[] }>(`/v1/focus/${encodeURIComponent(focusId)}/tree`);
	} catch (err) {
		// A pre-0010 gateway (no goal model) or absent DB renders an empty tree.
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { tree: [] };
		}
		throw err;
	}
}

export interface CreateGoalInput {
	title: string;
	description?: string;
	focus?: string;
	parent?: string;
	status?: string;
}

export async function createGoal(input: CreateGoalInput): Promise<{ goal: Goal }> {
	return apiFetch(`/v1/goals`, { method: 'POST', body: JSON.stringify(input) });
}

export async function archiveGoal(id: string): Promise<{ archived: boolean; id: string }> {
	return apiFetch(`/v1/goals/${encodeURIComponent(id)}/archive`, { method: 'POST' });
}

export async function createTask(goal: string, title: string): Promise<{ created: boolean; id: string }> {
	return apiFetch(`/v1/tasks`, { method: 'POST', body: JSON.stringify({ goal, title }) });
}

export async function setTaskStatus(
	id: string,
	status: 'todo' | 'doing' | 'done'
): Promise<{ updated: boolean; id: string; status: string }> {
	return apiFetch(`/v1/tasks/${encodeURIComponent(id)}/status`, {
		method: 'POST',
		body: JSON.stringify({ status })
	});
}

export interface CreateObservationInput {
	body: string;
	goal?: string;
	run?: string;
	source?: string;
}

export async function createObservation(input: CreateObservationInput): Promise<{ created: boolean; id: string }> {
	return apiFetch(`/v1/observations`, { method: 'POST', body: JSON.stringify(input) });
}

// ── Operations (WP-6 — premade autonomous operations on goals) ────────────────

/** A built-in operation template surfaced as a cockpit button. */
export interface Operation {
	id: string;
	label: string;
	description: string;
	agent: string;
	risk: string;
}

export async function listOperations(): Promise<{ operations: Operation[] }> {
	try {
		return await apiFetch<{ operations: Operation[] }>(`/v1/operations`);
	} catch (err) {
		// A pre-WP-6 gateway (no /v1/operations route) renders no operations.
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { operations: [] };
		}
		throw err;
	}
}

/** Trigger an operation on a goal → background run. Real execution needs the
 * rebuilt gateway + a configured provider; otherwise the run records + fails. */
export async function runOperation(
	opId: string,
	goalId: string,
	agent?: AgentRuntime
): Promise<{ run: Run; executing: boolean; operation: string }> {
	const body: { goal_id: string; agent?: AgentRuntime } = { goal_id: goalId };
	if (agent) body.agent = agent;
	return apiFetch(`/v1/operations/${encodeURIComponent(opId)}/run`, {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

// ── Console chat endpoint (operator workbench) ──────────────────────────────

export interface ConsoleChatEvent {
	type: string;
	text?: string;
	tool_name?: string | null;
	tool_call_id?: string | null;
	input?: unknown;
	content?: unknown;
	error?: string;
	is_error?: boolean;
	subtype?: string | null;
	num_turns?: number | null;
	total_cost_usd?: number | null;
	usage?: unknown;
}

// ── Shared surface-session contracts (Phase 10.7) ──────────────────────────

export async function createSurfaceSession(body: {
	surface_kind: 'webui';
	surface_id: string;
	workspace_kind: 'global' | 'project';
	project_id?: string;
	agent?: string;
	provider?: string;
	model?: string;
	permission_mode?: 'allow' | 'ask' | 'deny';
}): Promise<SurfaceSession> {
	return apiFetch('/v1/surface-sessions', {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

function surfaceOwnerHeaders(ownerToken: string): HeadersInit {
	if (!ownerToken) throw new Error('surface owner token is required');
	return { 'X-Atlas-Surface-Owner': ownerToken };
}

export async function getSurfaceSession(id: string, ownerToken: string): Promise<SurfaceSession> {
	return apiFetch(`/v1/surface-sessions/${encodeURIComponent(id)}`, {
		headers: surfaceOwnerHeaders(ownerToken)
	});
}

async function mutateSurfaceSession(
	session: Pick<SurfaceSession, 'id' | 'owner_token'>,
	action: 'heartbeat' | 'suspend' | 'resume' | 'cancel' | 'close'
): Promise<SurfaceSession> {
	return apiFetch(`/v1/surface-sessions/${encodeURIComponent(session.id)}/${action}`, {
		method: 'POST',
		body: JSON.stringify({ owner_token: session.owner_token })
	});
}

export const heartbeatSurfaceSession = (session: SurfaceSession) =>
	mutateSurfaceSession(session, 'heartbeat');
export const resumeSurfaceSession = (session: SurfaceSession) =>
	mutateSurfaceSession(session, 'resume');
export const cancelSurfaceSession = (session: SurfaceSession) =>
	mutateSurfaceSession(session, 'cancel');
export const closeSurfaceSession = (session: SurfaceSession) =>
	mutateSurfaceSession(session, 'close');

export async function getSurfaceEvents(
	session: Pick<SurfaceSession, 'id' | 'owner_token'>,
	afterSeq = -1
): Promise<SurfaceEventReplay> {
	return apiFetch(
		`/v1/surface-sessions/${encodeURIComponent(session.id)}/events?after_seq=${afterSeq}`,
		{ headers: surfaceOwnerHeaders(session.owner_token) }
	);
}

// ── Knowledge graph (Graphify view) ─────────────────────────────────────────

export interface GraphNode {
	id: string;
	label: string;
	kind: string;
	group: string;
	size: number;
}

export interface GraphLink {
	source: string;
	target: string;
	kind: string;
}

export type GraphScope = 'atlas' | 'global' | 'projects' | 'obsidian';

export interface GraphData {
	nodes: GraphNode[];
	links: GraphLink[];
	root: string;
	scope?: string;
	error?: string;
	counts: { nodes: number; links: number };
}

// Building the graph rescans markdown on the gateway every call, so we cache
// per scope with a 5-minute TTL. Switching tabs / navigating away and back
// reuses a fresh-enough graph instantly; stale entries re-fetch; REBUILD
// passes `force` to rescan that scope.
const GRAPH_CACHE_TTL_MS = 5 * 60 * 1000;
const graphCache = new Map<GraphScope, { data: GraphData; fetchedAt: number }>();

export function getGraphFetchedAt(scope: GraphScope = 'atlas'): number | null {
	return graphCache.get(scope)?.fetchedAt ?? null;
}

export async function getGraph(scope: GraphScope = 'atlas', force = false): Promise<GraphData> {
	if (!force) {
		const hit = graphCache.get(scope);
		if (hit && Date.now() - hit.fetchedAt < GRAPH_CACHE_TTL_MS) return hit.data;
		if (hit) graphCache.delete(scope); // expired — drop before re-fetch
	}
	const data = await apiFetch<GraphData>(`/v1/graph?scope=${encodeURIComponent(scope)}`);
	graphCache.set(scope, { data, fetchedAt: Date.now() });
	return data;
}

export async function getProject(
	id: string
): Promise<{ project: Project; missions: Mission[] }> {
	return apiFetch(`/v1/projects/${encodeURIComponent(id)}`);
}

/** Create a NEW project folder (mkdir) and register it. */
export async function createProject(
	name: string,
	path: string
): Promise<{ project: Project; missions: Mission[] }> {
	return apiFetch('/v1/projects', {
		method: 'POST',
		body: JSON.stringify({ name, path })
	});
}

/** Register an EXISTING folder on the machine as a project. */
export async function registerProject(
	name: string,
	path: string
): Promise<{ project: Project; missions: Mission[] }> {
	return apiFetch('/v1/projects/register', {
		method: 'POST',
		body: JSON.stringify({ name, path })
	});
}

// ── Module endpoints (Decision 3b — optional activatable modules) ─────────────

/** A block on a schema-driven module page (rendered by ATLAS-owned components —
 * the visual constraint; no module code executes). */
export interface ModulePageBlock {
	kind: string; // 'heading' | 'markdown' | 'metrics' | 'actions' | future kinds
	text?: string;
	items?: Array<{ label: string; value?: string; command?: string }>;
}

export interface ModulePage {
	id: string;
	title: string;
	icon: string;
	blocks: ModulePageBlock[];
}

/** Parsed module.yaml manifest (null for legacy seeded modules). */
export interface ModuleManifest {
	id: string;
	name: string;
	version: string;
	description: string;
	capabilities: {
		commands: Array<{ name: string; description: string; template: string }>;
		pages: ModulePage[];
	};
}

/** An optional, activatable ATLAS module (e.g. cashflow). Mirrors db.rs module_row. */
export interface Module {
	id: string;
	name: string;
	description: string;
	status: 'active' | 'inactive';
	activated_at: string | null;
	version?: string;
	source_path?: string;
	manifest?: ModuleManifest | null;
	missing?: boolean;
}

/** A slash command contributed by an active manifest module. */
export interface ModuleCommand {
	name: string;
	description: string;
	template: string;
	module: string;
}

/** Module-contributed slash commands (merged with the built-in catalog by the
 * palette and slash surfaces). Pre-module gateways render empty. */
export async function listModuleCommands(): Promise<ModuleCommand[]> {
	try {
		const out = await apiFetch<{ commands: ModuleCommand[]; count: number }>('/v1/commands');
		return out.commands ?? [];
	} catch {
		return [];
	}
}

/** List optional modules. A pre-0007 gateway (no route/table) renders empty. */
export async function listModules(): Promise<{ modules: Module[]; count: number }> {
	try {
		return await apiFetch<{ modules: Module[]; count: number }>('/v1/modules');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { modules: [], count: 0 };
		}
		throw err;
	}
}

/** Activate or deactivate a module; returns the updated row. */
export async function setModuleActive(id: string, active: boolean): Promise<{ module: Module }> {
	const action = active ? 'activate' : 'deactivate';
	return apiFetch(`/v1/modules/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
}

/** Cashflow module process state (its own Next.js process on :3000). */
export interface CashflowStatus {
	running: boolean;
	backend: string;
}

export async function cashflowStatus(): Promise<CashflowStatus> {
	try {
		return await apiFetch<CashflowStatus>('/v1/cashflow/status');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { running: false, backend: 'local' };
		}
		throw err;
	}
}

/** Start the cashflow app against the chosen DB backend. */
export async function cashflowStart(backend: 'local' | 'supabase'): Promise<{ message: string }> {
	return apiFetch('/v1/cashflow/start', { method: 'POST', body: JSON.stringify({ backend }) });
}

export async function cashflowStop(): Promise<{ message: string }> {
	return apiFetch('/v1/cashflow/stop', { method: 'POST' });
}

/** Sync the model registry against the live sidecar /models list. */
export async function modelsRefresh(): Promise<{ message: string }> {
	return apiFetch('/v1/models/refresh', { method: 'POST' });
}

// ── FreeLLMAPI sidecar control (D-015 external checkout) ─────────────────────

export interface FreellmapiStatus {
	running: boolean;
	base_url: string;
	dir: string | null;
	installed: boolean;
	api_key?: string | null;
	remediation: string | null;
}

export async function freellmapiStatus(): Promise<FreellmapiStatus> {
	try {
		return await apiFetch<FreellmapiStatus>('/v1/freellmapi/status');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { running: false, base_url: '', dir: null, installed: false, remediation: null };
		}
		throw err;
	}
}

export async function freellmapiStart(): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/v1/freellmapi/start', { method: 'POST' });
}

export async function freellmapiStop(): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/v1/freellmapi/stop', { method: 'POST' });
}

export interface CashflowClient {
	id: string;
	name: string;
	service: string;
	monthlyPayment: number;
	startDate: string;
	contractMonths: number;
	active: boolean;
	phone: string | null;
	notes: string;
}

export interface CashflowInvoice {
	id: string;
	clientName: string;
	description: string;
	amount: number;
	issueDate: string;
	dueDate: string;
	paidDate: string | null;
	status: string;
}

export interface CashflowExpense {
	id: string;
	clientId: string | null;
	category: string;
	description: string;
	amount: number;
	date: string;
	recurring: boolean;
}

export interface CashflowSummary {
	available: boolean;
	db_path: string;
	metrics: {
		active_clients: number;
		monthly_revenue: number;
		monthly_expenses: number;
		profit: number;
		outstanding: number;
		overdue_invoices: number;
		due_soon_invoices: number;
	};
	clients: CashflowClient[];
	invoices: CashflowInvoice[];
	expenses: CashflowExpense[];
}

export async function cashflowSummary(): Promise<CashflowSummary> {
	try {
		return await apiFetch<CashflowSummary>('/v1/cashflow/summary');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return {
				available: false,
				db_path: '',
				metrics: {
					active_clients: 0,
					monthly_revenue: 0,
					monthly_expenses: 0,
					profit: 0,
					outstanding: 0,
					overdue_invoices: 0,
					due_soon_invoices: 0
				},
				clients: [],
				invoices: [],
				expenses: []
			};
		}
		throw err;
	}
}

// ── Run endpoints ────────────────────────────────────────────────────────────

/**
 * Trigger a mission run. `agent` selects the runtime the gateway records the run
 * against ("native" default | "claude_code"); it is sent in the JSON body only
 * when provided so a pre-P4 gateway still accepts the bodyless request.
 *
 * When `execute` is true the gateway spawns a *detached* `atlas run exec` so the
 * run executes in the background (the autonomous loop) and the call returns the
 * run_id immediately. Real background execution requires the rebuilt gateway; an
 * old binary ignores `execute` and records the run only. The body carries
 * `execute` only when true to stay compatible with pre-WP-1 gateways.
 */
export interface StartRunOptions {
	goalMode?: boolean;
	judgeModel?: string;
	maxRuns?: number;
}

export async function startRun(
	missionId: string,
	agent?: AgentRuntime,
	execute?: boolean,
	surfaceSessionId?: string,
	options?: StartRunOptions
): Promise<{ run: Run; executing?: boolean }> {
	const init: RequestInit = { method: 'POST' };
	const body: {
		agent?: AgentRuntime;
		execute?: boolean;
		surface_session_id?: string;
		goal_mode?: boolean;
		judge_model?: string;
		max_runs?: number;
	} = {};
	if (agent) body.agent = agent;
	if (execute) body.execute = true;
	if (surfaceSessionId) body.surface_session_id = surfaceSessionId;
	if (options?.goalMode !== undefined) body.goal_mode = options.goalMode;
	if (options?.judgeModel !== undefined) body.judge_model = options.judgeModel;
	if (options?.maxRuns !== undefined) body.max_runs = options.maxRuns;
	if (Object.keys(body).length > 0) init.body = JSON.stringify(body);
	return apiFetch(`/v1/missions/${encodeURIComponent(missionId)}/run`, init);
}

/**
 * Retry a failed/cancelled mission. The gateway reopens the mission in place
 * (`failed|cancelled -> pending`) and starts a fresh run, returning the new run.
 * Prior runs stay attached as attempt history. Same `agent`/`execute` semantics
 * as {@link startRun}; the body is sent only when needed for pre-retry gateways.
 */
export async function retryMission(
	missionId: string,
	agent?: AgentRuntime,
	execute?: boolean
): Promise<{ run: Run; executing?: boolean }> {
	const init: RequestInit = { method: 'POST' };
	const body: { agent?: AgentRuntime; execute?: boolean } = {};
	if (agent) body.agent = agent;
	if (execute) body.execute = true;
	if (agent || execute) init.body = JSON.stringify(body);
	return apiFetch(`/v1/missions/${encodeURIComponent(missionId)}/retry`, init);
}

export async function getRun(id: string): Promise<{ run: Run }> {
	return apiFetch(`/v1/runs/${encodeURIComponent(id)}`);
}

export async function getRunEvents(
	id: string,
	after?: number,
	limit?: number
): Promise<{ run_id: string; events: AuditEvent[]; next_cursor: number }> {
	const params = new URLSearchParams();
	if (after !== undefined) params.set('after', String(after));
	if (limit !== undefined) params.set('limit', String(limit));
	const query = params.size > 0 ? `?${params.toString()}` : '';
	return apiFetch(`/v1/runs/${encodeURIComponent(id)}/events${query}`);
}

/**
 * Cancel a mission's active runs.
 * Note: the gateway dispatches `atlas mission cancel`, which halts EVERY
 * running run of the mission, not a single run.
 */
export async function cancelRun(missionId: string): Promise<{ status: string }> {
	return apiFetch(`/v1/missions/${encodeURIComponent(missionId)}/cancel`, {
		method: 'POST'
	});
}

/**
 * Live audit stream for a run. Resumes from `after` so a reconnect continues the
 * stream rather than replaying it from rowid 0. The gateway emits named SSE
 * events: `audit` (an AuditEvent), `end` ({ status }), `stream_error` ({ error }).
 * WebView2 supports EventSource.
 */
export function openRunStream(id: string, after = 0): EventSource {
	return new EventSource(`${GATEWAY}/v1/runs/${encodeURIComponent(id)}/stream?after=${after}`);
}

/** A run joined to its mission title — what the cross-mission Runs feed renders. */
export interface RunWithMission extends Run {
	mission_title: string;
}

/**
 * Cross-mission run feed — single `GET /v1/runs` query (mission title JOINed
 * gateway-side). Falls back to the legacy listMissions → getMission fan-out
 * only when the running gateway binary predates the endpoint (404).
 */
export async function listRuns(limit = 100): Promise<{ runs: RunWithMission[] }> {
	try {
		const { runs } = await apiFetch<{ runs: RunWithMission[] }>(`/v1/runs?limit=${limit}`);
		return { runs };
	} catch (err) {
		if (!(err instanceof ApiError) || err.status !== 404) throw err;
	}
	// Legacy fan-out for stale gateway binaries.
	const { missions } = await listMissions(limit);
	const settled = await Promise.allSettled(missions.map((m) => getMission(m.id)));
	const seen = new Set<string>();
	const runs: RunWithMission[] = [];
	settled.forEach((res, i) => {
		if (res.status !== 'fulfilled') return;
		for (const run of res.value.runs) {
			if (seen.has(run.id)) continue;
			seen.add(run.id);
			runs.push({ ...run, mission_title: missions[i].title });
		}
	});
	runs.sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at));
	return { runs: runs.slice(0, limit) };
}

// ── Wiki endpoints ────────────────────────────────────────────────────────────

/** Mirrors memory_provenance row exposed by the gateway page-detail endpoint. */
export interface ProvenanceRecord {
	run_id: string | null;
	operator_id: string | null;
	source_id: string | null;
	sensitivity: string;
	written_at: string;
}

export interface WikiPageDetail extends WikiPage {
	provenance: ProvenanceRecord | null;
}

export async function listWikiPages(limit = 50): Promise<{ pages: WikiPage[]; count: number }> {
	return apiFetch(`/v1/wiki/pages?limit=${limit}`);
}

/** Mirrors the gateway's FTS search row: snippet + rank score, no created_at. */
export interface WikiSearchResult {
	slug: string;
	title: string;
	snippet: string;
	score: number;
	updated_at: string;
}

export async function searchWiki(
	q: string,
	limit?: number
): Promise<{ query: string; results: WikiSearchResult[] }> {
	const limitParam = limit !== undefined ? `&limit=${limit}` : '';
	return apiFetch(`/v1/wiki/search?q=${encodeURIComponent(q)}${limitParam}`);
}

export async function getWikiPage(slug: string): Promise<{ page: WikiPageDetail }> {
	return apiFetch(`/v1/wiki/pages/${encodeURIComponent(slug)}`);
}

export async function createWikiPage(
	slug: string,
	title: string,
	body: string
): Promise<{ page: WikiPageDetail }> {
	return apiFetch('/v1/wiki/pages', {
		method: 'POST',
		body: JSON.stringify({ slug, title, body })
	});
}

export async function updateWikiPage(
	slug: string,
	updates: { title?: string; body?: string }
): Promise<{ page: WikiPageDetail }> {
	return apiFetch(`/v1/wiki/pages/${encodeURIComponent(slug)}`, {
		method: 'PUT',
		body: JSON.stringify(updates)
	});
}

// ── Model registry ────────────────────────────────────────────────────────────

/**
 * Mirrors actual model_registry schema from 0003_model_registry.sql.
 * Columns: model_id / provider / source / first_seen / last_seen / active
 * Plan-spec fields (tier / health / policy / updated_at) are not in the DB;
 * tier and health are derived client-side when absent from the API response.
 */
export interface ModelEntry {
	model_id: string;
	provider: string;
	/** source URI / registry path */
	source: string;
	first_seen: string;
	last_seen: string;
	/** db.rs emits a JSON boolean (`active != 0`). */
	active: boolean;
	/** Optional fields the gateway may add in the future */
	tier?: string;
	health?: string;
	policy?: string;
}

/**
 * GET /v1/models — returns { models, count }.
 * Degrades gracefully ONLY on 404 (endpoint/table absent) and 503 (db
 * unavailable): those render as the empty-registry state. Every other failure
 * (500s, network errors) is rethrown so the page shows its error banner.
 */
export async function listModels(): Promise<{ models: ModelEntry[]; count: number }> {
	try {
		return await apiFetch<{ models: ModelEntry[]; count: number }>('/v1/models');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
			return { models: [], count: 0 };
		}
		throw err;
	}
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string; db: string }> {
	return apiFetch('/health');
}

// ── Config (~/.atlas/config.yaml, masked) ─────────────────────────────────────

/** Credential wiring mode for the multi-mode provider mesh. */
export type ProviderAuthMode = 'api_key' | 'oauth_import' | 'claude_code' | 'freellmapi';

/** Reasoning effort forwarded to providers that support it; '' = provider default. */
export type ReasoningEffort = '' | 'minimal' | 'low' | 'medium' | 'high';

export interface AtlasConfigView {
	/** Optimistic-concurrency revision required by PATCH /v1/config. */
	revision?: number;
	provider: {
		name: string;
		model: string;
		api_key: string;
		base_url: string | null;
		auth_mode?: ProviderAuthMode;
		reasoning_effort?: ReasoningEffort;
	};
	/** Function-slot routing: curator/auxiliary side-task model autoconfig. */
	functions?: {
		autoconfig: boolean;
		curator_model: string;
		auxiliary_model: string;
		actor_model?: string;
		judge_model?: string;
	};
	runtime: { default_agent: string; iteration_budget: number; compression: string };
	gateway: { rust_port: number; messaging_enabled: boolean; messaging_port: number };
	cockpit: { port: number; branding: string };
	modules: Record<string, boolean>;
	/** True when no effective provider credential resolves (drives the cockpit's
	 * "MOCK MODE" banner). Older gateways/CLIs predating this field omit it. */
	mock_mode?: boolean;
}

/** Masked ATLAS config from the gateway. Secrets are env: refs only. */
export async function getConfig(): Promise<AtlasConfigView> {
	return apiFetch('/v1/config');
}

/**
 * One optimistic config mutation. `changes` maps dotted setting paths
 * (e.g. "provider.auth_mode") to new values; a stale `expectedRevision`
 * rejects with a 409 ApiError carrying `currentRevision`.
 */
export async function patchConfig(
	expectedRevision: number,
	changes: Record<string, unknown>
): Promise<AtlasConfigView> {
	return apiFetch('/v1/config', {
		method: 'PATCH',
		body: JSON.stringify({ expected_revision: expectedRevision, changes })
	});
}

// ── Provider mesh (status / modes / auth) ─────────────────────────────────────

export interface ProviderStatusView {
	provider: string;
	model: string;
	auth_mode: ProviderAuthMode;
	auth_mode_label: string;
	base_url: string | null;
	credentials_present: boolean;
	mock_mode: boolean;
	remediation: string | null;
	reasoning_effort?: string | null;
	privacy_warning?: string | null;
}

export interface ProviderModeView {
	mode: ProviderAuthMode;
	label: string;
	active: boolean;
	available: boolean;
	detail: string;
	remediation: string | null;
}

/** Active provider resolution + mock-vs-live verdict (secret-free). */
export async function getProviderStatus(): Promise<ProviderStatusView> {
	return apiFetch('/v1/provider/status');
}

/** The four-way "which ways can I wire?" availability board. */
export async function getProviderModes(): Promise<ProviderModeView[]> {
	return apiFetch('/v1/provider/modes');
}

/** Store an API key in the ATLAS auth store (secret crosses once, masked reply). */
export async function storeProviderKey(
	provider: string,
	apiKey: string,
	baseUrl?: string
): Promise<{ provider: string; status: string; redacted_hint: string }> {
	return apiFetch('/v1/auth/providers', {
		method: 'POST',
		body: JSON.stringify({ provider, api_key: apiKey, ...(baseUrl ? { base_url: baseUrl } : {}) })
	});
}

/** Import the operator's Codex/ChatGPT OAuth login into the owned store. */
export async function importCodex(): Promise<{ imported: boolean; reason?: string }> {
	return apiFetch('/v1/auth/codex/import', { method: 'POST' });
}

// ── Channels (foundation messaging gateway config) ────────────────────────────

export interface ChannelSummary {
	name: string;
	enabled: boolean;
	credential_present: boolean;
}

/** Configured messaging channels. Empty when no foundation config / gateway. */
export async function listChannels(): Promise<{ channels: ChannelSummary[] }> {
	try {
		return await apiFetch<{ channels: ChannelSummary[] }>('/v1/channels');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return { channels: [] };
		}
		throw err;
	}
}

/** Enable/disable a channel; persists to the foundation config.yaml. */
export async function toggleChannel(name: string, enabled: boolean): Promise<{ name: string; enabled: boolean }> {
	return apiFetch(`/v1/channels/${encodeURIComponent(name)}/toggle`, {
		method: 'POST',
		body: JSON.stringify({ enabled })
	});
}

export interface MessagingGatewayStatus {
	running: boolean;
	pid: number | null;
}

/** Lifecycle status of the foundation messaging gateway (the bot daemon, not the
 * Rust REST gateway). Returns stopped when no gateway/config is reachable. */
export async function messagingGatewayStatus(): Promise<MessagingGatewayStatus> {
	try {
		return await apiFetch<MessagingGatewayStatus>('/v1/gateway/messaging/status');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return { running: false, pid: null };
		}
		throw err;
	}
}

/** Start the foundation messaging gateway (detached, pid-tracked). */
export async function startMessagingGateway(): Promise<{ ok: boolean; message: string; running?: boolean; pid?: number | null }> {
	return apiFetch('/v1/gateway/messaging/start', { method: 'POST' });
}

/** Stop the foundation messaging gateway (idempotent). */
export async function stopMessagingGateway(): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/v1/gateway/messaging/stop', { method: 'POST' });
}

// ── Discord surface (vendored L2-BOT sidecar) ─────────────────────────────────

export interface DiscordSidecarStatus {
	running: boolean;
	pid: number | null;
	ready: boolean;
	guild_count: number;
}

export interface DiscordGuild {
	id: string;
	name: string;
}

export interface DiscordChannel {
	id: string;
	name: string;
	type: string;
	position?: number;
	topic?: string | null;
	category_name?: string | null;
}

export interface DiscordCategory {
	id: string;
	name: string;
	position: number;
	channels: DiscordChannel[];
}

export interface DiscordRole {
	id: string;
	name: string;
	color: string;
	position: number;
	mentionable?: boolean;
	hoist?: boolean;
	managed?: boolean;
}

export interface DiscordStructure {
	guild: { id: string; name: string; member_count: number };
	categories: DiscordCategory[];
	uncategorized: DiscordChannel[];
	roles: DiscordRole[];
}

/** Discord sidecar lifecycle status. Stopped when unreachable. */
export async function discordStatus(): Promise<DiscordSidecarStatus> {
	try {
		return await apiFetch<DiscordSidecarStatus>('/v1/discord/status');
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return { running: false, pid: null, ready: false, guild_count: 0 };
		}
		throw err;
	}
}

export async function startDiscord(): Promise<{ ok: boolean; message: string; running?: boolean; pid?: number | null }> {
	return apiFetch('/v1/discord/start', { method: 'POST' });
}

export async function stopDiscord(): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/v1/discord/stop', { method: 'POST' });
}

/** Guilds the bot is in. Empty when the sidecar is not running. */
export async function listGuilds(): Promise<DiscordGuild[]> {
	try {
		const data = await apiFetch<{ guilds: DiscordGuild[] }>('/v1/discord/guilds');
		return data.guilds ?? [];
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return [];
		}
		throw err;
	}
}

/** A guild's structure: categories → channels, plus roles. */
export async function getGuildStructure(guildId: string): Promise<DiscordStructure> {
	return apiFetch(`/v1/discord/guilds/${encodeURIComponent(guildId)}/structure`);
}

// ── Gated Discord writes (propose → approve → execute) ───────────────────────

export type DiscordAction =
	| 'create_channel'
	| 'edit_channel'
	| 'delete_channel'
	| 'create_role'
	| 'edit_role'
	| 'delete_role'
	| 'send_message'
	| 'set_permissions';

export type DiscordApprovalStatus = 'pending' | 'executing' | 'executed' | 'rejected' | 'failed';

export interface DiscordApproval {
	id: string;
	action: DiscordAction;
	guild_id: string;
	target_id: string | null;
	params: string;
	summary: string;
	status: DiscordApprovalStatus;
	reason: string | null;
	result: string | null;
	run_id: string;
	requested_at: string;
	decided_at: string | null;
}

/** Propose a gated Discord write. Records a pending approval; nothing executes. */
export async function proposeDiscordWrite(args: {
	action: DiscordAction;
	guild: string;
	target?: string | null;
	params?: Record<string, unknown>;
	reason?: string;
}): Promise<DiscordApproval> {
	return apiFetch('/v1/discord/writes', {
		method: 'POST',
		body: JSON.stringify({
			action: args.action,
			guild: args.guild,
			target: args.target ?? null,
			params: args.params ?? {},
			reason: args.reason ?? null
		})
	});
}

/** Pending gated writes awaiting an operator decision. Empty when offline. */
export async function listDiscordApprovals(): Promise<DiscordApproval[]> {
	try {
		const data = await apiFetch<{ approvals: DiscordApproval[] }>('/v1/discord/approvals');
		return data.approvals ?? [];
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return [];
		}
		throw err;
	}
}

/** Approve + execute a pending write via the sidecar. Returns the terminal row. */
export async function approveDiscordWrite(id: string): Promise<DiscordApproval> {
	return apiFetch(`/v1/discord/approvals/${encodeURIComponent(id)}/approve`, { method: 'POST' });
}

/** Reject a pending write (it will never execute). */
export async function rejectDiscordWrite(id: string, reason?: string): Promise<DiscordApproval> {
	return apiFetch(`/v1/discord/approvals/${encodeURIComponent(id)}/reject`, {
		method: 'POST',
		body: JSON.stringify({ reason: reason ?? null })
	});
}

// ── Developer tool integrations (Phase 10.0.4) ─────────────────────────────

export type ToolRiskLevel = 'read' | 'write' | 'shell';
export type ToolApprovalStatus = 'pending' | 'executing' | 'executed' | 'rejected' | 'failed';

export interface ToolManifestInput {
	name: string;
	required: boolean;
	description: string;
}

export interface ToolManifest {
	name: string;
	description: string;
	risk_level: ToolRiskLevel;
	permissions: string[];
	inputs: ToolManifestInput[];
	outputs: string[];
	audit_events: string[];
}

export type ToolApproval = SurfaceToolApproval;

export interface ToolResult {
	tool_name: string;
	ok: boolean;
	output: string;
	error: string | null;
	exit_code: number | null;
}

/** All tool manifests (name/risk_level/permissions/…). Empty when offline. */
export async function getToolManifests(): Promise<ToolManifest[]> {
	try {
		const data = await apiFetch<{ manifests: ToolManifest[] }>('/v1/tools/manifests');
		return data.manifests ?? [];
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return [];
		}
		throw err;
	}
}

/** Tool approvals (all statuses, newest first). Empty when offline. */
export async function listToolApprovals(): Promise<ToolApproval[]> {
	try {
		const data = await apiFetch<{ approvals: ToolApproval[] }>('/v1/tools/approvals?status=all');
		return data.approvals ?? [];
	} catch (err) {
		if (err instanceof ApiError && (err.status === 404 || err.status === 500 || err.status === 503)) {
			return [];
		}
		throw err;
	}
}

/** Actionable queue owned by one live surface session. */
export async function listOwnedToolApprovals(
	session: Pick<SurfaceSession, 'id' | 'owner_token'>
): Promise<ToolApproval[]> {
	const params = new URLSearchParams({ status: 'pending' });
	const data = await apiFetch<{ approvals: ToolApproval[] }>(
		`/v1/surface-sessions/${encodeURIComponent(session.id)}/approvals?${params.toString()}`,
		{ headers: surfaceOwnerHeaders(session.owner_token) }
	);
	return data.approvals ?? [];
}

/** Invoke a tool through the policy chokepoint. Read-class runs now; write/shell
 *  returns a pending approval (nothing executes inline). */
export async function proposeToolCall(args: {
	tool: string;
	args?: Record<string, unknown>;
	mode?: string;
	reason?: string;
}): Promise<ToolResult | ToolApproval> {
	return apiFetch('/v1/tools/calls', {
		method: 'POST',
		body: JSON.stringify({
			tool: args.tool,
			args: args.args ?? {},
			mode: args.mode ?? 'read_only',
			reason: args.reason ?? null
		})
	});
}

/** Approve + execute a pending write/shell tool call. Returns the terminal row. */
export async function approveToolCall(
	approval: Pick<ToolApproval, 'id' | 'surface_session_id' | 'nonce'>,
	ownerToken: string,
	scope: 'once' | 'session' | 'durable'
): Promise<ToolApproval> {
	if (!approval.surface_session_id || !approval.nonce) {
		throw new Error('approval decision requires surface ownership and nonce');
	}
	return apiFetch(`/v1/surface-sessions/${encodeURIComponent(approval.surface_session_id)}/approvals/${encodeURIComponent(approval.id)}/approve`, {
		method: 'POST',
		headers: surfaceOwnerHeaders(ownerToken),
		body: JSON.stringify({
			nonce: approval.nonce,
			scope
		})
	});
}

/** Reject a pending tool call (it will never execute). */
export async function rejectToolCall(
	approval: Pick<ToolApproval, 'id' | 'surface_session_id' | 'nonce'>,
	ownerToken: string,
	reason?: string
): Promise<ToolApproval> {
	if (!approval.surface_session_id || !approval.nonce) {
		throw new Error('approval decision requires surface ownership and nonce');
	}
	return apiFetch(`/v1/surface-sessions/${encodeURIComponent(approval.surface_session_id)}/approvals/${encodeURIComponent(approval.id)}/reject`, {
		method: 'POST',
		headers: surfaceOwnerHeaders(ownerToken),
		body: JSON.stringify({
			nonce: approval.nonce,
			reason: reason ?? null
		})
	});
}
