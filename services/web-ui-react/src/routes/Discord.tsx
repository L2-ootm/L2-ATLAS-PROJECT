import { useCallback, useEffect, useState } from 'react';
import {
	Hash, Volume2, MessagesSquare, Megaphone, Mic, Power, Server, Users,
	Plus, Pencil, Trash2, Send, ShieldHalf, Check, X, Clock
} from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	discordStatus,
	startDiscord,
	stopDiscord,
	listGuilds,
	getGuildStructure,
	proposeDiscordWrite,
	listDiscordApprovals,
	approveDiscordWrite,
	rejectDiscordWrite,
	type DiscordSidecarStatus,
	type DiscordGuild,
	type DiscordStructure,
	type DiscordChannel,
	type DiscordRole,
	type DiscordApproval,
	type DiscordAction
} from '../lib/api';

// ── Discord — the vendored L2-BOT sidecar surface ────────────────────────────
// Read browser (sidecar lifecycle + guild → channels + roles) PLUS gated writes:
// every mutation is PROPOSED (never executed inline), lands in a Pending Approvals
// queue, and an operator clicks Approve to execute it via the sidecar. Data flows
// gateway → `atlas discord` CLI → bot loopback API; approval state lives in SQLite.

const STOPPED: DiscordSidecarStatus = { running: false, pid: null, ready: false, guild_count: 0 };

// A pending write the operator is composing (drives the modal). `null` = closed.
type ModalSpec =
	| { kind: 'create_channel' }
	| { kind: 'edit_channel'; ch: DiscordChannel }
	| { kind: 'delete_channel'; ch: DiscordChannel }
	| { kind: 'send_message'; ch: DiscordChannel }
	| { kind: 'permissions'; ch: DiscordChannel }
	| { kind: 'create_role' }
	| { kind: 'edit_role'; role: DiscordRole }
	| { kind: 'delete_role'; role: DiscordRole };

export default function Discord() {
	const [status, setStatus] = useState<DiscordSidecarStatus>(STOPPED);
	const [guilds, setGuilds] = useState<DiscordGuild[]>([]);
	const [selected, setSelected] = useState<string | null>(null);
	const [structure, setStructure] = useState<DiscordStructure | null>(null);
	const [approvals, setApprovals] = useState<DiscordApproval[]>([]);
	const [busy, setBusy] = useState(false);
	const [loadingStruct, setLoadingStruct] = useState(false);
	const [err, setErr] = useState<string | null>(null);
	const [modal, setModal] = useState<ModalSpec | null>(null);

	const refresh = useCallback(async () => {
		const [s, g, a] = await Promise.allSettled([discordStatus(), listGuilds(), listDiscordApprovals()]);
		setStatus(s.status === 'fulfilled' ? s.value : STOPPED);
		setGuilds(g.status === 'fulfilled' ? g.value : []);
		setApprovals(a.status === 'fulfilled' ? a.value : []);
	}, []);

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 10_000);
		return () => clearInterval(id);
	}, [refresh]);

	// Auto-select the first guild once the bot is ready and guilds load.
	useEffect(() => {
		if (!selected && guilds.length > 0) setSelected(guilds[0].id);
	}, [guilds, selected]);

	const loadStructure = useCallback(async (guildId: string) => {
		setLoadingStruct(true);
		setErr(null);
		try {
			setStructure(await getGuildStructure(guildId));
		} catch {
			setStructure(null);
			setErr('Could not load that guild — is the bot ready?');
		} finally {
			setLoadingStruct(false);
		}
	}, []);

	useEffect(() => {
		if (selected) void loadStructure(selected);
		else setStructure(null);
	}, [selected, loadStructure]);

	async function toggleSidecar() {
		setBusy(true);
		setErr(null);
		try {
			if (status.running) await stopDiscord();
			else await startDiscord();
			await refresh();
		} catch {
			setErr('Could not control the Discord sidecar — is the gateway running?');
		} finally {
			setBusy(false);
		}
	}

	// Submit a proposed write; it joins the approval queue (does NOT execute).
	async function propose(action: DiscordAction, params: Record<string, unknown>, target?: string | null) {
		if (!selected) return;
		setErr(null);
		try {
			await proposeDiscordWrite({ action, guild: selected, target: target ?? null, params });
			setModal(null);
			await refresh();
		} catch {
			setErr('Could not propose that action — is the gateway running?');
		}
	}

	async function decide(id: string, approve: boolean) {
		setErr(null);
		try {
			if (approve) await approveDiscordWrite(id);
			else await rejectDiscordWrite(id);
			await Promise.all([refresh(), selected ? loadStructure(selected) : Promise.resolve()]);
		} catch {
			setErr('Could not record that decision — is the gateway running?');
		}
	}

	return (
		<Page eyebrow="STRUCTURE" title="Discord">
			<SidecarPanel status={status} busy={busy} onToggle={toggleSidecar} />

			{err && (
				<div style={{ ...glassPanel({ padding: '12px 18px', marginBottom: 16 }), color: 'var(--l2-error)', fontSize: 12.5, fontFamily: 'var(--l2-font-mono)' }}>
					{err}
				</div>
			)}

			{approvals.length > 0 && <ApprovalsPanel approvals={approvals} onDecide={decide} />}

			{status.running ? (
				<div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, alignItems: 'start' }}>
					<GuildList guilds={guilds} selected={selected} ready={status.ready} onSelect={setSelected} />
					<StructureView
						structure={structure}
						loading={loadingStruct}
						canWrite={!!selected}
						onAction={setModal}
					/>
				</div>
			) : (
				<div style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13.5, lineHeight: 1.6 }}>
					The Discord sidecar is stopped. Start it above to browse guilds, channels, and roles.
				</div>
			)}

			{modal && structure && (
				<WriteModal spec={modal} roles={structure.roles} onClose={() => setModal(null)} onPropose={propose} />
			)}
		</Page>
	);
}

