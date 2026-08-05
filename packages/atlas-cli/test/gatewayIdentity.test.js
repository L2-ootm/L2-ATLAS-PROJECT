'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { parseIdentity, verifyIdentity } = require('../../../scripts/ci/verify-gateway-identity');

const valid = { service: 'atlas-gateway', release_version: '9.8.7', component_version: '0.1.0', build_sha: 'abc123' };

test('accepts matching compiled gateway identity', () => {
	assert.equal(verifyIdentity(valid, { releaseVersion: '9.8.7', buildSha: 'abc123' }), valid);
});

test('rejects release mismatch and stale skipped binary', () => {
	assert.throws(() => verifyIdentity(valid, { releaseVersion: '9.8.8', buildSha: 'abc123' }), /stale gateway binary: release/);
	assert.throws(() => verifyIdentity(valid, { releaseVersion: '9.8.7', buildSha: 'def456' }), /stale gateway binary: build/);
});

test('rejects malformed JSON and missing SHA', () => {
	assert.throws(() => parseIdentity('{nope'), /malformed version JSON/);
	assert.throws(() => verifyIdentity({ ...valid, build_sha: '' }, { releaseVersion: '9.8.7' }), /missing build_sha/);
});

test('development identity requires explicit allowance', () => {
	const dev = { ...valid, build_sha: 'dev' };
	assert.throws(() => verifyIdentity(dev, { releaseVersion: '9.8.7' }), /development build identity/);
	assert.equal(verifyIdentity(dev, { releaseVersion: '9.8.7', allowDev: true }), dev);
});
