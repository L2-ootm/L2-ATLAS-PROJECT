import { useCallback, useEffect, useState } from 'react';
import type * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Crosshair, Plus, Pencil, Archive, Rocket, X, ListTree, Check, CornerDownRight } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import { GlassPanel } from '../components/GlassFx';
import GlowBorder from '../components/GlowBorder';
import { HudLabel, StatusBadge, AgentBadge } from '../components/hud';
import LiveBadge from '../components/LiveBadge';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import {
	getCurrentFocus,
	createFocus,
	archiveFocus,
	getFocusTree,
	createGoal,
	archiveGoal,
	createTask,
	setTaskStatus,
	createMission,
	startRun,
	listRuns,
	agentRuntimeLabel,
	type Focus,
	type GoalNode,
	type AgentRuntime,
	type RunWithMission
} from '../lib/api';

// Command Center (WP-4) — the execution-first surface over the autonomous loop.
// Three bands: the operator's Current Focus, a launcher that turns that focus
// into a background run, and a live activity feed. Reads degrade to empty/null
// against a pre-WP-2 gateway (api.ts swallows 404/503), and real background
// execution requires the rebuilt gateway — an old binary records the run only.

const AGENTS: AgentRuntime[] = ['native', 'claude_code'];
const FEED_POLL_MS = 6000;

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

function isActive(status: string): boolean {
	const s = status.toUpperCase();
	return s === 'RUNNING' || s === 'PENDING';
}

type FocusLoad = { s: 'loading' } | { s: 'ready'; focus: Focus | null } | { s: 'error' };

export default function Command() {
	const { online, epoch } = useGatewayHealth();
	const [focusLoad, setFocusLoad] = useState<FocusLoad>({ s: 'loading' });
	const [tree, setTree] = useState<GoalNode[]>([]);
	const [runs, setRuns] = useState<RunWithMission[]>([]);
	const [feedReady, setFeedReady] = useState(false);
	const [editing, setEditing] = useState<Focus | 'new' | null>(null);
	const [launchBusy, setLaunchBusy] = useState(false);
	const [launchErr, setLaunchErr] = useState<string | null>(null);
	const navigate = useNavigate();

	const focus = focusLoad.s === 'ready' ? focusLoad.focus : null;

	const refreshTree = useCallback(async (focusId: string | null) => {
		if (!focusId) {
			setTree([]);
			return;
		}
		try {
			const { tree } = await getFocusTree(focusId);
			setTree(tree);
		} catch {
			setTree([]);
		}
	}, []);

	const refreshFocus = useCallback(async () => {
		try {
			const { focus } = await getCurrentFocus();
			setFocusLoad({ s: 'ready', focus });
			await refreshTree(focus?.id ?? null);
		} catch {
			setFocusLoad({ s: 'error' });
		}
	}, [refreshTree]);

	const refreshFeed = useCallback(async () => {
		try {
			const { runs } = await listRuns(20);
			setRuns(runs);
			setFeedReady(true);
		} catch {
			/* keep the last good feed; the focus card surfaces offline state */
		}
	}, []);

	// Initial load + refetch on every (re)connect.
	useEffect(() => {
		void refreshFocus();
		void refreshFeed();
	}, [epoch, refreshFocus, refreshFeed]);

	// Poll the activity feed so background runs surface without a manual refresh.
	useEffect(() => {
		const id = window.setInterval(() => void refreshFeed(), FEED_POLL_MS);
		return () => window.clearInterval(id);
	}, [refreshFeed]);

	async function onArchive(f: Focus) {
		try {
			await archiveFocus(f.id);
			await refreshFocus();
		} catch {
			/* surfaced by the next focus refresh; no-op on transient failure */
		}
	}

	async function onLaunch(agent: AgentRuntime, prompt: string) {
		if (!focus) return;
		setLaunchBusy(true);
		setLaunchErr(null);
		try {
			const intent = prompt.trim() || focus.title;
			const { mission } = await createMission(focus.title, intent, focus.project_id ?? undefined);
			await startRun(mission.id, agent, /* execute */ true);
			await refreshFeed();
		} catch (e) {
			setLaunchErr(e instanceof Error ? e.message : String(e));
		} finally {
			setLaunchBusy(false);
		}
	}

	return (
		<Page
			eyebrow="MISSION"
			title="Command Center"
			actions={
				<>
					<LiveBadge connected={online === true} />
					<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={() => setEditing('new')}>
						{focus ? 'New Focus' : 'Set Focus'}
					</PrimaryButton>
				</>
			}
		>
			<div className="atlas-command-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
				<div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
					<FocusCard
						load={focusLoad}
						onEdit={(f) => setEditing(f)}
						onArchive={onArchive}
						onSet={() => setEditing('new')}
					/>
					{focus && <GoalsPanel focus={focus} tree={tree} onChanged={() => void refreshTree(focus.id)} />}
					<LaunchPanel focus={focus} busy={launchBusy} err={launchErr} onLaunch={onLaunch} />
				</div>
				<ActivityFeed
					runs={runs}
					ready={feedReady}
					offline={online === false}
					onOpen={(id) => navigate(`/runs/${id}`)}
				/>
			</div>

			{editing && (
				<FocusModal
					initial={editing === 'new' ? null : editing}
					onClose={() => setEditing(null)}
					onSaved={() => {
						setEditing(null);
						void refreshFocus();
					}}
				/>
			)}
		</Page>
	);
}

