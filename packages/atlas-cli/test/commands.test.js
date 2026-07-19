'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const cmds = require('../src/commands');
const { hashFile } = require('../src/manifest');
const { buildReleaseIndex } = require('../src/buildReleaseIndex');
const { createTarGz } = require('../src/tarball');
const { verifyCleanInstall } = require('../src/verifyCleanInstall');
const { resolveRollbackTarget } = require('../src/rollbackHistory');

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

test('doctor flags a launcher/runtime version mismatch only for npm-platform-package installs', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/runtime.js': 'process.exit(0);\n' });
	const launcherVersion = require('../package.json').version;

	cmds.installBundledPlatform(home, { from: bundle, version: launcherVersion, entrypoint: 'bin/runtime.js' });
	let report = cmds.doctor(home);
	let versionCheck = report.checks.find((c) => c.name === 'version-consistency');
	assert.ok(versionCheck);
	assert.equal(versionCheck.ok, true);

	cmds.uninstall(home, {});
	cmds.installBundledPlatform(home, { from: bundle, version: '0.0.1-mismatch', entrypoint: 'bin/runtime.js' });
	report = cmds.doctor(home);
	versionCheck = report.checks.find((c) => c.name === 'version-consistency');
	assert.equal(versionCheck.ok, false);
	assert.equal(report.ok, false);
});

test('doctor skips the version-consistency check for local-staged installs (arbitrary dev versions)', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'binary-stub' });
	cmds.install(home, { from: bundle, version: '9.9.9' });

	const report = cmds.doctor(home);
	assert.equal(report.checks.some((c) => c.name === 'version-consistency'), false);
	assert.equal(report.ok, true);
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

test('rollback rejects when already at the target version', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.throws(() => cmds.rollback(home, { to: '0.1.0' }), cmds.CliError);
});

test('rollback history chain supports multi-level yo-yo undo', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	const v3 = tempDir('v3');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	stageBundle(v3, { 'bin/atlas-gateway': 'v3' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });
	cmds.update(home, { from: v3, version: '0.3.0' });

	const r1 = cmds.rollback(home, {});
	assert.equal(r1.version, '0.2.0');
	assert.equal(r1.rolledBackFrom, '0.3.0');

	// history chain: rolling back again from 0.2.0 undoes the first rollback (yo-yo back to 0.3.0)
	const r2 = cmds.rollback(home, {});
	assert.equal(r2.version, '0.3.0');
	assert.equal(r2.rolledBackFrom, '0.2.0');

	const hist = cmds.rollbackHistory(home);
	assert.equal(hist.current, '0.3.0');
	assert.equal(hist.history.length, 2);
	assert.equal(hist.history[0].from, '0.2.0');
	assert.equal(hist.history[0].to, '0.3.0');
	assert.equal(hist.history[1].from, '0.3.0');
	assert.equal(hist.history[1].to, '0.2.0');
});

test('rollback --dry-run reports the plan without modifying any state', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	const result = cmds.rollback(home, { dryRun: true });
	assert.equal(result.dryRun, true);
	assert.equal(result.version, '0.1.0');
	assert.equal(result.rolledBackFrom, '0.2.0');
	assert.equal(result.manifestVerified, true);

	assert.equal(cmds.readCurrent(home), '0.2.0');
	assert.deepEqual(cmds.rollbackHistory(home).history, []);
});

test('rollback --no-verify skips pre-verification and is reflected in the result', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	const result = cmds.rollback(home, { noVerify: true });
	assert.equal(result.version, '0.1.0');
	assert.equal(result.manifestVerified, false);
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('rollback fails pre-verification when the target manifest was tampered with', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });

	const { path: v1Path } = cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	fs.writeFileSync(path.join(v1Path, 'bin', 'atlas-gateway'), 'tampered', 'utf8');
	assert.throws(() => cmds.rollback(home, {}), /pre-verification/);
	// nothing was flipped
	assert.equal(cmds.readCurrent(home), '0.2.0');
});

