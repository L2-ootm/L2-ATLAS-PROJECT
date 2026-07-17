import { useState } from 'react';
import type { AuditEvent } from '../lib/api';
import type { AuditLogItem } from '../lib/logProjection';

// SseEventRow — one line of the audit stream. Mono + tabular: timestamp ·
// event_type chip · tool · duration · policy chip. New rows blur in (isNew);
// the parent fires a topo sonar-ping at the row's position when it lands.

export const ROW_GRID = '92px 150px 1fr 78px 96px';

function policyStyle(result: string | null): { color: string; bg: string; border: string } {
	switch ((result ?? '').toLowerCase()) {
		case 'allow':
		case 'allowed':
		case 'ok':
			return { color: '#46F0E0', bg: 'rgba(70,240,224,0.10)', border: 'rgba(70,240,224,0.30)' };
		case 'deny':
		case 'denied':
		case 'block':
		case 'blocked':
			return { color: '#FF4D7D', bg: 'rgba(255,0,85,0.10)', border: 'rgba(255,0,85,0.30)' };
		case 'warn':
		case 'review':
			return { color: '#FFD600', bg: 'rgba(255,214,0,0.10)', border: 'rgba(255,214,0,0.28)' };
		default:
			return { color: 'var(--l2-fg-3)', bg: 'transparent', border: 'var(--l2-hairline)' };
	}
}

function ts(iso: string): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '—';
	return d.toLocaleTimeString('en-GB', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

export default function SseEventRow({
	event,
	isNew,
	group
}: {
	event: AuditEvent;
	isNew: boolean;
	group?: AuditLogItem;
}) {
	const pol = policyStyle(event.policy_result);
	const [expanded, setExpanded] = useState(false);
	const grouped = !!group && group.count > 1;
	return (
		<>
		<div
			role={grouped ? 'button' : 'listitem'}
			tabIndex={grouped ? 0 : undefined}
			aria-expanded={grouped ? expanded : undefined}
			onClick={grouped ? () => setExpanded((value) => !value) : undefined}
			onKeyDown={grouped ? (e) => {
				if (e.key === 'Enter' || e.key === ' ') {
					e.preventDefault();
					setExpanded((value) => !value);
				}
			} : undefined}
			style={{
				display: 'grid',
				gridTemplateColumns: ROW_GRID,
				gap: 12,
				alignItems: 'center',
				padding: '7px 14px',
				borderBottom: '1px solid rgba(237,234,224,0.04)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 11.5,
				lineHeight: 1.5,
				animation: isNew ? 'atlas-blur-in 0.4s var(--l2-ease) both' : 'none',
				cursor: grouped ? 'pointer' : 'default',
				background: expanded ? 'rgba(79,139,255,0.055)' : 'transparent'
			}}
		>
			<span style={{ color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
				{ts(event.timestamp)}
			</span>
			<span
				style={{
					color: 'var(--atlas-celestial)',
					textTransform: 'uppercase',
					letterSpacing: '0.08em',
					overflow: 'hidden',
					textOverflow: 'ellipsis',
					whiteSpace: 'nowrap'
				}}
			>
				{event.event_type}{grouped ? ` ×${group.count}` : ''}
			</span>
			<span style={{ color: 'var(--l2-fg-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
				{grouped ? `${group.charCount.toLocaleString()} chars · #${group.firstCursor}–${group.lastCursor}` : event.tool_name ?? '—'}
			</span>
			<span style={{ color: 'var(--l2-fg-3)', fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>
				{event.duration_ms != null ? `${event.duration_ms}ms` : '—'}
			</span>
			<span style={{ textAlign: 'right' }}>
				{event.policy_result ? (
					<span
						style={{
							fontSize: 10,
							letterSpacing: '0.08em',
							textTransform: 'uppercase',
							padding: '2px 7px',
							borderRadius: 3,
							color: pol.color,
							background: pol.bg,
							border: `1px solid ${pol.border}`
						}}
					>
						{event.policy_result}
					</span>
				) : (
					<span style={{ color: 'var(--l2-fg-ghost)' }}>—</span>
				)}
			</span>
		</div>
		{grouped && expanded && (
			<div
				style={{
					padding: '10px 14px 12px 118px',
					borderBottom: '1px solid rgba(79,139,255,0.16)',
					background: 'rgba(4,7,12,0.72)',
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 11,
					lineHeight: 1.55,
					color: 'var(--l2-fg-2)',
					whiteSpace: 'pre-wrap',
					wordBreak: 'break-word',
					maxHeight: 220,
					overflowY: 'auto'
				}}
			>
				{group.text || 'Delta payload contains no text.'}
			</div>
		)}
		</>
	);
}