// ── Current Focus card ────────────────────────────────────────────────────────
function FocusCard({
	load,
	onEdit,
	onArchive,
	onSet
}: {
	load: FocusLoad;
	onEdit: (f: Focus) => void;
	onArchive: (f: Focus) => void;
	onSet: () => void;
}) {
	return (
		<GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<Crosshair size={14} strokeWidth={1.8} color="var(--atlas-bronze)" />
				<HudLabel style={{ color: 'var(--atlas-bronze)' }}>CURRENT FOCUS</HudLabel>
			</div>

			{load.s === 'loading' && <FocusSkeleton />}
			{load.s === 'error' && <Offline />}
			{load.s === 'ready' && load.focus === null && <NoFocus onSet={onSet} />}
			{load.s === 'ready' && load.focus !== null && (
				<FocusBody focus={load.focus} onEdit={() => onEdit(load.focus as Focus)} onArchive={() => onArchive(load.focus as Focus)} />
			)}
		</GlassPanel>
	);
}

function FocusBody({ focus, onEdit, onArchive }: { focus: Focus; onEdit: () => void; onArchive: () => void }) {
	return (
		<div data-topo="good" style={{ padding: '18px 18px 20px' }}>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14, marginBottom: 14 }}>
				<h2 style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 22, lineHeight: 1.2, color: 'var(--l2-fg-1)', margin: 0, minWidth: 0 }}>
					{focus.title}
				</h2>
				<div style={{ display: 'flex', gap: 8, flex: 'none' }}>
					<IconButton title="Edit focus" onClick={onEdit}>
						<Pencil size={14} strokeWidth={1.7} />
					</IconButton>
					<IconButton title="Archive focus" onClick={onArchive}>
						<Archive size={14} strokeWidth={1.7} />
					</IconButton>
				</div>
			</div>

			{focus.framework && (
				<div style={{ marginBottom: 16 }}>
					<FieldLabel>FRAMEWORK</FieldLabel>
					<span style={{ display: 'inline-block', padding: '4px 11px', borderRadius: 2, border: '1px solid rgba(70,240,160,0.32)', background: 'rgba(70,240,160,0.08)', color: 'var(--atlas-emerald)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.1em' }}>
						{focus.framework}
					</span>
				</div>
			)}

			<TagBlock label="PRIORITIES" items={focus.priorities} accent="158,90,62" />
			<TagBlock label="DRIVERS" items={focus.drivers} accent="79,139,255" />

			<div style={{ marginTop: 6, fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)', letterSpacing: '0.06em' }}>
				SET {rel(focus.created_at)}
			</div>
		</div>
	);
}

