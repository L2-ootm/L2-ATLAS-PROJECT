#!/usr/bin/env node
'use strict';

const { buildReleaseIndex } = require('../../packages/atlas-cli/src/buildReleaseIndex');

function parseArgs(argv) {
	const opts = {};
	let i = 0;
	while (i < argv.length) {
		const arg = argv[i];
		if (arg === '--bundle') opts.bundleDir = argv[++i];
		else if (arg === '--out-dir') opts.outDir = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--platform') opts.platform = argv[++i];
		else if (arg === '--channel') opts.channel = argv[++i];
		else if (arg === '--base-url') opts.baseUrl = argv[++i];
		else if (arg === '--index-name') opts.indexName = argv[++i];
		else if (arg === '--commit') opts.commit = argv[++i];
		else if (arg === '--entrypoint') opts.entrypoint = argv[++i];
		i += 1;
	}
	return opts;
}

function usage() {
	console.error('usage: build-release-index --bundle dir --out-dir dir --version x --platform os-arch [--entrypoint bin/atlas.exe] [--channel stable] [--base-url url]');
}

try {
	const opts = parseArgs(process.argv.slice(2));
	if (!opts.bundleDir || !opts.outDir || !opts.version || !opts.platform) {
		usage();
		process.exit(1);
	}
	const result = buildReleaseIndex(opts);
	console.log(`archive: ${result.archivePath}`);
	console.log(`index: ${result.indexPath}`);
	console.log(`sha256: ${result.index.releases[result.version].platforms[result.platform].sha256}`);
} catch (err) {
	console.error(`FAIL build-release-index: ${err.message}`);
	process.exit(1);
}
