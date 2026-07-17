import { useCallback, useEffect, useState } from 'react';
import { Package, Download, Trash2 } from 'lucide-react';
import { glassPanel } from '../../lib/glass';
import { listComponents, componentAction, type ComponentStatus } from '../../lib/api';
import { invalidateComponentsCache } from '../../lib/agentRuntimes';

/**
 * Optional SDK components (claude/codex): availability + install/uninstall.
 * Uninstalled components hide their agent runtime across every picker, so
 * this panel is the one place the operator manages what ATLAS can drive.
 */
export function ComponentsPanel() {
	const [components, setComponents] = useState<ComponentStatus[] | null>(null);
	const [busy, setBusy] = useState<string | null>(null);
	const [err, setErr] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		setComponents(await listComponents());
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	async function act(c: ComponentStatus, action: 'install' | 'uninstall') {
		setBusy(c.name);
		setErr(null);
		try {
			await componentAction(c.name, action);
			invalidateComponentsCache();
			await refresh();
		} catch (e) {
			setErr(e instanceof Error ? e.message : String(e));
		} finally {
			setBusy(null);
		}
	}

	return (
		<section style={glassPanel({ overflow: 'hidden', marginTop: 16 })}>
			<header
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 10,
					padding: '14px 18px',
					borderBottom: '1px solid var(--l2-hairline)'
				}}
			>
				<Package size={14} strokeWidth={1.8} color="var(--atlas-bronze)" />
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.22em', color: 'var(--atlas-bronze)' }}>
					SDK COMPONENTS
				</span>
				<span style={{ marginLeft: 'auto', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.1em', color: 'var(--l2-fg-3)' }}>
					UNINSTALLED RUNTIMES ARE HIDDEN FROM PICKERS
				</span>
			</header>

			{err && (
				<div style={{ padding: '12px 18px', color: 'var(--l2-error)', fontSize: 12, fontFamily: 'var(--l2-font-mono)' }}>
					{err}
				</div>
			)}

			{components === null ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>Probing components…</div>
			) : components.length === 0 ? (
				<div style={{ padding: '24px 18px', color: 'var(--l2-fg-3)', fontSize: 13 }}>
					Component management requires an updated gateway/runtime.
				</div>
			) : (
				components.map((c, i) => (
					<div
						key={c.name}
						style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							gap: 16,
							padding: '15px 18px',
							borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)'
						}}
					>
						<div style={{ minWidth: 0 }}>
							<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
								<span style={{ color: 'var(--l2-fg-1)', fontSize: 14 }}>{c.name.toUpperCase()}</span>
								<Tag color={c.installed ? 'var(--atlas-emerald)' : 'var(--l2-fg-3)'}>
									{c.installed ? 'INSTALLED' : 'NOT INSTALLED'}
								</Tag>
								<Tag color={c.cli_present ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)'}>
									{c.cli_present ? 'CLI FOUND' : 'CLI MISSING'}
								</Tag>
							</div>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 12.5 }}>{c.description}</div>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 10.5, fontFamily: 'var(--l2-font-mono)', marginTop: 3 }}>
								{c.pip_requirement}
							</div>
						</div>
						<button
							type="button"
							disabled={busy !== null}
							onClick={() => void act(c, c.installed ? 'uninstall' : 'install')}
							style={{
								display: 'inline-flex',
								alignItems: 'center',
								gap: 7,
								padding: '8px 14px',
								borderRadius: 2,
								flex: 'none',
								border: `1px solid ${c.installed ? 'rgba(255,0,85,0.35)' : 'rgba(70,240,160,0.4)'}`,
								background: c.installed ? 'rgba(255,0,85,0.07)' : 'rgba(70,240,160,0.1)',
								color: c.installed ? 'var(--l2-error)' : 'var(--atlas-emerald)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10.5,
								letterSpacing: '0.14em',
								cursor: busy !== null ? 'default' : 'pointer',
								opacity: busy !== null && busy !== c.name ? 0.5 : 1
							}}
						>
							{c.installed ? <Trash2 size={13} strokeWidth={1.8} /> : <Download size={13} strokeWidth={1.8} />}
							{busy === c.name ? 'WORKING…' : c.installed ? 'UNINSTALL' : 'INSTALL'}
						</button>
					</div>
				))
			)}
		</section>
	);
}

function Tag({ children, color }: { children: React.ReactNode; color: string }) {
	return (
		<span
			style={{
				padding: '1px 7px',
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 8.5,
				letterSpacing: '0.16em',
				color
			}}
		>
			{children}
		</span>
	);
}