function TagBlock({ label, items, accent }: { label: string; items: string[]; accent: string }) {
	if (!items || items.length === 0) return null;
	return (
		<div style={{ marginBottom: 16 }}>
			<FieldLabel>{label}</FieldLabel>
			<div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
				{items.map((it, i) => (
					<span
						key={`${it}-${i}`}
						style={{
							padding: '4px 10px',
							borderRadius: 2,
							border: `1px solid rgba(${accent},0.28)`,
							background: `rgba(${accent},0.07)`,
							color: 'var(--l2-fg-1)',
							fontSize: 12.5
						}}
					>
						{it}
					</span>
				))}
			</div>
		</div>
	);
}

function NoFocus({ onSet }: { onSet: () => void }) {
	return (
		<div style={{ padding: '34px 24px', textAlign: 'center' }}>
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 19, color: 'var(--l2-fg-1)', marginBottom: 6 }}>No Current Focus</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, marginBottom: 18, maxWidth: 360, marginInline: 'auto', lineHeight: 1.5 }}>
				Set the operator's working focus — framework, priorities, drivers. The loop feeds it to every run as audited context.
			</div>
			<PrimaryButton icon={<Plus size={15} strokeWidth={2} />} onClick={onSet}>
				Set Focus
			</PrimaryButton>
		</div>
	);
}

function FocusSkeleton() {
	return (
		<div style={{ padding: '20px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
			<div style={sk('60%', 20)} />
			<div style={sk('30%', 12)} />
			<div style={{ display: 'flex', gap: 7 }}>
				<div style={sk(72, 12)} />
				<div style={sk(60, 12)} />
				<div style={sk(84, 12)} />
			</div>
		</div>
	);
}

// ── Goals panel (the goal tree under the Current Focus) ────────────────────────
function GoalsPanel({ focus, tree, onChanged }: { focus: Focus; tree: GoalNode[]; onChanged: () => void }) {
	const [adding, setAdding] = useState(false);
	const [busy, setBusy] = useState(false);

	async function addRoot(title: string) {
		setBusy(true);
		try {
			await createGoal({ title, focus: focus.id });
			onChanged();
		} finally {
			setBusy(false);
			setAdding(false);
		}
	}

	return (
		<GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 9, padding: '13px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
					<ListTree size={14} strokeWidth={1.8} color="var(--atlas-bronze)" />
					<HudLabel style={{ color: 'var(--atlas-bronze)' }}>GOALS</HudLabel>
				</span>
				<button
					type="button"
					onClick={() => setAdding((v) => !v)}
					title="Add goal"
					style={ghostIconStyle}
				>
					<Plus size={14} strokeWidth={2} />
				</button>
			</div>
			<div style={{ padding: tree.length === 0 && !adding ? '20px 18px' : '12px 10px 14px' }}>
				{adding && <InlineAdd placeholder="New goal…" busy={busy} onSubmit={addRoot} onCancel={() => setAdding(false)} />}
				{tree.length === 0 && !adding && (
					<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.5 }}>
						No goals yet. Add goals, sub-goals, and tasks — the loop synthesizes run instructions from this tree.
					</div>
				)}
				{tree.map((node) => (
					<GoalNodeView key={node.id} node={node} focusId={focus.id} depth={0} onChanged={onChanged} />
				))}
			</div>
		</GlassPanel>
	);
}

const GOAL_STATUS_COLOR: Record<string, string> = {
	open: 'var(--l2-fg-3)',
	active: 'var(--atlas-celestial)',
	done: 'var(--atlas-emerald)'
};

