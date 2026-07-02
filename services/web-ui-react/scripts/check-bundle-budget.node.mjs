// The .node.mjs suffix keeps this node:test suite outside Vitest discovery.
import assert from 'node:assert/strict';
import test from 'node:test';
import {
	classifyChunk,
	evaluateBundle
} from './check-bundle-budget.mjs';

test('classifies stable entry and vendor chunk names', () => {
	assert.equal(classifyChunk('index-abc.js'), 'entry');
	assert.equal(classifyChunk('vendor-react-abc.js'), 'react');
	assert.equal(classifyChunk('vendor-force-graph-abc.js'), 'graph');
	assert.equal(classifyChunk('Console-abc.js'), 'other');
});

test('accepts chunks at the explicit raw and gzip ceilings', () => {
	const result = evaluateBundle([
		{ name: 'index-a.js', rawBytes: 350_000, gzipBytes: 100_000 },
		{ name: 'vendor-react-a.js', rawBytes: 300_000, gzipBytes: 100_000 },
		{ name: 'vendor-force-graph-a.js', rawBytes: 1_400_000, gzipBytes: 400_000 },
		{ name: 'Console-a.js', rawBytes: 500_000, gzipBytes: 499_000 }
	]);

	assert.deepEqual(result.violations, []);
});

test('reports missing stable chunks and every exceeded budget', () => {
	const result = evaluateBundle([
		{ name: 'index-a.js', rawBytes: 350_001, gzipBytes: 100_001 },
		{ name: 'Console-a.js', rawBytes: 500_001, gzipBytes: 1 }
	]);

	assert.ok(result.violations.some((message) => message.includes('entry raw')));
	assert.ok(result.violations.some((message) => message.includes('entry gzip')));
	assert.ok(result.violations.some((message) => message.includes('Console-a.js raw')));
	assert.ok(result.violations.some((message) => message.includes('missing React vendor')));
	assert.ok(result.violations.some((message) => message.includes('missing graph vendor')));
});
