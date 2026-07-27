import {
	ArrowUpToLine,
	ListPlus,
	Paperclip,
	Pencil,
	SendHorizontal,
	Square,
	Trash2,
	X
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { AgentRuntime } from '../../lib/api';
import { agentRuntimeLabel } from '../../lib/api';
import { ATLAS_COMMANDS, expandCommandTemplate, matchAtlasCommands, type AtlasCommand } from '../../lib/atlasCommands';
import { loadAtlasCommandCatalog } from '../../lib/commandCatalog';
import type { QueuedChatPrompt } from '../../lib/chatPersistence';

// The gateway's only prompt channel is `createMission(title, intent)` — a text
// intent. There is no multipart/attachment endpoint, so a text-like file is
// inlined into the prompt behind a delimiter and anything binary is rejected
// with a visible reason rather than silently dropped.
interface ChatAttachment {
	id: string;
	name: string;
	mimeType: string;
	size: number;
	/** Decoded text content — what actually reaches the agent. */
	text: string;
}

interface RejectedAttachment {
	id: string;
	name: string;
	reason: string;
}

/** Wrap each attachment in a fenced, labelled block so the agent can tell
 * operator prose from file content. */
function attachmentsToPrompt(prompt: string, attachments: ChatAttachment[]): string {
	if (attachments.length === 0) return prompt;
	const blocks = attachments.map(
		(att) => `--- ATTACHED FILE: ${att.name} (${att.mimeType || 'text/plain'}, ${att.size} bytes) ---\n${att.text}\n--- END ${att.name} ---`
	);
	return prompt ? `${prompt}\n\n${blocks.join('\n\n')}` : blocks.join('\n\n');
}

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
	const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
	const [rejected, setRejected] = useState<RejectedAttachment[]>([]);
	const fileInputRef = useRef<HTMLInputElement>(null);
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
		setAttachments([]);
		setRejected([]);
		onDraftPersist('');
	}

	// Inlined into the prompt, so the cap is about prompt size, not upload size.
	const MAX_FILE_SIZE = 256 * 1024; // 256KB of text per file
	const MAX_FILES = 5;
	const TEXT_TYPES = ['text/plain', 'text/markdown', 'text/csv', 'application/json'];
	const TEXT_EXTENSIONS = /\.(txt|md|csv|json|py|js|ts|jsx|tsx|html|css|yaml|yml|toml|sql|sh|rs|go|toml|ini|log|xml)$/i;
	const ACCEPT_HINT = [...TEXT_TYPES, '.md', '.py', '.ts', '.tsx', '.js', '.jsx', '.yaml', '.yml', '.toml', '.rs', '.go', '.sh', '.sql'].join(',');

	function noteRejection(name: string, reason: string) {
		setRejected((prev) => [
			...prev,
			{ id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, name, reason }
		]);
	}

	function isTextLike(file: File): boolean {
		if (TEXT_TYPES.includes(file.type)) return true;
		if (file.type.startsWith('text/')) return true;
		// Editors often report an empty type for source files; trust the extension.
		return (file.type === '' || !file.type.includes('/')) && TEXT_EXTENSIONS.test(file.name);
	}

	function handleFiles(files: FileList | File[]) {
		const fileArray = Array.from(files);
		setRejected([]);
		let slots = MAX_FILES - attachments.length;

		for (const file of fileArray) {
			if (slots <= 0) {
				noteRejection(file.name, `over the ${MAX_FILES}-file limit`);
				continue;
			}
			if (!isTextLike(file)) {
				noteRejection(
					file.name,
					`${file.type || 'binary'} is not supported — the agent accepts text only`
				);
				continue;
			}
			if (file.size > MAX_FILE_SIZE) {
				noteRejection(
					file.name,
					`${(file.size / 1024).toFixed(0)}KB exceeds the ${MAX_FILE_SIZE / 1024}KB text limit`
				);
				continue;
			}
			slots -= 1;

			const reader = new FileReader();
			reader.onerror = () => noteRejection(file.name, 'could not be read');
			reader.onload = (e) => {
				const result = e.target?.result;
				if (typeof result !== 'string') {
					noteRejection(file.name, 'could not be decoded as text');
					return;
				}
				setAttachments((prev) => [
					...prev,
					{
						id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
						name: file.name,
						mimeType: file.type || 'text/plain',
						size: file.size,
						text: result
					}
				]);
			};
			reader.readAsText(file);
		}
	}

	function removeAttachment(id: string) {
		setAttachments((prev) => prev.filter((a) => a.id !== id));
	}

	function handlePaste(event: React.ClipboardEvent) {
		const items = event.clipboardData?.items;
		if (!items) return;

		const files: File[] = [];
		for (const item of Array.from(items)) {
			if (item.kind === 'file') {
				const file = item.getAsFile();
				if (file) files.push(file);
			}
		}
		if (files.length > 0) {
			event.preventDefault();
			handleFiles(files);
		}
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
		// Display keeps the operator's own words; the executed prompt carries the
		// inlined file content, which is the only channel the gateway accepts.
		const display = attachments.length > 0
			? `${localDraft}${localDraft ? '\n\n' : ''}${attachments.map((a) => `📎 ${a.name}`).join('\n')}`
			: localDraft;
		if (onSubmit(display, attachmentsToPrompt(execution, attachments))) clearDraft();
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
			{attachments.length > 0 && (
				<div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '6px 10px', borderBottom: '1px solid rgba(237,234,224,0.06)' }}>
					{attachments.map((att) => (
						<div
							key={att.id}
							style={{
								display: 'flex',
								alignItems: 'center',
								gap: 6,
								padding: '4px 8px',
								borderRadius: 2,
								border: '1px solid rgba(237,234,224,0.10)',
								background: 'rgba(13,16,24,0.45)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 11,
								color: 'var(--l2-fg-2)'
							}}
						>
							<Paperclip size={11} aria-hidden="true" />
							<span>{att.name}</span>
							<span style={{ color: 'var(--l2-fg-3)', fontSize: 10 }}>
								{(att.size / 1024).toFixed(0)}KB
							</span>
							<button
								type="button"
								onClick={() => removeAttachment(att.id)}
								title={`Remove ${att.name}`}
								aria-label={`Remove ${att.name}`}
								style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', padding: 0, display: 'flex' }}
							>
								<X size={12} />
							</button>
						</div>
					))}
				</div>
			)}
			{rejected.length > 0 && (
				<div
					role="status"
					style={{
						display: 'flex',
						flexDirection: 'column',
						gap: 3,
						padding: '6px 10px',
						borderBottom: '1px solid rgba(237,234,224,0.06)',
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10.5,
						color: 'var(--l2-error)'
					}}
				>
					{rejected.map((item) => (
						<div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
							<span>NOT ATTACHED · {item.name} — {item.reason}</span>
							<button
								type="button"
								onClick={() => setRejected((prev) => prev.filter((r) => r.id !== item.id))}
								title="Dismiss"
								aria-label={`Dismiss ${item.name}`}
								style={{ background: 'none', border: 'none', color: 'var(--l2-error)', cursor: 'pointer', padding: 0, marginLeft: 'auto', display: 'flex' }}
							>
								<X size={11} />
							</button>
						</div>
					))}
				</div>
			)}
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
				<input
					ref={fileInputRef}
					type="file"
					multiple
					accept={ACCEPT_HINT}
					style={{ display: 'none' }}
					onChange={(e) => {
						if (e.target.files) handleFiles(e.target.files);
						e.target.value = '';
					}}
				/>
				<textarea
					className="chat-composer-input"
					value={localDraft}
					onChange={(event) => changeDraft(event.target.value)}
					onPaste={handlePaste}
					onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = 'rgba(79,139,255,0.5)'; }}
					onDragLeave={(e) => { e.currentTarget.style.borderColor = ''; }}
					onDrop={(e) => {
						e.preventDefault();
						e.currentTarget.style.borderColor = '';
						if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
					}}
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
						<button
							type="button"
							onClick={() => fileInputRef.current?.click()}
							title="Attach text files — their contents are inlined into the prompt (images and other binaries are not supported)"
							aria-label="Attach text files"
							style={{
								display: 'inline-flex',
								alignItems: 'center',
								justifyContent: 'center',
								width: 28,
								height: 28,
								borderRadius: 2,
								border: '1px solid rgba(237,234,224,0.10)',
								background: 'transparent',
								color: 'var(--l2-fg-3)',
								cursor: 'pointer'
							}}
						>
							<Paperclip size={14} />
						</button>
						{busy && (
							<button type="button" className="chat-composer-cancel" onClick={onCancel} title="Cancel the running turn" aria-label="Cancel the running turn">
								<Square size={13} fill="currentColor" />
							</button>
						)}
						<button
							type="button"
							className="chat-composer-submit"
							onClick={submit}
							disabled={!localDraft.trim() && attachments.length === 0}
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
