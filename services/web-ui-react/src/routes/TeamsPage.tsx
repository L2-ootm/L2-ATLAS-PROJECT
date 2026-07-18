import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Users, UserSquare2, ArrowUp, ArrowDown, Play, X } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel, HudLabel } from '../components/hud';
import {
	type AgentPreset,
	type Team,
	type TeamRun,
	type TeamChatMessage,
	listPresets,
	createPreset,
	deletePreset,
	listTeams,
	createTeam,
	deleteTeam,
	setTeamMembers,
	startTeamRun,
	getTeamRun,
	listTeamRunMessages
} from '../lib/api';

type Tab = 'teams' | 'presets';

const STATUS_COLORS: Record<string, string> = {
	queued: 'var(--l2-fg-3)',
	running: 'var(--atlas-celestial)',
	completed: 'var(--atlas-emerald, #3ecf8e)',
	failed: 'var(--atlas-crimson, #e5484d)',
	cancelled: 'var(--l2-fg-3)'
};

const fieldStyle: React.CSSProperties = {
	padding: '7px 10px',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'rgba(9,11,16,0.72)',
	color: 'var(--l2-fg-1)',
	fontSize: 12.5,
	width: '100%'
};

export default function TeamsPage() {
	const [tab, setTab] = useState<Tab>('teams');
	const [presets, setPresets] = useState<AgentPreset[]>([]);
	const [teams, setTeams] = useState<Team[]>([]);
	const [loading, setLoading] = useState(true);

	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const [presetsRes, teamsRes] = await Promise.all([listPresets(), listTeams()]);
			setPresets(presetsRes.presets || []);
			setTeams(teamsRes.teams || []);
		} catch {
			// Gateway offline
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	return (
		<Page eyebrow="MISSION" title="Teams">
			<div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
				<TabButton active={tab === 'teams'} onClick={() => setTab('teams')} icon={Users} label="TEAMS" />
				<TabButton active={tab === 'presets'} onClick={() => setTab('presets')} icon={UserSquare2} label="PRESETS" />
			</div>

			{loading ? (
				<GlassPanel style={{ padding: 48, display: 'grid', placeItems: 'center' }}>
					<HudLabel>LOADING…</HudLabel>
				</GlassPanel>
			) : tab === 'presets' ? (
				<PresetsTab presets={presets} onChange={refresh} />
			) : (
				<TeamsTab teams={teams} presets={presets} onChange={refresh} />
			)}
		</Page>
	);
}

function TabButton({
	active,
	onClick,
	icon: Icon,
	label
}: {
	active: boolean;
	onClick: () => void;
	icon: typeof Users;
	label: string;
}) {
	return (
		<button
			type="button"
			onClick={onClick}
			style={{
				display: 'flex',
				alignItems: 'center',
				gap: 6,
				padding: '7px 14px',
				borderRadius: 2,
				border: `1px solid ${active ? 'rgba(79,139,255,0.4)' : 'var(--l2-hairline)'}`,
				background: active ? 'rgba(79,139,255,0.1)' : 'transparent',
				color: active ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				letterSpacing: '0.14em',
				cursor: 'pointer'
			}}
		>
			<Icon size={13} />
			{label}
		</button>
	);
}

// --- Presets --------------------------------------------------------------

