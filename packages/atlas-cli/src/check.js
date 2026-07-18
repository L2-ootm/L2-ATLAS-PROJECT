'use strict';

const { checkLatestVersion, compareVersions, PACKAGE_NAME } = require('./selfUpdate');
const packageJson = require('../package.json');

/**
 * `atlas check` — report whether a newer @systemsl2/atlas release exists.
 *
 * npm is the real, CI-verified distribution channel (see
 * .github/workflows/publish-npm.yml + scripts/release/npm-release.ps1):
 * the launcher and its pinned platform runtime package publish together,
 * so comparing the launcher's own version against the npm registry's
 * `latest` dist-tag answers "is a newer runtime available" too. This is
 * read-only — unlike `atlas update`, it never installs anything.
 */
async function check(options = {}) {
	const current = options.currentVersion || packageJson.version;
	const latest = await checkLatestVersion(options.fetcher || fetch);
	const updateAvailable = compareVersions(latest, current) > 0;
	return { packageName: PACKAGE_NAME, current, latest, updateAvailable };
}

module.exports = { check };
