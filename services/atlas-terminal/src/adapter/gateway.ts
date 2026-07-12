/**
 * Typed ATLAS gateway client for the adapter — the same contracts the Go TUI
 * proved (surface sessions, missions, runs, approvals, SSE run stream).
 * Owner-token mutations send X-Atlas-Surface-Owner exactly like the Go client.
 */

export interface SurfaceSession {
	id: string;
	owner_token: string;
	state: string;
}

export interface Mission {
	id: string;
	title: string;
	status: string;
}

export interface ToolApproval {
	id: string;
	tool_name: string;
	risk_level: string;
	args: string;
	summary: string;
	status: string;
	run_id: string;
	surface_session_id: string;
	requested_at: string;
	/** Replay nonce — approve/reject require it (gateway rejects without). */
	nonce: string;
}

export type ApprovalScope = 'once' | 'session' | 'durable';

export interface RunEvent {
	name: string; // "audit" | "end" | "stream_error"
	data: Record<string, unknown>;
}

export class GatewayError extends Error {
	constructor(
		public readonly status: number,
		public readonly path: string,
		message: string
	) {
		super(`${path}: ${status} ${message}`);
	}
}

/** Per-request deadline — a hung gateway must not block the caller forever. */
const REQUEST_TIMEOUT_MS = 15_000;

export class GatewayClient {
	private readonly gw: string;
	private readonly f: typeof fetch;

	constructor(gateway: string, fetchImpl?: typeof fetch) {
		this.gw = gateway.replace(/\/+$/, '');
		this.f = fetchImpl ?? fetch;
	}

	private async request<T>(
		method: string,
		path: string,
		body?: unknown,
		ownerToken?: string
	): Promise<T> {
		const headers: Record<string, string> = {};
		if (body !== undefined) headers['content-type'] = 'application/json';
		if (ownerToken) headers['X-Atlas-Surface-Owner'] = ownerToken;
		const res = await this.f(`${this.gw}${path}`, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body),
			signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
		});
		if (!res.ok) {
			const text = await res.text().catch(() => '');
			throw new GatewayError(res.status, path, text.slice(0, 300));
		}
		return (await res.json()) as T;
	}

	createSurface(surfaceKind = 'tui', workspaceKind = 'global'): Promise<SurfaceSession> {
		return this.request<SurfaceSession>('POST', '/v1/surface-sessions', {
			surface_kind: surfaceKind,
			workspace_kind: workspaceKind
		});
	}

	closeSurface(session: SurfaceSession): Promise<unknown> {
		return this.request('POST', `/v1/surface-sessions/${encodeURIComponent(session.id)}/close`, {
			owner_token: session.owner_token
		});
	}

	cancelSurface(session: SurfaceSession): Promise<unknown> {
		return this.request('POST', `/v1/surface-sessions/${encodeURIComponent(session.id)}/cancel`, {
			owner_token: session.owner_token
		});
	}

	/** POST heartbeat — keeps the approval channel and owner lease alive (same contract the Go TUI used). */
	heartbeatSurface(session: SurfaceSession): Promise<SurfaceSession> {
		return this.request<SurfaceSession>(
			'POST',
			`/v1/surface-sessions/${encodeURIComponent(session.id)}/heartbeat`,
			{ owner_token: session.owner_token }
		);
	}

	async createMission(title: string, intent: string): Promise<Mission> {
		const env = await this.request<{ mission: Mission }>('POST', '/v1/missions', { title, intent });
		return env.mission;
	}

	async startRun(missionID: string, agent: string, surfaceSessionID: string): Promise<string> {
		const env = await this.request<{ run: { id: string } }>(
			'POST',
			`/v1/missions/${encodeURIComponent(missionID)}/run`,
			{ agent: agent || 'native', execute: true, surface_session_id: surfaceSessionID }
		);
		return env.run.id;
	}

	async approvals(session: SurfaceSession, status = 'pending'): Promise<ToolApproval[]> {
		const env = await this.request<{ approvals: ToolApproval[] }>(
			'GET',
			`/v1/surface-sessions/${encodeURIComponent(session.id)}/approvals?status=${encodeURIComponent(status)}`,
			undefined,
			session.owner_token
		);
		return env.approvals ?? [];
	}

	decideApproval(
		session: SurfaceSession,
		approval: ToolApproval,
		decision: 'approve' | 'reject',
		scope: ApprovalScope = 'once'
	): Promise<unknown> {
		// Gateway ToolDecisionBody: {nonce, scope?, reason?}; owner rides the header.
		const body = decision === 'approve' ? { nonce: approval.nonce, scope } : { nonce: approval.nonce };
		return this.request(
			'POST',
			`/v1/surface-sessions/${encodeURIComponent(session.id)}/approvals/${encodeURIComponent(approval.id)}/${decision}`,
			body,
			session.owner_token
		);
	}

	/**
	 * Consume GET /v1/runs/{id}/stream (text/event-stream); invokes onEvent per
	 * frame and resolves when the stream closes. "end" frames still flow to
	 * onEvent — the caller owns terminal-state handling. Deliberately NOT under
	 * REQUEST_TIMEOUT_MS: runs stream for minutes and the gateway keepalives.
	 */
	async streamRun(runID: string, onEvent: (event: RunEvent) => void): Promise<void> {
		const res = await this.f(`${this.gw}/v1/runs/${encodeURIComponent(runID)}/stream`, {
			headers: { accept: 'text/event-stream' }
		});
		if (!res.ok || !res.body) {
			throw new GatewayError(res.status, `/v1/runs/${runID}/stream`, 'stream unavailable');
		}
		const reader = res.body.getReader();
		const decoder = new TextDecoder();
		let buffer = '';
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });
			let sep: number;
			while ((sep = buffer.indexOf('\n\n')) >= 0) {
				const frame = buffer.slice(0, sep);
				buffer = buffer.slice(sep + 2);
				const event = parseSSEFrame(frame);
				if (event) onEvent(event);
			}
		}
	}
}

function parseSSEFrame(frame: string): RunEvent | null {
	let name = 'message';
	const dataLines: string[] = [];
	for (const raw of frame.split('\n')) {
		const line = raw.replace(/\r$/, '');
		if (line.startsWith(':')) continue; // comment/keepalive
		if (line.startsWith('event:')) name = line.slice(6).trim();
		else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
	}
	if (dataLines.length === 0) return null;
	try {
		return { name, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> };
	} catch {
		return { name, data: { raw: dataLines.join('\n') } };
	}
}