function PresetsTab({ presets, onChange }: { presets: AgentPreset[]; onChange: () => void }) {
	const [showForm, setShowForm] = useState(false);
	const [name, setName] = useState('');
	const [role, setRole] = useState('');
	const [goal, setGoal] = useState('');
	const [model, setModel] = useState('');
	const [error, setError] = useState('');

	async function submit() {
		setError('');
		try {
			await createPreset({ name, role_label: role, goal_template: goal, model: model || undefined });
			setName('');
			setRole('');
			setGoal('');
			setModel('');
			setShowForm(false);
			onChange();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to create preset');
		}
	}

	return (
		<div>
			<div style={{ marginBottom: 12 }}>
				<button type="button" onClick={() => setShowForm((v) => !v)} style={newButtonStyle}>
					<Plus size={13} /> NEW PRESET
				</button>
			</div>
			{showForm && (
				<GlassPanel style={{ padding: 14, marginBottom: 12 }}>
					<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
						<input style={fieldStyle} placeholder="Name (e.g. researcher)" value={name} onChange={(e) => setName(e.target.value)} />
						<input style={fieldStyle} placeholder="Role label (e.g. researcher)" value={role} onChange={(e) => setRole(e.target.value)} />
					</div>
					<textarea
						style={{ ...fieldStyle, minHeight: 60, marginBottom: 10, resize: 'vertical' }}
						placeholder="Goal template — what this preset is briefed to do"
						value={goal}
						onChange={(e) => setGoal(e.target.value)}
					/>
					<input
						style={{ ...fieldStyle, marginBottom: 10 }}
						placeholder="Model override (optional — inherits session model if blank)"
						value={model}
						onChange={(e) => setModel(e.target.value)}
					/>
					{error && <div style={{ color: 'var(--atlas-crimson, #e5484d)', fontSize: 12, marginBottom: 8 }}>{error}</div>}
					<div style={{ display: 'flex', gap: 8 }}>
						<button type="button" onClick={submit} style={primaryButtonStyle} disabled={!name || !role || !goal}>
							Create
						</button>
						<button type="button" onClick={() => setShowForm(false)} style={ghostButtonStyle}>
							Cancel
						</button>
					</div>
				</GlassPanel>
			)}
			{presets.length === 0 ? (
				<GlassPanel style={{ padding: 32, textAlign: 'center', color: 'var(--l2-fg-3)', fontSize: 13 }}>
					No presets yet. Create one to start building a team.
				</GlassPanel>
			) : (
				<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
					{presets.map((preset) => (
						<GlassPanel key={preset.id} style={{ padding: 14 }}>
							<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
								<div style={{ minWidth: 0 }}>
									<div style={{ fontSize: 14, fontWeight: 600, color: 'var(--l2-fg-1)' }}>{preset.name}</div>
									<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--atlas-celestial)', letterSpacing: '0.1em' }}>
										{preset.role_label}
									</div>
								</div>
								<button
									type="button"
									onClick={async () => {
										try {
											await deletePreset(preset.id);
											onChange();
										} catch {
											// still referenced by a team; leave it visible
										}
									}}
									style={iconButtonStyle}
									aria-label={`Delete ${preset.name}`}
								>
									<Trash2 size={13} />
								</button>
							</div>
							<div style={{ fontSize: 12, color: 'var(--l2-fg-3)', marginTop: 8, lineHeight: 1.45 }}>
								{preset.goal_template}
							</div>
							{preset.model && (
								<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)', marginTop: 8 }}>
									model: {preset.model}
								</div>
							)}
						</GlassPanel>
					))}
				</div>
			)}
		</div>
	);
}

// --- Teams ------------------------------------------------------------------

function TeamsTab({
	teams,
	presets,
	onChange
}: {
	teams: Team[];
	presets: AgentPreset[];
	onChange: () => void;
}) {
	const [showForm, setShowForm] = useState(false);
	const [name, setName] = useState('');
	const [error, setError] = useState('');

	async function submit() {
		setError('');
		try {
			await createTeam(name);
			setName('');
			setShowForm(false);
			onChange();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to create team');
		}
	}

	return (
		<div>
			<div style={{ marginBottom: 12 }}>
				<button type="button" onClick={() => setShowForm((v) => !v)} style={newButtonStyle}>
					<Plus size={13} /> NEW TEAM
				</button>
			</div>
			{showForm && (
				<GlassPanel style={{ padding: 14, marginBottom: 12 }}>
					<div style={{ display: 'flex', gap: 8 }}>
						<input style={fieldStyle} placeholder="Team name" value={name} onChange={(e) => setName(e.target.value)} />
						<button type="button" onClick={submit} style={primaryButtonStyle} disabled={!name}>
							Create
						</button>
						<button type="button" onClick={() => setShowForm(false)} style={ghostButtonStyle}>
							Cancel
						</button>
					</div>
					{error && <div style={{ color: 'var(--atlas-crimson, #e5484d)', fontSize: 12, marginTop: 8 }}>{error}</div>}
				</GlassPanel>
			)}
			{teams.length === 0 ? (
				<GlassPanel style={{ padding: 32, textAlign: 'center', color: 'var(--l2-fg-3)', fontSize: 13 }}>
					No teams yet. Create one, then add presets to its roster.
				</GlassPanel>
			) : (
				<div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
					{teams.map((team) => (
						<TeamCard key={team.id} team={team} presets={presets} onChange={onChange} />
					))}
				</div>
			)}
		</div>
	);
}

