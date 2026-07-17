import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Cable, KeyRound, Power, ShieldAlert, Zap, RefreshCw, Save } from 'lucide-react';
import { TopoScroll } from '../components/TopoScroll';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	ApiError,
	freellmapiStart,
	freellmapiStatus,
	freellmapiStop,
	getConfig,
	getProviderModes,
	getProviderStatus,
	importCodex,
	listModels,
	patchConfig,
	storeProviderKey,
	type AtlasConfigView,
	type FreellmapiStatus,
	type ModelEntry,
	type ProviderAuthMode,
	type ProviderModeView,
	type ProviderStatusView,
	type ReasoningEffort
} from '../lib/api';

// ── Settings — provider mesh + model control surface ─────────────────────────
// The write path mirrors the TUI settings overlay: secrets go through
// POST /v1/auth/providers (never the config file), everything else is one
// optimistic PATCH /v1/config keyed on the masked snapshot's revision.

const EFFORT_LEVELS: ReasoningEffort[] = ['', 'minimal', 'low', 'medium', 'high'];

const MODE_HINTS: Record<ProviderAuthMode, string> = {
	api_key: 'Direct key via the ATLAS auth store or an env:VAR reference.',
	oauth_import: 'Imports your Codex/ChatGPT login once; the foundation owns refresh.',
	claude_code: 'Runs on the local Claude Code subscription session — no key.',
	freellmapi: 'Free OpenAI-compatible endpoint. Privacy cost: prompts may be logged.'
};

type Banner = { tone: 'good' | 'bad' | 'warn'; text: string } | null;

// Route shim: /settings now redirects to /control (PROVIDER tab); this default
// export remains the standalone page form used by the component tests.
export default function Settings() {
	return (
		<Page eyebrow="SYSTEM" title="Settings">
			<ProviderSettingsPanel />
		</Page>
	);
}

