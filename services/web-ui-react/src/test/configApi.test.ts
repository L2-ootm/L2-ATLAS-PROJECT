import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, patchConfig } from '../lib/api';

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('owned configuration API', () => {
	it('fails locally without leaking an unauthenticated mutation to the gateway', async () => {
		const fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);

		await expect(patchConfig(2, { 'provider.model': 'next/model' })).rejects.toMatchObject({
			status: 403,
			code: 'surface_owner_missing'
		});
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('binds the owner token, session id, and bounded reason to one request', async () => {
		localStorage.setItem(
			'atlas.agent-surface.reconnect.v1',
			JSON.stringify({ id: 'surface-1', ownerToken: 'owner-secret' })
		);
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ revision: 3, receipt: null }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);
		vi.stubGlobal('fetch', fetchMock);

		await patchConfig(2, { 'provider.model': 'next/model' }, 'operator selected model');

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.headers).toMatchObject({ 'x-atlas-surface-owner': 'owner-secret' });
		expect(JSON.parse(String(init.body))).toEqual({
			expected_revision: 2,
			changes: { 'provider.model': 'next/model' },
			surface_session_id: 'surface-1',
			reason: 'operator selected model'
		});
	});

	it('preserves committed partial-failure state so callers never auto-retry', async () => {
		localStorage.setItem(
			'atlas.agent-surface.reconnect.v1',
			JSON.stringify({ id: 'surface-1', ownerToken: 'owner-secret' })
		);
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(
					JSON.stringify({
						error: {
							code: 'config_audit_failed',
							message: 'config committed but audit failed',
							remediation: 'reconcile before retrying'
						},
						current_revision: 3,
						committed: true
					}),
					{ status: 500, headers: { 'Content-Type': 'application/json' } }
				)
			)
		);

		try {
			await patchConfig(2, { 'provider.model': 'next/model' });
			expect.unreachable('patchConfig should reject');
		} catch (error) {
			expect(error).toBeInstanceOf(ApiError);
			expect(error).toMatchObject({
				code: 'config_audit_failed',
				currentRevision: 3,
				committed: true
			});
		}
	});
});
