import { useCallback, useEffect, useState } from 'react';
import { Server, Database, Copy, Check, Power, Wallet } from 'lucide-react';
import { Page } from '../components/Page';
import { glassPanel } from '../lib/glass';
import {
	checkHealth,
	listModules,
	setModuleActive,
	cashflowStatus,
	cashflowStart,
	cashflowStop,
	type Module,
	type CashflowStatus
} from '../lib/api';
import { isTauri, startGatewayViaShell } from '../lib/host';

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
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [busyId, setBusyId] = useState<string | null>(null);
	const [err, setErr] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		const [h, m] = await Promise.allSettled([checkHealth(), listModules()]);
		if (h.status === 'fulfilled') {
			setHealth(h.value);
			setOnline(true);
		} else {
			setHealth(null);
			setOnline(false);
		}
		if (m.status === 'fulfilled') setModules(m.value.modules);
		setLoad({ s: h.status === 'rejected' && m.status === 'rejected' ? 'error' : 'ready' });
	}, []);

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 15_000);
		return () => clearInterval(id);
	}, [refresh]);

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

			<ModulesPanel
				modules={modules}
				loading={load.s === 'loading'}
				offline={online === false}
				busyId={busyId}
				onToggle={toggle}
				err={err}
			/>

			{modules.some((m) => m.id === 'cashflow' && m.status === 'active') && <CashflowControl />}
		</Page>
	);
}

// ── cashflow process control (shown when the cashflow module is active) ──────
function CashflowControl() {
	const [st, setSt] = useState<CashflowStatus | null>(null);
	const [backend, setBackend] = useState<'local' | 'supabase'>('local');
	const [busy, setBusy] = useState(false);
	const [msg, setMsg] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		try {
			const s = await cashflowStatus();
			setSt(s);
			if (s.backend === 'local' || s.backend === 'supabase') setBackend(s.backend);
		} catch {
			setSt(null);
		}
	}, []);

	useEffect(() => {
		void refresh();
		const id = setInterval(() => void refresh(), 10_000);
		return () => clearInterval(id);
	}, [refresh]);

	async function action(kind: 'start' | 'stop') {
		setBusy(true);
		setMsg(null);
		try {
			const res = kind === 'start' ? await cashflowStart(backend) : await cashflowStop();
			setMsg(res.message);
			await refresh();
		} catch {
			setMsg(`Could not ${kind} cashflow — is the gateway running?`);
		} finally {
			setBusy(false);
		}
	}

	const running = st?.running === true;

	return (
		<section style={glassPanel({ overflow: 'hidden', marginTop: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
					<Wallet size={14} strokeWidth={1.6} color="var(--atlas-bronze)" />
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
						CASHFLOW PROCESS
					</span>
				</span>
				<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
					<span
						style={{
							width: 6,
							height: 6,
							borderRadius: '50%',
							background: running ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)',
							boxShadow: running ? '0 0 8px var(--atlas-cyan-glow)' : 'none'
						}}
					/>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em', color: running ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)' }}>
						{running ? 'RUNNING' : 'STOPPED'}
					</span>
				</span>
			</header>

			<div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
				<div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, letterSpacing: '0.2em', color: 'var(--l2-fg-3)' }}>
						DB BACKEND
					</span>
					<Segmented value={backend} options={['local', 'supabase']} disabled={running || busy} onChange={setBackend} />
					{running && (
						<span style={{ fontSize: 11.5, color: 'var(--l2-fg-3)' }}>stop to change backend</span>
					)}
				</div>

				<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
					<button
						onClick={() => action(running ? 'stop' : 'start')}
						disabled={busy}
						style={{
							padding: '9px 18px',
							borderRadius: 2,
							border: `1px solid ${running ? 'var(--l2-hairline)' : 'rgba(79,139,255,0.4)'}`,
							background: running ? 'transparent' : 'rgba(79,139,255,0.12)',
							color: running ? 'var(--l2-fg-2)' : 'var(--atlas-celestial)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 11,
							letterSpacing: '0.16em',
							textTransform: 'uppercase',
							cursor: busy ? 'default' : 'pointer',
							opacity: busy ? 0.6 : 1
						}}
					>
						{busy ? '…' : running ? 'Stop' : 'Start'}
					</button>
					{running && (
						<a
							href="http://localhost:3000"
							target="_blank"
							rel="noreferrer"
							style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.12em', color: 'var(--atlas-celestial)', textDecoration: 'none' }}
						>
							OPEN ↗
						</a>
					)}
				</div>

				{msg && <div style={{ color: 'var(--l2-fg-3)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>{msg}</div>}
			</div>
		</section>
	);
}

function Segmented({
	value,
	options,
	disabled,
	onChange
}: {
	value: string;
	options: ('local' | 'supabase')[];
	disabled: boolean;
	onChange: (v: 'local' | 'supabase') => void;
}) {
	return (
		<div style={{ display: 'inline-flex', border: '1px solid var(--l2-hairline)', borderRadius: 2, overflow: 'hidden' }}>
			{options.map((opt) => {
				const active = opt === value;
				return (
					<button
						key={opt}
						onClick={() => !disabled && onChange(opt)}
						disabled={disabled}
						style={{
							padding: '7px 14px',
							border: 'none',
							background: active ? 'rgba(79,139,255,0.16)' : 'transparent',
							color: active ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10.5,
							letterSpacing: '0.12em',
							textTransform: 'uppercase',
							cursor: disabled ? 'default' : 'pointer',
							opacity: disabled && !active ? 0.5 : 1
						}}
					>
						{opt}
					</button>
				);
			})}
		</div>
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