export function ProviderSettingsPanel() {
	const [config, setConfig] = useState<AtlasConfigView | null>(null);
	const [status, setStatus] = useState<ProviderStatusView | null>(null);
	const [modes, setModes] = useState<ProviderModeView[]>([]);
	const [models, setModels] = useState<ModelEntry[]>([]);
	const [offline, setOffline] = useState(false);

	const [authMode, setAuthMode] = useState<ProviderAuthMode>('api_key');
	const [providerName, setProviderName] = useState('');
	const [model, setModel] = useState('');
	const [baseUrl, setBaseUrl] = useState('');
	const [apiKey, setApiKey] = useState('');
	const [effort, setEffort] = useState<ReasoningEffort>('');
	const [fnAutoconfig, setFnAutoconfig] = useState(true);
	const [fnCurator, setFnCurator] = useState('');
	const [fnAuxiliary, setFnAuxiliary] = useState('');
	const [fnJudge, setFnJudge] = useState('');

	const [busy, setBusy] = useState(false);
	const [banner, setBanner] = useState<Banner>(null);
	const [sidecar, setSidecar] = useState<FreellmapiStatus | null>(null);
	const [sidecarBusy, setSidecarBusy] = useState(false);

	const refresh = useCallback(async () => {
		const [c, s, m, md, fl] = await Promise.allSettled([
			getConfig(),
			getProviderStatus(),
			getProviderModes(),
			listModels(),
			freellmapiStatus()
		]);
		setOffline(c.status === 'rejected');
		const cfg = c.status === 'fulfilled' ? c.value : null;
		const sv = s.status === 'fulfilled' ? s.value : null;
		if (cfg) {
			setConfig(cfg);
			const mode = cfg.provider.auth_mode ?? 'api_key';
			setAuthMode(mode);
			// Canonical provider names for managed modes — overrides stale config values.
			let pName = cfg.provider.name;
			if (mode === 'oauth_import') pName = 'openai-codex';
			else if (mode === 'claude_code') pName = 'claude_code';
			else if (mode === 'freellmapi') pName = 'freellmapi';
			setProviderName(pName);
			// Prefer effective model from status when modes agree (avoids stale config model).
			const effectiveModel = sv && sv.auth_mode === mode ? sv.model : cfg.provider.model;
			setModel(effectiveModel);
			setBaseUrl(cfg.provider.base_url ?? '');
			setEffort(cfg.provider.reasoning_effort ?? '');
			setFnAutoconfig(cfg.functions?.autoconfig ?? true);
			setFnCurator(cfg.functions?.curator_model ?? '');
			setFnAuxiliary(cfg.functions?.auxiliary_model ?? '');
			setFnJudge(cfg.functions?.judge_model ?? '');
		}
		setStatus(sv);
		setModes(m.status === 'fulfilled' ? m.value : []);
		setModels(md.status === 'fulfilled' ? md.value.models : []);
		setSidecar(fl.status === 'fulfilled' ? fl.value : null);
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const revision = config?.revision;
	const canSave = !busy && revision !== undefined && providerName.trim() !== '' && model.trim() !== '';

	const save = useCallback(async () => {
		if (revision === undefined) return;
		if (authMode === 'freellmapi' && baseUrl.trim() === '') {
			setBanner({ tone: 'bad', text: 'FreeLLMAPI mode requires a base URL.' });
			return;
		}
		setBusy(true);
		setBanner(null);
		try {
			if ((authMode === 'api_key' || authMode === 'freellmapi') && apiKey.trim() !== '') {
				await storeProviderKey(providerName.trim(), apiKey, baseUrl.trim() || undefined);
				setApiKey('');
			}
			await patchConfig(revision, {
				'provider.name': providerName.trim(),
				'provider.model': model.trim(),
				'provider.auth_mode': authMode,
				'provider.base_url': baseUrl.trim() === '' ? null : baseUrl.trim(),
				'provider.reasoning_effort': effort,
				'functions.autoconfig': fnAutoconfig,
				'functions.curator_model': fnCurator.trim(),
				'functions.auxiliary_model': fnAuxiliary.trim(),
				'functions.judge_model': fnJudge.trim()
			});
			setBanner({ tone: 'good', text: 'Provider configuration saved.' });
			await refresh();
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				setBanner({
					tone: 'warn',
					text: 'Config changed elsewhere — reloaded the latest revision, review and save again.'
				});
				await refresh();
			} else {
				const detail = err instanceof ApiError && err.remediation ? ` — ${err.remediation}` : '';
				setBanner({ tone: 'bad', text: `${(err as Error).message}${detail}` });
			}
		} finally {
			setBusy(false);
		}
	}, [
		revision,
		authMode,
		providerName,
		model,
		baseUrl,
		apiKey,
		effort,
		fnAutoconfig,
		fnCurator,
		fnAuxiliary,
		fnJudge,
		refresh
	]);

	const runCodexImport = useCallback(async () => {
		setBusy(true);
		setBanner(null);
		try {
			const result = await importCodex();
			setBanner(
				result.imported
					? { tone: 'good', text: 'Codex login imported into the owned store.' }
					: { tone: 'bad', text: result.reason || 'Codex login was not importable.' }
			);
			await refresh();
		} catch (err) {
			setBanner({ tone: 'bad', text: (err as Error).message });
		} finally {
			setBusy(false);
		}
	}, [refresh]);

	/** Auto-sets canonical provider name when switching to a managed auth mode. */
	const selectMode = useCallback((mode: ProviderAuthMode) => {
		setAuthMode(mode);
		if (mode === 'oauth_import') setProviderName('openai-codex');
		else if (mode === 'claude_code') setProviderName('claude_code');
		else if (mode === 'freellmapi') {
			setProviderName('freellmapi');
			if (sidecar?.base_url) setBaseUrl(sidecar.base_url);
			if (sidecar?.api_key) setApiKey(sidecar.api_key);
		}
	}, [sidecar]);

	const toggleSidecar = useCallback(async () => {
		if (!sidecar) return;
		setSidecarBusy(true);
		try {
			const r = sidecar.running ? await freellmapiStop() : await freellmapiStart();
			if (r.ok === false) {
				setBanner({ tone: 'bad', text: r.message });
			}
			// The sidecar boots asynchronously; poll a few times so the pill flips.
			for (let i = 0; i < 5; i++) {
				await new Promise((res) => setTimeout(res, 1200));
				const st = await freellmapiStatus();
				setSidecar(st);
				if (st.running !== sidecar.running) break;
			}
		} catch (err) {
			setBanner({ tone: 'bad', text: (err as Error).message });
		} finally {
			setSidecarBusy(false);
		}
	}, [sidecar]);

	/** Model options filtered to the active provider for faster selection.
	 * Falls back to all models if the registry has nothing for this provider yet. */
	const modelOptions = useMemo(() => {
		const pName = providerName.trim().toLowerCase();
		const matching = pName ? models.filter((m) => m.provider.toLowerCase() === pName) : models;
		const ids = [...new Set(matching.map((m) => m.model_id))].slice(0, 200);
		return ids.length > 0 ? ids : [...new Set(models.map((m) => m.model_id))].slice(0, 200);
	}, [models, providerName]);

	return (
		<div>
			{offline && (
				<div style={{ ...glassPanel({ borderColor: 'rgba(255,183,77,0.45)' }), padding: 16, marginBottom: 16 }}>
					<span style={mono(11, 'var(--l2-warning)')}>
						GATEWAY OFFLINE — start it with `atlas gateway start` to edit settings.
					</span>
				</div>
			)}
			{banner && (
				<div
					role="status"
					style={{
						...glassPanel({
							borderColor:
								banner.tone === 'good' ? 'rgba(102,187,106,0.45)' : 'rgba(255,183,77,0.45)'
						}),
						padding: 12,
						marginBottom: 16
					}}
				>
					<span
						style={mono(
							11,
							banner.tone === 'good'
								? 'var(--l2-success)'
								: banner.tone === 'warn'
									? 'var(--l2-warning)'
									: 'var(--l2-error)'
						)}
					>
						{banner.text}
					</span>
				</div>
			)}

			<div style={{ display: 'grid', gap: 16 }}>
				<ActiveStatusPanel status={status} />
				<section style={{ ...glassPanel(), padding: 20 }}>
					<SectionTitle icon={<Cable size={13} />} text="PROVIDER MODE" />
					<div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
						{modes.map((m) => (
							<button
								key={m.mode}
								onClick={() => selectMode(m.mode)}
								aria-pressed={authMode === m.mode}
								style={{
									display: 'flex',
									alignItems: 'baseline',
									gap: 12,
									textAlign: 'left',
									padding: '10px 14px',
									borderRadius: 2,
									border: `1px solid ${authMode === m.mode ? 'rgba(0,229,255,0.5)' : 'var(--l2-hairline)'}`,
									background: authMode === m.mode ? 'rgba(0,229,255,0.06)' : 'transparent',
									cursor: 'pointer'
								}}
							>
								<span style={mono(11, authMode === m.mode ? 'var(--atlas-cyan)' : 'var(--l2-fg-1)')}>
									{m.label}
								</span>
								<span style={mono(9.5, m.available ? 'var(--l2-success)' : 'var(--l2-fg-3)')}>
									{m.available ? 'READY' : 'MISSING'}
								</span>
								{m.active && <span style={mono(9.5, 'var(--atlas-bronze)')}>ACTIVE NOW</span>}
								<span style={{ ...mono(9.5, 'var(--l2-fg-3)'), marginLeft: 'auto' }}>{m.detail}</span>
							</button>
						))}
						{modes.length === 0 && (
							<span style={mono(10, 'var(--l2-fg-3)')}>Mode availability unavailable (gateway offline?).</span>
						)}
					</div>
					<p style={{ ...mono(9.5, 'var(--l2-fg-3)'), marginTop: 10 }}>{MODE_HINTS[authMode]}</p>
					{authMode === 'freellmapi' && (
						<>
						<div role="alert" style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
							<ShieldAlert size={13} color="var(--l2-warning)" />
							<span style={mono(10.5, 'var(--l2-warning)')}>
								Privacy warning: free endpoints may log prompts — never send secrets. Every run is
								audit-stamped with this warning.
							</span>
						</div>
						{sidecar && (
							<div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', borderRadius: 2, border: `1px solid ${sidecar.running ? 'rgba(0,229,255,0.25)' : 'var(--l2-hairline)'}` }}>
								<Zap size={12} color="var(--atlas-bronze)" />
								<span style={mono(10, 'var(--atlas-bronze)')}>SIDECAR</span>
								<span style={{ width: 6, height: 6, borderRadius: '50%', background: sidecar.running ? 'var(--l2-success)' : 'var(--l2-fg-3)', flexShrink: 0 }} />
								<span style={mono(10, sidecar.running ? 'var(--l2-success)' : 'var(--l2-fg-3)')}>{sidecar.running ? 'RUNNING' : 'STOPPED'}</span>
								{sidecar.base_url && <span style={{ ...mono(10, 'var(--l2-fg-3)'), overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 240 }}>{sidecar.base_url}</span>}
								<button
									onClick={() => void toggleSidecar()}
									disabled={sidecarBusy || (!sidecar.installed && !sidecar.running)}
									style={{
										marginLeft: 'auto', flexShrink: 0,
										display: 'inline-flex', alignItems: 'center', gap: 6,
										padding: '5px 12px', borderRadius: 2,
										border: `1px solid ${sidecar.running ? 'var(--l2-error)' : 'rgba(79,139,255,0.4)'}`,
										background: sidecar.running ? 'transparent' : 'rgba(79,139,255,0.12)',
										color: sidecar.running ? 'var(--l2-error)' : 'var(--atlas-celestial)',
										cursor: sidecarBusy || (!sidecar.installed && !sidecar.running) ? 'default' : 'pointer',
										opacity: sidecarBusy || (!sidecar.installed && !sidecar.running) ? 0.5 : 1,
										...mono(10)
									}}
								>
									<Power size={11} />
									{sidecarBusy ? '…' : sidecar.running ? 'STOP' : 'START'}
								</button>
							</div>
						)}
						</>
					)}
					{authMode === 'oauth_import' && (
						<div style={{ marginTop: 10 }}>
							<ActionButton onClick={runCodexImport} disabled={busy} icon={<KeyRound size={12} />}>
								IMPORT CODEX LOGIN
							</ActionButton>
						</div>
					)}
				</section>

				<section style={{ ...glassPanel(), padding: 20 }}>
					<SectionTitle icon={<Zap size={13} />} text="MODEL & EFFORT" />
					<div style={{ display: 'grid', gap: 12, marginTop: 12, maxWidth: 560 }}>
						<Field label="PROVIDER">
							{authMode === 'api_key' || authMode === 'freellmapi' ? (
								<TextInput
									value={providerName}
									onChange={setProviderName}
									placeholder={authMode === 'freellmapi' ? 'freellmapi' : 'openrouter'}
									ariaLabel="Provider name"
								/>
							) : (
								<div style={{ padding: '9px 12px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', gap: 10 }}>
									<span style={mono(11, 'var(--l2-fg-2)')}>{providerName || '—'}</span>
									<span style={mono(9, 'var(--l2-fg-ghost)')}>managed by auth mode</span>
								</div>
							)}
						</Field>
						<Field label="MODEL">
							<TextInput
								value={model}
								onChange={setModel}
								placeholder="provider/model"
								ariaLabel="Model id"
								options={modelOptions}
							/>
						</Field>
						<Field label="BASE URL">
							<TextInput
								value={baseUrl}
								onChange={setBaseUrl}
								placeholder={authMode === 'freellmapi' ? 'http://127.0.0.1:3001/v1' : 'optional OpenAI-compatible endpoint'}
								ariaLabel="Base URL"
							/>
						</Field>
						{(authMode === 'api_key' || authMode === 'freellmapi') && (
							<Field label="API KEY">
								<TextInput
									value={apiKey}
									onChange={setApiKey}
									placeholder={authMode === 'freellmapi' ? '(Optional) freellmapi-...' : 'leave blank to keep the stored credential'}
									ariaLabel="API key"
									password
								/>
							</Field>
						)}
						<Field label="REASONING EFFORT">
							<div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
								{EFFORT_LEVELS.map((level) => (
									<button
										key={level || 'default'}
										onClick={() => setEffort(level)}
										aria-pressed={effort === level}
										style={{
											padding: '6px 12px',
											borderRadius: 2,
											border: `1px solid ${effort === level ? 'rgba(0,229,255,0.5)' : 'var(--l2-hairline)'}`,
											background: effort === level ? 'rgba(0,229,255,0.08)' : 'transparent',
											color: effort === level ? 'var(--atlas-cyan)' : 'var(--l2-fg-2)',
											...mono(10)
										}}
									>
										{level === '' ? 'DEFAULT' : level.toUpperCase()}
									</button>
								))}
							</div>
						</Field>
					</div>
				</section>

				<section style={{ ...glassPanel(), padding: 20 }}>
					<SectionTitle icon={<RefreshCw size={13} />} text="FUNCTION ROUTING (CURATOR / AUXILIARY / JUDGE)" />
					<p style={{ ...mono(9.5, 'var(--l2-fg-3)'), marginTop: 8 }}>
						With autoconfig on, side tasks (curator review, compression, titles) bind to the lightest
						model on the active provider — e.g. Codex runs them on the mini tier. Overrides use
						provider/model form.
					</p>
					<div style={{ display: 'grid', gap: 12, marginTop: 12, maxWidth: 560 }}>
						<Field label="AUTOCONFIG">
							<button
								onClick={() => setFnAutoconfig((v) => !v)}
								aria-pressed={fnAutoconfig}
								style={{
									padding: '6px 14px',
									borderRadius: 2,
									border: `1px solid ${fnAutoconfig ? 'rgba(0,229,255,0.4)' : 'var(--l2-hairline)'}`,
									background: fnAutoconfig ? 'rgba(0,229,255,0.08)' : 'transparent',
									color: fnAutoconfig ? 'var(--atlas-cyan)' : 'var(--l2-fg-2)',
									...mono(10)
								}}
							>
								{fnAutoconfig ? 'ON — lightest model per provider' : 'OFF'}
							</button>
						</Field>
						<Field label="CURATOR MODEL">
							<TextInput value={fnCurator} onChange={setFnCurator} placeholder="auto (e.g. openai-codex/gpt-5.4-mini)" ariaLabel="Curator model override" />
						</Field>
						<Field label="AUXILIARY MODEL">
							<TextInput value={fnAuxiliary} onChange={setFnAuxiliary} placeholder="auto" ariaLabel="Auxiliary model override" />
						</Field>
						<Field label="JUDGE MODEL">
							<TextInput
								value={fnJudge}
								onChange={setFnJudge}
								placeholder="Inherit chat session"
								ariaLabel="Judge model override"
								options={modelOptions}
							/>
						</Field>
					</div>
				</section>

				<div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
					<ActionButton onClick={save} disabled={!canSave} icon={<Save size={12} />}>
						{busy ? 'SAVING…' : 'SAVE CONFIGURATION'}
					</ActionButton>
					<span style={mono(9.5, 'var(--l2-fg-3)')}>
						{revision !== undefined ? `revision ${revision}` : 'revision unavailable — update the gateway'}
					</span>
				</div>
			</div>
		</div>
	);
}

function ActiveStatusPanel({ status }: { status: ProviderStatusView | null }) {
	if (!status) return null;
	const live = !status.mock_mode;
	return (
		<section
			style={{
				...glassPanel({
					borderColor: live ? 'rgba(102,187,106,0.45)' : 'rgba(255,183,77,0.45)'
				}),
				padding: 20
			}}
		>
			<SectionTitle icon={<Cable size={13} />} text="ACTIVE STATUS" />
			<div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 10, alignItems: 'baseline' }}>
				<span style={mono(12, live ? 'var(--l2-success)' : 'var(--l2-warning)')}>
					{live ? 'LIVE' : 'MOCK MODE'}
				</span>
				<span style={mono(11, 'var(--l2-fg-1)')}>
					{status.provider}/{status.model}
				</span>
				<span style={mono(10, 'var(--l2-fg-3)')}>{status.auth_mode_label}</span>
				{status.reasoning_effort && (
					<span style={mono(10, 'var(--l2-fg-2)')}>effort: {status.reasoning_effort}</span>
				)}
			</div>
			{status.privacy_warning && (
				<p style={{ ...mono(10, 'var(--l2-warning)'), marginTop: 8 }}>{status.privacy_warning}</p>
			)}
			{status.remediation && (
				<p style={{ ...mono(10, 'var(--l2-fg-3)'), marginTop: 8 }}>fix: {status.remediation}</p>
			)}
		</section>
	);
}

