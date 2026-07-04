'use strict';

const os = require('node:os');
const path = require('node:path');

/**
 * ATLAS_HOME layout (docs/plans/2026-07-03-wsb-installer-plan.md §3.1):
 *   ~/.atlas/versions/<version>/   — one directory per installed release
 *   ~/.atlas/current               — pointer file naming the active version
 *   ~/.atlas/install.json          — { installedVersion, installMethod, lastUpdateCheck }
 *
 * `current` is a plain text pointer file rather than a symlink/junction:
 * junctions need elevation for some operations on Windows, and a pointer
 * file makes rollback a single atomic write on every platform.
 */
function atlasHome(env = process.env) {
	return env.ATLAS_HOME || path.join(os.homedir(), '.atlas');
}

function versionsDir(home) {
	return path.join(home, 'versions');
}

function versionDir(home, version) {
	return path.join(versionsDir(home), version);
}

function currentPointerFile(home) {
	return path.join(home, 'current');
}

function installStateFile(home) {
	return path.join(home, 'install.json');
}

function manifestFile(versionPath) {
	return path.join(versionPath, 'manifest.json');
}

module.exports = {
	atlasHome,
	versionsDir,
	versionDir,
	currentPointerFile,
	installStateFile,
	manifestFile
};
