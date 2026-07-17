import { beforeEach, describe, expect, it } from 'vitest';
import {
	emptyChatSnapshot,
	loadChatSession,
	saveChatSession
} from '../lib/chatPersistence';

describe('chat prompt queue persistence', () => {
	beforeEach(() => localStorage.clear());

	it('restores queued prompts in order and enforces the four-item boundary', () => {
		const queuedPrompts = Array.from({ length: 5 }, (_, index) => ({
			id: `queue-${index}`,
			text: `prompt ${index}`
		}));
		saveChatSession('chat-queue', { ...emptyChatSnapshot(), queuedPrompts });
		const restored = loadChatSession('chat-queue');
		expect(restored?.queuedPrompts).toEqual(queuedPrompts.slice(0, 4));
	});
});
