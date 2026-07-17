import {
	ArrowUpToLine,
	ListPlus,
	Pencil,
	SendHorizontal,
	Square,
	Trash2
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { AgentRuntime } from '../../lib/api';
import { agentRuntimeLabel } from '../../lib/api';
import { ATLAS_COMMANDS, expandCommandTemplate, matchAtlasCommands, type AtlasCommand } from '../../lib/atlasCommands';
import { loadAtlasCommandCatalog } from '../../lib/commandCatalog';
import type { QueuedChatPrompt } from '../../lib/chatPersistence';

export function QueuedChatComposer({
	draft,
	onDraftPersist,
	queue,
	busy,
	agent,
	error,
	onSubmit,
	onAction,
	onCancel,
	onPromote,
	onEdit,
	onRemove
}: {
	draft: string;
	onDraftPersist: (value: string) => void;
	queue: QueuedChatPrompt[];
	busy: boolean;
	agent: AgentRuntime;
	error: string | null;
	onSubmit: (draft: string, executionDraft?: string) => boolean;
	/** Local action commands (/help, /new, /agent …) — returns true when the
	 * action was handled and the draft should clear. Absent = actions hidden. */
	onAction?: (command: AtlasCommand, args: string) => boolean;
	onCancel: () => void;
	onPromote: (id: string) => void;
	onEdit: (item: QueuedChatPrompt) => void;
	onRemove: (id: string) => void;
}) {
	const [localDraft, setLocalDraft] = useState(draft);
	const [catalog, setCatalog] = useState<AtlasCommand[]>(ATLAS_COMMANDS);
	const [slashSelected, setSlashSelected] = useState(0);
	const scanRef = useRef<HTMLSpanElement>(null);
	const persistTimer = useRef<number | null>(null);
	useEffect(() => setLocalDraft(draft), [draft]);
	useEffect(() => {
		void loadAtlasCommandCatalog().then(setCatalog);
		return () => {
			if (persistTimer.current !== null) window.clearTimeout(persistTimer.current);
		};
	}, []);
	const visibleCatalog = useMemo(
		() => (onAction ? catalog : catalog.filter((command) => command.kind !== 'action')),
		[catalog, onAction]
	);
	const slashMatches = useMemo(
		() => localDraft.startsWith('/') && !localDraft.includes('\n') ? matchAtlasCommands(visibleCatalog, localDraft, 6) : [],
		[visibleCatalog, localDraft]
	);
	const slashHead = localDraft.split(/\s/, 1)[0];
	useEffect(() => setSlashSelected(0), [slashHead]);

	function persistSoon(value: string) {
		if (persistTimer.current !== null) window.clearTimeout(persistTimer.current);
		persistTimer.current = window.setTimeout(() => onDraftPersist(value), 350);
	}

	function changeDraft(value: string) {
		setLocalDraft(value);
		persistSoon(value);
		const scan = scanRef.current;
		if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && typeof scan?.animate === 'function') {
			if (typeof scan.getAnimations === 'function') scan.getAnimations().forEach((animation) => animation.cancel());
			scan.animate(
				[{ transform: 'translateY(-14px)', opacity: 0 }, { opacity: 0.18, offset: 0.35 }, { transform: 'translateY(72px)', opacity: 0 }],
				{ duration: 190, easing: 'cubic-bezier(.2,.8,.2,1)' }
			);
		}
	}

	function completeSlash(command: AtlasCommand) {
		const rest = localDraft.replace(/^\/\S+\s*/, '');
		changeDraft(`/${command.name}${rest ? ` ${rest}` : ' '}`);
	}

	function clearDraft() {
		if (persistTimer.current !== null) {
			window.clearTimeout(persistTimer.current);
			persistTimer.current = null;
		}
		setLocalDraft('');
		onDraftPersist('');
	}

	function submit() {
		const trimmed = localDraft.trim();
		const match = /^\/(\S+)(?:\s+([\s\S]*))?$/.exec(trimmed);
		const command = match ? visibleCatalog.find((item) => item.name === match[1].toLowerCase()) : undefined;
		if (command?.kind === 'action' && onAction) {
			if (onAction(command, match?.[2] ?? '')) clearDraft();
			return;
		}
		const execution = command ? expandCommandTemplate(command.template, match?.[2] ?? '') : localDraft;
		if (onSubmit(localDraft, execution)) clearDraft();
	}
	const placeholder = busy
		? `Write the next request for ${agentRuntimeLabel(agent)}`
		: agent === 'claude_code'
			? 'Ask Claude Code in this workspace'
			: agent === 'codex'
				? 'Ask Codex in this workspace'
				: 'Message ATLAS';

	return (
		<div className="chat-composer-region">
			{queue.length > 0 && (
				<div className="chat-prompt-queue" aria-label={`${queue.length} queued prompts`}>
					{queue.map((item, index) => (
						<div key={item.id} className="chat-prompt-queue__item">
							<span className="chat-prompt-queue__index">{index + 1}</span>
							<span className="chat-prompt-queue__text">{item.displayText ?? item.text}</span>
							<div className="chat-prompt-queue__actions">
								{index > 0 && (
									<button type="button" onClick={() => onPromote(item.id)} title="Run this prompt next" aria-label="Run this prompt next">
										<ArrowUpToLine size={13} />
									</button>
								)}
								<button type="button" onClick={() => onEdit(item)} title="Edit queued prompt" aria-label="Edit queued prompt">
									<Pencil size={13} />
								</button>
								<button type="button" onClick={() => onRemove(item.id)} title="Remove queued prompt" aria-label="Remove queued prompt">
									<Trash2 size={13} />
								</button>
							</div>
						</div>
					))}
				</div>
			)}
			{slashMatches.length > 0 && (
				<div className="chat-slash-suggestions" role="listbox" aria-label="Slash command suggestions">
					<div className="chat-slash-suggestions__rail" aria-hidden>
						<span>COMMAND INDEX</span><span>↑↓ SELECT · TAB COMPLETE</span>
					</div>
					{slashMatches.map((command, index) => (
						<button
							key={command.name}
							type="button"
							role="option"
							aria-selected={index === slashSelected}
							className={index === slashSelected ? 'is-active' : undefined}
							onMouseDown={(event) => event.preventDefault()}
							onClick={() => completeSlash(command)}
						>
							<strong>/{command.name}</strong>
							<span>{command.argumentHint ?? command.description}</span>
							<em>{command.source === 'module' ? command.module : 'CORE'}</em>
						</button>
					))}
				</div>
			)}
			<div className="chat-composer-shell" data-busy={busy ? 'true' : 'false'}>
				<span ref={scanRef} className="chat-composer-typing-scan" aria-hidden="true" />
				<textarea
					className="chat-composer-input"
					value={localDraft}
					onChange={(event) => changeDraft(event.target.value)}
					onKeyDown={(event) => {
						if (slashMatches.length && event.key === 'ArrowDown') {
							event.preventDefault();
							setSlashSelected((current) => Math.min(current + 1, slashMatches.length - 1));
							return;
						}
						if (slashMatches.length && event.key === 'ArrowUp') {
							event.preventDefault();
							setSlashSelected((current) => Math.max(current - 1, 0));
							return;
						}
						if (slashMatches.length && event.key === 'Tab') {
							event.preventDefault();
							completeSlash(slashMatches[slashSelected]);
							return;
						}
						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							const head = localDraft.slice(1).split(/\s/, 1)[0];
							if (slashMatches.length && slashMatches[slashSelected].name !== head) {
								completeSlash(slashMatches[slashSelected]);
								return;
							}
							submit();
						}
					}}
					placeholder={placeholder}
					rows={3}
				/>
				<div className="chat-composer-toolbar">
					<div className="chat-composer-toolbar__state">
						<ListPlus size={14} />
						<span>{busy ? `${queue.length}/4 queued · Enter adds next` : 'Enter to send · Shift+Enter for a line break'}</span>
					</div>
					<div className="chat-composer-toolbar__actions">
						{busy && (
							<button type="button" className="chat-composer-cancel" onClick={onCancel} title="Cancel the running turn" aria-label="Cancel the running turn">
								<Square size={13} fill="currentColor" />
							</button>
						)}
						<button
							type="button"
							className="chat-composer-submit"
							onClick={submit}
							disabled={!localDraft.trim()}
							title={busy ? 'Queue this prompt' : 'Send prompt'}
							aria-label={busy ? 'Queue this prompt' : 'Send prompt'}
						>
							{busy ? <ListPlus size={16} /> : <SendHorizontal size={16} />}
						</button>
					</div>
				</div>
			</div>
			{error && <div className="chat-composer-error" role="status">{error}</div>}
		</div>
	);
}
