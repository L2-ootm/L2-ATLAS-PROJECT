'use strict';

/**
 * Reader for infra/release/payload.manifest — the single declaration of what
 * ships inside a platform runtime bundle.
 *
 * Three parsers exist for this format, one per consumer language:
 *   - Invoke-PayloadManifest  in scripts/ci/build-windows-runtime.ps1
 *   - apply_payload_manifest  in scripts/ci/build-linux-runtime.sh and
 *                                scripts/ci/build-darwin-runtime.sh
 *   - readPayloadManifest     here, for Node-side tooling and tests
 *
 * They must stay behaviourally identical; packages/atlas-cli/test/payloadManifest.test.js
 * asserts the build scripts still delegate to the manifest rather than carrying
 * their own copy of the list.
 */

const fs = require('node:fs');
const path = require('node:path');

const MODES = new Set(['tracked', 'tree']);

/**
 * Parse a payload manifest.
 *
 * @param {string} manifestPath
 * @returns {{mode: 'tracked'|'tree', pathspec: string, line: number}[]}
 */
function readPayloadManifest(manifestPath) {
	const text = fs.readFileSync(manifestPath, 'utf8');
	const entries = [];
	const lines = text.split(/\r?\n/);
	for (let index = 0; index < lines.length; index += 1) {
		const raw = lines[index];
		const trimmed = raw.trim();
		if (!trimmed || trimmed.startsWith('#')) continue;
		const match = /^(\S+)\s+(.*\S)\s*$/.exec(trimmed);
		if (!match) {
			throw new Error(`malformed payload manifest line ${index + 1}: ${raw}`);
		}
		const [, mode, pathspec] = match;
		if (!MODES.has(mode)) {
			throw new Error(
				`unknown payload manifest mode '${mode}' on line ${index + 1}: ${raw}`
			);
		}
		entries.push({ mode, pathspec, line: index + 1 });
	}
	if (entries.length === 0) {
		throw new Error(`payload manifest declared no entries: ${manifestPath}`);
	}
	return entries;
}

function defaultManifestPath(repoRoot) {
	return path.join(repoRoot, 'infra', 'release', 'payload.manifest');
}

module.exports = { readPayloadManifest, defaultManifestPath, MODES };
