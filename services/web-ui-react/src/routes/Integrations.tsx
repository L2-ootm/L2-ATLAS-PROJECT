import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cable } from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	checkHealth,
	getToolManifests,
	listChannels,
	listModules,
	messagingGatewayStatus,
	discordStatus,
	cashflowStatus,
	type ToolManifest
} from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import sealMark from '../brand/assets/seal.webp';

// ── Integrations — /integrations — what ATLAS is wired to ─────────────────────
// A read-only posture board across every adapter / sidecar / tool surface: the
// REST gateway, the developer tool manifests (10.0.4), messaging channels + the
// foundation gateway, the Discord sidecar, and the cashflow module. INTERIM
// (HARNESS-WIRING §5): no single /v1/integrations endpoint yet, so this composes
// the live status calls each surface already exposes. Honest connection state.

type State = 'online' | 'offline' | 'degraded' | 'unknown';

interface IntegrationRow {
	name: string;
	kind: string;
	state: State;
	posture: string;
	detail: string;
	tone?: string;
	to?: string;
}

type Load =
	| { s: 'loading' }
	| { s: 'ready'; rows: IntegrationRow[]; offline: boolean }
	| { s: 'error' };

const STATE_TONE: Record<State, string> = {
	online: 'var(--atlas-cyan)',
	offline: 'var(--l2-fg-3)',
	degraded: 'var(--l2-error)',
	unknown: 'var(--l2-fg-3)'
};

export default function Integrations() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const { epoch } = useGatewayHealth();
	const nav = useNavigate();

	const refresh = useCallback(async () => {
		const [h, tools, channels, modules, msg, dis, cash] = await Promise.allSettled([
			checkHealth(),
			getToolManifests(),
			listChannels(),
			listModules(),
			messagingGatewayStatus(),
			discordStatus(),
			cashflowStatus()
		]);

		const gatewayOnline = h.status === 'fulfilled';
		if (!gatewayOnline) {
			setLoad({ s: 'ready', rows: [gatewayRow(false, null)], offline: true });
			return;
		}

		const toolsKnown = tools.status === 'fulfilled';
		const channelsKnown = channels.status === 'fulfilled';
		const modulesKnown = modules.status === 'fulfilled';
		const messagingKnown = msg.status === 'fulfilled';
		const discordKnown = dis.status === 'fulfilled';
		const cashflowKnown = cash.status === 'fulfilled';
		const toolList: ToolManifest[] = toolsKnown ? tools.value : [];
		const channelList = channelsKnown ? channels.value.channels : [];
		const moduleList = modulesKnown ? modules.value.modules : [];
		const msgGw = messagingKnown ? msg.value : { running: false, pid: null };
		const discord = discordKnown ? dis.value : { running: false, ready: false, guild_count: 0, pid: null };
		const cashflow = cashflowKnown ? cash.value : { running: false, backend: 'local' };

		const enabledChannels = channelList.filter((c) => c.enabled).length;
		const writeTools = toolList.filter((t) => t.risk_level !== 'read').length;
		const activeModules = moduleList.filter((m) => m.status === 'active').length;

		const rows: IntegrationRow[] = [
			gatewayRow(true, h.value),
			{
				name: 'Developer Tools',
				kind: 'tool registry',
				state: toolsKnown && toolList.length > 0 ? 'online' : 'unknown',
				posture: writeTools > 0 ? 'approval-gated' : 'read-only',
				detail: toolsKnown ? `${toolList.length} registered · ${writeTools} write/shell gated` : 'registry status unavailable',
				to: '/system'
			},
			{
				name: 'Messaging Channels',
				kind: 'foundation adapter',
				state: !channelsKnown || !messagingKnown ? 'unknown' : msgGw.running ? 'online' : enabledChannels > 0 ? 'degraded' : 'offline',
				posture: 'config-gated',
				detail: !channelsKnown || !messagingKnown
					? 'channel or gateway status unavailable'
					: channelList.length === 0
					? 'none configured'
					: `${enabledChannels}/${channelList.length} enabled · gateway ${msgGw.running ? 'running' : 'stopped'}`,
				to: '/system'
			},
			{
				name: 'Discord',
				kind: 'sidecar',
				state: !discordKnown ? 'unknown' : discord.running ? (discord.ready ? 'online' : 'degraded') : 'offline',
				posture: 'approval-gated writes',
				detail: !discordKnown ? 'sidecar status unavailable' : discord.running ? `${discord.guild_count} guild(s) · ${discord.ready ? 'ready' : 'connecting'}` : 'sidecar stopped',
				to: '/discord'
			},
			{
				name: 'Cashflow',
				kind: 'module',
				state: !cashflowKnown ? 'unknown' : cashflow.running ? 'online' : 'offline',
				posture: 'optional module',
				detail: !cashflowKnown ? 'module status unavailable' : cashflow.running ? `running · ${cashflow.backend} backend` : 'stopped',
				to: '/cashflow'
			},
			{
				name: 'Optional Modules',
				kind: 'module registry',
				state: !modulesKnown ? 'unknown' : activeModules > 0 ? 'online' : 'offline',
				posture: 'operator-activated',
				detail: !modulesKnown ? 'module registry unavailable' : moduleList.length === 0 ? 'none available' : `${activeModules}/${moduleList.length} active`,
				to: '/system'
			}
		];

		setLoad({ s: 'ready', rows, offline: false });
	}, []);

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 15_000);
		return () => clearInterval(id);
	}, [refresh, epoch]);

	const onlineCount = load.s === 'ready' ? load.rows.filter((r) => r.state === 'online').length : null;

	return (
		<Page
			eyebrow="STRUCTURE"
			title="Integrations"
			actions={
				<span style={mono(11, 'var(--l2-fg-3)')}>
					{load.s === 'ready' ? `${onlineCount}/${load.rows.length} ONLINE` : '—'}
				</span>
			}
		>
			<PostureBanner />

			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<Cable size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ ...mono(11, 'var(--atlas-bronze)'), letterSpacing: '0.22em' }}>WIRED SURFACES</span>
				</header>

				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' && (
					load.offline ? (
						<>
							{load.rows.map((r, i) => <Row key={r.name} r={r} i={i} onOpen={(to) => nav(to)} />)}
							<OfflineNote />
						</>
					) : (
						load.rows.map((r, i) => <Row key={r.name} r={r} i={i} onOpen={(to) => nav(to)} />)
					)
				)}
			</section>
		</Page>
	);
}

