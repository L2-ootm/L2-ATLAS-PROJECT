'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const cmds = require('../src/commands');
const { atlasInstallRoot, atlasStateHome } = require('../src/paths');
const { resolveRuntimeEntrypoint, launchRuntime } = require('../src/launcher');
const { compareVersions, updateLauncher } = require('../src/selfUpdate');
const { safeRelativeEntrypoint } = require('../src/release');
const { buildPlatformPackage } = require('../src/buildPlatformPackage');
const { materializePlatformPackage, platformPackageName } = require('../src/platformPackage');

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-lifecycle-${label}-`));
}

test('application install root is separate from ATLAS_HOME state', () => {
	const env = {
		LOCALAPPDATA: 'C:\\Users\\operator\\AppData\\Local',
		ATLAS_HOME: 'C:\\Users\\operator\\atlas-state'
	};
	assert.equal(atlasInstallRoot(env, 'win32'), path.resolve('C:\\Users\\operator\\AppData\\Local', 'atlas'));
	assert.equal(atlasStateHome(env), path.resolve(env.ATLAS_HOME));
	assert.notEqual(atlasInstallRoot(env, 'win32'), atlasStateHome(env));
});

test('runtime entrypoint resolves only inside the active immutable release', () => {
	const root = tempDir('root');
	const bundle = tempDir('bundle');
	fs.mkdirSync(path.join(bundle, 'bin'), { recursive: true });
	fs.writeFileSync(path.join(bundle, 'bin', 'runtime.js'), 'process.exit(0);\n');
	cmds.install(root, { from: bundle, version: '1.0.0', entrypoint: 'bin/runtime.js' });
	assert.equal(resolveRuntimeEntrypoint(root), path.join(root, 'versions', '1.0.0', 'bin', 'runtime.js'));
	assert.equal(launchRuntime(root, []), 0);
});

test('release entrypoint rejects absolute and traversal paths', () => {
	assert.equal(safeRelativeEntrypoint('bin/atlas.exe'), 'bin/atlas.exe');
	assert.throws(() => safeRelativeEntrypoint('../atlas.exe'), /unsafe/);
	assert.throws(() => safeRelativeEntrypoint('C:\\atlas.exe'), /relative/);
});

test('launcher semver comparison and npm self-update are deterministic', async () => {
	assert.equal(compareVersions('1.2.0', '1.1.9'), 1);
	assert.equal(compareVersions('1.2.0-beta.1', '1.2.0'), -1);
	let invocation = null;
	const result = await updateLauncher({
		currentVersion: '0.1.0',
		fetcher: async () => ({ ok: true, json: async () => ({ version: '0.2.0' }) }),
		spawn: (command, args) => {
			invocation = { command, args };
			return { status: 0 };
		}
	});
	assert.equal(result.updated, true);
	assert.deepEqual(invocation, {
		command: 'npm',
		args: ['install', '--global', '@l2/atlas@0.2.0']
	});
});

test('platform npm package materializes a verified release without touching ATLAS_HOME', () => {
	const installRoot = tempDir('install');
	const stateHome = tempDir('state');
	const bundle = tempDir('bundle');
	const packages = tempDir('packages');
	fs.mkdirSync(path.join(bundle, 'bin'), { recursive: true });
	fs.writeFileSync(path.join(bundle, 'bin', 'runtime.js'), 'process.exit(0);\n');
	const built = buildPlatformPackage({
		bundleDir: bundle,
		outDir: packages,
		version: '1.0.0',
		platform: `${process.platform}-${process.arch}`,
		entrypoint: 'bin/runtime.js'
	});
	const marker = path.join(stateHome, 'modules', 'operator-module', 'module.yaml');
	fs.mkdirSync(path.dirname(marker), { recursive: true });
	fs.writeFileSync(marker, 'id: operator-module\n');

	const result = materializePlatformPackage(installRoot, {
		env: { ATLAS_PLATFORM_PACKAGE_ROOT: built.packageDir, ATLAS_HOME: stateHome }
	});
	assert.equal(platformPackageName(), `@l2/atlas-${process.platform}-${process.arch}`);
	assert.equal(cmds.readCurrent(installRoot), '1.0.0');
	assert.equal(fs.readFileSync(marker, 'utf8'), 'id: operator-module\n');
	assert.equal(resolveRuntimeEntrypoint(installRoot), path.join(installRoot, 'versions', '1.0.0', 'bin', 'runtime.js'));
});
