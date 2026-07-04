'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

/** sha256 of a single file, hex-encoded. */
function hashFile(filePath) {
	const data = fs.readFileSync(filePath);
	return crypto.createHash('sha256').update(data).digest('hex');
}

/** Recursively list every file under dir, relative paths, POSIX-separated. */
function listFiles(dir) {
	const out = [];
	const walk = (current, rel) => {
		for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
			const abs = path.join(current, entry.name);
			const relPath = rel ? `${rel}/${entry.name}` : entry.name;
			if (entry.isDirectory()) {
				walk(abs, relPath);
			} else if (entry.isFile()) {
				out.push(relPath);
			}
		}
	};
	walk(dir, '');
	return out.sort();
}

/**
 * Build a manifest.json for a staged version directory: per-file sha256,
 * so `atlas-cli doctor` can detect drift between what's installed and what
 * a component actually is on disk (closes the "stale gateway binary" gap
 * called out in WS-D).
 */
function buildManifest(versionDir, version, meta = {}) {
	const files = listFiles(versionDir).filter((f) => f !== 'manifest.json');
	const checksums = {};
	for (const rel of files) {
		checksums[rel] = hashFile(path.join(versionDir, rel));
	}
	return {
		version,
		buildDate: meta.buildDate || new Date().toISOString(),
		commit: meta.commit || null,
		checksums
	};
}

function readManifest(manifestPath) {
	return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

function writeManifest(manifestPath, manifest) {
	fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
}

/** Verify every file the manifest lists still matches its recorded checksum. */
function verifyManifest(versionDir, manifest) {
	const mismatches = [];
	const missing = [];
	for (const [rel, expected] of Object.entries(manifest.checksums)) {
		const abs = path.join(versionDir, rel);
		if (!fs.existsSync(abs)) {
			missing.push(rel);
			continue;
		}
		const actual = hashFile(abs);
		if (actual !== expected) mismatches.push(rel);
	}
	return { ok: mismatches.length === 0 && missing.length === 0, mismatches, missing };
}

module.exports = { hashFile, listFiles, buildManifest, readManifest, writeManifest, verifyManifest };
