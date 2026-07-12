/**
 * Chat orchestrator — donor session semantics over ATLAS mission/run contracts.
 *
 * Mapping (same loop the Go TUI proved):
 * - donor session      = local conversation bound to ONE ATLAS surface session
 * - donor prompt       = ATLAS mission (title/intent = prompt) + run (execute)
 * - donor message part = translated ATLAS audit frame from /v1/runs/{id}/stream
 * - donor permission   = ATLAS tool approval on the owned surface session
 *
 * ATLAS keeps runtime/provider/config/audit/policy/session/storage authority;
 * this module only translates. Shapes follow the donor SDK v2 openapi; the
 * STAGE 2 donor-UI vendoring pass is the fidelity gate for optional fields.
 */

import { EventBus } from './events';
import { GatewayClient, GatewayError, type RunEvent, type SurfaceSession, type ToolApproval } from './gateway';

interface DonorTime {
	created: number;
	updated?: number;
	completed?: number;
}

export interface DonorSession {
	id: string;
	slug: string;
	projectID: string;
	directory: string;
	title: string;
	version: string;
	time: DonorTime;
}

interface DonorMessageInfo {
	id: string;
	sessionID: string;
	role: 'user' | 'assistant';
	time: DonorTime;
	// assistant-only donor-required fields (harmless on user messages)
	parentID?: string;
	modelID?: string;
	providerID?: string;
	mode?: string;
	agent?: string;
	cost?: number;
	tokens?: Record<string, number>;
	path?: Record<string, string>;
}

interface DonorPart {
	id: string;
	sessionID: string;
	messageID: string;
	type: string;
	text?: string;
	callID?: string;
	tool?: string;
	state?: Record<string, unknown>;
	time?: Record<string, number>;
}

export interface DonorMessage {
	info: DonorMessageInfo;
	parts: DonorPart[];
}

interface PromptBody {
	parts?: Array<{ type?: string; text?: string }>;
	model?: { providerID?: string; modelID?: string };
	agent?: string;
}

const VERSION = 'atlas-terminal-stage1';

export interface ChatAdapterOptions {
	gateway: GatewayClient;
	bus: EventBus;
	directory?: string;
	/** ATLAS agent used for runs; donor agent names are not ATLAS agents. */
	atlasAgent?: string;
	/** Poll cadence for pending approvals while a run is active (ms). */
	permissionPollMs?: number;
	/** Surface heartbeat cadence (ms); 0 disables (tests). */
	heartbeatMs?: number;
}

export class ChatAdapter {
	private readonly gw: GatewayClient;
	private readonly bus: EventBus;
	private readonly directory: string;
	private readonly atlasAgent: string;
	private readonly permissionPollMs: number;

	private surface: SurfaceSession | null = null;
	private counter = 0;
	private readonly sessions = new Map<string, DonorSession>();
	private readonly messages = new Map<string, DonorMessage[]>();
	private readonly partsByCall = new Map<string, DonorPart>();
	/**
	 * assistant message id -> the text part fed by llm_delta chunks. `open`
	 * stays true while a turn's deltas are arriving; end_of_turn flips it to
	 * false so a later turn (e.g. after a tool round) starts a fresh part,
	 * while the entry itself survives so the trailing llm_call can still
	 * reconcile onto it instead of appending a duplicate.
	 */
	private readonly streamingText = new Map<string, { part: DonorPart; open: boolean }>();
	private readonly seenApprovals = new Set<string>();
	/** approvalID → donor sessionID that was busy when it surfaced. */
	private readonly approvalSession = new Map<string, string>();
	/** approvalID → full approval; decide requires its replay nonce. */
	private readonly approvalByID = new Map<string, ToolApproval>();
	private activeRuns = 0;
	private pollTimer: ReturnType<typeof setInterval> | undefined;
	private heartbeatTimer: ReturnType<typeof setInterval> | undefined;
	private readonly heartbeatMs: number;
	/** donor sessionIDs with a run in flight — backs GET /session/status. */
	private readonly busySessions = new Set<string>();

