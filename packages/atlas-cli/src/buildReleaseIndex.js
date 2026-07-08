'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const { hashFile } = require('./manifest');

function normalizeBaseUrl(baseUrl) {
	if (!baseUrl) return null;
	return baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
}

function artifactUrl(baseUrl, archiveName, archivePath) {
	const normalized = normalizeBaseUrl(baseUrl);
	if (normalized) return new URL(archiveName, normalized).href;
	return new URL(`file://${path.resolve(archivePath).replace(/\\/g, '/')}`).href;
}

function createArchive(bundleDir, archivePath) {
	fs.mkdirSync(path.dirname(archivePath), { recursive: true });
	const result = spawnSync('tar', ['-czf', archivePath, '-C', bundleDir, '.'], { encoding: 'utf8' });
	if (result.status !== 0) {
		throw new Error(`tar failed: ${result.stderr || result.stdout}`);
	}
}

function buildReleaseIndex(opts) {
	const bundleDir = path.resolve(opts.bundleDir || '');
	const outDir = path.resolve(opts.outDir || '');
	const version = opts.version;
	const platform = opts.platform;
	const channel = opts.channel || 'stable';

	if (!version) throw new Error('version is required');
	if (!platform) throw new Error('platform is required');
	if (!fs.existsSync(bundleDir)) throw new Error(`bundle directory not found: ${bundleDir}`);

	const archiveName = `atlas-${version}-${platform}.tar.gz`;
	const archivePath = path.join(outDir, archiveName);
	createArchive(bundleDir, archivePath);

	const index = {
		channels: { [channel]: version },
		releases: {
			[version]: {
				platforms: {
					[platform]: {
						url: artifactUrl(opts.baseUrl, archiveName, archivePath),
						sha256: hashFile(archivePath),
					},
				},
			},
		},
	};
	if (opts.commit) index.commit = opts.commit;

	const indexPath = path.join(outDir, opts.indexName || 'index.json');
	fs.writeFileSync(indexPath, JSON.stringify(index, null, 2) + '\n', 'utf8');
	return { version, platform, archivePath, indexPath, index };
}

module.exports = { buildReleaseIndex };