function TeamCard({
	team,
	presets,
	onChange
}: {
	team: Team;
	presets: AgentPreset[];
	onChange: () => void;
}) {
	const [editing, setEditing] = useState(false);
	const [roster, setRoster] = useState<string[]>(team.members.map((m) => m.id));
	const [running, setRunning] = useState<string | null>(null);
	const [kickoff, setKickoff] = useState('');
	const [showRun, setShowRun] = useState(false);

	function moveMember(index: number, direction: -1 | 1) {
		const next = [...roster];
		const target = index + direction;
		if (target < 0 || target >= next.length) return;
		[next[index], next[target]] = [next[target], next[index]];
		setRoster(next);
	}

	function toggleMember(presetId: string) {
		setRoster((prev) =>
			prev.includes(presetId) ? prev.filter((id) => id !== presetId) : [...prev, presetId]
		);
	}

	async function saveRoster() {
		if (roster.length === 0) return;
		await setTeamMembers(team.id, roster);
		setEditing(false);
		onChange();
	}

	async function launchRun() {
		if (!kickoff.trim()) return;
		const run = await startTeamRun(team.id, kickoff);
		setKickoff('');
		setShowRun(false);
		setRunning(run.id);
	}

	return (
		<GlassPanel style={{ padding: 14 }}>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
				<div>
					<div style={{ fontSize: 14, fontWeight: 600, color: 'var(--l2-fg-1)' }}>{team.name}</div>
					{team.description && (
						<div style={{ fontSize: 12, color: 'var(--l2-fg-3)', marginTop: 2 }}>{team.description}</div>
					)}
				</div>
				<div style={{ display: 'flex', gap: 6 }}>
					<button type="button" onClick={() => setShowRun((v) => !v)} style={iconButtonStyle} aria-label="Run team">
						<Play size={13} />
					</button>
					<button
						type="button"
						onClick={async () => {
							try {
								await deleteTeam(team.id);
								onChange();
							} catch {
								// active run in progress; leave visible
							}
						}}
						style={iconButtonStyle}
						aria-label={`Delete ${team.name}`}
					>
						<Trash2 size={13} />
					</button>
				</div>
			</div>

			<div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
				{team.members.map((member, index) => (
					<span
						key={member.id}
						style={{
							display: 'flex',
							alignItems: 'center',
							gap: 4,
							padding: '3px 8px',
							borderRadius: 2,
							border: '1px solid var(--l2-hairline)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							color: 'var(--l2-fg-2)'
						}}
					>
						{index + 1}. {member.name}
					</span>
				))}
				<button
					type="button"
					onClick={() => setEditing((v) => !v)}
					style={{ ...ghostButtonStyle, padding: '3px 8px', fontSize: 10 }}
				>
					{editing ? 'close roster' : 'edit roster'}
				</button>
			</div>

			{editing && (
				<div style={{ marginTop: 10, borderTop: '1px solid var(--l2-hairline)', paddingTop: 10 }}>
					{presets.length === 0 ? (
						<div style={{ fontSize: 12, color: 'var(--l2-fg-3)' }}>No presets exist yet — create some first.</div>
					) : (
						<div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
							{presets.map((preset) => {
								const idx = roster.indexOf(preset.id);
								const selected = idx !== -1;
								return (
									<div key={preset.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
										<label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--l2-fg-2)', flex: 1 }}>
											<input type="checkbox" checked={selected} onChange={() => toggleMember(preset.id)} />
											{preset.name} <span style={{ color: 'var(--l2-fg-3)' }}>({preset.role_label})</span>
										</label>
										{selected && (
											<div style={{ display: 'flex', gap: 2 }}>
												<button type="button" onClick={() => moveMember(idx, -1)} style={iconButtonStyle} aria-label="Move up">
													<ArrowUp size={11} />
												</button>
												<button type="button" onClick={() => moveMember(idx, 1)} style={iconButtonStyle} aria-label="Move down">
													<ArrowDown size={11} />
												</button>
											</div>
										)}
									</div>
								);
							})}
						</div>
					)}
					<div style={{ marginTop: 10 }}>
						<button type="button" onClick={saveRoster} style={primaryButtonStyle} disabled={roster.length === 0}>
							Save roster
						</button>
					</div>
				</div>
			)}

			{showRun && (
				<div style={{ marginTop: 10, borderTop: '1px solid var(--l2-hairline)', paddingTop: 10, display: 'flex', gap: 8 }}>
					<input
						style={fieldStyle}
						placeholder="Kickoff message for the team…"
						value={kickoff}
						onChange={(e) => setKickoff(e.target.value)}
					/>
					<button type="button" onClick={launchRun} style={primaryButtonStyle} disabled={!kickoff.trim()}>
						Start
					</button>
				</div>
			)}

			{running && <TeamRunTranscript teamRunId={running} onClose={() => setRunning(null)} />}
		</GlassPanel>
	);
}

