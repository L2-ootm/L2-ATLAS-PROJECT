import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Server, Database, Boxes } from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	checkHealth,
	getConfig,
	listChannels,
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
	type Module,
	type ToolManifest,
	type ToolApproval
} from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import { ProviderSettingsPanel } from './Settings';
import { VisualsPanel } from '../components/control/VisualsPanel';
import { StoragePanel } from '../components/control/StoragePanel';
import {
	AboutPanel,
	ChannelsPanel,
	ModulesPanel,
	OfflinePanel,
	PolicyPanel,
	RuntimeConfigPanel,
	StatusCard,
	ToolApprovalsPanel,
	ToolsPanel
} from '../components/control/panels';

// ── Control — the merged Settings/System operator surface ────────────────────
// One modular page with tabs instead of two competing sidebar destinations.
// /settings and /system remain as redirects into a tab here. Tab state is
// carried in ?tab= so deep links and the redirect shims stay addressable.

const TAB_IDS = ['status', 'provider', 'visuals', 'storage', 'tools', 'channels', 'modules', 'about'] as const;
type TabId = (typeof TAB_IDS)[number];

type Health = { status: string; db: string } | null;
type Load = { s: 'loading' } | { s: 'ready' } | { s: 'error' };

export default function Control() {
	const [searchParams, setSearchParams] = useSearchParams();
	const rawTab = searchParams.get('tab') ?? 'status';
	const tab: TabId = (TAB_IDS as readonly string[]).includes(rawTab) ? (rawTab as TabId) : 'status';

	const [health, setHealth] = useState<Health>(null);
	const [online, setOnline] = useState<boolean | null>(null);
	const [modules, setModules] = useState<Module[]>([]);
	const [config, setConfig] = useState<AtlasConfigView | null>(null);
	const [channels, setChannels] = useState<ChannelSummary[]>([]);
	const [tools, setTools] = useState<ToolManifest[]>([]);
	const [toolApprovals, setToolApprovals] = useState<ToolApproval[]>([]);
	const [msgGw, setMsgGw] = useState<MessagingGatewayStatus>({ running: false, pid: null });
	const [msgGwBusy, setMsgGwBusy] = useState(false);
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [busyId, setBusyId] = useState<string | null>(null);
	const [chBusy, setChBusy] = useState<string | null>(null);
	const [err, setErr] = useState<string | null>(null);
	const { epoch } = useGatewayHealth();
	const tabRefs = useRef<Map<TabId, HTMLButtonElement>>(new Map());

	const refresh = useCallback(async () => {
		const [h, m, c, ch, gw, tl, ta] = await Promise.allSettled([
			checkHealth(),
			listModules(),
			getConfig(),
			listChannels(),
			messagingGatewayStatus(),
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
		setTools(tl.status === 'fulfilled' ? tl.value : []);
		setToolApprovals(ta.status === 'fulfilled' ? ta.value : []);
		setLoad({ s: h.status === 'rejected' && m.status === 'rejected' ? 'error' : 'ready' });
	}, []);

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 15_000);
		return () => clearInterval(id);
	}, [refresh, epoch]);

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

	async function toggleModule(mod: Module) {
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

	const pendingApprovals = toolApprovals.filter((a) => a.status === 'pending').length;
	const activeModules = modules.filter((m) => m.status === 'active').length;

	// Dynamic tab chrome: live counts appear as badges so the operator sees
	// actionable state (pending approvals, active modules) without switching.
	const tabs = useMemo(
		(): Array<{ id: TabId; label: string; badge?: string; alert?: boolean }> => [
			{ id: 'status', label: 'STATUS', badge: online === false ? 'OFFLINE' : undefined, alert: online === false },
			{ id: 'provider', label: 'PROVIDER' },
			{ id: 'visuals', label: 'VISUALS' },
			{ id: 'storage', label: 'STORAGE' },
			{
				id: 'tools',
				label: 'TOOLS & POLICY',
				badge: pendingApprovals > 0 ? String(pendingApprovals) : undefined,
				alert: pendingApprovals > 0
			},
			{ id: 'channels', label: 'CHANNELS', badge: channels.length > 0 ? `${channels.filter((c) => c.enabled).length}/${channels.length}` : undefined },
			{ id: 'modules', label: 'MODULES', badge: modules.length > 0 ? `${activeModules}/${modules.length}` : undefined },
			{ id: 'about', label: 'ABOUT' }
		],
		[online, pendingApprovals, channels, modules, activeModules]
	);

	const selectTab = useCallback(
		(next: TabId) => {
			setSearchParams(next === 'status' ? {} : { tab: next }, { replace: true });
		},
		[setSearchParams]
	);

	// Roving-focus arrow-key navigation per the WAI-ARIA tabs pattern.
	function onTablistKeyDown(e: React.KeyboardEvent) {
		const idx = tabs.findIndex((t) => t.id === tab);
		let next: number | null = null;
		if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
		else if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
		else if (e.key === 'Home') next = 0;
		else if (e.key === 'End') next = tabs.length - 1;
		if (next !== null) {
			e.preventDefault();
			const id = tabs[next].id;
			selectTab(id);
			tabRefs.current.get(id)?.focus();
		}
	}

	return (
		<Page eyebrow="SYSTEM" title="Control">
			<div
				role="tablist"
				aria-label="System control sections"
				onKeyDown={onTablistKeyDown}
				style={{
					display: 'flex',
					gap: 4,
					flexWrap: 'wrap',
					marginBottom: 18,
					borderBottom: '1px solid var(--l2-hairline)',
					paddingBottom: 0
				}}
			>
				{tabs.map((t) => {
					const active = t.id === tab;
					return (
						<button
							key={t.id}
							ref={(el) => {
								if (el) tabRefs.current.set(t.id, el);
								else tabRefs.current.delete(t.id);
							}}
							role="tab"
							id={`control-tab-${t.id}`}
							aria-selected={active}
							aria-controls={`control-panel-${t.id}`}
							tabIndex={active ? 0 : -1}
							onClick={() => selectTab(t.id)}
							style={{
								display: 'inline-flex',
								alignItems: 'center',
								gap: 8,
								padding: '10px 16px 12px',
								border: 'none',
								borderBottom: `2px solid ${active ? 'var(--atlas-cyan)' : 'transparent'}`,
								marginBottom: -1,
								background: 'transparent',
								color: active ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10.5,
								letterSpacing: '0.18em',
								cursor: 'pointer'
							}}
						>
							{t.label}
							{t.badge && (
								<span
									style={{
										fontFamily: 'var(--l2-font-mono)',
										fontSize: 8.5,
										letterSpacing: '0.12em',
										color: t.alert ? 'var(--l2-warning)' : 'var(--l2-fg-3)',
										border: `1px solid ${t.alert ? 'rgba(255,183,77,0.45)' : 'var(--l2-hairline)'}`,
										borderRadius: 2,
										padding: '1px 6px'
									}}
								>
									{t.badge}
								</span>
							)}
						</button>
					);
				})}
			</div>

			<div role="tabpanel" id={`control-panel-${tab}`} aria-labelledby={`control-tab-${tab}`}>
				{tab === 'status' && (
					<>
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
						<section style={{ ...glassPanel(), padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 10 }}>
							<Boxes size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
							<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
								The provider/model registry lives in{' '}
								<Link to="/models" style={{ color: 'var(--atlas-celestial)' }}>
									MODELS
								</Link>
								.
							</span>
						</section>
					</>
				)}

				{tab === 'provider' && <ProviderSettingsPanel />}
				{tab === 'visuals' && <VisualsPanel />}
				{tab === 'storage' && <StoragePanel />}

				{tab === 'tools' && (
					<>
						<PolicyPanel />
						<ToolsPanel tools={tools} />
						<ToolApprovalsPanel approvals={toolApprovals} />
					</>
				)}

				{tab === 'channels' && (
					<ChannelsPanel
						channels={channels}
						offline={online === false}
						busyName={chBusy}
						onToggle={toggleCh}
						gateway={msgGw}
						gatewayBusy={msgGwBusy}
						onGatewayToggle={toggleMsgGw}
					/>
				)}

				{tab === 'modules' && (
					<ModulesPanel
						modules={modules}
						loading={load.s === 'loading'}
						offline={online === false}
						busyId={busyId}
						onToggle={toggleModule}
						err={err}
					/>
				)}

				{tab === 'about' && <AboutPanel />}
			</div>
		</Page>
	);
}