function GoalNodeView({ node, focusId, depth, onChanged }: { node: GoalNode; focusId: string; depth: number; onChanged: () => void }) {
	const [mode, setMode] = useState<null | 'task' | 'subgoal'>(null);
	const [busy, setBusy] = useState(false);

	async function addTask(title: string) {
		setBusy(true);
		try {
			await createTask(node.id, title);
			onChanged();
		} finally {
			setBusy(false);
			setMode(null);
		}
	}
	async function addSub(title: string) {
		setBusy(true);
		try {
			await createGoal({ title, focus: focusId, parent: node.id });
			onChanged();
		} finally {
			setBusy(false);
			setMode(null);
		}
	}
	async function toggleTask(taskId: string, status: string) {
		const next = status === 'todo' ? 'doing' : status === 'doing' ? 'done' : 'todo';
		await setTaskStatus(taskId, next as 'todo' | 'doing' | 'done');
		onChanged();
	}

	return (
		<div style={{ paddingLeft: depth > 0 ? 14 : 0, borderLeft: depth > 0 ? '1px solid var(--l2-hairline)' : 'none', marginLeft: depth > 0 ? 6 : 0, marginBottom: 6 }}>
			<div data-topo={node.status === 'active' ? 'info' : undefined} style={{ padding: '8px 8px', borderRadius: 2 }}>
				<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
					<span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: GOAL_STATUS_COLOR[node.status] ?? 'var(--l2-fg-3)', flex: 'none' }} />
					<span style={{ color: 'var(--l2-fg-1)', fontSize: 13.5, fontWeight: node.status === 'active' ? 600 : 400, flex: 1, minWidth: 0 }}>
						{node.title}
					</span>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 8.5, letterSpacing: '0.16em', color: GOAL_STATUS_COLOR[node.status] ?? 'var(--l2-fg-3)', textTransform: 'uppercase' }}>
						{node.status}
					</span>
					<button type="button" title="Add sub-goal" onClick={() => setMode(mode === 'subgoal' ? null : 'subgoal')} style={miniIconStyle}>
						<CornerDownRight size={12} strokeWidth={1.8} />
					</button>
					<button type="button" title="Add task" onClick={() => setMode(mode === 'task' ? null : 'task')} style={miniIconStyle}>
						<Plus size={13} strokeWidth={2} />
					</button>
					<button type="button" title="Archive goal" onClick={() => { void archiveGoal(node.id).then(onChanged); }} style={miniIconStyle}>
						<Archive size={12} strokeWidth={1.8} />
					</button>
				</div>
				{node.description && (
					<div style={{ color: 'var(--l2-fg-3)', fontSize: 12, marginTop: 4, marginLeft: 14, lineHeight: 1.45 }}>{node.description}</div>
				)}
				{node.tasks.length > 0 && (
					<div style={{ marginTop: 6, marginLeft: 14, display: 'flex', flexDirection: 'column', gap: 3 }}>
						{node.tasks.map((t) => (
							<button
								key={t.id}
								type="button"
								onClick={() => void toggleTask(t.id, t.status)}
								title={`Status: ${t.status} — click to advance`}
								style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left' }}
							>
								<span aria-hidden style={{
									width: 13, height: 13, borderRadius: 2, flex: 'none',
									border: `1px solid ${t.status === 'done' ? 'var(--atlas-emerald)' : 'var(--l2-hairline)'}`,
									background: t.status === 'done' ? 'rgba(70,240,160,0.18)' : t.status === 'doing' ? 'rgba(79,139,255,0.18)' : 'transparent',
									display: 'inline-flex', alignItems: 'center', justifyContent: 'center'
								}}>
									{t.status === 'done' && <Check size={10} strokeWidth={2.6} color="var(--atlas-emerald)" />}
									{t.status === 'doing' && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--atlas-celestial)' }} />}
								</span>
								<span style={{ fontSize: 12.5, color: t.status === 'done' ? 'var(--l2-fg-3)' : 'var(--l2-fg-2)', textDecoration: t.status === 'done' ? 'line-through' : 'none' }}>
									{t.title}
								</span>
							</button>
						))}
					</div>
				)}
				{node.observations.length > 0 && (
					<div style={{ marginTop: 6, marginLeft: 14, display: 'flex', flexDirection: 'column', gap: 2 }}>
						{node.observations.slice(0, 3).map((o) => (
							<div key={o.id} style={{ fontSize: 11, color: 'var(--l2-fg-3)', fontFamily: 'var(--l2-font-mono)', lineHeight: 1.4 }}>
								<span style={{ color: 'var(--atlas-bronze)' }}>· {o.source}:</span> {o.body}
							</div>
						))}
					</div>
				)}
				{mode && (
					<div style={{ marginLeft: 14, marginTop: 6 }}>
						<InlineAdd
							placeholder={mode === 'task' ? 'New task…' : 'New sub-goal…'}
							busy={busy}
							onSubmit={mode === 'task' ? addTask : addSub}
							onCancel={() => setMode(null)}
						/>
					</div>
				)}
			</div>
			{node.children.map((child) => (
				<GoalNodeView key={child.id} node={child} focusId={focusId} depth={depth + 1} onChanged={onChanged} />
			))}
		</div>
	);
}

