import type { EvidenceFileChange } from '../../lib/api';

export function FileChangeReceipt({
	file,
	actorId,
	durationMs,
	onInspect
}: {
	file: EvidenceFileChange;
	actorId?: string | null;
	durationMs?: number | null;
	onInspect: (file: EvidenceFileChange) => void;
}) {
	const warning = file.availability !== 'available';
	return (
		<button
			type="button"
			aria-label={`Inspect ${file.path}`}
			onClick={() => onInspect(file)}
			style={{
				display: 'grid',
				gridTemplateColumns: '82px minmax(0, 1fr) auto auto minmax(70px, auto) auto',
				alignItems: 'center',
				gap: 10,
				width: '100%',
				padding: '8px 10px',
				border: `1px solid ${warning ? 'rgba(242,182,90,0.35)' : 'var(--l2-hairline)'}`,
				borderRadius: 2,
				background: warning ? 'rgba(242,182,90,0.06)' : 'rgba(8,10,15,0.5)',
				color: 'var(--l2-fg-2)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11,
				textAlign: 'left',
				cursor: 'pointer'
			}}
		>
			<span style={{ color: 'var(--atlas-celestial)', letterSpacing: '0.1em' }}>
				{file.operation.toUpperCase()}
			</span>
			<span
				title={file.path}
				style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
			>
				{file.path}
			</span>
			<span style={{ color: 'var(--l2-good, #46f0a0)' }}>+{file.additions}</span>
			<span style={{ color: 'var(--l2-error, #ff4d7d)' }}>−{file.deletions}</span>
			<span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
				{actorId ?? 'operator'}
			</span>
			<span>{durationMs == null ? '—' : `${durationMs} ms`}</span>
			{warning && (
				<span
					style={{
						gridColumn: '1 / -1',
						color: 'var(--l2-warning, #f2b65a)',
						fontSize: 10,
						letterSpacing: '0.08em'
					}}
				>
					{file.availability.toUpperCase()} EVIDENCE
					{file.redaction_count > 0 ? ` · ${file.redaction_count} REDACTIONS` : ''}
				</span>
			)}
		</button>
	);
}