	constructor(opts: ChatAdapterOptions) {
		this.gw = opts.gateway;
		this.bus = opts.bus;
		this.directory = opts.directory ?? process.cwd();
		this.atlasAgent = opts.atlasAgent ?? 'native';
		this.permissionPollMs = opts.permissionPollMs ?? 4000;
		this.heartbeatMs = opts.heartbeatMs ?? 30_000;
	}

	private nextID(prefix: string): string {
		this.counter += 1;
		return `${prefix}_${Date.now().toString(36)}${this.counter.toString(36).padStart(4, '0')}`;
	}

	private async ensureSurface(): Promise<SurfaceSession> {
		if (this.surface) return this.surface;
		// gateway SurfaceIdentity.kind literal: cli|tui|webui|api|native|test
		// Retry: a briefly unreachable gateway mid-prompt must not surface as an
		// unhandled throw (2 retries, 1s backoff).
		let lastErr: unknown;
		for (let attempt = 0; attempt < 3; attempt++) {
			if (attempt > 0) await new Promise((resolve) => setTimeout(resolve, 1000));
			try {
				this.surface = await this.gw.createSurface('tui', 'global');
				this.startHeartbeat();
				return this.surface;
			} catch (err) {
				lastErr = err;
			}
		}
		const message = lastErr instanceof Error ? lastErr.message : String(lastErr);
		throw new Error(`gateway surface unavailable after 3 attempts: ${message}`);
	}

	// ── surface heartbeat (owner lease keepalive) ───────────────────────────

	private startHeartbeat(): void {
		if (this.heartbeatTimer || this.heartbeatMs <= 0) return;
		const timer = setInterval(() => {
			void this.heartbeatOnce();
		}, this.heartbeatMs);
		// Never hold the process open for a keepalive.
		(timer as unknown as { unref?: () => void }).unref?.();
		this.heartbeatTimer = timer;
	}

	private stopHeartbeat(): void {
		if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
		this.heartbeatTimer = undefined;
	}

	/**
	 * One heartbeat tick. A definitive owner/lease rejection (401/403/404/410 —
	 * e.g. gateway restart or the SURF-05 orphan sweep reaped the surface) drops
	 * the cached surface so the next prompt re-surfaces cleanly; transient
	 * failures keep the timer and retry next tick.
	 */
	async heartbeatOnce(): Promise<void> {
		const surface = this.surface;
		if (!surface) return;
		try {
			await this.gw.heartbeatSurface(surface);
		} catch (err) {
			if (err instanceof GatewayError && [401, 403, 404, 410].includes(err.status)) {
				this.surface = null;
				this.stopHeartbeat();
			}
		}
	}

	// ── sessions ────────────────────────────────────────────────────────────

	createSession(title = 'New session'): DonorSession {
		const now = Date.now();
		const session: DonorSession = {
			id: this.nextID('ses'),
			slug: this.nextID('slug'),
			projectID: 'atlas',
			directory: this.directory,
			title,
			version: VERSION,
			time: { created: now, updated: now }
		};
		this.sessions.set(session.id, session);
		this.messages.set(session.id, []);
		// Donor sync.tsx has no 'session.created' case — it treats 'session.updated'
		// as the single upsert event (insert-if-missing) for both create and update.
		this.bus.emit('session.updated', { sessionID: session.id, info: session });
		return session;
	}

	listSessions(): DonorSession[] {
		return [...this.sessions.values()];
	}

	getSession(id: string): DonorSession | undefined {
		return this.sessions.get(id);
	}

	listMessages(sessionID: string): DonorMessage[] {
		return this.messages.get(sessionID) ?? [];
	}

	async abort(sessionID: string): Promise<boolean> {
		if (!this.sessions.has(sessionID) || !this.surface) return false;
		await this.gw.cancelSurface(this.surface);
		this.busySessions.delete(sessionID);
		this.bus.emit('session.status', { sessionID, status: { type: 'idle' } });
		return true;
	}

	/** Donor GET /session/status — real idle/busy per known session. */
	sessionStatuses(): Record<string, { type: 'idle' | 'busy' }> {
		const out: Record<string, { type: 'idle' | 'busy' }> = {};
		for (const id of this.sessions.keys()) {
			out[id] = { type: this.busySessions.has(id) ? 'busy' : 'idle' };
		}
		return out;
	}

	// ── prompt → mission/run → SSE parts ────────────────────────────────────