test('rollback reports a healthy post-rollback doctor check', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	const result = cmds.rollback(home, {});
	assert.equal(result.postHealthCheck, true);
	assert.ok(result.doctorReport);
	assert.equal(result.doctorReport.ok, true);
});

test('explicit --to overrides the rollback history chain', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	const v3 = tempDir('v3');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	stageBundle(v3, { 'bin/atlas-gateway': 'v3' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });
	cmds.update(home, { from: v3, version: '0.3.0' });

	const result = cmds.rollback(home, { to: '0.1.0' });
	assert.equal(result.version, '0.1.0');
	assert.equal(result.rolledBackFrom, '0.3.0');
});

test('rollback history is capped at 20 entries', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	for (let i = 2; i <= 23; i += 1) {
		const vDir = tempDir(`v${i}`);
		stageBundle(vDir, { 'bin/atlas-gateway': `v${i}` });
		cmds.update(home, { from: vDir, version: `0.${i}.0` });
		cmds.rollback(home, {});
	}

	const hist = cmds.rollbackHistory(home);
	assert.ok(hist.history.length <= 20);
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

/** A `.js` runtime-entrypoint stub, in the style of lifecycle.test.js's
 * `bin/runtime.js` fixture, that answers `db init` the way the real
 * atlas_runtime CLI does (see cli/main.py db_init: "applied X" per line or
 * "already up to date"). Returns the relative entrypoint path to pass as
 * `opts.entrypoint`. */
function writeMigrationStub(bundleDir, behavior) {
	const relPath = 'bin/runtime.js';
	const scriptPath = path.join(bundleDir, relPath);
	fs.mkdirSync(path.dirname(scriptPath), { recursive: true });
	const body = {
		'apply-one': "if (args[0] === 'db' && args[1] === 'init') { console.log('applied 0099_test.sql'); process.exit(0); }",
		'up-to-date': "if (args[0] === 'db' && args[1] === 'init') { console.log('already up to date'); process.exit(0); }",
		fail: "if (args[0] === 'db' && args[1] === 'init') { process.stderr.write('duplicate column: foo\\n'); process.exit(1); }"
	}[behavior];
	fs.writeFileSync(scriptPath, `'use strict';\nconst args = process.argv.slice(2);\n${body}\nprocess.exit(0);\n`, 'utf8');
	return relPath;
}

test('install runs migrations via the resolved runtime entrypoint and reports applied versions', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const entrypoint = writeMigrationStub(bundle, 'apply-one');

	const result = cmds.install(home, { from: bundle, version: '0.1.0', entrypoint });

	assert.ok(result.migrations);
	assert.equal(result.migrations.ok, true);
	assert.deepEqual(result.migrations.applied, ['0099_test.sql']);
});

test('install reports "already up to date" when no migrations are pending', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const entrypoint = writeMigrationStub(bundle, 'up-to-date');

	const result = cmds.install(home, { from: bundle, version: '0.1.0', entrypoint });

	assert.equal(result.migrations.ok, true);
	assert.deepEqual(result.migrations.applied, []);
	assert.equal(result.migrations.note, 'already up to date');
});

test('migration failure is reported but does not block install', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	const entrypoint = writeMigrationStub(bundle, 'fail');

	const result = cmds.install(home, { from: bundle, version: '0.1.0', entrypoint });

	assert.equal(result.migrations.ok, false);
	assert.match(result.migrations.error, /duplicate column/);
	// the install itself still succeeded — migration failure only warns
	assert.equal(result.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('install skips migrations when no runtime entrypoint is bundled', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'README.txt': 'no runtime here' });

	const result = cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.equal(result.migrations.ok, true);
	assert.deepEqual(result.migrations.applied, []);
	assert.match(result.migrations.note, /not found/);
});

