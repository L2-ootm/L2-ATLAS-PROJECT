'use strict';

const fs = require('node:fs');
const path = require('node:path');

/**
 * Find index fragment files anywhere under `dir`. `pattern` is an exact
 * filename (default `index.json`) unless it starts with `*`, in which case
 * it's treated as a suffix match (e.g. `*.json` matches any per-platform
 * fragment named `release-index.<platform>.json`) — needed because CI
 * downloads multiple platforms' artifacts into one flattened directory and
 * same-named fragments would collide/overwrite each other on download.
 */
function findIndexFiles(dir, pattern = 'index.json') {
	const matches = pattern.startsWith('*')
		? (name) => name.endsWith(pattern.slice(1))
		: (name) => name === pattern;
	const out = [];
	const walk = (current) => {
		for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
			const abs = path.join(current, entry.name);
			if (entry.isDirectory()) walk(abs);
			else if (entry.isFile() && matches(entry.name)) out.push(abs);
		}
	};
	walk(dir);
	return out.sort();
}

/**
 * Union multiple single-platform release-index objects (schema v1, additive)
 * into one multi-platform index.
 *
 * - `channels` are merged (later inputs win on key collision).
 * - `releases[version].platforms` are merged per version (later inputs win
 *   on a platform-key collision).
 * - Scalar/object metadata (`schemaVersion`, `generatedAt`, `commit`,
 *   `compatibility`, per-release `publishedAt`/`requiresLauncher`) is taken
 *   from the first input that defines it; later inputs don't need to repeat
 *   it. `compatibility` is shallow-merged so per-platform compatibility
 *   entries from different inputs both survive.
 */
function mergeReleaseIndexes(indexes) {
	const merged = { channels: {}, releases: {} };
	for (const index of indexes) {
		if (index.schemaVersion !== undefined && merged.schemaVersion === undefined) {
			merged.schemaVersion = index.schemaVersion;
		}
		if (index.generatedAt && merged.generatedAt === undefined) merged.generatedAt = index.generatedAt;
		if (index.commit && merged.commit === undefined) merged.commit = index.commit;
		if (index.compatibility) {
			merged.compatibility = {
				...merged.compatibility,
				...index.compatibility,
				platforms: { ...merged.compatibility?.platforms, ...index.compatibility.platforms },
			};
		}
		Object.assign(merged.channels, index.channels || {});
		for (const [version, release] of Object.entries(index.releases || {})) {
			if (!merged.releases[version]) merged.releases[version] = { platforms: {} };
			const target = merged.releases[version];
			if (release.publishedAt && !target.publishedAt) target.publishedAt = release.publishedAt;
			if (release.requiresLauncher && !target.requiresLauncher) {
				target.requiresLauncher = release.requiresLauncher;
			}
			Object.assign(target.platforms, release.platforms || {});
		}
	}
	return merged;
}

/** Read + JSON.parse a list of index.json paths, then merge them. */
function mergeReleaseIndexFiles(files) {
	const indexes = files.map((file) => JSON.parse(fs.readFileSync(file, 'utf8')));
	return mergeReleaseIndexes(indexes);
}

module.exports = { findIndexFiles, mergeReleaseIndexes, mergeReleaseIndexFiles };
