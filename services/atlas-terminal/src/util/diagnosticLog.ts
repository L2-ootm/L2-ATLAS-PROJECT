/**
 * File-backed diagnostic capture for failures the TUI renderer makes
 * invisible: console.error under the fullscreen renderer is overdrawn, and
 * piped-stdio harnesses never exercise the interactive path (see
 * .debug/2026-07-04-session-creation-failure-investigation.md). Appending to
 * a well-known temp file means any operator reproduction persists evidence
 * without needing a console.
 */
import { appendFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export function diagnosticLogPath(): string {
	return join(tmpdir(), 'atlas-terminal-diagnostics.log');
}

export function appendDiagnostic(tag: string, detail: string): void {
	try {
		appendFileSync(diagnosticLogPath(), `${new Date().toISOString()} ${tag} ${detail}\n`);
	} catch {
		// best-effort — diagnostics must never break the UI
	}
}
