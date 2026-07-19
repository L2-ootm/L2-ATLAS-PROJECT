'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { buildReleaseIndex } = require('../src/buildReleaseIndex');
const { selectArtifact, satisfiesLauncherRequirement } = require('../src/release');
const { findIndexFiles, mergeReleaseIndexes, mergeReleaseIndexFiles } = require('../src/mergeReleaseIndexes');

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-release-index-${label}-`));
}

/** A throwaway staged "release bundle" directory with a couple of files. */
function stageBundle(dir, contents) {
	fs.mkdirSync(dir, { recursive: true });
	for (const [rel, text] of Object.entries(contents)) {
		const abs = path.join(dir, rel);
		fs.mkdirSync(path.dirname(abs), { recursive: true });
		fs.writeFileSync(abs, text, 'utf8');
	}
}

function buildFixture(overrides = {}) {
	const bundle = tempDir('bundle');
	const outDir = tempDir('out');
	stageBundle(bundle, {
		'bin/atlas.exe': 'runtime-entrypoint',
		'README.txt': 'release notes',
	});
	return buildReleaseIndex({
		bundleDir: bundle,
		outDir,
		version: '0.2.0',
		platform: 'win32-x64',
		channel: 'stable',
		...overrides,
	});
}

test('buildReleaseIndex emits schema v1 fields alongside the existing shape', () => {
	const { index, archivePath } = buildFixture({
		commit: 'abc123',
		requiresLauncher: '>=0.1.0 <0.4.0',
		compatibility: { launcher: { node: '>=20' }, platforms: { 'win32-x64': { minOs: '10.0.17763' } } },
	});

	// New top-level fields.
	assert.equal(index.schemaVersion, 1);
	assert.equal(typeof index.generatedAt, 'string');
	assert.doesNotThrow(() => new Date(index.generatedAt).toISOString());
	assert.equal(index.commit, 'abc123');
	assert.deepEqual(index.compatibility, {
		launcher: { node: '>=20' },
		platforms: { 'win32-x64': { minOs: '10.0.17763' } },
	});

	// New per-release fields.
	const release = index.releases['0.2.0'];
	assert.equal(typeof release.publishedAt, 'string');
	assert.equal(release.requiresLauncher, '>=0.1.0 <0.4.0');

	// New per-platform artifact field.
	const artifact = release.platforms['win32-x64'];
	assert.equal(artifact.size, fs.statSync(archivePath).size);
	assert.equal(typeof artifact.size, 'number');
	assert.ok(artifact.size > 0);

	// Existing fields untouched.
	assert.equal(index.channels.stable, '0.2.0');
	assert.equal(typeof artifact.url, 'string');
	assert.equal(typeof artifact.sha256, 'string');
	assert.equal(artifact.entrypoint, 'bin/atlas.exe');
});

test('buildReleaseIndex omits opt-in fields when not requested (still additive)', () => {
	const { index } = buildFixture();
	assert.equal(index.commit, undefined);
	assert.equal(index.compatibility, undefined);
	assert.equal(index.releases['0.2.0'].requiresLauncher, undefined);
	// Mandatory new fields are always present.
	assert.equal(index.schemaVersion, 1);
	assert.equal(typeof index.generatedAt, 'string');
});

test('selectArtifact resolves a v1-shaped index the same way it resolves the old shape', () => {
	const { index } = buildFixture();
	const selected = selectArtifact(index, { channel: 'stable', platform: 'win32-x64' });
	assert.equal(selected.version, '0.2.0');
	assert.equal(selected.platform, 'win32-x64');
	assert.equal(selected.artifact.entrypoint, 'bin/atlas.exe');
	assert.equal(selected.artifact.sha256, index.releases['0.2.0'].platforms['win32-x64'].sha256);
});

test('selectArtifact still resolves a hand-built pre-v1 index with no new fields', () => {
	const oldIndex = {
		channels: { stable: '0.1.0' },
		releases: {
			'0.1.0': {
				platforms: {
					'win32-x64': { url: 'file:///archive.tar.gz', sha256: 'deadbeef', entrypoint: 'bin/atlas.exe' },
				},
			},
		},
	};
	const selected = selectArtifact(oldIndex, { channel: 'stable', platform: 'win32-x64' });
	assert.equal(selected.version, '0.1.0');
	assert.equal(selected.artifact.sha256, 'deadbeef');
});

test('satisfiesLauncherRequirement evaluates space-separated AND ranges', () => {
	assert.equal(satisfiesLauncherRequirement('>=0.1.0 <0.4.0', '0.2.0'), true);
	assert.equal(satisfiesLauncherRequirement('>=0.1.0 <0.4.0', '0.4.0'), false);
	assert.equal(satisfiesLauncherRequirement('>=0.1.0 <0.4.0', '0.0.9'), false);
	assert.equal(satisfiesLauncherRequirement(undefined, '0.0.1'), true);
	assert.equal(satisfiesLauncherRequirement('=1.2.3', '1.2.3'), true);
});

test('selectArtifact enforces requiresLauncher only when a launcherVersion is supplied', () => {
	const { index } = buildFixture({ requiresLauncher: '>=0.1.0 <0.4.0' });

	// No launcherVersion passed: unknown/unchecked field is ignored, old callers unaffected.
	assert.doesNotThrow(() => selectArtifact(index, { channel: 'stable', platform: 'win32-x64' }));

	// launcherVersion satisfies the range.
	assert.doesNotThrow(() =>
		selectArtifact(index, { channel: 'stable', platform: 'win32-x64', launcherVersion: '0.2.0' })
	);

	// launcherVersion violates the range.
	assert.throws(
		() => selectArtifact(index, { channel: 'stable', platform: 'win32-x64', launcherVersion: '0.5.0' }),
		/requires launcher/
	);
});

test('mergeReleaseIndexes unions two single-platform indexes into one multi-platform index', () => {
	const winFixture = buildFixture({
		commit: 'sha-win',
		compatibility: { platforms: { 'win32-x64': { minOs: '10.0.17763' } } },
	});
	const macBundle = tempDir('mac-bundle');
	stageBundle(macBundle, { 'bin/atlas': 'runtime-entrypoint-mac' });
	const macOut = tempDir('mac-out');
	const macResult = buildReleaseIndex({
		bundleDir: macBundle,
		outDir: macOut,
		version: '0.2.0',
		platform: 'darwin-arm64',
		channel: 'stable',
		compatibility: { platforms: { 'darwin-arm64': { minOs: '13.0' } } },
	});

	const merged = mergeReleaseIndexes([winFixture.index, macResult.index]);

	assert.equal(merged.schemaVersion, 1);
	assert.equal(merged.commit, 'sha-win');
	assert.equal(merged.channels.stable, '0.2.0');
	assert.deepEqual(Object.keys(merged.releases['0.2.0'].platforms).sort(), ['darwin-arm64', 'win32-x64']);
	assert.equal(
		merged.releases['0.2.0'].platforms['win32-x64'].sha256,
		winFixture.index.releases['0.2.0'].platforms['win32-x64'].sha256
	);
	assert.equal(
		merged.releases['0.2.0'].platforms['darwin-arm64'].sha256,
		macResult.index.releases['0.2.0'].platforms['darwin-arm64'].sha256
	);
	assert.deepEqual(merged.compatibility.platforms, {
		'win32-x64': { minOs: '10.0.17763' },
		'darwin-arm64': { minOs: '13.0' },
	});

	// The merged index is itself a valid v1 index a consumer can select from.
	const selectedWin = selectArtifact(merged, { channel: 'stable', platform: 'win32-x64' });
	const selectedMac = selectArtifact(merged, { channel: 'stable', platform: 'darwin-arm64' });
	assert.equal(selectedWin.artifact.entrypoint, 'bin/atlas.exe');
	assert.equal(selectedMac.artifact.entrypoint, 'bin/atlas');
});

test('findIndexFiles + mergeReleaseIndexFiles merge index.json files discovered on disk', () => {
	const winFixture = buildFixture();
	const macBundle = tempDir('mac-bundle');
	stageBundle(macBundle, { 'bin/atlas': 'runtime-entrypoint-mac' });
	const macOut = tempDir('mac-out');
	buildReleaseIndex({
		bundleDir: macBundle,
		outDir: macOut,
		version: '0.2.0',
		platform: 'darwin-arm64',
		channel: 'stable',
	});

	// Simulate the CI layout: a parent directory containing one
	// per-platform index.json under each platform's own subdirectory.
	const root = tempDir('merge-root');
	fs.mkdirSync(path.join(root, 'win32-x64'), { recursive: true });
	fs.cpSync(winFixture.indexPath, path.join(root, 'win32-x64', 'index.json'));
	fs.mkdirSync(path.join(root, 'darwin-arm64'), { recursive: true });
	fs.cpSync(path.join(macOut, 'index.json'), path.join(root, 'darwin-arm64', 'index.json'));

	const files = findIndexFiles(root, 'index.json');
	assert.equal(files.length, 2);

	const merged = mergeReleaseIndexFiles(files);
	assert.deepEqual(Object.keys(merged.releases['0.2.0'].platforms).sort(), ['darwin-arm64', 'win32-x64']);
});
