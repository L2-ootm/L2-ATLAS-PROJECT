'use strict';

const { spawnSync } = require('node:child_process');
const packageJson = require('../package.json');

const PACKAGE_NAME = packageJson.name;
const REGISTRY_LATEST = `https://registry.npmjs.org/${encodeURIComponent(PACKAGE_NAME)}/latest`;

function versionParts(value) {
	const match = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/.exec(String(value));
	if (!match) throw new Error(`invalid package version: ${value}`);
	return { numbers: match.slice(1, 4).map(Number), prerelease: match[4] || null };
}

function compareVersions(left, right) {
	const a = versionParts(left);
	const b = versionParts(right);
	for (let i = 0; i < 3; i += 1) {
		if (a.numbers[i] !== b.numbers[i]) return a.numbers[i] < b.numbers[i] ? -1 : 1;
	}
	if (a.prerelease === b.prerelease) return 0;
	if (a.prerelease === null) return 1;
	if (b.prerelease === null) return -1;
	return a.prerelease.localeCompare(b.prerelease, undefined, { numeric: true });
}

async function checkLatestVersion(fetcher = fetch) {
	const response = await fetcher(REGISTRY_LATEST, { headers: { accept: 'application/json' } });
	if (!response.ok) throw new Error(`npm registry check failed (${response.status})`);
	const metadata = await response.json();
	versionParts(metadata.version);
	return metadata.version;
}

async function updateLauncher(options = {}) {
	const current = options.currentVersion || packageJson.version;
	const latest = await checkLatestVersion(options.fetcher || fetch);
	if (compareVersions(latest, current) <= 0) return { updated: false, current, latest };

	const runner = options.spawn || spawnSync;
	const result = runner('npm', ['install', '--global', `${PACKAGE_NAME}@${latest}`], {
		stdio: 'inherit',
		shell: process.platform === 'win32'
	});
	if (result.error) throw result.error;
	if (result.status !== 0) throw new Error(`npm launcher update failed (exit ${result.status})`);
	return { updated: true, current, latest };
}

function handoffUpdatedLauncher(args = [], options = {}) {
	const runner = options.spawn || spawnSync;
	const node = options.node || process.execPath;
	const entrypoint = options.entrypoint || process.argv[1];
	const result = runner(node, [entrypoint, 'update', ...args, '--no-launcher-update'], {
		stdio: 'inherit',
		shell: false,
		env: options.env || process.env
	});
	if (result.error) throw result.error;
	return result.status ?? 1;
}

module.exports = {
	PACKAGE_NAME,
	REGISTRY_LATEST,
	compareVersions,
	checkLatestVersion,
	updateLauncher,
	handoffUpdatedLauncher
};
