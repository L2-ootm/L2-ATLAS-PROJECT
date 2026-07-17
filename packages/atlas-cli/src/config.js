'use strict';

const packageJson = require('../package.json');

const DEFAULT_RELEASE_MANIFEST = packageJson.atlas?.releaseManifest;

function releaseManifest(env = process.env) {
	return env.ATLAS_RELEASE_MANIFEST || DEFAULT_RELEASE_MANIFEST;
}

module.exports = { DEFAULT_RELEASE_MANIFEST, releaseManifest };