function InlineAdd({ placeholder, busy, onSubmit, onCancel }: { placeholder: string; busy: boolean; onSubmit: (v: string) => void; onCancel: () => void }) {
	const [value, setValue] = useState('');
	function submit() {
		const v = value.trim();
		if (v) onSubmit(v);
	}
	return (
		<div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
			<input
				autoFocus
				value={value}
				disabled={busy}
				onChange={(e) => setValue(e.target.value)}
				onKeyDown={(e) => {
					if (e.key === 'Enter') submit();
					if (e.key === 'Escape') onCancel();
				}}
				placeholder={placeholder}
				style={{ flex: 1, minWidth: 0, height: 32, borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'rgba(9,11,16,0.72)', color: 'var(--l2-fg-1)', fontSize: 12.5, padding: '0 10px', outline: 'none' }}
			/>
			<button type="button" onClick={submit} disabled={busy} style={{ ...ghostIconStyle, borderColor: 'rgba(70,240,160,0.4)', color: 'var(--atlas-emerald)' }} title="Add">
				<Check size={14} strokeWidth={2.2} />
			</button>
			<button type="button" onClick={onCancel} style={ghostIconStyle} title="Cancel">
				<X size={14} strokeWidth={2} />
			</button>
		</div>
	);
}

const ghostIconStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	width: 28,
	height: 28,
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer'
};

const miniIconStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	width: 22,
	height: 22,
	borderRadius: 2,
	border: 'none',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer',
	flex: 'none'
};

