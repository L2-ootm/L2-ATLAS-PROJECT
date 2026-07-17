import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Boxes, Check, ChevronRight, Search, SlidersHorizontal, X } from 'lucide-react';
import {
	getConfig,
	listModels,
	patchConfig,
	type AtlasConfigView,
	type ModelEntry
} from '../../lib/api';

type ModelRole = 'primary' | 'actors' | 'curator' | 'auxiliary' | 'judge';

const ROLES: Array<{ id: ModelRole; label: string; detail: string }> = [
	{ id: 'primary', label: 'CHAT', detail: 'Primary conversation and tools' },
	{ id: 'actors', label: 'ACTORS', detail: 'Durable subagent default' },
	{ id: 'curator', label: 'CURATOR', detail: 'Review and synthesis' },
	{ id: 'auxiliary', label: 'AUXILIARY', detail: 'Compression and titles' },
	{ id: 'judge', label: 'JUDGE', detail: 'Goal completion judgement' }
];

function modelKey(model: ModelEntry): string {
	return `${model.provider}/${model.model_id}`;
}

function roleValue(config: AtlasConfigView | null, role: ModelRole): string {
	if (!config) return '';
	if (role === 'primary') return `${config.provider.name}/${config.provider.model}`;
	if (role === 'actors') return config.functions?.actor_model ?? '';
	if (role === 'curator') return config.functions?.curator_model ?? '';
	if (role === 'auxiliary') return config.functions?.auxiliary_model ?? '';
	return config.functions?.judge_model ?? '';
}

function rolePatch(role: ModelRole, value: string): Record<string, unknown> {
	if (role === 'primary') {
		const [provider, ...model] = value.split('/');
		return { 'provider.name': provider, 'provider.model': model.join('/') };
	}
	const key = role === 'actors'
		? 'actor_model'
		: role === 'curator'
			? 'curator_model'
			: role === 'auxiliary'
				? 'auxiliary_model'
				: 'judge_model';
	return { [`functions.${key}`]: value };
}

export function ChatModelRouter({
	provider,
	modelId,
	busy
}: {
	provider?: string | null;
	modelId?: string | null;
	busy: boolean;
}) {
	const [open, setOpen] = useState(false);
	const [role, setRole] = useState<ModelRole>('primary');
	const [models, setModels] = useState<ModelEntry[]>([]);
	const [config, setConfig] = useState<AtlasConfigView | null>(null);
	const [query, setQuery] = useState('');
	const [loading, setLoading] = useState(false);
	const [saving, setSaving] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const [registry, current] = await Promise.all([listModels(), getConfig()]);
			setModels(registry.models);
			setConfig(current);
		} catch (cause) {
			setError(cause instanceof Error ? cause.message : String(cause));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		if (!open) return;
		void load();
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') setOpen(false);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [load, open]);

	const selected = roleValue(config, role);
	const displayModel = config
		? `${config.provider.name}/${config.provider.model}`
		: provider && modelId
			? `${provider}/${modelId}`
			: 'Resolve on next run';
	const filtered = useMemo(() => {
		const needle = query.trim().toLowerCase();
		const active = models.filter((model) => model.active);
		const source = active.length > 0 ? active : models;
		return source.filter((model) => {
			const key = modelKey(model).toLowerCase();
			return !needle || key.includes(needle);
		});
	}, [models, query]);

	async function assign(value: string) {
		if (config?.revision === undefined || busy || saving) return;
		setSaving(value || '__inherit__');
		setError(null);
		try {
			const updated = await patchConfig(config.revision, rolePatch(role, value));
			setConfig(updated);
		} catch (cause) {
			setError(cause instanceof Error ? cause.message : String(cause));
			await load();
		} finally {
			setSaving(null);
		}
	}

	return (
		<>
			<button
				type="button"
				className="chat-model-router-trigger"
				onClick={() => setOpen(true)}
				aria-haspopup="dialog"
			>
				<span className="chat-model-router-trigger__icon"><SlidersHorizontal size={13} /></span>
				<span className="chat-model-router-trigger__copy">
					<small>MODEL MESH</small>
					<strong>{displayModel}</strong>
				</span>
				<ChevronRight size={13} />
			</button>

			{open && createPortal(
				<div className="chat-model-router-layer">
					<button type="button" className="chat-model-router-backdrop" onClick={() => setOpen(false)} aria-label="Close model routing" />
					<section className="chat-model-router" role="dialog" aria-modal="true" aria-labelledby="model-router-title">
						<header className="chat-model-router__header">
							<div>
								<span>PROVIDER MESH · FUNCTION ROUTING</span>
								<h2 id="model-router-title">Model routing</h2>
								<p>Choose the model each ATLAS role resolves at its next safe boundary.</p>
							</div>
							<button type="button" onClick={() => setOpen(false)} aria-label="Close model routing" autoFocus><X size={16} /></button>
						</header>

						<div className="chat-model-router__body">
							<nav className="chat-model-roles" aria-label="Model role">
								{ROLES.map((item) => {
									const value = roleValue(config, item.id);
									return (
										<button key={item.id} type="button" className={role === item.id ? 'is-active' : ''} onClick={() => setRole(item.id)}>
											<span>{item.label}</span>
											<small>{item.detail}</small>
											<em>{value || (item.id === 'primary' ? 'unresolved' : 'inherit / auto')}</em>
										</button>
									);
								})}
							</nav>

							<div className="chat-model-catalog">
								<div className="chat-model-catalog__toolbar">
									<div>
										<span>{ROLES.find((item) => item.id === role)?.label}</span>
										<strong>{selected || (role === 'primary' ? displayModel : 'Inherit / automatic')}</strong>
									</div>
									<label>
										<Search size={13} />
										<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter models" aria-label="Filter models" />
									</label>
								</div>
								{busy && <div className="chat-model-router__notice">A turn is live. Routing unlocks when it settles.</div>}
								{error && <div className="chat-model-router__error" role="status">{error}</div>}
								<div className="chat-model-catalog__list">
									{role !== 'primary' && (
										<button type="button" className="chat-model-row" data-selected={!selected} disabled={busy || !!saving || !config} onClick={() => void assign('')}>
											<span className="chat-model-row__glyph"><Boxes size={13} /></span>
											<span><strong>Inherit / automatic</strong><small>Follow the primary mesh or ATLAS light-model policy</small></span>
											{!selected && <Check size={14} />}
										</button>
									)}
									{loading && <div className="chat-model-catalog__empty">Loading model registry…</div>}
									{!loading && filtered.map((model) => {
										const key = modelKey(model);
										return (
											<button key={key} type="button" className="chat-model-row" data-selected={selected === key} disabled={busy || !!saving || !config} onClick={() => void assign(key)}>
												<span className="chat-model-row__glyph"><Boxes size={13} /></span>
												<span><strong>{model.model_id}</strong><small>{model.provider} · {model.health || (model.active ? 'active' : 'inactive')}</small></span>
												{selected === key && <Check size={14} />}
											</button>
										);
									})}
									{!loading && filtered.length === 0 && <div className="chat-model-catalog__empty">No registered models match this filter.</div>}
								</div>
							</div>
						</div>
					</section>
				</div>,
				document.body
			)}
		</>
	);
}
