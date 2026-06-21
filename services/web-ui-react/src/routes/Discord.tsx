import { useCallback, useEffect, useState } from 'react';
import { Hash, Volume2, MessagesSquare, Megaphone, Mic, Power, Server, Users } from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	discordStatus,
	startDiscord,
	stopDiscord,
	listGuilds,
	getGuildStructure,
	type DiscordSidecarStatus,
	type DiscordGuild,
	type DiscordStructure,
	type DiscordChannel
} from '../lib/api';

// ── Discord — the vendored L2-BOT sidecar surface ────────────────────────────
// Read-only browser: sidecar lifecycle + guild → channels (by category) + roles.
// Data flows gateway → `atlas discord` CLI → the bot's loopback API. Write/manage
// actions (create/edit/delete channel & role) are a gated follow-up.

const STOPPED: DiscordSidecarStatus = { running: false, pid: null, ready: false, guild_count: 0 };

export default function Discord() {
	const [status, setStatus] = useState<DiscordSidecarStatus>(STOPPED);
	const [guilds, setGuilds] = useState<DiscordGuild[]>([]);
	const [selected, setSelected] = useState<string | null>(null);
	const [structure, setStructure] = useState<DiscordStructure | null>(null);
	const [busy, setBusy] = useState(false);
	const [loadingStruct, setLoadingStruct] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		const [s, g] = await Promise.allSettled([discordStatus(), listGuilds()]);
		const st = s.status === 'fulfilled' ? s.value : STOPPED;
		setStatus(st);
		setGuilds(g.status === 'fulfilled' ? g.value : []);
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

	return (
		<Page eyebrow="STRUCTURE" title="Discord">
			<SidecarPanel status={status} busy={busy} onToggle={toggleSidecar} />

			{err && (
				<div style={{ ...glassPanel({ padding: '12px 18px', marginBottom: 16 }), color: 'var(--l2-error)', fontSize: 12.5, fontFamily: 'var(--l2-font-mono)' }}>
					{err}
				</div>
			)}

			{status.running ? (
				<div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, alignItems: 'start' }}>
					<GuildList guilds={guilds} selected={selected} ready={status.ready} onSelect={setSelected} />
					<StructureView structure={structure} loading={loadingStruct} />
				</div>
			) : (
				<div style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13.5, lineHeight: 1.6 }}>
					The Discord sidecar is stopped. Start it above to browse guilds, channels, and roles.
				</div>
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

function ChannelRow({ ch }: { ch: DiscordChannel }) {
	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0 5px 14px' }}>
			{channelIcon(ch.type)}
			<span style={{ color: 'var(--l2-fg-2)', fontSize: 13 }}>{ch.name}</span>
		</div>
	);
}

function StructureView({ structure, loading }: { structure: DiscordStructure | null; loading: boolean }) {
	if (loading) return <section style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13 }}>Loading structure…</section>;
	if (!structure) return <section style={{ ...glassPanel({ padding: '24px 20px' }), color: 'var(--l2-fg-3)', fontSize: 13 }}>Select a guild to view its channels and roles.</section>;
	return (
		<div style={{ display: 'grid', gap: 16 }}>
			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>CHANNELS</span>
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
							{cat.channels.map((ch) => <ChannelRow key={ch.id} ch={ch} />)}
						</div>
					))}
					{structure.uncategorized.length > 0 && (
						<div style={{ marginTop: 12 }}>
							<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.16em', color: 'var(--l2-fg-3)', textTransform: 'uppercase', marginBottom: 2 }}>
								Uncategorized
							</div>
							{structure.uncategorized.map((ch) => <ChannelRow key={ch.id} ch={ch} />)}
						</div>
					)}
				</div>
			</section>

			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<Users size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>ROLES</span>
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
							</span>
						))
					)}
				</div>
			</section>
		</div>
	);
}
