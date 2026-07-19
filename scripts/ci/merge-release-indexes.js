#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { findIndexFiles, mergeReleaseIndexFiles } = require('../../packages/atlas-cli/src/mergeReleaseIndexes');

function parseArgs(argv) {
	const opts = {};
	let i = 0;
	while (i < argv.length) {
		const arg = argv[i];
		if (arg === '--dir') opts.dir = argv[++i];
		else if (arg === '--out') opts.out = argv[++i];
		else if (arg === '--pattern') opts.pattern = argv[++i];
		i += 1;
	}
	return opts;
}

function usage() {
	console.error('usage: merge-release-indexes --dir dir [--out file] [--pattern index.json]');
}

try {
	const opts = parseArgs(process.argv.slice(2));
	if (!opts.dir) {
		usage();
		process.exit(1);
	}
	const dir = path.resolve(opts.dir);
	if (!fs.existsSync(dir)) throw new Error(`directory not found: ${dir}`);
	const pattern = opts.pattern || 'index.json';
	const files = findIndexFiles(dir, pattern);
	if (files.length === 0) throw new Error(`no ${pattern} files found under ${dir}`);

	const merged = mergeReleaseIndexFiles(files);
	const outPath = path.resolve(opts.out || path.join(dir, 'index.json'));
	fs.writeFileSync(outPath, JSON.stringify(merged, null, 2) + '\n', 'utf8');

	console.log(`merged ${files.length} indexes -> ${outPath}`);
	for (const file of files) console.log(`  + ${file}`);
} catch (err) {
	console.error(`FAIL merge-release-indexes: ${err.message}`);
	process.exit(1);
}