	/**
	 * Donor POST /session/{id}/prompt_async. Returns once the run is started;
	 * parts stream onto the bus in the background.
	 */
	async promptAsync(sessionID: string, body: PromptBody): Promise<void> {
		const session = this.sessions.get(sessionID);
		if (!session) throw new Error(`unknown session ${sessionID}`);
		const text = (body.parts ?? [])
			.filter((p) => (p.type ?? 'text') === 'text' && p.text)
			.map((p) => p.text)
			.join('\n')
			.trim();
		if (!text) throw new Error('prompt has no text parts');

		const now = Date.now();
		const userMsg: DonorMessage = {
			info: { id: this.nextID('msg'), sessionID, role: 'user', time: { created: now } },
			parts: []
		};
		const userPart: DonorPart = {
			id: this.nextID('prt'),
			sessionID,
			messageID: userMsg.info.id,
			type: 'text',
			text
		};
		userMsg.parts.push(userPart);
		this.messages.get(sessionID)!.push(userMsg);
		this.bus.emit('message.updated', { sessionID, info: userMsg.info });
		this.bus.emit('message.part.updated', { sessionID, part: userPart, time: Date.now() });
		if (session.title === 'New session') {
			session.title = text.length > 64 ? `${text.slice(0, 61)}...` : text;
			this.bus.emit('session.updated', { sessionID, info: session });
		}

		let runID: string;
		try {
			const surface = await this.ensureSurface();
			const mission = await this.gw.createMission(session.title.slice(0, 120), text);
			runID = await this.gw.startRun(mission.id, this.atlasAgent, surface.id);
		} catch (err) {
			// Surface the failure in-session (not just as a 500 toast) and leave
			// the session idle so the composer stays usable.
			const message = err instanceof Error ? err.message : String(err);
			this.bus.emit('session.error', {
				sessionID,
				error: { name: 'UnknownError', data: { message } }
			});
			this.bus.emit('session.status', { sessionID, status: { type: 'idle' } });
			throw err;
		}

		const assistant: DonorMessage = {
			info: {
				id: this.nextID('msg'),
				sessionID,
				role: 'assistant',
				time: { created: Date.now() },
				parentID: userMsg.info.id,
				providerID: body.model?.providerID ?? '',
				modelID: body.model?.modelID ?? '',
				mode: 'build',
				agent: body.agent ?? this.atlasAgent,
				cost: 0,
				tokens: {},
				path: { cwd: this.directory, root: this.directory }
			},
			parts: []
		};
		this.messages.get(sessionID)!.push(assistant);
		this.bus.emit('message.updated', { sessionID, info: assistant.info });
		this.busySessions.add(sessionID);
		this.bus.emit('session.status', { sessionID, status: { type: 'busy' } });

		this.runStarted(sessionID);
		void this.gw
			.streamRun(runID, (event) => this.onRunEvent(sessionID, assistant, event))
			.catch((err: unknown) => {
				this.appendPart(assistant, {
					type: 'text',
					text: `stream error: ${err instanceof Error ? err.message : String(err)}`
				});
				this.bus.emit('session.error', {
					sessionID,
					error: { name: 'UnknownError', data: { message: String(err) } }
				});
			})
			.finally(() => {
				this.streamingText.delete(assistant.info.id);
				if (!assistant.info.time.completed) {
					assistant.info.time.completed = Date.now();
					this.bus.emit('message.updated', { sessionID, info: assistant.info });
				}
				this.busySessions.delete(sessionID);
				this.bus.emit('session.status', { sessionID, status: { type: 'idle' } });
				this.bus.emit('session.idle', { sessionID });
				this.runFinished();
			});
	}

	// ── audit frame → donor part translation ────────────────────────────────

	private appendPart(message: DonorMessage, fields: Partial<DonorPart> & { type: string }): DonorPart {
		const part: DonorPart = {
			id: this.nextID('prt'),
			sessionID: message.info.sessionID,
			messageID: message.info.id,
			...fields
		};
		message.parts.push(part);
		this.bus.emit('message.part.updated', { sessionID: part.sessionID, part, time: Date.now() });
		return part;
	}

