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

export interface Run {
	id: string;
	mission_id: string;
	session_id: string | null;
	status: string;
	started_at: string;
	finished_at: string | null;
	summary: string;
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
	intent: string
): Promise<{ mission: Mission; runs: Run[] }> {
	return apiFetch('/v1/missions', {
		method: 'POST',
		body: JSON.stringify({ title, intent })
	});
}

// ── Run endpoints ────────────────────────────────────────────────────────────

export async function startRun(missionId: string): Promise<{ run: Run }> {
	return apiFetch(`/v1/missions/${encodeURIComponent(missionId)}/run`, {
		method: 'POST'
	});
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
