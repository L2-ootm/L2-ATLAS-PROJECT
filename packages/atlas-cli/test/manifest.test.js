'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { listFiles } = require('../src/manifest');

test('release manifests exclude local test scratch artifacts', () => {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-manifest-'));
	try {
		fs.mkdirSync(path.join(root, '.pytest-cache'));
		fs.writeFileSync(path.join(root, '.pytest-cache', 'worker-state'), 'scratch');
		fs.writeFileSync(path.join(root, 'test_localsystem.txt'), 'scratch');
		fs.writeFileSync(path.join(root, 'runtime.txt'), 'product');

		assert.deepEqual(listFiles(root), ['runtime.txt']);
	} finally {
		fs.rmSync(root, { recursive: true, force: true });
	}
});