	private onRunEvent(sessionID: string, assistant: DonorMessage, event: RunEvent): void {
		if (event.name === 'end') {
			assistant.info.time.completed = Date.now();
			this.bus.emit('message.updated', { sessionID, info: assistant.info });
			return;
		}
		if (event.name === 'stream_error') {
			const message = typeof event.data['error'] === 'string' ? event.data['error'] : 'stream error';
			this.appendPart(assistant, { type: 'text', text: `stream error: ${message}` });
			return;
		}
		if (event.name !== 'audit') return;

		const frame = event.data as {
			event_type?: string;
			tool_name?: string;
			tool_call_id?: string;
			data?: Record<string, unknown>;
		};
		const data = frame.data ?? {};
		const eventType = frame.event_type ?? '';
		const str = (key: string): string => (typeof data[key] === 'string' ? (data[key] as string) : '');
		const textOrSummary = str('text') || str('summary');

		// mission lifecycle transitions ride on tool_call frames
		const transition = str('transition');
		if (transition) {
			if (transition === 'failed') {
				this.appendPart(assistant, { type: 'text', text: str('summary') || str('error') || 'run failed' });
				this.bus.emit('session.error', {
					sessionID,
					error: { name: 'UnknownError', data: { message: str('summary') || str('error') || 'run failed' } }
				});
			} else if (transition === 'succeeded' && str('summary')) {
				const dupe = assistant.parts.some((p) => p.type === 'text' && p.text === str('summary'));
				if (!dupe) this.appendPart(assistant, { type: 'text', text: str('summary') });
			}
			return;
		}

		const surfaceKind = str('surface_kind');
		if (surfaceKind === 'reasoning' || (eventType === 'llm_call' && data['reasoning'] === true)) {
			if (textOrSummary) {
				this.appendPart(assistant, { type: 'reasoning', text: textOrSummary, time: { start: Date.now() } });
			}
			return;
		}
		if (eventType === 'llm_delta') {
			const deltaText = typeof data['delta'] === 'string' ? (data['delta'] as string) : '';
			const endOfTurn = data['end_of_turn'] === true;
			let entry = this.streamingText.get(assistant.info.id);
			// If the entry was already closed (reconciled by a prior llm_call
			// that deleted it), do NOT create a fresh part — that would
			// duplicate the text the llm_call already placed.
			if (entry && !entry.open) {
				// Reconciled: ignore remaining deltas for this turn.
				if (endOfTurn) this.streamingText.delete(assistant.info.id);
				return;
			}
			if (!entry && deltaText) {
				entry = { part: this.appendPart(assistant, { type: 'text', text: '' }), open: true };
				this.streamingText.set(assistant.info.id, entry);
			}
			if (entry?.open && deltaText) {
				entry.part.text = (entry.part.text ?? '') + deltaText;
				this.bus.emit('message.part.delta', {
					sessionID,
					messageID: assistant.info.id,
					partID: entry.part.id,
					field: 'text',
					delta: deltaText
				});
			}
			if (endOfTurn && entry) entry.open = false;
			return;
		}
		if (eventType === 'llm_call' || eventType === 'model_call_end') {
			if (textOrSummary) {
				// A streamed part already carries this turn's text incrementally;
				// reconcile it to the authoritative final text (post-processing
				// like think-block stripping can differ from the raw stream)
				// instead of appending a duplicate part.
				const entry = this.streamingText.get(assistant.info.id);
				if (entry) {
					entry.part.text = textOrSummary;
					this.bus.emit('message.part.updated', { sessionID, part: entry.part, time: Date.now() });
					this.streamingText.delete(assistant.info.id);
				} else {
					this.appendPart(assistant, { type: 'text', text: textOrSummary });
				}
			}
			return;
		}
		if (eventType === 'tool_call' || eventType === 'tool_requested') {
			if (frame.tool_name === 'native_runtime') return; // engagement marker
			const callID = frame.tool_call_id || this.nextID('call');
			const part = this.appendPart(assistant, {
				type: 'tool',
				callID,
				tool: frame.tool_name || 'tool',
				state: {
					status: 'running',
					input: data['input'] ?? { summary: str('summary') || str('command') || str('path') },
					time: { start: Date.now() }
				}
			});
			this.partsByCall.set(callID, part);
			return;
		}
		if (eventType === 'tool_completed' || eventType === 'discord_action') {
			this.settleTool(frame.tool_call_id, 'completed', str('summary') || str('result'));
			return;
		}
		if (eventType === 'tool_failed' || eventType === 'failure' || eventType.endsWith('_failed')) {
			this.settleTool(frame.tool_call_id, 'error', str('error') || str('message') || 'failed');
			return;
		}
		// unknown frames stay quiet; the audit ledger is redacted at write time
		// but we never dump opaque payload maps into the transcript.
	}

