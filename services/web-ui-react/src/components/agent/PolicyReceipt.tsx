import { ShieldCheck } from 'lucide-react';
import { parsePolicyReceipt } from '../../lib/surfaceContracts';
import type { ToolApproval } from '../../lib/api';

export default function PolicyReceipt({ approval }: { approval: ToolApproval }) {
	const receipt: ReturnType<typeof parsePolicyReceipt> = (() => {
		try {
			return parsePolicyReceipt(approval.policy_receipt);
		} catch {
			return { source_layer: 'hardline', reason_code: 'invalid_receipt', decision: 'deny' };
		}
	})();
	const hardline = receipt?.source_layer === 'hardline';
	const decision = approval.status === 'executed' ? 'ALLOWED' : 'DENIED';
	const source = hardline
		? 'HARDLINE SAFETY FLOOR'
		: String(receipt?.source_layer ?? approval.decision ?? 'AUTHORITY');
	return (
		<div className="policy-receipt" data-outcome={approval.status}>
			<ShieldCheck size={13} aria-hidden="true" />
			<div>
				<strong>{decision} · {source.toUpperCase()}</strong>
				<span>{approval.decided_at ?? approval.requested_at} · {approval.surface_kind ?? 'surface'}</span>
			</div>
		</div>
	);
}
