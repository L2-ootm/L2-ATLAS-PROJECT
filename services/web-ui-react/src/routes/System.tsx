import { useCallback, useEffect, useState } from 'react';
import { Server, Database, Copy, Check, Power, Cpu, Radio, ShieldCheck, Wrench, Clock } from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	checkHealth,
	getConfig,
	listChannels,
	listModels,
	listModules,
	messagingGatewayStatus,
	setModuleActive,
	startMessagingGateway,
	stopMessagingGateway,
	toggleChannel,
	getToolManifests,
	listToolApprovals,
	type AtlasConfigView,
	type ChannelSummary,
	type MessagingGatewayStatus,
	type ModelEntry,
	type Module,
	type ToolManifest,
	type ToolApproval
} from '../lib/api';
import { isTauri, startGatewayViaShell } from '../lib/host';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import emblemFull from '../brand/assets/emblem-full.webp';

// ── System — operator control surface ────────────────────────────────────────
// Gateway + database health, the offline start affordance (a browser SPA cannot
// spawn a process; in the future Tauri shell it can — feature-detected here), and
// the activatable-modules toggle (Decision 3b: cashflow is an optional module).

const START_COMMAND = 'atlas gateway start';

type Health = { status: string; db: string } | null;
type Load = { s: 'loading' } | { s: 'ready' } | { s: 'error' };

export default function System() {
	const [health, setHealth] = useState<Health>(null);
	const [online, setOnline] = useState<boolean | null>(null);
	const [modules, setModules] = useState<Module[]>([]);
	const [config, setConfig] = useState<AtlasConfigView | null>(null);
	const [channels, setChannels] = useState<ChannelSummary[]>([]);
	const [models, setModels] = useState<ModelEntry[]>([]);
	const [tools, setTools] = useState<ToolManifest[]>([]);
	const [toolApprovals, setToolApprovals] = useState<ToolApproval[]>([]);
	const [msgGw, setMsgGw] = useState<MessagingGatewayStatus>({ running: false, pid: null });
	const [msgGwBusy, setMsgGwBusy] = useState(false);
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [busyId, setBusyId] = useState<string | null>(null);
	const [chBusy, setChBusy] = useState<string | null>(null);
	const [err, setErr] = useState<string | null>(null);
	const { epoch } = useGatewayHealth();

	const refresh = useCallback(async () => {
		const [h, m, c, ch, gw, md, tl, ta] = await Promise.allSettled([
			checkHealth(),
			listModules(),
			getConfig(),
			listChannels(),
			messagingGatewayStatus(),
			listModels(),
			getToolManifests(),
			listToolApprovals()
		]);
		if (h.status === 'fulfilled') {
			setHealth(h.value);
			setOnline(true);
		} else {
			setHealth(null);
			setOnline(false);
		}
		if (m.status === 'fulfilled') setModules(m.value.modules);
		setConfig(c.status === 'fulfilled' ? c.value : null);
		setChannels(ch.status === 'fulfilled' ? ch.value.channels : []);
		setMsgGw(gw.status === 'fulfilled' ? gw.value : { running: false, pid: null });
		setModels(md.status === 'fulfilled' ? md.value.models : []);
		setTools(tl.status === 'fulfilled' ? tl.value : []);
		setToolApprovals(ta.status === 'fulfilled' ? ta.value : []);
		setLoad({ s: h.status === 'rejected' && m.status === 'rejected' ? 'error' : 'ready' });
	}, []);

	async function toggleMsgGw() {
		setMsgGwBusy(true);
		setErr(null);
		try {
			if (msgGw.running) await stopMessagingGateway();
			else await startMessagingGateway();
			await refresh();
		} catch {
			setErr('Could not control the messaging gateway — is the REST gateway running?');
		} finally {
			setMsgGwBusy(false);
		}
	}

	async function toggleCh(ch: ChannelSummary) {
		setChBusy(ch.name);
		setErr(null);
		try {
			await toggleChannel(ch.name, !ch.enabled);
			await refresh();
		} catch {
			setErr(`Could not toggle ${ch.name} — is the gateway running?`);
		} finally {
			setChBusy(null);
		}
	}

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 15_000);
		return () => clearInterval(id);
	}, [refresh, epoch]);

	async function toggle(mod: Module) {
		setBusyId(mod.id);
		setErr(null);
		try {
			await setModuleActive(mod.id, mod.status !== 'active');
			await refresh();
		} catch {
			setErr(`Could not toggle ${mod.name} — is the gateway running?`);
		} finally {
			setBusyId(null);
		}
	}

	return (
		<Page eyebrow="SYSTEM" title="System">
			<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
				<StatusCard
					icon={<Server size={15} strokeWidth={1.5} />}
					label="GATEWAY"
					value={online === null ? 'CHECKING' : online ? 'ONLINE' : 'OFFLINE'}
					ok={online === true}
				/>
				<StatusCard
					icon={<Database size={15} strokeWidth={1.5} />}
					label="DATABASE"
					value={(health?.db ?? (online ? 'unknown' : '—')).toUpperCase()}
					ok={(health?.db ?? '').toLowerCase() === 'ok'}
				/>
			</div>

			{online === false && <OfflinePanel onStarted={() => void refresh()} />}

			{config && <RuntimeConfigPanel config={config} />}

			<ModelRegistryPanel models={models} provider={config?.provider.name ?? null} />

			<PolicyPanel />

			<ToolsPanel tools={tools} />

			<ToolApprovalsPanel approvals={toolApprovals} />

			<ChannelsPanel
				channels={channels}
				offline={online === false}
				busyName={chBusy}
				onToggle={toggleCh}
				gateway={msgGw}
				gatewayBusy={msgGwBusy}
				onGatewayToggle={toggleMsgGw}
			/>

			<ModulesPanel
				modules={modules}
				loading={load.s === 'loading'}
				offline={online === false}
				busyId={busyId}
				onToggle={toggle}
				err={err}
			/>

			<AboutPanel />
		</Page>
	);
}

