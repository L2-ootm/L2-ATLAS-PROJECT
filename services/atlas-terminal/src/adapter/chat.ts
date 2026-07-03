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
import { GatewayClient, type RunEvent, type SurfaceSession, type ToolApproval } from './gateway';

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
	private readonly seenApprovals = new Set<string>();
	/** approvalID → donor sessionID that was busy when it surfaced. */
	private readonly approvalSession = new Map<string, string>();
	private activeRuns = 0;
	private pollTimer: ReturnType<typeof setInterval> | undefined;

	constructor(opts: ChatAdapterOptions) {
		this.gw = opts.gateway;
		this.bus = opts.bus;
		this.directory = opts.directory ?? process.cwd();
		this.atlasAgent = opts.atlasAgent ?? 'native';
		this.permissionPollMs = opts.permissionPollMs ?? 4000;
	}

	private nextID(prefix: string): string {
		this.counter += 1;
		return `${prefix}_${Date.now().toString(36)}${this.counter.toString(36).padStart(4, '0')}`;
	}

	private async ensureSurface(): Promise<SurfaceSession> {
		if (this.surface) return this.surface;
		// gateway SurfaceIdentity.kind literal: cli|tui|webui|api|native|test
		this.surface = await this.gw.createSurface('tui', 'global');
		return this.surface;
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
		this.bus.emit('session.created', { info: session });
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
		this.bus.emit('session.status', { sessionID, status: { type: 'idle' } });
		return true;
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
		this.bus.emit('message.updated', { info: userMsg.info });
		this.bus.emit('message.part.updated', { part: userPart });
		if (session.title === 'New session') {
			session.title = text.length > 64 ? `${text.slice(0, 61)}...` : text;
			this.bus.emit('session.updated', { info: session });
		}

		const surface = await this.ensureSurface();
		const mission = await this.gw.createMission(session.title.slice(0, 120), text);
		const runID = await this.gw.startRun(mission.id, this.atlasAgent, surface.id);

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
		this.bus.emit('message.updated', { info: assistant.info });
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
					error: { name: 'StreamError', data: { message: String(err) } }
				});
			})
			.finally(() => {
				if (!assistant.info.time.completed) {
					assistant.info.time.completed = Date.now();
					this.bus.emit('message.updated', { info: assistant.info });
				}
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
		this.bus.emit('message.part.updated', { part });
		return part;
	}

	private onRunEvent(sessionID: string, assistant: DonorMessage, event: RunEvent): void {
		if (event.name === 'end') {
			assistant.info.time.completed = Date.now();
			this.bus.emit('message.updated', { info: assistant.info });
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
					error: { name: 'RunFailed', data: { message: str('summary') || str('error') } }
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
		if (eventType === 'llm_call' || eventType === 'model_call_end') {
			if (textOrSummary) this.appendPart(assistant, { type: 'text', text: textOrSummary });
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
		this.bus.emit('message.part.updated', { part });
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
			if (this.seenApprovals.has(approval.id)) continue;
			this.seenApprovals.add(approval.id);
			this.approvalSession.set(approval.id, this.lastBusySession);
			this.bus.emit('permission.asked', {
				id: approval.id,
				sessionID: this.lastBusySession,
				permission: {
					id: approval.id,
					type: approval.tool_name,
					pattern: approval.args,
					title: approval.summary || `${approval.tool_name} requires approval`,
					metadata: { risk_level: approval.risk_level, run_id: approval.run_id },
					time: { created: Date.parse(approval.requested_at) || Date.now() }
				}
			});
		}
		return pending;
	}

	listPermissions(): Array<{ id: string; sessionID: string }> {
		return [...this.approvalSession.entries()].map(([id, sessionID]) => ({ id, sessionID }));
	}

	/** Donor POST /permission/{id}/reply — response "reject" rejects, else approves. */
	async replyPermission(approvalID: string, response: string): Promise<void> {
		const surface = await this.ensureSurface();
		const decision = response === 'reject' || response === 'never' ? 'reject' : 'approve';
		await this.gw.decideApproval(surface, approvalID, decision);
		this.bus.emit('permission.replied', {
			sessionID: this.approvalSession.get(approvalID) ?? '',
			permissionID: approvalID,
			response
		});
	}

	async dispose(): Promise<void> {
		if (this.pollTimer) clearInterval(this.pollTimer);
		this.pollTimer = undefined;
		if (this.surface) {
			await this.gw.closeSurface(this.surface).catch(() => undefined);
			this.surface = null;
		}
	}
}
