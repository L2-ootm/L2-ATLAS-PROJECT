import type { CSSProperties, ReactNode } from 'react';
import { agentRuntimeLabel, type AgentRuntime } from '../lib/api';

// Semantic glow colors (UX-VISUAL-SPEC Law 4 — color is context, never theme).
export type GlowTone = 'info' | 'ai' | 'good' | 'warn' | 'bad' | 'atlas';
const GLOW_BLEED: Record<GlowTone, string> = {
	info: 'rgba(79,139,255,0.22)',
	ai: 'rgba(161,123,255,0.22)',
	good: 'rgba(70,240,224,0.20)',
	warn: 'rgba(255,214,0,0.18)',
	bad: 'rgba(255,77,125,0.22)',
	atlas: 'rgba(224,169,78,0.18)'
};

// ── Panel — PlasmaGlass: a hairline-framed ink band lifted by a specular top
//    edge + inner light, never a floating glass card. Optional bronze top-accent
//    marks it as a brand surface; optional semantic `glow` lets plasma bleed up
//    through the lower edge (UX-VISUAL-SPEC §3). ──────────────────────────────
export function GlassPanel({
	children,
	className,
	style,
	topo,
	accent = false,
	glow
}: {
	children?: ReactNode;
	className?: string;
	style?: CSSProperties;
	topo?: string;
	accent?: boolean;
	glow?: GlowTone;
}) {
	return (
		<div
			className={className}
			data-topo={topo}
			style={{
				position: 'relative',
				background: 'linear-gradient(180deg, rgba(21,24,32,0.62), rgba(11,13,18,0.62))',
				border: '1px solid var(--l2-hairline)',
				backdropFilter: 'blur(14px) saturate(1.35)',
				WebkitBackdropFilter: 'blur(14px) saturate(1.35)',
				borderRadius: 2,
				boxShadow: 'inset 0 1px 0 rgba(237,234,224,0.06), 0 1px 0 rgba(0,0,0,0.5)',
				overflow: 'hidden',
				...style
			}}
		>
			{glow && (
				<span
					aria-hidden="true"
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						bottom: 0,
						height: '55%',
						pointerEvents: 'none',
						background: `radial-gradient(120% 100% at 50% 130%, ${GLOW_BLEED[glow]}, transparent 70%)`
					}}
				/>
			)}
			{accent && (
				<span
					aria-hidden="true"
					style={{
						position: 'absolute',
						top: 0,
						left: 0,
						right: 0,
						height: 1,
						background:
							'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)',
						opacity: 0.55
					}}
				/>
			)}
			{children}
		</div>
	);
}

// ── HudLabel — the system speaking. Mono, tracked, uppercase. ───────────────
export function HudLabel({ children, style }: { children?: ReactNode; style?: CSSProperties }) {
	return (
		<span
			style={{
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 12,
				textTransform: 'uppercase',
				letterSpacing: '0.2em',
				color: 'var(--l2-fg-2)',
				...style
			}}
		>
			{children}
		</span>
	);
}

// ── StatusBadge — lifecycle state, status-color law (unchanged). ────────────
interface BadgeStyle {
	background: string;
	border: string;
	color: string;
}
function getBadgeStyle(s: string): BadgeStyle {
	switch (s.toUpperCase()) {
		case 'PENDING':
			return { background: 'rgba(161,123,255,0.10)', border: 'rgba(161,123,255,0.32)', color: '#A17BFF' };
		case 'RUNNING':
			return { background: 'rgba(79,139,255,0.12)', border: 'rgba(79,139,255,0.36)', color: '#4F8BFF' };
		case 'SUCCEEDED':
		case 'COMPLETED':
			return { background: 'rgba(70,240,224,0.10)', border: 'rgba(70,240,224,0.30)', color: '#46F0E0' };
		case 'FAILED':
			return { background: 'rgba(255,0,85,0.10)', border: 'rgba(255,0,85,0.30)', color: '#FF4D7D' };
		case 'CANCELLED':
		case 'CANCELED':
			return { background: 'rgba(255,77,125,0.06)', border: 'rgba(255,77,125,0.22)', color: '#C77' };
		case 'PARTIAL':
			return { background: 'rgba(255,214,0,0.10)', border: 'rgba(255,214,0,0.28)', color: '#FFD600' };
		default:
			return { background: 'rgba(237,234,224,0.04)', border: 'var(--l2-hairline)', color: '#9BA0AD' };
	}
}
export function StatusBadge({ status }: { status: string }) {
	const s = getBadgeStyle(status);
	return (
		<span
			style={{
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 12,
				textTransform: 'uppercase',
				letterSpacing: '0.1em',
				padding: '4px 8px',
				borderRadius: 4,
				border: `1px solid ${s.border}`,
				background: s.background,
				color: s.color
			}}
		>
			{status.toUpperCase()}
		</span>
	);
}

// ── AgentBadge — which runtime a run was recorded against (P4 modular agents).
//    Reuses the StatusBadge shape language; color is context (info blue = native
//    ATLAS, AI purple = the operator's Claude Code session).
function getAgentStyle(agent: AgentRuntime): BadgeStyle {
	return agent === 'claude_code'
		? { background: 'rgba(161,123,255,0.10)', border: 'rgba(161,123,255,0.32)', color: '#A17BFF' }
		: { background: 'rgba(79,139,255,0.10)', border: 'rgba(79,139,255,0.30)', color: '#4F8BFF' };
}
export function AgentBadge({ agent }: { agent: AgentRuntime }) {
	const s = getAgentStyle(agent);
	return (
		<span
			title={`Agent runtime: ${agentRuntimeLabel(agent)}`}
			style={{
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10,
				textTransform: 'uppercase',
				letterSpacing: '0.14em',
				padding: '3px 7px',
				borderRadius: 4,
				border: `1px solid ${s.border}`,
				background: s.background,
				color: s.color,
				whiteSpace: 'nowrap'
			}}
		>
			{agentRuntimeLabel(agent)}
		</span>
	);
}
