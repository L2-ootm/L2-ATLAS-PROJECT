import {
	ArrowUpToLine,
	ListPlus,
	Pencil,
	SendHorizontal,
	Square,
	Trash2
} from 'lucide-react';
import type { AgentRuntime } from '../../lib/api';
import { agentRuntimeLabel } from '../../lib/api';
import type { QueuedChatPrompt } from '../../lib/chatPersistence';

export function QueuedChatComposer({
	draft,
	onDraftChange,
	queue,
	busy,
	agent,
	error,
	onSubmit,
	onCancel,
	onPromote,
	onEdit,
	onRemove
}: {
	draft: string;
	onDraftChange: (value: string) => void;
	queue: QueuedChatPrompt[];
	busy: boolean;
	agent: AgentRuntime;
	error: string | null;
	onSubmit: () => void;
	onCancel: () => void;
	onPromote: (id: string) => void;
	onEdit: (item: QueuedChatPrompt) => void;
	onRemove: (id: string) => void;
}) {
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
							<span className="chat-prompt-queue__text">{item.text}</span>
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
			<div className="chat-composer-shell" data-busy={busy ? 'true' : 'false'}>
				<textarea
					className="chat-composer-input"
					value={draft}
					onChange={(event) => onDraftChange(event.target.value)}
					onKeyDown={(event) => {
						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							onSubmit();
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
							onClick={onSubmit}
							disabled={!draft.trim()}
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
