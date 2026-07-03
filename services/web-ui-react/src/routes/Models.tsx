import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, Boxes, RefreshCw, Power, Star, Zap } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import { glassPanel } from '../lib/glass';
import {
	ApiError,
	freellmapiStart,
	freellmapiStatus,
	freellmapiStop,
	getConfig,
	getProviderStatus,
	listModels,
	modelsRefresh,
	patchConfig,
	type AtlasConfigView,
	type FreellmapiStatus,
	type ModelEntry,
	type ProviderStatusView
} from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import sealMark from '../brand/assets/seal.webp';

// ── Models — /models — the dynamic model control surface ─────────────────────
// Driven entirely by the live contracts: registry (GET /v1/models), masked
// config (GET/PATCH /v1/config), provider status, and the FreeLLMAPI sidecar
// control routes. Every row action saves immediately through one optimistic
// PATCH keyed on the config revision — there is no page-level save button.

type Load =
	| { s: 'loading' }
	| { s: 'ready' }
	| { s: 'error' };

type Toast = { tone: 'good' | 'bad' | 'warn'; text: string } | null;

const FAV_KEY = 'atlas.models.favorites';

function loadFavorites(): Set<string> {
	try {
		return new Set(JSON.parse(localStorage.getItem(FAV_KEY) ?? '[]') as string[]);
	} catch {
		return new Set();
	}
}

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