// ── sidecar lifecycle panel ──────────────────────────────────────────────────
function SidecarPanel({ status, busy, onToggle }: { status: DiscordSidecarStatus; busy: boolean; onToggle: () => void }) {
	const tone = status.running ? (status.ready ? 'var(--atlas-cyan)' : 'var(--atlas-bronze)') : 'var(--l2-error)';
	const label = status.running ? (status.ready ? 'READY' : 'STARTING') : 'STOPPED';
	return (
		<section style={{ ...glassPanel({ padding: '16px 18px', marginBottom: 16 }), display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
				<Server size={15} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.18em', color: 'var(--l2-fg-2)' }}>DISCORD SIDECAR</span>
				<span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
					<span style={{ width: 7, height: 7, borderRadius: '50%', background: tone, boxShadow: `0 0 8px ${tone}` }} />
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.1em', color: tone }}>{label}</span>
				</span>
				{status.running && (
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.1em', color: 'var(--l2-fg-3)' }}>
						{status.guild_count} guilds{status.pid != null ? ` · PID ${status.pid}` : ''}
					</span>
				)}
			</div>
			<button
				onClick={onToggle}
				disabled={busy}
				style={{
					display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 14px', borderRadius: 2,
					border: `1px solid ${status.running ? 'var(--l2-error)' : 'var(--l2-hairline)'}`,
					background: 'transparent', color: status.running ? 'var(--l2-error)' : 'var(--atlas-cyan)',
					fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.14em',
					cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.5 : 1
				}}
			>
				<Power size={13} strokeWidth={2} />
				{busy ? '…' : status.running ? 'STOP' : 'START'}
			</button>
		</section>
	);
}

// ── pending approvals queue ──────────────────────────────────────────────────
function statusTone(s: DiscordApproval['status']): string {
	if (s === 'executed') return 'var(--atlas-cyan)';
	if (s === 'failed') return 'var(--l2-error)';
	if (s === 'rejected') return 'var(--l2-fg-3)';
	return 'var(--atlas-bronze)';
}

function ApprovalsPanel({ approvals, onDecide }: { approvals: DiscordApproval[]; onDecide: (id: string, approve: boolean) => void }) {
	return (
		<section style={{ ...glassPanel({ overflow: 'hidden', marginBottom: 16 }) }}>
			<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<Clock size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>PENDING APPROVALS</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)' }}>{approvals.length}</span>
			</header>
			<div>
				{approvals.map((a, i) => (
					<div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
						<span style={{ width: 7, height: 7, borderRadius: '50%', background: statusTone(a.status), boxShadow: `0 0 7px ${statusTone(a.status)}`, flexShrink: 0 }} />
						<div style={{ minWidth: 0, flex: 1 }}>
							<div style={{ color: 'var(--l2-fg-1)', fontSize: 13 }}>{a.summary || a.action}</div>
							<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.1em', color: 'var(--l2-fg-3)' }}>
								{a.action} · {a.status}
							</div>
						</div>
						{a.status === 'pending' && (
							<div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
								<IconBtn tone="var(--atlas-cyan)" title="Approve" onClick={() => onDecide(a.id, true)}><Check size={13} /></IconBtn>
								<IconBtn tone="var(--l2-error)" title="Reject" onClick={() => onDecide(a.id, false)}><X size={13} /></IconBtn>
							</div>
						)}
					</div>
				))}
			</div>
		</section>
	);
}

// ── guild list ───────────────────────────────────────────────────────────────
function GuildList({ guilds, selected, ready, onSelect }: { guilds: DiscordGuild[]; selected: string | null; ready: boolean; onSelect: (id: string) => void }) {
	return (
		<section style={glassPanel({ overflow: 'hidden' })}>
			<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 16px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>GUILDS</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)' }}>{guilds.length}</span>
			</header>
			{guilds.length === 0 ? (
				<div style={{ padding: '20px 16px', color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.6 }}>
					{ready ? 'Bot is in no guilds.' : 'Waiting for the bot to connect…'}
				</div>
			) : (
				guilds.map((g, i) => {
					const active = g.id === selected;
					return (
						<button
							key={g.id}
							onClick={() => onSelect(g.id)}
							style={{
								display: 'block', width: '100%', textAlign: 'left', padding: '12px 16px',
								borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
								borderLeft: `2px solid ${active ? 'var(--atlas-celestial)' : 'transparent'}`,
								background: active ? 'rgba(79,139,255,0.08)' : 'transparent',
								color: active ? 'var(--l2-fg-1)' : 'var(--l2-fg-2)', fontSize: 13.5, cursor: 'pointer'
							}}
						>
							{g.name}
						</button>
					);
				})
			)}
		</section>
	);
}