// ── about band (PAGES-SPEC §10) ──────────────────────────────────────────────
// Where the full Operator-Atlas emblem lives at rest: brand narrative, the three
// thesis pillars, and the honest foundation attribution. Always renders (no
// gateway dependency) — this page is partly an offline-diagnostic surface.
function AboutPanel() {
	return (
		<section
			style={glassPanel({
				overflow: 'hidden',
				marginTop: 16,
				position: 'relative',
				textAlign: 'center',
				padding: '40px 28px 34px'
			})}
		>
			<span
				aria-hidden="true"
				style={{
					position: 'absolute',
					top: 0,
					left: 0,
					right: 0,
					height: 1,
					background: 'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)',
					opacity: 0.5
				}}
			/>
			<img
				src={emblemFull}
				alt="The Operator Atlas"
				style={{ width: 'min(280px, 70%)', height: 'auto', margin: '0 auto 22px', display: 'block', filter: 'drop-shadow(0 8px 32px rgba(79,139,255,0.18))' }}
			/>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.34em', color: 'var(--atlas-bronze)', textTransform: 'uppercase', marginBottom: 12 }}>
				The Operator Atlas
			</div>
			<h2 style={{ fontFamily: 'var(--l2-font-serif)', fontWeight: 600, fontSize: 24, color: 'var(--l2-fg-1)', margin: '0 0 18px', letterSpacing: '0.04em' }}>
				Bearing Complexity Through Structure
			</h2>
			<div style={{ display: 'flex', justifyContent: 'center', gap: 28, flexWrap: 'wrap', marginBottom: 22 }}>
				{[
					['MISSION', 'Author intent; the titan does the work.'],
					['AUDIT', 'Every action accounted for.'],
					['STRUCTURE', 'Memory, models, and integrations, mapped.']
				].map(([k, v]) => (
					<div key={k} style={{ maxWidth: 200 }}>
						<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.22em', color: 'var(--atlas-celestial)', marginBottom: 6 }}>{k}</div>
						<div style={{ color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.5 }}>{v}</div>
					</div>
				))}
			</div>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.26em', color: 'var(--l2-fg-2)', marginBottom: 8 }}>
				BY L2 SYSTEMS
			</div>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.06em', color: 'var(--l2-fg-3)', maxWidth: 520, margin: '0 auto', lineHeight: 1.6 }}>
				Runtime foundation derived from Hermes (MIT). See ATTRIBUTION.md.
			</div>
		</section>
	);
}

