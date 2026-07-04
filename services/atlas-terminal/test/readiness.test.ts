import { describe, expect, it } from 'bun:test';
import { readinessFor, type ProviderStatus } from '../src/tui/util/readiness';

// Mirrors services/atlas-tui/internal/tui/readiness_test.go's cases so both
// TUI surfaces classify provider health identically.
function status(overrides: Partial<ProviderStatus> = {}): ProviderStatus {
	return {
		provider: '',
		model: '',
		auth_mode: '',
		auth_mode_label: '',
		base_url: null,
		credentials_present: false,
		mock_mode: false,
		remediation: null,
		reasoning_effort: null,
		privacy_warning: null,
		...overrides
	};
}

describe('readinessFor', () => {
	it('is LIVE when not mock and provider/model are set', () => {
		const r = readinessFor(status({ provider: 'openrouter', model: 'anthropic/claude-sonnet-4' }), false);
		expect(r).toEqual({ kind: 'live', canRun: true, label: 'LIVE', remediation: '' });
	});

	it('fails closed to UNCONFIGURED on a zero-value projection, never LIVE', () => {
		const r = readinessFor(status(), false);
		expect(r.kind).toBe('unconfigured');
		expect(r.canRun).toBe(false);
	});

	it('is MOCK / EXPLICIT when mock_mode and allowMock are both set', () => {
		const r = readinessFor(status({ mock_mode: true, remediation: 'set an API key' }), true);
		expect(r).toEqual({ kind: 'mock', canRun: true, label: 'MOCK / EXPLICIT', remediation: 'set an API key' });
	});

	it('is DEGRADED when mock but credentials are present and mock is not explicitly allowed', () => {
		const r = readinessFor(status({ mock_mode: true, credentials_present: true }), false);
		expect(r.kind).toBe('degraded');
		expect(r.canRun).toBe(false);
	});

	it('is UNCONFIGURED when mock, no credentials, and mock not allowed', () => {
		const r = readinessFor(status({ mock_mode: true, credentials_present: false }), false);
		expect(r.kind).toBe('unconfigured');
		expect(r.canRun).toBe(false);
	});
});
