<script lang="ts">
	import GlassPanel from '$lib/components/GlassPanel.svelte';
	import HudLabel from '$lib/components/HudLabel.svelte';
	import { createMission } from '$lib/api';
	import type { Mission } from '$lib/api';

	interface Props {
		open: boolean;
		onClose: () => void;
		onCreated: (mission: Mission) => void;
	}

	let { open, onClose, onCreated }: Props = $props();

	let title = $state('');
	let intent = $state('');
	let submitting = $state(false);
	let formError: string | null = $state(null);

	function handleDiscard() {
		title = '';
		intent = '';
		formError = null;
		onClose();
	}

	async function handleSubmit() {
		if (!title.trim() || submitting) return;
		submitting = true;
		formError = null;
		try {
			const result = await createMission(title.trim(), intent.trim());
			title = '';
			intent = '';
			onCreated(result.mission);
			onClose();
		} catch (err) {
			if (err instanceof Error) {
				formError = `MISSION CREATE FAILED — ${err.message}. Retry or check gateway logs.`;
			} else {
				formError = 'MISSION CREATE FAILED — Unknown error. Retry or check gateway logs.';
			}
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleDiscard();
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby="modal-title"
		class="overlay"
		tabindex="-1"
		onkeydown={handleKeydown}
	>
		<!-- Backdrop click to dismiss -->
		<button
			class="backdrop"
			onclick={handleDiscard}
			aria-label="Close modal"
			tabindex="-1"
		></button>

		<div class="modal-container">
			<GlassPanel style="border-radius: 8px; padding: 24px; min-width: 480px; position: relative; z-index: 1;">
				<div style="display: flex; flex-direction: column; gap: 20px;">
					<!-- Header -->
					<h2 id="modal-title" style="margin: 0;">
						<HudLabel>CREATE MISSION</HudLabel>
					</h2>

					<!-- TITLE field -->
					<div style="display: flex; flex-direction: column; gap: 6px;">
						<label
							for="mission-title"
							style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: #A0A0A0;"
						>
							TITLE
						</label>
						<input
							id="mission-title"
							type="text"
							bind:value={title}
							placeholder="Mission title"
							disabled={submitting}
							class="field-input"
							autocomplete="off"
						/>
					</div>

					<!-- INTENT field -->
					<div style="display: flex; flex-direction: column; gap: 6px;">
						<label
							for="mission-intent"
							style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; color: #A0A0A0;"
						>
							INTENT
						</label>
						<textarea
							id="mission-intent"
							bind:value={intent}
							placeholder="Describe the operator intent..."
							disabled={submitting}
							class="field-input"
							style="min-height: 96px; resize: vertical;"
						></textarea>
					</div>

					<!-- Inline error -->
					{#if formError}
						<div
							style="font-family: var(--l2-font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #FF0055; padding: 8px; background: rgba(255,0,85,0.08); border: 1px solid rgba(255,0,85,0.20); border-radius: 2px;"
							role="alert"
						>
							{formError}
						</div>
					{/if}

					<!-- Actions row -->
					<div style="display: flex; gap: 8px; justify-content: flex-end;">
						<button
							onclick={handleDiscard}
							class="btn-secondary"
							disabled={submitting}
						>
							DISCARD
						</button>
						<button
							onclick={handleSubmit}
							class="btn-primary"
							disabled={!title.trim() || submitting}
						>
							{submitting ? 'CREATING...' : 'CREATE MISSION'}
						</button>
					</div>
				</div>
			</GlassPanel>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.backdrop {
		position: absolute;
		inset: 0;
		background: transparent;
		border: none;
		cursor: default;
		z-index: 0;
	}

	.modal-container {
		position: relative;
		z-index: 1;
	}

	.field-input {
		width: 100%;
		box-sizing: border-box;
		background: rgba(255,255,255,0.05);
		border: 1px solid rgba(255,255,255,0.08);
		border-radius: 2px;
		color: #E0E0E0;
		font-family: var(--l2-font-sans);
		font-size: 16px;
		font-weight: 400;
		padding: 8px 12px;
		transition: border-color 150ms ease, box-shadow 150ms ease;
		outline: none;
	}

	.field-input::placeholder {
		color: rgba(255,255,255,0.20);
	}

	.field-input:focus {
		border-color: #7F00FF;
		box-shadow: 0 0 0 2px rgba(127,0,255,0.20);
	}

	.field-input:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		background: #7F00FF;
		border: 1px solid rgba(127,0,255,0.6);
		box-shadow: 0 0 24px rgba(127,0,255,0.35);
		color: #FFFFFF;
		font-family: var(--l2-font-mono);
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		border-radius: 2px;
		padding: 8px 16px;
		cursor: pointer;
		transition: background 80ms ease, border-color 80ms ease, box-shadow 80ms ease;
		outline-offset: 2px;
	}

	.btn-primary:hover:not(:disabled) {
		background: rgba(127,0,255,0.85);
		border-color: rgba(127,0,255,1);
	}

	.btn-primary:focus {
		outline: 2px solid rgba(127,0,255,0.6);
	}

	.btn-primary:disabled {
		opacity: 0.4;
		pointer-events: none;
		box-shadow: none;
	}

	.btn-secondary {
		background: rgba(20,20,20,0.60);
		border: 1px solid rgba(255,255,255,0.08);
		color: #A0A0A0;
		font-family: var(--l2-font-sans);
		font-size: 14px;
		font-weight: 600;
		letter-spacing: 0.05em;
		border-radius: 2px;
		padding: 8px 16px;
		cursor: pointer;
		transition: background 80ms ease, color 80ms ease;
		outline-offset: 2px;
	}

	.btn-secondary:hover:not(:disabled) {
		background: rgba(255,255,255,0.08);
		color: #E0E0E0;
	}

	.btn-secondary:focus {
		outline: 2px solid rgba(127,0,255,0.6);
	}

	.btn-secondary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