// ── status cards ──────────────────────────────────────────────────────────────
function StatusCard({
	icon,
	label,
	value,
	ok
}: {
	icon: React.ReactNode;
	label: string;
	value: string;
	ok: boolean;
}) {
	const color = ok ? 'var(--atlas-cyan)' : 'var(--l2-error)';
	return (
		<div style={glassPanel({ padding: '18px 20px' })}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--l2-fg-3)', marginBottom: 14 }}>
				{icon}
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.24em' }}>{label}</span>
			</div>
			<div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
				<span style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` }} />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 18, letterSpacing: '0.06em', color }}>{value}</span>
			</div>
		</div>
	);
}

// ── runtime config panel ─────────────────────────────────────────────────────
// Reads ~/.atlas/config.yaml (masked) via the gateway. Secrets are env: refs only,
// so no value is ever shown. Configure with `atlas setup` / `atlas config set`.
function RuntimeConfigPanel({ config }: { config: AtlasConfigView }) {
	const rows: Array<[string, string]> = [
		['Provider', config.provider.name],
		['Model', config.provider.model],
		['API key', config.provider.api_key || '— (set via atlas setup)'],
		['Default agent', config.runtime.default_agent],
		['Iteration budget', String(config.runtime.iteration_budget)],
		['Gateway port', String(config.gateway.rust_port)],
		['Messaging', config.gateway.messaging_enabled ? 'enabled' : 'disabled'],
		['Cockpit port', String(config.cockpit.port)],
		['Branding', config.cockpit.branding]
	];
	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Cpu size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					RUNTIME CONFIG
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					~/.atlas/config.yaml
				</span>
			</header>
			<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
				{rows.map(([k, v], i) => (
					<div
						key={k}
						style={{
							display: 'flex',
							justifyContent: 'space-between',
							gap: 12,
							padding: '11px 18px',
							borderTop: i < 2 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<span style={{ color: 'var(--l2-fg-3)', fontSize: 12.5 }}>{k}</span>
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 12, color: 'var(--l2-fg-1)', textAlign: 'right', wordBreak: 'break-all' }}>
							{v}
						</span>
					</div>
				))}
			</div>
		</section>
	);
}

// ── model registry panel ──────────────────────────────────────────────────────
// The provider/model registry (GET /v1/models). Provider credentials live in the
// RUNTIME CONFIG panel above; this lists every known model with its source and
// active state. Read-only — discovery/seeding happens via the CLI.
function ModelRegistryPanel({ models, provider }: { models: ModelEntry[]; provider: string | null }) {
	const [query, setQuery] = useState('');
	const activeCount = models.filter((m) => m.active).length;

	// Filter by model id or provider; grouping + a capped-scroll body keep the
	// panel bounded once `atlas models refresh` pulls a real (hundreds-long) list.
	const q = query.trim().toLowerCase();
	const filtered = q
		? models.filter((m) => m.model_id.toLowerCase().includes(q) || m.provider.toLowerCase().includes(q))
		: models;

	const groups = new Map<string, ModelEntry[]>();
	for (const m of filtered) {
		const key = m.provider || 'unknown';
		const bucket = groups.get(key);
		if (bucket) bucket.push(m);
		else groups.set(key, [m]);
	}
	const providerKeys = [...groups.keys()].sort();
	for (const k of providerKeys) groups.get(k)!.sort((a, b) => a.model_id.localeCompare(b.model_id));

	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Cpu size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					MODEL REGISTRY
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{activeCount}/{models.length} ACTIVE
				</span>
			</header>

			{models.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6 }}>
					No models registered{provider ? ` for ${provider}` : ''}. Sync the registry with{' '}
					<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas models refresh</code>.
				</div>
			) : (
				<>
					{models.length > 8 && (
						<div
							style={{
								display: 'flex',
								alignItems: 'center',
								gap: 12,
								padding: '10px 18px',
								borderBottom: '1px solid var(--l2-hairline)'
							}}
						>
							<input
								value={query}
								onChange={(e) => setQuery(e.target.value)}
								placeholder="Filter by model or provider…"
								style={{
									flex: 1,
									minWidth: 0,
									background: 'transparent',
									border: 'none',
									outline: 'none',
									color: 'var(--l2-fg-1)',
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 12,
									letterSpacing: '0.04em'
								}}
							/>
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.12em', color: 'var(--l2-fg-3)', flexShrink: 0 }}>
								{q ? `${filtered.length}/${models.length}` : `${models.length}`}
							</span>
						</div>
					)}
					<div style={{ maxHeight: 320, overflowY: 'auto' }}>
						{filtered.length === 0 ? (
							<div style={{ padding: '20px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>
								No models match “{query.trim()}”.
							</div>
						) : (
							providerKeys.map((pk) => (
								<div key={pk}>
									<div
										style={{
											position: 'sticky',
											top: 0,
											display: 'flex',
											alignItems: 'center',
											gap: 8,
											padding: '7px 18px',
											background: 'rgba(11, 13, 18, 0.92)',
											borderTop: '1px solid var(--l2-hairline)',
											borderBottom: '1px solid var(--l2-hairline)'
										}}
									>
										<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.18em', color: 'var(--atlas-bronze)', textTransform: 'uppercase' }}>
											{pk}
										</span>
										<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.1em', color: 'var(--l2-fg-3)' }}>
											{groups.get(pk)!.length}
										</span>
									</div>
									{groups.get(pk)!.map((m, i) => (
										<div
											key={`${m.provider}/${m.model_id}`}
											style={{
												display: 'flex',
												alignItems: 'center',
												justifyContent: 'space-between',
												gap: 16,
												padding: '11px 18px',
												borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
											}}
										>
											<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
												<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 13, color: 'var(--l2-fg-1)', wordBreak: 'break-all' }}>
													{m.model_id}
												</span>
												<StatusPill active={m.active} />
											</div>
											{m.health && (
												<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.1em', color: 'var(--l2-fg-3)', flexShrink: 0 }}>
													{m.health.toUpperCase()}
												</span>
											)}
										</div>
									))}
								</div>
							))
						)}
					</div>
				</>
			)}
		</section>
	);
}

// ── channels panel ────────────────────────────────────────────────────────────
// Messaging channels from the foundation gateway config. Toggling persists to
// the foundation config.yaml via the gateway; credential presence only (never
// values). Credentials/tokens are configured out-of-band (atlas setup / env).
function ChannelsPanel({
	channels,
	offline,
	busyName,
	onToggle,
	gateway,
	gatewayBusy,
	onGatewayToggle
}: {
	channels: ChannelSummary[];
	offline: boolean;
	busyName: string | null;
	onToggle: (c: ChannelSummary) => void;
	gateway: MessagingGatewayStatus;
	gatewayBusy: boolean;
	onGatewayToggle: () => void;
}) {
	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Radio size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					CHANNELS
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{channels.filter((c) => c.enabled).length}/{channels.length} ENABLED
				</span>
			</header>

			{channels.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6 }}>
					No messaging channels configured. Configure the foundation gateway with{' '}
					<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas setup</code>, then
					enable channels here.
				</div>
			) : (
				channels.map((c, i) => (
					<div
						key={c.name}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '14px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
							<span style={{ color: 'var(--l2-fg-1)', fontSize: 14, textTransform: 'capitalize' }}>{c.name}</span>
							<StatusPill active={c.enabled} />
							<span
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 9.5,
									letterSpacing: '0.12em',
									color: c.credential_present ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)'
								}}
							>
								{c.credential_present ? 'CREDENTIAL SET' : 'NO CREDENTIAL'}
							</span>
						</div>
						<ToggleButton
							active={c.enabled}
							busy={busyName === c.name}
							disabled={offline || busyName !== null}
							onClick={() => onToggle(c)}
						/>
					</div>
				))
			)}

			<div
				style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					gap: 16,
					padding: '14px 18px',
					borderTop: '1px solid var(--l2-hairline)',
					background: 'rgba(9,11,16,0.35)'
				}}
			>
				<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.14em', color: 'var(--l2-fg-2)' }}>
						MESSAGING GATEWAY
					</span>
					<StatusPill active={gateway.running} />
					{gateway.running && gateway.pid != null && (
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.1em', color: 'var(--l2-fg-3)' }}>
							PID {gateway.pid}
						</span>
					)}
				</div>
				<button
					onClick={onGatewayToggle}
					disabled={offline || gatewayBusy}
					style={{
						display: 'inline-flex',
						alignItems: 'center',
						gap: 7,
						padding: '8px 14px',
						borderRadius: 2,
						border: `1px solid ${gateway.running ? 'var(--l2-error)' : 'var(--l2-hairline)'}`,
						background: 'transparent',
						color: offline ? 'var(--l2-fg-3)' : gateway.running ? 'var(--l2-error)' : 'var(--atlas-cyan)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 11,
						letterSpacing: '0.14em',
						cursor: offline || gatewayBusy ? 'not-allowed' : 'pointer',
						opacity: offline || gatewayBusy ? 0.5 : 1
					}}
				>
					<Power size={13} strokeWidth={2} />
					{gatewayBusy ? '…' : gateway.running ? 'STOP' : 'START'}
				</button>
			</div>
		</section>
	);
}

// ── offline start panel ─────────────────────────────────────────────────────
function OfflinePanel({ onStarted }: { onStarted: () => void }) {
	const [copied, setCopied] = useState(false);
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState<string | null>(null);
	const shell = isTauri();

	async function copy() {
		try {
			await navigator.clipboard.writeText(START_COMMAND);
			setCopied(true);
			setTimeout(() => setCopied(false), 1600);
		} catch {
			/* clipboard blocked — the command is shown for manual copy */
		}
	}

	async function startViaShell() {
		setBusy(true);
		setErr(null);
		try {
			await startGatewayViaShell();
			onStarted();
		} catch (e) {
			setErr(e instanceof Error ? e.message : 'failed to start the gateway');
		} finally {
			setBusy(false);
		}
	}

	return (
		<div style={glassPanel({ padding: '20px 22px', marginBottom: 16 })}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
				<Power size={15} strokeWidth={1.6} color="var(--l2-error)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.18em', color: 'var(--l2-fg-1)' }}>
					GATEWAY OFFLINE
				</span>
			</div>
			<p style={{ color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6, margin: '0 0 14px', maxWidth: 560 }}>
				{shell
					? 'The desktop shell can start the gateway directly.'
					: 'Run this in any terminal to start the gateway (the `atlas` CLI is on your PATH). The cockpit will reconnect automatically.'}
			</p>
			{shell ? (
				<>
					<PrimaryButton icon={<Power size={14} strokeWidth={2} />} onClick={() => void startViaShell()} disabled={busy}>
						{busy ? 'STARTING…' : 'START GATEWAY'}
					</PrimaryButton>
					{err && <div style={{ marginTop: 10, color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{err}</div>}
				</>
			) : (
				<div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
					<code
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 13,
							color: 'var(--atlas-celestial)',
							background: 'rgba(9,11,16,0.7)',
							border: '1px solid var(--l2-hairline)',
							borderRadius: 2,
							padding: '9px 14px'
						}}
					>
						{START_COMMAND}
					</code>
					<button
						onClick={copy}
						style={{
							display: 'inline-flex',
							alignItems: 'center',
							gap: 7,
							padding: '9px 14px',
							borderRadius: 2,
							border: '1px solid var(--l2-hairline)',
							background: 'transparent',
							color: copied ? 'var(--atlas-cyan)' : 'var(--l2-fg-2)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 11,
							letterSpacing: '0.12em',
							cursor: 'pointer'
						}}
					>
						{copied ? <Check size={13} /> : <Copy size={13} />}
						{copied ? 'COPIED' : 'COPY'}
					</button>
				</div>
			)}
		</div>
	);
}

// ── modules panel ─────────────────────────────────────────────────────────────
function ModulesPanel({
	modules,
	loading,
	offline,
	busyId,
	onToggle,
	err
}: {
	modules: Module[];
	loading: boolean;
	offline: boolean;
	busyId: string | null;
	onToggle: (m: Module) => void;
	err: string | null;
}) {
	return (
		<section style={glassPanel({ overflow: 'hidden' })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					MODULES
				</span>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{modules.filter((m) => m.status === 'active').length}/{modules.length} ACTIVE
				</span>
			</header>

			{err && (
				<div style={{ padding: '12px 18px', color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>
					{err}
				</div>
			)}

			{loading ? (
				<div style={{ padding: '28px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>Loading modules…</div>
			) : modules.length === 0 ? (
				<div style={{ padding: '28px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>
					No optional modules available.
				</div>
			) : (
				modules.map((m, i) => (
					<div
						key={m.id}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '16px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ minWidth: 0 }}>
							<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
								<span style={{ color: 'var(--l2-fg-1)', fontSize: 14 }}>{m.name}</span>
								<StatusPill active={m.status === 'active'} />
							</div>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.5, maxWidth: 620 }}>
								{m.description}
							</div>
						</div>
						<ToggleButton
							active={m.status === 'active'}
							busy={busyId === m.id}
							disabled={offline || busyId !== null}
							onClick={() => onToggle(m)}
						/>
					</div>
				))
			)}
		</section>
	);
}

// ── tool policy panel (SC3 — the posture must be VISIBLE, not just enforced) ──
function PolicyPanel() {
	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<ShieldCheck size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					TOOL POLICY
				</span>
				<span
					style={{
						marginLeft: 'auto',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 9,
						letterSpacing: '0.16em',
						color: 'var(--atlas-cyan)',
						border: '1px solid rgba(0,229,255,0.4)',
						borderRadius: 2,
						padding: '2px 8px'
					}}
				>
					READ-ONLY BY DEFAULT
				</span>
			</header>
			<div style={{ padding: '16px 18px', display: 'grid', gap: 12 }}>
				<div style={{ display: 'grid', gap: 8 }}>
					<RiskLegendRow tone="var(--atlas-cyan)" level="read" text="auto-allowed — runs immediately" />
					<RiskLegendRow tone="var(--atlas-celestial)" level="write" text="requires explicit operator approval" />
					<RiskLegendRow tone="var(--l2-error)" level="shell" text="requires explicit operator approval" />
				</div>
				<p style={{ color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.6, margin: 0, maxWidth: 640 }}>
					No sensitive data is stored: credentials are <code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>env:VAR</code> references only,
					and tool arguments/results are redacted before any audit or approval row is persisted.
					Web requests are SSRF-guarded (loopback/private targets blocked) and file access is bounded to the workspace.
				</p>
			</div>
		</section>
	);
}

function RiskLegendRow({ tone, level, text }: { tone: string; level: string; text: string }) {
	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
			<span
				style={{
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 9,
					letterSpacing: '0.16em',
					color: tone,
					border: `1px solid ${tone}`,
					borderRadius: 2,
					padding: '1px 7px',
					textTransform: 'uppercase',
					minWidth: 54,
					textAlign: 'center'
				}}
			>
				{level}
			</span>
			<span style={{ color: 'var(--l2-fg-2)', fontSize: 12.5 }}>{text}</span>
		</div>
	);
}

// ── tools panel — manifest-driven (SC2/SC3) ───────────────────────────────────
function ToolsPanel({ tools }: { tools: ToolManifest[] }) {
	const toneFor = (r: string) => (r === 'read' ? 'var(--atlas-cyan)' : r === 'write' ? 'var(--atlas-celestial)' : 'var(--l2-error)');
	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Wrench size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					TOOLS
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{tools.length} REGISTERED
				</span>
			</header>
			{tools.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6 }}>
					No tools registered. See{' '}
					<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>docs/tools.md</code> to add one (manifest + adapter).
				</div>
			) : (
				tools.map((t, i) => (
					<div
						key={t.name}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '13px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 13, color: 'var(--l2-fg-1)' }}>{t.name}</span>
							<span
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 8.5,
									letterSpacing: '0.16em',
									color: toneFor(t.risk_level),
									border: `1px solid ${toneFor(t.risk_level)}`,
									borderRadius: 2,
									padding: '1px 6px',
									textTransform: 'uppercase'
								}}
							>
								{t.risk_level}
							</span>
						</div>
						<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.08em', color: 'var(--l2-fg-3)', textAlign: 'right', wordBreak: 'break-all' }}>
							{t.permissions.join(' · ') || '—'}
						</span>
					</div>
				))
			)}
		</section>
	);
}

// ── tool approvals panel — clones the Discord ApprovalsPanel pattern ──────────
function ToolApprovalsPanel({
	approvals
}: {
	approvals: ToolApproval[];
}) {
	const statusTone = (s: string) =>
		s === 'executed' ? 'var(--atlas-cyan)' : s === 'pending' ? 'var(--atlas-celestial)' : s === 'failed' || s === 'rejected' ? 'var(--l2-error)' : 'var(--l2-fg-3)';
	const pending = approvals.filter((a) => a.status === 'pending');
	return (
		<section style={glassPanel({ overflow: 'hidden', marginBottom: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 8,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Clock size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					TOOL APPROVALS
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
					{pending.length} PENDING
				</span>
			</header>
			{approvals.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6 }}>
					No tool approvals. Write/shell tool calls land here as PENDING and never execute until approved.
				</div>
			) : (
				approvals.map((a, i) => (
					<div
						key={a.id}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '13px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
							<span style={{ width: 7, height: 7, borderRadius: '50%', background: statusTone(a.status), boxShadow: `0 0 7px ${statusTone(a.status)}`, flexShrink: 0 }} />
							<span style={{ color: 'var(--l2-fg-1)', fontSize: 13, wordBreak: 'break-all' }}>{a.summary || a.tool_name}</span>
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.12em', color: statusTone(a.status), textTransform: 'uppercase', flexShrink: 0 }}>
								{a.tool_name} · {a.status}
							</span>
						</div>
						{a.status === 'pending' && (
							<a
								href="/console"
								style={{
									color: 'var(--atlas-celestial)',
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 10,
									letterSpacing: '0.1em',
									textTransform: 'uppercase'
								}}
							>
								Open owning session
							</a>
						)}
					</div>
				))
			)}
		</section>
	);
}

function StatusPill({ active }: { active: boolean }) {
	const color = active ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)';
	return (
		<span
			style={{
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 8.5,
				letterSpacing: '0.18em',
				color,
				border: `1px solid ${active ? 'rgba(0,229,255,0.4)' : 'var(--l2-hairline)'}`,
				borderRadius: 2,
				padding: '1px 6px'
			}}
		>
			{active ? 'ACTIVE' : 'INACTIVE'}
		</span>
	);
}

function ToggleButton({
	active,
	busy,
	disabled,
	onClick
}: {
	active: boolean;
	busy: boolean;
	disabled: boolean;
	onClick: () => void;
}) {
	const on = active;
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			aria-pressed={on}
			style={{
				flex: 'none',
				padding: '8px 16px',
				borderRadius: 2,
				border: `1px solid ${on ? 'rgba(0,229,255,0.4)' : 'rgba(79,139,255,0.4)'}`,
				background: on ? 'rgba(0,229,255,0.08)' : 'rgba(79,139,255,0.12)',
				color: on ? 'var(--atlas-cyan)' : 'var(--atlas-celestial)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10.5,
				letterSpacing: '0.14em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled && !busy ? 0.5 : 1
			}}
		>
			{busy ? '…' : on ? 'DEACTIVATE' : 'ACTIVATE'}
		</button>
	);
}

function PrimaryButton({
	children,
	icon,
	onClick,
	disabled
}: {
	children: React.ReactNode;
	icon?: React.ReactNode;
	onClick?: () => void;
	disabled?: boolean;
}) {
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
				border: '1px solid rgba(79,139,255,0.4)',
				background: 'rgba(79,139,255,0.12)',
				color: 'var(--atlas-celestial)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				letterSpacing: '0.16em',
				textTransform: 'uppercase',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1
			}}
		>
			{icon}
			{children}
		</button>
	);
}