test('update and rollback both run migrations against their respective target versions', () => {
	const home = tempDir('home');
	const bundleV1 = tempDir('bundle-v1');
	const bundleV2 = tempDir('bundle-v2');
	const entrypointV1 = writeMigrationStub(bundleV1, 'up-to-date');
	const entrypointV2 = writeMigrationStub(bundleV2, 'apply-one');

	cmds.install(home, { from: bundleV1, version: '0.1.0', entrypoint: entrypointV1 });
	const updated = cmds.update(home, { from: bundleV2, version: '0.2.0', entrypoint: entrypointV2 });
	assert.equal(updated.migrations.ok, true);
	assert.deepEqual(updated.migrations.applied, ['0099_test.sql']);

	const rolled = cmds.rollback(home, {});
	assert.equal(rolled.version, '0.1.0');
	assert.ok(rolled.migrations);
	assert.equal(rolled.migrations.ok, true);
});

// ---------------------------------------------------------------------------
// Phase 2 Track B2 — F17 §6 gap fixes
// ---------------------------------------------------------------------------

// Gap 1: install.json (`installedVersion`) is now the single source of truth
// for the current version, committed in one atomic write. The legacy
// `current` text file is only a best-effort mirror.

test('Gap1: readCurrent trusts install.json even when the legacy current file is stale or missing', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	// Simulate the legacy mirror write never having happened (crash between the
	// install.json commit and the best-effort `current` file refresh) — the
	// authoritative install.json commit already completed, so readCurrent must
	// still resolve correctly with no desync.
	fs.rmSync(path.join(home, 'current'), { force: true });
	assert.equal(cmds.readCurrent(home), '0.1.0');
	assert.equal(cmds.doctor(home).ok, true);
	assert.deepEqual(cmds.versions(home), [{ version: '0.1.0', current: true }]);

	// Simulate the mirror surviving with stale content from a previous version —
	// install.json must still win, proving there is no window where the two
	// disagree from atlas-cli's own point of view.
	fs.writeFileSync(path.join(home, 'current'), 'bogus-stale-version\n', 'utf8');
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('Gap1: rollback commits the pointer flip and history chain in one transaction, with no partial-write window', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1');
	const v2 = tempDir('v2');
	stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	cmds.rollback(home, {});

	// Delete the legacy mirror entirely (as if the crash happened right after
	// install.json committed but before the mirror write ran) and confirm the
	// rollback's target version + history are still fully intact via install.json alone.
	fs.rmSync(path.join(home, 'current'), { force: true });
	assert.equal(cmds.readCurrent(home), '0.1.0');
	const hist = cmds.rollbackHistory(home);
	assert.equal(hist.current, '0.1.0');
	assert.equal(hist.history.length, 1);
	assert.equal(hist.history[0].from, '0.2.0');
	assert.equal(hist.history[0].to, '0.1.0');
});

// Gap 2: `atlas versions prune --keep N`

test('Gap2: pruneVersions keeps the N most recent, dry-run reports without deleting', () => {
	const home = tempDir('home');
	const b1 = tempDir('b1'); stageBundle(b1, { 'bin/atlas-gateway': 'v1' });
	const b2 = tempDir('b2'); stageBundle(b2, { 'bin/atlas-gateway': 'v2' });
	const b3 = tempDir('b3'); stageBundle(b3, { 'bin/atlas-gateway': 'v3' });
	const b4 = tempDir('b4'); stageBundle(b4, { 'bin/atlas-gateway': 'v4' });

	cmds.install(home, { from: b1, version: '0.1.0' });
	cmds.update(home, { from: b2, version: '0.2.0' });
	cmds.update(home, { from: b3, version: '0.3.0' });
	cmds.update(home, { from: b4, version: '0.4.0' });

	const dry = cmds.pruneVersions(home, { keep: 2, dryRun: true });
	assert.equal(dry.dryRun, true);
	assert.deepEqual(dry.kept.sort(), ['0.3.0', '0.4.0']);
	assert.deepEqual(dry.removed.sort(), ['0.1.0', '0.2.0']);
	// nothing actually removed on disk
	assert.deepEqual(cmds.listVersions(home).sort(), ['0.1.0', '0.2.0', '0.3.0', '0.4.0']);

	const real = cmds.pruneVersions(home, { keep: 2 });
	assert.equal(real.dryRun, false);
	assert.deepEqual(real.removed.sort(), ['0.1.0', '0.2.0']);
	assert.deepEqual(cmds.listVersions(home).sort(), ['0.3.0', '0.4.0']);
});

