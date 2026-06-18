// ATLAS Cockpit — API client targeting Phase 7 gateway
// Base: http://127.0.0.1:8484

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
}

/** Folder-backed working directory (P3). Mirrors db.rs project_row. */
export interface Project {
	id: string;
	name: string;
	root_path: string;
	created_at: string;
	updated_at: string;
}

/** Agent runtime that executes a run: native ATLAS in-process, or the operator's
 * local Claude Code session. Mirrors the gateway's `agent` request field /
 * `agent_runtime` response field (P4 — modular agents). */
export type AgentRuntime = 'native' | 'claude_code';

/** Human display label for an agent runtime (e.g. "claude_code" → "CLAUDE CODE"). */
export function agentRuntimeLabel(agent: AgentRuntime): string {
	switch (agent) {
		case 'native':
			return 'NATIVE';
		case 'claude_code':
			return 'CLAUDE CODE';
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
		message: string
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
		throw new ApiError(response.status, `GATEWAY ERROR ${response.status} — ${path}: ${text}`);
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

// ── Run endpoints ────────────────────────────────────────────────────────────

/**
 * Trigger a mission run. `agent` selects the runtime the gateway records the run
 * against ("native" default | "claude_code"); it is sent in the JSON body only
 * when provided so a pre-P4 gateway still accepts the bodyless request.
 */
export async function startRun(missionId: string, agent?: AgentRuntime): Promise<{ run: Run }> {
	const init: RequestInit = { method: 'POST' };
	if (agent) init.body = JSON.stringify({ agent });
	return apiFetch(`/v1/missions/${encodeURIComponent(missionId)}/run`, init);
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
 * Cross-mission run feed. INTERIM: the gateway has no `GET /v1/runs` yet
 * (HARNESS-WIRING §5), so this fans out listMissions → getMission and flattens.
 * Bounded by the mission list limit; replace with the real endpoint when it ships.
 */
export async function listRuns(limit = 100): Promise<{ runs: RunWithMission[] }> {
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
