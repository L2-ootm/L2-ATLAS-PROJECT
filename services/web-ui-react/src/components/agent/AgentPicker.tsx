import React, { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Check } from 'lucide-react';
import { agentRuntimeLabel, type AgentRuntime } from '../../lib/api';
import { AGENT_RUNTIME_OPTIONS } from '../../lib/agentRuntimeOptions';

/** Accent color per runtime, used for the active chip and menu marks. */
function runtimeAccent(agent: AgentRuntime): string {
	switch (agent) {
		case 'claude_code':
			return 'var(--atlas-bronze)';
		case 'codex':
			return 'var(--atlas-signal, #00FF94)';
		default:
			return 'var(--atlas-celestial)';
	}
}

/**
 * Dropdown selector for the agent runtime executing a surface's runs.
 * Replaces the fixed two-button segment toggle so new runtimes (codex, future
 * module-provided agents) join without layout growth.
 */
export function AgentPicker({
	value,
	onChange,
	disabled,
	placement = 'bottom'
}: {
	value: AgentRuntime;
	onChange: (agent: AgentRuntime) => void;
	disabled?: boolean;
	placement?: 'top' | 'bottom';
}) {
	const [open, setOpen] = useState(false);
	const rootRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		if (!open) return;
		const onDown = (e: MouseEvent) => {
			if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
		};
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setOpen(false);
		};
		window.addEventListener('mousedown', onDown);
		window.addEventListener('keydown', onKey);
		return () => {
			window.removeEventListener('mousedown', onDown);
			window.removeEventListener('keydown', onKey);
		};
	}, [open]);

	const accent = runtimeAccent(value);
	return (
		<div ref={rootRef} style={{ position: 'relative' }}>
			<button
				type="button"
				disabled={disabled}
				onClick={() => setOpen((v) => !v)}
				style={{ ...chipStyle, borderColor: open ? accent : 'rgba(237,234,224,0.12)', color: accent, opacity: disabled ? 0.5 : 1 }}
				title="Agent runtime"
				aria-haspopup="listbox"
				aria-expanded={open}
			>
				<Bot size={13} strokeWidth={1.7} />
				{agentRuntimeLabel(value)}
				<ChevronDown size={12} strokeWidth={1.8} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform 120ms' }} />
			</button>
			{open && (
				<div
					style={{
						...menuStyle,
						top: placement === 'bottom' ? 'calc(100% + 6px)' : 'auto',
						bottom: placement === 'top' ? 'calc(100% + 6px)' : 'auto'
					}}
					role="listbox"
					data-topo="atlas"
				>
					<div style={menuTitleStyle}>AGENT RUNTIME</div>
					{AGENT_RUNTIME_OPTIONS.map((option) => {
						const active = option.value === value;
						const color = runtimeAccent(option.value);
						return (
							<button
								key={option.value}
								type="button"
								role="option"
								aria-selected={active}
								style={{ ...itemStyle, background: active ? 'rgba(237,234,224,0.05)' : 'transparent' }}
								onClick={() => {
									onChange(option.value);
									setOpen(false);
								}}
							>
								<span style={{ ...itemLabelStyle, color: active ? color : 'var(--l2-fg-1)' }}>
									{agentRuntimeLabel(option.value)}
								</span>
								<span style={itemDescriptionStyle}>{option.description}</span>
								{active && <Check size={12} strokeWidth={2} style={{ color, flexShrink: 0 }} />}
							</button>
						);
					})}
				</div>
			)}
		</div>
	);
}

const chipStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	border: '1px solid rgba(237,234,224,0.12)',
	background: 'rgba(237,234,224,0.03)',
	borderRadius: 2,
	padding: '6px 10px',
	height: 30,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.13em',
	textTransform: 'uppercase',
	cursor: 'pointer',
	whiteSpace: 'nowrap'
};

const menuStyle: React.CSSProperties = {
	position: 'absolute',
	top: 'calc(100% + 6px)',
	right: 0,
	zIndex: 60,
	minWidth: 260,
	border: '1px solid rgba(237,234,224,0.12)',
	background: 'rgba(10,13,20,0.98)',
	borderRadius: 2,
	padding: 6,
	boxShadow: '0 18px 52px rgba(0,0,0,0.55)'
};

const menuTitleStyle: React.CSSProperties = {
	padding: '4px 8px 6px',
	color: 'var(--l2-fg-3)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.16em'
};

const itemStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	width: '100%',
	border: 'none',
	color: 'var(--l2-fg-1)',
	textAlign: 'left',
	padding: '7px 8px',
	borderRadius: 1,
	cursor: 'pointer'
};

const itemLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.12em',
	minWidth: 96,
	flexShrink: 0
};

const itemDescriptionStyle: React.CSSProperties = {
	color: 'var(--l2-fg-3)',
	fontSize: 11,
	lineHeight: 1.35,
	flex: 1
};