test('Gap2: pruneVersions never removes the current version even if it falls outside the keep-N window', () => {
	const home = tempDir('home');
	const b1 = tempDir('b1'); stageBundle(b1, { 'bin/atlas-gateway': 'v1' });
	const b2 = tempDir('b2'); stageBundle(b2, { 'bin/atlas-gateway': 'v2' });
	const b3 = tempDir('b3'); stageBundle(b3, { 'bin/atlas-gateway': 'v3' });
	const b4 = tempDir('b4'); stageBundle(b4, { 'bin/atlas-gateway': 'v4' });

	cmds.install(home, { from: b1, version: '0.1.0' });
	cmds.update(home, { from: b2, version: '0.2.0' });
	cmds.update(home, { from: b3, version: '0.3.0' });
	cmds.update(home, { from: b4, version: '0.4.0' });

	// Jump back to the oldest version directly — it now sits outside a keep-2 window.
	cmds.use(home, '0.1.0');

	const result = cmds.pruneVersions(home, { keep: 2 });
	assert.equal(result.current, '0.1.0');
	assert.ok(result.kept.includes('0.1.0'), 'current version must always be kept');
	assert.deepEqual(result.kept.sort(), ['0.1.0', '0.3.0', '0.4.0']);
	assert.deepEqual(cmds.listVersions(home).sort(), ['0.1.0', '0.3.0', '0.4.0']);
});

test('Gap2: pruneVersions defaults keep to a sensible value when not specified', () => {
	const home = tempDir('home');
	const b1 = tempDir('b1'); stageBundle(b1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: b1, version: '0.1.0' });

	const result = cmds.pruneVersions(home, {});
	assert.ok(result.keep >= 1);
	assert.deepEqual(result.removed, []);
});

// Gap 3: `atlas use <version>`

test('Gap3: use directly activates an installed version without recording rollback history', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	const result = cmds.use(home, '0.1.0', {});
	assert.equal(result.version, '0.1.0');
	assert.equal(result.activatedFrom, '0.2.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');

	// `use` is a direct/neutral jump — it must not extend the rollback yo-yo chain.
	assert.deepEqual(cmds.rollbackHistory(home).history, []);
});

test('Gap3: use rejects a version that is not installed', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle'); stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.throws(() => cmds.use(home, '9.9.9', {}), cmds.CliError);
	assert.throws(() => cmds.use(home, undefined, {}), cmds.CliError);
});

test('Gap3: use rejects a version whose manifest checksum has been tampered with', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	const { path: v1Path } = cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	fs.writeFileSync(path.join(v1Path, 'bin', 'atlas-gateway'), 'tampered', 'utf8');
	assert.throws(() => cmds.use(home, '0.1.0', {}), /failed verification/);
	assert.equal(cmds.readCurrent(home), '0.2.0', 'nothing should be flipped on a failed check');
});

test('Gap3: use rejects re-activating the version that is already current', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle'); stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.throws(() => cmds.use(home, '0.1.0', {}), cmds.CliError);
});

test('Gap3: use --dry-run reports the plan without flipping the pointer', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	const result = cmds.use(home, '0.1.0', { dryRun: true });
	assert.equal(result.dryRun, true);
	assert.equal(result.version, '0.1.0');
	assert.equal(result.activatedFrom, '0.2.0');
	assert.equal(cmds.readCurrent(home), '0.2.0', 'dry-run must not modify state');
});

// Gap 4: orphaned version directory cleanup

test('Gap4: install auto-cleans an orphaned version directory left by a crash between copyDir and commit', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle'); stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });

	// Simulate the crash scenario directly: the version directory exists (a
	// prior copyDir succeeded) but install.json was never written, so nothing
	// ever attested to this being a completed install.
	const dest = path.join(home, 'versions', '0.1.0');
	fs.mkdirSync(dest, { recursive: true });
	fs.writeFileSync(path.join(dest, 'stale-partial-file.txt'), 'leftover from crashed copyDir', 'utf8');
	assert.equal(fs.existsSync(path.join(home, 'install.json')), false);

	const result = cmds.install(home, { from: bundle, version: '0.1.0' });
	assert.equal(result.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
	// the orphaned leftover file is gone — a full clean re-copy happened
	assert.equal(fs.existsSync(path.join(dest, 'stale-partial-file.txt')), false);
	assert.equal(fs.readFileSync(path.join(dest, 'bin', 'atlas-gateway'), 'utf8'), 'v1');
});