// ── structure view ───────────────────────────────────────────────────────────
function channelIcon(type: string) {
	const c = 'var(--l2-fg-3)';
	if (type === 'voice') return <Volume2 size={13} color={c} />;
	if (type === 'forum') return <MessagesSquare size={13} color={c} />;
	if (type === 'announcement') return <Megaphone size={13} color={c} />;
	if (type === 'stage') return <Mic size={13} color={c} />;
	return <Hash size={13} color={c} />;
}

function IconBtn({ children, tone, title, onClick }: { children: React.ReactNode; tone: string; title: string; onClick: () => void }) {
	return (
		<button
			title={title}
			onClick={onClick}
			style={{
				display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26,
				borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: tone, cursor: 'pointer'
			}}
		>
			{children}
		</button>
	);
}

function ChannelRow({ ch, canWrite, onAction }: { ch: DiscordChannel; canWrite: boolean; onAction: (m: ModalSpec) => void }) {
	const [hover, setHover] = useState(false);
	return (
		<div
			onMouseEnter={() => setHover(true)}
			onMouseLeave={() => setHover(false)}
			style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0 5px 14px' }}
		>
			{channelIcon(ch.type)}
			<span style={{ color: 'var(--l2-fg-2)', fontSize: 13 }}>{ch.name}</span>
			{canWrite && (
				<div style={{ display: 'flex', gap: 6, marginLeft: 'auto', opacity: hover ? 1 : 0, transition: 'opacity 0.12s' }}>
					<IconBtn tone="var(--l2-fg-2)" title="Send embed" onClick={() => onAction({ kind: 'send_message', ch })}><Send size={12} /></IconBtn>
					<IconBtn tone="var(--l2-fg-2)" title="Permissions" onClick={() => onAction({ kind: 'permissions', ch })}><ShieldHalf size={12} /></IconBtn>
					<IconBtn tone="var(--l2-fg-2)" title="Edit channel" onClick={() => onAction({ kind: 'edit_channel', ch })}><Pencil size={12} /></IconBtn>
					<IconBtn tone="var(--l2-error)" title="Delete channel" onClick={() => onAction({ kind: 'delete_channel', ch })}><Trash2 size={12} /></IconBtn>
				</div>
			)}
		</div>
	);
}

