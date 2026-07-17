'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const cmds = require('../src/commands');
const { hashFile } = require('../src/manifest');
const { buildReleaseIndex } = require('../src/buildReleaseIndex');
const { createTarGz } = require('../src/tarball');
const { verifyCleanInstall } = require('../src/verifyCleanInstall');

const packageJson = require('../package.json');

/** A throwaway staged "release bundle" directory with a couple of files. */
function stageBundle(dir, contents) {
	fs.mkdirSync(dir, { recursive: true });
	for (const [rel, text] of Object.entries(contents)) {
		const abs = path.join(dir, rel);
		fs.mkdirSync(path.dirname(abs), { recursive: true });
		fs.writeFileSync(abs, text, 'utf8');
	}
}

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-cli-${label}-`));
}

function makeTarball(sourceDir, outFile) {
	// Same engine the runtime uses (src/tarball.js) so the fixture cannot
	// diverge from production — and no system `tar`, which breaks on
	// Windows `C:\` paths.
	createTarGz(sourceDir, outFile);
}

function fileUrl(p) {
	return new URL(`file://${path.resolve(p).replace(/\\/g, '/')}`).href;
}

test('npm package metadata matches the public install contract', () => {
	assert.equal(packageJson.name, '@systemsl2/atlas');
	assert.notEqual(packageJson.private, true);
	assert.deepEqual(packageJson.bin, { atlas: 'bin/atlas.js' });

	const result = spawnSync(process.execPath, [path.join(__dirname, '..', 'bin', 'atlas.js')], {
		encoding: 'utf8',
		env: { ...process.env, ATLAS_INSTALL_ROOT: tempDir('metadata-home') }
	});
	assert.equal(result.status, 0);
	assert.match(result.stdout, /^usage: atlas /);
});

test('bin doctor --json emits machine-readable health reports', () => {
	const home = tempDir('home');
	const result = spawnSync(
		process.execPath,
		[path.join(__dirname, '..', 'bin', 'atlas.js'), 'doctor', '--json'],
		{ encoding: 'utf8', env: { ...process.env, ATLAS_INSTALL_ROOT: home } }
	);

	assert.equal(result.status, 1);
	assert.equal(result.stderr, '');
	const report = JSON.parse(result.stdout);
	assert.equal(report.ok, false);
	assert.equal(report.checks[0].name, 'current-version-set');
});

test('bin versions --json emits installed versions with current marker', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'binary-stub' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	const result = spawnSync(
		process.execPath,
		[path.join(__dirname, '..', 'bin', 'atlas.js'), 'versions', '--json'],
		{ encoding: 'utf8', env: { ...process.env, ATLAS_INSTALL_ROOT: home } }
	);

	assert.equal(result.status, 0);
	assert.equal(result.stderr, '');
	assert.deepEqual(JSON.parse(result.stdout), [{ version: '0.1.0', current: true }]);
});

test('bin command failures honor --json with a structured error object', () => {
	const home = tempDir('home');
	const result = spawnSync(
		process.execPath,
		[path.join(__dirname, '..', 'bin', 'atlas.js'), 'install', '--from', path.join(home, 'missing'), '--json'],
		{ encoding: 'utf8', env: { ...process.env, ATLAS_INSTALL_ROOT: home } }
	);

	assert.equal(result.status, 1);
	assert.equal(result.stderr, '');
	assert.deepEqual(JSON.parse(result.stdout), {
		error: {
			code: 'atlas_cli_error',
			message: `staged bundle not found: ${path.join(home, 'missing')}`
		}
	});
});

test('install stages a local bundle, sets current, writes a manifest', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'binary-stub', 'manifest-source.txt': 'v1' });

	const result = cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.equal(result.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
	assert.deepEqual(cmds.listVersions(home), ['0.1.0']);
	assert.ok(fs.existsSync(path.join(result.path, 'manifest.json')));
});

test('installing the same version twice refuses rather than clobbering', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'binary-stub' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.throws(() => cmds.install(home, { from: bundle, version: '0.1.0' }), cmds.CliError);
});

test('doctor reports healthy after install and unhealthy on checksum drift', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'binary-stub' });
	const { path: versionPath } = cmds.install(home, { from: bundle, version: '0.1.0' });

	let report = cmds.doctor(home);
	assert.equal(report.ok, true);

	// simulate drift: a component on disk no longer matches what was recorded
	fs.writeFileSync(path.join(versionPath, 'bin', 'atlas-gateway'), 'tampered', 'utf8');
	report = cmds.doctor(home);
	assert.equal(report.ok, false);
	const checksumCheck = report.checks.find((c) => c.name === 'manifest-checksum-match');
	assert.equal(checksumCheck.ok, false);
	assert.match(checksumCheck.detail, /atlas-gateway/);
});

