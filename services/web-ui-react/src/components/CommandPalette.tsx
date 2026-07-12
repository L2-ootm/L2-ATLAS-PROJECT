import { useEffect, useMemo, useRef, useState } from 'react';
import type * as React from 'react';
import { SquareSlash } from 'lucide-react';
import { ATLAS_COMMANDS, expandCommandTemplate } from '../lib/atlasCommands';

interface CommandPaletteProps {
	open: boolean;
	onClose: () => void;
	/** Composer is locked on a pending turn — list renders but execute is disabled. */
	busy: boolean;
	/** Run an expanded command: `display` echoes what the operator typed
	 * (`/review HEAD~1`), `prompt` is the expanded template sent to the agent. */
	onRun: (display: string, prompt: string) => void;
}

/**
 * Cmd+K / Ctrl+K slash-command palette for the Console — TUI parity for the six
 * built-in commands (init/review/dream/distill/goal/deep-research). Input works
 * like the TUI composer: first token picks the command, the rest are arguments
 * substituted into the template's `$ARGUMENTS` slot.
 */
export default function CommandPalette({ open, onClose, busy, onRun }: CommandPaletteProps) {
	const [query, setQuery] = useState('');
	const [selected, setSelected] = useState(0);
	const inputRef = useRef<HTMLInputElement>(null);

	const [head, args] = useMemo(() => {
		const trimmed = query.replace(/^\//, '');
		const space = trimmed.indexOf(' ');
		if (space < 0) return [trimmed, ''];
		return [trimmed.slice(0, space), trimmed.slice(space + 1)];
	}, [query]);

	const matches = useMemo(() => {
		const needle = head.toLowerCase();
		if (!needle) return ATLAS_COMMANDS;
		const exact = ATLAS_COMMANDS.filter((c) => c.name === needle);
		if (exact.length) return exact;
		return ATLAS_COMMANDS.filter(
			(c) => c.name.includes(needle) || c.description.toLowerCase().includes(needle)
		);
	}, [head]);

	useEffect(() => {
		if (open) {
			setQuery('');
			setSelected(0);
			// Focus after the overlay paints.
			window.setTimeout(() => inputRef.current?.focus(), 0);
		}
	}, [open]);

	useEffect(() => {
		setSelected((s) => Math.min(s, Math.max(0, matches.length - 1)));
	}, [matches.length]);

	if (!open) return null;

	function execute() {
		const command = matches[selected];
		if (!command || busy) return;
		const display = `/${command.name}${args.trim() ? ` ${args.trim()}` : ''}`;
		onRun(display, expandCommandTemplate(command.template, args));
		onClose();
	}

	function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			setSelected((s) => Math.min(s + 1, matches.length - 1));
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			setSelected((s) => Math.max(s - 1, 0));
		} else if (e.key === 'Enter') {
			e.preventDefault();
			execute();
		} else if (e.key === 'Tab' && matches[selected]) {
			// Tab completes the command name so arguments can follow.
			e.preventDefault();
			setQuery(`${matches[selected].name} `);
		}
	}

	return (
		<div
			role="dialog"
			aria-modal="true"
			aria-label="Command palette"
			onMouseDown={(e) => {
				if (e.target === e.currentTarget) onClose();
			}}
			style={{
				position: 'fixed',
				inset: 0,
				zIndex: 4000,
				display: 'flex',
				justifyContent: 'center',
				alignItems: 'flex-start',
				paddingTop: '18vh',
				background: 'rgba(4,4,6,0.55)',
				backdropFilter: 'blur(3px)'
			}}
		>
			<div
				style={{
					width: 'min(560px, calc(100vw - 48px))',
					borderRadius: 'var(--l2-radius)',
					border: '1px solid var(--l2-glass-border-lo)',
					background: 'linear-gradient(180deg, rgba(14,14,18,0.96), rgba(8,8,11,0.98))',
					boxShadow: '0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(79,139,255,0.08)',
					overflow: 'hidden'
				}}
			>
				<div
					style={{
						display: 'flex',
						alignItems: 'center',
						gap: 10,
						padding: '12px 14px',
						borderBottom: '1px solid var(--l2-glass-border-lo)'
					}}
				>
					<SquareSlash size={15} strokeWidth={1.5} color="var(--atlas-celestial)" aria-hidden="true" />
					<input
						ref={inputRef}
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						onKeyDown={onKeyDown}
						placeholder="command [arguments] — e.g. review HEAD~1"
						aria-label="Slash command"
						spellCheck={false}
						style={{
							flex: 1,
							background: 'none',
							border: 'none',
							outline: 'none',
							color: 'var(--l2-fg-1)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 13,
							letterSpacing: '0.02em'
						}}
					/>
					<span
						style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 9,
							letterSpacing: '0.18em',
							color: 'var(--l2-fg-3)',
							border: '1px solid var(--l2-glass-border-lo)',
							borderRadius: 2,
							padding: '2px 6px'
						}}
					>
						ESC
					</span>
				</div>
				<ul role="listbox" aria-label="Commands" style={{ listStyle: 'none', margin: 0, padding: 6, maxHeight: 320, overflowY: 'auto' }}>
					{matches.length === 0 && (
						<li
							style={{
								padding: '14px 12px',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 11,
								letterSpacing: '0.08em',
								color: 'var(--l2-fg-3)'
							}}
						>
							NO MATCHING COMMAND
						</li>
					)}
					{matches.map((command, i) => {
						const active = i === selected;
						return (
							<li key={command.name} role="option" aria-selected={active}>
								<button
									onMouseEnter={() => setSelected(i)}
									onClick={execute}
									disabled={busy}
									style={{
										display: 'flex',
										alignItems: 'baseline',
										gap: 10,
										width: '100%',
										textAlign: 'left',
										padding: '9px 10px',
										borderRadius: 'var(--l2-radius)',
										border: 'none',
										cursor: busy ? 'not-allowed' : 'pointer',
										background: active ? 'rgba(79,139,255,0.10)' : 'transparent',
										boxShadow: active ? 'inset 0 0 0 1px rgba(79,139,255,0.22)' : 'none'
									}}
								>
									<span
										style={{
											fontFamily: 'var(--l2-font-mono)',
											fontSize: 12.5,
											fontWeight: 600,
											color: active ? 'var(--atlas-celestial)' : 'var(--l2-fg-1)',
											whiteSpace: 'nowrap'
										}}
									>
										/{command.name}
									</span>
									<span
										style={{
											fontFamily: 'var(--l2-font-mono)',
											fontSize: 10.5,
											color: 'var(--l2-fg-3)',
											letterSpacing: '0.02em',
											overflow: 'hidden',
											textOverflow: 'ellipsis',
											whiteSpace: 'nowrap'
										}}
									>
										{command.description}
									</span>
								</button>
							</li>
						);
					})}
				</ul>
				<div
					style={{
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'space-between',
						padding: '8px 14px',
						borderTop: '1px solid var(--l2-glass-border-lo)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 9,
						letterSpacing: '0.16em',
						color: busy ? 'var(--l2-warn, #FFD600)' : 'var(--l2-fg-3)'
					}}
				>
					<span>{busy ? 'AGENT BUSY · WAIT FOR THE ACTIVE TURN' : '↑↓ SELECT · TAB COMPLETE · ↵ RUN'}</span>
					<span>{matches.length}/{ATLAS_COMMANDS.length}</span>
				</div>
			</div>
		</div>
	);
}