function TeamRunTranscript({ teamRunId, onClose }: { teamRunId: string; onClose: () => void }) {
	const [run, setRun] = useState<TeamRun | null>(null);
	const [messages, setMessages] = useState<TeamChatMessage[]>([]);

	useEffect(() => {
		let cancelled = false;
		let timer: ReturnType<typeof setTimeout>;

		async function poll() {
			try {
				const [runRes, messagesRes] = await Promise.all([
					getTeamRun(teamRunId),
					listTeamRunMessages(teamRunId)
				]);
				if (cancelled) return;
				setRun(runRes);
				setMessages(messagesRes.messages || []);
				if (runRes.status === 'queued' || runRes.status === 'running') {
					timer = setTimeout(poll, 2000);
				}
			} catch {
				if (!cancelled) timer = setTimeout(poll, 3000);
			}
		}
		void poll();
		return () => {
			cancelled = true;
			clearTimeout(timer);
		};
	}, [teamRunId]);

	return (
		<div style={{ marginTop: 10, borderTop: '1px solid var(--l2-hairline)', paddingTop: 10 }}>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
				<span
					style={{
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10,
						letterSpacing: '0.14em',
						color: STATUS_COLORS[run?.status ?? 'queued']
					}}
				>
					{(run?.status ?? 'queued').toUpperCase()}
					{run && ` · ROUND ${run.current_round}/${run.max_rounds}`}
				</span>
				<button type="button" onClick={onClose} style={iconButtonStyle} aria-label="Close transcript">
					<X size={12} />
				</button>
			</div>
			<div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
				{messages.map((msg) => (
					<div key={msg.id} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
						<span
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 9.5,
								letterSpacing: '0.08em',
								color: msg.sender_actor_id ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
								flexShrink: 0,
								width: 90,
								overflow: 'hidden',
								textOverflow: 'ellipsis',
								whiteSpace: 'nowrap'
							}}
						>
							{msg.sender_role}
						</span>
						<span style={{ fontSize: 12.5, color: 'var(--l2-fg-1)', lineHeight: 1.45 }}>{msg.content}</span>
					</div>
				))}
			</div>
		</div>
	);
}

const newButtonStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 6,
	padding: '7px 14px',
	borderRadius: 2,
	border: '1px solid rgba(79,139,255,0.4)',
	background: 'rgba(79,139,255,0.1)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};

const primaryButtonStyle: React.CSSProperties = {
	padding: '7px 14px',
	borderRadius: 2,
	border: '1px solid rgba(79,139,255,0.4)',
	background: 'rgba(79,139,255,0.15)',
	color: 'var(--atlas-celestial)',
	fontSize: 12.5,
	cursor: 'pointer'
};

const ghostButtonStyle: React.CSSProperties = {
	padding: '7px 14px',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	fontSize: 12.5,
	cursor: 'pointer'
};

const iconButtonStyle: React.CSSProperties = {
	display: 'grid',
	placeItems: 'center',
	width: 24,
	height: 24,
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer'
};
