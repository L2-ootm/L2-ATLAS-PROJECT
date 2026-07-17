'use strict';

const os = require('node:os');
const path = require('node:path');

/**
 * Application install layout (state remains separately owned by ATLAS_HOME):
 *   <install-root>/versions/<version>/ — one immutable release
 *   <install-root>/current              — active version pointer
 *   <install-root>/install.json         — lifecycle metadata
 *
 * `current` is a plain text pointer file rather than a symlink/junction:
 * junctions need elevation for some operations on Windows, and a pointer
 * file makes rollback a single atomic write on every platform.
 */
function atlasInstallRoot(env = process.env, platform = process.platform) {
	if (env.ATLAS_INSTALL_ROOT) return path.resolve(env.ATLAS_INSTALL_ROOT);
	if (platform === 'win32') {
		return path.join(env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'atlas');
	}
	if (platform === 'darwin') {
		return path.join(os.homedir(), 'Library', 'Application Support', 'atlas');
	}
	return path.join(env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share'), 'atlas');
}

function atlasStateHome(env = process.env) {
	return path.resolve(env.ATLAS_HOME || path.join(os.homedir(), '.atlas'));
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
	atlasInstallRoot,
	atlasStateHome,
	versionsDir,
	versionDir,
	currentPointerFile,
	installStateFile,
	manifestFile
};
