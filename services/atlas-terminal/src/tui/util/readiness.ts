/**
 * Ported from services/atlas-tui/internal/tui/readiness.go (readinessFor /
 * mockAllowed) so both TUI surfaces classify provider health identically.
 */

export type ReadinessKind = 'live' | 'unconfigured' | 'degraded' | 'mock';

export interface ExecutionReadiness {
	kind: ReadinessKind;
	canRun: boolean;
	label: string;
	remediation: string;
}

export interface ProviderStatus {
	provider: string;
	model: string;
	auth_mode: string;
	auth_mode_label: string;
	base_url: string | null;
	credentials_present: boolean;
	mock_mode: boolean;
	remediation: string | null;
	reasoning_effort: string | null;
	privacy_warning: string | null;
}

export function readinessFor(status: ProviderStatus, allowMock: boolean): ExecutionReadiness {
	const remediation = status.remediation?.trim() ?? '';

	if (!status.mock_mode) {
		// A zero-value projection (gateway hiccup, fetch not yet resolved) must
		// never read as LIVE — fail closed to onboarding.
		if (!status.provider?.trim() && !status.model?.trim()) {
			return { kind: 'unconfigured', canRun: false, label: 'PROVIDER SETUP REQUIRED', remediation };
		}
		return { kind: 'live', canRun: true, label: 'LIVE', remediation: '' };
	}

	if (allowMock) {
		return { kind: 'mock', canRun: true, label: 'MOCK / EXPLICIT', remediation };
	}

	if (status.credentials_present) {
		return { kind: 'degraded', canRun: false, label: 'PROVIDER DEGRADED', remediation };
	}

	return { kind: 'unconfigured', canRun: false, label: 'PROVIDER SETUP REQUIRED', remediation };
}

export function mockAllowed(): boolean {
	const value = (process.env['ATLAS_TUI_ALLOW_MOCK'] ?? '').trim().toLowerCase();
	return value === '1' || value === 'true' || value === 'yes';
}