function HeaderBtn({ label, onClick }: { label: string; onClick: () => void }) {
	return (
		<button
			onClick={onClick}
			style={{
				display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 2,
				border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--atlas-cyan)',
				fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.12em', cursor: 'pointer'
			}}
		>
			<Plus size={12} strokeWidth={2} />{label}
		</button>
	);
}

function StructureView({ structure, loading, canWrite, onAction }: {
	structure: DiscordStructure | null; loading: boolean; canWrite: boolean; onAction: (m: ModalSpec) => void;
}) {
	if (loading) return <section style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13 }}>Loading structure…</section>;
	if (!structure) return <section style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13 }}>Select a guild to view its channels and roles.</section>;
	return (
		<div style={{ display: 'grid', gap: 16 }}>
			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>CHANNELS</span>
					{canWrite && <span style={{ marginLeft: 10 }}><HeaderBtn label="NEW" onClick={() => onAction({ kind: 'create_channel' })} /></span>}
					<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)' }}>
						{structure.guild.name} · {structure.guild.member_count} members
					</span>
				</header>
				<div style={{ padding: '8px 18px 16px' }}>
					{structure.categories.length === 0 && structure.uncategorized.length === 0 && (
						<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, padding: '10px 0' }}>No visible channels.</div>
					)}
					{structure.categories.map((cat) => (
						<div key={cat.id} style={{ marginTop: 12 }}>
							<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.16em', color: 'var(--l2-fg-3)', textTransform: 'uppercase', marginBottom: 2 }}>
								{cat.name}
							</div>
							{cat.channels.map((ch) => <ChannelRow key={ch.id} ch={ch} canWrite={canWrite} onAction={onAction} />)}
						</div>
					))}
					{structure.uncategorized.length > 0 && (
						<div style={{ marginTop: 12 }}>
							<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.16em', color: 'var(--l2-fg-3)', textTransform: 'uppercase', marginBottom: 2 }}>
								Uncategorized
							</div>
							{structure.uncategorized.map((ch) => <ChannelRow key={ch.id} ch={ch} canWrite={canWrite} onAction={onAction} />)}
						</div>
					)}
				</div>
			</section>

			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<Users size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>ROLES</span>
					{canWrite && <span style={{ marginLeft: 10 }}><HeaderBtn label="NEW" onClick={() => onAction({ kind: 'create_role' })} /></span>}
					<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)' }}>{structure.roles.length}</span>
				</header>
				<div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '14px 18px' }}>
					{structure.roles.length === 0 ? (
						<span style={{ color: 'var(--l2-fg-3)', fontSize: 13 }}>No roles.</span>
					) : (
						structure.roles.map((r) => (
							<span key={r.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '5px 10px', borderRadius: 2, border: '1px solid var(--l2-hairline)', fontSize: 12.5, color: 'var(--l2-fg-2)' }}>
								<span style={{ width: 9, height: 9, borderRadius: '50%', background: r.color === '#000000' ? 'var(--l2-fg-3)' : r.color }} />
								{r.name}
								{canWrite && !r.managed && (
									<span style={{ display: 'inline-flex', gap: 4, marginLeft: 4 }}>
										<button title="Edit role" onClick={() => onAction({ kind: 'edit_role', role: r })} style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', padding: 0, display: 'inline-flex' }}><Pencil size={11} /></button>
										<button title="Delete role" onClick={() => onAction({ kind: 'delete_role', role: r })} style={{ background: 'none', border: 'none', color: 'var(--l2-error)', cursor: 'pointer', padding: 0, display: 'inline-flex' }}><Trash2 size={11} /></button>
									</span>
								)}
							</span>
						))
					)}
				</div>
			</section>
		</div>
	);
}

