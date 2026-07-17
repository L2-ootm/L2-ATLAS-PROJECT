#!/usr/bin/env node
'use strict';

const { buildPlatformPackage } = require('../../packages/atlas-cli/src/buildPlatformPackage');

function parseArgs(argv) {
	const opts = {};
	for (let i = 0; i < argv.length; i += 1) {
		const arg = argv[i];
		if (arg === '--bundle') opts.bundleDir = argv[++i];
		else if (arg === '--out-dir') opts.outDir = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--platform') opts.platform = argv[++i];
		else if (arg === '--entrypoint') opts.entrypoint = argv[++i];
	}
	return opts;
}

try {
	const opts = parseArgs(process.argv.slice(2));
	if (!opts.bundleDir || !opts.outDir || !opts.version || !opts.platform || !opts.entrypoint) {
		throw new Error('usage: build-platform-package --bundle dir --out-dir dir --version x --platform win32-x64 --entrypoint bin/atlas.exe');
	}
	const result = buildPlatformPackage(opts);
	console.log(`package: ${result.packageDir}`);
	console.log(`name: ${result.metadata.name}@${result.metadata.version}`);
} catch (error) {
	console.error(`FAIL build-platform-package: ${error.message}`);
	process.exitCode = 1;
}
