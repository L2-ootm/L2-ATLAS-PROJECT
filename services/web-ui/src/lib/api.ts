// ATLAS Cockpit — API client targeting Phase 7 gateway
// Base: http://127.0.0.1:8484

const GATEWAY = 'http://127.0.0.1:8484';

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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${GATEWAY}${path}`, {
		headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
		...init
	});
	if (!response.ok) {
		const text = await response.text().catch(() => response.statusText);
		throw new Error(`GATEWAY ERROR ${response.status} — ${path}: ${text}`);
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
	after?: number
): Promise<{ run_id: string; events: AuditEvent[]; next_cursor: number }> {
	const query = after !== undefined ? `?after=${after}` : '';
	return apiFetch(`/v1/runs/${encodeURIComponent(id)}/events${query}`);
}

/**
 * Stream run events via SSE.
 * Returns a close function.
 */
export function streamRun(
	id: string,
	onEvent: (e: AuditEvent) => void,
	onEnd: (status: string) => void,
	onError: (msg: string) => void
): () => void {
	const source = new EventSource(`${GATEWAY}/v1/runs/${encodeURIComponent(id)}/stream`);

	source.addEventListener('audit', (evt: MessageEvent) => {
		try {
			const data = JSON.parse(evt.data) as AuditEvent;
			onEvent(data);
		} catch {
			onError(`Failed to parse SSE event: ${evt.data}`);
		}
	});

	source.addEventListener('end', (evt: MessageEvent) => {
		source.close();
		onEnd(evt.data ?? 'SUCCEEDED');
	});

	source.addEventListener('error', () => {
		onError('STREAM INTERRUPTED — reconnecting in 2s. If this persists, check gateway health.');
	});

	return () => source.close();
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

export async function searchWiki(
	q: string,
	limit?: number
): Promise<{ query: string; results: WikiPage[] }> {
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
	/** 1 = active, 0 = inactive */
	active: number;
	/** Optional fields the gateway may add in the future */
	tier?: string;
	health?: string;
	policy?: string;
}

/**
 * GET /v1/models — returns { models, count }.
 * Degrades gracefully: returns empty list on 404/503 so the models page renders
 * an empty state instead of throwing.
 */
export async function listModels(): Promise<{ models: ModelEntry[]; count: number }> {
	try {
		return await apiFetch<{ models: ModelEntry[]; count: number }>('/v1/models');
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		// Degrade gracefully on gateway-down / table-absent errors
		if (
			msg.includes('503') ||
			msg.includes('404') ||
			msg.includes('Failed to fetch') ||
			msg.includes('GATEWAY ERROR')
		) {
			return { models: [], count: 0 };
		}
		throw err;
	}
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string; db: string }> {
	return apiFetch('/health');
}