export default function Models() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [models, setModels] = useState<ModelEntry[]>([]);
	const [config, setConfig] = useState<AtlasConfigView | null>(null);
	const [status, setStatus] = useState<ProviderStatusView | null>(null);
	const [sidecar, setSidecar] = useState<FreellmapiStatus | null>(null);
	const [query, setQuery] = useState('');
	const [providerFilter, setProviderFilter] = useState<string | null>(null);
	const [activeOnly, setActiveOnly] = useState(false);
	const [favorites, setFavorites] = useState<Set<string>>(loadFavorites);
	const [busyKey, setBusyKey] = useState<string | null>(null);
	const [toast, setToast] = useState<Toast>(null);
	const { epoch } = useGatewayHealth();

	const refresh = useCallback(async () => {
		const [m, c, s, f] = await Promise.allSettled([
			listModels(),
			getConfig(),
			getProviderStatus(),
			freellmapiStatus()
		]);
		if (m.status !== 'fulfilled') {
			setLoad({ s: 'error' });
			return;
		}
		setModels(m.value.models);
		setConfig(c.status === 'fulfilled' ? c.value : null);
		setStatus(s.status === 'fulfilled' ? s.value : null);
		setSidecar(f.status === 'fulfilled' ? f.value : null);
		setLoad({ s: 'ready' });
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh, epoch]);

	// One optimistic PATCH per row action — instant per-model persistence.
	const patch = useCallback(
		async (key: string, changes: Record<string, unknown>, doneText: string) => {
			if (!config || config.revision === undefined) {
				setToast({ tone: 'bad', text: 'Config unavailable — is the gateway running?' });
				return;
			}
			setBusyKey(key);
			setToast(null);
			try {
				await patchConfig(config.revision, changes);
				setToast({ tone: 'good', text: doneText });
				await refresh();
			} catch (err) {
				if (err instanceof ApiError && err.status === 409) {
					setToast({ tone: 'warn', text: 'Config changed elsewhere — reloaded; try again.' });
					await refresh();
				} else {
					setToast({ tone: 'bad', text: (err as Error).message });
				}
			} finally {
				setBusyKey(null);
			}
		},
		[config, refresh]
	);

	const toggleFavorite = useCallback((id: string) => {
		setFavorites((prev) => {
			const next = new Set(prev);
			if (next.has(id)) next.delete(id);
			else next.add(id);
			localStorage.setItem(FAV_KEY, JSON.stringify([...next]));
			return next;
		});
	}, []);

	const syncRegistry = useCallback(async () => {
		setBusyKey('__sync__');
		setToast(null);
		try {
			const r = await modelsRefresh();
			setToast({ tone: 'good', text: r.message.split('\n')[1] ?? r.message.split('\n')[0] ?? 'registry synced' });
			await refresh();
		} catch (err) {
			setToast({ tone: 'bad', text: `sync failed: ${(err as Error).message}` });
		} finally {
			setBusyKey(null);
		}
	}, [refresh]);

	const toggleSidecar = useCallback(async () => {
		if (!sidecar) return;
		setBusyKey('__sidecar__');
		setToast(null);
		try {
			const r = sidecar.running ? await freellmapiStop() : await freellmapiStart();
			setToast({ tone: r.ok === false ? 'bad' : 'good', text: r.message });
			// The sidecar boots asynchronously; poll a few times so the pill flips.
			for (let i = 0; i < 5; i++) {
				await new Promise((res) => setTimeout(res, 1200));
				const st = await freellmapiStatus();
				setSidecar(st);
				if (st.running !== sidecar.running) break;
			}
		} catch (err) {
			setToast({ tone: 'bad', text: (err as Error).message });
		} finally {
			setBusyKey(null);
		}
	}, [sidecar]);

	const activeModel = config ? `${config.provider.name}/${config.provider.model}` : null;
	const curator = config?.functions?.curator_model ?? '';
	const auxiliary = config?.functions?.auxiliary_model ?? '';

	const providers = useMemo(() => [...new Set(models.map((m) => m.provider || 'unknown'))].sort(), [models]);

	const filtered = useMemo(() => {
		const q = query.trim().toLowerCase();
		return models.filter((m) => {
			if (activeOnly && !m.active) return false;
			if (providerFilter && (m.provider || 'unknown') !== providerFilter) return false;
			if (q && !m.model_id.toLowerCase().includes(q) && !m.provider.toLowerCase().includes(q)) return false;
			return true;
		});
	}, [models, query, providerFilter, activeOnly]);

	const groups = useMemo(() => {
		const g = new Map<string, ModelEntry[]>();
		for (const m of filtered) {
			const key = m.provider || 'unknown';
			const bucket = g.get(key);
			if (bucket) bucket.push(m);
			else g.set(key, [m]);
		}
		const keys = [...g.keys()].sort();
		for (const k of keys)
			g.get(k)!.sort((a, b) => {
				const fa = favorites.has(`${a.provider}/${a.model_id}`) ? 0 : 1;
				const fb = favorites.has(`${b.provider}/${b.model_id}`) ? 0 : 1;
				return fa - fb || a.model_id.localeCompare(b.model_id);
			});
		return { g, keys };
	}, [filtered, favorites]);

	const activeCount = models.filter((m) => m.active).length;
	const live = status ? !status.mock_mode : false;

	return (
		<Page
			eyebrow="STRUCTURE"
			title="Models"
			actions={
				<div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
					{status && (
						<span style={mono(10, live ? 'var(--l2-success)' : 'var(--l2-warning)')}>
							{live ? 'LIVE' : 'MOCK'}
						</span>
					)}
					{activeModel && <span style={mono(11, 'var(--l2-fg-2)')}>{activeModel}</span>}
					<span style={mono(11, 'var(--l2-fg-3)')}>
						{load.s === 'ready' ? `${activeCount}/${models.length} ACTIVE` : '—'}
					</span>
				</div>
			}
		>
			{toast && (
				<div
					role="status"
					style={{
						...glassPanel({
							borderColor:
								toast.tone === 'good'
									? 'rgba(102,187,106,0.45)'
									: toast.tone === 'warn'
										? 'rgba(255,183,77,0.45)'
										: 'rgba(255,82,82,0.45)'
						}),
						padding: 12,
						marginBottom: 14
					}}
				>
					<span
						style={mono(
							11,
							toast.tone === 'good' ? 'var(--l2-success)' : toast.tone === 'warn' ? 'var(--l2-warning)' : 'var(--l2-error)'
						)}
					>
						{toast.text}
					</span>
				</div>
			)}

			<SidecarPanel sidecar={sidecar} busy={busyKey === '__sidecar__'} onToggle={() => void toggleSidecar()} />

			<div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
				<div style={{ flex: '1 1 260px', minWidth: 220 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Search models…"
						ariaLabel="Search models"
						tone="info"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
				</div>
				<FilterChip label="ALL" active={providerFilter === null} onClick={() => setProviderFilter(null)} />
				{providers.map((p) => (
					<FilterChip key={p} label={p.toUpperCase()} active={providerFilter === p} onClick={() => setProviderFilter(providerFilter === p ? null : p)} />
				))}
				<FilterChip label="ACTIVE ONLY" active={activeOnly} onClick={() => setActiveOnly((v) => !v)} />
				<button
					onClick={() => void syncRegistry()}
					disabled={busyKey !== null}
					style={{
						display: 'inline-flex',
						alignItems: 'center',
						gap: 7,
						padding: '8px 14px',
						borderRadius: 2,
						border: '1px solid rgba(79,139,255,0.4)',
						background: 'rgba(79,139,255,0.12)',
						color: 'var(--atlas-celestial)',
						cursor: busyKey !== null ? 'default' : 'pointer',
						opacity: busyKey !== null ? 0.5 : 1,
						...mono(10)
					}}
				>
					<RefreshCw size={12} />
					{busyKey === '__sync__' ? 'SYNCING…' : 'SYNC REGISTRY'}
				</button>
			</div>

			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<Boxes size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ ...mono(11, 'var(--atlas-bronze)'), letterSpacing: '0.22em' }}>MODEL REGISTRY</span>
					<span style={{ marginLeft: 'auto', ...mono(10, 'var(--l2-fg-3)'), letterSpacing: '0.14em' }}>
						{filtered.length === models.length ? `${models.length} KNOWN` : `${filtered.length}/${models.length}`}
					</span>
				</header>

				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' && models.length === 0 && <Empty provider={config?.provider.name ?? null} />}
				{load.s === 'ready' && models.length > 0 && (
					filtered.length === 0 ? (
						<div style={{ padding: '22px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>No models match the current filters.</div>
					) : (
						<div style={{ maxHeight: '58vh', overflowY: 'auto' }}>
							{groups.keys.map((pk) => (
								<div key={pk}>
									<div style={{ position: 'sticky', top: 0, zIndex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 18px', background: 'rgba(11,13,18,0.94)', borderTop: '1px solid var(--l2-hairline)', borderBottom: '1px solid var(--l2-hairline)' }}>
										<span style={{ ...mono(10, 'var(--atlas-bronze)'), letterSpacing: '0.18em', textTransform: 'uppercase' }}>{pk}</span>
										<span style={{ marginLeft: 'auto', ...mono(10, 'var(--l2-fg-3)') }}>{groups.g.get(pk)!.length}</span>
									</div>
									{groups.g.get(pk)!.map((m, i) => {
										const id = `${m.provider}/${m.model_id}`;
										const isActive = activeModel === id;
										const isCurator = curator === id;
										const isAux = auxiliary === id;
										const fav = favorites.has(id);
										return (
											<div
												key={id}
												style={{
													display: 'flex',
													alignItems: 'center',
													justifyContent: 'space-between',
													gap: 16,
													padding: '11px 18px',
													borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
													background: isActive ? 'rgba(0,229,255,0.04)' : 'transparent'
												}}
											>
												<div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
													<button
														onClick={() => toggleFavorite(id)}
														aria-label={fav ? `Unfavorite ${m.model_id}` : `Favorite ${m.model_id}`}
														aria-pressed={fav}
														style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 2, display: 'flex' }}
													>
														<Star size={13} color={fav ? 'var(--atlas-bronze)' : 'var(--l2-fg-ghost)'} fill={fav ? 'var(--atlas-bronze)' : 'none'} />
													</button>
													<span style={{ ...mono(13, m.active ? 'var(--l2-fg-1)' : 'var(--l2-fg-3)'), wordBreak: 'break-all' }}>{m.model_id}</span>
													{!m.active && <Pill text="INACTIVE" color="var(--l2-fg-3)" />}
													{isActive && <Pill text="IN USE" color="var(--atlas-cyan)" />}
													{isCurator && <Pill text="CURATOR" color="var(--atlas-bronze)" />}
													{isAux && <Pill text="AUX" color="var(--atlas-celestial)" />}
													{m.health && <span style={mono(9.5, 'var(--l2-fg-3)')}>{m.health.toUpperCase()}</span>}
												</div>
												<div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
													<span style={mono(10, 'var(--l2-fg-ghost)')}>{rel(m.last_seen)}</span>
													<RowAction
														label={isActive ? 'ACTIVE' : 'USE'}
														title={`Set ${id} as the active provider/model`}
														disabled={busyKey !== null || isActive || !config}
														busy={busyKey === `use:${id}`}
														highlight={isActive}
														onClick={() =>
															void patch(
																`use:${id}`,
																{ 'provider.name': m.provider, 'provider.model': m.model_id },
																`Active model set to ${id}.`
															)
														}
													/>
													<RowAction
														label={isCurator ? 'CURATOR ✓' : 'CURATOR'}
														title={isCurator ? 'Clear the curator override' : `Route curator tasks to ${id}`}
														disabled={busyKey !== null || !config}
														busy={busyKey === `curator:${id}`}
														highlight={isCurator}
														onClick={() =>
															void patch(
																`curator:${id}`,
																{ 'functions.curator_model': isCurator ? '' : id },
																isCurator ? 'Curator override cleared.' : `Curator routed to ${id}.`
															)
														}
													/>
													<RowAction
														label={isAux ? 'AUX ✓' : 'AUX'}
														title={isAux ? 'Clear the auxiliary override' : `Route auxiliary tasks to ${id}`}
														disabled={busyKey !== null || !config}
														busy={busyKey === `aux:${id}`}
														highlight={isAux}
														onClick={() =>
															void patch(
																`aux:${id}`,
																{ 'functions.auxiliary_model': isAux ? '' : id },
																isAux ? 'Auxiliary override cleared.' : `Auxiliary routed to ${id}.`
															)
														}
													/>
												</div>
											</div>
										);
									})}
								</div>
							))}
						</div>
					)
				)}
			</section>
		</Page>
	);
}

// ── freellmapi sidecar panel ──────────────────────────────────────────────────
function SidecarPanel({
	sidecar,
	busy,
	onToggle
}: {
	sidecar: FreellmapiStatus | null;
	busy: boolean;
	onToggle: () => void;
}) {
	if (!sidecar) return null;
	const color = sidecar.running ? 'var(--l2-success)' : 'var(--l2-fg-3)';
	return (
		<div style={{ ...glassPanel(), padding: '13px 18px', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
			<Zap size={13} color="var(--atlas-bronze)" />
			<span style={{ ...mono(10.5, 'var(--atlas-bronze)'), letterSpacing: '0.2em' }}>FREELLMAPI ENDPOINT</span>
			<span style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` }} />
			<span style={mono(10.5, color)}>{sidecar.running ? 'RUNNING' : 'STOPPED'}</span>
			{sidecar.base_url && <span style={mono(10.5, 'var(--l2-fg-3)')}>{sidecar.base_url}</span>}
			{!sidecar.installed && sidecar.remediation && (
				<span style={mono(10, 'var(--l2-warning)')}>{sidecar.remediation}</span>
			)}
			<button
				onClick={onToggle}
				disabled={busy || (!sidecar.installed && !sidecar.running)}
				style={{
					marginLeft: 'auto',
					display: 'inline-flex',
					alignItems: 'center',
					gap: 7,
					padding: '7px 14px',
					borderRadius: 2,
					border: `1px solid ${sidecar.running ? 'var(--l2-error)' : 'rgba(79,139,255,0.4)'}`,
					background: sidecar.running ? 'transparent' : 'rgba(79,139,255,0.12)',
					color: sidecar.running ? 'var(--l2-error)' : 'var(--atlas-celestial)',
					cursor: busy ? 'default' : 'pointer',
					opacity: busy || (!sidecar.installed && !sidecar.running) ? 0.5 : 1,
					...mono(10)
				}}
			>
				<Power size={12} />
				{busy ? '…' : sidecar.running ? 'STOP' : 'START'}
			</button>
		</div>
	);
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
	return (
		<button
			onClick={onClick}
			aria-pressed={active}
			style={{
				padding: '7px 12px',
				borderRadius: 2,
				border: `1px solid ${active ? 'rgba(0,229,255,0.5)' : 'var(--l2-hairline)'}`,
				background: active ? 'rgba(0,229,255,0.08)' : 'transparent',
				color: active ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)',
				cursor: 'pointer',
				...mono(9.5)
			}}
		>
			{label}
		</button>
	);
}

function RowAction({
	label,
	title,
	disabled,
	busy,
	highlight,
	onClick
}: {
	label: string;
	title: string;
	disabled: boolean;
	busy: boolean;
	highlight: boolean;
	onClick: () => void;
}) {
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			title={title}
			style={{
				padding: '5px 10px',
				borderRadius: 2,
				border: `1px solid ${highlight ? 'rgba(0,229,255,0.5)' : 'var(--l2-hairline)'}`,
				background: highlight ? 'rgba(0,229,255,0.08)' : 'transparent',
				color: highlight ? 'var(--atlas-cyan)' : 'var(--l2-fg-2)',
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled && !highlight ? 0.45 : 1,
				...mono(9)
			}}
		>
			{busy ? '…' : label}
		</button>
	);
}

function Pill({ text, color }: { text: string; color: string }) {
	return (
		<span style={{ ...mono(8.5, color), letterSpacing: '0.16em', border: `1px solid ${color}`, borderRadius: 2, padding: '1px 6px', flexShrink: 0 }}>
			{text}
		</span>
	);
}

function Empty({ provider }: { provider: string | null }) {
	return (
		<div style={{ padding: '40px 24px', textAlign: 'center' }}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 100, opacity: 0.82, marginBottom: 14 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 20, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				Model registry empty
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13, lineHeight: 1.6, maxWidth: 440, margin: '0 auto' }}>
				No models registered{provider ? ` for ${provider}` : ''}. Use SYNC REGISTRY above (or{' '}
				<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas models refresh</code>) to populate it.
			</div>
		</div>
	);
}

function Offline() {
	return (
		<div style={{ padding: '24px 18px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
			<span style={{ width: 7, height: 7, marginTop: 4, borderRadius: '50%', background: 'var(--l2-error)', boxShadow: '0 0 9px rgba(255,0,85,0.55)', flex: 'none' }} />
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 4 }}>Gateway unavailable</div>
				<div style={mono(11.5, 'var(--l2-fg-3)')}>NO RESPONSE FROM 127.0.0.1:8484 — START THE GATEWAY</div>
			</div>
		</div>
	);
}

function SkeletonRows() {
	return (
		<div>
			{Array.from({ length: 6 }).map((_, i) => (
				<div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={sk(`${40 + ((i * 9) % 30)}%`)} />
					<div style={sk(60, true)} />
				</div>
			))}
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
