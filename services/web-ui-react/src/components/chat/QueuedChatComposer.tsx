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

interface ChatAttachment {
	id: string;
	name: string;
	type: 'image' | 'file';
	mimeType: string;
	size: number;
	data?: string; // base64 for images
	previewUrl?: string;
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
		onDraftPersist('');
	}

	const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
	const MAX_FILES = 5;
	const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml'];
	const ALLOWED_TYPES = [...IMAGE_TYPES, 'application/pdf', 'text/plain', 'text/markdown', 'text/csv', 'application/json'];

	function handleFiles(files: FileList | File[]) {
		const fileArray = Array.from(files);
		if (attachments.length + fileArray.length > MAX_FILES) {
			return; // Silently ignore excess files
		}

		for (const file of fileArray) {
			if (file.size > MAX_FILE_SIZE) continue;
			if (!ALLOWED_TYPES.includes(file.type) && !file.name.match(/\.(txt|md|csv|json|py|js|ts|jsx|tsx|html|css|yaml|yml|toml)$/i)) {
				continue;
			}

			const reader = new FileReader();
			const isImage = IMAGE_TYPES.includes(file.type);

			reader.onload = (e) => {
				const result = e.target?.result as string;
				const attachment: ChatAttachment = {
					id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
					name: file.name,
					type: isImage ? 'image' : 'file',
					mimeType: file.type,
					size: file.size,
					data: isImage ? result : undefined,
					previewUrl: isImage ? URL.createObjectURL(file) : undefined
				};
				setAttachments((prev) => [...prev, attachment]);
			};

			if (isImage) {
				reader.readAsDataURL(file);
			} else {
				reader.readAsText(file);
			}
		}
	}

	function removeAttachment(id: string) {
		setAttachments((prev) => {
			const att = prev.find((a) => a.id === id);
			if (att?.previewUrl) URL.revokeObjectURL(att.previewUrl);
			return prev.filter((a) => a.id !== id);
		});
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
							{att.type === 'image' && att.previewUrl && (
								<img src={att.previewUrl} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: 1 }} />
							)}
							<span>{att.name}</span>
							<span style={{ color: 'var(--l2-fg-3)', fontSize: 10 }}>
								{(att.size / 1024).toFixed(0)}KB
							</span>
							<button
								type="button"
								onClick={() => removeAttachment(att.id)}
								style={{ background: 'none', border: 'none', color: 'var(--l2-fg-3)', cursor: 'pointer', padding: 0, display: 'flex' }}
							>
								<X size={12} />
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
					accept={ALLOWED_TYPES.join(',')}
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
							title="Attach files"
							aria-label="Attach files"
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
