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
	rowid: number;
	run_id: string;
	event_type: string;
	payload: string;
	created_at: string;
}

export interface WikiPage {
	slug: string;
	title: string;
	body: string;
	layer: number;
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

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string; db: string }> {
	return apiFetch('/health');
}
