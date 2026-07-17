'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const { readInstallState } = require('./installState');
const { versionDir } = require('./paths');
const { readCurrent } = require('./commands');

function candidateEntrypoints(platform = process.platform) {
	return platform === 'win32'
		? ['bin/atlas.exe', 'atlas.exe']
		: ['bin/atlas', 'atlas'];
}

function resolveRuntimeEntrypoint(installRoot, platform = process.platform) {
	const current = readCurrent(installRoot);
	if (!current) return null;
	const root = path.resolve(versionDir(installRoot, current));
	const state = readInstallState(installRoot);
	const candidates = state?.runtimeEntrypoint
		? [state.runtimeEntrypoint]
		: candidateEntrypoints(platform);

	for (const relative of candidates) {
		const absolute = path.resolve(root, relative);
		if (!absolute.startsWith(`${root}${path.sep}`)) continue;
		if (fs.existsSync(absolute) && fs.statSync(absolute).isFile()) return absolute;
	}
	return null;
}

function launchRuntime(installRoot, args, options = {}) {
	const entrypoint = resolveRuntimeEntrypoint(installRoot, options.platform);
	if (!entrypoint) {
		throw new Error('ATLAS runtime entrypoint is not installed; run `atlas install`');
	}
	const isNodeScript = path.extname(entrypoint).toLowerCase() === '.js';
	const command = isNodeScript ? process.execPath : entrypoint;
	const commandArgs = isNodeScript ? [entrypoint, ...args] : args;
	const runner = options.spawn || spawnSync;
	const result = runner(command, commandArgs, {
		stdio: 'inherit',
		env: { ...process.env, ATLAS_INSTALL_ROOT: installRoot },
		shell: false
	});
	if (result.error) throw result.error;
	return result.status ?? 1;
}

module.exports = { candidateEntrypoints, resolveRuntimeEntrypoint, launchRuntime };