test('Gap4: update auto-cleans an orphaned version directory from a crashed prior update attempt', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	// Simulate a crashed update: the 0.2.0 dir was copied but install.json
	// still only knows about 0.1.0 — 0.2.0 was never committed.
	const dest = path.join(home, 'versions', '0.2.0');
	fs.mkdirSync(dest, { recursive: true });
	fs.writeFileSync(path.join(dest, 'stale.txt'), 'orphaned', 'utf8');

	const result = cmds.update(home, { from: v2, version: '0.2.0' });
	assert.equal(result.version, '0.2.0');
	assert.equal(cmds.readCurrent(home), '0.2.0');
	assert.equal(fs.existsSync(path.join(dest, 'stale.txt')), false);
});

test('Gap4: install still refuses a version directory that IS referenced by install.json (no silent clobber of a real install)', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	assert.throws(() => cmds.install(home, { from: v1, version: '0.1.0' }), cmds.CliError);
	// the real, committed install must remain untouched
	assert.equal(fs.readFileSync(path.join(home, 'versions', '0.1.0', 'bin', 'atlas-gateway'), 'utf8'), 'v1');
});

test('Gap4: a version still referenced only via previousVersion/rollbackHistory is not treated as orphaned', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });

	// 0.1.0 is retained on disk and referenced as previousVersion — attempting
	// to re-install over it must still refuse, not silently wipe it.
	assert.throws(() => cmds.install(home, { from: v1, version: '0.1.0' }), cmds.CliError);
	assert.equal(fs.readFileSync(path.join(home, 'versions', '0.1.0', 'bin', 'atlas-gateway'), 'utf8'), 'v1');
});

// ---------------------------------------------------------------------------
// Phase 3 Track D — F18 Option C: atomic version staging
// ---------------------------------------------------------------------------
//
// Before this, install()/update()/installBundledPlatform()/stageRelease() all
// copied (or extracted) directly into the final `versions/<version>/` path.
// A crash mid-copy left a partially-written directory sitting AT the real
// version path — indistinguishable, at a glance, from a real completed
// install. Gap 4's orphan cleanup could eventually delete it on the *next*
// attempt, but only after it had already been visible at the real path in
// the meantime. Now every write lands in `versions/<version>.atlas-staging/`
// first and only `fs.renameSync`'s to the real path once fully built — the
// partial-directory-at-the-real-path window is closed entirely, not just
// cleaned up after the fact. These tests assert that property directly
// (nothing ever appears at `dest` on failure), not just that cleanup
// eventually happens.

test('F18: a crash mid-copy during install leaves only a .atlas-staging dir, never a partial directory at the real version path', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1', 'nested/file.txt': 'data' });

	const originalCpSync = fs.cpSync;
	let cpCalls = 0;
	fs.cpSync = () => {
		cpCalls += 1;
		throw new Error('simulated crash mid-copy');
	};
	try {
		assert.throws(() => cmds.install(home, { from: bundle, version: '0.1.0' }), /simulated crash mid-copy/);
	} finally {
		fs.cpSync = originalCpSync;
	}
	assert.ok(cpCalls >= 1, 'the mocked copy must actually have been invoked');

	const dest = path.join(home, 'versions', '0.1.0');
	const staging = cmds.stagingDirFor(home, '0.1.0');
	assert.equal(fs.existsSync(dest), false, 'no partial directory must ever appear at the real version path');
	assert.equal(fs.existsSync(staging), false, 'the staging dir is cleaned up when the failure is caught synchronously');
	assert.deepEqual(cmds.listVersions(home), []);
	assert.equal(fs.existsSync(path.join(home, 'install.json')), false, 'nothing was ever committed');
});

