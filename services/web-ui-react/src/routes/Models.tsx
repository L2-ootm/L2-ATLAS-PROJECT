import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, Boxes } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import { glassPanel } from '../lib/glass';
import { listModels, getConfig, type ModelEntry } from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import sealMark from '../brand/assets/seal.webp';

// ── Models — /models — the model registry ────────────────────────────────────
// Every known model, grouped by provider, with active state and source. Data:
// GET /v1/models (degrades to empty on 404/503). Provider credentials live in
// System ▸ Runtime Config; routing is task-class-based (D-017), noted below.

type Load =
	| { s: 'loading' }
	| { s: 'ready'; models: ModelEntry[]; provider: string | null }
	| { s: 'error' };

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
	const [query, setQuery] = useState('');
	const { epoch } = useGatewayHealth();

	const refresh = useCallback(async () => {
		try {
			const [m, c] = await Promise.allSettled([listModels(), getConfig()]);
			if (m.status !== 'fulfilled') {
				setLoad({ s: 'error' });
				return;
			}
			const provider = c.status === 'fulfilled' ? c.value.provider.name : null;
			setLoad({ s: 'ready', models: m.value.models, provider });
		} catch {
			setLoad({ s: 'error' });
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh, epoch]);

	const models = load.s === 'ready' ? load.models : [];
	const q = query.trim().toLowerCase();
	const filtered = q
		? models.filter((m) => m.model_id.toLowerCase().includes(q) || m.provider.toLowerCase().includes(q))
		: models;

	const groups = useMemo(() => {
		const g = new Map<string, ModelEntry[]>();
		for (const m of filtered) {
			const key = m.provider || 'unknown';
			const bucket = g.get(key);
			if (bucket) bucket.push(m);
			else g.set(key, [m]);
		}
		const keys = [...g.keys()].sort();
		for (const k of keys) g.get(k)!.sort((a, b) => a.model_id.localeCompare(b.model_id));
		return { g, keys };
	}, [filtered]);

	const activeCount = models.filter((m) => m.active).length;

	return (
		<Page
			eyebrow="STRUCTURE"
			title="Models"
			actions={
				<span style={mono(11, 'var(--l2-fg-3)')}>
					{load.s === 'ready' ? `${activeCount}/${models.length} ACTIVE` : '—'}
				</span>
			}
		>
			<RoutingNote />

			{models.length > 8 && (
				<div style={{ marginBottom: 14 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Filter by model or provider…"
						ariaLabel="Filter models"
						tone="info"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
				</div>
			)}

			<section style={glassPanel({ overflow: 'hidden' })}>
				<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<Boxes size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ ...mono(11, 'var(--atlas-bronze)'), letterSpacing: '0.22em' }}>MODEL REGISTRY</span>
					<span style={{ marginLeft: 'auto', ...mono(10, 'var(--l2-fg-3)'), letterSpacing: '0.14em' }}>
						{q ? `${filtered.length}/${models.length}` : `${models.length} KNOWN`}
					</span>
				</header>

				{load.s === 'loading' && <SkeletonRows />}
				{load.s === 'error' && <Offline />}
				{load.s === 'ready' && models.length === 0 && (
					<Empty provider={load.provider} />
				)}
				{load.s === 'ready' && models.length > 0 && (
					filtered.length === 0 ? (
						<div style={{ padding: '22px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>No models match “{query.trim()}”.</div>
					) : (
						<div style={{ maxHeight: '62vh', overflowY: 'auto' }}>
							{groups.keys.map((pk) => (
								<div key={pk}>
									<div style={{ position: 'sticky', top: 0, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 18px', background: 'rgba(11,13,18,0.94)', borderTop: '1px solid var(--l2-hairline)', borderBottom: '1px solid var(--l2-hairline)' }}>
										<span style={{ ...mono(10, 'var(--atlas-bronze)'), letterSpacing: '0.18em', textTransform: 'uppercase' }}>{pk}</span>
										<span style={{ marginLeft: 'auto', ...mono(10, 'var(--l2-fg-3)') }}>{groups.g.get(pk)!.length}</span>
									</div>
									{groups.g.get(pk)!.map((m, i) => (
										<div key={`${m.provider}/${m.model_id}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '12px 18px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
											<div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
												<span style={{ ...mono(13, 'var(--l2-fg-1)'), wordBreak: 'break-all' }}>{m.model_id}</span>
												<StatusPill active={m.active} />
											</div>
											<div style={{ display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
												{m.health && <span style={mono(9.5, 'var(--l2-fg-3)')}>{m.health.toUpperCase()}</span>}
												<span style={mono(10.5, 'var(--l2-fg-3)')}>{rel(m.last_seen)}</span>
											</div>
										</div>
									))}
								</div>
							))}
						</div>
					)
				)}
			</section>
		</Page>
	);
}

function RoutingNote() {
	return (
		<div style={glassPanel({ padding: '16px 20px', marginBottom: 16, display: 'flex', gap: 14, alignItems: 'flex-start' })}>
			<span style={{ width: 7, height: 7, marginTop: 6, borderRadius: '50%', background: 'var(--atlas-celestial)', boxShadow: '0 0 8px var(--atlas-celestial)', flexShrink: 0 }} />
			<p style={{ margin: 0, color: 'var(--l2-fg-3)', fontSize: 12.5, lineHeight: 1.65, maxWidth: 720 }}>
				ATLAS routes by <strong style={{ color: 'var(--l2-fg-2)' }}>task class</strong> (D-017): each LLM call selects a model
				from this registry by capability and cost, with the choice recorded as audit-event metadata. The active provider and
				default model are set in <code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>System ▸ Runtime Config</code>.
				Sync the registry with <code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas models refresh</code>.
			</p>
		</div>
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
				No models registered{provider ? ` for ${provider}` : ''}. Run{' '}
				<code style={{ fontFamily: 'var(--l2-font-mono)', color: 'var(--atlas-celestial)' }}>atlas models refresh</code> to populate it.
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

function StatusPill({ active }: { active: boolean }) {
	const color = active ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)';
	return (
		<span style={{ ...mono(8.5, color), letterSpacing: '0.18em', border: `1px solid ${active ? 'rgba(0,229,255,0.4)' : 'var(--l2-hairline)'}`, borderRadius: 2, padding: '1px 6px' }}>
			{active ? 'ACTIVE' : 'INACTIVE'}
		</span>
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
