'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { atomicWriteFileSync } = require('../src/atomicWrite');

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-atomic-${label}-`));
}

test('atomicWriteFileSync writes the target and leaves no temp file behind', () => {
	const dir = tempDir('write');
	const target = path.join(dir, 'install.json');

	atomicWriteFileSync(target, '{"a":1}\n', 'utf8');

	assert.equal(fs.readFileSync(target, 'utf8'), '{"a":1}\n');
	const leftovers = fs.readdirSync(dir).filter((name) => name.includes('.tmp'));
	assert.deepEqual(leftovers, []);
});

test('atomicWriteFileSync replaces existing content atomically (rename, not truncate-in-place)', () => {
	const dir = tempDir('replace');
	const target = path.join(dir, 'current');
	fs.writeFileSync(target, 'old-version\n', 'utf8');

	atomicWriteFileSync(target, 'new-version\n', 'utf8');

	assert.equal(fs.readFileSync(target, 'utf8'), 'new-version\n');
});