test('F18: a crash mid-copy during update leaves the previous version untouched and no partial dir at the new version path', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	const originalCpSync = fs.cpSync;
	fs.cpSync = () => { throw new Error('simulated crash mid-copy'); };
	try {
		assert.throws(() => cmds.update(home, { from: v2, version: '0.2.0' }), /simulated crash mid-copy/);
	} finally {
		fs.cpSync = originalCpSync;
	}

	const dest = path.join(home, 'versions', '0.2.0');
	const staging = cmds.stagingDirFor(home, '0.2.0');
	assert.equal(fs.existsSync(dest), false, 'no partial directory must ever appear at the real version path');
	assert.equal(fs.existsSync(staging), false);
	assert.deepEqual(cmds.listVersions(home), ['0.1.0'], 'the already-installed version is untouched by the failed update');
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('F18: installBundledPlatform also stages atomically — a crash mid-copy never leaves a partial dir at the real version path', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/runtime.js': 'process.exit(0);\n' });

	const originalCpSync = fs.cpSync;
	fs.cpSync = () => { throw new Error('simulated crash mid-copy'); };
	try {
		assert.throws(
			() => cmds.installBundledPlatform(home, { from: bundle, version: '1.2.3', entrypoint: 'bin/runtime.js' }),
			/simulated crash mid-copy/
		);
	} finally {
		fs.cpSync = originalCpSync;
	}

	assert.equal(fs.existsSync(path.join(home, 'versions', '1.2.3')), false);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '1.2.3')), false);
	assert.equal(cmds.readCurrent(home), null);
});

test('F18: successful install and update end with the version at the real path and no leftover staging dir', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });

	const installed = cmds.install(home, { from: v1, version: '0.1.0' });
	assert.equal(installed.path, path.join(home, 'versions', '0.1.0'));
	assert.equal(fs.existsSync(installed.path), true);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.1.0')), false);

	const updated = cmds.update(home, { from: v2, version: '0.2.0' });
	assert.equal(fs.existsSync(updated.path), true);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.2.0')), false);
	assert.equal(cmds.readCurrent(home), '0.2.0');
});

test('F18: retry after a simulated crash cleans up the stale staging dir and succeeds', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });

	// Simulate a real process crash: a prior attempt wrote into
	// <version>.atlas-staging/ but the process died before fs.renameSync ever
	// ran, so the real `versions/0.1.0/` path was never touched — only the
	// staging dir exists, with partial leftover content.
	const staging = cmds.stagingDirFor(home, '0.1.0');
	fs.mkdirSync(staging, { recursive: true });
	fs.writeFileSync(path.join(staging, 'partial-leftover.txt'), 'from the crashed attempt', 'utf8');
	assert.equal(fs.existsSync(path.join(home, 'versions', '0.1.0')), false);

	const result = cmds.install(home, { from: bundle, version: '0.1.0' });

	assert.equal(result.version, '0.1.0');
	assert.equal(cmds.readCurrent(home), '0.1.0');
	assert.equal(fs.existsSync(staging), false, 'stale staging dir from the crashed attempt is cleaned up');
	assert.equal(fs.existsSync(path.join(result.path, 'partial-leftover.txt')), false, 'the clean re-stage does not carry over crash leftovers');
	assert.equal(fs.readFileSync(path.join(result.path, 'bin', 'atlas-gateway'), 'utf8'), 'v1');
});

test('F18: a leftover staging dir never surfaces in listVersions or doctor, even without a retry', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: bundle, version: '0.1.0' });

	// Drop an unrelated stale staging dir for a version that is never retried.
	const staleStaging = cmds.stagingDirFor(home, '9.9.9');
	fs.mkdirSync(staleStaging, { recursive: true });
	fs.writeFileSync(path.join(staleStaging, 'stub.txt'), 'never committed', 'utf8');

	assert.deepEqual(cmds.listVersions(home), ['0.1.0']);
	const report = cmds.doctor(home);
	const retained = report.checks.find((c) => c.name === 'retained-versions');
	assert.equal(retained.detail, '0.1.0');
});