test('update retains the previous version and rollback flips current back', () => {
	const home = tempDir('home');
	const bundleV1 = tempDir('bundle-v1');
	const bundleV2 = tempDir('bundle-v2');
	stageBundle(bundleV1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(bundleV2, { 'bin/atlas-gateway': 'v2' });

	cmds.install(home, { from: bundleV1, version: '0.1.0' });
	const updated = cmds.update(home, { from: bundleV2, version: '0.2.0' });

	assert.equal(updated.previous, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.2.0');
	assert.deepEqual(cmds.listVersions(home).sort(), ['0.1.0', '0.2.0']);

	const rolled = cmds.rollback(home, {});
	assert.equal(rolled.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
	// the newer version stays on disk — rollback is a pointer flip, not a delete
	assert.deepEqual(cmds.listVersions(home).sort(), ['0.1.0', '0.2.0']);
});

test('rollback with no prior version on record requires an explicit --to', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.throws(() => cmds.rollback(home, {}), cmds.CliError);
});

test('uninstall removes versions/current/install.json and doctor then reports no version', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	const result = cmds.uninstall(home, {});
	assert.ok(result.removed.length > 0);
	assert.equal(cmds.readCurrent(home), null);
	assert.deepEqual(cmds.listVersions(home), []);

	const report = cmds.doctor(home);
	assert.equal(report.ok, false);
});

test('full clean-machine cycle: install -> doctor -> update -> rollback -> uninstall', () => {
	const home = tempDir('home');
	const bundleV1 = tempDir('bundle-v1');
	const bundleV2 = tempDir('bundle-v2');
	stageBundle(bundleV1, { 'bin/atlas-gateway': 'v1', 'bin/atlas-tui': 'tui-v1' });
	stageBundle(bundleV2, { 'bin/atlas-gateway': 'v2', 'bin/atlas-tui': 'tui-v2' });

	cmds.install(home, { from: bundleV1, version: '0.1.0' });
	assert.equal(cmds.doctor(home).ok, true);

	cmds.update(home, { from: bundleV2, version: '0.2.0' });
	assert.equal(cmds.doctor(home).ok, true);
	assert.equal(cmds.readCurrent(home), '0.2.0');

	cmds.rollback(home, {});
	assert.equal(cmds.doctor(home).ok, true);
	assert.equal(cmds.readCurrent(home), '0.1.0');

	cmds.uninstall(home, {});
	assert.deepEqual(cmds.listVersions(home), []);
	assert.equal(fs.existsSync(home), true, 'uninstall (no --purge) leaves ATLAS_HOME itself intact');
});

test('install can fetch a release bundle from a manifest and verify checksum before extracting', async () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const releases = tempDir('releases');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1-from-release' });
	const archive = path.join(releases, 'atlas-0.1.0-win32-x64.tar.gz');
	makeTarball(bundle, archive);
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.1.0' },
			releases: {
				'0.1.0': {
					platforms: {
						'win32-x64': {
							url: fileUrl(archive),
							sha256: hashFile(archive)
						}
					}
				}
			}
		}),
		'utf8'
	);

	const result = await cmds.installFromRelease(home, {
		manifest: fileUrl(releaseIndex),
		channel: 'stable',
		platform: 'win32-x64'
	});

	assert.equal(result.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
	assert.equal(fs.readFileSync(path.join(result.path, 'bin', 'atlas-gateway'), 'utf8'), 'v1-from-release');
	assert.equal(cmds.doctor(home).ok, true);
});

test('release-index builder emits a consumable platform artifact and index', async () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const releases = tempDir('releases');
	stageBundle(bundle, {
		'bin/atlas-gateway': 'v1-from-builder',
		'bin/atlas.exe': 'runtime-entrypoint',
		'README.txt': 'release notes'
	});

	const result = buildReleaseIndex({
		bundleDir: bundle,
		outDir: releases,
		version: '0.1.0',
		platform: 'win32-x64',
		channel: 'stable',
		baseUrl: 'file://' + path.resolve(releases).replace(/\\/g, '/') + '/'
	});

	assert.equal(result.version, '0.1.0');
	assert.equal(result.platform, 'win32-x64');
	assert.equal(fs.existsSync(result.archivePath), true);
	assert.equal(fs.existsSync(result.indexPath), true);

	const index = JSON.parse(fs.readFileSync(result.indexPath, 'utf8'));
	const artifact = index.releases['0.1.0'].platforms['win32-x64'];
	assert.equal(index.channels.stable, '0.1.0');
	assert.equal(artifact.sha256, hashFile(result.archivePath));
	assert.match(artifact.url, /atlas-0\.1\.0-win32-x64\.tar\.gz$/);

	const installed = await cmds.installFromRelease(home, {
		manifest: fileUrl(result.indexPath),
		channel: 'stable',
		platform: 'win32-x64'
	});
	assert.equal(fs.readFileSync(path.join(installed.path, 'bin', 'atlas-gateway'), 'utf8'), 'v1-from-builder');
});