// ── write modal — composes a single proposed action ──────────────────────────
const FIELD = {
	display: 'block', width: '100%', boxSizing: 'border-box' as const, padding: '8px 10px', borderRadius: 2,
	border: '1px solid var(--l2-hairline)', background: 'rgba(0,0,0,0.2)', color: 'var(--l2-fg-1)',
	fontSize: 13, fontFamily: 'inherit', marginTop: 4
};
const LABEL = { fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.14em', color: 'var(--l2-fg-3)', textTransform: 'uppercase' as const };

// Curated permission flags exposed in the cockpit (discord.py names).
const ROLE_PERMS = ['administrator', 'manage_channels', 'manage_roles', 'manage_messages', 'kick_members', 'ban_members'];
const OVERWRITE_PERMS = ['view_channel', 'send_messages', 'manage_messages', 'connect', 'speak'];

function WriteModal({ spec, roles, onClose, onPropose }: {
	spec: ModalSpec;
	roles: DiscordRole[];
	onClose: () => void;
	onPropose: (action: DiscordAction, params: Record<string, unknown>, target?: string | null) => void;
}) {
	// One generic field bag; each modal kind reads the keys it needs.
	const [f, setF] = useState<Record<string, string>>({ type: 'text' });
	const [perms, setPerms] = useState<Record<string, boolean>>({});
	const [overwrite, setOverwrite] = useState<Record<string, 'allow' | 'deny' | ''>>({});
	const [roleId, setRoleId] = useState<string>(roles[0]?.id ?? '');
	const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

	const title: Record<ModalSpec['kind'], string> = {
		create_channel: 'New channel', edit_channel: 'Edit channel', delete_channel: 'Delete channel',
		send_message: 'Send embed', permissions: 'Channel permissions',
		create_role: 'New role', edit_role: 'Edit role', delete_role: 'Delete role'
	};

	function submit() {
		switch (spec.kind) {
			case 'create_channel':
				return onPropose('create_channel', { name: f.name, type: f.type || 'text', topic: f.topic || '' });
			case 'edit_channel':
				return onPropose('edit_channel', { name: f.name || spec.ch.name, topic: f.topic ?? '' }, spec.ch.id);
			case 'delete_channel':
				return onPropose('delete_channel', {}, spec.ch.id);
			case 'send_message':
				return onPropose('send_message', { embed: { title: f.title || undefined, description: f.body || undefined } }, spec.ch.id);
			case 'permissions': {
				const allow = Object.entries(overwrite).filter(([, v]) => v === 'allow').map(([k]) => k);
				const deny = Object.entries(overwrite).filter(([, v]) => v === 'deny').map(([k]) => k);
				return onPropose('set_permissions', { role_id: roleId, allow, deny }, spec.ch.id);
			}
			case 'create_role':
				return onPropose('create_role', { name: f.name, color_hex: f.color || '', permissions: perms });
			case 'edit_role':
				return onPropose('edit_role', { name: f.name || spec.role.name, color_hex: f.color ?? '' }, spec.role.id);
			case 'delete_role':
				return onPropose('delete_role', {}, spec.role.id);
		}
	}

	const isDelete = spec.kind === 'delete_channel' || spec.kind === 'delete_role';
	const targetName = spec.kind === 'delete_channel' || spec.kind === 'edit_channel' || spec.kind === 'send_message' || spec.kind === 'permissions'
		? spec.ch.name
		: spec.kind === 'delete_role' || spec.kind === 'edit_role' ? spec.role.name : '';

	return (
		<div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
			<div onClick={(e) => e.stopPropagation()} style={{ ...glassPanel({ padding: 0 }), width: 'min(440px, 92vw)', maxHeight: '86vh', overflow: 'auto' }}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '16px 20px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.18em', color: isDelete ? 'var(--l2-error)' : 'var(--atlas-bronze)' }}>
						{title[spec.kind].toUpperCase()}
					</span>
					{targetName && <span style={{ marginLeft: 'auto', color: 'var(--l2-fg-3)', fontSize: 12 }}>{targetName}</span>}
				</header>

				<div style={{ padding: '18px 20px', display: 'grid', gap: 14 }}>
					{isDelete && (
						<p style={{ color: 'var(--l2-fg-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>
							This proposes deleting <strong>{targetName}</strong>. It will not run until you approve it in the queue.
						</p>
					)}

					{(spec.kind === 'create_channel') && (
						<>
							<label><span style={LABEL}>Name</span><input style={FIELD} value={f.name || ''} onChange={(e) => set('name', e.target.value)} placeholder="general" /></label>
							<label><span style={LABEL}>Type</span>
								<select style={FIELD} value={f.type} onChange={(e) => set('type', e.target.value)}>
									<option value="text">text</option><option value="voice">voice</option>
									<option value="forum">forum</option><option value="category">category</option>
								</select>
							</label>
							<label><span style={LABEL}>Topic</span><input style={FIELD} value={f.topic || ''} onChange={(e) => set('topic', e.target.value)} placeholder="(optional)" /></label>
						</>
					)}

					{spec.kind === 'edit_channel' && (
						<>
							<label><span style={LABEL}>Name</span><input style={FIELD} value={f.name ?? spec.ch.name} onChange={(e) => set('name', e.target.value)} /></label>
							<label><span style={LABEL}>Topic</span><input style={FIELD} value={f.topic ?? (spec.ch.topic || '')} onChange={(e) => set('topic', e.target.value)} /></label>
						</>
					)}

					{spec.kind === 'send_message' && (
						<>
							<label><span style={LABEL}>Embed title</span><input style={FIELD} value={f.title || ''} onChange={(e) => set('title', e.target.value)} /></label>
							<label><span style={LABEL}>Embed body</span><textarea style={{ ...FIELD, minHeight: 90, resize: 'vertical' }} value={f.body || ''} onChange={(e) => set('body', e.target.value)} /></label>
						</>
					)}

					{spec.kind === 'permissions' && (
						<>
							<label><span style={LABEL}>Role</span>
								<select style={FIELD} value={roleId} onChange={(e) => setRoleId(e.target.value)}>
									{roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
								</select>
							</label>
							<div style={{ display: 'grid', gap: 6 }}>
								{OVERWRITE_PERMS.map((p) => (
									<div key={p} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
										<span style={{ flex: 1, color: 'var(--l2-fg-2)', fontSize: 12.5 }}>{p}</span>
										{(['allow', 'deny', ''] as const).map((v) => (
											<button key={v || 'inherit'} onClick={() => setOverwrite((o) => ({ ...o, [p]: v }))}
												style={{
													padding: '3px 9px', borderRadius: 2, fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, cursor: 'pointer',
													border: `1px solid ${(overwrite[p] || '') === v ? 'var(--atlas-cyan)' : 'var(--l2-hairline)'}`,
													background: (overwrite[p] || '') === v ? 'rgba(79,139,255,0.12)' : 'transparent',
													color: v === 'allow' ? 'var(--atlas-cyan)' : v === 'deny' ? 'var(--l2-error)' : 'var(--l2-fg-3)'
												}}>
												{v === '' ? 'inherit' : v}
											</button>
										))}
									</div>
								))}
							</div>
						</>
					)}

					{spec.kind === 'create_role' && (
						<>
							<label><span style={LABEL}>Name</span><input style={FIELD} value={f.name || ''} onChange={(e) => set('name', e.target.value)} placeholder="moderator" /></label>
							<label><span style={LABEL}>Color hex</span><input style={FIELD} value={f.color || ''} onChange={(e) => set('color', e.target.value)} placeholder="#5865F2" /></label>
							<div style={{ display: 'grid', gap: 6 }}>
								{ROLE_PERMS.map((p) => (
									<label key={p} style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--l2-fg-2)', fontSize: 12.5 }}>
										<input type="checkbox" checked={!!perms[p]} onChange={(e) => setPerms((o) => ({ ...o, [p]: e.target.checked }))} />
										{p}
									</label>
								))}
							</div>
						</>
					)}

					{spec.kind === 'edit_role' && (
						<>
							<label><span style={LABEL}>Name</span><input style={FIELD} value={f.name ?? spec.role.name} onChange={(e) => set('name', e.target.value)} /></label>
							<label><span style={LABEL}>Color hex</span><input style={FIELD} value={f.color ?? spec.role.color} onChange={(e) => set('color', e.target.value)} /></label>
						</>
					)}
				</div>

				<footer style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 20px', borderTop: '1px solid var(--l2-hairline)' }}>
					<button onClick={onClose} style={{ padding: '8px 14px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.12em', cursor: 'pointer' }}>
						CANCEL
					</button>
					<button onClick={submit} style={{ padding: '8px 16px', borderRadius: 2, border: `1px solid ${isDelete ? 'var(--l2-error)' : 'var(--atlas-cyan)'}`, background: 'transparent', color: isDelete ? 'var(--l2-error)' : 'var(--atlas-cyan)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.12em', cursor: 'pointer' }}>
						PROPOSE
					</button>
				</footer>
			</div>
		</div>
	);
}