// ---------------------------------------------------------------------------
// Phase 3 Track D — F19 P0 test gaps
// ---------------------------------------------------------------------------

test('F19 P0: installFromRelease cleans up and throws a clear CliError when the network fetch fails', async () => {
	const home = tempDir('home');
	const releases = tempDir('releases');
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.1.0' },
			releases: {
				'0.1.0': {
					platforms: {
						'win32-x64': {
							url: 'https://release-host.invalid/atlas-0.1.0-win32-x64.tar.gz',
							sha256: '0'.repeat(64)
						}
					}
				}
			}
		}),
		'utf8'
	);

	const originalFetch = global.fetch;
	global.fetch = async () => { throw new Error('simulated network failure: ECONNRESET'); };
	try {
		await assert.rejects(
			() => cmds.installFromRelease(home, {
				manifest: fileUrl(releaseIndex),
				channel: 'stable',
				platform: 'win32-x64'
			}),
			cmds.CliError
		);
	} finally {
		global.fetch = originalFetch;
	}

	assert.deepEqual(cmds.listVersions(home), []);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.1.0')), false, 'no staging dir left behind either');
	assert.equal(cmds.readCurrent(home), null);
});

test('F19 P0: updateFromRelease cleans up and throws a clear CliError when the network fetch fails, leaving the current version untouched', async () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	const releases = tempDir('releases');
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.2.0' },
			releases: {
				'0.2.0': {
					platforms: {
						'win32-x64': {
							url: 'https://release-host.invalid/atlas-0.2.0-win32-x64.tar.gz',
							sha256: '1'.repeat(64)
						}
					}
				}
			}
		}),
		'utf8'
	);

	const originalFetch = global.fetch;
	global.fetch = async () => { throw new Error('simulated network failure: ETIMEDOUT'); };
	try {
		await assert.rejects(
			() => cmds.updateFromRelease(home, {
				manifest: fileUrl(releaseIndex),
				channel: 'stable',
				platform: 'win32-x64'
			}),
			cmds.CliError
		);
	} finally {
		global.fetch = originalFetch;
	}

	assert.deepEqual(cmds.listVersions(home), ['0.1.0']);
	assert.equal(cmds.readCurrent(home), '0.1.0');
});

test('F19 P0: updateFromRelease cleans up on a corrupted/invalid tarball, leaving the previous version installed and listVersions clean', async () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	const releases = tempDir('releases');
	// Checksum matches (so the download-verification step passes), but the
	// bytes are not a gzip stream at all — extraction must fail.
	const archive = path.join(releases, 'atlas-0.2.0-win32-x64.tar.gz');
	fs.writeFileSync(archive, Buffer.from('this is not a valid gzip stream'));
	const releaseIndex = path.join(releases, 'index.json');
	fs.writeFileSync(
		releaseIndex,
		JSON.stringify({
			channels: { stable: '0.2.0' },
			releases: {
				'0.2.0': {
					platforms: {
						'win32-x64': { url: fileUrl(archive), sha256: hashFile(archive) }
					}
				}
			}
		}),
		'utf8'
	);

	await assert.rejects(
		() => cmds.updateFromRelease(home, {
			manifest: fileUrl(releaseIndex),
			channel: 'stable',
			platform: 'win32-x64'
		}),
		cmds.CliError
	);

	assert.deepEqual(cmds.listVersions(home), ['0.1.0'], 'the failed update leaves no trace of 0.2.0');
	assert.equal(fs.existsSync(path.join(home, 'versions', '0.2.0')), false);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.2.0')), false, 'staging dir is cleaned up too');
	assert.equal(cmds.readCurrent(home), '0.1.0', 'the previously installed version stays current');
});