function gatewayRow(online: boolean, health: { status: string; db: string } | null): IntegrationRow {
	return {
		name: 'ATLAS Gateway',
		kind: 'rust · axum',
		state: online ? 'online' : 'offline',
		posture: 'read=SQLite · write=CLI',
		detail: online ? `db ${health?.db ?? 'ok'} · 127.0.0.1:8484` : 'no response from 127.0.0.1:8484',
		to: '/system'
	};
}

function PostureBanner() {
	return (
		<div style={glassPanel({ padding: '16px 20px', marginBottom: 16, display: 'flex', gap: 14, alignItems: 'flex-start' })}>
			<span style={{ width: 7, height: 7, marginTop: 6, borderRadius: '50%', background: 'var(--atlas-cyan)', boxShadow: '0 0 8px var(--atlas-cyan)', flexShrink: 0 }} />
			<p style={{ margin: 0, color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.65, maxWidth: 720 }}>
				Every integration is <strong style={{ color: 'var(--l2-fg-2)' }}>read-only by default</strong>. Writes — Discord
				mutations, write/shell tools — are <strong style={{ color: 'var(--l2-fg-2)' }}>approval-gated</strong> and audited
				through the one CLI contract. Credentials are <code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>env:VAR</code> references;
				no secret value is ever shown here.
			</p>
		</div>
	);
}

function Row({ r, i, onOpen }: { r: IntegrationRow; i: number; onOpen: (to: string) => void }) {
	const tone = r.tone ?? STATE_TONE[r.state];
	const clickable = !!r.to;
	return (
		<div
			role={clickable ? 'button' : undefined}
			tabIndex={clickable ? 0 : undefined}
			data-topo="info"
			onClick={clickable ? () => onOpen(r.to!) : undefined}
			onKeyDown={clickable ? (e) => (e.key === 'Enter' || e.key === ' ') && onOpen(r.to!) : undefined}
			style={{
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'space-between',
				gap: 16,
				padding: '15px 18px',
				borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
				cursor: clickable ? 'pointer' : 'default',
				transition: 'background var(--l2-duration-xs) var(--l2-ease)'
			}}
			onMouseEnter={(e) => clickable && (e.currentTarget.style.background = 'rgba(79,139,255,0.05)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
		>
			<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
				<span style={{ width: 8, height: 8, borderRadius: '50%', background: tone, boxShadow: `0 0 8px ${tone}`, flexShrink: 0 }} />
				<div style={{ minWidth: 0 }}>
					<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
						<span style={{ color: 'var(--l2-fg-1)', fontSize: 14 }}>{r.name}</span>
						<span style={{ ...mono(9, 'var(--l2-fg-3)'), letterSpacing: '0.12em', textTransform: 'uppercase' }}>{r.kind}</span>
					</div>
					<div style={mono(11, 'var(--l2-fg-3)')}>{r.detail}</div>
				</div>
			</div>
			<div style={{ display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
				<span style={{ ...mono(9, 'var(--l2-fg-2)'), letterSpacing: '0.1em', textTransform: 'uppercase', border: '1px solid var(--l2-hairline)', borderRadius: 2, padding: '2px 7px' }}>
					{r.posture}
				</span>
				<span style={{ ...mono(9.5, tone), letterSpacing: '0.16em', minWidth: 64, textAlign: 'right' }}>
					{r.state.toUpperCase()}
				</span>
			</div>
		</div>
	);
}

function OfflineNote() {
	return (
		<div style={{ padding: '18px 18px', borderTop: '1px solid var(--l2-hairline)', color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.6 }}>
			The gateway is offline, so downstream integration status cannot be read. Start it from{' '}
			<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>System</code> or run{' '}
			<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas gateway start</code>.
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 5 }).map((_, i) => (
				<div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '17px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(`${30 + ((i * 11) % 30)}%`)} />
					<div style={sk(70, true)} />
				</div>
			))}
		</div>
	);
}

function Offline() {
	return (
		<div style={{ padding: '24px 18px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 90, opacity: 0.8, marginBottom: 12 }} />
			<div style={{ color: 'var(--l2-fg-1)', fontSize: 14 }}>Could not read integration status</div>
		</div>
	);
}

const sk = (w: number | string, right = false): React.CSSProperties => ({
	height: 12,
	width: w,
	alignSelf: 'center',
	justifySelf: right ? 'end' : 'start',
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});

function mono(size: number, color?: string): React.CSSProperties {
	return { fontFamily: 'var(--l2-font-mono)', fontSize: size, ...(color ? { color } : {}) };
}