test('release install refuses a bundle whose checksum does not match the manifest', async () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const releases = tempDir('releases');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1-from-release' });
	const archive = path.join(releases, 'atlas-0.1.0-win32-x64.tar.gz');
	makeTarball(bundle, archive);
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.1.0' },
			releases: {
				'0.1.0': {
					platforms: {
						'win32-x64': {
							url: fileUrl(archive),
							sha256: 'not-the-real-hash'
						}
					}
				}
			}
		}),
		'utf8'
	);

	await assert.rejects(
		() => cmds.installFromRelease(home, {
			manifest: fileUrl(releaseIndex),
			channel: 'stable',
			platform: 'win32-x64'
		}),
		cmds.CliError
	);
	assert.deepEqual(cmds.listVersions(home), []);
});

test('update can fetch a release bundle from a manifest and keeps rollback metadata', async () => {
	const home = tempDir('home');
	const bundleV1 = tempDir('bundle-v1');
	const bundleV2 = tempDir('bundle-v2');
	const releases = tempDir('releases');
	stageBundle(bundleV1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(bundleV2, { 'bin/atlas-gateway': 'v2-from-release' });
	cmds.install(home, { from: bundleV1, version: '0.1.0' });

	const archive = path.join(releases, 'atlas-0.2.0-win32-x64.tar.gz');
	makeTarball(bundleV2, archive);
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.2.0' },
			releases: {
				'0.2.0': {
					platforms: {
						'win32-x64': {
							url: fileUrl(archive),
							sha256: hashFile(archive)
						}
					}
				}
			}
		}),
		'utf8'
	);

	const updated = await cmds.updateFromRelease(home, {
		manifest: fileUrl(releaseIndex),
		channel: 'stable',
		platform: 'win32-x64'
	});

	assert.equal(updated.previous, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.2.0');
	assert.equal(fs.readFileSync(path.join(updated.path, 'bin', 'atlas-gateway'), 'utf8'), 'v2-from-release');

	const rolled = cmds.rollback(home, {});
	assert.equal(rolled.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('clean install verifier runs install, update, rollback, uninstall against release manifests', async () => {
	const home = tempDir('home');
	const bundleV1 = tempDir('bundle-v1');
	const bundleV2 = tempDir('bundle-v2');
	const releases = tempDir('releases');
	stageBundle(bundleV1, { 'bin/atlas-gateway': 'v1', 'bin/atlas-tui': 'tui-v1' });
	stageBundle(bundleV2, { 'bin/atlas-gateway': 'v2', 'bin/atlas-tui': 'tui-v2' });

	const archiveV1 = path.join(releases, 'atlas-0.1.0-win32-x64.tar.gz');
	const archiveV2 = path.join(releases, 'atlas-0.2.0-win32-x64.tar.gz');
	makeTarball(bundleV1, archiveV1);
	makeTarball(bundleV2, archiveV2);
	const indexV1 = path.join(releases, 'index-v1.json');
	const indexV2 = path.join(releases, 'index-v2.json');
	fs.writeFileSync(
		indexV1,
		JSON.stringify({
			channels: { stable: '0.1.0' },
			releases: {
				'0.1.0': {
					platforms: { 'win32-x64': { url: fileUrl(archiveV1), sha256: hashFile(archiveV1) } }
				}
			}
		}),
		'utf8'
	);
	fs.writeFileSync(
		indexV2,
		JSON.stringify({
			channels: { stable: '0.2.0' },
			releases: {
				'0.2.0': {
					platforms: { 'win32-x64': { url: fileUrl(archiveV2), sha256: hashFile(archiveV2) } }
				}
			}
		}),
		'utf8'
	);

	const report = await verifyCleanInstall({
		home,
		manifest: fileUrl(indexV1),
		updateManifest: fileUrl(indexV2),
		channel: 'stable',
		platform: 'win32-x64'
	});

	assert.equal(report.ok, true);
	assert.deepEqual(report.steps.map((s) => s.name), [
		'install',
		'doctor-after-install',
		'update',
		'doctor-after-update',
		'rollback',
		'doctor-after-rollback',
		'uninstall',
		'doctor-after-uninstall'
	]);
	assert.equal(cmds.readCurrent(home), null);
	assert.deepEqual(cmds.listVersions(home), []);
});