// ── Launch panel (closes the loop) ────────────────────────────────────────────
function LaunchPanel({
	focus,
	busy,
	err,
	onLaunch
}: {
	focus: Focus | null;
	busy: boolean;
	err: string | null;
	onLaunch: (agent: AgentRuntime, prompt: string) => void;
}) {
	const [agent, setAgent] = useState<AgentRuntime>('native');
	const [prompt, setPrompt] = useState('');
	const disabled = focus === null || busy;

	return (
		<GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<Rocket size={14} strokeWidth={1.8} color="var(--atlas-celestial)" />
				<HudLabel style={{ color: 'var(--atlas-celestial)' }}>LAUNCH AUTONOMOUS RUN</HudLabel>
			</div>
			<div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
				<div>
					<FieldLabel>AGENT</FieldLabel>
					<div style={{ display: 'flex', gap: 7 }}>
						{AGENTS.map((a) => (
							<button
								key={a}
								type="button"
								onClick={() => setAgent(a)}
								style={{
									padding: '8px 14px',
									borderRadius: 2,
									border: `1px solid ${a === agent ? 'rgba(79,139,255,0.5)' : 'var(--l2-hairline)'}`,
									background: a === agent ? 'rgba(79,139,255,0.12)' : 'transparent',
									color: a === agent ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 10.5,
									letterSpacing: '0.14em',
									cursor: 'pointer',
									transition: 'border-color var(--l2-duration-xs) var(--l2-ease)'
								}}
							>
								{agentRuntimeLabel(a)}
							</button>
						))}
					</div>
				</div>
				<div>
					<FieldLabel>INTENT (OPTIONAL)</FieldLabel>
					<TopoInput
						value={prompt}
						onChange={setPrompt}
						multiline
						rows={3}
						tone="info"
						quiet
						ariaLabel="Run intent"
						placeholder={focus ? `Defaults to the focus: “${focus.title}”` : 'Set a focus to launch a run'}
					/>
				</div>
				{err && <div style={{ color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{err}</div>}
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)', letterSpacing: '0.06em', lineHeight: 1.4 }}>
						{focus ? 'CREATES A MISSION + BACKGROUND RUN FROM THIS FOCUS' : 'NO FOCUS SET'}
					</span>
					<LaunchButton disabled={disabled} busy={busy} onClick={() => onLaunch(agent, prompt)} />
				</div>
			</div>
		</GlassPanel>
	);
}

// ── Activity feed ─────────────────────────────────────────────────────────────
function ActivityFeed({
	runs,
	ready,
	offline,
	onOpen
}: {
	runs: RunWithMission[];
	ready: boolean;
	offline: boolean;
	onOpen: (id: string) => void;
}) {
	const liveCount = runs.filter((r) => isActive(r.status)).length;
	return (
		<GlassPanel style={{ padding: 0, overflow: 'hidden', position: 'sticky', top: 8 }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '13px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<HudLabel>LIVE ACTIVITY</HudLabel>
				<LiveBadge connected={liveCount > 0} />
			</div>
			{!ready && !offline && <FeedSkeleton />}
			{offline && !ready && <Offline />}
			{ready && runs.length === 0 && (
				<div style={{ padding: '30px 22px', textAlign: 'center', color: 'var(--l2-fg-3)', fontSize: 13 }}>
					No runs yet. Launch one to populate the loop.
				</div>
			)}
			{runs.length > 0 && (
				<div style={{ maxHeight: 520, overflowY: 'auto' }}>
					{runs.map((r, i) => (
						<FeedRow key={r.id} r={r} first={i === 0} onClick={() => onOpen(r.id)} />
					))}
				</div>
			)}
		</GlassPanel>
	);
}

function FeedRow({ r, first, onClick }: { r: RunWithMission; first: boolean; onClick: () => void }) {
	const active = isActive(r.status);
	const inner = (
		<div
			role="button"
			tabIndex={0}
			data-topo={active ? 'info' : 'atlas'}
			onClick={onClick}
			onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
			style={{
				display: 'flex',
				flexDirection: 'column',
				gap: 8,
				padding: '13px 18px',
				borderTop: first || active ? 'none' : '1px solid var(--l2-hairline)',
				cursor: 'pointer',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
				<span style={{ color: 'var(--l2-fg-1)', fontSize: 13.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
					{r.mission_title}
				</span>
				<span style={{ display: 'flex', alignItems: 'center', gap: 7, flex: 'none' }}>
					<StatusBadge status={r.status} />
					{active && <LiveBadge connected />}
				</span>
			</div>
			<div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)' }}>
				<span style={{ fontVariantNumeric: 'tabular-nums' }}>{r.id.slice(0, 8)}</span>
				{r.agent_runtime && <AgentBadge agent={r.agent_runtime as AgentRuntime} />}
				<span style={{ marginLeft: 'auto' }}>{rel(r.started_at)}</span>
			</div>
		</div>
	);
	// Running/pending rows get the electric border treatment, matching the Runs feed.
	return active ? <GlowBorder active>{inner}</GlowBorder> : inner;
}

function FeedSkeleton() {
	return (
		<div>
			{Array.from({ length: 5 }).map((_, i) => (
				<div key={i} style={{ padding: '14px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)', display: 'flex', flexDirection: 'column', gap: 8 }}>
					<div style={sk(`${55 + ((i * 9) % 30)}%`, 13)} />
					<div style={sk('40%', 10)} />
				</div>
			))}
		</div>
	);
}

// ── Focus create / edit modal ─────────────────────────────────────────────────
function FocusModal({ initial, onClose, onSaved }: { initial: Focus | null; onClose: () => void; onSaved: () => void }) {
	const [title, setTitle] = useState(initial?.title ?? '');
	const [framework, setFramework] = useState(initial?.framework ?? '');
	const [priorities, setPriorities] = useState((initial?.priorities ?? []).join(', '));
	const [drivers, setDrivers] = useState((initial?.drivers ?? []).join(', '));
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);
	const isEdit = initial !== null;

	function splitCsv(raw: string): string[] {
		return raw.split(',').map((s) => s.trim()).filter(Boolean);
	}

	async function submit() {
		if (!title.trim()) {
			setErr('A focus statement is required.');
			return;
		}
		setBusy(true);
		setErr(null);
		try {
			// create_focus archives the prior active focus on the backend, so an
			// "edit" is modelled as creating a fresh Current Focus (single-active
			// invariant). The prior row is preserved as archived for provenance.
			await createFocus({
				title: title.trim(),
				framework: framework.trim() || undefined,
				priorities: splitCsv(priorities),
				drivers: splitCsv(drivers),
				project: initial?.project_id ?? undefined
			});
			onSaved();
		} catch (e) {
			setErr(e instanceof Error ? e.message : 'Could not save the focus — is the gateway running?');
			setBusy(false);
		}
	}

	return (
		<div
			onClick={onClose}
			style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'grid', placeItems: 'center', background: 'rgba(5,6,10,0.76)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
		>
			<div onClick={(e) => e.stopPropagation()} style={{ width: 'min(560px, 92vw)' }}>
				<div style={{ position: 'relative', borderRadius: 2, overflow: 'hidden', background: 'linear-gradient(135deg, rgba(237,234,224,0.08), rgba(13,16,24,0.62) 40%, rgba(70,240,160,0.06))', border: '1px solid var(--l2-hairline)', boxShadow: '0 28px 90px rgba(0,0,0,0.58)' }}>
					<span aria-hidden="true" style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)', opacity: 0.5, zIndex: 2 }} />
					<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--l2-hairline)' }}>
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
							{isEdit ? 'UPDATE FOCUS' : 'SET CURRENT FOCUS'}
						</span>
						<button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', display: 'flex' }}>
							<X size={16} />
						</button>
					</div>
					<div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
						<Field label="FOCUS STATEMENT">
							<TopoInput value={title} onChange={setTitle} placeholder="What are we driving toward?" tone="good" ariaLabel="Focus statement" autoFocus quiet />
						</Field>
						<Field label="FRAMEWORK (OPTIONAL)">
							<TopoInput value={framework} onChange={setFramework} placeholder="e.g. GSD, OKR" tone="good" ariaLabel="Framework" quiet />
						</Field>
						<Field label="PRIORITIES (COMMA-SEPARATED)">
							<TopoInput value={priorities} onChange={setPriorities} placeholder="latency, trust, coverage" tone="info" ariaLabel="Priorities" quiet />
						</Field>
						<Field label="DRIVERS (COMMA-SEPARATED)">
							<TopoInput value={drivers} onChange={setDrivers} placeholder="operator, deadline" tone="info" ariaLabel="Drivers" quiet />
						</Field>
						{isEdit && (
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, lineHeight: 1.5 }}>
								Saving replaces the Current Focus; the prior one is archived for provenance.
							</div>
						)}
						{err && <div style={{ color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{err}</div>}
					</div>
					<div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 20px', borderTop: '1px solid var(--l2-hairline)' }}>
						<button onClick={onClose} style={{ padding: '9px 16px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em', cursor: 'pointer' }}>
							CANCEL
						</button>
						<PrimaryButton onClick={submit} disabled={busy}>
							{busy ? 'SAVING…' : isEdit ? 'UPDATE' : 'SET FOCUS'}
						</PrimaryButton>
					</div>
				</div>
			</div>
		</div>
	);
}

// ── shared bits ───────────────────────────────────────────────────────────────
function FieldLabel({ children }: { children: React.ReactNode }) {
	return (
		<span style={{ display: 'block', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)', marginBottom: 8 }}>
			{children}
		</span>
	);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div style={{ display: 'block' }}>
			<span style={{ display: 'block', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)', marginBottom: 7 }}>{label}</span>
			{children}
		</div>
	);
}

const sk = (w: number | string, h: number): React.CSSProperties => ({
	height: h,
	width: w,
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});

function Offline() {
	return (
		<div style={{ padding: '24px 18px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
			<span style={{ width: 7, height: 7, marginTop: 4, borderRadius: '50%', background: 'var(--l2-error)', boxShadow: '0 0 9px rgba(255,0,85,0.55)', flex: 'none' }} />
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 4 }}>Gateway unavailable</div>
				<div style={{ color: 'var(--l2-fg-3)', fontSize: 11.5, fontFamily: 'var(--l2-font-mono)', letterSpacing: '0.04em' }}>
					NO RESPONSE FROM 127.0.0.1:8484 — START THE GATEWAY
				</div>
			</div>
		</div>
	);
}

function PrimaryButton({ children, icon, onClick, disabled }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void; disabled?: boolean }) {
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '9px 16px',
				borderRadius: 2,
				border: '1px solid rgba(70,240,160,0.4)',
				background: 'rgba(70,240,160,0.12)',
				color: 'var(--atlas-emerald, #46f0a0)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1,
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => !disabled && (e.currentTarget.style.background = 'rgba(70,240,160,0.2)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(70,240,160,0.12)')}
		>
			{icon}
			{children}
		</button>
	);
}

