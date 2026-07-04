'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const cmds = require('../src/commands');

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
