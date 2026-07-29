import { useContext, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Circle, Network, RadioTower } from 'lucide-react';
import { AgentSurfaceContext } from '../../context/AgentSurfaceContext';
import {
	listChangeSetFiles,
	type ConsoleChatEvent,
	type EvidenceAvailability,
	type EvidenceFileChange
} from '../../lib/api';
import type { SubagentActivity } from '../../lib/subagents';
import { EvidenceInspector } from '../evidence/EvidenceInspector';
import { FileChangeReceipt } from '../evidence/FileChangeReceipt';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'orphaned']);
const NON_SUCCESS_ACTOR = new Set(['failed', 'cancelled', 'orphaned']);
const EVIDENCE_AVAILABILITY = new Set<EvidenceAvailability>([
	'available',
	'redacted',
	'partial',
	'binary',
	'too_large',
	'corrupt',
	'unavailable'
]);

interface OrchestrationEvidence {
	evidenceIds: string[];
	fileCount: number;
	additions: number;
	deletions: number;
	coverage: string;
	availability: EvidenceAvailability;
	redactionCount: number;
	ancestry: {
		actorId: string | null;
		parentActorId: string | null;
		teamRunId: string | null;
		goalId: string | null;
		runId: string | null;
	};
	cleanup: { status: string; error: string | null } | null;
	incident: { kind: string; status: string; reason: string | null } | null;
}

function record(value: unknown): Record<string, unknown> {
	if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
		return value as Record<string, unknown>;
	}
	if (typeof value === 'string') {
		try {
			const parsed = JSON.parse(value) as unknown;
			return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
				? parsed as Record<string, unknown>
				: {};
		} catch {
			return {};
		}
	}
	return {};
}

function goals(input: unknown): string[] {
	const value = record(input);
	const tasks = Array.isArray(value.tasks) ? value.tasks : [];
	const fromTasks = tasks
		.map((task) => record(task).goal)
		.filter((goal): goal is string => typeof goal === 'string' && goal.trim().length > 0);
	if (fromTasks.length > 0) return fromTasks;
	const direct = value.goal ?? value.task ?? value.prompt;
	return typeof direct === 'string' && direct.trim() ? [direct] : [];
}