test('F19 P0: rollback history persists across process restarts — re-reading install.json from disk still resolves the correct target', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	const v2 = tempDir('v2'); stageBundle(v2, { 'bin/atlas-gateway': 'v2' });
	const v3 = tempDir('v3'); stageBundle(v3, { 'bin/atlas-gateway': 'v3' });

	cmds.install(home, { from: v1, version: '0.1.0' });
	cmds.update(home, { from: v2, version: '0.2.0' });
	cmds.update(home, { from: v3, version: '0.3.0' });
	cmds.rollback(home, {}); // 0.3.0 -> 0.2.0, history: [{from: 0.3.0, to: 0.2.0}]

	// Simulate a brand-new process: read install.json straight off disk
	// instead of relying on anything held over from the calls above.
	const persisted = JSON.parse(fs.readFileSync(path.join(home, 'install.json'), 'utf8'));

	assert.equal(persisted.installedVersion, '0.2.0');
	assert.ok(Array.isArray(persisted.rollbackHistory));
	assert.equal(persisted.rollbackHistory.length, 1);
	assert.equal(persisted.rollbackHistory[0].from, '0.3.0');
	assert.equal(persisted.rollbackHistory[0].to, '0.2.0');

	// resolveRollbackTarget against the freshly-parsed state must still
	// resolve the yo-yo target, proving the chain round-trips through disk.
	assert.equal(resolveRollbackTarget(persisted, undefined), '0.3.0');

	// And a real rollback call against this same on-disk state confirms it end-to-end.
	const rolled = cmds.rollback(home, {});
	assert.equal(rolled.version, '0.3.0');
	assert.equal(rolled.rolledBackFrom, '0.2.0');
});

test('F19 P0: rollback history persistence also honors the legacy previousVersion fallback when read fresh from disk', () => {
	const home = tempDir('home');
	const v1 = tempDir('v1'); stageBundle(v1, { 'bin/atlas-gateway': 'v1' });
	cmds.install(home, { from: v1, version: '0.1.0' });

	// Simulate state written before rollbackHistory existed: no history
	// array, only the legacy single-slot previousVersion.
	const installFile = path.join(home, 'install.json');
	const state = JSON.parse(fs.readFileSync(installFile, 'utf8'));
	delete state.rollbackHistory;
	state.previousVersion = '0.0.9-legacy';
	fs.writeFileSync(installFile, JSON.stringify(state, null, 2) + '\n', 'utf8');

	const persisted = JSON.parse(fs.readFileSync(installFile, 'utf8'));
	assert.equal(resolveRollbackTarget(persisted, undefined), '0.0.9-legacy');
});

// ---------------------------------------------------------------------------
// Phase 3 Track D — F19 P1 (picked up as time allowed)
// ---------------------------------------------------------------------------

test('F19 P1: install surfaces the underlying error and cleans up when the install root cannot be written to (permission denied)', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });

	const originalMkdirSync = fs.mkdirSync;
	fs.mkdirSync = (target, ...rest) => {
		if (String(target).includes('versions')) {
			const err = new Error(`EACCES: permission denied, mkdir '${target}'`);
			err.code = 'EACCES';
			throw err;
		}
		return originalMkdirSync(target, ...rest);
	};
	try {
		assert.throws(() => cmds.install(home, { from: bundle, version: '0.1.0' }), /EACCES/);
	} finally {
		fs.mkdirSync = originalMkdirSync;
	}
	assert.deepEqual(cmds.listVersions(home), []);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.1.0')), false);
});

test('F19 P1: install cleans up on a simulated disk-full (ENOSPC) failure mid-copy', () => {
	const home = tempDir('home');
	const bundle = tempDir('bundle');
	stageBundle(bundle, { 'bin/atlas-gateway': 'v1' });

	const originalCpSync = fs.cpSync;
	fs.cpSync = () => {
		const err = new Error('ENOSPC: no space left on device, write');
		err.code = 'ENOSPC';
		throw err;
	};
	try {
		assert.throws(() => cmds.install(home, { from: bundle, version: '0.1.0' }), /ENOSPC/);
	} finally {
		fs.cpSync = originalCpSync;
	}
	assert.equal(fs.existsSync(path.join(home, 'versions', '0.1.0')), false);
	assert.equal(fs.existsSync(cmds.stagingDirFor(home, '0.1.0')), false);
	assert.deepEqual(cmds.listVersions(home), []);
});