	private settleTool(callID: string | undefined, status: 'completed' | 'error', output: string): void {
		if (!callID) return;
		const part = this.partsByCall.get(callID);
		if (!part) return;
		const prior = (part.state ?? {}) as Record<string, unknown>;
		part.state = {
			...prior,
			status,
			...(status === 'completed' ? { output } : { error: output }),
			time: { ...(prior['time'] as Record<string, number> | undefined), end: Date.now() }
		};
		this.bus.emit('message.part.updated', { sessionID: part.sessionID, part, time: Date.now() });
	}

	// ── permissions (tool approvals) ────────────────────────────────────────

	private runStarted(sessionID: string): void {
		this.activeRuns += 1;
		this.lastBusySession = sessionID;
		if (this.pollTimer || this.permissionPollMs <= 0) return;
		this.pollTimer = setInterval(() => {
			void this.pollPermissions();
		}, this.permissionPollMs);
	}

	private runFinished(): void {
		this.activeRuns = Math.max(0, this.activeRuns - 1);
		if (this.activeRuns === 0 && this.pollTimer) {
			clearInterval(this.pollTimer);
			this.pollTimer = undefined;
		}
	}

	private lastBusySession = '';

	/** Poll pending approvals; emit permission.asked once per approval id. */
	async pollPermissions(): Promise<ToolApproval[]> {
		if (!this.surface) return [];
		const pending = await this.gw.approvals(this.surface, 'pending').catch(() => []);
		for (const approval of pending) {
			this.approvalByID.set(approval.id, approval); // refresh even if seen — nonce may rotate
			if (this.seenApprovals.has(approval.id)) continue;
			this.seenApprovals.add(approval.id);
			this.approvalSession.set(approval.id, this.lastBusySession);
			// Donor PermissionRequest is flat: permission is the tool name string,
			// patterns/always are arrays. sync.tsx stores event.properties directly.
			this.bus.emit('permission.asked', {
				id: approval.id,
				sessionID: this.lastBusySession,
				permission: approval.tool_name,
				patterns: approval.args ? [approval.args] : [],
				metadata: {
					risk_level: approval.risk_level,
					run_id: approval.run_id,
					summary: approval.summary || `${approval.tool_name} requires approval`,
					requested_at: approval.requested_at
				},
				always: []
			});
		}
		return pending;
	}

	listPermissions(): Array<{ id: string; sessionID: string }> {
		return [...this.approvalSession.entries()].map(([id, sessionID]) => ({ id, sessionID }));
	}

	/** Donor POST /permission/{id}/reply — reply "reject"/"never" rejects, else approves. */
	async replyPermission(approvalID: string, response: string): Promise<void> {
		const surface = await this.ensureSurface();
		const approval = this.approvalByID.get(approvalID);
		if (!approval) throw new Error(`unknown approval ${approvalID}`);
		const reply = response === 'reject' || response === 'never' ? 'reject' : response === 'always' ? 'always' : 'once';
		if (reply === 'reject') {
			await this.gw.decideApproval(surface, approval, 'reject');
		} else {
			// Donor "always" means "until restart" — ATLAS scope 'session'.
			await this.gw.decideApproval(surface, approval, 'approve', reply === 'always' ? 'session' : 'once');
		}
		this.approvalByID.delete(approvalID);
		this.bus.emit('permission.replied', {
			sessionID: this.approvalSession.get(approvalID) ?? '',
			requestID: approvalID,
			reply
		});
	}

	async dispose(): Promise<void> {
		this.stopHeartbeat();
		if (this.pollTimer) clearInterval(this.pollTimer);
		this.pollTimer = undefined;
		if (this.surface) {
			await this.gw.closeSurface(this.surface).catch(() => undefined);
			this.surface = null;
		}
	}
}
