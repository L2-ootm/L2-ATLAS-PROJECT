#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { verifyCleanInstall } = require('../../packages/atlas-cli/src/verifyCleanInstall');

function parseArgs(argv) {
	const opts = {};
	for (let i = 0; i < argv.length; i += 1) {
		const arg = argv[i];
		if (arg === '--manifest') opts.manifest = argv[++i];
		else if (arg === '--update-manifest') opts.updateManifest = argv[++i];
		else if (arg === '--channel') opts.channel = argv[++i];
		else if (arg === '--platform') opts.platform = argv[++i];
		else if (arg === '--home') opts.home = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--update-version') opts.updateVersion = argv[++i];
	}
	return opts;
}

function usage() {
	console.log('usage: verify-clean-install --manifest url --update-manifest url [--channel stable] [--platform os-arch] [--home dir]');
}

async function main() {
	const opts = parseArgs(process.argv.slice(2));
	if (!opts.manifest || !opts.updateManifest) {
		usage();
		process.exitCode = 2;
		return;
	}
	opts.home = opts.home || fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-clean-install-'));

	const report = await verifyCleanInstall(opts);
	for (const step of report.steps) {
		console.log(`${step.ok ? 'OK' : 'FAIL'} ${step.name}: ${step.detail}`);
	}
	if (!report.ok) process.exitCode = 1;
}

main().catch((err) => {
	console.error(`FAIL verify-clean-install: ${err.message}`);
	process.exitCode = 1;
});
