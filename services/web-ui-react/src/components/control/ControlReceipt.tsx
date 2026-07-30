import { RotateCcw } from 'lucide-react';
import { GlassPanel, HudLabel } from '../hud';

export interface ControlReceiptData {
	receipt_id: string;
	resource_type: string;
	resource_id: string;
	resource_name: string;
	action: string;
	before: string;
	after: string;
	actor: string;
	reason: string;
	timestamp: string;
	status: 'committed';
}

function timestampLabel(value: string): string {
	const parsed = Date.parse(value);
	return Number.isNaN(parsed) ? value : new Date(parsed).toLocaleString();
}

export function ControlReceipt({
	receipt,
	onUndo,
	undoBusy = false
}: {
	receipt: ControlReceiptData;
	onUndo?: () => void;
	undoBusy?: boolean;
}) {
	return (
		<div role="status" aria-label={`${receipt.resource_name} change receipt`}>
			<GlassPanel
				style={{ padding: 0, overflow: 'hidden', marginBottom: 14 }}
			>
				<div
					style={{
						display: 'flex',
						alignItems: 'center',
						gap: 12,
						padding: '10px 12px',
						borderBottom: '1px solid var(--l2-hairline)'
					}}
				>
					<span
						style={{
							width: 7,
							height: 7,
							borderRadius: '50%',
							background: 'var(--atlas-emerald)',
							boxShadow: '0 0 8px rgba(43, 211, 153, 0.45)'
						}}
					/>
					<HudLabel>CHANGE COMMITTED</HudLabel>
					<span
						style={{
							color: 'var(--l2-fg-3)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							marginLeft: 'auto'
						}}
					>
						{timestampLabel(receipt.timestamp)}
					</span>
					{onUndo && (
						<button
							type="button"
							onClick={onUndo}
							disabled={undoBusy}
							style={{
								display: 'inline-flex',
								alignItems: 'center',
								gap: 5,
								padding: '5px 8px',
								border: '1px solid var(--l2-hairline)',
								borderRadius: 2,
								background: 'transparent',
								color: 'var(--l2-fg-2)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 9.5,
								letterSpacing: '0.1em',
								cursor: undoBusy ? 'wait' : 'pointer',
								opacity: undoBusy ? 0.55 : 1
							}}
						>
							<RotateCcw size={11} />
							{undoBusy ? 'ROLLING BACK…' : 'UNDO'}
						</button>
					)}
				</div>
				<div
					style={{
						display: 'grid',
						gridTemplateColumns: 'minmax(180px, 1.2fr) minmax(160px, 1fr) minmax(220px, 2fr)',
						gap: 12,
						padding: '10px 12px',
						fontSize: 11.5
					}}
				>
					<div>
						<div style={{ color: 'var(--l2-fg-1)', fontWeight: 600 }}>{receipt.resource_name}</div>
						<div style={{ color: 'var(--l2-fg-3)', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, marginTop: 3 }}>
							{receipt.resource_type} · {receipt.receipt_id}
						</div>
					</div>
					<div style={{ fontFamily: 'var(--l2-font-mono)' }}>
						<span style={{ color: 'var(--l2-fg-3)' }}>{receipt.before}</span>
						<span style={{ color: 'var(--l2-fg-3)', margin: '0 7px' }}>→</span>
						<span style={{ color: 'var(--atlas-emerald)' }}>{receipt.after}</span>
					</div>
					<div>
						<div style={{ color: 'var(--l2-fg-2)' }}>{receipt.reason}</div>
						<div style={{ color: 'var(--l2-fg-3)', fontFamily: 'var(--l2-font-mono)', fontSize: 9.5, marginTop: 3 }}>
							ACTOR · {receipt.actor}
						</div>
					</div>
				</div>
			</GlassPanel>
		</div>
	);
}