function SectionTitle({ icon, text }: { icon: React.ReactNode; text: string }) {
	return (
		<h2 style={{ display: 'flex', alignItems: 'center', gap: 8, ...mono(10.5, 'var(--atlas-bronze)') }}>
			{icon}
			{text}
		</h2>
	);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<label style={{ display: 'grid', gap: 6 }}>
			<span style={mono(9.5, 'var(--l2-fg-3)')}>{label}</span>
			{children}
		</label>
	);
}

function TextInput({
	value,
	onChange,
	placeholder,
	ariaLabel,
	password,
	options
}: {
	value: string;
	onChange: (v: string) => void;
	placeholder?: string;
	ariaLabel: string;
	password?: boolean;
	options?: string[];
}) {
	const [focused, setFocused] = useState(false);
	const wrapperRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!focused || !options) return;
		function onDocClick(e: MouseEvent) {
			if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
				setFocused(false);
			}
		}
		document.addEventListener('mousedown', onDocClick);
		return () => document.removeEventListener('mousedown', onDocClick);
	}, [focused, options]);

	const filtered = options ? options.filter(o => o.toLowerCase().includes(value.toLowerCase())) : [];

	return (
		<div style={{ position: 'relative', width: '100%', flex: 1 }} ref={wrapperRef}>
			<input
				type={password ? 'password' : 'text'}
				value={value}
				onChange={(e) => onChange(e.target.value)}
				onFocus={(e) => {
					e.target.style.borderColor = 'rgba(0, 229, 255, 0.4)';
					setFocused(true);
				}}
				onBlur={(e) => {
					e.target.style.borderColor = 'var(--l2-hairline)';
				}}
				placeholder={placeholder}
				aria-label={ariaLabel}
				autoComplete="off"
				style={{
					width: '100%',
					padding: '9px 12px',
					borderRadius: 2,
					border: '1px solid var(--l2-hairline)',
					background: 'rgba(255,255,255,0.02)',
					color: 'var(--l2-fg-1)',
					outline: 'none',
					...mono(11)
				}}
			/>
			{options && focused && filtered.length > 0 && (
				<TopoScroll tone="info" className="atlas-dropdown-scroll" style={{
					position: 'absolute',
					top: '100%',
					left: 0,
					right: 0,
					marginTop: 4,
					background: 'var(--l2-void-card)',
					border: '1px solid var(--l2-hairline)',
					borderRadius: 2,
					maxHeight: 200,
					zIndex: 100,
					boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
					display: 'flex',
					flexDirection: 'column'
				}} viewportStyle={{ maxHeight: 200, display: 'flex', flexDirection: 'column' }}>
					{filtered.map(o => (
						<button
							key={o}
							onMouseDown={(e) => {
								e.preventDefault();
								onChange(o);
								setFocused(false);
							}}
							style={{
								padding: '8px 12px',
								textAlign: 'left',
								background: 'transparent',
								border: 'none',
								borderBottom: '1px solid rgba(255,255,255,0.03)',
								color: 'var(--l2-fg-1)',
								cursor: 'pointer',
								transition: 'background 100ms, color 100ms',
								...mono(11)
							}}
							onMouseEnter={(e) => {
								e.currentTarget.style.background = 'rgba(0, 229, 255, 0.1)';
								e.currentTarget.style.color = 'var(--l2-fg-0)';
							}}
							onMouseLeave={(e) => {
								e.currentTarget.style.background = 'transparent';
								e.currentTarget.style.color = 'var(--l2-fg-1)';
							}}
						>
							{o}
						</button>
					))}
				</TopoScroll>
			)}
		</div>
	);
}

function ActionButton({
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
				cursor: disabled ? 'default' : 'pointer',
				opacity: disabled ? 0.5 : 1,
				...mono(11)
			}}
		>
			{icon}
			{children}
		</button>
	);
}

function mono(size: number, color?: string): React.CSSProperties {
	return {
		fontFamily: 'var(--l2-font-mono)',
		fontSize: size,
		letterSpacing: '0.08em',
		...(color ? { color } : {})
	};
}