function LaunchButton({ disabled, busy, onClick }: { disabled: boolean; busy: boolean; onClick: () => void }) {
	return (
		<button
			type="button"
			onClick={onClick}
			disabled={disabled}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '10px 18px',
				borderRadius: 2,
				border: '1px solid rgba(79,139,255,0.45)',
				background: 'linear-gradient(180deg, rgba(79,139,255,0.18), rgba(79,139,255,0.07))',
				color: 'var(--atlas-celestial)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.45 : 1,
				transition: 'border-color 150ms var(--l2-ease), background 150ms var(--l2-ease), transform 150ms var(--l2-ease)'
			}}
			onMouseEnter={(e) => {
				if (disabled) return;
				e.currentTarget.style.borderColor = 'rgba(79,139,255,0.75)';
				e.currentTarget.style.transform = 'translateY(-1px)';
			}}
			onMouseLeave={(e) => {
				e.currentTarget.style.borderColor = 'rgba(79,139,255,0.45)';
				e.currentTarget.style.transform = 'none';
			}}
		>
			<Rocket size={14} strokeWidth={1.8} />
			{busy ? 'LAUNCHING…' : 'LAUNCH'}
		</button>
	);
}

function IconButton({ children, title, onClick }: { children: React.ReactNode; title: string; onClick: () => void }) {
	return (
		<button
			type="button"
			title={title}
			aria-label={title}
			onClick={onClick}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				justifyContent: 'center',
				width: 30,
				height: 30,
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				background: 'transparent',
				color: 'var(--l2-fg-3)',
				cursor: 'pointer',
				transition: 'border-color var(--l2-duration-xs) var(--l2-ease), color var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => {
				e.currentTarget.style.borderColor = 'rgba(70,240,160,0.4)';
				e.currentTarget.style.color = 'var(--l2-fg-1)';
			}}
			onMouseLeave={(e) => {
				e.currentTarget.style.borderColor = 'var(--l2-hairline)';
				e.currentTarget.style.color = 'var(--l2-fg-3)';
			}}
		>
			{children}
		</button>
	);
}