function normalized(value: string): string {
	return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

function text(value: unknown): string | null {
	return typeof value === 'string' && value.trim() ? value : null;
}

function count(value: unknown): number {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : 0;
}

function orchestrationEvidence(
	event: ConsoleChatEvent,
	result?: ConsoleChatEvent
): OrchestrationEvidence | null {
	const sources = [result?.content, event.content, result?.text, event.input];
	let value: Record<string, unknown> | null = null;
	for (const source of sources) {
		const evidence = record(record(source).evidence);
		if (Object.keys(evidence).length > 0) {
			value = evidence;
			break;
		}
	}
	if (!value) return null;

	const ids = Array.isArray(value.evidence_ids) ? value.evidence_ids : [];
	const evidenceIds = [...new Set(ids.filter((id): id is string => typeof id === 'string' && id.length > 0))];
	const ancestry = record(value.ancestry);
	const rawCleanup = record(value.cleanup);
	const rawIncident = record(value.incident);
	const availability = EVIDENCE_AVAILABILITY.has(value.availability as EvidenceAvailability)
		? value.availability as EvidenceAvailability
		: 'unavailable';
	return {
		evidenceIds,
		fileCount: count(value.file_count),
		additions: count(value.additions),
		deletions: count(value.deletions),
		coverage: text(value.coverage) ?? 'unavailable',
		availability,
		redactionCount: count(value.redaction_count),
		ancestry: {
			actorId: text(ancestry.actor_id),
			parentActorId: text(ancestry.parent_actor_id),
			teamRunId: text(ancestry.team_run_id),
			goalId: text(ancestry.goal_id),
			runId: text(ancestry.run_id)
		},
		cleanup: Object.keys(rawCleanup).length > 0
			? { status: text(rawCleanup.status) ?? 'failed', error: text(rawCleanup.error) }
			: null,
		incident: Object.keys(rawIncident).length > 0
			? {
				kind: text(rawIncident.kind) ?? 'policy_incident',
				status: text(rawIncident.status) ?? 'denied',
				reason: text(rawIncident.reason)
			}
			: null
	};
}

function warningLabel(evidence: OrchestrationEvidence): string | null {
	if (evidence.incident) return evidence.incident.kind.replaceAll('_', ' ').toUpperCase();
	if (evidence.cleanup && evidence.cleanup.status !== 'complete') {
		return `CLEANUP ${evidence.cleanup.status.toUpperCase()}`;
	}
	if (evidence.availability !== 'available') return evidence.availability.toUpperCase();
	if (evidence.coverage !== 'complete' && evidence.coverage !== 'tool_only') {
		return evidence.coverage.toUpperCase();
	}
	return null;
}

export function OrchestrationCallCard({
	event,
	result,
	actors
}: {
	event: ConsoleChatEvent;
	result?: ConsoleChatEvent;
	actors: SubagentActivity[];
}) {
	const surface = useContext(AgentSurfaceContext);
	const [open, setOpen] = useState(false);
	const [files, setFiles] = useState<EvidenceFileChange[]>([]);
	const [filesStatus, setFilesStatus] = useState<'idle' | 'loading' | 'loaded' | 'unavailable'>('idle');
	const [selectedFile, setSelectedFile] = useState<EvidenceFileChange | null>(null);
	const plannedGoals = useMemo(() => goals(event.input), [event.input]);
	const evidence = useMemo(() => orchestrationEvidence(event, result), [event, result]);
	const relevantActors = useMemo(() => {
		if (plannedGoals.length === 0) return actors;
		const wanted = new Set(plannedGoals.map(normalized));
		return actors.filter((actor) => wanted.has(normalized(actor.goal)));
	}, [actors, plannedGoals]);
	const evidenceWarning = evidence ? warningLabel(evidence) : null;
	const failed = result?.type === 'failure'
		|| result?.is_error === true
		|| relevantActors.some((actor) => NON_SUCCESS_ACTOR.has(actor.phase))
		|| evidenceWarning !== null;
	const allActorsTerminal = relevantActors.length > 0 && relevantActors.every((actor) => TERMINAL.has(actor.phase));
	const done = (!!result && !failed) || allActorsTerminal;
	const label = (event.tool_name ?? 'orchestration').toUpperCase();
	const headline = plannedGoals[0] ?? ((event.tool_name ?? '').toLowerCase() === 'atlas_actor' ? 'Durable actor operation' : 'Parallel delegation');
	const Chevron = open ? ChevronDown : ChevronRight;
	const ownerToken = surface?.session?.owner_token ?? '';
	const actorId = evidence?.ancestry.actorId ?? relevantActors[0]?.id ?? null;
	const runId = evidence?.ancestry.runId ?? relevantActors[0]?.childRunId ?? 'unknown';
	const durationMs = relevantActors[0]?.durationSeconds == null
		? null
		: Math.round(relevantActors[0].durationSeconds * 1000);

	useEffect(() => {
		if (!open || !evidence || evidence.evidenceIds.length === 0) return;
		if (!ownerToken) {
			setFilesStatus('unavailable');
			return;
		}
		const controller = new AbortController();
		setFilesStatus('loading');
		Promise.all(
			evidence.evidenceIds.map((id) =>
				listChangeSetFiles(id, ownerToken, { limit: 100, signal: controller.signal })
			)
		)
			.then((pages) => {
				const unique = new Map<string, EvidenceFileChange>();
				for (const page of pages) {
					for (const file of page.files) unique.set(file.id, file);
				}
				setFiles([...unique.values()]);
				setFilesStatus('loaded');
			})
			.catch((reason: unknown) => {
				if (reason instanceof DOMException && reason.name === 'AbortError') return;
				setFilesStatus('unavailable');
			});
		return () => controller.abort();
	}, [evidence, open, ownerToken]);

	return (
		<section className="chat-orchestration-card" data-state={failed ? 'failed' : done ? 'done' : 'running'}>
			<button type="button" className="chat-orchestration-card__header" onClick={() => setOpen((value) => !value)}>
				<span className="chat-orchestration-card__glyph"><Network size={15} /></span>
				<span className="chat-orchestration-card__copy">
					<small>{label} · ACTOR PLANE</small>
					<strong>{headline}</strong>
				</span>
				<span className="chat-orchestration-card__state">
					<Circle size={7} fill="currentColor" stroke="none" />
					{failed ? 'ATTENTION' : done ? 'SETTLED' : 'DISPATCHING'}
				</span>
				<Chevron size={14} />
			</button>
			{evidence && (
				<div
					aria-label="Orchestration evidence summary"
					style={{
						display: 'flex',
						alignItems: 'center',
						gap: 10,
						padding: '7px 12px',
						borderTop: '1px solid var(--l2-hairline)',
						color: evidenceWarning ? 'var(--l2-warning, #f2b65a)' : 'var(--l2-fg-3)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10,
						letterSpacing: '0.06em'
					}}
				>
					<span>{evidence.evidenceIds.length} EVIDENCE SETS</span>
					<span>{evidence.fileCount} FILES</span>
					<span style={{ color: 'var(--l2-good, #46f0a0)' }}>+{evidence.additions}</span>
					<span style={{ color: 'var(--l2-error, #ff4d7d)' }}>−{evidence.deletions}</span>
					{evidence.coverage.toUpperCase() !== evidenceWarning && (
						<span>{evidence.coverage.toUpperCase()}</span>
					)}
					{evidence.redactionCount > 0 && <span>{evidence.redactionCount} REDACTIONS</span>}
					{evidenceWarning && <strong>{evidenceWarning}</strong>}
				</div>
			)}
			{open && (
				<div className="chat-orchestration-card__body">
					{plannedGoals.map((goal, index) => (
						<div key={`${goal}-${index}`} className="chat-orchestration-card__goal">
							<RadioTower size={13} />
							<span><small>ACTOR {String(index + 1).padStart(2, '0')}</small>{goal}</span>
						</div>
					))}
					{relevantActors.length > 0 && (
						<div className="chat-orchestration-card__actors">
							{relevantActors.map((actor) => <span key={actor.id} data-phase={actor.phase}>{actor.phase} · {actor.tool || actor.model || actor.id}</span>)}
						</div>
					)}
					{evidence && (
						<div style={{ display: 'grid', gap: 6 }}>
							{files.map((file) => (
								<FileChangeReceipt
									key={file.id}
									file={file}
									actorId={actorId}
									durationMs={durationMs}
									onInspect={setSelectedFile}
								/>
							))}
							{filesStatus === 'loading' && <span>LOADING EVIDENCE…</span>}
							{filesStatus === 'unavailable' && <span role="alert">EVIDENCE UNAVAILABLE</span>}
							{filesStatus === 'loaded' && files.length === 0 && (
								<span>NO FILE RECEIPTS IN REFERENCED SETS</span>
							)}
							{evidence.cleanup?.error && <span>{evidence.cleanup.error}</span>}
							{evidence.incident?.reason && <span>{evidence.incident.reason}</span>}
						</div>
					)}
				</div>
			)}
			{selectedFile && (
				<EvidenceInspector
					file={selectedFile}
					ownerToken={ownerToken}
					provenance={{
						actorId,
						runId,
						toolCallId: event.tool_call_id ?? null
					}}
					onClose={() => setSelectedFile(null)}
				/>
			)}
		</section>
	);
}
